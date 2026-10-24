"""MET Norway (locationforecast/2.0) API client and normalizer."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from core.http import CancellationToken, HttpClient, get_default_http_client
from core.logging import get_logger
from data.wmo_conditions import met_symbol_to_wmo
from providers.base import (
    BaseWeatherClient,
    CurrentPoint,
    DailySummary,
    HourlyPoint,
    SourceForecast,
)

logger = get_logger("clients.met_norway")

MET_NORWAY_COVERAGE = {
    "temperature",
    "weather_code",
    "is_day",
    "wind_speed",
    "wind_direction",
    "wind_gusts",
    "humidity",
    "pressure_msl",
    "dew_point",
    "precipitation",
    "precipitation_probability",
    "uv_index",
}


class MetNorwayClient(BaseWeatherClient):
    """Network client for Norwegian Meteorological Institute (MET Norway)."""

    name: str = "met_norway"

    def __init__(self, http_client: HttpClient | None = None):
        self.http_client = http_client or get_default_http_client()

    def build_forecast_url(self, lat: float, lon: float) -> str:
        return f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat:.4f}&lon={lon:.4f}"

    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        cancel_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> SourceForecast | None:
        """Fetch compact locationforecast/2.0 from MET Norway."""
        url = self.build_forecast_url(lat, lon)
        start_ts = time.time()
        try:
            raw = self.http_client.fetch_json(url, token=cancel_token)
            if not isinstance(raw, dict) or "properties" not in raw:
                logger.warning("Invalid MET Norway response structure for %f, %f", lat, lon)
                return None
            return self.normalize_response(raw, lat=lat, lon=lon, fetched_at=start_ts)
        except Exception as e:
            logger.debug("MET Norway fetch failed for %f, %f: %s", lat, lon, e)
            return None

    def normalize_response(
        self,
        raw_data: dict[str, Any],
        lat: float,
        lon: float,
        fetched_at: float | None = None,
    ) -> SourceForecast:
        """Parse raw GeoJSON timeseries into unified SourceForecast model."""
        ts = fetched_at or time.time()
        props = raw_data.get("properties", {})
        timeseries = props.get("timeseries", [])

        if not timeseries:
            raise ValueError("MET Norway response contains empty timeseries")

        # First entry is current observation / short-term analysis
        first_entry = timeseries[0]
        f_details = first_entry.get("data", {}).get("instant", {}).get("details", {})
        f_next1 = first_entry.get("data", {}).get("next_1_hours", {})
        f_next6 = first_entry.get("data", {}).get("next_6_hours", {})
        f_next12 = first_entry.get("data", {}).get("next_12_hours", {})
        f_sym = (
            f_next1.get("summary", {}).get("symbol_code")
            or f_next6.get("summary", {}).get("symbol_code")
            or f_next12.get("summary", {}).get("symbol_code")
            or "clearsky_day"
        )
        f_wmo, f_is_day = met_symbol_to_wmo(f_sym)

        current = CurrentPoint(
            temp=float(f_details.get("air_temperature", 0.0)),
            weather_code=f_wmo,
            is_day=f_is_day,
            wind_speed=float(f_details.get("wind_speed", 0.0)),
            wind_direction=float(f_details.get("wind_from_direction", 0.0)),
            wind_gusts=float(f_details["wind_speed_of_gust"]) if f_details.get("wind_speed_of_gust") is not None else None,
            humidity=float(f_details["relative_humidity"]) if f_details.get("relative_humidity") is not None else None,
            pressure_msl=float(f_details["air_pressure_at_sea_level"]) if f_details.get("air_pressure_at_sea_level") is not None else None,
            precipitation=float(f_next1.get("details", {}).get("precipitation_amount", 0.0)),
            dew_point=float(f_details["dew_point_temperature"]) if f_details.get("dew_point_temperature") is not None else None,
            uv_index=float(f_details["ultraviolet_index_clear_sky"]) if f_details.get("ultraviolet_index_clear_sky") is not None else None,
            visibility=None,  # MET Norway does not provide visibility
        )

        hourly_list: list[HourlyPoint] = []
        days_agg: dict[str, list[HourlyPoint]] = defaultdict(list)

        for item in timeseries:
            t_raw = item.get("time", "")
            t_iso = f"{t_raw}Z" if not t_raw.endswith("Z") else t_raw
            dt_data = item.get("data", {})
            instant = dt_data.get("instant", {}).get("details", {})
            next1 = dt_data.get("next_1_hours", {})
            next6 = dt_data.get("next_6_hours", {})
            next12 = dt_data.get("next_12_hours", {})

            sym = (
                next1.get("summary", {}).get("symbol_code")
                or next6.get("summary", {}).get("symbol_code")
                or next12.get("summary", {}).get("symbol_code")
                or ""
            )
            wmo_code, is_day_val = met_symbol_to_wmo(sym, default_is_day=1)

            precip_amt = next1.get("details", {}).get("precipitation_amount")
            if precip_amt is None and next6:
                amt6 = next6.get("details", {}).get("precipitation_amount")
                precip_amt = (amt6 / 6.0) if amt6 is not None else None

            precip_prob = next1.get("details", {}).get("probability_of_precipitation")
            if precip_prob is None and next6:
                precip_prob = next6.get("details", {}).get("probability_of_precipitation")

            hp = HourlyPoint(
                time_iso=t_iso,
                temp=float(instant.get("air_temperature", 0.0)),
                weather_code=wmo_code,
                is_day=is_day_val,
                wind_speed=float(instant.get("wind_speed", 0.0)),
                wind_direction=float(instant.get("wind_from_direction", 0.0)),
                wind_gusts=float(instant["wind_speed_of_gust"]) if instant.get("wind_speed_of_gust") is not None else None,
                humidity=float(instant["relative_humidity"]) if instant.get("relative_humidity") is not None else None,
                pressure_msl=float(instant["air_pressure_at_sea_level"]) if instant.get("air_pressure_at_sea_level") is not None else None,
                precipitation=float(precip_amt) if precip_amt is not None else None,
                precipitation_probability=int(precip_prob) if precip_prob is not None else None,
                dew_point=float(instant["dew_point_temperature"]) if instant.get("dew_point_temperature") is not None else None,
                uv_index=float(instant["ultraviolet_index_clear_sky"]) if instant.get("ultraviolet_index_clear_sky") is not None else None,
                visibility=None,
            )
            hourly_list.append(hp)

            date_str = t_raw[:10]
            days_agg[date_str].append(hp)

        # Aggregate daily summaries from hourly slices
        daily_list: list[DailySummary] = []
        for d_str, points in sorted(days_agg.items()):
            if not points:
                continue
            temps = [p.temp for p in points]
            min_t = min(temps)
            max_t = max(temps)
            precip_sum = sum(p.precipitation or 0.0 for p in points)
            probs = [p.precipitation_probability for p in points if p.precipitation_probability is not None]
            max_prob = max(probs) if probs else None
            winds = [p.wind_speed for p in points]
            max_wind = max(winds) if winds else None
            gusts = [p.wind_gusts for p in points if p.wind_gusts is not None]
            max_gust = max(gusts) if gusts else None

            # Dominant weather code (majority vote across day hours)
            codes = [p.weather_code for p in points]
            rep_code = max(set(codes), key=codes.count)

            dirs = [p.wind_direction for p in points]
            dom_dir = dirs[len(dirs) // 2] if dirs else None

            daily_list.append(DailySummary(
                date_str=d_str,
                temp_min=min_t,
                temp_max=max_t,
                weather_code=rep_code,
                precipitation_sum=round(precip_sum, 1),
                precipitation_probability_max=max_prob,
                wind_speed_max=max_wind,
                wind_gusts_max=max_gust,
                wind_direction_dominant=dom_dir,
            ))

        depth = min(10, len(daily_list)) or 1

        return SourceForecast(
            source_name=self.name,
            fetched_at=ts,
            lat=lat,
            lon=lon,
            current=current,
            hourly=hourly_list,
            daily=daily_list,
            coverage=set(MET_NORWAY_COVERAGE),
            depth_days=depth,
            is_basic_mode=False,
        )
