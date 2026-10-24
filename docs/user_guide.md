# info-weather User Guide 🌤️

**info-weather** — a modern, lightweight and feature-rich weather widget for the Linux desktop (KDE Plasma, GNOME, XFCE and others) built on Qt / PySide6.

---

## Contents
1. [Installation and Launch](#installation-and-launch)
2. [Widget Interface and Controls](#widget-interface-and-controls)
3. [Detailed Forecast Window](#detailed-forecast-window)
   - [Screen 1: Temperature and Pressure](#screen-1-temperature-and-pressure)
   - [Screen 2: Climate Normals and Comfort](#screen-2-climate-normals-and-comfort)
   - [Screen 3: Wind Rose](#screen-3-wind-rose)
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
- **Python:** >= 3.10
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
- **Detailed forecast:** click the widget once with the LMB to open the extended forecast window.
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

The detailed forecast dialog is opened by an LMB click on the widget. The window contains three full-screen analytical sections with convenient navigation by clicking the background or using the header switcher:

### Screen 1: Temperature and Pressure
The period switcher is located at the top:
- **"24h" (Hourly forecast):**
  - A smooth temperature spline for the next 24 hours with data points, degree values, weather icons and feels-like temperature ("Feels like").
  - An hourly barometric pressure chart with a short-term trend calculation (rising / steady / falling).
- **"X days" (Multi-day forecast):**
  - The number of days is configurable in the block options (from 3 to 10 days).
  - **Two independent temperature curves:**
    - **Day temperature (max):** warm amber-orange curve (`● Day`), weather icons and values above the points.
    - **Night temperature (min):** blue curve (`● Night`) with values below the points.
    - Between the curves, a soft translucent gradient fills the daily temperature range.
  - **Multi-day barometer:** a pressure trend line over the days of the week with points, numeric labels and a trend indicator.
  - **Interactive scrubber:** hovering the mouse over the chart shows a tooltip with detailed data for the selected day/hour.

### Screen 2: Climate Normals and Comfort
- Comparison of the actual temperature and precipitation with the long-term climate normals of the global **Copernicus ERA5** reanalysis (1991–2020) for the coordinates of the selected city.
- Indicators of deviation from the norm and seasonal anomalies.

### Screen 3: Wind Rose
- A functional **16-point wind rose** with radial speed accumulation (stacked radial wedges).
- Time-slice switch tabs: **"24h"** and **"X days"**.
- Wind speed gradation on the international Beaufort scale:
  - 0–2 m/s — blue (calm)
  - 2–4 m/s — turquoise (light)
  - 4–6 m/s — emerald (gentle)
  - 6–8 m/s — yellow (moderate)
  - 8–11 m/s — orange (fresh)
  - > 11 m/s — red (strong/gale)
- Concentric percentage rings of time distribution, an arrow for the prevailing and current wind direction, peak gusts.

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
- **Network parameters:** HTTP request timeout, DNS timeout, retry count, IPv4 preference over IPv6.

### "Notifications" Tab
- Alerts about rain/snow starting within the next hour.
- Alerts about frost (t < 0 °C) and strong wind (> 10 m/s).
- "Quiet hours" mode (e.g. no sounds or popups from 23:00 to 08:00).

---

## Keyboard and Mouse Shortcuts

| Action | Control |
|---|---|
| Move the widget | Hold LMB and drag |
| Detailed forecast | LMB click on the widget |
| Flip forecast screens | LMB click on the empty background of the forecast dialog |
| Switch forecast period (24h / X days) | Click the "24h" / "X days" buttons on Screens 1 and 3 |
| Interactive chart inspection | Hover the mouse over the temperature spline |
| Switch locations (cities) | Scroll the mouse wheel over the widget |
| Context menu | RMB click on the widget |
| Close dialogs | `Esc` key |

---

## Offline Mode

When there is no internet connection, the widget automatically switches to a resilient mode:
1. **Level S1 (Cache):** the last successfully fetched data is displayed with a "(cache)" marker and the time of the last update.
2. **Level S0 (ERA5 Climatology):** if there is no cache (e.g. a first launch on a new system without internet), the built-in array of daily climate normals from **Copernicus ERA5** (1991–2020) is activated. The widget honestly shows the climate normal for the city coordinates without crashes or empty screens.
