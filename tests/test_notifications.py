"""Unit tests for core/notifications.py event detection and deduplication."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.notifications import NotificationEngine
from data.fallback import get_offline_climatology_data


class TestNotifications(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "notif_state.json"
        self.engine = NotificationEngine(state_file=self.state_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_quiet_hours(self):
        # 23:30 is during quiet hours (22:00 to 08:00)
        dt_night = datetime(2026, 10, 14, 23, 30)
        self.assertTrue(self.engine.is_quiet_hours(dt_night, "22:00", "08:00"))

        # 07:15 is during quiet hours
        dt_early = datetime(2026, 10, 14, 7, 15)
        self.assertTrue(self.engine.is_quiet_hours(dt_early, "22:00", "08:00"))

        # 14:00 is daytime
        dt_day = datetime(2026, 10, 14, 14, 0)
        self.assertFalse(self.engine.is_quiet_hours(dt_day, "22:00", "08:00"))

    def test_event_detection_and_deduplication(self):
        fc = get_offline_climatology_data(55.75, 37.61, "Moscow")
        fc.current.wind_speed = 12.0  # triggers high_wind (> 10 m/s)
        fc.current.temp = -2.0  # triggers frost

        dt_noon = datetime(2026, 10, 14, 12, 0)
        events1 = self.engine.evaluate_forecast(fc, quiet_hours_enabled=False, now_dt=dt_noon)
        self.assertGreaterEqual(len(events1), 2)
        event_types = [e.event_type for e in events1]
        self.assertIn("frost", event_types)
        self.assertIn("high_wind", event_types)

        # Re-running immediately on same data must return EMPTY due to deduplication
        events2 = self.engine.evaluate_forecast(fc, quiet_hours_enabled=False, now_dt=dt_noon)
        self.assertEqual(len(events2), 0)

        # Persistence: create a new NotificationEngine instance pointing to same state file
        new_engine = NotificationEngine(state_file=self.state_file)
        events3 = new_engine.evaluate_forecast(fc, quiet_hours_enabled=False, now_dt=dt_noon)
        self.assertEqual(len(events3), 0)

    def test_precipitation_onset_detection(self):
        fc = get_offline_climatology_data(55.75, 37.61, "Moscow")
        fc.current.temp = 5.0
        fc.current.wind_speed = 3.0
        # Imminent rain in 1 hour
        if fc.hourly:
            fc.hourly[0].precip_amount = 2.5
            fc.hourly[0].precip_prob = 90
            fc.hourly[0].code = 61  # rain

        dt_noon = datetime(2026, 10, 14, 12, 0)
        events = self.engine.evaluate_forecast(fc, quiet_hours_enabled=False, now_dt=dt_noon)
        event_types = [e.event_type for e in events]
        self.assertIn("precipitation", event_types)

    def test_sharp_temperature_drop(self):
        fc = get_offline_climatology_data(55.75, 37.61, "Moscow")
        fc.current.temp = 15.0
        fc.current.wind_speed = 3.0
        # Sudden drop from 15 to 5 degrees within 12 hours
        if len(fc.hourly) >= 12:
            fc.hourly[0].temp = 15.0
            fc.hourly[11].temp = 5.0

        dt_noon = datetime(2026, 10, 14, 12, 0)
        events = self.engine.evaluate_forecast(fc, quiet_hours_enabled=False, now_dt=dt_noon)
        event_types = [e.event_type for e in events]
        self.assertIn("temp_drop", event_types)

    def test_precipitation_uses_hours_from_now(self):
        """With UTC timestamps present, alerts must look at the next hours, not the list head."""
        from models.weather import HourlyForecast

        fc = get_offline_climatology_data(55.75, 37.61, "Moscow")
        fc.current.temp = 5.0
        fc.current.wind_speed = 3.0
        fc.current.precipitation = 0.0

        # 24 hours of data starting today 00:00 UTC; rain only at 18:00-19:00 UTC
        fc.hourly = [
            HourlyForecast(
                time=f"{h:02d}:00",
                time_iso=f"2026-10-14T{h:02d}:00:00Z",
                temp=5.0,
                precip_prob=0,
                precip_amount=0.0,
            )
            for h in range(24)
        ]
        for h in (18, 19):
            fc.hourly[h].precip_prob = 80
            fc.hourly[h].precip_amount = 2.5
            fc.hourly[h].code = 61

        now_utc = datetime(2026, 10, 14, 17, 30, tzinfo=timezone.utc)
        events = self.engine.evaluate_forecast(fc, quiet_hours_enabled=False, now_dt=now_utc)
        precip_events = [e for e in events if e.event_type == "precipitation"]
        self.assertTrue(precip_events, "expected precipitation alert for 18:00 rain")
        self.assertIn("18:00", precip_events[0].body)

    def test_no_alert_when_only_past_hours_wet(self):
        """Rain that already happened (before now) must not raise a new alert."""
        from models.weather import HourlyForecast

        fc = get_offline_climatology_data(55.75, 37.61, "Moscow")
        fc.current.temp = 5.0
        fc.current.wind_speed = 3.0
        fc.current.precipitation = 0.0

        fc.hourly = [
            HourlyForecast(
                time=f"{h:02d}:00",
                time_iso=f"2026-10-14T{h:02d}:00:00Z",
                temp=5.0,
                precip_prob=0,
                precip_amount=0.0,
            )
            for h in range(24)
        ]
        # Rain at 05:00-06:00 UTC, now is 17:30 UTC
        for h in (5, 6):
            fc.hourly[h].precip_prob = 80
            fc.hourly[h].precip_amount = 2.5
            fc.hourly[h].code = 61

        now_utc = datetime(2026, 10, 14, 17, 30, tzinfo=timezone.utc)
        events = self.engine.evaluate_forecast(fc, quiet_hours_enabled=False, now_dt=now_utc)
        self.assertNotIn("precipitation", [e.event_type for e in events])

    def test_check_notifications_with_config_type_keys(self):
        """Проверка маппинга конфигурационных ключей (rain_snow_1h, strong_wind и т.д.)."""
        fc = get_offline_climatology_data(55.75, 37.61, "Moscow")
        fc.current.temp = -2.0
        fc.current.wind_speed = 12.0
        cfg = {
            "notifications": {
                "enabled": True,
                "types": {
                    "rain_snow_1h": False,
                    "frost": True,
                    "strong_wind": True,
                    "sharp_temperature_change": False,
                    "high_uv": False,
                },
                "quiet_hours": {"enabled": False},
            }
        }
        events = self.engine.check_notifications(current_fc=fc, config=cfg)
        event_types = [e.event_type for e in events]
        self.assertIn("frost", event_types)
        self.assertIn("high_wind", event_types)
        self.assertNotIn("precipitation", event_types)


if __name__ == "__main__":
    unittest.main()

