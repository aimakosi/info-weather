"""Internationalization (i18n) framework for info-weather.

Translations are stored in JSON resource files under `data/locales/{lang}.json` (ru/uk/en)
and are resolved via t(); date/time formatting helpers are included.
"""

from __future__ import annotations

import json
import locale
import os
from datetime import datetime
from pathlib import Path
from typing import Any

_current_language: str = "ru"

SUPPORTED_LANGUAGES = {
    "ru": "Русский",
    "uk": "Українська",
    "en": "English",
}

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "data" / "locales"
_loaded_locales: dict[str, dict[str, str]] = {}


def _load_locale(lang: str) -> dict[str, str]:
    """Load locale dictionary from data/locales/{lang}.json with caching."""
    if lang in _loaded_locales:
        return _loaded_locales[lang]

    json_path = _LOCALES_DIR / f"{lang}.json"
    if json_path.is_file():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _loaded_locales[lang] = data
                    return data
        except Exception:
            pass

    _loaded_locales[lang] = {}
    return _loaded_locales[lang]


def get_all_locales() -> dict[str, dict[str, str]]:
    """Get all supported locale string dictionaries."""
    for lang in SUPPORTED_LANGUAGES:
        if lang not in _loaded_locales:
            _load_locale(lang)
    return _loaded_locales


class _BuiltinStringsProxy(dict):
    """Backwards-compatible dictionary proxy exposing BUILTIN_STRINGS interface."""

    def __getitem__(self, key: str) -> dict[str, str]:
        get_all_locales()
        result = {}
        for lang, d in _loaded_locales.items():
            if key in d:
                result[lang] = d[key]
        if not result:
            raise KeyError(key)
        return result

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        get_all_locales()
        return any(key in d for d in _loaded_locales.values())

    def items(self):
        get_all_locales()
        all_keys = set()
        for d in _loaded_locales.values():
            all_keys.update(d.keys())
        for k in sorted(all_keys):
            yield (k, self[k])


BUILTIN_STRINGS = _BuiltinStringsProxy()


MONTHS_SHORT = {
    "ru": ["янв.", "февр.", "март", "апр.", "май", "июнь", "июль", "авг.", "сент.", "окт.", "нояб.", "дек."],
    "uk": ["січ.", "лют.", "берез.", "квіт.", "трав.", "черв.", "лип.", "серп.", "верес.", "жовт.", "листоп.", "груд."],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}

MONTHS_FULL = {
    "ru": ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"],
    "uk": ["січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень", "вересень", "жовтень", "листопад", "грудень"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}

MONTHS_GENITIVE = {
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"],
    "uk": ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}

WEEKDAYS_SHORT = {
    "ru": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    "uk": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

WEEKDAYS_FULL = {
    "ru": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
    "uk": ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}


def detect_system_language() -> str:
    """Detect primary language code from environment or locale settings."""
    for env_var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(env_var)
        if val:
            code = val.split(".")[0].split("_")[0].lower()
            if code in SUPPORTED_LANGUAGES:
                return code
            if code.startswith("ru"):
                return "ru"
            if code.startswith("uk"):
                return "uk"
            if code.startswith("en"):
                return "en"
    try:
        loc = locale.getlocale()[0]
        if loc:
            code = loc.split(".")[0].split("_")[0].lower()
            if code in SUPPORTED_LANGUAGES:
                return code
            if code.startswith("ru"):
                return "ru"
            if code.startswith("uk"):
                return "uk"
            if code.startswith("en"):
                return "en"
    except Exception:
        pass
    return "ru"


def set_language(lang: str) -> None:
    """Set active language (falls back to 'ru' for unsupported codes)."""
    global _current_language
    if lang not in SUPPORTED_LANGUAGES:
        lang = "ru"
    _current_language = lang


def get_current_language() -> str:
    """Get active language code ('ru', 'uk' or 'en')."""
    return _current_language


def t(key: str, **kwargs: Any) -> str:
    """Translate key via localized resource files and apply kwargs formatting."""
    lang = kwargs.pop("_lang", None) or _current_language
    strings = _load_locale(lang)
    text = strings.get(key)
    if text is None and lang != "en":
        text = _load_locale("en").get(key)
    if text is None:
        text = key

    if kwargs:
        if "{unit}" in text and "unit" not in kwargs:
            kwargs["unit"] = "°C"
        return text.format(**kwargs)
    return text


def get_month_name(month_num: int, short: bool = False, genitive: bool = False, lang: str | None = None) -> str:
    """Get localized month name (1..12)."""
    lang = lang or _current_language
    idx = max(0, min(11, month_num - 1))
    if genitive:
        names = MONTHS_GENITIVE.get(lang, MONTHS_GENITIVE["en"])
    elif short:
        names = MONTHS_SHORT.get(lang, MONTHS_SHORT["en"])
    else:
        names = MONTHS_FULL.get(lang, MONTHS_FULL["en"])
    return names[idx]


def get_weekday_name(weekday_idx: int, short: bool = True, lang: str | None = None) -> str:
    """Get localized weekday name (0=Monday..6=Sunday)."""
    lang = lang or _current_language
    idx = weekday_idx % 7
    if short:
        names = WEEKDAYS_SHORT.get(lang, WEEKDAYS_SHORT["en"])
    else:
        names = WEEKDAYS_FULL.get(lang, WEEKDAYS_FULL["en"])
    return names[idx]


def format_day_month(day: int, month: int, lang: str | None = None) -> str:
    """Format day and month, e.g. '14 октября' or '14 October'."""
    m_name = get_month_name(month, genitive=True, lang=lang)
    return f"{day} {m_name}"


# Supported display formats for the "Date format" setting in the Units tab.
DATE_FORMAT_OPTIONS = (
    "DD.MM",
    "DD.MM.YYYY",
    "MM/DD/YYYY",
    "YYYY-MM-DD",
    "DD MMM",
)


def format_date_str(date_iso: str, fmt: str = "DD.MM", lang: str | None = None) -> str:
    """Format an ISO date string (YYYY-MM-DD) for display."""
    if not date_iso or len(date_iso) < 10:
        return ""
    try:
        dt = datetime.strptime(date_iso[:10], "%Y-%m-%d")
    except ValueError:
        return date_iso[5:].replace("-", ".") if len(date_iso) >= 10 else date_iso

    day, month, year = dt.day, dt.month, dt.year
    if fmt == "DD.MM.YYYY":
        return f"{day:02d}.{month:02d}.{year:04d}"
    if fmt == "MM/DD/YYYY":
        return f"{month:02d}/{day:02d}/{year:04d}"
    if fmt == "YYYY-MM-DD":
        return f"{year:04d}-{month:02d}-{day:02d}"
    if fmt == "DD MMM":
        month_name = get_month_name(month, short=True, lang=lang)
        return f"{day:02d} {month_name}"
    return f"{day:02d}.{month:02d}"


# Initialize with detected system language on import
set_language(detect_system_language())
