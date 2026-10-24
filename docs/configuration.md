# config.json Configuration Reference ⚙️

The application configuration file is stored at:
- **Linux:** `~/.config/info-weather/config.json`
- **Windows:** `%LOCALAPPDATA%\info-weather\config.json`

The file is created automatically on the first launch with default values. When settings are changed through the GUI, the file is rewritten atomically.

---

## Full Configuration Example

```json
{
  "schema_version": 1,
  "app_language": "ru",
  "weather_language": "ru",
  "display_mode": "both",
  "data_source": "consensus",
  "open_meteo_model": "best_match",
  "update_interval_minutes": 60,
  "max_consensus_age_minutes": 120,
  "home_city": "Abakan",
  "current_city": "Abakan",
  "cities": [
    {
      "name": "Abakan",
      "lat": 53.7167,
      "lon": 91.4292,
      "country": "RU"
    },
    {
      "name": "Saint Petersburg",
      "lat": 59.9386,
      "lon": 30.3141,
      "country": "RU"
    }
  ],
  "skin": {
    "name": "default_dark",
    "icons_name": "svg",
    "theme_mode": "auto_solar",
    "opacity": 0.92,
    "scale": 1.0,
    "weekend_color": "#ef4444",
    "wind_arrow_color": "#38bdf8"
  },
  "view_blocks": {
    "now": { "enabled": true, "offset_x": 0, "offset_y": 0 },
    "wind": { "enabled": true, "offset_x": 0, "offset_y": 0 },
    "today": { "enabled": true, "offset_x": 0, "offset_y": 0 },
    "hourly": { "enabled": false, "hours": 24 },
    "daily": { "enabled": true, "days": 6, "offset_x": 0, "offset_y": 0 },
    "day_periods": { "enabled": true, "offset_x": 0, "offset_y": 0 },
    "astronomy": { "enabled": true, "offset_x": 0, "offset_y": 0 },
    "metrics": { "enabled": true, "offset_x": 0, "offset_y": 0 },
    "additional_info": { "enabled": true, "offset_x": 0, "offset_y": 0 }
  },
  "landmark": {
    "enabled": false,
    "image_path": "",
    "dimming_night": 0.55
  },
  "units": {
    "temp": "C",
    "wind": "m/s",
    "pressure": "mmHg",
    "distance": "km"
  },
  "network": {
    "timeout_seconds": 8.0,
    "dns_timeout_seconds": 5.0,
    "retries": 1,
    "prefer_ipv4": true,
    "fetch_timeout_seconds": 30.0
  },
  "notifications": {
    "enabled": true,
    "quiet_hours_enabled": false,
    "quiet_hours_start": "23:00",
    "quiet_hours_end": "08:00",
    "types": {
      "rain_snow_1h": true,
      "frost": true,
      "wind_storm": true,
      "temp_drop": true,
      "high_uv": true
    }
  },
  "animation_mode": "balanced",
  "wheel_city_switch": true,
  "wheel_debounce_ms": 400,
  "autostart": false,
  "autostart_delay_sec": 0,
  "window_behavior": {
    "lock_position": false,
    "on_all_desktops": false,
    "always_on_top": false,
    "show_in_taskbar": false
  },
  "window_position": {
    "x": 100,
    "y": 100,
    "save_position": true,
    "saved": true
  }
}
```

---

## Parameter Reference

### Core Settings
- **`app_language`** (`string`, `"ru"` | `"uk"` | `"en"`): language of the UI elements, dialogs and system messages.
- **`weather_language`** (`string`): language of the textual weather descriptions ("Overcast", "Clear", "Light rain").
- **`update_interval_minutes`** (`integer`, default `60`): automatic data refresh period in minutes.
- **`max_consensus_age_minutes`** (`integer`, default `120`): maximum age of cached data before it is considered stale.
- **`home_city`** (`string`): the home city shown at startup.
- **`cities`** (`list[object]`): the list of saved cities. Each object contains:
  - `name`: the locality name.
  - `lat`: geographical latitude (floating point).
  - `lon`: geographical longitude (floating point).
  - `country`: two-letter ISO country code.

### Appearance (`skin`)
- **`theme_mode`** (`string`):
  - `"auto_solar"` — automatic light/dark theme switching based on the sunrise/sunset calculation for the city coordinates.
  - `"light"` — light theme.
  - `"dark"` — dark theme.
- **`icons_name`** (`string`): the weather icon set (`"svg"` — the project's own default set, `"Meteocons_monochrome"`, `"WeatherIcons"`).
- **`scale`** (`float`, `0.8` – `1.5`): widget scaling factor.
- **`opacity`** (`float`, `0.1` – `1.0`): widget background opacity.
- **`weekend_color`** (`string`, hex code): highlight color for Saturday and Sunday in the calendar.
- **`wind_arrow_color`** (`string`, hex code): wind direction arrow color on the compass.

### Widget Blocks (`view_blocks`)
Each block is controlled by a separate key with an `"enabled"` parameter (`true` / `false`):
- **`now`**: current temperature, weather condition and city.
- **`today`**: brief forecast for the current day.
- **`day_periods`**: temperature and precipitation by day periods (morning, afternoon, evening, night).
- **`daily`**: multi-day forecast. The `"days"` parameter (`integer`, `3` – `10`) sets the number of days.
- **`hourly`**: compact hourly block on the widget.
- **`wind`**: compact wind rose with direction and speed.
- **`astronomy`**: sunrise/sunset times, moon phase.
- **`metrics`**: key atmospheric parameters (humidity, pressure, dew point).
- **`additional_info`**: extended meteorological parameters.

### Units (`units`)
- **`temp`**: `"C"` (Celsius) or `"F"` (Fahrenheit).
- **`wind`**: `"m/s"` (meters per second), `"km/h"`, `"mph"`, `"knots"`.
- **`pressure`**: `"mmHg"` (millimeters of mercury) or `"hPa"` (hectopascals / millibars).
- **`distance`**: `"km"` (kilometers) or `"mi"` (miles).

### Network and Resilience (`network`)
- **`timeout_seconds`** (`float`): timeout of a single HTTP request (seconds).
- **`dns_timeout_seconds`** (`float`): DNS resolution time limit.
- **`retries`** (`integer`): number of retries on failure.
- **`prefer_ipv4`** (`boolean`): IPv4 connection preference.
- **`fetch_timeout_seconds`** (`float`): maximum total time of one consensus collection cycle.

### Window Behavior (`window_behavior` and `window_position`)
- **`lock_position`** (`boolean`): prevent accidental mouse movement of the widget.
- **`on_all_desktops`** (`boolean`): show the widget on all virtual desktops.
- **`always_on_top`** (`boolean`): pin above other windows.
- **`show_in_taskbar`** (`boolean`): show the widget button on the taskbar (default `false`).
- **`save_position`** (`boolean`): save and restore the `(x, y)` coordinates on the screen.
