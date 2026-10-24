"""Deterministic consensus merging engine for meteorological data (Stage 2.5).

Implements Step 2 & Step 3 of the specification:
- Freshness gate: source participation requires age <= max_consensus_age
- P-rule (presence): only sources providing the field participate
- Numeric fields: median across available fresh sources (midpoint if even count, priority on tie)
- Categorical fields (weather_code, wind_direction): majority vote with priority tiebreaker
- Precipitation probability: strictly provider priority (OM > MET > wttr)
- Derived fields (feels_like, dew_point, beaufort): computed post-merge via core.units
- Provenance tracking (sources, n_sources, low_confidence)
- Cascade level S3 -> S2 -> S1 -> S0
- Basic mode detection (when covered only by wttr.in)
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from core.astronomy import (
    calculate_detailed_moon,
    calculate_moon_phase,
    calculate_solar_details,
)
from core.i18n import get_weekday_name, t
from core.units import (
    calculate_apparent_temperature,
    calculate_dew_point,
)
from data.wmo_conditions import (
    WMO_INFO,
    get_condition_text,
    get_geo_timezone_offset_seconds,
    get_wind_direction_info,
)
from models.weather import (
    CurrentConditions,
    DailyForecast,
    DayDetailedForecast,
    DetailedMoon,
    HourlyForecast,
    SolarDetails,
    WeatherForecastData,
)
from providers.base import (
    DailySummary,
    HourlyPoint,
    SourceForecast,
)

SOURCE_PRIORITY = ["open_meteo", "met_norway", "wttr"]


def calc_median(items: list[tuple[float, str]]) -> tuple[float, list[str]]:
    """
    Calculate median of (value, source_name) tuples.
    Returns (median_value, participating_sources).
    """
    if not items:
        raise ValueError("Cannot calculate median of empty items")
    if len(items) == 1:
        return (items[0][0], [items[0][1]])

    # Sort primarily by value, secondarily by source priority
    def sort_key(pair: tuple[float, str]) -> tuple[float, int]:
        src = pair[1]
        prio = SOURCE_PRIORITY.index(src) if src in SOURCE_PRIORITY else 99
        return (pair[0], prio)

    sorted_items = sorted(items, key=sort_key)
    n = len(sorted_items)
    sources = [s for _, s in sorted_items]

    if n % 2 == 1:
        med_val = sorted_items[n // 2][0]
    else:
        # Even number of sources: average of the two middle values
        mid1 = sorted_items[n // 2 - 1][0]
        mid2 = sorted_items[n // 2][0]
        med_val = (mid1 + mid2) / 2.0

    return (round(med_val, 1), sources)


def calc_majority(items: list[tuple[Any, str]]) -> tuple[Any, list[str]]:
    """
    Majority vote for categorical fields with priority tiebreaker.
    """
    if not items:
        raise ValueError("Cannot calculate majority of empty items")
    if len(items) == 1:
        return (items[0][0], [items[0][1]])

    counts: dict[Any, int] = Counter(val for val, _ in items)
    max_count = max(counts.values())
    candidates = [val for val, count in counts.items() if count == max_count]

    if len(candidates) == 1:
        # Clear majority
        winning_val = candidates[0]
    else:
        # Tie: break by source priority
        winning_val = None
        for src in SOURCE_PRIORITY:
            for val, s in items:
                if s == src and val in candidates:
                    winning_val = val
                    break
            if winning_val is not None:
                break
        if winning_val is None:
            winning_val = candidates[0]

    sources = [s for val, s in items if val == winning_val]
    return (winning_val, sources)


def merge_source_forecasts(
    sources: list[SourceForecast],
    lat: float,
    lon: float,
    city_name: str = "",
    country: str = "",
    now_ts: float | None = None,
    max_consensus_age_seconds: float = 7200.0,  # 2 hours default
    lang: str = "ru",
    tz_name: str = "",
) -> WeatherForecastData:
    """
    Synthesize deterministic consensus WeatherForecastData from list of SourceForecasts.
    """
    now = now_ts or datetime.now(timezone.utc).timestamp()

    # 1. Freshness filter
    fresh_sources: list[SourceForecast] = []
    for s in sources:
        age = now - s.fetched_at
        if age <= max_consensus_age_seconds:
            fresh_sources.append(s)

    # Sort fresh sources by priority order
    fresh_sources.sort(
        key=lambda s: SOURCE_PRIORITY.index(s.source_name) if s.source_name in SOURCE_PRIORITY else 99
    )

    n_fresh = len(fresh_sources)
    if n_fresh >= 3:
        level = "S3"
    elif n_fresh == 2:
        level = "S2"
    elif n_fresh == 1:
        level = "S1"
    else:
        level = "S0"

    # If no fresh sources, use whatever sources exist or return empty
    active_sources = fresh_sources if fresh_sources else sources
    if not active_sources:
        raise ValueError("No source forecasts provided to merge")

    is_basic = all(s.is_basic_mode for s in active_sources)
    src_names = [s.source_name for s in active_sources]

    # ------------------------------------------------------------------------
    # Merge Current Conditions
    # ------------------------------------------------------------------------
    cur_temps = [(s.current.temp, s.source_name) for s in active_sources if s.current.temp is not None]
    cur_codes = [(s.current.weather_code, s.source_name) for s in active_sources if s.current.weather_code is not None]
    cur_winds = [(s.current.wind_speed, s.source_name) for s in active_sources if s.current.wind_speed is not None]
    cur_dirs = [(s.current.wind_direction, s.source_name) for s in active_sources if s.current.wind_direction is not None]
    cur_gusts = [(s.current.wind_gusts, s.source_name) for s in active_sources if s.current.wind_gusts is not None]
    cur_hums = [(s.current.humidity, s.source_name) for s in active_sources if s.current.humidity is not None]
    cur_press = [(s.current.pressure_msl, s.source_name) for s in active_sources if s.current.pressure_msl is not None]
    cur_precip = [(s.current.precipitation, s.source_name) for s in active_sources if s.current.precipitation is not None]
    cur_uvs = [(s.current.uv_index, s.source_name) for s in active_sources if s.current.uv_index is not None]
    cur_vis = [(s.current.visibility, s.source_name) for s in active_sources if s.current.visibility is not None]

    temp_val, t_srcs = calc_median(cur_temps) if cur_temps else (0.0, [])
    code_val, c_srcs = calc_majority(cur_codes) if cur_codes else (0, [])
    wind_val, _ = calc_median(cur_winds) if cur_winds else (0.0, [])
    dir_val, _ = calc_majority(cur_dirs) if cur_dirs else (0.0, [])
    gust_val, _ = calc_median(cur_gusts) if cur_gusts else (wind_val, [])
    hum_val, _ = calc_median(cur_hums) if cur_hums else (50.0, [])
    press_val, _ = calc_median(cur_press) if cur_press else (1013.0, [])
    precip_val, _ = calc_median(cur_precip) if cur_precip else (0.0, [])
    uv_val = cur_uvs[0][0] if cur_uvs else 0.0
    vis_val = cur_vis[0][0] if cur_vis else 10.0

    # Derived values
    feels_like_val = calculate_apparent_temperature(temp_val, wind_val, hum_val)
    dew_point_val = calculate_dew_point(temp_val, hum_val)
    wind_card, wind_desc = get_wind_direction_info(dir_val, lang=lang)

    # Day/Night determination
    day_votes = [s.current.is_day for s in active_sources if s.current.is_day is not None]
    is_day_val = 1 if (sum(day_votes) >= len(day_votes) / 2.0) else 0

    current = CurrentConditions(
        temp=temp_val,
        feels_like=feels_like_val,
        humidity=hum_val,
        dew_point=dew_point_val,
        wind_speed=wind_val,
        wind_gusts=gust_val,
        wind_direction=dir_val,
        wind_cardinal=wind_card,
        wind_desc=wind_desc,
        pressure_mm=round(press_val * 0.750062),
        pressure_hpa=press_val,
        uv_index=uv_val,
        visibility_km=vis_val,
        precipitation=precip_val,
        is_day=is_day_val,
        weather_code=code_val,
        condition_text=get_condition_text(code_val, lang=lang, is_day=(is_day_val == 1)),
        sources=src_names,
        n_sources=len(active_sources),
        low_confidence=(len(t_srcs) < 2),
    )

    # ------------------------------------------------------------------------
    # Merge Hourly Points
    # ------------------------------------------------------------------------
    hourly_by_time: dict[str, list[tuple[HourlyPoint, str]]] = defaultdict(list)
    for s in active_sources:
        for hp in s.hourly:
            hourly_by_time[hp.time_iso].append((hp, s.source_name))

    merged_hourly: list[HourlyForecast] = []
    for t_iso in sorted(hourly_by_time.keys()):
        hp_list = hourly_by_time[t_iso]
        h_srcs = [src for _, src in hp_list]

        h_temps = [(hp.temp, src) for hp, src in hp_list if hp.temp is not None]
        h_codes = [(hp.weather_code, src) for hp, src in hp_list if hp.weather_code is not None]
        h_winds = [(hp.wind_speed, src) for hp, src in hp_list if hp.wind_speed is not None]
        h_dirs = [(hp.wind_direction, src) for hp, src in hp_list if hp.wind_direction is not None]
        h_hums = [(hp.humidity, src) for hp, src in hp_list if hp.humidity is not None]
        h_press = [(hp.pressure_msl, src) for hp, src in hp_list if hp.pressure_msl is not None]
        h_precips = [(hp.precipitation, src) for hp, src in hp_list if hp.precipitation is not None]
        h_probs = [(hp.precipitation_probability, src) for hp, src in hp_list if hp.precipitation_probability is not None]

        ht_val, ht_srcs = calc_median(h_temps) if h_temps else (0.0, [])
        hc_val, _ = calc_majority(h_codes) if h_codes else (0, [])
        hw_val, _ = calc_median(h_winds) if h_winds else (0.0, [])
        hd_val, _ = calc_majority(h_dirs) if h_dirs else (0.0, [])
        hh_val, _ = calc_median(h_hums) if h_hums else (50.0, [])
        hp_val, _ = calc_median(h_press) if h_press else (1013.0, [])
        hpr_val, _ = calc_median(h_precips) if h_precips else (0.0, [])

        # Precipitation probability: priority order (OM > MET > wttr).
        # A 0% answer from a higher-priority source wins over 60% from a lower one.
        hprob_val = 0
        if h_probs:
            by_src = {s: prob for prob, s in h_probs}
            for p_src in SOURCE_PRIORITY:
                if p_src in by_src:
                    hprob_val = by_src[p_src]
                    break

        is_d = hp_list[0][0].is_day

        # Time label e.g. "15:00"
        t_label = t_iso[11:16] if len(t_iso) >= 16 else t_iso

        merged_hourly.append(HourlyForecast(
            time=t_label,
            time_iso=t_iso,
            temp=ht_val,
            code=hc_val,
            is_day=is_d,
            precip_prob=hprob_val,
            precip_amount=hpr_val,
            pressure_hpa=hp_val,
            humidity=hh_val,
            wind_speed=hw_val,
            wind_direction=hd_val,
            sources=h_srcs,
            low_confidence=(len(ht_srcs) < 2),
        ))

    # ------------------------------------------------------------------------
    # Merge Daily Summaries
    # ------------------------------------------------------------------------
    daily_by_date: dict[str, list[tuple[DailySummary, str]]] = defaultdict(list)
    for s in active_sources:
        for ds in s.daily:
            daily_by_date[ds.date_str].append((ds, s.source_name))

    merged_daily: list[DailyForecast] = []
    days_detailed: list[DayDetailedForecast] = []

    dt_now_utc = datetime.fromtimestamp(now, timezone.utc)
    utc_offset = get_geo_timezone_offset_seconds(lat, lon, tz_name)
    utc_offset_hours = utc_offset / 3600.0

    dt_local = dt_now_utc + timedelta(seconds=utc_offset)
    today_str = dt_local.strftime("%Y-%m-%d")

    for d_idx, d_str in enumerate(sorted(daily_by_date.keys())):
        ds_list = daily_by_date[d_str]
        d_srcs = [src for _, src in ds_list]

        d_mins = [(ds.temp_min, src) for ds, src in ds_list if ds.temp_min is not None]
        d_maxs = [(ds.temp_max, src) for ds, src in ds_list if ds.temp_max is not None]
        d_codes = [(ds.weather_code, src) for ds, src in ds_list if ds.weather_code is not None]
        d_precips = [(ds.precipitation_sum, src) for ds, src in ds_list if ds.precipitation_sum is not None]
        d_probs = [(ds.precipitation_probability_max, src) for ds, src in ds_list if ds.precipitation_probability_max is not None]
        d_winds = [(ds.wind_speed_max, src) for ds, src in ds_list if ds.wind_speed_max is not None]
        d_gusts = [(ds.wind_gusts_max, src) for ds, src in ds_list if ds.wind_gusts_max is not None]

        min_val, min_srcs = calc_median(d_mins) if d_mins else (0.0, [])
        max_val, max_srcs = calc_median(d_maxs) if d_maxs else (10.0, [])
        code_val, _ = calc_majority(d_codes) if d_codes else (0, [])
        precip_sum_val, _ = calc_median(d_precips) if d_precips else (0.0, [])
        wind_max_val, _ = calc_median(d_winds) if d_winds else (wind_val, [])
        gust_max_val, _ = calc_median(d_gusts) if d_gusts else (gust_val, [])

        prob_max_val = 0
        if d_probs:
            by_src = {s: prob for prob, s in d_probs}
            for p_src in SOURCE_PRIORITY:
                if p_src in by_src:
                    prob_max_val = by_src[p_src]
                    break

        try:
            d_date = datetime.strptime(d_str, "%Y-%m-%d").date()
            w_idx = d_date.weekday()
            w_name = get_weekday_name(w_idx, short=True, lang=lang)
            w_letter = w_name[:1]
        except Exception:
            w_idx = d_idx % 7  # unparsable date: fall back to position within the list
            w_name = d_str
            w_letter = "П"

        is_today = (d_str == today_str)
        day_label = t("weather_today", _lang=lang) if is_today else w_name

        is_low = (len(min_srcs) < 2)
        icon_info = WMO_INFO.get(code_val, {})
        icon_name_val = icon_info.get("icon_day", "clear-day.svg")

        merged_daily.append(DailyForecast(
            day=day_label,
            weekday_idx=w_idx,
            min=min_val,
            max=max_val,
            code=code_val,
            icon_name=icon_name_val,
            precip_sum=precip_sum_val,
            precip_prob_max=prob_max_val,
            date_str=d_str,
            sources=d_srcs,
            low_confidence=is_low,
        ))

        # Day-specific metrics for synthetic detailed curve and cards
        d_dirs = [(ds.wind_direction_dominant, src) for ds, src in ds_list if ds.wind_direction_dominant is not None]
        day_dir_val, _ = calc_majority(d_dirs) if d_dirs else (dir_val if is_today else 0.0, [])
        day_wind_card, day_wind_desc = get_wind_direction_info(day_dir_val, lang=lang)

        day_hours = [h for h in merged_hourly if getattr(h, "time_iso", "") and h.time_iso.startswith(d_str)]
        if is_today:
            day_press = press_val
            day_hum = hum_val
            day_dew = dew_point_val
            day_vis = vis_val
            day_uv = uv_val or 3.0
        elif day_hours:
            day_press = sum(h.pressure_hpa for h in day_hours) / len(day_hours)
            day_hum = sum(h.humidity for h in day_hours) / len(day_hours)
            day_dew = calculate_dew_point((min_val + max_val) / 2.0, day_hum)
            day_vis = 10.0
            day_uv = 3.0
        else:
            day_press = 1013.25
            day_hum = 60.0
            day_dew = calculate_dew_point((min_val + max_val) / 2.0, day_hum)
            day_vis = 10.0
            day_uv = 3.0

        # Synthetic 24-hour detailed day curve for detail cards
        h24_temps = []
        h24_apps = []
        h24_probs = []
        h24_precips = []
        h24_codes = []
        h24_is_days = []
        h24_winds = []
        h24_wind_dirs = []
        h24_gusts = []
        h24_uvs = []
        h24_hums = []
        h24_dews = []
        h24_vis_km = []
        h24_press_mm = []
        h24_press_hpa = []

        for h in range(24):
            diurnal = math.sin((h - 9) / 24.0 * 2 * math.pi)
            val = round(min_val + (max_val - min_val) * (diurnal + 1.0) / 2.0, 1)
            h24_temps.append(val)
            h24_apps.append(round(val + (1.0 if 11 <= h <= 16 else -1.0), 1))
            h24_probs.append(prob_max_val if h in range(12, 18) else 0)
            h24_precips.append(round(precip_sum_val / 6.0, 1) if h in range(12, 18) else 0.0)
            h24_codes.append(code_val)
            h24_is_days.append(1 if 6 <= h < 21 else 0)
            h24_winds.append(wind_max_val)
            h24_wind_dirs.append(day_dir_val)
            h24_gusts.append(gust_max_val)
            h24_uvs.append(round(max(0.0, math.sin(max(0, h - 6) / 14.0 * math.pi) * day_uv), 1) if 6 <= h <= 18 else 0.0)
            h24_hums.append(day_hum)
            h24_dews.append(day_dew)
            h24_vis_km.append(day_vis)
            h24_press_mm.append(round(day_press * 0.750062))
            h24_press_hpa.append(day_press)

        days_detailed.append(DayDetailedForecast(
            day_index=d_idx,
            date_str=d_str,
            day_num=int(d_str.split("-")[-1]) if "-" in d_str else d_idx + 1,
            weekday_letter=w_letter,
            weekday_short=w_name,
            full_date=d_str,
            min=min_val,
            max=max_val,
            apparent_min=min_val - 1.0,
            apparent_max=max_val + 1.0,
            code=code_val,
            precip_sum=precip_sum_val,
            precip_prob_max=prob_max_val,
            is_today=is_today,
            hourly_temps=h24_temps,
            hourly_apparent=h24_apps,
            hourly_probs=h24_probs,
            hourly_precips=h24_precips,
            hourly_codes=h24_codes,
            hourly_is_days=h24_is_days,
            hourly_winds=h24_winds,
            hourly_wind_dirs=h24_wind_dirs,
            hourly_gusts=h24_gusts,
            hourly_uvs=h24_uvs,
            hourly_hums=h24_hums,
            hourly_dews=h24_dews,
            hourly_vis_km=h24_vis_km,
            hourly_press_mm=h24_press_mm,
            hourly_press_hpa=h24_press_hpa,
            uv_max=max(h24_uvs) if h24_uvs else 0.0,
            wind_max=wind_max_val,
            gust_max=gust_max_val,
            dominant_wind_dir=day_dir_val,
            dominant_wind_cardinal=day_wind_card,
            dominant_wind_desc=day_wind_desc,
            min_humidity=max(0.0, day_hum - 10.0),
            max_humidity=min(100.0, day_hum + 10.0),
            min_pressure_mm=round(day_press * 0.750062) - 2,
            max_pressure_mm=round(day_press * 0.750062) + 2,
        ))

    # Overall min and max across all days
    all_mins = [d.min for d in merged_daily]
    all_maxs = [d.max for d in merged_daily]
    overall_min = min(all_mins) if all_mins else temp_val - 5
    overall_max = max(all_maxs) if all_maxs else temp_val + 5

    # Astronomical calculations (always local NOAA)
    today_date = dt_now_utc.date()
    solar_dict = calculate_solar_details(lat, lon, today_date, utc_offset_hours, lang=lang)
    moon_dict = calculate_detailed_moon(lat, lon, dt_now_utc, utc_offset_hours, lang=lang)
    solar_details = SolarDetails.from_dict(solar_dict)
    detailed_moon = DetailedMoon.from_dict(moon_dict)

    current.sunrise_str = solar_details.sunrise
    current.sunset_str = solar_details.sunset
    if merged_daily:
        current.temp_min = merged_daily[0].min
        current.temp_max = merged_daily[0].max

    # Status text
    if level == "S3":
        status_text = f"Консенсус 3 источников ({', '.join(src_names)})" if lang == "ru" else f"Consensus of 3 sources ({', '.join(src_names)})"
    elif level == "S2":
        status_text = f"Консенсус 2 источников ({', '.join(src_names)})" if lang == "ru" else f"Consensus of 2 sources ({', '.join(src_names)})"
    elif level == "S1":
        status_text = f"Один источник: {src_names[0]} (низкая достоверность)" if lang == "ru" else f"Single source: {src_names[0]} (low confidence)"
    else:
        status_text = "Данные из кэша" if lang == "ru" else "Cached data"

    if is_basic:
        status_text += " [Базовый режим]" if lang == "ru" else " [Basic mode]"

    return WeatherForecastData(
        city_name=city_name,
        country=country,
        lat=lat,
        lon=lon,
        current=current,
        hourly=merged_hourly,
        daily=merged_daily,
        days_detailed=days_detailed,
        solar_details=solar_details,
        detailed_moon=detailed_moon,
        moon_phase=calculate_moon_phase(dt_now_utc, lang=lang),
        forecast_date=merged_daily[0].date_str if merged_daily else today_str,
        utc_offset_seconds=utc_offset,
        cached_at=now,
        weather_model="Consensus",
        forecast_source="consensus" if level in ("S3", "S2") else (src_names[0] if src_names else "consensus"),
        is_consensus=(level in ("S3", "S2")),
        sources_count=len(active_sources),
        source_name=", ".join(src_names),
        consensus_level=level,
        status_text=status_text,
        sources=src_names,
        overall_min=overall_min,
        overall_max=overall_max,
    )
