"""Resource loader for info-weather with lazy-loading and caching."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_RESOURCES_DIR = Path(__file__).parent
_major_cities: dict[str, dict[str, Any]] | None = None
_era5_baseline: dict[str, Any] | None = None


def get_major_cities() -> dict[str, dict[str, Any]]:
    """Get dictionary of major cities (lazy loaded)."""
    global _major_cities
    if _major_cities is None:
        path = _RESOURCES_DIR / "major_cities.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    _major_cities = json.load(f)
            except Exception:
                _major_cities = {}
        else:
            _major_cities = {}
    return _major_cities


def get_era5_baseline() -> dict[str, Any]:
    """Get ERA5 baseline climatology (lazy loaded)."""
    global _era5_baseline
    if _era5_baseline is None:
        path = _RESOURCES_DIR / "era5_baseline.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    _era5_baseline = json.load(f)
            except Exception:
                _era5_baseline = {}
        else:
            _era5_baseline = {}
    return _era5_baseline


def find_city_by_name(name: str) -> dict[str, Any] | None:
    """Look up major city info dictionary by name or key."""
    clean = name.strip().lower()
    for prefix in ("погода в ", "погода ", "weather in ", "weather "):
        if clean.startswith(prefix):
            clean = clean[len(prefix):].strip()
            break
    if not clean:
        return None
    base_part = clean.split(",")[0].split("(")[0].strip()
    cities = get_major_cities()
    for q in (clean, base_part):
        if not q:
            continue
        if q in cities:
            return dict(cities[q])
        for key, info in cities.items():
            if (
                key.lower() == q
                or info.get("name_ru", "").lower() == q
                or info.get("name_en", "").lower() == q
                or info.get("name_uk", "").lower() == q
                or q in [kw.lower() for kw in info.get("keywords", [])]
            ):
                return dict(info)
    return None


def find_city_by_coords(lat: float, lon: float, threshold: float = 0.20) -> dict[str, Any] | None:
    """Find a city from major_cities.json closest to given coordinates within threshold (degrees)."""
    cities = get_major_cities()
    best: dict[str, Any] | None = None
    min_dist = float("inf")
    for info in cities.values():
        c_lat = float(info.get("lat", 0.0))
        c_lon = float(info.get("lon", 0.0))
        dist = ((lat - c_lat) ** 2 + (lon - c_lon) ** 2) ** 0.5
        if dist < threshold and dist < min_dist:
            min_dist = dist
            best = info
    return dict(best) if best else None


# Ukrainian country name translations
_UK_COUNTRIES: dict[str, str] = {
    "Россия": "Росія",
    "Russia": "Росія",
    "RU": "Росія",
    "Австралия": "Австралія",
    "Australia": "Австралія",
    "AU": "Австралія",
    "США": "США",
    "USA": "США",
    "US": "США",
    "Великобритания": "Великобританія",
    "UK": "Великобританія",
    "GB": "Великобританія",
    "United Kingdom": "Великобританія",
    "Германия": "Німеччина",
    "Germany": "Німеччина",
    "DE": "Німеччина",
    "Франция": "Франція",
    "France": "Франція",
    "FR": "Франція",
    "Италия": "Італія",
    "Italy": "Італія",
    "IT": "Італія",
    "Испания": "Іспанія",
    "Spain": "Іспанія",
    "ES": "Іспанія",
    "Китай": "Китай",
    "China": "Китай",
    "CN": "Китай",
    "Япония": "Японія",
    "Japan": "Японія",
    "JP": "Японія",
    "Канада": "Канада",
    "Canada": "Канада",
    "CA": "Канада",
    "Бразилия": "Бразилія",
    "Brazil": "Бразилія",
    "BR": "Бразилія",
    "Индия": "Індія",
    "India": "Індія",
    "IN": "Індія",
    "Турция": "Туреччина",
    "Turkey": "Туреччина",
    "TR": "Туреччина",
    "Казахстан": "Казахстан",
    "Kazakhstan": "Казахстан",
    "KZ": "Казахстан",
    "Беларусь": "Білорусь",
    "Belarus": "Білорусь",
    "BY": "Білорусь",
    "Украина": "Україна",
    "Ukraine": "Україна",
    "UA": "Україна",
}

_RU_COUNTRIES: dict[str, str] = {
    "Russia": "Россия",
    "Russian Federation": "Россия",
    "RU": "Россия",
    "Australia": "Австралия",
    "AU": "Австралия",
    "USA": "США",
    "United States": "США",
    "US": "США",
    "UK": "Великобритания",
    "GB": "Великобритания",
    "United Kingdom": "Великобритания",
    "Germany": "Германия",
    "DE": "Германия",
    "France": "Франция",
    "FR": "Франция",
    "Italy": "Италия",
    "IT": "Италия",
    "Spain": "Испания",
    "ES": "Испания",
    "China": "Китай",
    "CN": "Китай",
    "Japan": "Япония",
    "JP": "Япония",
    "Canada": "Канада",
    "CA": "Канада",
    "Brazil": "Бразилия",
    "BR": "Бразилия",
    "India": "Индия",
    "IN": "Индия",
    "Turkey": "Турция",
    "TR": "Турция",
    "Kazakhstan": "Казахстан",
    "KZ": "Казахстан",
    "Belarus": "Беларусь",
    "BY": "Беларусь",
    "Ukraine": "Украина",
    "UA": "Украина",
}

_EN_COUNTRIES: dict[str, str] = {
    "Россия": "Russia",
    "Росія": "Russia",
    "RU": "Russia",
    "Австралия": "Australia",
    "Австралія": "Australia",
    "AU": "Australia",
    "США": "USA",
    "US": "USA",
    "Великобритания": "United Kingdom",
    "Великобританія": "United Kingdom",
    "UK": "United Kingdom",
    "GB": "United Kingdom",
    "Германия": "Germany",
    "Німеччина": "Germany",
    "DE": "Germany",
    "Франция": "France",
    "Франція": "France",
    "FR": "France",
    "Италия": "Italy",
    "Італія": "Italy",
    "IT": "Italy",
    "Испания": "Spain",
    "Іспанія": "Spain",
    "ES": "Spain",
    "Китай": "China",
    "CN": "China",
    "Япония": "Japan",
    "Японія": "Japan",
    "JP": "Japan",
    "Канада": "Canada",
    "CA": "Canada",
    "Бразилия": "Brazil",
    "Бразилія": "Brazil",
    "BR": "Brazil",
    "Индия": "India",
    "Індія": "India",
    "IN": "India",
    "Турция": "Turkey",
    "Туреччина": "Turkey",
    "TR": "Turkey",
    "Казахстан": "Kazakhstan",
    "KZ": "Kazakhstan",
    "Беларусь": "Belarus",
    "Білорусь": "Belarus",
    "BY": "Belarus",
    "Украина": "Ukraine",
    "Україна": "Ukraine",
    "UA": "Ukraine",
}

# Common Ukrainian city names mapping
_UK_CITIES: dict[str, str] = {
    "Москва": "Москва",
    "Moscow": "Москва",
    "Абакан": "Абакан",
    "Abakan": "Абакан",
    "Санкт-Петербург": "Санкт-Петербург",
    "Saint Petersburg": "Санкт-Петербург",
    "Новосибирск": "Новосибірськ",
    "Novosibirsk": "Новосибірськ",
    "Екатеринбург": "Єкатеринбург",
    "Yekaterinburg": "Єкатеринбург",
    "Киев": "Київ",
    "Kyiv": "Київ",
    "Kiev": "Київ",
    "Харьков": "Харків",
    "Kharkiv": "Харків",
    "Одесса": "Одеса",
    "Odesa": "Одеса",
    "Днепр": "Дніпро",
    "Dnipro": "Дніпро",
    "Львов": "Львів",
    "Lviv": "Львів",
    "Мельбурн": "Мельбурн",
    "Melbourne": "Мельбурн",
    "Лондон": "Лондон",
    "London": "Лондон",
    "Париж": "Париж",
    "Paris": "Париж",
    "Берлин": "Берлін",
    "Berlin": "Берлін",
    "Рим": "Рим",
    "Rome": "Рим",
    "Токио": "Токіо",
    "Tokyo": "Токіо",
    "Нью-Йорк": "Нью-Йорк",
    "New York": "Нью-Йорк",
}


def _transliterate_cyr_to_lat(text: str) -> str:
    """Simple transliteration from Cyrillic to Latin for city names."""
    table = {
        "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "Yo",
        "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
        "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
        "Ф": "F", "Х": "Kh", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh", "Щ": "Shch",
        "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "Yu", "Я": "Ya",
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
        "І": "I", "і": "i", "Ї": "Yi", "ї": "yi", "Є": "Ye", "є": "ye", "Ґ": "G", "ґ": "g",
    }
    return "".join(table.get(ch, ch) for ch in text)


def _is_city_match(name: str, info: dict[str, Any]) -> bool:
    """Check if the provided name matches or is an alias for the city info."""
    clean = name.strip().lower()
    for prefix in ("погода в ", "погода ", "weather in ", "weather "):
        if clean.startswith(prefix):
            clean = clean[len(prefix):].strip()
            break
    if not clean:
        return True

    # If name contains comma or parenthesis (e.g. "Moscow, Russia"), extract the city portion
    base_part = clean.split(",")[0].split("(")[0].strip()

    names = {
        info.get("name_ru", "").strip().lower(),
        info.get("name_en", "").strip().lower(),
        info.get("name_uk", "").strip().lower(),
    }
    for kw in info.get("keywords", []):
        names.add(kw.strip().lower())

    ru_name = info.get("name_ru", "")
    if ru_name in _UK_CITIES:
        names.add(_UK_CITIES[ru_name].strip().lower())
    en_name = info.get("name_en", "")
    if en_name in _UK_CITIES:
        names.add(_UK_CITIES[en_name].strip().lower())

    names.discard("")

    for n in names:
        if clean == n or base_part == n:
            return True
        trans_clean = _transliterate_cyr_to_lat(base_part).lower()
        if trans_clean == n or base_part == _transliterate_cyr_to_lat(n).lower():
            return True
        n_no_hyphen = n.replace("-", " ")
        b_no_hyphen = base_part.replace("-", " ")
        if b_no_hyphen == n_no_hyphen:
            return True

    return False


def localize_city(
    name: str = "",
    lat: float | None = None,
    lon: float | None = None,
    country: str = "",
    lang: str = "ru",
) -> tuple[str, str]:
    """
    Return (localized_city_name, localized_country) for the given language.
    Resolves via:
      1. Coordinates matching bundled major_cities.json
      2. Name matching bundled major_cities.json
      3. Dictionary transliteration / mapping fallback
    """
    target_lang = lang if lang in ("ru", "en", "uk") else "ru"
    info: dict[str, Any] | None = None

    if lat is not None and lon is not None:
        try:
            candidate = find_city_by_coords(float(lat), float(lon))
            if candidate and (not name or _is_city_match(name, candidate)):
                info = candidate
        except (ValueError, TypeError):
            info = None

    if not info and name:
        info = find_city_by_name(name)

    if info:
        if target_lang == "en":
            loc_name = info.get("name_en") or info.get("name_ru") or name
            loc_country = info.get("country_en") or _EN_COUNTRIES.get(country, country)
        elif target_lang == "uk":
            loc_name = info.get("name_uk") or _UK_CITIES.get(info.get("name_ru", ""), "") or info.get("name_ru") or name
            loc_country = info.get("country_uk") or _UK_COUNTRIES.get(country) or _UK_COUNTRIES.get(info.get("country_ru", "")) or country
        else:  # ru
            loc_name = info.get("name_ru") or info.get("name_en") or name
            loc_country = info.get("country_ru") or _RU_COUNTRIES.get(country, country)
        return loc_name, loc_country

    # Fallback when not in major_cities.json
    loc_name = name
    loc_country = country

    if target_lang == "en":
        if any("\u0400" <= ch <= "\u04ff" for ch in loc_name):
            loc_name = _transliterate_cyr_to_lat(loc_name)
        if country in _EN_COUNTRIES:
            loc_country = _EN_COUNTRIES[country]
    elif target_lang == "uk":
        if name in _UK_CITIES:
            loc_name = _UK_CITIES[name]
        if country in _UK_COUNTRIES:
            loc_country = _UK_COUNTRIES[country]
    elif target_lang == "ru":
        if country in _RU_COUNTRIES:
            loc_country = _RU_COUNTRIES[country]

    return loc_name, loc_country


def search_local_cities(query: str, lang: str = "ru", limit: int = 10) -> list[Any]:
    """Fuzzy and prefix search through bundled major cities resource."""
    from providers.base import SearchResult

    clean = query.strip().lower()
    for prefix in ("погода в ", "погода ", "weather in ", "weather "):
        if clean.startswith(prefix):
            clean = clean[len(prefix):].strip()
            break
    if not clean:
        return []

    cities = get_major_cities()
    matches: list[tuple[int, SearchResult]] = []

    for key, info in cities.items():
        name_ru = info.get("name_ru", "")
        name_en = info.get("name_en", "")
        country_ru = info.get("country_ru", "")
        country_en = info.get("country_en", "")
        keywords = [kw.lower() for kw in info.get("keywords", [])]

        display_name = name_ru if lang == "ru" and name_ru else (name_en or name_ru or key)
        display_country = country_ru if lang == "ru" and country_ru else (country_en or country_ru)

        score = 0
        if clean == key or clean == name_ru.lower() or clean == name_en.lower():
            score = 100
        elif name_ru.lower().startswith(clean) or name_en.lower().startswith(clean) or key.startswith(clean):
            score = 80
        elif clean in name_ru.lower() or clean in name_en.lower() or clean in key:
            score = 60
        elif any(clean == kw for kw in keywords):
            score = 50
        elif any(clean in kw for kw in keywords):
            score = 40

        if score > 0:
            sr = SearchResult(
                name=display_name,
                country=display_country,
                lat=float(info.get("lat", 0.0)),
                lon=float(info.get("lon", 0.0)),
                timezone="auto",
            )
            matches.append((score, sr))

    matches.sort(key=lambda x: -x[0])
    return [sr for _, sr in matches[:limit]]

