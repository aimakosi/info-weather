"""Unit conversion and formatting engine for info-weather.

Internal standard units:
- Temperature: Celsius (°C)
- Wind speed: meters per second (m/s)
- Pressure: hectopascals (hPa / mbar) at Mean Sea Level (MSL)
- Precipitation: millimeters (mm)
- Visibility: kilometers (km)
- Humidity: percentage (%)

Conversions to and from user-configured display units (FR-9) and
template string interpolation.
"""

from __future__ import annotations

import math

# ============================================================================
# 1. TEMPERATURE CONVERSIONS
# ============================================================================

def celsius_to_fahrenheit(c: float | int) -> float:
    """Convert Celsius to Fahrenheit."""
    return float(c) * 1.8 + 32.0


def fahrenheit_to_celsius(f: float | int) -> float:
    """Convert Fahrenheit to Celsius."""
    return (float(f) - 32.0) / 1.8


def _norm_unit(unit: str) -> str:
    """Map config-style unit keys ('C', 'F', 'mmHg') to canonical function keys."""
    u = str(unit).strip().lower()
    return {"c": "celsius", "f": "fahrenheit"}.get(u, u)


def convert_temp(celsius: float | int | None, unit: str = "celsius") -> int | None:
    """Convert Celsius temperature to display unit (celsius or fahrenheit) rounded to int."""
    if celsius is None:
        return None
    try:
        c_val = float(celsius)
    except (TypeError, ValueError):
        return None
    if _norm_unit(unit) == "fahrenheit":
        return round(celsius_to_fahrenheit(c_val))
    return round(c_val)


def convert_temp_float(celsius: float | int | None, unit: str = "celsius") -> float | None:
    """Convert Celsius temperature to display unit as float."""
    if celsius is None:
        return None
    try:
        c_val = float(celsius)
    except (TypeError, ValueError):
        return None
    if _norm_unit(unit) == "fahrenheit":
        return round(celsius_to_fahrenheit(c_val), 1)
    return round(c_val, 1)


def convert_temp_diff(celsius_diff: float | int | None, unit: str = "celsius") -> int | None:
    """Convert temperature difference/delta (no 32-degree shift)."""
    if celsius_diff is None:
        return None
    try:
        d_val = float(celsius_diff)
    except (TypeError, ValueError):
        return None
    if _norm_unit(unit) == "fahrenheit":
        return round(d_val * 1.8)
    return round(d_val)


def format_temp(
    celsius: float | int | None,
    unit: str = "celsius",
    show_sign: bool = True,
    show_unit: bool = False,
    template: str | None = None,
) -> str:
    """Format temperature with optional sign, degree symbol, or custom template."""
    if celsius is None:
        return "--"
    unit = _norm_unit(unit)
    val = convert_temp(celsius, unit)
    if val is None:
        return "--"

    sign = "+" if (show_sign and val > 0) else ("-" if val < 0 else "")
    abs_val = abs(val)
    unit_sym = "°F" if (show_unit and unit == "fahrenheit") else ("°C" if show_unit else "°")

    if template:
        return template.format(
            t=abs_val if "{t_sign}" in template else val,
            t_sign=sign,
            t_full=f"{sign}{abs_val}" if sign else str(abs_val),
            unit=unit_sym,
        )

    if show_sign:
        return f"{sign}{abs_val}{unit_sym}" if sign else f"{abs_val}{unit_sym}"
    return f"{val}{unit_sym}"


# ============================================================================
# 2. WIND CONVERSIONS & BEAUFORT
# ============================================================================

# Beaufort scale boundaries (m/s)
BEAUFORT_LEVELS = [
    (0.3, 0, "Calm", "Штиль"),
    (1.6, 1, "Light air", "Тихий"),
    (3.4, 2, "Light breeze", "Лёгкий"),
    (5.5, 3, "Gentle breeze", "Слабый"),
    (8.0, 4, "Moderate breeze", "Умеренный"),
    (10.8, 5, "Fresh breeze", "Свежий"),
    (13.9, 6, "Strong breeze", "Сильный"),
    (17.2, 7, "High wind", "Крепкий"),
    (20.8, 8, "Gale", "Очень крепкий"),
    (24.5, 9, "Strong gale", "Шторм"),
    (28.5, 10, "Storm", "Сильный шторм"),
    (32.7, 11, "Violent storm", "Жестокий шторм"),
    (float("inf"), 12, "Hurricane", "Ураган"),
]


def kmh_to_ms(kmh: float | int) -> float:
    """Convert km/h to m/s."""
    return float(kmh) / 3.6


def mph_to_ms(mph: float | int) -> float:
    """Convert miles per hour to m/s."""
    return float(mph) * 0.44704


def knots_to_ms(knots: float | int) -> float:
    """Convert knots to m/s."""
    return float(knots) * 0.514444


