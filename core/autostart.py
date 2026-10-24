"""
Autostart Manager for info-weather (FR-12).

Manages XDG desktop entry in ~/.config/autostart/info-weather.desktop.
Supports:
- Enable / disable autostart
- Configurable delay before launch
- Safe start without focus grabbing (--autostart flag)
"""

from __future__ import annotations

import os
from pathlib import Path

from core.logging import get_logger

logger = get_logger("core.autostart")


def get_autostart_dir() -> Path:
    """Return standard XDG autostart directory."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        base = Path(xdg_config)
    else:
        base = Path.home() / ".config"
    return base / "autostart"


def get_autostart_file_path() -> Path:
    """Return path to info-weather.desktop inside autostart."""
    return get_autostart_dir() / "info-weather.desktop"


def is_autostart_enabled(filepath: Path | None = None) -> bool:
    """Check if autostart desktop entry exists and is active."""
    target = filepath or get_autostart_file_path()
    if not target.is_file():
        return False

    try:
        content = target.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("Hidden=true") or line.startswith("X-GNOME-Autostart-enabled=false"):
                return False
        return True
    except Exception as e:
        logger.warning("Could not read autostart file %s: %s", target, e)
        return False


def enable_autostart(
    delay_sec: int = 0,
    custom_exec: str | None = None,
    filepath: Path | None = None,
) -> bool:
    """
    Generate and save XDG autostart desktop entry.
    """
    target = filepath or get_autostart_file_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)

        if custom_exec:
            exec_line = custom_exec
        else:
            # Standard binary or python entry
            bin_name = "info-weather"
            if delay_sec > 0:
                exec_line = f"{bin_name} --autostart --delay {delay_sec}"
            else:
                exec_line = f"{bin_name} --autostart"

        entry_content = f"""[Desktop Entry]
Type=Application
Name=Info Weather Widget
Comment=Desktop weather widget with deterministic consensus
Exec={exec_line}
Icon=info-weather
Terminal=false
Categories=Utility;Clock;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
        target.write_text(entry_content, encoding="utf-8")
        logger.info("Enabled autostart at %s (delay=%ds)", target, delay_sec)
        return True
    except Exception as e:
        logger.error("Failed to enable autostart at %s: %s", target, e)
        return False


def disable_autostart(filepath: Path | None = None) -> bool:
    """
    Remove autostart desktop entry.
    """
    target = filepath or get_autostart_file_path()
    try:
        if target.is_file():
            target.unlink()
            logger.info("Disabled autostart (removed %s)", target)
        return True
    except Exception as e:
        logger.error("Failed to disable autostart at %s: %s", target, e)
        return False
