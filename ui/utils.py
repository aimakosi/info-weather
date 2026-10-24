"""UI utilities and icon path resolver for info-weather."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_ASSETS_DIR = Path(__file__).parent.parent / "assets" / "icons" / "weather"
_THEMES_DIR = Path(__file__).parent.parent / "assets" / "icons" / "themes"
_CURRENT_ICON_THEME: str = "svg"

WMO_TO_YAHOO: dict[int, tuple[int, int]] = {
    0: (32, 31),     # Clear: day=32, night=31
    1: (34, 33),     # Mainly clear: day=34, night=33
    2: (30, 29),     # Partly cloudy: day=30, night=29
    3: (26, 26),     # Overcast / cloudy: 26
    45: (20, 20),    # Fog: 20
    48: (20, 20),    # Rime fog: 20
    51: (9, 9),      # Light drizzle: 9
    53: (9, 9),      # Moderate drizzle: 9
    55: (9, 9),      # Dense drizzle: 9
    56: (8, 8),      # Freezing drizzle: 8
    57: (8, 8),      # Dense freezing drizzle: 8
    61: (11, 11),    # Slight rain: 11
    63: (12, 12),    # Rain: 12
    65: (40, 40),    # Heavy rain: 40
    66: (10, 10),    # Freezing rain: 10
    67: (10, 10),    # Heavy freezing rain: 10
    68: (5, 5),      # Rain and snow / Sleet: 5
    71: (14, 14),    # Slight snow: 14
    73: (16, 16),    # Moderate snow: 16
    75: (43, 43),    # Heavy snow: 43
    77: (14, 14),    # Snow grains: 14
    80: (39, 45),    # Rain showers: day=39, night=45
    81: (39, 45),    # Moderate showers: 39
    82: (40, 40),    # Violent showers: 40
    85: (41, 46),    # Snow showers: day=41, night=46
    86: (42, 46),    # Heavy snow showers: 42
    95: (4, 4),      # Thunderstorm: 4
    96: (35, 35),    # Thunderstorm with hail: 35
    99: (35, 35),    # Severe thunderstorm: 35
}

NAME_TO_YAHOO: dict[str, tuple[int, int]] = {
    # Clear / Sun
    "clear-day": (32, 31),
    "clear-night": (31, 31),
    "clear": (32, 31),
    "sun": (32, 31),
    "sunny": (32, 31),
    # Partly cloudy / Few clouds
    "partly-cloudy-day": (30, 29),
    "partly-cloudy-night": (29, 29),
    "partly-cloudy": (30, 29),
    "partlycloudy": (30, 29),
    "few-clouds": (30, 29),
    "weather-few-clouds": (30, 29),
    # Cloudy / Overcast
    "cloudy": (26, 26),
    "clouds": (26, 26),
    "cloud": (26, 26),
    "overcast": (26, 26),
    "weather-clouds": (26, 26),
    "weather-overcast": (26, 26),
    # Precipitation
    "rain": (12, 12),
    "drizzle": (9, 9),
    "shower": (12, 12),
    "showers": (12, 12),
    "weather-rain": (12, 12),
    "weather-showers": (12, 12),
    "snow": (14, 14),
    "sleet": (18, 18),
    "weather-snow": (14, 14),
    "thunderstorm": (4, 4),
    "thunder": (4, 4),
    "weather-storm": (4, 4),
    "fog": (20, 20),
    "mist": (20, 20),
    "haze": (21, 21),
    "weather-fog": (20, 20),
    "dust": (19, 19),
    "smoke": (22, 22),
    "wind": (24, 24),
    "windy": (24, 24),
    "weather-wind": (24, 24),
}


def discover_icon_themes() -> list[str]:
    """Return list of available icon themes (bundled dirs first, native 'svg' last)."""
    themes: list[str] = []
    if _THEMES_DIR.exists():
        for d in sorted(_THEMES_DIR.iterdir()):
            if d.is_dir() and ((d / "weather").exists() or any(d.glob("*.png")) or any(d.glob("*.svgz")) or any(d.glob("*.svg"))):
                themes.append(d.name)
    if "svg" not in themes:
        themes.append("svg")
    return themes


def set_current_icon_theme(theme_name: str) -> None:
    """Set the active icon theme (e.g. 'svg', 'Meteocons_monochrome', 'WeatherIcons')."""
    global _CURRENT_ICON_THEME
    _CURRENT_ICON_THEME = theme_name


def get_current_icon_theme() -> str:
    """Return the active icon theme."""
    return _CURRENT_ICON_THEME


def get_weather_icon_path(
    icon_name: str | int = "",
    is_day: int = 1,
    code: int | None = None,
    theme: str | None = None,
) -> str:
    """Resolve icon file path for meteorological condition across theme packs and SVG."""
    active_theme = theme or _CURRENT_ICON_THEME

    # 1. Check if a bundled theme provides the icon (e.g. Meteocons_monochrome, WeatherIcons)
    if active_theme and active_theme != "svg":
        theme_weather_dir = _THEMES_DIR / active_theme / "weather"
        if not theme_weather_dir.exists():
            theme_weather_dir = _THEMES_DIR / active_theme

        if theme_weather_dir.exists():
            y_code = None
            if code is not None and code in WMO_TO_YAHOO:
                y_code = WMO_TO_YAHOO[code][0 if is_day else 1]
            elif isinstance(icon_name, int) or (isinstance(icon_name, str) and icon_name.isdigit()):
                w_code = int(icon_name)
                if w_code in WMO_TO_YAHOO:
                    y_code = WMO_TO_YAHOO[w_code][0 if is_day else 1]

            if y_code is None and isinstance(icon_name, str):
                c_name = icon_name[:-4] if icon_name.endswith(".svg") else icon_name
                if c_name.startswith("weather-"):
                    c_name = c_name[len("weather-"):]

                # Service icons (sunrise, sunset, gauge, humidity, wind, …) live in
                # the bundled SVG set, not in weather icon themes.
                SERVICE_ICONS = {
                    "wind", "sunrise", "sunset", "sun", "sun-uv", "gauge", "humidity", "location-arrow",
                    "magnetic", "moon", "moon_surface", "thermometer",
                    "eye", "calendar", "chart-norm", "rain-drop",
                }
                if c_name in SERVICE_ICONS:
                    native_icon = _ASSETS_DIR / f"{c_name}.svg"
                    if native_icon.exists():
                        return str(native_icon)

                # Check if active theme provides this named icon directly
                theme_named = theme_weather_dir / f"{c_name}.svg"
                if theme_named.exists():
                    return str(theme_named)

                y_code = NAME_TO_YAHOO.get(c_name, (32, 31))[0 if is_day else 1]

            if y_code is None:
                y_code = 32 if is_day else 31

            for pattern in (
                f"{y_code:02d}.png",
                f"{y_code}.png",
                f"{y_code:02d}.svgz",
                f"{y_code}.svgz",
                f"{y_code:02d}.svg",
                f"{y_code}.svg",
            ):
                cand = theme_weather_dir / pattern
                if cand.exists():
                    return str(cand)

            for fallback_name in ("na.png", "na.svgz", "na.svg", "32.png", "32.svgz", "32.svg"):
                fb = theme_weather_dir / fallback_name
                if fb.exists():
                    return str(fb)

    # 2. Native vector SVG fallback / theme
    from data.wmo_conditions import WMO_INFO

    resolved_name = ""
    if code is not None and code in WMO_INFO:
        resolved_name = WMO_INFO[code].get("icon_day" if is_day else "icon_night", "")
    elif isinstance(icon_name, int) or (isinstance(icon_name, str) and icon_name.isdigit()):
        w_code = int(icon_name)
        if w_code in WMO_INFO:
            resolved_name = WMO_INFO[w_code].get("icon_day" if is_day else "icon_night", "")
    elif isinstance(icon_name, str) and icon_name:
        resolved_name = icon_name

    name_str = str(resolved_name).strip() if resolved_name is not None else ""

    clean_name = name_str[:-4] if name_str.endswith(".svg") else name_str
    if clean_name.startswith("weather-"):
        clean_name = clean_name[len("weather-"):]

    name_aliases = {
        "clouds": "cloudy",
        "cloud": "cloudy",
        "overcast": "cloudy",
        "partlycloudy": "partly-cloudy-day" if is_day else "partly-cloudy-night",
        "partly-cloudy": "partly-cloudy-day" if is_day else "partly-cloudy-night",
        "sun": "clear-day",
        "sunny": "clear-day",
        "clear": "clear-day" if is_day else "clear-night",
        "sleet": "snow",
        "drizzle": "rain",
        "shower": "rain",
        "showers": "rain",
        "thunder": "thunderstorm",
        "mist": "fog",
        "haze": "fog",
    }
    clean_name = name_aliases.get(clean_name, clean_name)

    filename = f"{clean_name}.svg" if clean_name else ""
    if filename:
        target = _ASSETS_DIR / filename
        if target.exists():
            return str(target)

    if code is not None and code in WMO_INFO:
        w_icon = WMO_INFO[code].get("icon_day" if is_day else "icon_night", "")
        if (_ASSETS_DIR / w_icon).exists():
            return str(_ASSETS_DIR / w_icon)

    fallback = "clear-day.svg" if is_day else "clear-night.svg"
    return str(_ASSETS_DIR / fallback)


def is_light_theme_widget(widget: Any) -> bool:
    """Return True when the widget lives inside the light-theme container."""
    parent = widget.parent() if widget is not None else None
    while parent is not None:
        try:
            if parent.objectName() == "WeatherWidgetContainer":
                return "light-theme" in str(parent.property("class") or "")
        except Exception:
            pass
        parent = parent.parent()
    return False


def render_colored_icon(
    icon_name: str,
    size: int,
    color: str,
    device_pixel_ratio: float = 2.0,
) -> Any:
    """Render a bundled monochrome SVG in a theme-appropriate color."""
    from ui.qt_compat import QColor, QPainter, QPixmap, QSvgRenderer, Qt, QtCore

    clean_name = icon_name[:-4] if icon_name.endswith(".svg") else icon_name
    if clean_name.startswith("weather-"):
        clean_name = clean_name[len("weather-"):]
    native_cand = _ASSETS_DIR / f"{clean_name}.svg"
    if native_cand.exists():
        path = str(native_cand)
    else:
        path = get_weather_icon_path(icon_name)
    canvas = max(8, int(size * device_pixel_ratio))
    pix = QPixmap(canvas, canvas)
    pix.fill(Qt.GlobalColor.transparent)

    if QSvgRenderer is None:
        source = QPixmap(path)
        if not source.isNull():
            pix = source.scaled(
                canvas,
                canvas,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return pix

    try:
        svg_text = Path(path).read_text(encoding="utf-8")
    except Exception:
        return QPixmap(path)

    qcolor = QColor(color)
    solid = qcolor.name() if qcolor.isValid() else color
    soft = (
        f"rgba({qcolor.red()},{qcolor.green()},{qcolor.blue()},0.12)"
        if qcolor.isValid()
        else color
    )
    svg_text = svg_text.replace("rgba(255,255,255,0.7)", solid)
    svg_text = svg_text.replace("rgba(255,255,255,0.08)", soft)
    svg_text = svg_text.replace('stroke="white"', f'stroke="{solid}"')
    svg_text = svg_text.replace('fill="white"', f'fill="{solid}"')
    svg_text = svg_text.replace('stroke="#f8fafc"', f'stroke="{solid}"')
    svg_text = svg_text.replace('fill="#f8fafc"', f'fill="{solid}"')

    renderer = QSvgRenderer(QtCore.QByteArray(svg_text.encode("utf-8")))
    if not renderer.isValid():
        return QPixmap(path)

    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    pix.setDevicePixelRatio(device_pixel_ratio)
    return pix


def is_weekend_day(weekday_idx: int, weekend_str: str = "Sa, Su") -> bool:
    """Check if weekday index (0=Monday..6=Sunday) matches weekend definition string."""
    if not weekend_str:
        return weekday_idx in (5, 6)
    tokens = [t.strip().lower() for t in weekend_str.replace(";", ",").split(",") if t.strip()]
    if not tokens:
        return weekday_idx in (5, 6)

    alias_map = {
        "mo": 0, "mon": 0, "пн": 0, "1": 0,
        "tu": 1, "tue": 1, "вт": 1, "2": 1,
        "we": 2, "wed": 2, "ср": 2, "3": 2,
        "th": 3, "thu": 3, "чт": 3, "4": 3,
        "fr": 4, "fri": 4, "пт": 4, "5": 4,
        "sa": 5, "sat": 5, "сб": 5, "6": 5,
        "su": 6, "sun": 6, "вс": 6, "нд": 6, "7": 6, "0": 6,
    }
    target_idx = weekday_idx % 7
    for tok in tokens:
        if tok in alias_map and alias_map[tok] == target_idx:
            return True
        for prefix, idx in [("sat", 5), ("sun", 6), ("fri", 4), ("суб", 5), ("вос", 6), ("нед", 6)]:
            if tok.startswith(prefix) and target_idx == idx:
                return True
    return False


def _kde_color_scheme_is_light() -> bool | None:
    """Read KDE's Application Style color scheme from ~/.config/kdeglobals."""
    try:
        import configparser

        path = Path.home() / ".config" / "kdeglobals"
        if not path.exists():
            return None
        parser = configparser.ConfigParser(strict=False, interpolation=None)
        parser.read(path, encoding="utf-8")
        raw = parser.get("Colors:Window", "BackgroundNormal", fallback="")
        parts = [int(p.strip()) for p in raw.split(",")[:3]]
        if len(parts) != 3:
            return None
        r, g, b = parts
        return (0.299 * r + 0.587 * g + 0.114 * b) > 128
    except Exception:
        return None


