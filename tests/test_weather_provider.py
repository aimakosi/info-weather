"""Unit tests for WeatherProvider orchestrator and geocoding cascade."""

from __future__ import annotations

import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.cache import CacheManager
from models.weather import CurrentConditions
from providers.base import CurrentPoint, DailySummary, HourlyPoint, SearchResult, SourceForecast
from providers.weather import WeatherProvider


def make_test_source(name: str, temp: float, fetched_at: float | None = None) -> SourceForecast:
    ts = fetched_at if fetched_at is not None else time.time()
    return SourceForecast(
        source_name=name,
        fetched_at=ts,
        lat=55.75,
        lon=37.61,
        current=CurrentPoint(
            temp=temp,
            weather_code=0,
            is_day=1,
            wind_speed=3.0,
            wind_direction=180.0,
            humidity=70.0,
            pressure_msl=1013.25,
            precipitation=0.0,
            visibility=10.0,
            uv_index=2.0,
        ),
        hourly=[
            HourlyPoint(
                time_iso=f"2026-10-14T{h:02d}:00:00Z",
                temp=temp + (h % 3),
                weather_code=0,
                is_day=1,
                wind_speed=3.0,
                wind_direction=180.0,
                pressure_msl=1013.25,
                humidity=70.0,
                precipitation=0.0,
                precipitation_probability=0,
            )
            for h in range(24)
        ],
        daily=[
            DailySummary(
                date_str="2026-10-14",
                temp_min=temp - 4.0,
                temp_max=temp + 4.0,
                weather_code=0,
                precipitation_sum=0.0,
                precipitation_probability_max=0,
            )
        ],
        coverage={"temperature", "humidity", "pressure_msl", "wind_speed", "weather_code"},
        depth_days=7,
    )


