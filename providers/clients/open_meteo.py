"""Open-Meteo API client with MSL pressure and normalized UTC forecasts."""

from __future__ import annotations

import time
import urllib.parse
from typing import Any

from core.http import CancellationToken, HttpClient, get_default_http_client
from core.logging import get_logger
from providers.base import (
    BaseWeatherClient,
    CurrentPoint,
    DailySummary,
    HourlyPoint,
    SearchResult,
    SourceForecast,
)

logger = get_logger("clients.open_meteo")

OPEN_METEO_COVERAGE = {
    "temperature",
    "feels_like",
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
    "visibility",
}


class OpenMeteoClient(BaseWeatherClient):
    """Network client for Open-Meteo Forecast and Geocoding APIs."""

    name: str = "open_meteo"

    def __init__(self, http_client: HttpClient | None = None):
        self.http_client = http_client or get_default_http_client()

    def build_forecast_url(
        self,
        lat: float,
        lon: float,
        model: str = "best_match",
        elevation: float | None = None,
        forecast_days: int = 10,
    ) -> str:
        """Construct query URL with explicit MSL pressure and UTC timezone."""
        model_param = urllib.parse.quote(str(model))
        elev_param = f"&elevation={float(elevation)}" if elevation is not None else ""

        return (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,"
            f"wind_speed_10m,wind_direction_10m,wind_gusts_10m,pressure_msl,dew_point_2m,precipitation,"
            f"uv_index,visibility"
            f"&hourly=temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,"
            f"precipitation_probability,precipitation,weather_code,pressure_msl,wind_speed_10m,"
            f"wind_direction_10m,wind_gusts_10m,uv_index,visibility,is_day"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
            f"apparent_temperature_min,uv_index_max,precipitation_sum,precipitation_probability_max,"
            f"wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant"
            f"&models={model_param}&cell_selection=land{elev_param}"
            f"&timezone=UTC&forecast_days={forecast_days}"
        )

    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        cancel_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> SourceForecast | None:
        """Fetch forecast from Open-Meteo and normalize."""
        city_info = city_info or {}
        model = kwargs.get("model") or city_info.get("model", "best_match")
        elevation = city_info.get("elevation") or city_info.get("altitude")

        url = self.build_forecast_url(lat, lon, model=model, elevation=elevation)
        start_ts = time.time()
        try:
            raw = self.http_client.fetch_json(url, token=cancel_token)
            if not isinstance(raw, dict) or "current" not in raw:
                logger.warning("Invalid Open-Meteo response structure for %f, %f", lat, lon)
                return None
            return self.normalize_response(raw, lat=lat, lon=lon, fetched_at=start_ts)
        except Exception as e:
            logger.debug("Open-Meteo fetch failed for %f, %f: %s", lat, lon, e)
            return None

    def normalize_response(
        self,
        raw_data: dict[str, Any],
        lat: float,
        lon: float,
        fetched_at: float | None = None,
    ) -> SourceForecast:
        """Parse raw Open-Meteo JSON into unified SourceForecast model."""
        ts = fetched_at or time.time()
        cur_raw = raw_data.get("current", {})
        hourly_raw = raw_data.get("hourly", {})
        daily_raw = raw_data.get("daily", {})

        current = CurrentPoint(
            temp=float(cur_raw.get("temperature_2m", 0.0)),
            weather_code=int(cur_raw.get("weather_code", 0)),
            is_day=int(cur_raw.get("is_day", 1)),
            wind_speed=float(cur_raw.get("wind_speed_10m", 0.0)),
            wind_direction=float(cur_raw.get("wind_direction_10m", 0.0)),
            wind_gusts=float(cur_raw["wind_gusts_10m"]) if cur_raw.get("wind_gusts_10m") is not None else None,
            humidity=float(cur_raw["relative_humidity_2m"]) if cur_raw.get("relative_humidity_2m") is not None else None,
            pressure_msl=float(cur_raw["pressure_msl"]) if cur_raw.get("pressure_msl") is not None else (
                float(cur_raw["surface_pressure"]) if cur_raw.get("surface_pressure") is not None else None
            ),
            precipitation=float(cur_raw["precipitation"]) if cur_raw.get("precipitation") is not None else 0.0,
            dew_point=float(cur_raw["dew_point_2m"]) if cur_raw.get("dew_point_2m") is not None else None,
            uv_index=float(cur_raw["uv_index"]) if cur_raw.get("uv_index") is not None else None,
            visibility=(float(cur_raw["visibility"]) / 1000.0) if cur_raw.get("visibility") is not None else None,
        )

        # Parse hourly
        hourly_list: list[HourlyPoint] = []
        h_times = hourly_raw.get("time", [])
        h_temps = hourly_raw.get("temperature_2m", [])
        h_codes = hourly_raw.get("weather_code", [])
        h_days = hourly_raw.get("is_day", [])
        h_winds = hourly_raw.get("wind_speed_10m", [])
        h_dirs = hourly_raw.get("wind_direction_10m", [])
        h_gusts = hourly_raw.get("wind_gusts_10m", [])
        h_hums = hourly_raw.get("relative_humidity_2m", [])
        h_press = hourly_raw.get("pressure_msl", hourly_raw.get("surface_pressure", []))
        h_precips = hourly_raw.get("precipitation", [])
        h_probs = hourly_raw.get("precipitation_probability", [])
        h_dews = hourly_raw.get("dew_point_2m", [])
        h_uvs = hourly_raw.get("uv_index", [])
        h_vis = hourly_raw.get("visibility", [])

        n_hours = len(h_times)
        for i in range(n_hours):
            t_raw = h_times[i]
            # Ensure UTC ISO format with Z
            t_iso = f"{t_raw}Z" if not t_raw.endswith("Z") else t_raw
            vis_val = (float(h_vis[i]) / 1000.0) if (i < len(h_vis) and h_vis[i] is not None) else None

            hourly_list.append(HourlyPoint(
                time_iso=t_iso,
                temp=float(h_temps[i]) if (i < len(h_temps) and h_temps[i] is not None) else 0.0,
                weather_code=int(h_codes[i]) if (i < len(h_codes) and h_codes[i] is not None) else 0,
                is_day=int(h_days[i]) if (i < len(h_days) and h_days[i] is not None) else 1,
                wind_speed=float(h_winds[i]) if (i < len(h_winds) and h_winds[i] is not None) else 0.0,
                wind_direction=float(h_dirs[i]) if (i < len(h_dirs) and h_dirs[i] is not None) else 0.0,
                wind_gusts=float(h_gusts[i]) if (i < len(h_gusts) and h_gusts[i] is not None) else None,
                humidity=float(h_hums[i]) if (i < len(h_hums) and h_hums[i] is not None) else None,
                pressure_msl=float(h_press[i]) if (i < len(h_press) and h_press[i] is not None) else None,
                precipitation=float(h_precips[i]) if (i < len(h_precips) and h_precips[i] is not None) else None,
                precipitation_probability=int(h_probs[i]) if (i < len(h_probs) and h_probs[i] is not None) else None,
                dew_point=float(h_dews[i]) if (i < len(h_dews) and h_dews[i] is not None) else None,
                uv_index=float(h_uvs[i]) if (i < len(h_uvs) and h_uvs[i] is not None) else None,
                visibility=vis_val,
            ))

        # Parse daily
        daily_list: list[DailySummary] = []
        d_times = daily_raw.get("time", [])
        d_min = daily_raw.get("temperature_2m_min", [])
        d_max = daily_raw.get("temperature_2m_max", [])
        d_code = daily_raw.get("weather_code", [])
        d_precip = daily_raw.get("precipitation_sum", [])
        d_prob = daily_raw.get("precipitation_probability_max", [])
        d_wind = daily_raw.get("wind_speed_10m_max", [])
        d_gust = daily_raw.get("wind_gusts_10m_max", [])
        d_dir = daily_raw.get("wind_direction_10m_dominant", [])

        n_days = len(d_times)
        for i in range(n_days):
            daily_list.append(DailySummary(
                date_str=str(d_times[i]),
                temp_min=float(d_min[i]) if (i < len(d_min) and d_min[i] is not None) else 0.0,
                temp_max=float(d_max[i]) if (i < len(d_max) and d_max[i] is not None) else 0.0,
                weather_code=int(d_code[i]) if (i < len(d_code) and d_code[i] is not None) else 0,
                precipitation_sum=float(d_precip[i]) if (i < len(d_precip) and d_precip[i] is not None) else None,
                precipitation_probability_max=int(d_prob[i]) if (i < len(d_prob) and d_prob[i] is not None) else None,
                wind_speed_max=float(d_wind[i]) if (i < len(d_wind) and d_wind[i] is not None) else None,
                wind_gusts_max=float(d_gust[i]) if (i < len(d_gust) and d_gust[i] is not None) else None,
                wind_direction_dominant=float(d_dir[i]) if (i < len(d_dir) and d_dir[i] is not None) else None,
            ))

        depth = min(10, n_days) if n_days else (min(10, len(hourly_list) // 24) or 1)

        return SourceForecast(
            source_name=self.name,
            fetched_at=ts,
            lat=lat,
            lon=lon,
            current=current,
            hourly=hourly_list,
            daily=daily_list,
            coverage=set(OPEN_METEO_COVERAGE),
            depth_days=depth,
            is_basic_mode=False,
        )

    def search_city(
        self,
        query: str,
        lang: str = "ru",
        count: int = 10,
        cancel_token: CancellationToken | None = None,
    ) -> list[SearchResult]:
        """Search cities via Open-Meteo Geocoding API."""
        clean_q = query.strip()
        if not clean_q:
            return []
        encoded = urllib.parse.quote(clean_q)
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count={count}&language={lang}&format=json"
        try:
            resp = self.http_client.fetch_json(url, token=cancel_token)
            if not isinstance(resp, dict) or "results" not in resp:
                return []
            results: list[SearchResult] = []
            for item in resp.get("results", []):
                results.append(SearchResult(
                    name=str(item.get("name", "")),
                    country=str(item.get("country", "")),
                    lat=float(item.get("latitude", 0.0)),
                    lon=float(item.get("longitude", 0.0)),
                    timezone=str(item.get("timezone", "auto")),
                    elevation=float(item["elevation"]) if item.get("elevation") is not None else None,
                    country_code=str(item.get("country_code", "")),
                    admin1=str(item.get("admin1", "")),
                ))
            return results
        except Exception as e:
            logger.debug("Geocoding lookup failed for '%s': %s", query, e)
            return []
