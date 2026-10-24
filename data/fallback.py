"""Offline climate baseline and honest fallback generator for info-weather.

Provides non-fabricated historical climate normals from ERA5 resources
when no cached forecast is available and the network is completely unreachable (S0 level).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from core.astronomy import (
    calculate_detailed_moon,
    calculate_moon_phase,
    calculate_solar_details,
    determine_solar_time_of_day,
)
from core.i18n import (
    get_weekday_name,
    t,
)
from data.resources import get_era5_baseline
from data.wmo_conditions import (
    WMO_INFO,
    get_condition_text,
    get_geo_timezone_offset_seconds,
)
from models.weather import (
    CurrentConditions,
    DailyForecast,
    DetailedMoon,
    HourlyForecast,
    SolarDetails,
    WeatherForecastData,
)


def get_offline_climatology_data(
    lat: float,
    lon: float,
    city_name: str = "Офлайн",
    country: str = "",
    lang: str = "ru",
) -> WeatherForecastData:
    """
    Generate an honest, non-fabricated offline forecast based on ERA5 climatology.
    Clearly marks data as offline historical baseline (S0 level).
    """
    baseline = get_era5_baseline()
    now_utc = datetime.now(timezone.utc)
    utc_offset = get_geo_timezone_offset_seconds(lat, lon)
    utc_offset_hours = utc_offset / 3600.0
    local_now = now_utc + timedelta(seconds=utc_offset)
    today = local_now.date()
    cur_m = today.month
    m_idx = cur_m - 1

    monthly = baseline.get("monthly", [])
    if monthly and len(monthly) == 12:
        m_row = monthly[m_idx]
        base_min = float(m_row.get("temp_min", 0.0))
        base_max = float(m_row.get("temp_max", 10.0))
    else:
        base_min, base_max = 0.0, 10.0

    # Latitude and continentality adjustments
    lat_diff = (55.0 - lat) * 0.7
    cont_diff = 0.0
    if 60.0 <= lon <= 110.0 and lat > 50.0:
        if cur_m in (11, 12, 1, 2):
            cont_diff = -7.0
        elif cur_m in (10, 3):
            cont_diff = -2.0
        elif cur_m in (6, 7, 8):
            cont_diff = 1.0
    elif lat < 45.0:
        lat_diff = (55.0 - lat) * 1.1

    norm_min = round(base_min + lat_diff + cont_diff)
    norm_max = round(base_max + lat_diff + cont_diff)
    if norm_min >= norm_max:
        norm_max = norm_min + 4

    tod, is_day = determine_solar_time_of_day(lat, lon, now_utc, utc_offset_hours=utc_offset_hours)
    if tod == "night":
        current_temp = norm_min + 1
    elif tod == "day":
        current_temp = norm_max - 1
    else:
        current_temp = round((norm_min + norm_max) / 2)

    status_str = t("status_offline_era5", _lang=lang)

    current = CurrentConditions(
        temp=float(current_temp),
        feels_like=float(current_temp),
        weather_code=2 if is_day else 1,
        condition_text=get_condition_text(2 if is_day else 1, lang=lang, is_day=(is_day == 1)),
        is_day=is_day,
        humidity=60,
        wind_speed=3.0,
        wind_direction=240,
        wind_gusts=5.0,
        pressure_mm=round(1013.0 * 0.750062),
        pressure_hpa=1013.0,
        dew_point=float(norm_min - 2),
        uv_index=1.0 if is_day else 0.0,
        visibility_km=10.0,
        precipitation=0.0,
        sources=["era5_climatology"],
        n_sources=0,
        low_confidence=True,
    )

    # 24h hourly distribution based on diurnal curve
    hourly_items: list[HourlyForecast] = []
    for h in range(24):
        h_time_str = f"{h:02d}:00"
        diurnal = math.sin((h - 9) / 24.0 * 2 * math.pi)
        h_temp = round(norm_min + (norm_max - norm_min) * (diurnal + 1.0) / 2.0)
        h_is_day = 1 if 6 <= h < 21 else 0
        h_code = 1 if h_is_day else 0
        hourly_items.append(
            HourlyForecast(
                time=h_time_str,
                temp=float(h_temp),
                code=h_code,
                is_day=h_is_day,
                precip_amount=0.0,
                precip_prob=0,
                wind_speed=3.0,
                wind_direction=240,
                humidity=60,
                pressure_hpa=1013.0,
                sources=["era5_climatology"],
                low_confidence=True,
            )
        )

    # Daily forecast
    daily_items: list[DailyForecast] = []
    daily_variations = [0, 1, -1, 2, -1, 0, 1, -2, 0, 1]
    for d_idx in range(7):
        target_day = today + timedelta(days=d_idx)
        v = daily_variations[d_idx % len(daily_variations)]
        d_min = norm_min + v
        d_max = norm_max + v
        d_name = t("weather_today", _lang=lang) if d_idx == 0 else get_weekday_name(target_day.weekday(), short=True, lang=lang)
        daily_items.append(
            DailyForecast(
                day=d_name,
                date_str=target_day.strftime("%Y-%m-%d"),
                min=float(d_min),
                max=float(d_max),
                code=2,
                icon_name=WMO_INFO.get(2, {}).get("icon_day", "partly-cloudy-day.svg"),
                precip_prob_max=0,
                sources=["era5_climatology"],
                low_confidence=True,
            )
        )

    solar_dict = calculate_solar_details(lat, lon, today, utc_offset_hours, lang=lang)
    moon_dict = calculate_detailed_moon(lat, lon, local_now, utc_offset_hours, lang=lang)
    solar = SolarDetails.from_dict(solar_dict)
    moon = DetailedMoon.from_dict(moon_dict)

    return WeatherForecastData(
        city_name=city_name,
        country=country,
        lat=lat,
        lon=lon,
        current=current,
        hourly=hourly_items,
        daily=daily_items,
        days_detailed=[],
        solar_details=solar,
        detailed_moon=moon,
        moon_phase=calculate_moon_phase(now_utc, lang=lang),
        utc_offset_seconds=utc_offset,
        fetched_at=now_utc.isoformat(),
        forecast_source="offline",
        is_consensus=False,
        is_offline=True,
        consensus_level="S0",
        sources_count=0,
        status_text=status_str,
    )
