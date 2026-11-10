# Полное детальное ревью кодовой базы `info-weather`

**Версия проекта:** `0.1.0`  
**Стек:** Python 3.10+, PySide6 (Qt6), Pillow, `urllib` (stdlib)  
**Архитектура:** Модульный десктопный информер погоды для Linux (KDE Plasma / Wayland / X11) с консенсусным слиянием источников, честным офлайн-режимом (ERA5) и процедурными визуальными эффектами.  
**Объём проверенного кода:** ~11 500 строк Python-кода, 144 unit-теста, ресурсы, конфигурации сборки (.deb, AUR, AppStream, KWin).

---

## 1. Общее архитектурное резюме

Кодовая база спроектирована грамотно и демонстрирует высокую культуру разработки:
1. **Чёткое разделение ответственности (Separation of Concerns):**
   - Пакет [`models`](file:///A:/mine/info-weather/models/weather.py) содержит строго типизированные структуры данных ([`WeatherForecastData`](file:///A:/mine/info-weather/models/weather.py#L417-L535), [`CurrentConditions`](file:///A:/mine/info-weather/models/weather.py#L370-L415), [`HourlyForecast`](file:///A:/mine/info-weather/models/weather.py#L13-L58), [`DailyForecast`](file:///A:/mine/info-weather/models/weather.py#L60-L108)), не зависящие от GUI.
   - Слой [`core`](file:///A:/mine/info-weather/core/) содержит чистую бизнес-логику (астрономические расчеты NOAA, геомагнитная активность SWPC, конвертация единиц, конфигуратор, атомарный кэш, нотификации).
   - Слой [`providers`](file:///A:/mine/info-weather/providers/) абстрагирует метеорологические API ([`OpenMeteoClient`](file:///A:/mine/info-weather/providers/clients/open_meteo.py#L40), [`MetNorwayClient`](file:///A:/mine/info-weather/providers/clients/met_norway.py#L38), [`WttrClient`](file:///A:/mine/info-weather/providers/clients/wttr.py#L37)) и консенсусное слияние ([`merge_source_forecasts`](file:///A:/mine/info-weather/providers/consensus.py#L120-L520)).
   - Слой [`ui`](file:///A:/mine/info-weather/ui/) полностью изолирован от прямых синхронных сетевых вызовов: все запросы выполняются асинхронно в пуле потоков через [`WeatherProvider.fetch_forecast_async`](file:///A:/mine/info-weather/providers/weather.py#L388-L460) и безопасно маршалятся в главный поток Qt через механизм сигналов-слотов.
2. **Консенсус и надежность:** Реализована многоуровневая деградация данных: $S3 \to S2 \to S1 \to S0$ (актуальный кэш $\to$ устаревший кэш $\to$ историческая климатология ERA5). Приложение никогда не зависает и не показывает белый экран при обрыве сети.
3. **Интеграция с KDE Plasma:** Поддерживаются EWMH-атрибуты, скрытие из панели задач, корректные KWin-правила для Meta+D, автостарт, адаптация к системной цветовой схеме (светлая/тёмная) и солнечному циклу.

---

## 2. Критические дефекты и баги (P0 / P1)

### 2.1. [Runtime Bug / TypeError] Несовпадение сигнатуры в `fetch_geomagnetic_activity_sync`
- **Файл:** [`core/geomagnetic.py`](file:///A:/mine/info-weather/core/geomagnetic.py#L138-L142)
- **Суть проблемы:**
  В модуле геомагнитной активности выполняется вызов:
  ```python
  data = http_client.fetch_json(
      NOAA_KP_INDEX_URL,
      headers={"User-Agent": "info-weather-app/1.0 (space-weather)"},
      timeout=timeout,
  )
  ```
  Однако метод [`HttpClient.fetch_json`](file:///A:/mine/info-weather/core/http.py#L270-L279) не имеет параметра `headers` — он принимает `extra_headers: dict[str, str] | None = None`.
  При реальном сетевом запросе к NOAA SWPC вызов завершается исключением:
  `TypeError: HttpClient.fetch_json() got an unexpected keyword argument 'headers'`.
- **Почему не упал unit-тест:**
  В [`tests/test_geomagnetic.py`](file:///A:/mine/info-weather/tests/test_geomagnetic.py#L87) используется `@patch("core.http.HttpClient.fetch_json")` без спецификации (`autospec=True`), поэтому `MagicMock` принял некорректный аргумент молча.
- **Решение:**
  В [`core/geomagnetic.py`](file:///A:/mine/info-weather/core/geomagnetic.py#L140) заменить `headers=` на `extra_headers=`, либо в [`HttpClient.fetch_json`](file:///A:/mine/info-weather/core/http.py#L278) поддержать оба имени (`headers: dict[str, str] | None = None`). В тесте добавить `autospec=True`.

---

### 2.2. [Скрытый сбой в тестах] Передача неинициализированного `MagicMock` в консенсус
- **Файл:** [`tests/test_weather_provider.py`](file:///A:/mine/info-weather/tests/test_weather_provider.py#L334-L365)
- **Суть проблемы:**
  В тесте `test_multiple_rapid_async_fetches_no_deadlock` задается мок для `mock_om`, но не задаются возвращаемые значения для `mock_met` и `mock_wttr`.
  В результате пул потоков возвращает экземпляр `MagicMock` вместо `SourceForecast | None`. При слиянии прогнозов в [`providers/consensus.py`](file:///A:/mine/info-weather/providers/consensus.py#L140) выражение `now - s.fetched_at <= max_consensus_age_seconds` падает с ошибкой:
  `TypeError: '<=' not supported between instances of 'MagicMock' and 'float'`.
  Затем попытка кэширования дает `Object of type MagicMock is not JSON serializable`, и провайдер аварийно откатывается к ERA5-климатологии. Тест не падал только потому, что проверял лишь длину результирующего списка `len(received) >= 1`.
- **Решение:**
  Явно объявить `self.mock_met.fetch_forecast.return_value = None` и `self.mock_wttr.fetch_forecast.return_value = None` в данном тесте.

---

### 2.3. [Arch Linux Packaging Bug] Некорректное имя пакета зависимости в `PKGBUILD`
- **Файл:** [`packaging/arch/PKGBUILD`](file:///A:/mine/info-weather/packaging/arch/PKGBUILD#L9), [`packaging/scripts/build_pkg.py`](file:///A:/mine/info-weather/packaging/scripts/build_pkg.py#L169)
- **Суть проблемы:**
  В зависимостях указано `depends=('python>=3.10' 'pyside6' 'python-pillow')`.
  В официальном репозитории Arch Linux (`extra`) пакет биндингов Qt6 называется **`python-pyside6`**, а не `pyside6`. При сборке через `makepkg -si` установка зависимостей завершится ошибкой ненахождения пакета `pyside6`. (В [`main.py:214`](file:///A:/mine/info-weather/main.py#L214) система сама рекомендует `pacman -S python-pyside6`).
- **Решение:**
  Заменить `'pyside6'` на `'python-pyside6'` в `PKGBUILD` и генераторе `build_pkg.py`.

---

## 3. Анализ надежности, ресурсов и сетевого взаимодействия

### 3.1. Утечка осиротевших временных файлов при ошибках сериализации
- **Файлы:**
  - [`core/cache.py`](file:///A:/mine/info-weather/core/cache.py#L87-L97) (`_save_cache_locked`)
  - [`core/config.py`](file:///A:/mine/info-weather/core/config.py#L273-L297) (`save`)
  - [`core/notifications.py`](file:///A:/mine/info-weather/core/notifications.py#L98-L107) (`_save_state_locked`)
- **Суть проблемы:**
  Для атомарной записи используется связка `tempfile.mkstemp` / `NamedTemporaryFile(delete=False)` $\to$ `json.dump` $\to$ `os.replace`.
  Если во время `json.dump` возникает исключение (например, несериализуемый объект в словаре или нехватка места на диске), управление сразу переходит в `except:`, минуя `os.replace`. При этом созданный `.tmp` файл **не удаляется** и навсегда остается в каталоге пользователя (`~/.config/info-weather/` или `~/.cache/info-weather/`).
- **Рекомендация:**
  Использовать блок `try ... finally` для гарантированного удаления `tmp_path` при неудачном `os.replace`:
  ```python
  tmp_path = None
  try:
      fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix="state_", suffix=".tmp")
      with open(fd, "w", encoding="utf-8") as f:
          json.dump(data, f, ensure_ascii=False)
      os.replace(tmp_path, final_path)
      tmp_path = None
  finally:
      if tmp_path and os.path.exists(tmp_path):
          try:
              os.unlink(tmp_path)
          except OSError:
              pass
  ```

---

### 3.2. Потенциальное накопление daemon-потоков в DNS-резолвере
- **Файл:** [`core/http.py`](file:///A:/mine/info-weather/core/http.py#L36-L63) (`_resolve_host`)
- **Суть проблемы:**
  Для ограничения таймаута DNS создается отдельный поток:
  ```python
  thread = threading.Thread(target=_worker, name="info-weather-dns", daemon=True)
  thread.start()
  thread.join(timeout)
  if thread.is_alive():
      raise TimeoutError(...)
  ```
  В Python поток ОС нельзя прервать извне. Если системный вызов `socket.getaddrinfo` наглухо зависает из-за сбоя в локальной сети, этот поток продолжает висеть в памяти как поток-зомби до завершения процесса.
- **Рекомендация:**
  Для редких запросов (раз в час) это не критично, но более чистым решением является использование общего `ThreadPoolExecutor(max_workers=2)` для DNS-задач, чтобы число фоновых потоков резолвинга было строго ограничено сверху.

---

### 3.3. Кэширование словаря в `WeatherForecastData` и рассинхронизация при мутации
- **Файл:** [`models/weather.py`](file:///A:/mine/info-weather/models/weather.py#L470-L480, #L625-L640)
- **Суть проблемы:**
  Класс [`WeatherForecastData`](file:///A:/mine/info-weather/models/weather.py#L417) реализует интерфейс `MutableMapping`. Для оптимизации повторного доступа по ключам вида `data["temp"]` результат `to_dict()` кэшируется в `_cached_dict`.
  Сброс кэша (`_cached_dict = None`) происходит только при обращении через `__setitem__` (`data["k"] = v`).
  Если код напрямую модифицирует атрибут датакласса (например, `fc.city_name = loc_name` в [`providers/weather.py:219`](file:///A:/mine/info-weather/providers/weather.py#L219) или в [`ui/widget_window.py:1115`](file:///A:/mine/info-weather/ui/widget_window.py#L1115)), а до этого к объекту уже обращались как к словарю, `_cached_dict` **не сбрасывается**, и последующее обращение `fc["city_name"]` вернет старое значение!
- **Рекомендация:**
  Добавить переопределение `__setattr__`:
  ```python
  def __setattr__(self, name: str, value: Any) -> None:
      if name != "_cached_dict":
          object.__setattr__(self, "_cached_dict", None)
      object.__setattr__(self, name, value)
  ```

---

## 4. UI, графические эффекты и KDE-интеграция

### 4.1. [Оптимизация CPU / Батареи] Фоновый холостой ход анимации эффектов
- **Файл:** [`ui/effects/weather_effects.py`](file:///A:/mine/info-weather/ui/effects/weather_effects.py#L166-L209) ([`WeatherEffectsCanvas`](file:///A:/mine/info-weather/ui/effects/weather_effects.py#L80))
- **Суть проблемы:**
  В классе холста анимаций (`WeatherEffectsCanvas`) таймер `_timer` запускается с частотой 20–28 FPS (каждые 35–50 мс) для расчета движения капель дождя, снежинок и перерисовки виджета (`self.update()`).
  При этом в классе **отсутствуют обработчики `hideEvent` и `showEvent`**.
  Если пользователь скрывает виджет (в трей, в режиме `indicator_only`, или если рабочий стол перекрыт полноэкранным приложением), таймер **продолжает непрерывно тикать**, расходуя процессорное время и батарею ноутбука.
- **Решение:**
  Останавливать таймер при скрытии и возобновлять при показе:
  ```python
  def hideEvent(self, event: Any) -> None:
      super().hideEvent(event)
      if self._timer.isActive():
          self._timer.stop()

  def showEvent(self, event: Any) -> None:
      super().showEvent(event)
      self._configure_timer()
  ```

---

### 4.2. Несогласованность дефолтных координат (Москва vs Абакан)
- **Файлы:**
  - [`ui/dialogs/settings_dialog.py:239`](file:///A:/mine/info-weather/ui/dialogs/settings_dialog.py#L239)
  - [`ui/dialogs/city_search_dialog.py:173`](file:///A:/mine/info-weather/ui/dialogs/city_search_dialog.py#L173)
  - [`ui/widget_window.py:626-627`](file:///A:/mine/info-weather/ui/widget_window.py#L626-L627)
- **Суть проблемы:**
  В релизном плане (этап 11b) дефолтный город проекта был изменен на **Абакан** (`lat=53.7167, lon=91.4292`). Это изменение было применено в [`main.py`](file:///A:/mine/info-weather/main.py#L146) и [`providers/weather.py`](file:///A:/mine/info-weather/providers/weather.py#L164-L184).
  Однако в диалогах настроек, поиска городов и расчете солнечного времени в `widget_window.py` до сих пор вшиты запасные координаты Москвы:
  `lat, lon = 55.75, 37.61`.
- **Рекомендация:**
  Вынести единую константу `DEFAULT_CITY_COORDINATES = (53.7167, 91.4292)` в [`core/config.py`](file:///A:/mine/info-weather/core/config.py) и использовать её везде вместо ручного дублирования координат.

---

### 4.3. Связывание компонентов в `SegmentedPillToggle` через `parent()`
- **Файл:** [`ui/dialogs/detailed_forecast_dialog.py:91-95`](file:///A:/mine/info-weather/ui/dialogs/detailed_forecast_dialog.py#L91-L95)
- **Суть проблемы:**
  При переключении вкладок переключатель экранов вызывает метод родителя через интроспекцию:
  ```python
  parent = self.parent()
  if hasattr(parent, "_on_tab_switched"):
      parent._on_tab_switched(index)
  ```
  Это нарушает принцип инкапсуляции компонентов Qt: если `SegmentedPillToggle` будет обернут в дополнительный `QFrame` или `QLayout`, `self.parent()` перестанет быть диалогом, и переключение вкладок перестанет работать.
- **Рекомендация:**
  Использовать стандартный сигнал Qt:
  ```python
  class SegmentedPillToggle(QFrame):
      index_changed = Signal(int)
      ...
      def set_index(self, index: int, notify: bool = True) -> None:
          ...
          if notify:
              self.index_changed.emit(index)
  ```

---

## 5. Консенсусный движок и математика прогноза

### 5.1. Потеря фактических почасовых данных при построении детальных суток
- **Файл:** [`providers/consensus.py`](file:///A:/mine/info-weather/providers/consensus.py#L402-L420)
- **Суть проблемы:**
  Для экрана детальной аналитики формируется массив `DayDetailedForecast.hourly_temps`.
  В строке 365 модуль находит почасовые точки дня:
  ```python
  day_hours = [h for h in merged_hourly if getattr(h, "time_iso", "") and h.time_iso.startswith(d_str)]
  ```
  Однако в строках 402-420 фактические температуры из `day_hours` полностью игнорируются, и кривая строится искусственно по синусоиде:
  ```python
  diurnal = math.sin((h - 9) / 24.0 * 2 * math.pi)
  val = round(min_val + (max_val - min_val) * (diurnal + 1.0) / 2.0, 1)
  ```
  Если провайдеры Open-Meteo и MET Norway предоставили точный почасовой прогноз (например, прохождение холодного фронта днем, когда температура падает, а не растет), синусоида искажает реальный прогноз.
- **Рекомендация:**
  Если `day_hours` содержит точки для всех 24 часов (или интерполируемые значения), использовать фактические консенсусные значения из `day_hours`, а к `math.sin` прибегать только как к запасному варианту (fallback) при их отсутствии.

---

### 5.2. Устойчивость `calc_median` к `NaN`
- **Файл:** [`providers/consensus.py`](file:///A:/mine/info-weather/providers/consensus.py#L56-L85)
- **Суть проблемы:**
  В Python `sorted()` с элементами, содержащими `float('nan')`, дает неопределенный порядок сортировки, поскольку любое сравнение с `NaN` возвращает `False`. Если внешний API пришлет `NaN` в одном из численных полей, расчет медианы может стать недетерминированным.
- **Рекомендация:**
  Фильтровать нечисловые значения: `items = [(v, s) for v, s in items if v is not None and not math.isnan(v)]`.

---

## 6. Локализация (i18n)

### 6.1. Хардкод строк уведомлений и статуса консенсуса в обход словаря
- **Файлы:**
  - [`core/notifications.py:193-305`](file:///A:/mine/info-weather/core/notifications.py#L193-L305)
  - [`providers/consensus.py:483-494`](file:///A:/mine/info-weather/providers/consensus.py#L483-L494)
- **Суть проблемы:**
  В проекте заявлена полная поддержка трех языков: русского (`ru`), украинского (`uk`) и английского (`en`).
  Однако в [`core/notifications.py`](file:///A:/mine/info-weather/core/notifications.py) все тексты алертов написаны через бинарное ветвление:
  ```python
  title = "Заморозки" if lang == "ru" else "Frost Warning"
  title = "Штормовое предупреждение" if lang == "ru" else "High Wind Warning"
  title = "Резкое похолодание" if lang == "ru" else "Sharp Temperature Drop"
  ```
  Аналогично в [`providers/consensus.py`](file:///A:/mine/info-weather/providers/consensus.py#L484):
  ```python
  status_text = f"Консенсус 3 источников ({', '.join(src_names)})" if lang == "ru" else f"Consensus of 3 sources ({', '.join(src_names)})"
  ```
  При выборе украинского языка (`lang == "uk"`) пользователь получает сообщения на английском языке вместо украинского.
- **Рекомендация:**
  Вынести эти строки в словарь [`core/i18n.py`](file:///A:/mine/info-weather/core/i18n.py) и использовать стандартную функцию `t("key", _lang=lang)`.

---

## 7. Скрипты инсталляции и деинсталляции (`packaging/`)

### 7.1. Поведение деинсталлятора при обычном запуске (без `--purge`)
- **Файл:** [`packaging/scripts/uninstall.sh:24-95`](file:///A:/mine/info-weather/packaging/scripts/uninstall.sh#L24-L95)
- **Суть проблемы:**
  Скрипт [`install.sh`](file:///A:/mine/info-weather/packaging/scripts/install.sh#L21-L34) копирует кодовую базу приложения в `~/.local/share/info-weather`.
  В скрипте `uninstall.sh` удаление каталога `~/.local/share/info-weather` происходит **только** при передаче флага `--purge`.
  Если пользователь запускает `./uninstall.sh` без параметров (чтобы удалить установленную программу, но сохранить настройки), исполняемые файлы программы (`main.py`, модули, ассеты) остаются неудаленными на диске.
- **Рекомендация:**
  При обычном удалении очищать директорию с файлами приложения (`~/.local/share/info-weather`), сохраняя в ней только пользовательские модификации (например, пользовательские скины в `skins/`), либо удалять `~/.local/share/info-weather` целиком в обычном режиме, а под `--purge` оставить удаление конфигурации (`~/.config/info-weather`) и кэша (`~/.cache/info-weather`).

---

## 8. Тестовое покрытие и тестовый процесс

1. **Скорость и чистота:** Все 144 теста проходят за ~6.4 секунды. Сетевые запросы заглушены.
2. **Предупреждения ресурсов (ResourceWarning):**
   В [`tests/test_http.py:111`](file:///A:/mine/info-weather/tests/test_http.py#L111) создается `HTTPError(..., fp=io.BytesIO(b"{}"))`. Поскольку файловый дескриптор `fp` не закрывается явно в тесте, Python выдает `ResourceWarning: Implicitly cleaning up <HTTPError ...>`. Рекомендуется закрывать `fp.close()` или использовать контекстный менеджер.
3. **Строгость моков:**
   Рекомендуется включить `autospec=True` при мокировании методов `HttpClient`, чтобы сигнатуры методов автоматически валидировались во всех тестах (это предотвратило бы описанный выше баг 2.1).

---

## 9. Сводная матрица задач по итогам ревью

| Приоритет | Категория | Файл / Компонент | Суть исправления |
|---|---|---|---|
| **[P0]** | Bug (Runtime) | [`core/geomagnetic.py`](file:///A:/mine/info-weather/core/geomagnetic.py#L140) | Заменить `headers=` на `extra_headers=` при вызове `fetch_json` |
| **[P0]** | Packaging | [`packaging/arch/PKGBUILD`](file:///A:/mine/info-weather/packaging/arch/PKGBUILD#L9), [`build_pkg.py`](file:///A:/mine/info-weather/packaging/scripts/build_pkg.py#L169) | Заменить имя зависимости Arch Linux `'pyside6'` на `'python-pyside6'` |
| **[P1]** | Bug (Tests) | [`tests/test_weather_provider.py`](file:///A:/mine/info-weather/tests/test_weather_provider.py#L334) | Задать `return_value = None` для `mock_met` и `mock_wttr` в тесте асинхронного слияния |
| **[P1]** | Performance | [`ui/effects/weather_effects.py`](file:///A:/mine/info-weather/ui/effects/weather_effects.py#L166) | Добавить `hideEvent` / `showEvent` для остановки анимационного таймера в скрытом режиме |
| **[P1]** | Resource Leak | [`core/cache.py`](file:///A:/mine/info-weather/core/cache.py#L88), [`core/config.py`](file:///A:/mine/info-weather/core/config.py#L283), [`core/notifications.py`](file:///A:/mine/info-weather/core/notifications.py#L101) | Добавить удаление осиротевших `.tmp` файлов в блоке `finally` при сбоях атомарного сохранения |
| **[P1]** | Data Integrity | [`models/weather.py`](file:///A:/mine/info-weather/models/weather.py#L472, #L629) | Реализовать инвалидацию `_cached_dict` в `__setattr__` датакласса `WeatherForecastData` |
| **[P2]** | i18n | [`core/notifications.py`](file:///A:/mine/info-weather/core/notifications.py#L193), [`providers/consensus.py`](file:///A:/mine/info-weather/providers/consensus.py#L484) | Заменить бинарный тернарный оператор `lang == "ru"` на ключи словаря с поддержкой `uk` |
| **[P2]** | Consistency | [`ui/dialogs/settings_dialog.py`](file:///A:/mine/info-weather/ui/dialogs/settings_dialog.py#L239), [`city_search_dialog.py`](file:///A:/mine/info-weather/ui/dialogs/city_search_dialog.py#L173), [`widget_window.py`](file:///A:/mine/info-weather/ui/widget_window.py#L626) | Заменить хардкод координат Москвы `55.75, 37.61` на единую константу Абакана |
| **[P2]** | Architecture | [`ui/dialogs/detailed_forecast_dialog.py`](file:///A:/mine/info-weather/ui/dialogs/detailed_forecast_dialog.py#L92) | Заменить вызов `parent._on_tab_switched` на сигнал `Signal(int)` |
| **[P2]** | Logic | [`providers/consensus.py`](file:///A:/mine/info-weather/providers/consensus.py#L402) | Использовать реальные почасовые точки дня для детального прогноза вместо принудительной синусоиды |