def convert_wind_speed(ms: float | int | None, unit: str = "m_s") -> float | None:
    """Convert wind speed from m/s to target unit."""
    if ms is None:
        return None
    try:
        val = float(ms)
    except (TypeError, ValueError):
        return None

    if unit in ("m_s", "ms", "m/s", "м/с"):
        return round(val, 1)
    elif unit in ("km_h", "kmh", "km/h", "км/ч"):
        return round(val * 3.6, 1)
    elif unit in ("mph", "миль/ч"):
        return round(val / 0.44704, 1)
    elif unit in ("knots", "kn", "узлы"):
        return round(val / 0.514444, 1)
    elif unit in ("beaufort", "бофорт"):
        return float(get_beaufort_number(val))
    return round(val, 1)


def get_beaufort_number(ms: float | int | None) -> int:
    """Get Beaufort scale number (0..12) from wind speed in m/s."""
    if ms is None or ms < 0:
        return 0
    val = float(ms)
    for max_speed, level, _, _ in BEAUFORT_LEVELS:
        if val < max_speed:
            return level
    return 12


BEAUFORT_UK = [
    "Штиль", "Тихий", "Легкий", "Слабкий", "Помірний", "Свіжий",
    "Сильний", "Міцний", "Дуже міцний", "Шторм", "Сильний шторм",
    "Жорстокий шторм", "Ураган",
]


def get_beaufort_name(ms: float | int | None, lang: str = "ru") -> str:
    """Get localized Beaufort scale name."""
    b_num = get_beaufort_number(ms)
    if lang == "uk" and b_num < len(BEAUFORT_UK):
        return BEAUFORT_UK[b_num]
    entry = BEAUFORT_LEVELS[b_num]
    return entry[3] if lang == "ru" else entry[2]


def format_wind_speed(
    ms: float | int | None,
    unit: str = "m_s",
    lang: str = "ru",
    template: str | None = None,
) -> str:
    """Format wind speed with unit symbol."""
    if ms is None:
        return "--"
    val = convert_wind_speed(ms, unit)
    if val is None:
        return "--"

    unit_labels = {
        "m_s": "м/с" if lang in ("ru", "uk") else "m/s",
        "m/s": "м/с" if lang in ("ru", "uk") else "m/s",
        "km_h": "км/год" if lang == "uk" else ("км/ч" if lang == "ru" else "km/h"),
        "km/h": "км/год" if lang == "uk" else ("км/ч" if lang == "ru" else "km/h"),
        "mph": "миль/год" if lang == "uk" else ("миль/ч" if lang == "ru" else "mph"),
        "knots": "вуз." if lang == "uk" else ("уз." if lang == "ru" else "kn"),
        "kn": "вуз." if lang == "uk" else ("уз." if lang == "ru" else "kn"),
        "beaufort": "бал" if lang == "uk" else ("балл" if lang == "ru" else "Bft"),
    }
    unit_sym = unit_labels.get(unit, "м/с" if lang in ("ru", "uk") else "m/s")

    # Format cleanly without trailing zero if whole number
    num_str = f"{val:.0f}" if val.is_integer() else f"{val:.1f}"

    if template:
        return template.format(
            wind_speed=num_str,
            unit_wind=unit_sym,
            beaufort=get_beaufort_number(ms),
        )
    return f"{num_str} {unit_sym}"


# ============================================================================
# 3. PRESSURE CONVERSIONS
# ============================================================================

HPA_TO_MMHG = 0.750062
MMHG_TO_HPA = 1.0 / HPA_TO_MMHG
HPA_TO_INHG = 0.029530
INHG_TO_HPA = 1.0 / HPA_TO_INHG


def mmhg_to_hpa(mmhg: float | int) -> float:
    """Convert mmHg (Torr) to hPa."""
    return float(mmhg) * MMHG_TO_HPA


def inhg_to_hpa(inhg: float | int) -> float:
    """Convert inHg to hPa."""
    return float(inhg) * INHG_TO_HPA


def convert_pressure(hpa: float | int | None, unit: str = "mmhg") -> float | int | None:
    """Convert pressure from hPa (MSL) to target unit."""
    if hpa is None:
        return None
    try:
        val = float(hpa)
    except (TypeError, ValueError):
        return None

    unit = str(unit).strip().lower()
    if unit in ("mmhg", "мм", "мм рт. ст."):
        return round(val * HPA_TO_MMHG)
    elif unit in ("inhg", "in", "дюймы"):
        return round(val * HPA_TO_INHG, 2)
    elif unit in ("hpa", "mbar", "гпа"):
        return round(val)
    return round(val)


