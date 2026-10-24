"""Unit tests for deterministic consensus merging rules in providers/consensus.py."""

import unittest

from providers.base import CurrentPoint, DailySummary, HourlyPoint, SourceForecast
from providers.consensus import (
    calc_majority,
    calc_median,
    merge_source_forecasts,
)


def make_mock_source(
    name: str,
    temp: float,
    weather_code: int = 1,
    wind_speed: float = 5.0,
    pressure: float = 1015.0,
    fetched_at: float = 1000.0,
    is_basic: bool = False,
    precip_prob: int = 0,
) -> SourceForecast:
    current = CurrentPoint(
        temp=temp,
        weather_code=weather_code,
        is_day=1,
        wind_speed=wind_speed,
        wind_direction=220.0,
        pressure_msl=pressure,
        humidity=60.0,
        precipitation=0.0,
    )
    hourly = [
        HourlyPoint(
            time_iso="2026-10-14T12:00:00Z",
            temp=temp,
            weather_code=weather_code,
            is_day=1,
            wind_speed=wind_speed,
            wind_direction=220.0,
            pressure_msl=pressure,
            humidity=60.0,
            precipitation_probability=precip_prob,
        )
    ]
    daily = [
        DailySummary(
            date_str="2026-10-14",
            temp_min=temp - 4.0,
            temp_max=temp + 4.0,
            weather_code=weather_code,
            precipitation_probability_max=precip_prob,
        )
    ]
    return SourceForecast(
        source_name=name,
        fetched_at=fetched_at,
        lat=50.0,
        lon=70.0,
        current=current,
        hourly=hourly,
        daily=daily,
        depth_days=3 if is_basic else 7,
        is_basic_mode=is_basic,
    )