class TestWeatherProvider(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="info_weather_prov_test_")
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_manager = CacheManager(cache_dir=self.cache_dir)

        self.mock_om = MagicMock()
        self.mock_met = MagicMock()
        self.mock_wttr = MagicMock()

        self.provider = WeatherProvider(
            cache_manager=self.cache_manager,
            open_meteo_client=self.mock_om,
            met_norway_client=self.mock_met,
            wttr_client=self.mock_wttr,
            lang="ru",
        )

    def tearDown(self):
        self.provider.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fetch_forecast_consensus_success_s3(self):
        # All 3 clients succeed with valid forecasts
        self.mock_om.fetch_forecast.return_value = make_test_source("open_meteo", temp=12.0)
        self.mock_met.fetch_forecast.return_value = make_test_source("met_norway", temp=10.0)
        self.mock_wttr.fetch_forecast.return_value = make_test_source("wttr", temp=14.0)

        fc = self.provider.fetch_forecast(
            lat=55.75,
            lon=37.61,
            city_name="Москва",
            country="Россия",
            force_refresh=True,
        )

        self.assertEqual(fc.consensus_level, "S3")
        self.assertTrue(fc.is_consensus)
        # Median of 12.0, 10.0, 14.0 is 12.0
        self.assertEqual(fc.current.temp, 12.0)

        # Check that forecast was cached
        cached = self.cache_manager.get_forecast(55.75, 37.61)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.get("consensus_level"), "S3")

        # Check that individual source responses were cached for Replay mode
        om_saved = self.cache_manager.get_source_response("open_meteo", 55.75, 37.61)
        self.assertIsNotNone(om_saved)

    def test_apply_network_config_updates_http_client(self):
        from core.config import ConfigManager

        cfg = ConfigManager(Path(self.temp_dir) / "config_network.json")
        provider = WeatherProvider(
            config_manager=cfg,
            cache_manager=self.cache_manager,
            open_meteo_client=self.mock_om,
            met_norway_client=self.mock_met,
            wttr_client=self.mock_wttr,
            lang="ru",
        )
        try:
            self.assertEqual(provider.http_client.default_timeout, 8.0)
            network = dict(cfg.get("network"))
            network.update({
                "timeout_seconds": 3.0,
                "dns_timeout_seconds": 0.0,
                "retries": 3,
                "prefer_ipv4": False,
            })
            cfg.set("network", network)
            provider.apply_network_config()
            self.assertEqual(provider.http_client.default_timeout, 3.0)
            self.assertEqual(provider.http_client.default_retries, 3)
            self.assertFalse(provider.http_client.prefer_ipv4)
            self.assertEqual(provider.http_client.dns_timeout, 0.0)
        finally:
            provider.close()

    def test_overall_fetch_timeout_uses_completed_sources(self):
        from core.config import ConfigManager

        cfg = ConfigManager(Path(self.temp_dir) / "config_timeout.json")
        network = dict(cfg.get("network"))
        network["fetch_timeout_seconds"] = 0.2
        cfg.set("network", network)

        fast = MagicMock()
        fast.fetch_forecast.return_value = make_test_source("open_meteo", temp=12.0)

        def slow_fetch(*args, **kwargs):
            time.sleep(0.6)
            return make_test_source("met_norway", temp=10.0)

        slow = MagicMock()
        slow.fetch_forecast.side_effect = slow_fetch
        slow2 = MagicMock()
        slow2.fetch_forecast.side_effect = slow_fetch

        provider = WeatherProvider(
            config_manager=cfg,
            cache_manager=self.cache_manager,
            open_meteo_client=fast,
            met_norway_client=slow,
            wttr_client=slow2,
            lang="ru",
        )
        try:
            started = time.monotonic()
            fc = provider.fetch_forecast(
                lat=55.75,
                lon=37.61,
                city_name="Москва",
                country="Россия",
                force_refresh=True,
            )
            elapsed = time.monotonic() - started
        finally:
            provider.close()

        # The overall deadline must stop waiting for hung providers...
        self.assertLess(elapsed, 0.55)
        # ...and still use the source that completed in time.
        self.assertEqual(fc.consensus_level, "S1")
        self.assertEqual(fc.source_name, "open_meteo")

    def test_fresh_cache_avoids_network(self):
        # Pre-populate cache with fresh forecast
        test_fc = make_test_source("open_meteo", temp=25.0)
        from providers.consensus import merge_source_forecasts
        merged = merge_source_forecasts([test_fc], lat=55.75, lon=37.61, now_ts=time.time())
        self.cache_manager.set_forecast(55.75, 37.61, merged)

        # Network clients should NOT be called
        self.mock_om.fetch_forecast.side_effect = RuntimeError("Network should not be called")

        fc = self.provider.fetch_forecast(
            lat=55.75,
            lon=37.61,
            city_name="Москва",
            country="Россия",
            force_refresh=False,
        )

        self.assertEqual(fc.current.temp, 25.0)
        self.mock_om.fetch_forecast.assert_not_called()

    def test_cascade_fallback_to_stale_cache_s0(self):
        # All network clients fail (e.g. offline)
        self.mock_om.fetch_forecast.return_value = None
        self.mock_met.fetch_forecast.return_value = None
        self.mock_wttr.fetch_forecast.return_value = None

        # Pre-populate stale cache
        stale_ts = time.time() - 100000.0  # long ago
        test_fc = make_test_source("open_meteo", temp=7.0, fetched_at=stale_ts)
        from providers.consensus import merge_source_forecasts
        merged = merge_source_forecasts([test_fc], lat=55.75, lon=37.61, now_ts=stale_ts)
        self.cache_manager.set_forecast(55.75, 37.61, merged)

        fc = self.provider.fetch_forecast(
            lat=55.75,
            lon=37.61,
            city_name="Москва",
            country="Россия",
            force_refresh=True,
        )

        self.assertEqual(fc.consensus_level, "S0")
        self.assertTrue(fc.is_offline)
        self.assertEqual(fc.current.temp, 7.0)
        self.assertIn("кэш", fc.status_text.lower())

    def test_cascade_fallback_to_era5_climatology_s0(self):
        # All network clients fail AND cache is empty
        self.mock_om.fetch_forecast.return_value = None
        self.mock_met.fetch_forecast.return_value = None
        self.mock_wttr.fetch_forecast.return_value = None

        fc = self.provider.fetch_forecast(
            lat=55.75,
            lon=37.61,
            city_name="Москва",
            country="Россия",
            force_refresh=True,
        )

        self.assertEqual(fc.consensus_level, "S0")
        self.assertTrue(fc.is_offline)
        self.assertIn("климатическ", fc.status_text.lower())
        self.assertIsNotNone(fc.current.temp)
        self.assertTrue(len(fc.daily) >= 5)

    def test_replay_mode(self):
        # Save historical responses into cache
        s1 = make_test_source("open_meteo", temp=16.0)
        s2 = make_test_source("met_norway", temp=14.0)

        self.cache_manager.save_source_response("open_meteo", 55.75, 37.61, s1.to_dict())
        self.cache_manager.save_source_response("met_norway", 55.75, 37.61, s2.to_dict())

        # Replay should re-synthesize without network
        replayed = self.provider.replay_forecast(lat=55.75, lon=37.61, city_name="Москва")
        self.assertIsNotNone(replayed)
        self.assertEqual(replayed.consensus_level, "S2")
        self.assertEqual(replayed.current.temp, 15.0)  # midpoint of 16 and 14

    def test_search_cities_cascade(self):
        # 1. Local search works for bundled cities
        results = self.provider.search_cities("Новокузнецк")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].name, "Новокузнецк")
        self.assertAlmostEqual(results[0].lat, 53.7557, places=2)

        # 2. Remote results merge and deduplicate
        self.mock_om.search_city.return_value = [
            SearchResult(
                name="Новокузнецк",
                country="Россия",
                lat=53.7557,
                lon=87.1099,
            ),
            SearchResult(
                name="NewCity",
                country="TestCountry",
                lat=10.0,
                lon=20.0,
            ),
        ]
        results_merged = self.provider.search_cities("NewCity")
        self.assertTrue(any(r.name == "NewCity" for r in results_merged))

        # 3. Geocache store verification
        cached_geo = self.cache_manager.get_geocache("NewCity")
        self.assertIsNotNone(cached_geo)
        self.assertTrue(len(cached_geo) > 0)

    def test_async_fetch(self):
        self.mock_om.fetch_forecast.return_value = make_test_source("open_meteo", temp=19.0)
        self.mock_met.fetch_forecast.return_value = None
        self.mock_wttr.fetch_forecast.return_value = None

        received = []

        def on_update(data):
            received.append(data)

        self.provider.fetch_forecast_async(
            lat=55.75,
            lon=37.61,
            city_name="Москва",
            force_refresh=True,
            callback=on_update,
        )

        # Wait up to 2 seconds for worker thread
        for _ in range(20):
            if received:
                break
            time.sleep(0.1)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].current.temp, 19.0)
        self.assertEqual(received[0].consensus_level, "S1")

    def test_multiple_rapid_async_fetches_no_deadlock(self):
        """Verify that rapid concurrent city switches do not exhaust worker threads or deadlock."""
        mock_source = SourceForecast(
            source_name="open_meteo",
            lat=55.0,
            lon=37.0,
            fetched_at=time.time(),
            current=CurrentConditions(temp=22.0, humidity=50, pressure_hpa=1013.0, wind_speed=3.0, weather_code=0),
            hourly=[],
            daily=[],
        )
        self.mock_om.fetch_forecast.return_value = mock_source

        received = []
        # Rapidly fire 5 async requests simulating fast city switching in UI
        for i in range(5):
            self.provider.fetch_forecast_async(
                lat=50.0 + i,
                lon=30.0 + i,
                city_name=f"City_{i}",
                force_refresh=True,
                callback=lambda d: received.append(d),
            )

        # Wait up to 3 seconds for the latest request to settle
        deadline = time.time() + 3.0
        while time.time() < deadline and not received:
            time.sleep(0.05)

        # Should finish without deadlock
        self.assertGreaterEqual(len(received), 1)

    def test_get_cached_forecast_hit(self):
        """Verify get_cached_forecast returns cached data when available."""
        cached_dict = {
            "city_name": "TestCity",
            "country": "TC",
            "lat": 55.75,
            "lon": 37.61,
            "cached_at": time.time(),
            "consensus_level": "S3",
            "current": {
                "temp": 15.0,
                "weather_code": 1,
            },
            "hourly": [],
            "daily": [],
        }
        self.cache_manager.set_forecast(55.75, 37.61, cached_dict)
        cached_fc = self.provider.get_cached_forecast(55.75, 37.61)
        self.assertIsNotNone(cached_fc)
        self.assertEqual(cached_fc.city_name, "TestCity")
        self.assertEqual(cached_fc.current.temp, 15.0)

    def test_get_cached_forecast_fallback_climatology(self):
        """Verify get_cached_forecast falls back to ERA5 climatology when no cache exists."""
        # Query coordinates that have never been cached
        fc = self.provider.get_cached_forecast(12.34, 56.78, city_name="UnknownCity")
        self.assertIsNotNone(fc)
        self.assertEqual(fc.consensus_level, "S0")
        self.assertTrue(fc.is_offline)

    def test_localize_city_multilingual(self):
        """Verify city and country name localization for Russian, English, and Ukrainian."""
        from data.resources import localize_city

        # 1. Moscow (RU -> EN -> UK)
        city_ru, country_ru = localize_city("Москва", 55.75, 37.61, "Россия", lang="ru")
        self.assertEqual(city_ru, "Москва")
        self.assertEqual(country_ru, "Россия")

        city_en, country_en = localize_city("Москва", 55.75, 37.61, "Россия", lang="en")
        self.assertEqual(city_en, "Moscow")
        self.assertEqual(country_en, "Russia")

        city_uk, country_uk = localize_city("Moscow", 55.75, 37.61, "Russia", lang="uk")
        self.assertEqual(city_uk, "Москва")
        self.assertEqual(country_uk, "Росія")

        # 2. Melbourne
        melb_ru, melb_c_ru = localize_city("Melbourne", -37.81, 144.96, "Australia", lang="ru")
        self.assertEqual(melb_ru, "Мельбурн")
        self.assertEqual(melb_c_ru, "Австралия")

        melb_en, melb_c_en = localize_city("Мельбурн", -37.81, 144.96, "Австралия", lang="en")
        self.assertEqual(melb_en, "Melbourne")
        self.assertEqual(melb_c_en, "Australia")

        # 3. Custom / test city is preserved
        cust_name, cust_country = localize_city("CustomCity", 55.75, 37.61, "TC", lang="en")
        self.assertEqual(cust_name, "CustomCity")
        self.assertEqual(cust_country, "TC")


if __name__ == "__main__":
    unittest.main()

