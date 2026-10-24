# Справочник конфигурации config.json ⚙️

Конфигурационный файл приложения хранится по пути:
- **Linux:** `~/.config/info-weather/config.json`
- **Windows:** `%LOCALAPPDATA%\info-weather\config.json`

Файл автоматически создается при первом запуске со значениями по умолчанию. При изменении настроек через графический интерфейс файл перезаписывается атомарно.

---

## Пример полной конфигурации

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
  "home_city": "Абакан",
  "current_city": "Абакан",
  "cities": [
    {
      "name": "Абакан",
      "lat": 53.7167,
      "lon": 91.4292,
      "country": "RU"
    },
    {
      "name": "Санкт-Петербург",
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

## Описание параметров

### Основные настройки
- **`app_language`** (`string`, `"ru"` | `"uk"` | `"en"`): язык элементов пользовательского интерфейса, диалогов и системных сообщений.
- **`weather_language`** (`string`): язык текстовых описаний погоды («Пасмурно», «Ясно», «Небольшой дождь»).
- **`update_interval_minutes`** (`integer`, по умолчанию `60`): период автоматического обновления данных в минутах.
- **`max_consensus_age_minutes`** (`integer`, по умолчанию `120`): максимальный возраст кэшированных данных до признания их устаревшими.
- **`home_city`** (`string`): название домашнего города, отображаемого при первом старте.
- **`cities`** (`list[object]`): список сохраненных городов. Каждый объект содержит поля:
  - `name`: название населенного пункта.
  - `lat`: географическая широта (число с плавающей точкой).
  - `lon`: географическая долгота (число с плавающей точкой).
  - `country`: двухбуквенный ISO-код страны.

### Оформление (`skin`)
- **`theme_mode`** (`string`):
  - `"auto_solar"` — автоматическое переключение светлой/темной темы по расчету восхода и заката для координат города.
  - `"light"` — светлая тема.
  - `"dark"` — темная тема.
- **`icons_name`** (`string`): набор погодных иконок (`"svg"` — собственный набор по умолчанию, `"Meteocons_monochrome"`, `"WeatherIcons"`).
- **`scale`** (`float`, `0.8` – `1.5`): коэффициент масштабирования виджета.
- **`opacity`** (`float`, `0.1` – `1.0`): непрозрачность фона виджета.
- **`weekend_color`** (`string`, hex-код): цвет выделения субботы и воскресенья в календаре.
- **`wind_arrow_color`** (`string`, hex-код): цвет указателя направления ветра на компасе.

### Блоки виджета (`view_blocks`)
Каждый блок управляется отдельным ключом с параметром `"enabled"` (`true` / `false`):
- **`now`**: текущая температура, состояние погоды и город.
- **`today`**: краткий прогноз на текущие сутки.
- **`day_periods`**: температура и осадки по периодам суток (утро, день, вечер, ночь).
- **`daily`**: прогноз на несколько дней. Параметр `"days"` (`integer`, `3` – `10`) задает количество дней.
- **`hourly`**: компактный почасовой блок на виджете.
- **`wind`**: компактная роза ветров с направлением и скоростью.
- **`astronomy`**: время восхода/заката, фаза Луны.
- **`metrics`**: ключевые параметры атмосферы (влажность, давление, точка росы).
- **`additional_info`**: расширенные метеорологические параметры.

### Единицы измерения (`units`)
- **`temp`**: `"C"` (градусы Цельсия) или `"F"` (градусы Фаренгейта).
- **`wind`**: `"m/s"` (метры в секунду), `"km/h"` (км/ч), `"mph"` (мили/ч), `"knots"` (узлы).
- **`pressure`**: `"mmHg"` (миллиметры ртутного столба) или `"hPa"` (гектопаскали / миллибары).
- **`distance`**: `"km"` (километры) или `"mi"` (мили).

### Сеть и отказоустойчивость (`network`)
- **`timeout_seconds`** (`float`): таймаут одного HTTP-запроса (сек).
- **`dns_timeout_seconds`** (`float`): лимит времени на DNS-резолвинг.
- **`retries`** (`integer`): количество повторных попыток при сбое.
- **`prefer_ipv4`** (`boolean`): приоритет соединения по протоколу IPv4.
- **`fetch_timeout_seconds`** (`float`): максимальное общее время цикла сбора консенсуса.

### Поведение окна (`window_behavior` и `window_position`)
- **`lock_position`** (`boolean`): запрет случайного перемещения виджета мышью.
- **`on_all_desktops`** (`boolean`): отображение виджета на всех виртуальных рабочих столах.
- **`always_on_top`** (`boolean`): закрепление поверх других окон.
- **`show_in_taskbar`** (`boolean`): отображение кнопки виджета на панели задач (по умолчанию `false`).
- **`save_position`** (`boolean`): сохранение и восстановление координат `(x, y)` на экране.