class TestConsensus(unittest.TestCase):
    def test_calc_median(self):
        # Odd count: 3 items (10, 12, 15) -> median is 12
        items = [(10.0, "wttr"), (15.0, "met_norway"), (12.0, "open_meteo")]
        med, srcs = calc_median(items)
        self.assertEqual(med, 12.0)
        self.assertEqual(len(srcs), 3)

        # Even count: 2 items (10, 14) -> median is 12.0
        items_even = [(10.0, "open_meteo"), (14.0, "met_norway")]
        med_even, _ = calc_median(items_even)
        self.assertEqual(med_even, 12.0)

        # Single item
        med_single, s_single = calc_median([(20.5, "open_meteo")])
        self.assertEqual(med_single, 20.5)
        self.assertEqual(s_single, ["open_meteo"])

    def test_calc_majority(self):
        # Clear majority: two 3s and one 0 -> winner 3
        items = [(3, "open_meteo"), (0, "met_norway"), (3, "wttr")]
        win, srcs = calc_majority(items)
        self.assertEqual(win, 3)
        self.assertEqual(srcs, ["open_meteo", "wttr"])

        # Split tie: 0 from open_meteo, 2 from met_norway -> priority order chooses open_meteo
        tie_items = [(2, "met_norway"), (0, "open_meteo")]
        win_tie, _ = calc_majority(tie_items)
        self.assertEqual(win_tie, 0)

    def test_merge_s3_level(self):
        s1 = make_mock_source("open_meteo", temp=12.0, weather_code=2)
        s2 = make_mock_source("met_norway", temp=14.0, weather_code=2)
        s3 = make_mock_source("wttr", temp=10.0, weather_code=3)

        fc = merge_source_forecasts([s1, s2, s3], lat=50.0, lon=70.0, city_name="Karaganda", now_ts=1050.0)
        self.assertEqual(fc.consensus_level, "S3")
        self.assertTrue(fc.is_consensus)
        self.assertEqual(fc.sources_count, 3)
        # Median of (12, 14, 10) is 12.0
        self.assertEqual(fc.current.temp, 12.0)
        # Majority of (2, 2, 3) is 2
        self.assertEqual(fc.current.weather_code, 2)
        self.assertFalse(fc.current.low_confidence)

    def test_merge_s2_level(self):
        s1 = make_mock_source("open_meteo", temp=10.0)
        s2 = make_mock_source("met_norway", temp=14.0)

        fc = merge_source_forecasts([s1, s2], lat=50.0, lon=70.0, now_ts=1050.0)
        self.assertEqual(fc.consensus_level, "S2")
        self.assertTrue(fc.is_consensus)
        self.assertEqual(fc.current.temp, 12.0)  # midpoint (10 + 14)/2
        self.assertFalse(fc.current.low_confidence)

    def test_merge_s1_level_and_low_confidence(self):
        s1 = make_mock_source("open_meteo", temp=15.0)
        fc = merge_source_forecasts([s1], lat=50.0, lon=70.0, now_ts=1050.0)
        self.assertEqual(fc.consensus_level, "S1")
        self.assertFalse(fc.is_consensus)
        self.assertEqual(fc.current.temp, 15.0)
        self.assertTrue(fc.current.low_confidence)

    def test_freshness_gate_excludes_stale_source(self):
        # s1 is fresh (age 50s), s2 is stale (age 10000s > 7200s limit)
        s1 = make_mock_source("open_meteo", temp=18.0, fetched_at=19950.0)
        s2 = make_mock_source("met_norway", temp=10.0, fetched_at=10000.0)

        fc = merge_source_forecasts(
            [s1, s2],
            lat=50.0,
            lon=70.0,
            now_ts=20000.0,
            max_consensus_age_seconds=7200.0,
        )
        # s2 is excluded from consensus
        self.assertEqual(fc.consensus_level, "S1")
        self.assertEqual(fc.current.temp, 18.0)
        self.assertEqual(fc.sources, ["open_meteo"])

    def test_three_way_categorical_tie_prefers_open_meteo(self):
        s1 = make_mock_source("open_meteo", temp=15.0, weather_code=61)
        s2 = make_mock_source("met_norway", temp=15.0, weather_code=3)
        s3 = make_mock_source("wttr", temp=15.0, weather_code=1)

        fc = merge_source_forecasts([s1, s2, s3], lat=50.0, lon=70.0, now_ts=1050.0)
        # All three disagree: Open-Meteo priority tiebreaker wins
        self.assertEqual(fc.current.weather_code, 61)
        self.assertEqual(fc.daily[0].code, 61)

    def test_precip_probability_source_priority_not_median(self):
        s1 = make_mock_source("open_meteo", temp=15.0, precip_prob=80)
        s2 = make_mock_source("met_norway", temp=15.0, precip_prob=20)
        s3 = make_mock_source("wttr", temp=15.0, precip_prob=10)

        fc = merge_source_forecasts([s1, s2, s3], lat=50.0, lon=70.0, now_ts=1050.0)
        # Precipitation probability follows source priority (OM > MET > wttr), not median
        self.assertEqual(fc.daily[0].precip_prob_max, 80)

    def test_precip_probability_zero_from_top_source_wins(self):
        # A definitive 0% from Open-Meteo must beat 60% from wttr.in
        s1 = make_mock_source("open_meteo", temp=15.0, precip_prob=0)
        s2 = make_mock_source("met_norway", temp=15.0, precip_prob=20)
        s3 = make_mock_source("wttr", temp=15.0, precip_prob=60)

        fc = merge_source_forecasts([s1, s2, s3], lat=50.0, lon=70.0, now_ts=1050.0)
        self.assertEqual(fc.daily[0].precip_prob_max, 0)
        self.assertEqual(fc.hourly[0].precip_prob, 0)

    def test_daily_weekday_idx_matches_calendar(self):
        # 2026-10-14 is a Wednesday (weekday() == 2)
        s1 = make_mock_source("open_meteo", temp=15.0)
        fc = merge_source_forecasts([s1], lat=50.0, lon=70.0, now_ts=1050.0)
        self.assertEqual(fc.daily[0].weekday_idx, 2)

    def test_merged_hourly_keeps_utc_time_iso(self):
        s1 = make_mock_source("open_meteo", temp=15.0)
        fc = merge_source_forecasts([s1], lat=50.0, lon=70.0, now_ts=1050.0)
        self.assertEqual(fc.hourly[0].time_iso, "2026-10-14T12:00:00Z")


    def test_basic_mode_wttr_only(self):
        s3 = make_mock_source("wttr", temp=8.0, is_basic=True)
        fc = merge_source_forecasts([s3], lat=50.0, lon=70.0, now_ts=1050.0)
        self.assertIn("Базовый режим", fc.status_text)
        self.assertEqual(fc.current.temp, 8.0)


if __name__ == "__main__":
    unittest.main()


