"""Thread-safe, atomic disk-backed caching layer for info-weather.

Supports:
- Caching consensus forecasts
- Caching per-provider responses with fetched_at timestamps for replay mode
- Geocoding lookup cache
- Atomic persistence via temporary files + os.replace
- Automatic pruning of stale forecasts
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger("cache")

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "info-weather"
DEFAULT_CACHE_FILE = "cache.json"


class CacheManager:
    """Manager for forecasts, per-source responses, and geocoding cache."""

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        cache_filename: str = DEFAULT_CACHE_FILE,
        max_forecast_age_seconds: float = 86400 * 2,  # 2 days
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_file = self.cache_dir / cache_filename
        self.max_forecast_age = max_forecast_age_seconds
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {
            "forecasts": {},
            "source_responses": {},
            "geocache": {},
        }
        self._load_cache()

    def _coord_key(self, lat: float, lon: float) -> str:
        return f"{lat:.4f},{lon:.4f}"

    def _source_key(self, source: str, lat: float, lon: float) -> str:
        return f"{source}:{lat:.4f},{lon:.4f}"

    def _load_cache(self) -> None:
        with self._lock:
            if not self.cache_file.exists():
                return
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._cache["forecasts"] = data.get("forecasts", {})
                        self._cache["source_responses"] = data.get("source_responses", {})
                        self._cache["geocache"] = data.get("geocache", {})
                self._prune_stale_locked()
            except Exception as e:
                logger.warning("Failed to load cache from %s: %s", self.cache_file, e)

    def _prune_stale_locked(self) -> None:
        """Remove forecasts and responses that exceed maximum retention period."""
        now = time.time()
        stale_forecasts = [
            k for k, v in self._cache["forecasts"].items()
            if isinstance(v, dict) and (now - v.get("cached_at", 0) > self.max_forecast_age)
        ]
        for k in stale_forecasts:
            del self._cache["forecasts"][k]

        stale_sources = [
            k for k, v in self._cache["source_responses"].items()
            if isinstance(v, dict) and (now - v.get("fetched_at", 0) > self.max_forecast_age)
        ]
        for k in stale_sources:
            del self._cache["source_responses"][k]

    def _save_cache_locked(self) -> None:
        """Atomically persist cache dictionary using tempfile and os.replace."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=self.cache_dir, prefix="info_weather_cache_", suffix=".tmp")
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False)
            os.replace(tmp_path, self.cache_file)
        except Exception as e:
            logger.warning("Failed to atomically save cache to %s: %s", self.cache_file, e)

    def persist(self) -> None:
        """Write the current in-memory cache to disk."""
        with self._lock:
            self._save_cache_locked()

    # ------------------------------------------------------------------------
    # Consensus Forecasts
    # ------------------------------------------------------------------------

    def get_forecast(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Retrieve cached consensus forecast dictionary if available."""
        key = self._coord_key(lat, lon)
        with self._lock:
            val = self._cache["forecasts"].get(key)
            if isinstance(val, dict):
                return dict(val)
        return None

    def set_forecast(self, lat: float, lon: float, data: Any) -> None:
        """Save consensus forecast dictionary or dataclass model."""
        payload = data.to_dict() if hasattr(data, "to_dict") else dict(data)
        if not isinstance(payload, dict):
            return
        if "cached_at" not in payload or not payload["cached_at"]:
            payload["cached_at"] = time.time()
        key = self._coord_key(lat, lon)
        with self._lock:
            self._cache["forecasts"][key] = payload
            self._save_cache_locked()

    def invalidate_forecast(self, lat: float, lon: float) -> None:
        """Remove cached forecast for given coordinates."""
        key = self._coord_key(lat, lon)
        with self._lock:
            if key in self._cache["forecasts"]:
                del self._cache["forecasts"][key]
                self._save_cache_locked()

    # ------------------------------------------------------------------------
    # Per-Source Responses (Replay Mode Support)
    # ------------------------------------------------------------------------

    def save_source_response(
        self,
        source: str,
        lat: float,
        lon: float,
        data: dict[str, Any],
        fetched_at: float | None = None,
        persist: bool = True,
    ) -> None:
        """Save normalized or raw per-source response with fetched_at timestamp.

        Set persist=False to skip the disk write when several responses are
        saved in a row (the caller persists once at the end).
        """
        key = self._source_key(source, lat, lon)
        entry = {
            "source": source,
            "fetched_at": fetched_at or time.time(),
            "data": data,
        }
        with self._lock:
            self._cache["source_responses"][key] = entry
            if persist:
                self._save_cache_locked()

    def get_source_response(
        self,
        source: str,
        lat: float,
        lon: float,
    ) -> dict[str, Any] | None:
        """Get cached response for specific provider source."""
        key = self._source_key(source, lat, lon)
        with self._lock:
            entry = self._cache["source_responses"].get(key)
            if isinstance(entry, dict):
                return dict(entry)
        return None

    def get_replay_sources(self, lat: float, lon: float) -> dict[str, dict[str, Any]]:
        """
        Get all available cached source responses for coordinates.
        Enables replay-mode: re-synthesizing consensus from historical provider answers.
        """
        suffix = f":{lat:.4f},{lon:.4f}"
        results: dict[str, dict[str, Any]] = {}
        with self._lock:
            for k, v in self._cache["source_responses"].items():
                if k.endswith(suffix) and isinstance(v, dict):
                    source = v.get("source", k.split(":")[0])
                    results[source] = v
        return results

    # ------------------------------------------------------------------------
    # Geocoding Cache
    # ------------------------------------------------------------------------

    def get_geocache(self, query: str) -> list[dict[str, Any]] | dict[str, Any] | None:
        """Retrieve cached geocoding result."""
        clean_key = str(query).lower().strip()
        with self._lock:
            val = self._cache["geocache"].get(clean_key)
            if val is not None:
                return val
        return None

    def set_geocache(self, query: str, result: Any) -> None:
        """Save geocoding result for query."""
        clean_key = str(query).lower().strip()
        with self._lock:
            self._cache["geocache"][clean_key] = result
            self._save_cache_locked()

    def clear_all(self) -> None:
        """Clear all in-memory and on-disk cache entries."""
        with self._lock:
            self._cache = {
                "forecasts": {},
                "source_responses": {},
                "geocache": {},
            }
            self._save_cache_locked()
