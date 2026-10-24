"""Geomagnetic activity and planetary Kp-index manager for info-weather.

Fetches space weather data from NOAA Space Weather Prediction Center (SWPC):
https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json
Provides planetary Kp-index (0 to 9) and geomagnetic storm classification (G0 to G5).
Supports disk caching with TTL and non-blocking background updates.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from core.logging import get_logger

logger = get_logger("core.geomagnetic")

NOAA_KP_INDEX_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
CACHE_TTL_SECONDS = 3600.0  # 1 hour cache TTL

# Default cache directory
DEFAULT_GEOMAGNETIC_CACHE_DIR = Path.home() / ".cache" / "info-weather"
if os.name == "nt":
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        DEFAULT_GEOMAGNETIC_CACHE_DIR = Path(local_app_data) / "info-weather" / "cache"

GEOMAGNETIC_CACHE_FILE = DEFAULT_GEOMAGNETIC_CACHE_DIR / "geomagnetic.json"


@dataclass
class GeomagneticActivity:
    """Geomagnetic activity status and planetary Kp index."""

    kp_index: float = 2.0
    level: int = 2
    status_key: str = "geomagnetic_quiet"
    color: str = "#22c55e"
    noaa_scale: str = "G0"
    observed_at: str = ""
    cached_at: float = 0.0
    is_cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeomagneticActivity:
        return cls(
            kp_index=float(data.get("kp_index", 2.0)),
            level=int(data.get("level", 2)),
            status_key=str(data.get("status_key", "geomagnetic_quiet")),
            color=str(data.get("color", "#22c55e")),
            noaa_scale=str(data.get("noaa_scale", "G0")),
            observed_at=str(data.get("observed_at", "")),
            cached_at=float(data.get("cached_at", 0.0)),
            is_cached=bool(data.get("is_cached", True)),
        )


def classify_kp_index(kp: float) -> tuple[int, str, str, str]:
    """Classify Kp index into (level, status_key, color_hex, noaa_scale).

    Scale:
    - Kp < 2.5: Quiet (Спокойное), Green (#22c55e), G0
    - Kp < 3.5: Unsettled (Слабо возмущенное), Light Green (#84cc16), G0
    - Kp < 4.5: Active (Возмущенное), Yellow (#eab308), G0
    - Kp < 5.5: Minor Storm (Слабая буря G1), Orange (#f97316), G1
    - Kp < 6.5: Moderate Storm (Умеренная буря G2), Dark Orange (#ea580c), G2
    - Kp < 7.5: Strong Storm (Сильная буря G3), Red (#dc2626), G3
    - Kp < 8.5: Severe Storm (Очень сильная буря G4), Dark Red (#b91c1c), G4
    - Kp >= 8.5: Extreme Storm (Экстремальная буря G5), Purple (#7c3aed), G5
    """
    val = max(0.0, min(9.0, float(kp)))
    level = int(round(val))

    if val < 2.5:
        return level, "geomagnetic_quiet", "#22c55e", "G0"
    if val < 3.5:
        return level, "geomagnetic_unsettled", "#84cc16", "G0"
    if val < 4.5:
        return level, "geomagnetic_active", "#eab308", "G0"
    if val < 5.5:
        return level, "geomagnetic_minor_storm", "#f97316", "G1"
    if val < 6.5:
        return level, "geomagnetic_moderate_storm", "#ea580c", "G2"
    if val < 7.5:
        return level, "geomagnetic_strong_storm", "#dc2626", "G3"
    if val < 8.5:
        return level, "geomagnetic_severe_storm", "#b91c1c", "G4"
    return level, "geomagnetic_extreme_storm", "#7c3aed", "G5"


# In-memory singleton state
_cached_activity: GeomagneticActivity | None = None
_fetch_lock = threading.Lock()
_is_fetching = False


def _read_disk_cache() -> GeomagneticActivity | None:
    try:
        if GEOMAGNETIC_CACHE_FILE.is_file():
            with open(GEOMAGNETIC_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GeomagneticActivity.from_dict(data)
    except Exception as e:
        logger.debug("Failed to read geomagnetic disk cache: %s", e)
    return None


def _write_disk_cache(activity: GeomagneticActivity) -> None:
    try:
        GEOMAGNETIC_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = GEOMAGNETIC_CACHE_FILE.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(activity.to_dict(), f, indent=2)
        tmp_file.replace(GEOMAGNETIC_CACHE_FILE)
    except Exception as e:
        logger.debug("Failed to write geomagnetic disk cache: %s", e)


def fetch_geomagnetic_activity_sync(
    timeout: float = 4.0,
    http_client: Any | None = None,
) -> GeomagneticActivity:
    """Synchronously fetch planetary Kp-index from NOAA SWPC with disk caching using HttpClient."""
    global _cached_activity

    if http_client is None:
        from core.http import get_default_http_client
        http_client = get_default_http_client()

    data = http_client.fetch_json(
        NOAA_KP_INDEX_URL,
        headers={"User-Agent": "info-weather-app/1.0 (space-weather)"},
        timeout=timeout,
    )

    kp_val: float | None = None
    time_tag: str = ""
    if isinstance(data, list):
        for row in reversed(data):
            if isinstance(row, dict):
                val = row.get("Kp", row.get("kp"))
                if val is not None:
                    try:
                        kp_val = float(val)
                        time_tag = str(row.get("time_tag", ""))
                        break
                    except (ValueError, TypeError):
                        continue

    if kp_val is None:
        raise ValueError("No valid Kp index found in NOAA SWPC response")

    level, status_key, color, noaa_scale = classify_kp_index(kp_val)
    activity = GeomagneticActivity(
        kp_index=round(kp_val, 2),
        level=level,
        status_key=status_key,
        color=color,
        noaa_scale=noaa_scale,
        observed_at=time_tag,
        cached_at=time.time(),
        is_cached=False,
    )

    _cached_activity = activity
    _write_disk_cache(activity)
    logger.info("Updated geomagnetic activity: Kp=%.1f (%s, %s)", kp_val, status_key, noaa_scale)
    return activity


def _background_worker(
    on_complete: Callable[[GeomagneticActivity], None] | None = None,
    http_client: Any | None = None,
) -> None:
    global _is_fetching
    try:
        activity = fetch_geomagnetic_activity_sync(http_client=http_client)
        if on_complete:
            try:
                on_complete(activity)
            except Exception as e:
                logger.debug("Error in geomagnetic on_complete callback: %s", e)
    except Exception as e:
        logger.debug("Geomagnetic background fetch failed: %s", e)
    finally:
        with _fetch_lock:
            _is_fetching = False


def fetch_geomagnetic_activity_async(
    on_complete: Callable[[GeomagneticActivity], None] | None = None,
    http_client: Any | None = None,
) -> None:
    """Asynchronously fetch NOAA space weather data in a background daemon thread."""
    global _is_fetching
    with _fetch_lock:
        if _is_fetching:
            return
        _is_fetching = True

    thread = threading.Thread(
        target=_background_worker,
        args=(on_complete, http_client),
        daemon=True,
        name="GeomagneticFetchThread",
    )
    thread.start()


def get_geomagnetic_activity(
    force_sync: bool = False,
    on_updated: Callable[[GeomagneticActivity], None] | None = None,
    http_client: Any | None = None,
) -> GeomagneticActivity:
    """Get the current geomagnetic activity.

    Returns in-memory or disk cached data immediately.
    Triggers a background refresh if cache is older than CACHE_TTL_SECONDS.
    """
    global _cached_activity

    now = time.time()
    # 1. Check in-memory cache
    if _cached_activity is not None and (now - _cached_activity.cached_at) < CACHE_TTL_SECONDS:
        return _cached_activity

    # 2. Check disk cache
    disk_cached = _read_disk_cache()
    if disk_cached is not None:
        _cached_activity = disk_cached
        if (now - disk_cached.cached_at) < CACHE_TTL_SECONDS:
            return disk_cached
        # Stale cache: return immediately, refresh in background
        if force_sync:
            try:
                return fetch_geomagnetic_activity_sync(http_client=http_client)
            except Exception:
                return disk_cached
        fetch_geomagnetic_activity_async(on_complete=on_updated, http_client=http_client)
        return disk_cached

    # 3. No cache available
    if force_sync:
        try:
            return fetch_geomagnetic_activity_sync(http_client=http_client)
        except Exception as e:
            logger.warning("Failed to fetch initial geomagnetic activity: %s", e)
    else:
        # Trigger background fetch and return quiet default
        fetch_geomagnetic_activity_async(on_complete=on_updated, http_client=http_client)

    default_activity = GeomagneticActivity(
        kp_index=2.0,
        level=2,
        status_key="geomagnetic_quiet",
        color="#22c55e",
        noaa_scale="G0",
        observed_at="",
        cached_at=now,
        is_cached=False,
    )
    _cached_activity = default_activity
    return default_activity
