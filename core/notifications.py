"""Meteorological notification engine for info-weather (FR-11).

Evaluates consensus weather forecast data and detects meteorological events:
- Rain / precipitation onset in the next hour
- Frost onset (temperature < 0 °C)
- High wind warning (> 10 m/s)
- Sharp temperature drop or surge (> 5 °C within 12 hours)
- High UV index (>= 6)

Features:
- Persistent event ID tracking across restarts to avoid duplicate alerts
- Configurable Quiet Hours (e.g., 22:00 to 08:00)
- Scoped strictly to active / home city
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logging import get_logger
from models.weather import WeatherForecastData

logger = get_logger("notifications")

DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "info-weather"
DEFAULT_STATE_FILE = DEFAULT_STATE_DIR / "notifications.json"

NOTIFICATION_TYPE_MAPPING: dict[str, list[str]] = {
    "rain_snow_1h": ["precipitation"],
    "strong_wind": ["high_wind"],
    "sharp_temperature_change": ["temp_drop", "temp_surge"],
    "frost": ["frost"],
    "high_uv": ["high_uv"],
    "precipitation": ["precipitation"],
    "high_wind": ["high_wind"],
    "temp_drop": ["temp_drop"],
    "temp_surge": ["temp_surge"],
}


@dataclass
class WeatherEvent:
    """Detected meteorological event ready for desktop notification."""
    event_id: str
    event_type: str  # precipitation, frost, high_wind, temp_drop, temp_surge, high_uv
    title: str
    body: str
    severity: str = "normal"  # low, normal, critical
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NotificationEngine:
    """Analyzes weather data, dedupes events, and respects quiet hours."""

    def __init__(
        self,
        state_file: Path | str | None = None,
        max_history_days: int = 7,
    ):
        self.state_file = Path(state_file) if state_file else DEFAULT_STATE_FILE
        self.max_history_days = max_history_days
        self._lock = threading.Lock()
        self._dispatched_event_ids: dict[str, float] = {}
        self._load_state()

    def _load_state(self) -> None:
        with self._lock:
            if not self.state_file.exists():
                return
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._dispatched_event_ids = {
                            str(k): float(v) for k, v in data.items()
                        }
                self._prune_history_locked()
            except Exception as e:
                logger.warning("Could not load notifications state from %s: %s", self.state_file, e)

    def _prune_history_locked(self) -> None:
        cutoff = time.time() - (self.max_history_days * 86400)
        self._dispatched_event_ids = {
            k: v for k, v in self._dispatched_event_ids.items() if v >= cutoff
        }

    def _save_state_locked(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.state_file.parent, prefix="notif_state_", suffix=".tmp")
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(self._dispatched_event_ids, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.state_file)
        except Exception as e:
            logger.warning("Failed to atomically save notifications state: %s", e)

    def is_quiet_hours(
        self,
        now_dt: datetime,
        quiet_start: str = "22:00",
        quiet_end: str = "08:00",
    ) -> bool:
        """Check if given datetime falls within quiet hours (e.g. 22:00 - 08:00)."""
        try:
            s_h, s_m = map(int, quiet_start.split(":"))
            e_h, e_m = map(int, quiet_end.split(":"))
        except Exception:
            return False

        current_min = now_dt.hour * 60 + now_dt.minute
        start_min = s_h * 60 + s_m
        end_min = e_h * 60 + e_m

        if start_min <= end_min:
            return start_min <= current_min < end_min
        else:
            # Over midnight (e.g. 22:00 to 08:00)
            return current_min >= start_min or current_min < end_min

    def evaluate_forecast(
        self,
        data: WeatherForecastData,
        enabled_types: list[str] | None = None,
        quiet_hours_enabled: bool = True,
        quiet_start: str = "22:00",
        quiet_end: str = "08:00",
        lang: str = "ru",
        now_dt: datetime | None = None,
    ) -> list[WeatherEvent]:
        """
        Evaluate forecast data and return list of newly triggered, deduplicated events.
        """
        if enabled_types is None:
            active_types = {
                "precipitation",
                "frost",
                "high_wind",
                "temp_drop",
                "temp_surge",
                "high_uv",
            }
        else:
            active_types = set()
            for t_name in enabled_types:
                if t_name in NOTIFICATION_TYPE_MAPPING:
                    active_types.update(NOTIFICATION_TYPE_MAPPING[t_name])
                else:
                    active_types.add(t_name)

        if now_dt is None:
            now_dt = datetime.now()

        # Check quiet hours
        if quiet_hours_enabled and self.is_quiet_hours(now_dt, quiet_start, quiet_end):
            logger.debug("Quiet hours active (%s - %s), skipping notification generation", quiet_start, quiet_end)
            return []

        # Hourly entries starting from the current hour (data may include past hours)
        utc_now = now_dt.astimezone(timezone.utc) if now_dt.tzinfo else datetime.now(timezone.utc)
        now_hour_iso = utc_now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        future_hours = [
            h for h in data.hourly
            if getattr(h, "time_iso", "") and h.time_iso >= now_hour_iso
        ]
        if not future_hours:
            # No UTC timestamps available (offline baseline, old cache): use list head
            future_hours = list(data.hourly)

        city_id = f"{data.lat:.2f}_{data.lon:.2f}"
        today_str = now_dt.strftime("%Y-%m-%d")
        events: list[WeatherEvent] = []

        # 1. Precipitation onset in the next 1-2 hours
        if "precipitation" in active_types and future_hours:
            next_hours = future_hours[:2]
            for h in next_hours:
                prob = getattr(h, "precip_prob", 0) or 0
                amount = getattr(h, "precip_amount", 0.0) or 0.0
                if (prob >= 60 or amount >= 0.5) and data.current.precipitation == 0:
                    ev_id = f"{city_id}:precip:{today_str}_{h.time}"
                    if not self._is_dispatched(ev_id):
                        title = "Осадки в ближайшее время" if lang == "ru" else "Incoming Precipitation"
                        body = (
                            f"В городе {data.city_name} ожидаются осадки около {h.time}."
                            if lang == "ru"
                            else f"Precipitation expected in {data.city_name} around {h.time}."
                        )
                        events.append(WeatherEvent(
                            event_id=ev_id,
                            event_type="precipitation",
                            title=title,
                            body=body,
                            severity="normal",
                            timestamp=time.time(),
                        ))
                    break

        # 2. Frost warning (temp < 0 °C)
        if "frost" in active_types:
            if data.current.temp < 0 or (data.daily and data.daily[0].min < 0 and data.current.temp >= 0):
                ev_id = f"{city_id}:frost:{today_str}"
                if not self._is_dispatched(ev_id):
                    title = "Заморозки" if lang == "ru" else "Frost Warning"
                    body = (
                        f"Внимание: температура в {data.city_name} опустилась ниже нуля ({data.current.temp}°C)."
                        if lang == "ru"
                        else f"Warning: temperature in {data.city_name} has dropped below freezing ({data.current.temp}°C)."
                    )
                    events.append(WeatherEvent(
                        event_id=ev_id,
                        event_type="frost",
                        title=title,
                        body=body,
                        severity="normal",
                        timestamp=time.time(),
                    ))

        # 3. High wind warning (> 10 m/s)
        if "high_wind" in active_types:
            wind = data.current.wind_speed or 0.0
            gusts = data.current.wind_gusts or wind
            if wind >= 10.0 or gusts >= 15.0:
                ev_id = f"{city_id}:wind:{today_str}_{now_dt.hour // 4}"
                if not self._is_dispatched(ev_id):
                    title = "Штормовое предупреждение" if lang == "ru" else "High Wind Warning"
                    body = (
                        f"Порывы ветра в {data.city_name} достигают {gusts:.0f} м/с."
                        if lang == "ru"
                        else f"Wind gusts in {data.city_name} reaching {gusts:.0f} m/s."
                    )
                    events.append(WeatherEvent(
                        event_id=ev_id,
                        event_type="high_wind",
                        title=title,
                        body=body,
                        severity="critical" if gusts >= 20.0 else "normal",
                        timestamp=time.time(),
                    ))

        # 4. Sharp temperature surge or drop (> 5 °C within 12h)
        if ("temp_drop" in active_types or "temp_surge" in active_types) and len(future_hours) >= 12:
            t0 = future_hours[0].temp
            t12 = future_hours[11].temp
            diff = t12 - t0
            if "temp_drop" in active_types and diff <= -5:
                ev_id = f"{city_id}:temp_drop:{today_str}_{now_dt.hour // 6}"
                if not self._is_dispatched(ev_id):
                    title = "Резкое похолодание" if lang == "ru" else "Sharp Temperature Drop"
                    body = (
                        f"В {data.city_name} ожидается похолодание на {abs(round(diff))}°C за 12 часов."
                        if lang == "ru"
                        else f"Temperature in {data.city_name} expected to drop by {abs(round(diff))}°C within 12h."
                    )
                    events.append(WeatherEvent(
                        event_id=ev_id,
                        event_type="temp_drop",
                        title=title,
                        body=body,
                        severity="normal",
                        timestamp=time.time(),
                    ))
            elif "temp_surge" in active_types and diff >= 5:
                ev_id = f"{city_id}:temp_surge:{today_str}_{now_dt.hour // 6}"
                if not self._is_dispatched(ev_id):
                    title = "Резкое потепление" if lang == "ru" else "Sharp Temperature Surge"
                    body = (
                        f"В {data.city_name} ожидается потепление на {round(diff)}°C за 12 часов."
                        if lang == "ru"
                        else f"Temperature in {data.city_name} expected to surge by {round(diff)}°C within 12h."
                    )
                    events.append(WeatherEvent(
                        event_id=ev_id,
                        event_type="temp_surge",
                        title=title,
                        body=body,
                        severity="normal",
                        timestamp=time.time(),
                    ))

        # 5. High UV index (>= 6)
        if "high_uv" in active_types:
            uv = data.current.uv_index or 0.0
            if uv >= 6.0:
                ev_id = f"{city_id}:uv:{today_str}"
                if not self._is_dispatched(ev_id):
                    title = "Высокий уровень УФ" if lang == "ru" else "High UV Index"
                    body = (
                        f"УФ-индекс в {data.city_name} равен {uv:.1f}. Рекомендуется защита от солнца."
                        if lang == "ru"
                        else f"UV Index in {data.city_name} is {uv:.1f}. Sun protection advised."
                    )
                    events.append(WeatherEvent(
                        event_id=ev_id,
                        event_type="high_uv",
                        title=title,
                        body=body,
                        severity="normal",
                        timestamp=time.time(),
                    ))

        # Mark all new events as dispatched and persist
        if events:
            with self._lock:
                now_ts = time.time()
                for ev in events:
                    self._dispatched_event_ids[ev.event_id] = now_ts
                self._save_state_locked()

        return events

    def _is_dispatched(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._dispatched_event_ids

    def check_notifications(
        self,
        current_fc: WeatherForecastData,
        previous_fc: WeatherForecastData | None = None,
        config: dict[str, Any] | None = None,
        now_ts: float | None = None,
        lang: str = "ru",
    ) -> list[WeatherEvent]:
        """Convenience method calling evaluate_forecast."""
        enabled_types = None
        quiet_hours_enabled = False
        quiet_start = "22:00"
        quiet_end = "08:00"

        if config:
            notif_cfg = config.get("notifications", {})
            if not notif_cfg.get("enabled", True):
                return []
            types_dict = notif_cfg.get("types", {})
            enabled_types = [k for k, v in types_dict.items() if v]
            quiet_cfg = notif_cfg.get("quiet_hours", {})
            quiet_hours_enabled = quiet_cfg.get("enabled", False)
            quiet_start = quiet_cfg.get("start", "22:00")
            quiet_end = quiet_cfg.get("end", "08:00")

        now_dt = datetime.fromtimestamp(now_ts, timezone.utc) if now_ts else None

        return self.evaluate_forecast(
            data=current_fc,
            enabled_types=enabled_types,
            quiet_hours_enabled=quiet_hours_enabled,
            quiet_start=quiet_start,
            quiet_end=quiet_end,
            lang=lang,
            now_dt=now_dt,
        )