def _x11_read_cardinal(x11: Any, display: Any, window: int, atom: int) -> int | None:
    """Read a single CARDINAL X11 property."""
    import ctypes

    actual_type = ctypes.c_ulong()
    actual_format = ctypes.c_int()
    nitems = ctypes.c_ulong()
    bytes_after = ctypes.c_ulong()
    prop = ctypes.c_void_p()
    status = x11.XGetWindowProperty(
        display,
        ctypes.c_ulong(window),
        ctypes.c_ulong(atom),
        0,
        1,
        0,
        6,  # XA_CARDINAL
        ctypes.byref(actual_type),
        ctypes.byref(actual_format),
        ctypes.byref(nitems),
        ctypes.byref(bytes_after),
        ctypes.byref(prop),
    )
    if status != 0 or not prop.value or nitems.value == 0:
        return None
    try:
        return int(ctypes.cast(prop, ctypes.POINTER(ctypes.c_ulong))[0])
    finally:
        x11.XFree(prop)


def set_on_all_desktops(window_id: int, enabled: bool) -> bool:
    """Set or clear EWMH ``_NET_WM_DESKTOP`` for an X11 window.

    ``0xFFFFFFFF`` means "all desktops" in EWMH. When disabling, the window is
    moved back to the currently active desktop. Wayland does not expose this
    property to applications, so ``False`` is returned there.
    """
    import os

    if not window_id or os.environ.get("WAYLAND_DISPLAY") or not os.environ.get("DISPLAY"):
        return False

    # Make sure Qt is actually running on X11 (not offscreen / Wayland).
    try:
        from ui.qt_compat import QApplication

        app = QApplication.instance()
        if app is not None and (app.platformName() or "").lower() not in ("xcb", "x11"):
            return False
    except Exception:
        return False

    try:
        import ctypes
        import ctypes.util

        lib_name = ctypes.util.find_library("X11") or "libX11.so.6"
        x11 = ctypes.CDLL(lib_name)

        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XChangeProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
            ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
        ]
        x11.XChangeProperty.restype = ctypes.c_int
        x11.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long,
            ctypes.c_long, ctypes.c_int, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        x11.XGetWindowProperty.restype = ctypes.c_int
        x11.XFree.argtypes = [ctypes.c_void_p]
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

        display = x11.XOpenDisplay(None)
        if not display:
            return False

        try:
            atom_desktop = x11.XInternAtom(display, b"_NET_WM_DESKTOP", 0)
            atom_current = x11.XInternAtom(display, b"_NET_CURRENT_DESKTOP", 0)
            if enabled:
                value = 0xFFFFFFFF
            else:
                root = x11.XDefaultRootWindow(display)
                current = _x11_read_cardinal(x11, display, root, atom_current)
                value = current if current is not None else 0

            data = ctypes.c_ulong(value)
            status = x11.XChangeProperty(
                display,
                ctypes.c_ulong(window_id),
                ctypes.c_ulong(atom_desktop),
                ctypes.c_ulong(6),  # XA_CARDINAL
                32,
                0,  # PropModeReplace
                ctypes.cast(ctypes.byref(data), ctypes.c_void_p),
                1,
            )
            x11.XFlush(display)
            x11.XSync(display, 0)
            return bool(status)
        finally:
            x11.XCloseDisplay(display)
    except Exception:
        return False


