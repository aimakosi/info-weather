"""Celestial mechanics and NOAA astronomical calculations for info-weather.

Implements NOAA algorithms for:
- Solar position, equation of time, solar declination, solar noon
- Sunrise, sunset, civil dawn, civil dusk, daylight duration
- Solar elevation curve across 24 hours
- Annual solar table & solstice statistics
- Lunar phase, cycle fraction, illuminated percentage, distance in km,
  moonrise and moonset times, lunar tilt angle
- Solar UV estimate from elevation angle and cloud attenuation
- Solar time-of-day classification ('day', 'night', 'dusk') for auto_solar theme mode
"""

from __future__ import annotations

import calendar
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.i18n import (
    format_day_month,
    get_month_name,
    get_weekday_name,
    t,
)


def _solar_equation_terms(n_day: int) -> tuple[float, float]:
    """NOAA solar position terms for a day of year: (equation of time [min], declination [rad])."""
    gamma = 2.0 * math.pi / 365.0 * (n_day - 1 + 0.5)
    eqtime = (
        229.18 * (
            0.000075
            + 0.001868 * math.cos(gamma)
            - 0.032077 * math.sin(gamma)
            - 0.014615 * math.cos(2 * gamma)
            - 0.040849 * math.sin(2 * gamma)
        )
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    return eqtime, decl


def _moon_phase_key(cycle_frac: float) -> str:
    """Map moon cycle fraction (0..1) to a translation key for the phase name."""
    if cycle_frac < 0.03 or cycle_frac >= 0.97:
        return "weather_moon_phase_new"
    elif cycle_frac < 0.22:
        return "weather_moon_phase_waxing_crescent"
    elif cycle_frac < 0.28:
        return "weather_moon_phase_first_quarter"
    elif cycle_frac < 0.47:
        return "weather_moon_phase_waxing_gibbous"
    elif cycle_frac < 0.53:
        return "weather_moon_phase_full"
    elif cycle_frac < 0.72:
        return "weather_moon_phase_waning_gibbous"
    elif cycle_frac < 0.78:
        return "weather_moon_phase_last_quarter"
    return "weather_moon_phase_waning_crescent"


def calculate_moon_phase(dt: datetime | None = None, lang: str = "ru") -> dict[str, Any]:
    """Calculate basic Moon phase parameters, illumination, and age of cycle."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    ref_new_moon = datetime(2024, 1, 11, 11, 57, tzinfo=timezone.utc)
    synodic_month = 29.53058867
    diff_days = (dt - ref_new_moon).total_seconds() / 86400.0
    cycles = diff_days / synodic_month
    cycle_frac = cycles - math.floor(cycles)
    age_days = cycle_frac * synodic_month
    illumination = 0.5 * (1.0 - math.cos(2 * math.pi * cycle_frac)) * 100.0

    if cycle_frac < 0.5:
        days_to_full = (0.5 - cycle_frac) * synodic_month
    else:
        days_to_full = (1.5 - cycle_frac) * synodic_month

    phase_key = _moon_phase_key(cycle_frac)

    return {
        "cycle_fraction": cycle_frac,
        "age_days": round(age_days, 1),
        "illumination": round(illumination),
        "days_to_full": max(0, round(days_to_full)),
        "phase_name": t(phase_key, _lang=lang),
        "phase_name_ru": t(phase_key, _lang="ru"),
        "phase_name_en": t(phase_key, _lang="en"),
    }


def calculate_solar_details(
    lat: float,
    lon: float,
    dt: date | None = None,
    utc_offset_hours: float = 0.0,
    lang: str = "ru",
) -> dict[str, Any]:
    """Calculate first light, sunrise, solar noon, sunset, last light, and 24h elevation curve."""
    if dt is None:
        dt = date.today()

    eqtime, decl = _solar_equation_terms(dt.timetuple().tm_yday)

    time_offset = eqtime + 4.0 * lon - 60.0 * utc_offset_hours
    t_noon_min = 720.0 - time_offset
    lat_rad = math.radians(lat)

    def get_ha_for_elevation(elev_deg: float) -> float | None:
        elev_rad = math.radians(elev_deg)
        denom = math.cos(lat_rad) * math.cos(decl)
        if abs(denom) < 1e-6:
            return 0.0
        cos_ha = (math.sin(elev_rad) - math.sin(lat_rad) * math.sin(decl)) / denom
        if cos_ha > 1.0 or cos_ha < -1.0:
            return None
        return math.degrees(math.acos(cos_ha))

    ha_sun = get_ha_for_elevation(-0.833)
    ha_twilight = get_ha_for_elevation(-6.0)

    if ha_sun is not None:
        sunrise_min = t_noon_min - ha_sun * 4.0
        sunset_min = t_noon_min + ha_sun * 4.0
        daylight_min = max(0.0, sunset_min - sunrise_min)
    else:
        if math.sin(lat_rad) * math.sin(decl) > 0:
            sunrise_min, sunset_min = 0.0, 1440.0
            daylight_min = 1440.0
        else:
            sunrise_min, sunset_min = 720.0, 720.0
            daylight_min = 0.0

    if ha_twilight is not None:
        dawn_min = t_noon_min - ha_twilight * 4.0
        dusk_min = t_noon_min + ha_twilight * 4.0
    else:
        dawn_min = sunrise_min
        dusk_min = sunset_min

    def fmt_time(m: float) -> str:
        m_mod = m % 1440.0
        h = int(m_mod // 60)
        mins = int(round(m_mod % 60))
        if mins == 60:
            mins = 0
            h = (h + 1) % 24
        return f"{h:02d}:{mins:02d}"

    dl_h = int(daylight_min // 60)
    dl_m = int(round(daylight_min % 60))
    if lang == "uk":
        daylight_str = f"{dl_h} год {dl_m} хв"
    elif lang == "ru":
        daylight_str = f"{dl_h} ч {dl_m} мин"
    else:
        daylight_str = f"{dl_h}h {dl_m}m"
    daylight_duration = f"{dl_h:02d}:{dl_m:02d}"

    curve_points = []
    for step in range(97):
        h_frac = step * 0.25
        m_curr = h_frac * 60.0
        ha = (m_curr - t_noon_min) * 0.25
        sin_elev = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(math.radians(ha))
        sin_elev = max(-1.0, min(1.0, sin_elev))
        elev = math.degrees(math.asin(sin_elev))
        curve_points.append((round(h_frac, 2), round(elev, 2)))

    return {
        "first_light": fmt_time(dawn_min),
        "sunrise": fmt_time(sunrise_min),
        "sunset": fmt_time(sunset_min),
        "last_light": fmt_time(dusk_min),
        "daylight_min": daylight_min,
        "daylight_str": daylight_str,
        "daylight_duration": daylight_duration,
        "t_noon_frac": round(t_noon_min / 60.0, 3),
        "t_dawn_frac": round(dawn_min / 60.0, 3),
        "t_sunrise_frac": round(sunrise_min / 60.0, 3),
        "t_sunset_frac": round(sunset_min / 60.0, 3),
        "t_dusk_frac": round(dusk_min / 60.0, 3),
        "curve_points": curve_points,
    }


def determine_solar_time_of_day(
    lat: float,
    lon: float,
    utc_dt: datetime | None = None,
    utc_offset_hours: float | None = None,
) -> tuple[str, int]:
    """
    Dynamically determines (time_of_day, is_day) based on astronomical solar geometry.

    Returns:
        ('dusk', 1)  - Dawn or Dusk twilight
        ('day', 1)   - Daytime (sun is up)
        ('night', 0) - Nighttime (sun is below horizon)
    """
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)
    elif utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    if utc_offset_hours is None:
        utc_offset_hours = round(lon / 15.0)
    city_local_ts = utc_dt.timestamp() + utc_offset_hours * 3600
    local_dt = datetime.fromtimestamp(city_local_ts, timezone.utc)
    local_min = local_dt.hour * 60 + local_dt.minute

    eqtime, decl = _solar_equation_terms(local_dt.timetuple().tm_yday)

    time_offset = eqtime + 4.0 * lon - 60.0 * utc_offset_hours
    t_noon_min = 720.0 - time_offset
    lat_rad = math.radians(lat)

    def get_ha(elev_deg: float) -> float | None:
        elev_rad = math.radians(elev_deg)
        denom = math.cos(lat_rad) * math.cos(decl)
        if abs(denom) < 1e-6:
            return 0.0
        cos_ha = (math.sin(elev_rad) - math.sin(lat_rad) * math.sin(decl)) / denom
        if cos_ha > 1.0 or cos_ha < -1.0:
            return None
        return math.degrees(math.acos(cos_ha))

    ha_sun = get_ha(-0.833) or 90.0
    ha_twi = get_ha(-6.0) or 96.0

    sunrise_min = t_noon_min - ha_sun * 4.0
    sunset_min = t_noon_min + ha_sun * 4.0
    dawn_min = t_noon_min - ha_twi * 4.0
    dusk_min = t_noon_min + ha_twi * 4.0

    if (dawn_min - 20 <= local_min <= sunrise_min + 40) or (sunset_min - 50 <= local_min <= dusk_min + 30):
        return ("dusk", 1)
    elif sunrise_min + 40 < local_min < sunset_min - 50:
        return ("day", 1)
    else:
        return ("night", 0)


def calculate_lunar_distance_km(dt: datetime) -> int:
    """Calculate distance between Earth and Moon in kilometers."""
    y, m = dt.year, dt.month
    day_frac = dt.day + dt.hour / 24.0 + dt.minute / 1440.0 + dt.second / 86400.0
    if m <= 2:
        y -= 1
        m += 12
    a_val = int(y / 100)
    b_val = 2 - a_val + int(a_val / 4)
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day_frac + b_val - 1524.5
    t_cen = (jd - 2451545.0) / 36525.0

    d_ang = math.radians((297.8501921 + 445267.1114034 * t_cen - 0.0018819 * (t_cen ** 2)) % 360)
    m_sun = math.radians((357.5291092 + 35999.0502909 * t_cen - 0.0001536 * (t_cen ** 2)) % 360)
    m_moon = math.radians((134.9633964 + 477198.8675055 * t_cen + 0.0087414 * (t_cen ** 2)) % 360)
    f_arg = math.radians((93.2720950 + 483202.0175233 * t_cen - 0.0036539 * (t_cen ** 2)) % 360)

    dist = 385000.56
    dist -= 20905.355 * math.cos(m_moon)
    dist -= 3699.111 * math.cos(2 * d_ang - m_moon)
    dist -= 2955.968 * math.cos(2 * d_ang)
    dist -= 569.925 * math.cos(2 * m_moon)
    dist += 48.888 * math.cos(m_sun)
    dist -= 3.149 * math.cos(2 * f_arg)
    dist += 246.158 * math.cos(2 * d_ang - 2 * m_moon)
    dist -= 152.138 * math.cos(2 * d_ang - m_sun - m_moon)
    dist -= 170.733 * math.cos(2 * d_ang + m_moon)
    dist -= 204.586 * math.cos(2 * d_ang - m_sun)
    dist -= 129.620 * math.cos(m_moon - m_sun)
    dist += 108.743 * math.cos(d_ang)
    dist += 104.755 * math.cos(m_moon + m_sun)
    dist += 79.661 * math.cos(2 * d_ang - 2 * f_arg)
    return int(round(dist))


def calculate_moonrise_moonset(
    lat: float,
    lon: float,
    dt_day: date,
    utc_offset_hours: float,
) -> tuple[str, str]:
    """Calculate Moonrise and Moonset times for the specified date."""
    lat_r = math.radians(lat)

    def get_moon_alt(t_local_hour: float) -> float:
        t_utc_hour = t_local_hour - utc_offset_hours
        dt_utc = datetime(dt_day.year, dt_day.month, dt_day.day, tzinfo=timezone.utc) + timedelta(hours=t_utc_hour)
        y, m = dt_utc.year, dt_utc.month
        day_frac = dt_utc.day + dt_utc.hour / 24.0 + dt_utc.minute / 1440.0 + dt_utc.second / 86400.0
        if m <= 2:
            y -= 1
            m += 12
        a_val = int(y / 100)
        b_val = 2 - a_val + int(a_val / 4)
        jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day_frac + b_val - 1524.5
        t_cen = (jd - 2451545.0) / 36525.0

        lp = (218.3164477 + 481267.88123421 * t_cen) % 360
        d_ang = math.radians((297.8501921 + 445267.1114034 * t_cen) % 360)
        m_sun = math.radians((357.5291092 + 35999.0502909 * t_cen) % 360)
        m_moon = math.radians((134.9633964 + 477198.8675055 * t_cen) % 360)
        f_arg = math.radians((93.2720950 + 483202.0175233 * t_cen) % 360)

        lon_moon = (
            lp
            + 6.288774 * math.sin(m_moon)
            + 1.274027 * math.sin(2 * d_ang - m_moon)
            + 0.658314 * math.sin(2 * d_ang)
            + 0.213618 * math.sin(2 * m_moon)
            - 0.185116 * math.sin(m_sun)
            - 0.114332 * math.sin(2 * f_arg)
        )
        lat_moon = (
            5.128122 * math.sin(f_arg)
            + 0.280602 * math.sin(m_moon + f_arg)
            + 0.277693 * math.sin(m_moon - f_arg)
            + 0.173237 * math.sin(2 * d_ang - f_arg)
        )
        eps = math.radians(23.439291 - 0.0130042 * t_cen)

        lon_r = math.radians(lon_moon)
        lat_mr = math.radians(lat_moon)
        sin_dec = math.sin(lat_mr) * math.cos(eps) + math.cos(lat_mr) * math.sin(eps) * math.sin(lon_r)
        dec = math.asin(sin_dec)
        y_ra = math.sin(lon_r) * math.cos(eps) - math.tan(lat_mr) * math.sin(eps)
        x_ra = math.cos(lon_r)
        ra = math.atan2(y_ra, x_ra)

        gmst = (280.46061837 + 360.98564736629 * (jd - 2451545.0)) % 360
        lst = math.radians((gmst + lon) % 360)
        ha = lst - ra
        sin_alt = math.sin(lat_r) * math.sin(dec) + math.cos(lat_r) * math.cos(dec) * math.cos(ha)
        alt = math.asin(max(-1.0, min(1.0, sin_alt)))
        return math.degrees(alt) - 0.125

    rise_time, set_time = None, None
    prev_h = 0.0
    prev_alt = get_moon_alt(prev_h)

    for step in range(1, 97):
        h = step * 0.25
        alt = get_moon_alt(h)
        if prev_alt <= 0.0 and alt > 0.0 and rise_time is None:
            frac = (0.0 - prev_alt) / (alt - prev_alt) if (alt - prev_alt) != 0 else 0
            rise_time = prev_h + frac * 0.25
        elif prev_alt >= 0.0 and alt < 0.0 and set_time is None:
            frac = (0.0 - prev_alt) / (alt - prev_alt) if (alt - prev_alt) != 0 else 0
            set_time = prev_h + frac * 0.25
        prev_h, prev_alt = h, alt

    def fmt(h_val: float | None) -> str:
        if h_val is None:
            return "-:-"
        h_val = h_val % 24.0
        hh = int(h_val)
        mm = int(round((h_val - hh) * 60.0))
        if mm == 60:
            hh = (hh + 1) % 24
            mm = 0
        return f"{hh:02d}:{mm:02d}"

    return fmt(rise_time), fmt(set_time)


def calculate_detailed_moon(
    lat: float,
    lon: float,
    target_dt: datetime | None = None,
    utc_offset_hours: float = 0.0,
    lang: str = "ru",
) -> dict[str, Any]:
    """Calculate complete Moon metadata for detailed moon cards."""
    if target_dt is None:
        target_dt = datetime.now(timezone.utc) + timedelta(hours=utc_offset_hours)

    if target_dt.tzinfo is None:
        dt_utc = target_dt - timedelta(hours=utc_offset_hours)
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    else:
        dt_utc = target_dt.astimezone(timezone.utc)

    ref_new_moon = datetime(2024, 1, 11, 11, 57, tzinfo=timezone.utc)
    synodic = 29.53058867
    diff_days = (dt_utc - ref_new_moon).total_seconds() / 86400.0
    cycles = diff_days / synodic
    cycle_frac = (cycles - int(cycles)) % 1.0
    age_days = cycle_frac * synodic

    illumination = 0.5 * (1.0 - math.cos(2 * math.pi * cycle_frac)) * 100.0

    if cycle_frac < 0.5:
        days_to_full = (0.5 - cycle_frac) * synodic
    else:
        days_to_full = (1.5 - cycle_frac) * synodic
    days_to_new = (1.0 - cycle_frac) * synodic

    phase_key = _moon_phase_key(cycle_frac)

    phase_name = t(phase_key, _lang=lang)
    dist_km = calculate_lunar_distance_km(dt_utc)

    local_date = (dt_utc + timedelta(hours=utc_offset_hours)).date()
    rise_str, set_str = calculate_moonrise_moonset(lat, lon, local_date, utc_offset_hours)

    dt_full = target_dt + timedelta(days=days_to_full)
    dt_new = target_dt + timedelta(days=days_to_new)

    def fmt_d(d_val: datetime) -> str:
        d_str = get_weekday_name(d_val.weekday(), short=True, lang=lang)
        dm_str = format_day_month(d_val.day, d_val.month, lang=lang)
        return f"{d_str}, {dm_str}"

    full_moon_date_str = fmt_d(dt_full)
    new_moon_date_str = fmt_d(dt_new)

    h_frac = target_dt.hour + target_dt.minute / 60.0
    tilt_deg = 15.0 * math.sin(2 * math.pi * (cycle_frac - 0.25)) - 10.0 * math.cos(h_frac * math.pi / 12.0)
    dist_u = t("unit_distance_km", _lang=lang)

    return {
        "cycle_fraction": cycle_frac,
        "illumination": int(round(illumination)),
        "phase_name": phase_name,
        "phase_name_ru": t(phase_key, _lang="ru"),
        "phase_name_en": t(phase_key, _lang="en"),
        "age_days": round(age_days, 1),
        "days_to_full": max(0, int(round(days_to_full))),
        "distance_km": dist_km,
        "distance_str": f"{dist_km:,}".replace(",", " ") + f" {dist_u}",
        "moonrise": rise_str,
        "moonset": set_str,
        "next_full_moon_date_str": full_moon_date_str,
        "next_new_moon_date_str": new_moon_date_str,
        "tilt_deg": round(tilt_deg, 1),
    }


def compute_solar_uv(lat: float, dt: datetime, cloud_pct: float = 0.0) -> float:
    """
    Physical estimation of UV index based on solar zenith angle and cloud attenuation.
    """
    n_day = dt.timetuple().tm_yday
    _, decl = _solar_equation_terms(n_day)
    h_angle = math.radians((dt.hour + dt.minute / 60.0 - 12.0) * 15.0)
    lat_rad = math.radians(lat)
    sin_elev = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(h_angle)
    if sin_elev <= 0.05:
        return 0.0
    uv_clear = 9.5 * (sin_elev ** 1.7)
    cf = max(0.0, min(100.0, float(cloud_pct))) / 100.0
    uv_val = uv_clear * (1.0 - 0.72 * (cf ** 2.2))
    return max(0.0, round(uv_val, 1))


def calculate_annual_solar_table(
    lat: float,
    lon: float,
    utc_offset_hours: float = 0.0,
    lang: str = "ru",
) -> dict[str, Any]:
    """Calculate annual monthly average sunrise/sunset times and solstice length."""
    month_names = [get_month_name(m, short=True, lang=lang) for m in range(1, 13)]
    cur_month = datetime.now().month
    year = datetime.now().year
    lat_rad = math.radians(lat)

    monthly_rows = []
    for m in range(1, 13):
        num_days = calendar.monthrange(year, m)[1]
        sr_sum, ss_sum = 0.0, 0.0
        for d in range(1, num_days + 1):
            dt = date(year, m, d)
            eqtime, decl = _solar_equation_terms(dt.timetuple().tm_yday)
            time_offset = eqtime + 4.0 * lon - 60.0 * utc_offset_hours
            t_noon_min = 720.0 - time_offset

            denom = math.cos(lat_rad) * math.cos(decl)
            if abs(denom) > 1e-6:
                cos_ha = (math.sin(math.radians(-0.833)) - math.sin(lat_rad) * math.sin(decl)) / denom
                if cos_ha > 1.0:
                    sr, ss = 720.0, 720.0
                elif cos_ha < -1.0:
                    sr, ss = 0.0, 1440.0
                else:
                    ha = math.degrees(math.acos(cos_ha))
                    sr = t_noon_min - ha * 4.0
                    ss = t_noon_min + ha * 4.0
            else:
                sr, ss = 360.0, 1080.0
            sr_sum += sr
            ss_sum += ss

        sr_avg = sr_sum / num_days
        ss_avg = ss_sum / num_days

        def fmt(m_val: float) -> str:
            m_mod = m_val % 1440.0
            h = int(m_mod // 60)
            mins = int(round(m_mod % 60))
            if mins == 60:
                mins = 0
                h = (h + 1) % 24
            return f"{h:02d}:{mins:02d}"

        monthly_rows.append({
            "month": m,
            "name": month_names[m - 1],
            "sunrise_str": fmt(sr_avg),
            "sunset_str": fmt(ss_avg),
            "sunrise_frac": round(sr_avg / 60.0, 2),
            "sunset_frac": round(ss_avg / 60.0, 2),
            "daylight_min": max(0.0, ss_avg - sr_avg),
            "is_current": (m == cur_month),
        })

    return {
        "months": monthly_rows,
    }


def calculate_month_moon_calendar(
    year: int,
    month: int,
    is_ru: bool | None = None,
    lang: str | None = None,
) -> dict[str, Any]:
    """Calculate daily lunar illumination and phases for entire month."""
    from core.i18n import get_current_language
    target_lang = lang or (get_current_language() if is_ru is None else ("ru" if is_ru else "en"))
    ref_new_moon = datetime(2024, 1, 11, 11, 57, tzinfo=timezone.utc)
    synodic = 29.53058867

    first_weekday, num_days = calendar.monthrange(year, month)
    days = []

    for d in range(1, num_days + 1):
        dt = datetime(year, month, d, 12, 0, tzinfo=timezone.utc)
        diff_days = (dt - ref_new_moon).total_seconds() / 86400.0
        cycles = diff_days / synodic
        f = (cycles - int(cycles)) % 1.0
        illum = 0.5 * (1.0 - math.cos(2 * math.pi * f)) * 100.0

        days.append({
            "day": d,
            "weekday": dt.weekday(),
            "cycle_fraction": f,
            "illumination": int(round(illum)),
        })

    m_name = get_month_name(month, short=False, lang=target_lang).capitalize()
    if target_lang == "ru":
        title = f"{m_name} {year} г."
    else:
        title = f"{m_name} {year}"

    return {
        "year": year,
        "month": month,
        "title": title,
        "first_weekday": first_weekday,
        "num_days": num_days,
        "days": days,
    }

