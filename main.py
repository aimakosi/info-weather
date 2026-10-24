#!/usr/bin/env python3
"""
info-weather: Modern Qt (PySide6) Linux desktop weather widget.

Entry point supporting both interactive Qt widget mode and headless CLI mode.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

from core.cache import CacheManager
from core.config import ConfigManager
from core.i18n import detect_system_language
from core.logging import get_logger, setup_logging
from core.units import format_temp, format_wind_speed
from models.weather import WeatherForecastData
from providers.base import SearchResult
from providers.weather import WeatherProvider

logger = get_logger("main")

try:
    VERSION = pkg_version("info-weather")
except PackageNotFoundError:
    # Running from a source checkout without installation — keep in sync with pyproject.toml.
    VERSION = "0.1.0"


def print_cli_forecast(
    data: WeatherForecastData,
    lang: str = "ru",
    temp_unit: str = "celsius",
    wind_unit: str = "m_s",
) -> None:
    """Render a clean, structured weather report in terminal."""
    print("=" * 60)
    print(f" INFO WEATHER — {data.city_name}, {data.country} ({data.lat:.4f}, {data.lon:.4f})")
    print(f" Статус: [{data.consensus_level}] {data.status_text}")
    print(f" Источники: {data.source_name} (модель: {data.weather_model})")
    print("=" * 60)

    cur = data.current
    print(f" Погода сейчас:   {cur.condition_text or 'Ясно'} ({format_temp(cur.temp, temp_unit)})")
    print(f" Ощущается как:  {format_temp(cur.feels_like, temp_unit)}")
    print(f" Ветер:           {format_wind_speed(cur.wind_speed, wind_unit)} (порывы до {format_wind_speed(cur.wind_gusts or cur.wind_speed, wind_unit)}, {cur.wind_cardinal})")
    print(f" Давление (MSL):  {cur.pressure_mm} мм рт. ст. ({cur.pressure_hpa} hPa)")
    print(f" Влажность:       {cur.humidity}% (точка росы: {format_temp(cur.dew_point, temp_unit)})")
    print(f" УФ-индекс:       {cur.uv_index:.1f}")
    print(f" Видимость:       {cur.visibility_km:.1f} км")

    if data.solar_details:
        sd = data.solar_details
        print("-" * 60)
        print(f" Восход: {sd.sunrise} | Закат: {sd.sunset} | Долгота дня: {sd.daylight_str}")

    if data.detailed_moon:
        dm = data.detailed_moon
        print(f" Луна: {dm.phase_name} ({dm.illumination}%), {dm.distance_str}")

    if data.daily:
        from data.wmo_conditions import get_condition_text
        print("-" * 60)
        print(" ПРОГНОЗ ПО ДНЯМ:")
        for d in data.daily[:7]:
            cond = get_condition_text(d.code, lang=lang)
            precip_info = f", осадки {d.precip_prob_max}%" if d.precip_prob_max else ""
            print(f"   {d.day:<12} {d.date_str} | {d.min:+3.0f}° ... {d.max:+3.0f}° | {cond}{precip_info}")

    print("=" * 60)


def print_cli_search_results(results: list[SearchResult]) -> None:
    """Print geocoding search results in terminal."""
    if not results:
        print("Города не найдены.")
        return
    print(f"Найдено результатов: {len(results)}")
    print(f"{'№':<3} {'Город':<25} {'Страна':<20} {'Координаты':<20}")
    print("-" * 70)
    for i, r in enumerate(results, 1):
        coords = f"{r.lat:.4f}, {r.lon:.4f}"
        admin = f" ({r.admin1})" if r.admin1 else ""
        print(f"{i:<3} {r.name + admin:<25} {r.country:<20} {coords:<20}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="info-weather: Linux desktop weather widget and CLI client"
    )
    parser.add_argument("-c", "--city", help="City name or 'lat,lon' coordinates")
    parser.add_argument("-s", "--search", help="Search cities via geocoding cascade")
    parser.add_argument("--headless", action="store_true", help="Run in headless terminal mode")
    parser.add_argument("--replay", action="store_true", help="Replay consensus from cached responses")
    parser.add_argument("--autostart", action="store_true", help="Launch in autostart mode without stealing window focus")
    parser.add_argument("--delay", type=int, default=0, help="Optional delay in seconds before launching (for session startup)")
    parser.add_argument("--xcb", action="store_true", help="Force the X11 (xcb) Qt platform plugin instead of native Wayland")
    parser.add_argument("--config-path", help="Path to custom config.json")
    parser.add_argument("--reset-config", action="store_true", help="Reset config to defaults")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("-v", "--version", action="version", version=f"info-weather {VERSION}")

    args = parser.parse_args()

    if args.delay > 0:
        time.sleep(args.delay)

    setup_logging(level=logging.DEBUG if args.debug else logging.INFO)
    logger.debug("Starting info-weather version %s", VERSION)

    config_manager = ConfigManager(config_path=args.config_path)
    if args.reset_config:
        config_manager.reset_to_defaults()
        print("Конфигурация сброшена до заводских настроек по умолчанию.")
        return 0

    cache_manager = CacheManager()
    lang = config_manager.get("weather_language", "ru")
    if lang == "auto":
        lang = detect_system_language()

    units_cfg = config_manager.get("units", {}) or {}
    temp_unit = "fahrenheit" if str(units_cfg.get("temp", "C")).lower() == "f" else "celsius"
    wind_unit = str(units_cfg.get("wind", "m/s"))

    provider = WeatherProvider(
        config_manager=config_manager,
        cache_manager=cache_manager,
        lang=lang,
    )

    try:
        # 1. Geocoding search mode
        if args.search:
            results = provider.search_cities(args.search)
            print_cli_search_results(results)
            return 0

        # 2. Resolve target coordinates
        lat, lon = 53.7167, 91.4292
        city_name, country = "Абакан", "Россия"
        tz_name = ""

        if args.city:
            if "," in args.city:
                try:
                    parts = args.city.split(",")
                    lat, lon = float(parts[0].strip()), float(parts[1].strip())
                    city_name = f"Координаты {lat:.2f},{lon:.2f}"
                    country = ""
                except ValueError:
                    search_res = provider.search_cities(args.city)
                    if search_res:
                        lat, lon = search_res[0].lat, search_res[0].lon
                        city_name, country = search_res[0].name, search_res[0].country
                        tz_name = search_res[0].timezone if search_res[0].timezone != "auto" else ""
            else:
                search_res = provider.search_cities(args.city)
                if search_res:
                    lat, lon = search_res[0].lat, search_res[0].lon
                    city_name, country = search_res[0].name, search_res[0].country
                    tz_name = search_res[0].timezone if search_res[0].timezone != "auto" else ""
                else:
                    print(f"Город '{args.city}' не найден в базе данных.", file=sys.stderr)
                    return 1
        else:
            active_info = provider.get_active_city_info()
            lat = active_info.get("lat", 53.7167)
            lon = active_info.get("lon", 91.4292)
            city_name = active_info.get("name", "Абакан")
            country = active_info.get("country", "Россия")
            tz_name = active_info.get("timezone", "")

        # 3. Headless / Replay Mode check
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        is_headless = args.headless or args.replay or not has_display

        if is_headless:
            if args.replay:
                data = provider.replay_forecast(lat, lon, city_name=city_name, country=country, tz_name=tz_name)
                if not data:
                    print(f"Нет сохраненных данных для воспроизведения ({lat:.4f}, {lon:.4f}).", file=sys.stderr)
                    return 1
            else:
                data = provider.fetch_forecast(lat, lon, city_name=city_name, country=country, force_refresh=True, tz_name=tz_name)

            print_cli_forecast(data, lang=lang, temp_unit=temp_unit, wind_unit=wind_unit)
            return 0

        # 4. GUI Mode: Native Qt/KDE (PySide6). The Qt platform plugin is
        # chosen by Qt itself (native Wayland where available); pass --xcb
        # to force the X11 backend.
        if args.xcb:
            os.environ["QT_QPA_PLATFORM"] = "xcb"

        try:
            from ui.app import run_qt_app
            from ui.qt_compat import QT_API
            logger.info("Starting Qt GUI (%s) for KDE / Desktop...", QT_API)
            return run_qt_app(provider=provider, config_manager=config_manager, is_autostart=args.autostart)
        except ImportError as e_qt:
            print(
                f"\n[info-weather] Для запуска графического виджета под KDE требуется PySide6.\n"
                f"Ошибка: {e_qt}\n\n"
                f"Установите PySide6 одной командой:\n"
                f"    pip install PySide6\n"
                f"или через пакетный менеджер вашей системы:\n"
                f"    Arch/Manjaro:  sudo pacman -S python-pyside6\n"
                f"    Fedora:        sudo dnf install python3-pyside6\n"
                f"    Ubuntu/Debian: sudo apt install python3-pyside6.qtwidgets python3-pyside6.qtsvg\n",
                file=sys.stderr,
            )
            return 1

    finally:
        provider.close()


if __name__ == "__main__":
    sys.exit(main())