def set_skip_taskbar(window_id: int, skip: bool) -> bool:
    """Set or clear EWMH ``_NET_WM_STATE_SKIP_TASKBAR``/``_NET_WM_STATE_SKIP_PAGER``.

    Only taskbar/pager state is touched: window type and stacking are left to
    Qt window flags and the KWin rule.  Forcing ``_NET_WM_WINDOW_TYPE_DOCK`` and
    ``_NET_WM_STATE_BELOW`` from here made KWin re-evaluate the widget as a
    panel and also removed the skip state again when it applied its rules.

    While the window is still unmapped the EWMH property is written directly
    (Qt keeps the atoms it finds when mapping); once the window is visible an
    EWMH client message is sent to the window manager.
    """
    import sys

    if not window_id or sys.platform != "linux":
        return False

    try:
        from ui.qt_compat import QApplication

        app = QApplication.instance()
        if app is not None and (app.platformName() or "").lower() not in ("xcb", "x11"):
            return False
    except Exception:
        return False

    try:
        import ctypes
        import ctypes.util

        lib_name = ctypes.util.find_library("X11") or "libX11.so.6"
        x11 = ctypes.CDLL(lib_name)

        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XChangeProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
            ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
        ]
        x11.XChangeProperty.restype = ctypes.c_int
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XGetWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]
        x11.XGetWindowAttributes.restype = ctypes.c_int

        class XWindowAttributes(ctypes.Structure):
            _fields_ = [
                ("x", ctypes.c_int),
                ("y", ctypes.c_int),
                ("width", ctypes.c_int),
                ("height", ctypes.c_int),
                ("border_width", ctypes.c_int),
                ("depth", ctypes.c_int),
                ("visual", ctypes.c_void_p),
                ("root", ctypes.c_ulong),
                ("class_", ctypes.c_int),
                ("bit_gravity", ctypes.c_int),
                ("win_gravity", ctypes.c_int),
                ("backing_store", ctypes.c_int),
                ("backing_planes", ctypes.c_ulong),
                ("backing_pixel", ctypes.c_ulong),
                ("save_under", ctypes.c_int),
                ("colormap", ctypes.c_ulong),
                ("map_installed", ctypes.c_int),
                ("map_state", ctypes.c_int),
                ("all_event_masks", ctypes.c_long),
                ("your_event_mask", ctypes.c_long),
                ("do_not_propagate_mask", ctypes.c_long),
                ("override_redirect", ctypes.c_int),
                ("screen", ctypes.c_void_p),
            ]

        display = x11.XOpenDisplay(None)
        if not display:
            return False

        try:
            atom_net_wm_state = x11.XInternAtom(display, b"_NET_WM_STATE", 0)
            atom_skip_taskbar = x11.XInternAtom(display, b"_NET_WM_STATE_SKIP_TASKBAR", 0)
            atom_skip_pager = x11.XInternAtom(display, b"_NET_WM_STATE_SKIP_PAGER", 0)

            root = x11.XDefaultRootWindow(display)

            attrs = XWindowAttributes()
            is_viewable = (
                x11.XGetWindowAttributes(display, ctypes.c_ulong(window_id), ctypes.byref(attrs)) != 0
                and attrs.map_state == 2  # IsViewable
            )

            # Before the window is mapped Qt adds its own state atoms when
            # mapping it, but preserves the atoms that are already present.
            if skip and not is_viewable:
                atoms = (ctypes.c_ulong * 2)(atom_skip_taskbar, atom_skip_pager)
                x11.XChangeProperty(
                    display,
                    ctypes.c_ulong(window_id),
                    ctypes.c_ulong(atom_net_wm_state),
                    ctypes.c_ulong(4),  # XA_ATOM
                    32,
                    0,  # PropModeReplace
                    ctypes.cast(ctypes.byref(atoms), ctypes.c_void_p),
                    2,
                )

            # EWMH client message (_NET_WM_STATE_ADD = 1, _NET_WM_STATE_REMOVE = 0)
            action = 1 if skip else 0

            class XClientMessageData(ctypes.Union):
                _fields_ = [("b", ctypes.c_char * 20), ("s", ctypes.c_short * 10), ("l", ctypes.c_long * 5)]

            class XClientMessageEvent(ctypes.Structure):
                _fields_ = [
                    ("type", ctypes.c_int),
                    ("serial", ctypes.c_ulong),
                    ("send_event", ctypes.c_int),
                    ("display", ctypes.c_void_p),
                    ("window", ctypes.c_ulong),
                    ("message_type", ctypes.c_ulong),
                    ("format", ctypes.c_int),
                    ("data", XClientMessageData),
                ]

            class XEvent(ctypes.Union):
                _fields_ = [
                    ("type", ctypes.c_int),
                    ("xclient", XClientMessageEvent),
                    ("pad", ctypes.c_long * 24),
                ]

            xev = XEvent()
            xev.xclient.type = 33  # ClientMessage
            xev.xclient.serial = 0
            xev.xclient.send_event = 1
            xev.xclient.display = display
            xev.xclient.window = window_id
            xev.xclient.message_type = atom_net_wm_state
            xev.xclient.format = 32
            xev.xclient.data.l[0] = action
            xev.xclient.data.l[1] = atom_skip_taskbar
            xev.xclient.data.l[2] = atom_skip_pager
            xev.xclient.data.l[3] = 1  # source: normal application
            xev.xclient.data.l[4] = 0

            x11.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
            x11.XSendEvent.restype = ctypes.c_int

            substructure_mask = 0x00100000 | 0x00080000  # SubstructureRedirectMask | SubstructureNotifyMask
            x11.XSendEvent(
                display,
                root,
                0,
                substructure_mask,
                ctypes.byref(xev),
            )

            x11.XFlush(display)
            x11.XSync(display, 0)
            return True
        finally:
            x11.XCloseDisplay(display)
    except Exception:
        return False