def format_pressure(
    hpa: float | int | None,
    unit: str = "mmhg",
    lang: str = "ru",
    template: str | None = None,
) -> str:
    """Format pressure with unit."""
    if hpa is None:
        return "--"
    unit = str(unit).strip().lower()
    val = convert_pressure(hpa, unit)
    if val is None:
        return "--"

    unit_labels = {
        "mmhg": "мм рт. ст." if lang in ("ru", "uk") else "mmHg",
        "hpa": "гПа" if lang in ("ru", "uk") else "hPa",
        "inhg": "inHg",
    }
    unit_sym = unit_labels.get(unit, "мм рт. ст." if lang in ("ru", "uk") else "mmHg")

    if template:
        return template.format(pressure=val, unit_pressure=unit_sym)
    return f"{val} {unit_sym}"


# ============================================================================
# 4. PRECIPITATION CONVERSIONS
# ============================================================================

def inches_to_mm(inches: float | int) -> float:
    """Convert inches of precipitation to mm."""
    return float(inches) * 25.4


def convert_precip(mm: float | int | None, unit: str = "mm") -> float | None:
    """Convert precipitation amount from mm to target unit."""
    if mm is None:
        return None
    try:
        val = float(mm)
    except (TypeError, ValueError):
        return None
    if unit in ("in", "inches", "дюймы"):
        return round(val / 25.4, 2)
    return round(val, 1)


def format_precip(mm: float | int | None, unit: str = "mm", lang: str = "ru") -> str:
    """Format precipitation amount."""
    if mm is None:
        return "--"
    val = convert_precip(mm, unit)
    if val is None:
        return "--"
    unit_sym = "дюйм" if (unit in ("in", "inches") and lang in ("ru", "uk")) else ("in" if unit in ("in", "inches") else ("мм" if lang in ("ru", "uk") else "mm"))
    return f"{val} {unit_sym}"


# ============================================================================
# 5. VISIBILITY & DISTANCE
# ============================================================================

def miles_to_km(miles: float | int) -> float:
    """Convert miles to km."""
    return float(miles) * 1.60934


def convert_visibility(km: float | int | None, unit: str = "km") -> float | None:
    """Convert visibility from km to target unit."""
    if km is None:
        return None
    try:
        val = float(km)
    except (TypeError, ValueError):
        return None
    if unit in ("mi", "miles", "миль"):
        return round(val / 1.60934, 1)
    elif unit in ("m", "meters", "метры"):
        return round(val * 1000.0)
    return round(val, 1)


def format_visibility(km: float | int | None, unit: str = "km", lang: str = "ru") -> str:
    """Format visibility with unit."""
    if km is None:
        return "--"
    val = convert_visibility(km, unit)
    if val is None:
        return "--"
    if unit in ("mi", "miles"):
        u_sym = "миль" if lang in ("ru", "uk") else "mi"
    elif unit in ("m", "meters"):
        u_sym = "м" if lang in ("ru", "uk") else "m"
    else:
        u_sym = "км" if lang in ("ru", "uk") else "km"
    num_str = f"{val:.0f}" if isinstance(val, int) or val.is_integer() else f"{val:.1f}"
    return f"{num_str} {u_sym}"


# ============================================================================
# 6. DERIVED METEOROLOGICAL CALCULATIONS
# ============================================================================

def calculate_apparent_temperature(
    temperature_c: float,
    wind_speed_ms: float,
    relative_humidity: float,
) -> float:
    """
    Calculate apparent temperature (feels like) using the Australian Bureau
    of Meteorology formula (combination of heat index and wind chill).
    AT = Ta + 0.33 * e - 0.70 * ws - 4.00
    where e is water vapour pressure in hPa.
    """
    t = float(temperature_c)
    ws = max(0.0, float(wind_speed_ms))
    rh = max(0.0, min(100.0, float(relative_humidity)))

    # Vapour pressure (hPa)
    e = (rh / 100.0) * 6.105 * math.exp((17.27 * t) / (237.7 + t))
    at = t + 0.33 * e - 0.70 * ws - 4.00
    return round(at, 1)


def calculate_dew_point(temperature_c: float, relative_humidity: float) -> float:
    """
    Calculate dew point temperature (°C) using Magnus-Tetens formula.
    """
    t = float(temperature_c)
    rh = max(1.0, min(100.0, float(relative_humidity)))
    a = 17.27
    b = 237.7
    alpha = ((a * t) / (b + t)) + math.log(rh / 100.0)
    dew = (b * alpha) / (a - alpha)
    return round(dew, 1)


# ============================================================================
# 7. GENERIC FORMATTER ENGINE
# ============================================================================

def cardinal_from_degrees(degrees: float | int | None, lang: str = "ru") -> str:
    """Convert meteorological wind direction in degrees (0-360) to cardinal string (N, NW, С, СЗ etc.)."""
    if degrees is None:
        return ""
    from data.wmo_conditions import get_wind_direction_info
    card, _ = get_wind_direction_info(degrees, lang=lang)
    return card
