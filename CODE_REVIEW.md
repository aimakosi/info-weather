#### 1. Пропущена зависимость Pillow в pyproject.toml (Важно для дистрибьюции) [ИСПРАВЛЕНО]

• Файлы: pyproject.toml:26-28, packaging/scripts/build_deb.py, packaging/scripts/build_pkg.py
• Статус: Исправлено.
• Решение: В `pyproject.toml` в секцию `dependencies` добавлена зависимость `"Pillow>=9.0.0"`. В сборочные скрипты пакетов также включены зависимости `python3-pil` (.deb) и `python-pillow` (Arch/AUR).

──────
#### 2. Запросы Kp-индекса геомагнитной активности обходят HttpClient [ИСПРАВЛЕНО]

• Файл: core/geomagnetic.py
• Статус: Исправлено.
• Решение: Прямой вызов `urllib.request.urlopen` заменён на централизованный `core.http.get_default_http_client().fetch_json(NOAA_KP_INDEX_URL, timeout=timeout)`. Теперь запросы корректно уважают настройки таймаутов, DNS, IPv4 fallback и прокси.

──────
#### 3. Отмена устаревших запросов при поиске городов (UX и оптимизация сети) [ИСПРАВЛЕНО]

• Файл: ui/dialogs/city_search_dialog.py
• Статус: Исправлено.
• Решение: Добавлен `self._active_search_token = CancellationToken()`. При новом поиске, изменении текста или закрытии окна предыдущий токен отменяется, а активный токен передаётся в `provider.search_cities(query, cancel_token=token, limit=5)`. Устаревшие фоновые сетевые запросы прерываются немедленно.

──────
#### 4. Неполная локализация статусных строк для украинского языка [ИСПРАВЛЕНО]

• Файлы: core/i18n.py, providers/weather.py, data/fallback.py, core/astronomy.py
• Статус: Исправлено.
• Решение: В `core/i18n.py` добавлены ключи `status_cached_updating`, `status_cached_offline`, `status_offline_era5`, `unit_distance_km` с переводами для `ru`, `uk`, `en`. В `weather.py`, `fallback.py` и `astronomy.py` хардкод `lang == "ru"` заменён на вызовы `t()`.

──────
#### 5. Асинхронное обновление Kp-индекса при первом запуске [ИСПРАВЛЕНО]

• Файлы: core/geomagnetic.py, ui/blocks/astronomy_block.py
• Статус: Исправлено.
• Решение: `get_geomagnetic_activity(..., on_updated=...)` теперь передаёт колбэк в `fetch_geomagnetic_activity_async(on_complete=on_updated)`. В блоке астрономии передан обработчик через `QTimer.singleShot`, обновляющий значение Kp-индекса и тултип сразу же по завершении фоновой загрузки данных от NOAA.