def ensure_kwin_rule() -> None:
    """Bootstrap the KDE window rule (Meta+D protection) on first run.

    install.sh applies the rule at install time; for package installs
    (.deb / AUR) the helper script ships next to the app and is run once
    when the rule is not registered yet. No-op on non-KDE sessions and
    when the helper is not shipped (e.g. pip installs).
    """
    import os
    import subprocess
    import sys

    if sys.platform != "linux":
        return
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "kde" not in desktop and not os.environ.get("KDE_FULL_SESSION"):
        return
    kwinrc = Path.home() / ".config" / "kwinrulesrc"
    if kwinrc.is_file():
        try:
            if "info-weather" in kwinrc.read_text(encoding="utf-8", errors="replace"):
                return
        except OSError:
            pass
    helper = Path(__file__).resolve().parent.parent / "packaging" / "kde" / "install_kwinrule.sh"
    if not helper.is_file():
        return
    try:
        subprocess.run(
            [str(helper)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def is_system_light_theme() -> bool:
    """Detect if the system (KDE Application Style / Qt) uses a light color scheme.

    Order: Qt style hints (KDE platform theme) -> kdeglobals -> Qt palette.
    """
    app = None
    try:
        from ui.qt_compat import QApplication, Qt
        app = QApplication.instance()
        if app:
            hints = app.styleHints()
            if hasattr(hints, "colorScheme") and hasattr(Qt, "ColorScheme"):
                scheme = hints.colorScheme()
                if scheme == Qt.ColorScheme.Light:
                    return True
                if scheme == Qt.ColorScheme.Dark:
                    return False
    except Exception:
        pass

    kde_light = _kde_color_scheme_is_light()
    if kde_light is not None:
        return kde_light

    try:
        if app:
            pal = app.palette()
            bg = pal.color(pal.ColorRole.Window)
            lum = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
            return lum > 128
    except Exception:
        pass
    return False

