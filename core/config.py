"""
Configuration Manager for info-weather.
Handles loading, saving, whitelist-validation, atomic file writes,
backups of corrupted configs, and schema migrations.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger("core.config")

CONFIG_SCHEMA_VERSION = 1

# Дефолты «как у меня» (FR-14, эталон привычного информера пользователя)
DEFAULT_CONFIGURATION: dict[str, Any] = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "cities": [],  # При первом запуске пуст; используется дефолтный город Абакан (providers/weather.py)
    "home_city": "",
    "current_city": "",
    "layout": [
        {
            "type": "header",
            "enabled": True,
            "order": 0,
            "options": {"show_current_temp": True, "show_feels_like": True},
        },
        {
            "type": "today_summary",
            "enabled": True,
            "order": 1,
            "options": {"show_today": False, "show_tomorrow": True},
        },
        {
            "type": "metrics_compass",
            "enabled": True,
            "order": 2,
            "options": {
                "compass": True,
                "humidity": True,
                "pressure": True,
                "uv": False,
                "visibility": False,
            },
        },
        {
            "type": "daily_forecast",
            "enabled": True,
            "order": 3,
            "options": {"days": 6},
        },
        {
            "type": "hourly_forecast",
            "enabled": False,
            "order": 4,
            "options": {"hours": 24},
        },
    ],
    "view_blocks": {
        "now": {
            "enabled": True,
            "offset_x": 0,
            "offset_y": 0,
        },
        "wind": {
            "enabled": True,
            "offset_x": 0,
            "offset_y": 0,
            "angle": 0,
        },
        "additional_info": {
            "enabled": False,
            "offset_x": 0,
            "offset_y": 0,
        },
        "tomorrow": {
            "enabled": True,
            "offset_x": 0,
            "offset_y": 0,
        },
        "today": {
            "enabled": False,
            "offset_x": 0,
            "offset_y": 0,
        },
        "astronomy": {
            "enabled": True,
            "offset_x": 0,
            "offset_y": 0,
            "show_moon": True,
            "show_geomagnetic": True,
        },
        "daily": {
            "enabled": True,
            "offset_x": 0,
            "offset_y": 0,
            "days": 5,
            "horizontal": True,
            "show_precip_prob": True,
        },
    },
    "skin": {
        "name": "default_dark",
        "icons_name": "svg",  # Theme of weather icons: svg (native), Meteocons_monochrome, WeatherIcons
        "theme_mode": "auto_solar",  # "auto_solar", "auto_system", "day", "night"
        "scale": 1.0,
        "opacity": 1.0,
        "show_shadows": True,
        "font_family": "Serif",
        "font_size": 10,
        "small_font_family": "Serif",
        "small_font_size": 9,
        "weekend_color": "#ef4444",
        "wind_arrow_color": "#ef4444",
    },
    "seasonal_theme": {
        "enabled": True,
        "mode": "auto",  # "auto", "winter", "spring", "summer", "autumn"
    },
    "landmark": {
        "enabled": False,
        "image_path": "",
        "locations": {},
        "dimming": 0.35,
        "blur_radius": 3.0,
        "weather_effects": True,
        "active_effect": "auto",
    },
    "formats": {
        "t_fmt": "{t_day}\n{t_night}",
        "t_now_fmt": "{t_now}",
        "day_date_fmt": "{day}, {date}",
        "date_format": "DD.MM",  # DD.MM, DD.MM.YYYY, MM/DD/YYYY, YYYY-MM-DD, DD MMM
        "wind_fmt": "{wind_direct}, {wind_speed}",
        "weekend": "Sa, Su",
    },
    "units": {
        "temp": "C",  # C, F
        "wind": "m/s",  # m/s, km/h, mph, kn, beaufort
        "pressure": "mmHg",  # mmHg, hPa, inHg
        "distance": "km",  # km, mi
        "precipitation": "mm",  # mm, in
    },
    "update_interval_minutes": 60,
    "max_consensus_age_minutes": 120,
    "network": {
        "timeout_seconds": 8.0,          # таймаут одного HTTP-запроса
        "dns_timeout_seconds": 5.0,      # предел ожидания DNS-резолвинга
        "retries": 1,                    # число повторов при ошибке
        "prefer_ipv4": True,             # сначала IPv4 (обход сломанного IPv6)
        "fetch_timeout_seconds": 30.0,   # общий предел одного цикла обновления
    },
    "wheel_city_switch": True,
    "wheel_debounce_ms": 400,
    "notifications": {
        "enabled": True,
        "types": {
            "rain_snow_1h": True,
            "frost": True,
            "strong_wind": True,
            "sharp_temperature_change": True,
            "high_uv": False,
        },
        "quiet_hours": {
            "enabled": False,
            "start": "23:00",
            "end": "07:00",
        },
    },
    "animation_mode": "balanced",  # performance, balanced, power_saver
    "app_language": "ru",
    "weather_language": "ru",
    "display_mode": "both",  # both, widget_only, indicator_only
    "data_source": "consensus",  # consensus, open_meteo, met_norway, wttr
    "open_meteo_model": "best_match",
    "autostart": False,
    "autostart_delay_sec": 0,
    "window_behavior": {
        "lock_position": False,
        "on_all_desktops": False,
        "always_on_top": False,
        "show_in_taskbar": False,
    },
    "window_position": {
        "x": None,
        "y": None,
        "save_position": True,
        "saved": False,  # True once the user has actually positioned the widget
    },
}


def get_default_config_path() -> Path:
    """Return standard XDG config file path: ~/.config/info-weather/config.json"""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        base_dir = Path(xdg_config)
    else:
        base_dir = Path.home() / ".config"
    return base_dir / "info-weather" / "config.json"


class ConfigManager:
    """Manages application configuration lifecycle."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = Path(config_path) if config_path else get_default_config_path()
        self._data: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIGURATION)
        self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by top-level key."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        """Set config value and optionally save atomically."""
        self._data[key] = value
        if auto_save:
            self.save()

    def reset_to_defaults(self) -> None:
        """Reset configuration in memory and save to disk."""
        self._data = copy.deepcopy(DEFAULT_CONFIGURATION)
        self.save()

    def to_dict(self) -> dict[str, Any]:
        """Return a deep copy of current configuration dictionary."""
        return copy.deepcopy(self._data)

    def all(self) -> dict[str, Any]:
        """Return full configuration dictionary (alias for to_dict)."""
        return self.to_dict()

    def load(self) -> bool:
        """
        Load configuration from disk.
        If file is missing, initializes with default configuration.
        If file is corrupted, backs it up and resets to defaults.
        """
        if not self.config_path.exists():
            logger.info("Config file does not exist at %s, using defaults", self.config_path)
            self._data = copy.deepcopy(DEFAULT_CONFIGURATION)
            return True

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            if not isinstance(raw_data, dict):
                raise ValueError("Config root must be a JSON dictionary")

            validated_data = self._validate_and_migrate(raw_data)
            self._data = validated_data
            logger.debug("Configuration successfully loaded from %s", self.config_path)
            return True

        except Exception as e:
            logger.warning("Corrupted or invalid config at %s: %s. Recovering with backup.", self.config_path, e)
            self._backup_corrupted_file()
            self._data = copy.deepcopy(DEFAULT_CONFIGURATION)
            self.save()
            return False

    def save(self) -> bool:
        """
        Atomically write configuration to disk.
        Uses temporary file in the same directory and replaces atomically.
        """
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            dir_path = self.config_path.parent

            # Атомарная запись через tempfile на той же файловой системе
            with tempfile.NamedTemporaryFile("w", dir=dir_path, delete=False, encoding="utf-8") as tmp:
                json.dump(self._data, tmp, indent=2, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_name = tmp.name

            # Атомарная замена
            os.replace(temp_name, self.config_path)
            logger.debug("Configuration atomically saved to %s", self.config_path)
            return True

        except Exception as e:
            logger.error("Failed to save config to %s: %s", self.config_path, e)
            return False

    def _validate_and_migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate data against default schema and perform schema migration.
        Fills missing keys from DEFAULT_CONFIGURATION and strips unknown keys.
        """
        version = data.get("schema_version", 0)

        # Будущие миграции схемы:
        if version < CONFIG_SCHEMA_VERSION:
            data = self._migrate_schema(data, version, CONFIG_SCHEMA_VERSION)

        result = copy.deepcopy(DEFAULT_CONFIGURATION)

        # Whitelist-валидация и рекурсивное слияние
        for key, default_val in DEFAULT_CONFIGURATION.items():
            if key in data:
                if isinstance(default_val, dict) and isinstance(data[key], dict):
                    # Слияние вложенных словарей (например units, skin, notifications)
                    merged_sub = copy.deepcopy(default_val)
                    for sub_k, sub_v in data[key].items():
                        if sub_k in default_val:
                            if isinstance(default_val[sub_k], dict) and isinstance(sub_v, dict):
                                nested = copy.deepcopy(default_val[sub_k])
                                nested.update(sub_v)
                                merged_sub[sub_k] = nested
                            else:
                                merged_sub[sub_k] = sub_v
                    result[key] = merged_sub
                else:
                    result[key] = data[key]

        # Ensure daily forecast is always horizontal as requested
        if "view_blocks" in result and isinstance(result["view_blocks"], dict):
            daily_sec = result["view_blocks"].setdefault("daily", {})
            if isinstance(daily_sec, dict):
                daily_sec["horizontal"] = True
                if "days" in daily_sec and isinstance(daily_sec["days"], (int, float)):
                    daily_sec["days"] = min(max(1, int(daily_sec["days"])), 5)

        return result

    def _migrate_schema(self, data: dict[str, Any], from_ver: int, to_ver: int) -> dict[str, Any]:
        """Migrate configuration data between schema versions."""
        logger.info("Migrating configuration from schema v%s to v%s", from_ver, to_ver)
        data["schema_version"] = to_ver
        return data

    def _backup_corrupted_file(self) -> None:
        """Create a timestamped backup of the corrupted config file."""
        try:
            if self.config_path.exists():
                timestamp = int(time.time())
                backup_path = self.config_path.with_name(f"{self.config_path.name}.corrupted.{timestamp}.bak")
                shutil.copy2(self.config_path, backup_path)
                logger.info("Created backup of corrupted config at %s", backup_path)
        except Exception as e:
            logger.error("Failed to backup corrupted config file: %s", e)
