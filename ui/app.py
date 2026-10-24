"""PySide6 Application Runner for info-weather (KDE Plasma Optimized)."""

from __future__ import annotations

import sys
from pathlib import Path

from core.config import ConfigManager
from core.logging import get_logger
from providers.weather import WeatherProvider
from ui.qt_compat import QApplication, QCoreApplication, QIcon
from ui.widget_window import WeatherWidgetWindowQt

logger = get_logger("ui.app")


def run_qt_app(
    provider: WeatherProvider,
    config_manager: ConfigManager,
    is_autostart: bool = False,
) -> int:
    """Initialize and run the PySide6 application."""
    from ui.utils import ensure_kwin_rule
    wb_cfg = config_manager.get("window_behavior", {}) or {}
    # Applies the rule once if missing (install.sh already applies it for
    # user installs; package installs get it on first run).
    ensure_kwin_rule()

    if hasattr(QCoreApplication, "setApplicationName"):
        QCoreApplication.setApplicationName("info-weather")
    if hasattr(QCoreApplication, "setOrganizationName"):
        QCoreApplication.setOrganizationName("info-weather")
    if hasattr(QCoreApplication, "setDesktopFileName"):
        QCoreApplication.setDesktopFileName("info-weather")

    app = QApplication.instance()
    if app is None:
        if "-name" not in sys.argv:
            sys.argv.extend(["-name", "info-weather"])
        app = QApplication(sys.argv)

    app.setApplicationName("info-weather")
    if hasattr(app, "setDesktopFileName"):
        app.setDesktopFileName("info-weather")
    app.setOrganizationName("info-weather")
    display_mode = config_manager.get("display_mode", "both")
    app.setQuitOnLastWindowClosed(display_mode == "indicator_only")

    from core.i18n import set_language
    set_language(config_manager.get("app_language", "ru"))

    # Set Application Icon
    app_icon_path = Path(__file__).parent.parent / "assets" / "icons" / "info-weather.svg"
    if app_icon_path.is_file():
        app.setWindowIcon(QIcon(str(app_icon_path)))

    # Load QSS Stylesheet
    qss_path = Path(__file__).parent / "style.qss"
    check_icon_path = Path(__file__).parent.parent / "assets" / "icons" / "check.svg"
    if qss_path.exists():
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                stylesheet = f.read()
            stylesheet = stylesheet.replace("__CHECK_ICON__", check_icon_path.as_posix())
            app.setStyleSheet(stylesheet)
        except Exception as e:
            logger.warning("Failed to load style.qss: %s", e)

    # Instantiate widget window
    window = WeatherWidgetWindowQt(provider=provider, config_manager=config_manager)

    # Position window: restore the saved position, otherwise bottom-right.
    if not window.restore_saved_position():
        screen = app.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - window.width() - 40
            y = geo.bottom() - window.height() - 60
            window.move(max(geo.left(), x), max(geo.top(), y))

    display_mode = config_manager.get("display_mode", "both")
    if display_mode == "indicator_only":
        window.hide()
    else:
        window.show()
        always_on_top = bool(wb_cfg.get("always_on_top", False))
        if always_on_top:
            window.raise_()
            if not is_autostart:
                window.activateWindow()
        else:
            window.lower()

    return app.exec()


run_app = run_qt_app
InfoWeatherApp = WeatherWidgetWindowQt
