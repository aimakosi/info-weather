"""wttr.in (format=j1) API client and basic mode normalizer."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from core.http import CancellationToken, HttpClient, get_default_http_client
from core.logging import get_logger
from core.units import kmh_to_ms
from data.wmo_conditions import get_geo_timezone_offset_seconds, wttr_code_to_wmo
from providers.base import (
    BaseWeatherClient,
    CurrentPoint,
    DailySummary,
    HourlyPoint,
    SourceForecast,
)

logger = get_logger("clients.wttr")

WTTR_COVERAGE = {
    "temperature",
    "feels_like",
    "weather_code",
    "wind_speed",
    "wind_direction",
    "humidity",
    "pressure_msl",
    "precipitation",
    "precipitation_probability",
    "visibility",
}


class WttrClient(BaseWeatherClient):
    """Network client for wttr.in fallback weather service."""

    name: str = "wttr"

    def __init__(self, http_client: HttpClient | None = None):
        self.http_client = http_client or get_default_http_client()

    def build_forecast_url(self, lat: float, lon: float) -> str:
        return f"https://wttr.in/{lat:.4f},{lon:.4f}?format=j1"

    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        cancel_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> SourceForecast | None:
        """Fetch json from wttr.in and normalize to basic mode SourceForecast."""
        url = self.build_forecast_url(lat, lon)
        start_ts = time.time()
        try:
            raw = self.http_client.fetch_json(url, token=cancel_token)
            if not isinstance(raw, dict) or "current_condition" not in raw:
                logger.warning("Invalid wttr.in response structure for %f, %f", lat, lon)
                return None
            return self.normalize_response(raw, lat=lat, lon=lon, fetched_at=start_ts)
        except Exception as e:
            logger.debug("wttr.in fetch failed for %f, %f: %s", lat, lon, e)
            return None

    def normalize_response(
        self,
        raw_data: dict[str, Any],
        lat: float,
        lon: float,
        fetched_at: float | None = None,
    ) -> SourceForecast:
        """Parse raw wttr.in JSON format=j1 into unified SourceForecast model."""
        ts = fetched_at or time.time()
        cur_list = raw_data.get("current_condition", [])
        if not cur_list:
            raise ValueError("wttr.in response contains empty current_condition")
        cur_raw = cur_list[0]

        # wttr.in reports local clock times; convert to UTC via the location
        # offset so consensus aligns it with the UTC-based providers.
        utc_off_sec = get_geo_timezone_offset_seconds(lat, lon)

        def _opt_float(key: str) -> float | None:
            """wttr value as float, or None when the key is missing/blank."""
            v = cur_raw.get(key)
            try:
                return float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None

        temp_c = float(cur_raw.get("temp_C", 0.0))
        wind_kmh = float(cur_raw.get("windspeedKmph", 0.0))
        wind_ms = kmh_to_ms(wind_kmh)
        wind_deg = float(cur_raw.get("winddirDegree", 0.0))
        hum = _opt_float("humidity")
        press_hpa = _opt_float("pressure")
        precip_mm = _opt_float("precipMM") or 0.0
        vis_km = _opt_float("visibility")
        w_code = wttr_code_to_wmo(cur_raw.get("weatherCode", 113))

        current = CurrentPoint(
            temp=temp_c,
            weather_code=w_code,
            is_day=1,  # wttr current doesn't always flag day/night explicitly
            wind_speed=round(wind_ms, 1),
            wind_direction=wind_deg,
            wind_gusts=None,
            humidity=hum,
            pressure_msl=press_hpa,
            precipitation=precip_mm,
            dew_point=None,
            uv_index=None,  # Not used from wttr
            visibility=vis_km,
        )

        hourly_list: list[HourlyPoint] = []
        daily_list: list[DailySummary] = []

        weather_days = raw_data.get("weather", [])
        for day_item in weather_days:
            date_str = str(day_item.get("date", ""))
            min_c = float(day_item.get("mintempC", 0.0))
            max_c = float(day_item.get("maxtempC", 10.0))
            h_slices = day_item.get("hourly", [])

            # Aggregate daily codes & precip
            day_codes = []
            day_precip = 0.0
            day_probs = []

            for h in h_slices:
                raw_time = int(h.get("time", 0))  # e.g. 0, 300, 600, 1200, 1800, 2100
                h_val = raw_time // 100
                # wttr times are local; shift to UTC before labeling.
                dt_local = datetime.strptime(f"{date_str} {h_val:02d}:00", "%Y-%m-%d %H:%M")
                dt_utc = dt_local - timedelta(seconds=utc_off_sec)
                h_iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

                def _h_float(key: str, default: float | None = None) -> float | None:
                    v = h.get(key)
                    try:
                        return float(v) if v not in (None, "") else default
                    except (TypeError, ValueError):
                        return default

                h_temp = float(h.get("tempC", 0.0))
                h_code = wttr_code_to_wmo(h.get("weatherCode", 113))
                h_wms = kmh_to_ms(float(h.get("windspeedKmph", 0.0)))
                h_wdeg = float(h.get("winddirDegree", 0.0))
                h_hum = _h_float("humidity")
                h_press = _h_float("pressure")
                h_precip = _h_float("precipMM") or 0.0
                h_vis = _h_float("visibility")
                try:
                    rain_prob = int(h.get("chanceofrain", 0) or 0)
                    snow_prob = int(h.get("chanceofsnow", 0) or 0)
                except (TypeError, ValueError):
                    rain_prob, snow_prob = 0, 0
                h_prob = max(rain_prob, snow_prob)

                day_codes.append(h_code)
                day_precip += h_precip
                day_probs.append(h_prob)

                hourly_list.append(HourlyPoint(
                    time_iso=h_iso,
                    temp=h_temp,
                    weather_code=h_code,
                    is_day=1 if 6 <= h_val < 21 else 0,
                    wind_speed=round(h_wms, 1),
                    wind_direction=h_wdeg,
                    wind_gusts=None,
                    humidity=h_hum,
                    pressure_msl=h_press,
                    precipitation=h_precip,
                    precipitation_probability=h_prob,
                    dew_point=None,
                    uv_index=None,
                    visibility=h_vis,
                ))

            rep_code = max(set(day_codes), key=day_codes.count) if day_codes else w_code
            daily_list.append(DailySummary(
                date_str=date_str,  # local calendar day as reported by wttr
                temp_min=min_c,
                temp_max=max_c,
                weather_code=rep_code,
                precipitation_sum=round(day_precip, 1),
                precipitation_probability_max=max(day_probs) if day_probs else None,
            ))

        depth = min(3, len(daily_list)) or 1

        return SourceForecast(
            source_name=self.name,
            fetched_at=ts,
            lat=lat,
            lon=lon,
            current=current,
            hourly=hourly_list,
            daily=daily_list,
            coverage=set(WTTR_COVERAGE),
            depth_days=depth,
            is_basic_mode=True,
        )
