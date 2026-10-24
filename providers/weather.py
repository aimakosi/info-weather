"""Meteorological coordinator and geocoding orchestrator (Stage 2.5 & Stage 2.9).

Handles:
- Parallel fetching from Open-Meteo, MET Norway, and wttr.in
- Request cancellation tokens and request_id tracking to avoid race conditions
- Cache-first check with configurable TTL
- Deterministic consensus synthesis (S3 -> S2 -> S1)
- Honest fallback cascade down to offline ERA5 climatology (S0)
- City geocoding search (Geocache -> Local major cities -> Open-Meteo Geocoding)
- Replay mode from cached source responses
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Callable

from core.cache import CacheManager
from core.config import ConfigManager
from core.http import DEFAULT_TOTAL_FETCH_TIMEOUT, CancellationToken, HttpClient
from core.i18n import t
from core.logging import get_logger
from data.fallback import get_offline_climatology_data
from data.resources import (
    find_city_by_name,
    localize_city,
    search_local_cities,
)
from models.weather import WeatherForecastData
from providers.base import SearchResult, SourceForecast
from providers.clients.met_norway import MetNorwayClient
from providers.clients.open_meteo import OpenMeteoClient
from providers.clients.wttr import WttrClient
from providers.consensus import merge_source_forecasts

logger = get_logger("providers.weather")


class WeatherProvider:
    """Coordinator managing caching, parallel network fetches, consensus merging, and geocoding."""

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        cache_manager: CacheManager | None = None,
        open_meteo_client: OpenMeteoClient | None = None,
        met_norway_client: MetNorwayClient | None = None,
        wttr_client: WttrClient | None = None,
        http_client: HttpClient | None = None,
        lang: str = "ru",
    ):
        self.config_manager = config_manager
        self.cache_manager = cache_manager or CacheManager()
        self.http_client = http_client or HttpClient.from_config(config_manager)
        self.open_meteo_client = open_meteo_client or OpenMeteoClient(http_client=self.http_client)
        self.met_norway_client = met_norway_client or MetNorwayClient(http_client=self.http_client)
        self.wttr_client = wttr_client or WttrClient(http_client=self.http_client)
        self.lang = lang

        self.on_data_updated: Callable[[WeatherForecastData], None] | None = None
        self._data_listeners: list[Callable[[WeatherForecastData], None]] = []
        self.on_error: Callable[[Exception], None] | None = None
        self.on_status_changed: Callable[[str], None] | None = None

        self._lock = threading.Lock()
        self._current_request_id = 0
        self._current_cancel_token: CancellationToken | None = None
        self._fetch_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="weather_client")

    def add_data_listener(self, cb: Callable[[WeatherForecastData], None]) -> None:
        """Register a callback for forecast update events."""
        with self._lock:
            if cb not in self._data_listeners:
                self._data_listeners.append(cb)

    def apply_network_config(self) -> None:
        """Re-apply timeout / retry / IPv4 settings without restarting the app."""
        if self.config_manager is not None:
            self.http_client.configure_from_config(self.config_manager)

    def close(self) -> None:
        """Shut down thread pool and cancel any in-flight requests."""
        with self._lock:
            if self._current_cancel_token:
                self._current_cancel_token.cancel()
        self._fetch_executor.shutdown(wait=False)

    def localize_city(
        self,
        name: str = "",
        lat: float | None = None,
        lon: float | None = None,
        country: str = "",
        lang: str | None = None,
    ) -> tuple[str, str]:
        """Localize city and country names according to the given or active language."""
        target_lang = lang or self.lang or "ru"
        return localize_city(name=name, lat=lat, lon=lon, country=country, lang=target_lang)

    def get_active_city_info(self) -> dict[str, Any]:
        """Resolve current active city coordinates and name from config or defaults."""
        if self.config_manager:
            curr_city = self.config_manager.get("current_city") or self.config_manager.get("home_city")
            cities = self.config_manager.get("cities", [])
            if curr_city and cities:
                for c in cities:
                    if isinstance(c, dict):
                        c_name = c.get("name", "")
                        c_id = c.get("id")
                        c_orig = c.get("original_name", "")
                        lat = float(c.get("lat", 0.0))
                        lon = float(c.get("lon", 0.0))

                        # Match by name, id, original_name, or coordinates
                        is_match = curr_city in (c_name, c_id, c_orig)
                        if not is_match and c_name:
                            info_curr = find_city_by_name(curr_city)
                            info_c = find_city_by_name(c_name)
                            if info_curr and info_c and info_curr == info_c:
                                is_match = True
                            elif info_curr and c.get("lat") is not None and c.get("lon") is not None:
                                is_match = (
                                    abs(float(info_curr.get("lat", 0.0)) - lat) < 0.15
                                    and abs(float(info_curr.get("lon", 0.0)) - lon) < 0.15
                                )
                        if is_match:
                            loc_name, loc_country = self.localize_city(
                                name=c_name,
                                lat=lat,
                                lon=lon,
                                country=c.get("country", ""),
                            )
                            return {
                                "name": loc_name,
                                "country": loc_country,
                                "lat": lat,
                                "lon": lon,
                                "timezone": c.get("timezone", ""),
                                "original_name": c_name,
                            }
            if cities and isinstance(cities[0], dict):
                c0 = cities[0]
                lat = float(c0.get("lat", 53.7167))
                lon = float(c0.get("lon", 91.4292))
                loc_name, loc_country = self.localize_city(
                    name=c0.get("name", "Абакан"),
                    lat=lat,
                    lon=lon,
                    country=c0.get("country", "Россия"),
                )
                return {
                    "name": loc_name,
                    "country": loc_country,
                    "lat": lat,
                    "lon": lon,
                    "timezone": c0.get("timezone", ""),
                    "original_name": c0.get("name", ""),
                }

        # Check local bundled resource as fallback default
        m_info = find_city_by_name("Абакан")
        if m_info:
            loc_name, loc_country = self.localize_city(
                name="Абакан",
                lat=float(m_info.get("lat", 53.7167)),
                lon=float(m_info.get("lon", 91.4292)),
            )
            return {
                "name": loc_name,
                "country": loc_country,
                "lat": float(m_info.get("lat", 53.7167)),
                "lon": float(m_info.get("lon", 91.4292)),
            }

        loc_name, loc_country = self.localize_city("Абакан", 53.7167, 91.4292, "Россия")
        return {
            "name": loc_name,
            "country": loc_country,
            "lat": 53.7167,
            "lon": 91.4292,
        }

    # ------------------------------------------------------------------------
    # Forecast Fetching & Consensus
    # ------------------------------------------------------------------------

    def get_cached_forecast(
        self,
        lat: float,
        lon: float,
        city_name: str = "",
        country: str = "",
    ) -> WeatherForecastData | None:
        """
        Instantly retrieve cached forecast (fresh or stale) from local storage without network I/O.
        If cache exists on disk, returns deserialized WeatherForecastData.
        If no cache exists at all, falls back to offline ERA5 climatology baseline so the widget
        never starts blank or frozen.
        """
        cached = self.cache_manager.get_forecast(lat, lon)
        if cached and isinstance(cached, dict):
            try:
                fc = WeatherForecastData.from_dict(cached)
                now = time.time()
                ttl = float(self.config_manager.get("update_interval_minutes", 60)) * 60.0 if self.config_manager else 1800.0
                cached_age = now - float(cached.get("cached_at", 0))
                if cached_age > ttl:
                    fc.is_offline = True
                    fc.status_text = t("status_cached_updating", _lang=self.lang)
                loc_name, loc_country = self.localize_city(
                    name=fc.city_name or city_name,
                    lat=lat,
                    lon=lon,
                    country=fc.country or country,
                )
                fc.city_name = loc_name
                fc.country = loc_country
                return fc
            except Exception as e:
                logger.warning("Failed to deserialize cached forecast: %s", e)

        # Fallback to offline climatology if no cache exists on disk
        try:
            loc_name, loc_country = self.localize_city(name=city_name, lat=lat, lon=lon, country=country)
            fc = get_offline_climatology_data(lat, lon, city_name=loc_name, country=loc_country, lang=self.lang)
            return fc
        except Exception as e:
            logger.warning("Failed to generate offline climatology fallback: %s", e)
            return None

    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        city_name: str = "",
        country: str = "",
        force_refresh: bool = False,
        cancel_token: CancellationToken | None = None,
        tz_name: str = "",
    ) -> WeatherForecastData:
        """
        Synchronously fetch and merge weather forecast for coordinates with cascade fallback.
        1. Check fresh cache (if not force_refresh)
        2. Parallel network fetch (Open-Meteo, MET Norway, wttr.in)
        3. Consensus synthesis (S3 -> S2 -> S1)
        4. Stale cache fallback (S0)
        5. ERA5 climatology fallback (S0)
        """
        loc_city, loc_country = self.localize_city(name=city_name, lat=lat, lon=lon, country=country)
        city_name = loc_city
        country = loc_country

        now = time.time()
        ttl = 1800.0  # 30 minutes default cache TTL
        if self.config_manager:
            ttl = float(self.config_manager.get("update_interval_minutes", 60)) * 60.0

        # 1. Fresh Cache Check
        if not force_refresh:
            cached = self.cache_manager.get_forecast(lat, lon)
            if cached and isinstance(cached, dict):
                cached_age = now - float(cached.get("cached_at", 0))
                if cached_age <= ttl:
                    logger.debug("Returning fresh cached forecast for (%s, %s), age=%.1fs", lat, lon, cached_age)
                    try:
                        fc = WeatherForecastData.from_dict(cached)
                        return fc
                    except Exception as e:
                        logger.warning("Failed to deserialize cached forecast: %s", e)

        # 2. Check Preferred Data Source from Config
        preferred_source = "consensus"
        if self.config_manager:
            preferred_source = self.config_manager.get("data_source", "consensus")

        # 3. Parallel Network Fetch
        source_forecasts: list[SourceForecast] = []
        city_info = {"name": city_name, "country": country}

        fetch_tasks: list[tuple[str, Callable[[], SourceForecast | None]]] = []
        if preferred_source in ("consensus", "open_meteo"):
            fetch_tasks.append(
                ("open_meteo", lambda: self.open_meteo_client.fetch_forecast(lat, lon, city_info, cancel_token=cancel_token))
            )
        if preferred_source in ("consensus", "met_norway"):
            fetch_tasks.append(
                ("met_norway", lambda: self.met_norway_client.fetch_forecast(lat, lon, city_info, cancel_token=cancel_token))
            )
        if preferred_source in ("consensus", "wttr"):
            fetch_tasks.append(
                ("wttr", lambda: self.wttr_client.fetch_forecast(lat, lon, city_info, cancel_token=cancel_token))
            )

        total_timeout = DEFAULT_TOTAL_FETCH_TIMEOUT
        if self.config_manager:
            try:
                total_timeout = float(
                    (self.config_manager.get("network", {}) or {}).get(
                        "fetch_timeout_seconds", total_timeout
                    )
                )
            except (TypeError, ValueError):
                total_timeout = DEFAULT_TOTAL_FETCH_TIMEOUT
        total_timeout = max(0.1, total_timeout)

        futures_map = {self._fetch_executor.submit(fn): name for name, fn in fetch_tasks}
        try:
            for fut in as_completed(futures_map, timeout=total_timeout):
                src_name = futures_map[fut]
                if cancel_token and cancel_token.is_cancelled:
                    logger.debug("Fetch cancelled while waiting for futures")
                    break
                try:
                    sf = fut.result()
                    if sf is not None:
                        source_forecasts.append(sf)
                        # Save individual source response for Replay Mode
                        # (persist=False: written to disk once after the merge)
                        self.cache_manager.save_source_response(
                            source=sf.source_name,
                            lat=lat,
                            lon=lon,
                            data=sf.to_dict(),
                            fetched_at=sf.fetched_at,
                            persist=False,
                        )
                except Exception as e:
                    logger.warning("Provider client '%s' failed for (%s, %s): %s", src_name, lat, lon, e)
        except FuturesTimeoutError:
            logger.warning(
                "Overall weather fetch timeout (%.1fs) reached; using %d completed source(s)",
                total_timeout,
                len(source_forecasts),
            )
            for fut in futures_map:
                fut.cancel()

        if cancel_token and cancel_token.is_cancelled:
            logger.debug("Fetch cancelled after gathering futures")
            raise InterruptedError("Weather fetch cancelled")

        # 4. Consensus Synthesis (S3 / S2 / S1)
        max_consensus_age = 7200.0  # 2 hours default
        if self.config_manager:
            max_consensus_age = float(self.config_manager.get("max_consensus_age_minutes", 120)) * 60.0

        if source_forecasts:
            try:
                fc = merge_source_forecasts(
                    sources=source_forecasts,
                    lat=lat,
                    lon=lon,
                    city_name=city_name,
                    country=country,
                    now_ts=now,
                    max_consensus_age_seconds=max_consensus_age,
                    lang=self.lang,
                    tz_name=tz_name,
                )
                self.cache_manager.set_forecast(lat, lon, fc)
                return fc
            except Exception as e:
                logger.error("Failed to merge source forecasts: %s", e)
                # Persist the saved source responses even when the merge failed
                self.cache_manager.persist()

        # 5. Stale Cache Fallback (S0)
        stale = self.cache_manager.get_forecast(lat, lon)
        if stale and isinstance(stale, dict):
            logger.info("Network unavailable: Falling back to stale cached forecast for (%s, %s)", lat, lon)
            try:
                fc = WeatherForecastData.from_dict(stale)
                fc.consensus_level = "S0"
                fc.is_offline = True
                fc.status_text = t("status_cached_offline", _lang=self.lang)
                return fc
            except Exception as e:
                logger.warning("Failed to deserialize stale cache: %s", e)

        # 6. Climate Normals Fallback (S0 - ERA5)
        logger.info("Network and cache unavailable: Falling back to ERA5 historical climatology for (%s, %s)", lat, lon)
        fc = get_offline_climatology_data(lat, lon, city_name=city_name, country=country, lang=self.lang)
        return fc

    def fetch_forecast_async(
        self,
        lat: float,
        lon: float,
        city_name: str = "",
        country: str = "",
        force_refresh: bool = False,
        callback: Callable[[WeatherForecastData], None] | None = None,
        tz_name: str = "",
    ) -> CancellationToken:
        """
        Asynchronously trigger weather fetch. Automatically cancels older in-flight requests.
        Returns the CancellationToken for this request.
        """
        with self._lock:
            self._current_request_id += 1
            req_id = self._current_request_id
            if self._current_cancel_token:
                self._current_cancel_token.cancel()
            token = CancellationToken()
            self._current_cancel_token = token

        def _worker():
            try:
                if self.on_status_changed:
                    self.on_status_changed("updating")

                data = self.fetch_forecast(
                    lat=lat,
                    lon=lon,
                    city_name=city_name,
                    country=country,
                    force_refresh=force_refresh,
                    cancel_token=token,
                    tz_name=tz_name,
                )

                with self._lock:
                    if req_id != self._current_request_id or token.is_cancelled:
                        logger.debug("Async response for req_id=%d discarded (current=%d)", req_id, self._current_request_id)
                        return

                if callback:
                    callback(data)
                with self._lock:
                    listeners = list(self._data_listeners)
                for listener in listeners:
                    try:
                        listener(data)
                    except Exception as e:
                        logger.warning("Data listener error: %s", e)

                if self.on_data_updated:
                    self.on_data_updated(data)

                if self.on_status_changed:
                    self.on_status_changed("idle")

            except InterruptedError:
                logger.debug("Async request %d cancelled", req_id)
            except Exception as e:
                logger.error("Async forecast failed for req_id=%d: %s", req_id, e)
                with self._lock:
                    if req_id == self._current_request_id and not token.is_cancelled:
                        if self.on_error:
                            self.on_error(e)
                        if self.on_status_changed:
                            self.on_status_changed("error")

        t = threading.Thread(target=_worker, name=f"weather_async_{req_id}", daemon=True)
        t.start()
        return token

    # ------------------------------------------------------------------------
    # Replay Mode
    # ------------------------------------------------------------------------

    def replay_forecast(
        self,
        lat: float,
        lon: float,
        city_name: str = "",
        country: str = "",
        tz_name: str = "",
    ) -> WeatherForecastData | None:
        """
        Synthesize consensus directly from recorded per-source responses in cache (no network).
        """
        loc_city, loc_country = self.localize_city(name=city_name, lat=lat, lon=lon, country=country)
        city_name = loc_city
        country = loc_country

        sources_dict = self.cache_manager.get_replay_sources(lat, lon)
        if not sources_dict:
            return None

        sources: list[SourceForecast] = []
        for src_name, entry in sources_dict.items():
            data = entry.get("data")
            if isinstance(data, dict):
                try:
                    sources.append(SourceForecast.from_dict(data))
                except Exception as e:
                    logger.warning("Failed to deserialize replay source '%s': %s", src_name, e)

        if not sources:
            return None

        return merge_source_forecasts(
            sources=sources,
            lat=lat,
            lon=lon,
            city_name=city_name,
            country=country,
            now_ts=time.time(),
            max_consensus_age_seconds=86400 * 30,  # relaxed age for historical replay
            lang=self.lang,
            tz_name=tz_name,
        )

    # ------------------------------------------------------------------------
    # City Search & Geocoding (Stage 2.9)
    # ------------------------------------------------------------------------

    def search_cities(
        self,
        query: str,
        cancel_token: CancellationToken | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Cascade geocoding search:
        1. Cache lookup
        2. Local major cities resource lookup
        3. Open-Meteo Geocoding API lookup
        4. Coordinate deduplication and geocache store
        """
        clean_q = query.strip()
        if not clean_q:
            return []

        # 1. Geocache Check
        cached = self.cache_manager.get_geocache(clean_q)
        if isinstance(cached, list) and cached:
            try:
                return [SearchResult.from_dict(item) for item in cached]
            except Exception as e:
                logger.warning("Failed to parse cached geocoding: %s", e)

        # 2. Local Resource Search
        local_results = search_local_cities(clean_q, lang=self.lang, limit=limit)

        # 3. Remote Search
        remote_results: list[SearchResult] = []
        if not (cancel_token and cancel_token.is_cancelled):
            try:
                remote_results = self.open_meteo_client.search_city(
                    query=clean_q,
                    lang=self.lang,
                    count=limit,
                    cancel_token=cancel_token,
                )

                # Fallback heuristics for common user typing patterns:
                # a) CamelCase without spaces: e.g. "OldSaybrook" -> "Old Saybrook"
                if not remote_results and not (cancel_token and cancel_token.is_cancelled):
                    import re
                    spaced_q = re.sub(r"([a-z\u0430-\u044f\u0451])([A-Z\u0410-\u042f\u0401])", r"\1 \2", clean_q)
                    if spaced_q != clean_q:
                        remote_results = self.open_meteo_client.search_city(
                            query=spaced_q,
                            lang=self.lang,
                            count=limit,
                            cancel_token=cancel_token,
                        )

                # b) Appended region or comma: e.g. "OldSaybrook Коннектикут" -> "Old Saybrook"
                if not remote_results and not (cancel_token and cancel_token.is_cancelled):
                    import re
                    parts = clean_q.split(",") if "," in clean_q else clean_q.rsplit(" ", 1)
                    if len(parts) > 1:
                        prefix = parts[0].strip()
                        pref_spaced = re.sub(r"([a-z\u0430-\u044f\u0451])([A-Z\u0410-\u042f\u0401])", r"\1 \2", prefix)
                        for cand in [pref_spaced, prefix]:
                            if cand and cand != clean_q and len(cand) >= 2:
                                remote_results = self.open_meteo_client.search_city(
                                    query=cand,
                                    lang=self.lang,
                                    count=limit,
                                    cancel_token=cancel_token,
                                )
                                if remote_results:
                                    break
            except Exception as e:
                logger.warning("Remote geocoding failed for '%s': %s", clean_q, e)

        # 4. Merge & Deduplicate by coordinates (lat, lon rounded to 2 decimals)
        seen_coords: set[tuple[float, float]] = set()
        merged: list[SearchResult] = []

        for sr in local_results:
            key = (round(sr.lat, 2), round(sr.lon, 2))
            if key not in seen_coords:
                seen_coords.add(key)
                merged.append(sr)

        for sr in remote_results:
            key = (round(sr.lat, 2), round(sr.lon, 2))
            if key not in seen_coords:
                seen_coords.add(key)
                merged.append(sr)

        final_results = merged[:limit]

        # 5. Store in Geocache
        if final_results:
            self.cache_manager.set_geocache(clean_q, [sr.to_dict() for sr in final_results])

        return final_results
