# info-weather 🌤️

> **info-weather** — a modern desktop weather widget for Linux (Qt / PySide6, KDE Plasma), built as a complete, reliable and fast replacement for the outdated `gis-weather`.

[![CI](https://github.com/aimakosi/info-weather/actions/workflows/ci.yml/badge.svg)](https://github.com/aimakosi/info-weather/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## ✨ Key Features

1. **Deterministic provider consensus (S3 → S2 → S1 → S0)**
   - Parallel polling of three independent data sources: **Open-Meteo**, **MET Norway (yr.no)** and **wttr.in**.
   - Synthesis by strict meteorological rules: medians for continuous values (temperature, pressure, humidity), majority voting for weather phenomena (WMO codes), priority for precipitation.
   - Race protection and stale-response rejection (`request_id`).

2. **Honest offline mode based on ERA5 climatology (Level S0)**
   - Bundled daily and monthly climate normals based on the global **Copernicus ERA5** reanalysis (1991–2020 baseline, 0.25° grid).
   - With no network or cache, the widget honestly warns the user and shows the climate normal for the given coordinates instead of fake data.

3. **Native KDE Plasma desktop pinning (KWin)**
   - Frameless floating desktop widget.
   - A dedicated KWin rule (`packaging/kde/info-weather.kwinrule`) keeps the widget from being minimized by **Meta+D** ("Show Desktop").

4. **Detailed analytical forecast (3 full-screen sections)**
   - A deep weather analysis window with click-switchable sections:
     1. **Temperature & Pressure**:
        - **24h** tab: hourly temperature spline with feels-like temperature, precipitation and a 24-hour barometer.
        - **X days** tab: two independent spline curves — **Day max.** (amber-orange) and **Night min.** (blue) with weather icons, `● Day` / `● Night` legend, an interactive scrubber and a daily pressure chart.
     2. **Climate Normals & Comfort**: comparison with the monthly ERA5 climate normals and temperature anomaly assessment.
     3. **Wind Rose**: an interactive 16-point wind rose with radial speed accumulation (24h / X days), Beaufort scale, prevailing direction and current gusts.

5. **Themes, icon sets and live effects**
   - Theme modes: **By Sun (auto_solar)** with automatic day/night calculation using NOAA formulas, **Day (Light)** and **Night (Dark)**.
   - Full icon sets: the project's own colored **svg** set (default), **Meteocons** (Monochrome), **Weather Icons**.
   - Customizable appearance: scale (0.8x–1.5x), background opacity, weekend color and compass-arrow color.
   - Atmospheric micro-animations (Live Weather Effects: rain, snow, fog, sun glints, twinkling stars) with power-saving modes (< 1% CPU).
   - Landmark backgrounds with photorealistic silhouettes and automatic night dimming.

6. **Smart interface and dialogs**
   - A settings window with the "General" tab first for quick access to language and parameters.
   - Intelligent positioning: settings, forecast and city dialogs open next to the widget without covering it.
   - City management with automatic geocoding and name localization when switching languages (RU, UK, EN).

7. **Local weather notifications (FR-11)**
   - Detection of significant events: rain starting within the next hour, frost (t < 0 °C), storm wind (> 10 m/s), temperature swings, high UV.
   - Event deduplication by stable IDs across restarts.
   - Configurable "quiet hours" (e.g. 23:00–08:00).

---

## 📚 Documentation

*(Available in Russian)*

- [📖 **User Guide**](docs/user_guide.md) — detailed description of the interface, charts, wind rose, city management and settings.
- [📐 **Project Architecture**](docs/architecture.md) — overview of the core, provider consensus, ERA5 climatology, Bézier splines and vector rendering.
- [⚙️ **Configuration Reference**](docs/configuration.md) — full description of the `config.json` structure and parameters.

---

## 🚀 Installation

### Requirements
- Python >= 3.10
- PySide6 >= 6.5 (`pip install PySide6`, or on Debian/Ubuntu: `python3-pyside6.qtwidgets python3-pyside6.qtsvg`)

### From packages (Debian / Ubuntu)
Download the latest `.deb` from [GitHub Releases](https://github.com/aimakosi/info-weather/releases) and install:

```bash
sudo apt install ./info-weather_0.1.0-1_all.deb
```

### Quick start (install script, any distro)
```bash
sudo apt update
sudo apt install python3 python3-pip python3-pyside6.qtwidgets python3-pyside6.qtsvg

# Clone and install
git clone https://github.com/aimakosi/info-weather.git
cd info-weather

# Run the installer (optionally with --with-autostart)
./packaging/scripts/install.sh
```

### Arch Linux
The release ships an AUR-ready source tarball and `PKGBUILD` (`packaging/arch/`):

```bash
cd packaging/arch
makepkg -si
```

### Running from source
```bash
python3 main.py
```

### Uninstall
```bash
# Remove the app, keep your settings:
./packaging/scripts/uninstall.sh

# Full purge of configuration and cache:
./packaging/scripts/uninstall.sh --purge
```

---

## 🖥️ Command Line Usage (CLI)

`info-weather` can run fully headless (e.g. on servers or over SSH):

```bash
# Print a detailed weather report for the current city:
info-weather --headless

# Weather for a specific city or coordinates:
info-weather --city "Novosibirsk" --headless
info-weather --city "55.75,37.61" --headless

# Search cities via geocoder and the local catalog:
info-weather --search "Sochi"

# Replay consensus from cached responses (offline):
info-weather --replay

# Launch in autostart mode (without stealing focus):
info-weather --autostart --delay 3

# Force the X11 (xcb) backend instead of native Wayland:
info-weather --xcb

# Reset settings to factory defaults:
info-weather --reset-config
```

---

## 🌐 Network Settings

Available in **Settings → Providers → Network** and applied immediately. Stored in `~/.config/info-weather/config.json` under the `network` section:

```json
{
  "network": {
    "timeout_seconds": 8.0,
    "dns_timeout_seconds": 5.0,
    "retries": 1,
    "prefer_ipv4": true,
    "fetch_timeout_seconds": 30.0
  }
}
```

- `timeout_seconds` — timeout of a single HTTP request.
- `dns_timeout_seconds` — DNS resolution limit (protection against a "stuck" DNS).
- `retries` — number of request retries on error.
- `prefer_ipv4` — try IPv4 before IPv6 (helps with broken IPv6).
- `fetch_timeout_seconds` — overall limit of one refresh cycle: once expired, already fetched sources are used.

---

## ⚙️ Widget Controls

- **Move**: press and hold the left mouse button and drag the widget to a convenient spot. The position is remembered and restored on the next launch.
- **Window behavior** ("View" tab): position lock, show on all desktops (X11), "always on top" mode and taskbar visibility. The widget is hidden from the taskbar by default.
- **Switch cities**: scroll the mouse wheel over the widget (with a configurable debounce timer).
- **Detailed forecast**: left-click the widget or use the context menu item (opens the window with 3 analytical sections).
- **Context menu (right-click)**:
  - *Detailed forecast…* — opens the extended forecast (temperature/pressure, climatology, wind rose).
  - *Refresh now* — forces a network poll.
  - *Cities…* — add, remove, sort cities and pin the home city.
  - *Theme* — switch appearance modes (By Sun / Day / Night).
  - *Settings…* — options window (general, view & appearance, block layout, units, notifications, autostart).
  - *Quit* — cleanly exits the application, saving the position.

---

## 🧪 Testing

The project ships a comprehensive automated test suite for the core (consensus, geocoding, astronomy, unit conversion, API failure resilience, config validation, icon resolution):

```bash
pip install .[dev]
ruff check .                                     # linter (CI gate)
QT_QPA_PLATFORM=offscreen python -m pytest -q    # tests (CI gate)
```

---

## 📄 License & Attribution

The project is distributed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**.
The full license text and official attributions of the data providers (Copernicus Climate Change Service / ERA5 Climatology, Open-Meteo, MET Norway, wttr.in, NASA Moon Kit) are available in [NOTICE](NOTICE).
