"""WMO-4677 weather condition codes, taxonomic mappings, and cardinal direction helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

WMO_INFO: dict[int, dict[str, str]] = {
    0: {"ru": "Солнечно", "uk": "Сонячно", "en": "Clear", "icon_day": "clear-day.svg", "icon_night": "clear-night.svg", "grad": "clear"},
    1: {"ru": "В основном ясно", "uk": "Переважно ясно", "en": "Mainly clear", "icon_day": "clear-day.svg", "icon_night": "clear-night.svg", "grad": "clear"},
    2: {"ru": "В основном облачно", "uk": "Мінлива хмарність", "en": "Partly cloudy", "icon_day": "partly-cloudy-day.svg", "icon_night": "partly-cloudy-night.svg", "grad": "clouds"},
    3: {"ru": "Пасмурно", "uk": "Похмуро", "en": "Overcast", "icon_day": "cloudy.svg", "icon_night": "cloudy.svg", "grad": "clouds"},
    45: {"ru": "Туман", "uk": "Туман", "en": "Fog", "icon_day": "fog.svg", "icon_night": "fog.svg", "grad": "fog"},
    48: {"ru": "Туман с изморозью", "uk": "Туман з памороззю", "en": "Rime fog", "icon_day": "fog.svg", "icon_night": "fog.svg", "grad": "fog"},
    51: {"ru": "Изморось", "uk": "Мряка", "en": "Light drizzle", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "drizzle"},
    53: {"ru": "Умеренная изморось", "uk": "Помірна мряка", "en": "Moderate drizzle", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "drizzle"},
    55: {"ru": "Плотная изморось", "uk": "Густа мряка", "en": "Dense drizzle", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "drizzle"},
    56: {"ru": "Ледяная изморось", "uk": "Крижана мряка", "en": "Freezing drizzle", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "drizzle"},
    57: {"ru": "Плотная ледяная изморось", "uk": "Густа крижана мряка", "en": "Dense freezing drizzle", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "drizzle"},
    61: {"ru": "Небольшой дождь", "uk": "Невеликий дощ", "en": "Slight rain", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "rain"},
    63: {"ru": "Дождь", "uk": "Дощ", "en": "Rain", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "rain"},
    65: {"ru": "Сильный дождь", "uk": "Сильний дощ", "en": "Heavy rain", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "rain"},
    66: {"ru": "Ледяной дождь", "uk": "Крижаний дощ", "en": "Freezing rain", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "rain"},
    67: {"ru": "Сильный ледяной дождь", "uk": "Сильний крижаний дощ", "en": "Heavy freezing rain", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "rain"},
    68: {"ru": "Дождь со снегом", "uk": "Дощ зі снігом", "en": "Rain and snow / Sleet", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "rain"},
    71: {"ru": "Небольшой снег", "uk": "Невеликий сніг", "en": "Slight snow", "icon_day": "snow.svg", "icon_night": "snow.svg", "grad": "snow"},
    73: {"ru": "Снегопад", "uk": "Снігопад", "en": "Snow fall", "icon_day": "snow.svg", "icon_night": "snow.svg", "grad": "snow"},
    75: {"ru": "Сильный снегопад", "uk": "Сильний снігопад", "en": "Heavy snow", "icon_day": "snow.svg", "icon_night": "snow.svg", "grad": "snow"},
    77: {"ru": "Снежные зерна", "uk": "Снігова крупа", "en": "Snow grains", "icon_day": "snow.svg", "icon_night": "snow.svg", "grad": "snow"},
    80: {"ru": "Ливень", "uk": "Злива", "en": "Rain showers", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "rain"},
    81: {"ru": "Умеренный ливень", "uk": "Помірна злива", "en": "Moderate showers", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "rain"},
    82: {"ru": "Сильный ливень", "uk": "Сильна злива", "en": "Violent showers", "icon_day": "rain.svg", "icon_night": "rain.svg", "grad": "rain"},
    85: {"ru": "Снегопад", "uk": "Снігопад", "en": "Snow showers", "icon_day": "snow.svg", "icon_night": "snow.svg", "grad": "snow"},
    86: {"ru": "Метель", "uk": "Хуртовина", "en": "Heavy snow showers", "icon_day": "snow.svg", "icon_night": "snow.svg", "grad": "snow"},
    95: {"ru": "Гроза", "uk": "Гроза", "en": "Thunderstorm", "icon_day": "thunderstorm.svg", "icon_night": "thunderstorm.svg", "grad": "storm"},
    96: {"ru": "Гроза с градом", "uk": "Гроза з градом", "en": "Thunderstorm with hail", "icon_day": "thunderstorm.svg", "icon_night": "thunderstorm.svg", "grad": "storm"},
    99: {"ru": "Сильная гроза с градом", "uk": "Сильна гроза з градом", "en": "Severe thunderstorm with hail", "icon_day": "thunderstorm.svg", "icon_night": "thunderstorm.svg", "grad": "storm"},
}

CONDITION_NAMES: dict[int, dict[str, Any]] = {
    0: {"ru": ("Солнечно", "Ясно"), "uk": ("Сонячно", "Ясно"), "en": ("Sunny", "Clear")},
    1: {"ru": "В основном ясно", "uk": "Переважно ясно", "en": "Mainly clear"},
    2: {"ru": "В основном облачно", "uk": "Мінлива хмарність", "en": "Partly cloudy"},
    3: {"ru": "Пасмурно", "uk": "Похмуро", "en": "Overcast"},
    45: {"ru": "Туман", "uk": "Туман", "en": "Fog"},
    48: {"ru": "Туман с изморозью", "uk": "Туман з памороззю", "en": "Rime fog"},
    51: {"ru": "Изморось", "uk": "Мряка", "en": "Light drizzle"},
    53: {"ru": "Умеренная изморось", "uk": "Помірна мряка", "en": "Moderate drizzle"},
    55: {"ru": "Плотная изморось", "uk": "Густа мряка", "en": "Dense drizzle"},
    56: {"ru": "Ледяная изморось", "uk": "Крижана мряка", "en": "Freezing drizzle"},
    57: {"ru": "Плотная ледяная изморось", "uk": "Густа крижана мряка", "en": "Dense freezing drizzle"},
    61: {"ru": "Небольшой дождь", "uk": "Невеликий дощ", "en": "Slight rain"},
    63: {"ru": "Дождь", "uk": "Дощ", "en": "Rain"},
    65: {"ru": "Сильный дождь", "uk": "Сильний дощ", "en": "Heavy rain"},
    66: {"ru": "Ледяной дождь", "uk": "Крижаний дощ", "en": "Freezing rain"},
    67: {"ru": "Сильный ледяной дождь", "uk": "Сильний крижаний дощ", "en": "Heavy freezing rain"},
    68: {"ru": "Дождь со снегом", "uk": "Дощ зі снігом", "en": "Sleet"},
    71: {"ru": "Небольшой снег", "uk": "Невеликий сніг", "en": "Slight snow"},
    73: {"ru": "Снегопад", "uk": "Снігопад", "en": "Snow fall"},
    75: {"ru": "Сильный снегопад", "uk": "Сильний снігопад", "en": "Heavy snow"},
    77: {"ru": "Снежные зерна", "uk": "Снігова крупа", "en": "Snow grains"},
    80: {"ru": "Ливень", "uk": "Злива", "en": "Rain showers"},
    81: {"ru": "Умеренный ливень", "uk": "Помірна злива", "en": "Moderate showers"},
    82: {"ru": "Сильный ливень", "uk": "Сильна злива", "en": "Violent showers"},
    85: {"ru": "Снегопад", "uk": "Снігопад", "en": "Snow showers"},
    86: {"ru": "Метель", "uk": "Хуртовина", "en": "Heavy snow showers"},
    95: {"ru": "Гроза", "uk": "Гроза", "en": "Thunderstorm"},
    96: {"ru": "Гроза с градом", "uk": "Гроза з градом", "en": "Thunderstorm with hail"},
    99: {"ru": "Сильная гроза с градом", "uk": "Сильна гроза з градом", "en": "Severe thunderstorm with hail"},
}


def get_condition_text(code: int, lang: str = "ru", is_day: bool = True) -> str:
    """Get localized weather condition text for given WMO code."""
    data = CONDITION_NAMES.get(code, CONDITION_NAMES.get(0, {}))
    val = data.get(lang, data.get("en", "Clear"))
    if isinstance(val, tuple):
        return val[0] if is_day else val[1]
    return val


MET_SYMBOL_TO_WMO: dict[str, tuple[int, int]] = {
    "clearsky_day": (0, 1),
    "clearsky_night": (0, 0),
    "fair_day": (1, 1),
    "fair_night": (1, 0),
    "partlycloudy_day": (2, 1),
    "partlycloudy_night": (2, 0),
    "cloudy": (3, 1),
    "fog": (45, 1),
    "lightrainshowers_day": (80, 1),
    "lightrainshowers_night": (80, 0),
    "rainshowers_day": (81, 1),
    "rainshowers_night": (81, 0),
    "heavyrainshowers_day": (82, 1),
    "heavyrainshowers_night": (82, 0),
    "lightrain": (61, 1),
    "rain": (63, 1),
    "heavyrain": (65, 1),
    "lightrainshowersandthunder_day": (95, 1),
    "heavyrainshowersandthunder_day": (95, 1),
    "rainandthunder": (95, 1),
    "lightsleet": (68, 1),
    "sleet": (68, 1),
    "heavysleet": (68, 1),
    "lightsnow": (71, 1),
    "snow": (73, 1),
    "heavysnow": (75, 1),
    "lightsnowshowers_day": (85, 1),
    "lightsnowshowers_night": (85, 0),
    "snowshowers_day": (86, 1),
    "snowshowers_night": (86, 0),
    "snowandthunder": (95, 1),
}


def met_symbol_to_wmo(sym: str, default_is_day: int = 1) -> tuple[int, int]:
    """Map MET Norway symbol code string to (wmo_code, is_day)."""
    if not sym:
        return (0, default_is_day)
    clean_sym = sym.split("?")[0].lower()
    if clean_sym in MET_SYMBOL_TO_WMO:
        code, is_d = MET_SYMBOL_TO_WMO[clean_sym]
        if clean_sym in ("cloudy", "fog", "rain", "lightrain", "heavyrain", "snow", "lightsnow", "heavysnow", "rainandthunder", "lightsleet", "sleet", "heavysleet"):
            return (code, default_is_day)
        return (code, is_d)

    is_d = 0 if "night" in clean_sym else (1 if "day" in clean_sym else default_is_day)
    if "thunder" in clean_sym:
        return (95, is_d)
    if "snow" in clean_sym:
        return (73, is_d)
    if "sleet" in clean_sym:
        return (68, is_d)
    if "rain" in clean_sym:
        return (63, is_d)
    if "fog" in clean_sym:
        return (45, is_d)
    if "partly" in clean_sym:
        return (2, is_d)
    if "cloud" in clean_sym:
        return (3, is_d)
    return (0, is_d)


WTTR_CODE_TO_WMO: dict[int, int] = {
    113: 0,   # Sunny/Clear
    116: 2,   # Partly Cloudy
    119: 3,   # Cloudy
    122: 3,   # Overcast
    143: 45,  # Mist
    176: 80,  # Patchy rain possible
    179: 85,  # Patchy snow possible
    182: 68,  # Patchy sleet possible
    185: 56,  # Patchy freezing drizzle possible
    200: 95,  # Thundery outbreaks possible
    227: 73,  # Blowing snow
    230: 75,  # Blizzard
    248: 45,  # Fog
    260: 48,  # Freezing fog
    263: 51,  # Patchy light drizzle
    266: 51,  # Light drizzle
    281: 56,  # Freezing drizzle
    284: 57,  # Heavy freezing drizzle
    293: 61,  # Patchy light rain
    296: 61,  # Light rain
    299: 63,  # Moderate rain at times
    302: 63,  # Moderate rain
    305: 65,  # Heavy rain at times
    308: 65,  # Heavy rain
    311: 66,  # Light freezing rain
    314: 67,  # Heavy freezing rain
    317: 68,  # Light sleet
    320: 68,  # Heavy sleet
    323: 71,  # Patchy light snow
    326: 71,  # Light snow
    329: 73,  # Patchy moderate snow
    332: 73,  # Moderate snow
    335: 75,  # Patchy heavy snow
    338: 75,  # Heavy snow
    350: 77,  # Ice pellets
    353: 80,  # Light rain shower
    356: 81,  # Moderate/heavy rain shower
    359: 82,  # Torrential rain shower
    362: 85,  # Light sleet showers
    365: 85,  # Moderate/heavy sleet showers
    368: 85,  # Light snow showers
    371: 86,  # Moderate/heavy snow showers
    374: 77,  # Light showers of ice pellets
    377: 77,  # Heavy showers of ice pellets
    386: 95,  # Light rain with thunder
    389: 95,  # Heavy rain with thunder
    392: 95,  # Light snow with thunder
    395: 95,  # Heavy snow with thunder
}


def wttr_code_to_wmo(code: int | str | None) -> int:
    """Map wttr.in weatherCode to WMO-4677 standard code."""
    if code is None:
        return 0
    try:
        val = int(code)
    except (TypeError, ValueError):
        return 0
    return WTTR_CODE_TO_WMO.get(val, 0)


WIND_DIRECTIONS_8: dict[str, list[tuple[str, str]]] = {
    "ru": [
        ("С", "Северный ветер"),
        ("СВ", "Северо-восточный ветер"),
        ("В", "Восточный ветер"),
        ("ЮВ", "Юго-восточный ветер"),
        ("Ю", "Южный ветер"),
        ("ЮЗ", "Юго-западный ветер"),
        ("З", "Западный ветер"),
        ("СЗ", "Северо-западный ветер"),
    ],
    "uk": [
        ("Пн", "Північний вітер"),
        ("ПнСх", "Північно-східний вітер"),
        ("Сх", "Східний вітер"),
        ("ПдСх", "Південно-східний вітер"),
        ("Пд", "Південний вітер"),
        ("ПдЗх", "Південно-західний вітер"),
        ("Зх", "Західний вітер"),
        ("ПнЗх", "Північно-західний вітер"),
    ],
    "en": [
        ("N", "North wind"),
        ("NE", "Northeast wind"),
        ("E", "East wind"),
        ("SE", "Southeast wind"),
        ("S", "South wind"),
        ("SW", "Southwest wind"),
        ("W", "West wind"),
        ("NW", "Northwest wind"),
    ],
}

WIND_DIRECTIONS_16: dict[str, list[str]] = {
    "ru": ["С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ", "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"],
    "uk": ["Пн", "ПнПнСх", "ПнСх", "СхПнСх", "Сх", "СхПдСх", "ПдСх", "ПдПдСх", "Пд", "ПдПдЗх", "ПдЗх", "ЗхПдЗх", "Зх", "ЗхПнЗх", "ПнЗх", "ПнПнЗх"],
    "en": ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"],
}

COMPASS_CARDINALS_4: dict[str, tuple[str, str, str, str]] = {
    "ru": ("С", "В", "Ю", "З"),
    "uk": ("Пн", "Сх", "Пд", "Зх"),
    "en": ("N", "E", "S", "W"),
}

COMPASS_INTERCARDINALS_4: dict[str, tuple[str, str, str, str]] = {
    # 315° (NW), 45° (NE), 135° (SE), 225° (SW)
    "ru": ("СЗ", "СВ", "ЮВ", "ЮЗ"),
    "uk": ("ПнЗ", "ПнС", "ПдС", "ПдЗ"),
    "en": ("NW", "NE", "SE", "SW"),
}


def get_wind_direction_info(deg: float | int | None, lang: str = "ru") -> tuple[str, str]:
    """Get cardinal abbreviation and full descriptive string for wind angle in degrees."""
    if deg is None:
        return ("--", "--")
    deg_val = (float(deg) % 360 + 360) % 360
    dirs = WIND_DIRECTIONS_8.get(lang, WIND_DIRECTIONS_8["en"])
    idx = int((deg_val + 22.5) // 45) % 8
    return dirs[idx][0], dirs[idx][1]


def get_geo_timezone_offset_seconds(lat: float, lon: float, tz_name: str = "") -> int:
    """UTC offset in seconds for a location.

    Uses the IANA timezone name (via stdlib zoneinfo) when the caller has one —
    exact including DST. Falls back to a fast offline estimate from longitude
    & latitude, which can be off by an hour for odd UTC offsets and DST zones.
    """
    if tz_name:
        try:
            from datetime import datetime as _dt
            from datetime import timezone as _tz
            from zoneinfo import ZoneInfo
            offset = _dt.now(_tz.utc).astimezone(ZoneInfo(tz_name)).utcoffset()
            if offset is not None:
                return int(offset.total_seconds())
        except Exception:
            pass
    is_russia = (lat > 41 and 19 <= lon <= 190)
    if is_russia:
        if lon < 21.0:
            return 2 * 3600
        elif lon < 49.5:
            return 3 * 3600
        elif lon < 55.0:
            return 4 * 3600
        elif lon < 69.0:
            return 5 * 3600
        elif lon < 78.0:
            return 6 * 3600
        elif lon < 93.0:
            return 7 * 3600
        elif lon < 108.0:
            return 8 * 3600
        elif lon < 122.0:
            return 9 * 3600
        elif lon < 137.0:
            return 10 * 3600
        elif lon < 152.0:
            return 11 * 3600
        else:
            return 12 * 3600
    return int(round(lon / 15.0) * 3600)


WEEKDAY_LETTERS = {
    "ru": ["П", "В", "С", "Ч", "П", "С", "В"],
    "en": ["M", "T", "W", "T", "F", "S", "S"],
}


def format_full_date(dt: datetime, lang: str = "ru") -> str:
    """Format full human-readable date, e.g. 'Среда, 14 октября 2026 г.'."""
    from core.i18n import get_month_name, get_weekday_name
    w_name = get_weekday_name(dt.weekday(), short=False, lang=lang)
    m_name = get_month_name(dt.month, genitive=True, lang=lang)
    if lang == "ru":
        return f"{w_name}, {dt.day} {m_name} {dt.year} г."
    return f"{w_name}, {dt.day} {m_name} {dt.year}"

