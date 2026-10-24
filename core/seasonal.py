"""
Seasonal Daytime Themes Manager for info-weather.

Provides automatic calendar-based season detection (or explicit manual selection),
and locates the corresponding high-resolution transparent PNG themes ("hanging on desktop" card).
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Literal

SeasonName = Literal["winter", "spring", "summer", "autumn"]

_SEASON_BY_MONTH: dict[int, SeasonName] = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}

def get_current_season() -> SeasonName:
    """Determine current season based on calendar month."""
    month = datetime.datetime.now().month
    return _SEASON_BY_MONTH.get(month, "spring")

def get_seasonal_theme_dir() -> Path:
    """Resolve directory containing seasonal theme images."""
    return Path(__file__).resolve().parent.parent / "assets" / "themes" / "seasonal"

def resolve_seasonal_theme_image(mode: str = "auto") -> Path | None:
    """
    Resolve transparent PNG image path for given seasonal mode.
    Modes:
      - 'auto': chooses current season by month (Dec-Feb: winter, Mar-May: spring, Jun-Aug: summer, Sep-Nov: autumn)
      - 'winter', 'spring', 'summer', 'autumn': explicit season
    """
    if mode == "auto":
        season = get_current_season()
    elif mode in ("winter", "spring", "summer", "autumn"):
        season = mode
    else:
        season = get_current_season()

    theme_dir = get_seasonal_theme_dir()
    img_path = theme_dir / f"{season}.png"
    if img_path.is_file():
        return img_path
    return None
