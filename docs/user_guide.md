# info-weather User Guide 🌤️

**info-weather** — a modern, lightweight and feature-rich weather widget for the Linux desktop (KDE Plasma, GNOME, XFCE and others) built on Qt / PySide6.

---

## Contents
1. [Installation and Launch](#installation-and-launch)
2. [Widget Interface and Controls](#widget-interface-and-controls)
3. [Detailed Forecast Window](#detailed-forecast-window)
   - [Screen 1: Temperature & Precipitation](#screen-1-temperature--precipitation)
   - [Screen 2: Barometric Pressure](#screen-2-barometric-pressure)
   - [Screen 3: Geomagnetic Activity (Kp-index)](#screen-3-geomagnetic-activity-kp-index)
   - [Screen 4: Climate Normals (Copernicus ERA5 1991–2020)](#screen-4-climate-normals-copernicus-era5-19912020)
   - [Screen 5: 16-Ray Stacked Wind Rose](#screen-5-16-ray-stacked-wind-rose)
4. [Managing Locations (Cities)](#managing-locations-cities)
5. [Application Settings](#application-settings)
   - [General](#general-tab)
   - [View and Appearance](#view-and-appearance-tab)
   - [Layout](#layout-tab)
   - [Providers](#providers-tab)
   - [Notifications](#notifications-tab)
6. [Keyboard and Mouse Shortcuts](#keyboard-and-mouse-shortcuts)
7. [Offline Mode](#offline-mode)

---

## Installation and Launch

### System Requirements
- **OS:** Linux (KDE Plasma 5/6, GNOME, XFCE and others)
- **Python:** >= 3.11
- **Libraries:** PySide6 >= 6.5 (`pip install PySide6`, or on Debian/Ubuntu: `python3-pyside6.qtwidgets python3-pyside6.qtsvg`)

### Quick Install
```bash
git clone https://github.com/aimakosi/info-weather.git
cd info-weather
./packaging/scripts/install.sh
```

### Launch
```bash
# Standard widget launch:
python3 main.py

# Or via the installed command:
info-weather
```

---

## Widget Interface and Controls

The widget is displayed directly on the desktop as a neat frameless translucent window.

### Basic Mouse Actions
- **Move (Drag & Drop):** press and hold the left mouse button (LMB) on an empty area of the widget and drag it to the desired position. Coordinates are saved to the configuration automatically.
- **Contextual Detailed Forecast:** click on any meteorological block on the widget to open the extended forecast dialog directly to the relevant analytical screen:
  - 🧭 **Wind Block** (or wind row in additional info) → opens **Screen 5: Wind Rose**.
  - ⏱️ **Additional Info Block** (pressure, humidity) → opens **Screen 2: Barometric Pressure**.
  - 📅 **Daily Forecast Strip** or **Tomorrow Outlook** → opens **Screen 1: Temperature & Precipitation** in multi-day daily view.
  - 🌤️ **Header / Current Weather** or **Today Outlook** → opens **Screen 1: Temperature & Precipitation** in 24-hour hourly view.
  - ☀️ **Astronomy Strip** → opens **Screen 4: Climate Normals (Copernicus ERA5) & Solar Cycles**.
  - 🖱️ **Background / Empty Space** → opens Screen 1 by default.
  - Moving the mouse (> 6 px) engages window repositioning (drag-and-drop) without triggering clicks.
- **Switch saved cities:** scroll the mouse wheel up or down over the widget to quickly flip through locations. A debounce timer (400 ms) protects against accidental rapid triggers.
- **Context menu (RMB):**
  - **Detailed forecast…** — opens the analysis window.
  - **Refresh now** — forces a parallel network data fetch.
  - **Cities…** — dialog for adding, removing and selecting cities.
  - **Theme ▸** — quick switch of the appearance mode:
    - *By Sun (Auto Solar)* — automatic day/night switching based on the sun position calculated for the current location.
    - *Day (Light)* — light appearance theme.
    - *Night (Dark)* — dark high-contrast appearance theme.
  - **Settings…** — the application options dialog.
  - **Quit** — cleanly exits the program, saving the state.

---

## Detailed Forecast Window

The detailed forecast dialog is opened by an LMB click on the widget (or via context menu). The window features **Variant 3: "Glanceable Analytics Rail & Contextual Smart Horizon"** with a right-hand vertical rail displaying real-time live metrics and instant switching between 5 full-screen analytical sections:

### Navigation & Controls
- **Right Glanceable Rail:** 5 interactive tabs with live metric summaries visible without clicking:
  - 🌡️ **Temperature:** current temperature and daily range (`+18°C (+12°..+21°)`).
  - ⏱️ **Pressure:** current barometric pressure and trend arrow (`754 mmHg ↗`).
  - ⚡ **Geomagnetic:** NOAA peak Kp-index and storm classification (`Kp 2.0 (Quiet)`).
  - 🌍 **ERA5 Norms:** deviation from the 30-year climatological normal (`+2.1°C to normal`).
  - 🧭 **Wind Rose:** wind speed and cardinal direction (`4.2 m/s (SW)`).
- **Keyboard Shortcuts:** keys **1–5** or **F1–F5** jump directly to screens 1–5; **Up / Down** or **PageUp / PageDown** cycle screens; **Esc** closes the dialog.
- **Header Controls:** city title, weather summary, screen badge (`1/5 • Temperature`), `▲` / `▼` navigation buttons, and close button `✕`.
- **Theme Synchronization:** seamless automatic styling for Day (light) and Night (dark) themes with synchronized chart gradients and contrast.

### Screen 1: Temperature & Precipitation
- **"24h" (Hourly forecast):** smooth Bézier temperature spline for 24 hours with weather condition icons, degree values, wind vectors and precipitation probabilities.
- **"X days" (Multi-day forecast):** dual spline curves — **Day max.** (warm amber-orange, `● Day`) and **Night min.** (cyan-blue, `● Night`) with translucent temperature band fill and interactive scrubber.

### Screen 2: Barometric Pressure
- Barometric trend curve with normal pressure baseline reference (760 mmHg / 1013.25 hPa).
- Status pill indicating current pressure, numerical delta and tendency (`Rising ↗`, `Steady →`, `Falling ↘`).

### Screen 3: Geomagnetic Activity (Kp-index)
- NOAA SWPC planetary Kp-index forecast in 3-hour bins (24h) or daily maxima (X days).
- Standard color scale: green (Kp 0–2, Quiet), yellow (Kp 3–4, Unsettled), and red (Kp ≥ 5, Storm G1–G5) with peak Kp indicator.

### Screen 4: Climate Normals (Copernicus ERA5 1991–2020)
- Comparison of actual observation against 30-year ERA5 climatological baseline.
- Summary cards: Current Average, 30-Year Normal, Anomaly assessment, and 12-month annual profile.

### Screen 5: 16-Ray Stacked Wind Rose
- Full 16-point polar wind rose with radial speed accumulation on the international Beaufort scale.
- Time-slice selectors, percentage distribution rings, prevailing and current wind direction, and peak gust indicators.

---

## Managing Locations (Cities)

The **"Cities"** dialog (available via RMB → "Cities…" or in Settings):
- **Add a new city:** enter the city name in Russian, Ukrainian or English. The built-in Open-Meteo geocoder suggests options with country, region and coordinates.
- **Localization:** city names are automatically localized according to the selected interface language.
- **Home city:** the house button assigns a city as the startup default.
- **Ordering:** up/down arrows adjust the order used by mouse-wheel scrolling.
- **Removal:** the delete button removes a location from the favorites list.

---

## Application Settings

The settings window is organized into logical tabs and positions itself next to the widget when opened, without covering it.

### "General" Tab
- **Interface language:** Russian (`ru`), Ukrainian (`uk`), English (`en`).
- **Autostart:** enable/disable automatic launch at login (supports XDG Autostart with a delay in seconds).
- **Refresh interval:** the period of automatic weather-service polling (60 minutes by default).
- **Switch cities with the mouse wheel:** enable/disable location switching by scrolling and configure the debounce interval.

### "View and Appearance" Tab
- **Appearance theme:** "By Sun (Auto Solar)", "Day (Light)", "Night (Dark)".
- **Icon set:**
  - **svg** — the project's own colored set (default).
  - **Meteocons** (Monochrome) — modern outline weather pictograms (Bas Milius, MIT).
  - **Weather Icons** — a classic outline set (Erik Flowers, SIL OFL 1.1).
- **Widget scale:** from 80% to 150% for monitors of different resolutions (HiDPI / 4K).
- **Background opacity:** smooth adjustment of the widget backdrop opacity (0–100%).
- **Color accents:** the weekend color in the calendar and the wind-rose arrow color.
- **Live weather effects:** animated rain, falling snow, fog, sun glints and twinkling stars with CPU optimization (< 1%).
- **Landmark backgrounds:** a backdrop with silhouettes or photorealistic city views with automatic dimming at night.

### "Layout" Tab
- Enable, disable and reorder the informational blocks of the widget:
  - *Header ("Now")*: temperature, feels-like temperature, weather code, icon, city.
  - *Today / Tomorrow forecast*: a brief summary by day periods (morning, afternoon, evening, night).
  - *Multi-day forecast*: choose the number of displayed days (3 to 10).
  - *Compact wind rose*: a mini-compass of the current wind direction and speed.
  - *Astronomy*: sunrise, sunset, daylight duration, moon phase.
  - *Additional metrics*: humidity, pressure (mmHg or hPa), dew point, UV index, visibility.

### "Providers" Tab
- **Data sources:** Open-Meteo, MET Norway (yr.no), wttr.in.
- **Consensus mode:** automatic synthesis of an agreed forecast (temperature median, majority voting for phenomena).
- **Network parameters:** HTTP request timeout, retry count, overall update timeout. DNS timeout and IPv4 preference are hidden behind the "Advanced" toggle.

### "Notifications" Tab
- Alerts about rain/snow starting within the next hour.
- Alerts about frost (t < 0 °C) and strong wind (> 10 m/s).
- "Quiet hours" mode (e.g. no sounds or popups from 23:00 to 08:00).

---

## Keyboard and Mouse Shortcuts

| Action | Control |
|---|---|
| Move the widget | Hold LMB and drag |
| Detailed forecast | LMB click on a weather block (opens the matching section) or RMB → "Detailed forecast…" |
| Jump to forecast section | Click a tab on the right glanceable rail, press `1`–`5` or `F1`–`F5` |
| Cycle forecast sections | `Up` / `Down` or `PageUp` / `PageDown` |
| Switch forecast period (24h / X days) | Click the "24h" / "X days" buttons on Screens 1–3 |
| Interactive chart inspection | Hover the mouse over the temperature spline |
| Switch locations (cities) | Scroll the mouse wheel over the widget |
| Context menu | RMB click on the widget |
| Close dialogs | `Esc` key |

---

## Offline Mode

When there is no internet connection, the widget automatically switches to a resilient mode:
1. **Level S1 (Cache):** the last successfully fetched data is displayed with a "(cache)" marker and the time of the last update.
2. **Level S0 (ERA5 Climatology):** if there is no cache (e.g. a first launch on a new system without internet), the built-in array of daily climate normals from **Copernicus ERA5** (1991–2020) is activated. The widget honestly shows the climate normal for the city coordinates without crashes or empty screens.
