"""Internationalization (i18n) framework for info-weather.

Translations live in the built-in BUILTIN_STRINGS dictionary (ru/uk/en)
and are resolved via t(); date/time formatting helpers are included.
"""

from __future__ import annotations

import locale
import os
from datetime import datetime
from typing import Any

_current_language: str = "ru"

SUPPORTED_LANGUAGES = {
    "ru": "Русский",
    "uk": "Українська",
    "en": "English",
}

# Built-in translations for all UI strings (ru/uk/en)
BUILTIN_STRINGS: dict[str, dict[str, str]] = {
    "app_name": {
        "ru": "Информер погоды",
        "uk": "Інформер погоди",
        "en": "Info Weather",
    },
    "weather_today": {
        "ru": "Сегодня",
        "uk": "Сьогодні",
        "en": "Today",
    },
    "weather_tomorrow": {
        "ru": "Завтра",
        "uk": "Завтра",
        "en": "Tomorrow",
    },
    "weather_now": {
        "ru": "Сейчас",
        "uk": "Зараз",
        "en": "Now",
    },
    "weather_feels_like": {
        "ru": "Ощущается как",
        "uk": "Відчувається як",
        "en": "Feels like",
    },
    "weather_wind": {
        "ru": "Ветер",
        "uk": "Вітер",
        "en": "Wind",
    },
    "weather_humidity": {
        "ru": "Влажность",
        "uk": "Вологість",
        "en": "Humidity",
    },
    "weather_humidity_short": {
        "ru": "влажн.",
        "uk": "волог.",
        "en": "hum.",
    },
    "weather_dew_point": {
        "ru": "Т. росы",
        "uk": "Т. роси",
        "en": "Dew point",
    },
    "weather_pressure": {
        "ru": "Давление",
        "uk": "Тиск",
        "en": "Pressure",
    },
    "weather_uv": {
        "ru": "УФ-индекс",
        "uk": "УФ-індекс",
        "en": "UV Index",
    },
    "weather_visibility": {
        "ru": "Видимость",
        "uk": "Видимість",
        "en": "Visibility",
    },
    "weather_precipitation": {
        "ru": "Осадки",
        "uk": "Опади",
        "en": "Precipitation",
    },
    "weather_sunrise": {
        "ru": "Восход",
        "uk": "Схід",
        "en": "Sunrise",
    },
    "weather_sunset": {
        "ru": "Закат",
        "uk": "Захід",
        "en": "Sunset",
    },
    "weather_daylight": {
        "ru": "Долгота дня",
        "uk": "Тривалість дня",
        "en": "Daylight duration",
    },
    "weather_moon": {
        "ru": "Луна",
        "uk": "Місяць",
        "en": "Moon",
    },
    "weather_geomagnetic": {
        "ru": "Магнитное поле",
        "uk": "Магнітне поле",
        "en": "Magnetic field",
    },
    "geomagnetic_quiet": {
        "ru": "Спокойное",
        "uk": "Спокійне",
        "en": "Quiet",
    },
    "geomagnetic_unsettled": {
        "ru": "Слабо возмущенное",
        "uk": "Слабо збурене",
        "en": "Unsettled",
    },
    "geomagnetic_active": {
        "ru": "Возмущенное",
        "uk": "Збурене",
        "en": "Active",
    },
    "geomagnetic_minor_storm": {
        "ru": "Слабая буря (G1)",
        "uk": "Слабка буря (G1)",
        "en": "Minor Storm (G1)",
    },
    "geomagnetic_moderate_storm": {
        "ru": "Умеренная буря (G2)",
        "uk": "Помірна буря (G2)",
        "en": "Moderate Storm (G2)",
    },
    "geomagnetic_strong_storm": {
        "ru": "Сильная буря (G3)",
        "uk": "Сильна буря (G3)",
        "en": "Strong Storm (G3)",
    },
    "geomagnetic_severe_storm": {
        "ru": "Очень сильная буря (G4)",
        "uk": "Дуже сильна буря (G4)",
        "en": "Severe Storm (G4)",
    },
    "geomagnetic_extreme_storm": {
        "ru": "Экстремальная буря (G5)",
        "uk": "Екстремальна буря (G5)",
        "en": "Extreme Storm (G5)",
    },
    "weather_source": {
        "ru": "Источник",
        "uk": "Джерело",
        "en": "Source",
    },
    "weather_offline": {
        "ru": "Офлайн-данные (нет сети)",
        "uk": "Офлайн-дані (немає мережі)",
        "en": "Offline data (no network)",
    },
    "weather_stale": {
        "ru": "Данные устарели",
        "uk": "Дані застаріли",
        "en": "Data is stale",
    },
    "weather_basic_mode": {
        "ru": "Базовый режим",
        "uk": "Базовий режим",
        "en": "Basic mode",
    },
    "weather_no_data": {
        "ru": "Нет данных",
        "uk": "Немає даних",
        "en": "No data",
    },
    "weather_moon_phase_new": {
        "ru": "Новолуние",
        "uk": "Молодик",
        "en": "New Moon",
    },
    "weather_moon_phase_waxing_crescent": {
        "ru": "Растущий серп",
        "uk": "Молодий місяць",
        "en": "Waxing Crescent",
    },
    "weather_moon_phase_first_quarter": {
        "ru": "Первая четверть",
        "uk": "Перша чверть",
        "en": "First Quarter",
    },
    "weather_moon_phase_waxing_gibbous": {
        "ru": "Растущая Луна",
        "uk": "Прибуваючий місяць",
        "en": "Waxing Gibbous",
    },
    "weather_moon_phase_full": {
        "ru": "Полнолуние",
        "uk": "Повний місяць",
        "en": "Full Moon",
    },
    "weather_moon_phase_waning_gibbous": {
        "ru": "Убывающая Луна",
        "uk": "Спадаючий місяць",
        "en": "Waning Gibbous",
    },
    "weather_moon_phase_last_quarter": {
        "ru": "Последняя четверть",
        "uk": "Остання чверть",
        "en": "Last Quarter",
    },
    "weather_moon_phase_waning_crescent": {
        "ru": "Убывающий серп",
        "uk": "Старий місяць",
        "en": "Waning Crescent",
    },
    # UI & Settings Dialog
    "settings_title": {
        "ru": "Настройки — Info Weather",
        "uk": "Налаштування — Info Weather",
        "en": "Settings — Info Weather",
    },
    "btn_close": {
        "ru": "Закрыть",
        "uk": "Закрити",
        "en": "Close",
    },
    # Tab names
    "tab_theme": {
        "ru": "Оформление",
        "uk": "Оформлення",
        "en": "Appearance",
    },
    "tab_layout": {
        "ru": "Вид",
        "uk": "Вигляд",
        "en": "Layout",
    },
    "tab_units": {
        "ru": "Единицы",
        "uk": "Одиниці",
        "en": "Units",
    },
    "tab_providers": {
        "ru": "Провайдеры",
        "uk": "Провайдери",
        "en": "Providers",
    },
    "tab_notifications": {
        "ru": "Уведомления",
        "uk": "Сповіщення",
        "en": "Notifications",
    },
    "tab_general": {
        "ru": "Общие",
        "uk": "Загальні",
        "en": "General",
    },
    # General Tab
    "opt_language": {
        "ru": "Язык",
        "uk": "Мова",
        "en": "Language",
    },
    "opt_language_desc": {
        "ru": "Язык интерфейса программы и прогноза погоды",
        "uk": "Мова інтерфейсу програми та прогнозу погоди",
        "en": "User interface and weather forecast language",
    },
    "opt_app_language": {
        "ru": "Язык программы",
        "uk": "Мова програми",
        "en": "Program language",
    },
    "opt_app_language_desc": {
        "ru": "Язык пользовательского интерфейса",
        "uk": "Мова інтерфейсу користувача",
        "en": "User interface language",
    },
    "opt_weather_language": {
        "ru": "Язык погоды",
        "uk": "Мова погоди",
        "en": "Weather language",
    },
    "opt_weather_language_desc": {
        "ru": "Язык метеорологических описаний, дней недели и направлений ветра",
        "uk": "Мова метеорологічних описів, днів тижня та напрямків вітру",
        "en": "Language for weather descriptions, weekdays, and wind directions",
    },
    "opt_autostart": {
        "ru": "Автозапуск",
        "uk": "Автозапуск",
        "en": "Autostart",
    },
    "opt_autostart_chk": {
        "ru": "Запускать виджет при входе в систему",
        "uk": "Запускати віджет при вході в систему",
        "en": "Start widget on system startup",
    },
    "opt_update_interval": {
        "ru": "Интервал обновления данных",
        "uk": "Інтервал оновлення даних",
        "en": "Data update interval",
    },
    "interval_15m": {
        "ru": "Каждые 15 минут",
        "uk": "Кожні 15 хвилин",
        "en": "Every 15 minutes",
    },
    "interval_30m": {
        "ru": "Каждые 30 минут",
        "uk": "Кожні 30 хвилин",
        "en": "Every 30 minutes",
    },
    "interval_60m": {
        "ru": "Каждый час (рекомендуется)",
        "uk": "Щогодини (рекомендовано)",
        "en": "Every hour (recommended)",
    },
    "interval_120m": {
        "ru": "Каждые 2 часа",
        "uk": "Кожні 2 години",
        "en": "Every 2 hours",
    },
    # Theme Tab
    "theme_icons_title": {
        "ru": "Тема иконок погоды",
        "uk": "Тема піктограм погоди",
        "en": "Weather icon theme",
    },
    "theme_icons_svg": {
        "ru": "Векторные минималистичные (SVG)",
        "uk": "Векторні мінімалістичні (SVG)",
        "en": "Vector Minimal (SVG)",
    },
    "theme_icons_meteocons": {
        "ru": "Meteocons (Монохром)",
        "uk": "Meteocons (Монохром)",
        "en": "Meteocons (Monochrome)",
    },
    "theme_icons_desc": {
        "ru": "Выберите набор пиктограмм (поддерживаются все темы Gis-Weather):",
        "uk": "Виберіть набір піктограм (підтримуються всі теми Gis-Weather):",
        "en": "Choose icon set (all Gis-Weather themes supported):",
    },
    "theme_mode_title": {
        "ru": "Режим темы",
        "uk": "Режим теми",
        "en": "Theme mode",
    },
    "theme_mode_solar": {
        "ru": "По солнцу (восход / закат)",
        "uk": "За сонцем (схід / захід)",
        "en": "Solar cycle (sunrise / sunset)",
    },
    "theme_mode_system": {
        "ru": "Системная (KDE / Application Style)",
        "uk": "Системна (KDE / Application Style)",
        "en": "System (KDE / Application Style)",
    },
    "theme_mode_day": {
        "ru": "Дневная (светлая)",
        "uk": "Денна (світла)",
        "en": "Day (light)",
    },
    "theme_mode_night": {
        "ru": "Ночная (тёмная)",
        "uk": "Нічна (темна)",
        "en": "Night (dark)",
    },
    "theme_scale_title": {
        "ru": "Масштаб виджета",
        "uk": "Масштаб віджета",
        "en": "Widget scale",
    },
    "theme_scale_current": {
        "ru": "Текущий масштаб: {val:.1f}x",
        "uk": "Поточний масштаб: {val:.1f}x",
        "en": "Current scale: {val:.1f}x",
    },
    "theme_opacity_title": {
        "ru": "Непрозрачность фона",
        "uk": "Непрозорість фону",
        "en": "Background opacity",
    },
    "theme_opacity_current": {
        "ru": "Непрозрачность: {val}%",
        "uk": "Непрозорість: {val}%",
        "en": "Opacity: {val}%",
    },
    "theme_launch_mode_title": {
        "ru": "Вариант запуска",
        "uk": "Варіант запуску",
        "en": "Launch mode",
    },
    "theme_launch_mode_desc": {
        "ru": "Выберите режим отображения: виджет на рабочем столе, индикатор в трее или оба вместе",
        "uk": "Виберіть режим відображення: віджет на стільниці, індикатор у треї або разом",
        "en": "Choose display mode: desktop widget, tray indicator, or both",
    },
    "launch_mode_both": {
        "ru": "Виджет + Индикатор в трее",
        "uk": "Віджет + Індикатор у треї",
        "en": "Widget + Tray indicator",
    },
    "launch_mode_widget_only": {
        "ru": "Только виджет",
        "uk": "Тільки віджет",
        "en": "Widget only",
    },
    "launch_mode_indicator_only": {
        "ru": "Только индикатор в трее",
        "uk": "Тільки індикатор у треї",
        "en": "Tray indicator only",
    },
    "theme_group_display": {
        "ru": "Тема и режим отображения",
        "uk": "Тема та режим відображення",
        "en": "Theme & display mode",
    },
    "theme_group_geometry": {
        "ru": "Масштаб и прозрачность",
        "uk": "Масштаб та прозорість",
        "en": "Scale & opacity",
    },
    "theme_group_typography": {
        "ru": "Шрифты",
        "uk": "Шрифти",
        "en": "Fonts & Typography",
    },
    "theme_font_main": {
        "ru": "Основной шрифт:",
        "uk": "Основний шрифт:",
        "en": "Main font:",
    },
    "theme_font_small": {
        "ru": "Шрифт прогноза:",
        "uk": "Шрифт прогнозу:",
        "en": "Forecast font:",
    },
    "theme_font_small_desc": {
        "ru": "Шрифт для блока «Завтра» и прогноза на несколько дней",
        "uk": "Шрифт для блоку «Завтра» та прогнозу на кілька днів",
        "en": "Font for the Tomorrow block and the multi-day forecast",
    },
    "theme_weekend_hint": {
        "ru": "Например: Sa, Su (или Пн, Вт; 6, 7)",
        "uk": "Наприклад: Sa, Su (або Пн, Вт; 6, 7)",
        "en": "For example: Sa, Su (or Mon, Tue; 6, 7)",
    },
    "theme_group_seasonal": {
        "ru": "Сезонное дневное оформление (эффект «висящей» карточки)",
        "uk": "Сезонне денне оформлення (ефект «ширяючої» картки)",
        "en": "Seasonal daytime theme (floating card effect)",
    },
    "theme_seasonal_enable": {
        "ru": "Включить сезонную дневную тему",
        "uk": "Увімкнути сезонну денну тему",
        "en": "Enable seasonal daytime theme",
    },
    "theme_seasonal_mode": {
        "ru": "Сезон:",
        "uk": "Сезон:",
        "en": "Season:",
    },
    "theme_seasonal_auto": {
        "ru": "Автоматически (по календарю)",
        "uk": "Автоматично (за календарем)",
        "en": "Automatic (by calendar month)",
    },
    "theme_seasonal_winter": {
        "ru": "❄️ Зима (морозные узоры и снег)",
        "uk": "❄️ Зима (морозні візерунки та сніг)",
        "en": "❄️ Winter (frost & snow)",
    },
    "theme_seasonal_spring": {
        "ru": "🌸 Весна (ландыши и березовая зелень)",
        "uk": "🌸 Весна (конвалії та березова зелень)",
        "en": "🌸 Spring (lilies of the valley & birch)",
    },
    "theme_seasonal_summer": {
        "ru": "☀️ Лето (ромашки, васильки и подсолнухи)",
        "uk": "☀️ Літо (ромашки, волошки та соняшники)",
        "en": "☀️ Summer (wildflowers & daisies)",
    },
    "theme_seasonal_autumn": {
        "ru": "🍂 Осень (золотой клен, дуб и рябина)",
        "uk": "🍂 Осінь (золотий клен, дуб та горобина)",
        "en": "🍂 Autumn (golden maple, oak & rowan)",
    },
    "status_cached_updating": {
        "ru": "Данные из кэша (обновление...)",
        "uk": "Дані з кешу (оновлення...)",
        "en": "Cached data (updating...)",
    },
    "status_cached_offline": {
        "ru": "Данные из кэша (офлайн)",
        "uk": "Дані з кешу (офлайн)",
        "en": "Cached data (offline)",
    },
    "status_offline_era5": {
        "ru": "Офлайн-данные: климатическая норма ERA5 (нет сети)",
        "uk": "Офлайн-дані: кліматична норма ERA5 (немає мережі)",
        "en": "Offline data: ERA5 climate normals (no network)",
    },
    "unit_distance_km": {
        "ru": "км",
        "uk": "км",
        "en": "km",
    },
    "theme_group_landmark": {
        "ru": "Местная достопримечательность и погодные эффекты",
        "uk": "Місцева визначна пам'ятка та погодні ефекти",
        "en": "Local landmark & weather effects",
    },
    "theme_group_effects": {
        "ru": "Погодные эффекты",
        "uk": "Погодні ефекти",
        "en": "Weather effects",
    },
    "theme_landmark_enable": {
        "ru": "Использовать фото для фона (только дневная тема)",
        "uk": "Використовувати фото для фону (тільки денна тема)",
        "en": "Use photo as background (Day theme only)",
    },
    "theme_landmark_location": {
        "ru": "Локация (город):",
        "uk": "Локація (місто):",
        "en": "Location (city):",
    },
    "theme_landmark_location_all": {
        "ru": "По умолчанию (для всех городов)",
        "uk": "За замовчуванням (для всіх міст)",
        "en": "Default (for all cities)",
    },
    "theme_landmark_city_current": {
        "ru": "текущий",
        "uk": "поточний",
        "en": "current",
    },
    "theme_landmark_path_placeholder": {
        "ru": "Выберите изображение (по умолчанию — абстрактный голубой фон)",
        "uk": "Виберіть зображення (за замовчуванням — абстрактний блакитний фон)",
        "en": "Select image (default is abstract blue background)",
    },
    "theme_landmark_day_only_hint": {
        "ru": "Фон с картинкой действует только для дневной темы при выборе файла. Без картинки используется стандартный абстрактный голубой фон. Ночная тема остаётся тёмной.",
        "uk": "Фон із зображенням діє тільки для денної теми при виборі файлу. Без зображення використовується стандартний абстрактний блакитний фон. Нічна тема залишається темною.",
        "en": "Photo background applies only to the Day theme when an image file is selected. Without an image, standard abstract blue background is used. The Night theme remains dark.",
    },
    "theme_landmark_image": {
        "ru": "Изображение:",
        "uk": "Зображення:",
        "en": "Image:",
    },
    "theme_landmark_browse": {
        "ru": "Обзор…",
        "uk": "Огляд…",
        "en": "Browse…",
    },
    "theme_landmark_dimming": {
        "ru": "Затемнение / контраст:",
        "uk": "Затемнення / контраст:",
        "en": "Dimming / contrast:",
    },
    "theme_landmark_blur": {
        "ru": "Размытие (Blur):",
        "uk": "Розмиття (Blur):",
        "en": "Blur radius:",
    },
    "theme_landmark_effects": {
        "ru": "Живые погодные эффекты",
        "uk": "Живі погодні ефекти",
        "en": "Live weather effects",
    },
    "theme_landmark_test_effect": {
        "ru": "Погодные эффекты:",
        "uk": "Погодні ефекти:",
        "en": "Weather effects:",
    },
    "theme_landmark_effect_auto": {
        "ru": "Автоматически (по прогнозу)",
        "uk": "Автоматично (за прогнозом)",
        "en": "Automatic (from forecast)",
    },
    "theme_landmark_effect_rain": {
        "ru": "Дождь",
        "uk": "Дощ",
        "en": "Rain",
    },
    "theme_landmark_effect_drizzle": {
        "ru": "Изморось",
        "uk": "Мряка",
        "en": "Drizzle",
    },
    "theme_landmark_effect_snow": {
        "ru": "Снегопад",
        "uk": "Снігопад",
        "en": "Snow",
    },
    "theme_landmark_effect_blizzard": {
        "ru": "Метель",
        "uk": "Заметіль",
        "en": "Blizzard",
    },
    "theme_landmark_effect_sleet": {
        "ru": "Мокрый снег",
        "uk": "Мокрий сніг",
        "en": "Sleet",
    },
    "theme_landmark_effect_thunderstorm": {
        "ru": "Гроза",
        "uk": "Гроза",
        "en": "Thunderstorm",
    },
    "theme_landmark_effect_fog": {
        "ru": "Туман / Дымка",
        "uk": "Туман / Серпанок",
        "en": "Fog / Mist",
    },
    "theme_landmark_effect_sun_rays": {
        "ru": "Солнечные лучи",
        "uk": "Сонячні промені",
        "en": "Sun rays",
    },
    "theme_landmark_effect_clouds": {
        "ru": "Облачность",
        "uk": "Хмарність",
        "en": "Clouds",
    },
    "theme_landmark_effect_none": {
        "ru": "Отключить (None)",
        "uk": "Вимкнути (None)",
        "en": "None (Disabled)",
    },
    "theme_group_wind_rose": {
        "ru": "Роза ветров",
        "uk": "Роза вітрів",
        "en": "Wind rose",
    },
    "theme_wind_arrow_color": {
        "ru": "Цвет стрелки:",
        "uk": "Колір стрілки:",
        "en": "Arrow color:",
    },
    "theme_group_weekend": {
        "ru": "Выходные дни",
        "uk": "Вихідні дні",
        "en": "Weekend days",
    },
    "theme_weekend_days": {
        "ru": "Выходные дни:",
        "uk": "Вихідні дні:",
        "en": "Weekend days:",
    },
    "theme_weekend_color": {
        "ru": "Цвет выходных:",
        "uk": "Колір вихідних:",
        "en": "Weekend color:",
    },
    "btn_reset_default": {
        "ru": "Сбросить по умолчанию",
        "uk": "Скинути за замовчуванням",
        "en": "Reset to default",
    },
    "btn_choose_color": {
        "ru": "Выбрать цвет…",
        "uk": "Вибрати колір…",
        "en": "Choose color…",
    },
    # Layout Tab
    "layout_desc_title": {
        "ru": "Настройка блоков и 2D-смещения (X / Y)",
        "uk": "Налаштування блоків і 2D-зміщення (X / Y)",
        "en": "Block setup and 2D offset (X / Y)",
    },
    "layout_desc_sub": {
        "ru": "Переключайте блоки и настраивайте их точные координаты смещения по горизонтали и вертикали",
        "uk": "Вмикайте/вимикайте блоки та налаштовуйте їх точні координати зміщення",
        "en": "Toggle blocks and fine-tune their horizontal and vertical offset coordinates",
    },
    "layout_presets": {
        "ru": "Пресеты:",
        "uk": "Пресети:",
        "en": "Presets:",
    },
    "preset_standard": {
        "ru": "Стандартный",
        "uk": "Стандартний",
        "en": "Standard",
    },
    "preset_compact": {
        "ru": "Компактный",
        "uk": "Компактний",
        "en": "Compact",
    },
    "preset_full": {
        "ru": "Полный",
        "uk": "Повний",
        "en": "Full",
    },
    "layout_behavior_title": {
        "ru": "Поведение окна",
        "uk": "Поведінка вікна",
        "en": "Window behavior",
    },
    "layout_lock_position": {
        "ru": "Заблокировать позицию",
        "uk": "Заблокувати позицію",
        "en": "Lock position",
    },
    "layout_lock_position_desc": {
        "ru": "Запретить перетаскивание виджета мышью",
        "uk": "Заборонити перетягування віджета мишею",
        "en": "Prevent dragging the widget with the mouse",
    },
    "layout_on_all_desktops": {
        "ru": "На всех рабочих столах",
        "uk": "На всіх робочих столах",
        "en": "On all desktops",
    },
    "layout_on_all_desktops_desc": {
        "ru": "Показывать виджет на всех рабочих столах (X11 / KDE Plasma)",
        "uk": "Показувати віджет на всіх робочих столах (X11 / KDE Plasma)",
        "en": "Show the widget on all desktops (X11 / KDE Plasma)",
    },
    "layout_always_on_top": {
        "ru": "Поверх всех окон",
        "uk": "Поверх усіх вікон",
        "en": "Always on top",
    },
    "layout_always_on_top_desc": {
        "ru": "Держать виджет поверх остальных окон",
        "uk": "Тримати віджет поверх інших вікон",
        "en": "Keep the widget above other windows",
    },
    "layout_show_in_taskbar": {
        "ru": "Показывать на панели задач",
        "uk": "Показувати на панелі завдань",
        "en": "Show in taskbar",
    },
    "layout_show_in_taskbar_desc": {
        "ru": "Отображать виджет на панели задач и в списке окон. По умолчанию виджет работает как рабочий виджет без записи в панели задач",
        "uk": "Показувати віджет на панелі завдань і у списку вікон. За замовчуванням віджет працює без запису в панелі завдань",
        "en": "Show the widget in the taskbar and window list. By default it behaves like a desktop widget without a taskbar entry",
    },
    "blk_title_now": {
        "ru": "Текущая погода (Now)",
        "uk": "Поточна погода (Now)",
        "en": "Current weather (Now)",
    },
    "blk_title_wind": {
        "ru": "Роза ветров (Wind)",
        "uk": "Роза вітрів (Wind)",
        "en": "Wind compass (Wind)",
    },
    "blk_title_additional": {
        "ru": "Дополнительно (Info)",
        "uk": "Додатково (Info)",
        "en": "Additional info (Info)",
    },
    "blk_title_tomorrow": {
        "ru": "Завтра (ночь, утро, день, вечер)",
        "uk": "Завтра (ніч, ранок, день, вечір)",
        "en": "Tomorrow (night, morning, day, evening)",
    },
    "blk_title_today": {
        "ru": "Сегодня (ночь, утро, день, вечер)",
        "uk": "Сьогодні (ніч, ранок, день, вечір)",
        "en": "Today (night, morning, day, evening)",
    },
    "blk_title_astronomy": {
        "ru": "Астрономия (Солнце и Луна)",
        "uk": "Астрономія (Сонце та Місяць)",
        "en": "Astronomy (Sun & Moon)",
    },
    "blk_title_daily": {
        "ru": "Прогноз по дням (Daily)",
        "uk": "Прогноз по днях (Daily)",
        "en": "Daily forecast (Daily)",
    },
    "blk_toggle_show": {
        "ru": "Отображать блок",
        "uk": "Відображати блок",
        "en": "Display block",
    },
    "blk_always_on": {
        "ru": "Всегда включен",
        "uk": "Завжди увімкнено",
        "en": "Always enabled",
    },
    "offset_x": {
        "ru": "Смещение X:",
        "uk": "Зміщення X:",
        "en": "Offset X:",
    },
    "offset_y": {
        "ru": "Смещение Y:",
        "uk": "Зміщення Y:",
        "en": "Offset Y:",
    },
    "opt_wind_angle": {
        "ru": "Угол поворота стрелки (°):",
        "uk": "Кут повороту стрілки (°):",
        "en": "Arrow rotation angle (°):",
    },
    "opt_days_count": {
        "ru": "Количество дней:",
        "uk": "Кількість днів:",
        "en": "Number of days:",
    },
    "opt_daily_precip_prob": {
        "ru": "Осадки (%)",
        "uk": "Опади (%)",
        "en": "Precipitation (%)",
    },
    "opt_show_moon_phase": {
        "ru": "Показывать фазу Луны",
        "uk": "Показувати фазу Місяця",
        "en": "Show moon phase",
    },
    "opt_show_geomagnetic": {
        "ru": "Магнитное поле (Kp-индекс)",
        "uk": "Магнітне поле (Kp-індекс)",
        "en": "Magnetic field (Kp-index)",
    },
    # Units Tab
    "units_temp_title": {
        "ru": "Единица температуры",
        "uk": "Одиниця температури",
        "en": "Temperature unit",
    },
    "unit_celsius": {
        "ru": "Градусы Цельсия (°C)",
        "uk": "Градуси Цельсія (°C)",
        "en": "Degrees Celsius (°C)",
    },
    "unit_fahrenheit": {
        "ru": "Градусы Фаренгейта (°F)",
        "uk": "Градуси Фаренгейта (°F)",
        "en": "Degrees Fahrenheit (°F)",
    },
    "units_wind_title": {
        "ru": "Скорость ветра",
        "uk": "Швидкість вітру",
        "en": "Wind speed",
    },
    "unit_ms": {
        "ru": "Метры в секунду (м/с)",
        "uk": "Метри за секунду (м/с)",
        "en": "Meters per second (m/s)",
    },
    "unit_kmh": {
        "ru": "Километры в час (км/ч)",
        "uk": "Кілометри на годину (км/год)",
        "en": "Kilometers per hour (km/h)",
    },
    "unit_mph": {
        "ru": "Мили в час (миль/ч)",
        "uk": "Милі на годину (миль/год)",
        "en": "Miles per hour (mph)",
    },
    "unit_knots": {
        "ru": "Узлы (kn)",
        "uk": "Вузли (kn)",
        "en": "Knots (kn)",
    },
    "unit_beaufort": {
        "ru": "Шкала Бофорта (балл)",
        "uk": "Шкала Бофорта (бал)",
        "en": "Beaufort scale (Bft)",
    },
    "units_pressure_title": {
        "ru": "Атмосферное давление",
        "uk": "Атмосферний тиск",
        "en": "Atmospheric pressure",
    },
    "unit_mmhg": {
        "ru": "Миллиметры ртутного столба (мм рт. ст.)",
        "uk": "Міліметри ртутного стовпа (мм рт. ст.)",
        "en": "Millimeters of mercury (mmHg)",
    },
    "unit_hpa": {
        "ru": "Гектопаскали / Миллибары (гПа)",
        "uk": "Гектопаскалі / Мілібари (гПа)",
        "en": "Hectopascals / Millibars (hPa)",
    },
    "unit_inhg": {
        "ru": "Дюймы ртутного столба (inHg)",
        "uk": "Дюйми ртутного стовпа (inHg)",
        "en": "Inches of mercury (inHg)",
    },
    "units_date_format_title": {
        "ru": "Формат даты",
        "uk": "Формат дати",
        "en": "Date format",
    },
    "units_date_format_desc": {
        "ru": "Используется в шапке виджета и в прогнозе на несколько дней",
        "uk": "Використовується в шапці віджета та в прогнозі на кілька днів",
        "en": "Used in the widget header and multi-day forecast",
    },
    # Providers Tab
    "prov_source_title": {
        "ru": "Источник данных",
        "uk": "Джерело даних",
        "en": "Data source",
    },
    "prov_source_desc": {
        "ru": "«Консенсус» объединяет прогнозы нескольких сервисов для повышения точности. Можно также выбрать один конкретный провайдер.",
        "uk": "«Консенсус» об'єднує прогнози кількох служб для підвищення точності. Можна також вибрати окремого провайдера.",
        "en": "“Consensus” merges forecasts from multiple sources for higher accuracy. You can also pick a specific provider.",
    },
    "prov_model_title": {
        "ru": "Модель прогноза Open-Meteo",
        "uk": "Модель прогнозу Open-Meteo",
        "en": "Open-Meteo forecast model",
    },
    "prov_model_desc": {
        "ru": "Применяется только при использовании Open-Meteo. «Лучшая» автоматически выбирает оптимальную модель для вашего региона.",
        "uk": "Застосовується при використанні Open-Meteo. «Краща» автоматично вибирає оптимальну модель для вашого регіону.",
        "en": "Applies when Open-Meteo is used. “Best match” automatically selects the optimal model for your region.",
    },
    "model_best_match": {
        "ru": "Лучшая (автовыбор)",
        "uk": "Краща (автовибір)",
        "en": "Best match (auto)",
    },
    "prov_network_title": {
        "ru": "Сеть",
        "uk": "Мережа",
        "en": "Network",
    },
    "prov_network_desc": {
        "ru": "Таймауты, повторы и предпочтение IPv4. Изменения применяются сразу.",
        "uk": "Таймаути, повтори та перевага IPv4. Зміни застосовуються одразу.",
        "en": "Timeouts, retries, and IPv4 preference. Changes apply immediately.",
    },
    "opt_net_timeout": {
        "ru": "Таймаут запроса (сек):",
        "uk": "Таймаут запиту (сек):",
        "en": "Request timeout (sec):",
    },
    "opt_net_dns_timeout": {
        "ru": "Таймаут DNS (сек):",
        "uk": "Таймаут DNS (сек):",
        "en": "DNS timeout (sec):",
    },
    "opt_net_dns_hint": {
        "ru": "0 — отключить ограничение времени DNS",
        "uk": "0 — вимкнути обмеження часу DNS",
        "en": "0 disables the DNS time limit",
    },
    "opt_net_retries": {
        "ru": "Повторы при ошибке:",
        "uk": "Повтори при помилці:",
        "en": "Retries on error:",
    },
    "opt_net_fetch_timeout": {
        "ru": "Общий таймаут обновления (сек):",
        "uk": "Загальний таймаут оновлення (сек):",
        "en": "Overall update timeout (sec):",
    },
    "opt_net_prefer_ipv4": {
        "ru": "Сначала IPv4 (обход проблем с IPv6)",
        "uk": "Спочатку IPv4 (обхід проблем з IPv6)",
        "en": "Prefer IPv4 (works around broken IPv6)",
    },
    # Notifications Tab
    "notif_master": {
        "ru": "Включить всплывающие метео-уведомления",
        "uk": "Увімкнути спливаючі метео-сповіщення",
        "en": "Enable popup weather notifications",
    },
    "notif_types_title": {
        "ru": "Типы событий",
        "uk": "Типи подій",
        "en": "Event types",
    },
    "notif_rain_snow_1h": {
        "ru": "Начало осадков в ближайший час",
        "uk": "Початок опадів у найближчу годину",
        "en": "Precipitation starting within 1 hour",
    },
    "notif_frost": {
        "ru": "Заморозки (падение температуры ниже 0°C)",
        "uk": "Заморозки (зниження температури нижче 0°C)",
        "en": "Frost (temperature dropping below 0°C)",
    },
    "notif_strong_wind": {
        "ru": "Штормовой ветер (> 10 м/с)",
        "uk": "Штормовий вітер (> 10 м/с)",
        "en": "High winds (> 10 m/s)",
    },
    "notif_sharp_temperature_change": {
        "ru": "Резкое изменение температуры (> 5°C за 12ч)",
        "uk": "Різка зміна температури (> 5°C за 12г)",
        "en": "Sharp temperature shift (> 5°C in 12h)",
    },
    "notif_high_uv": {
        "ru": "Высокий уровень УФ-излучения (индекс ≥ 6)",
        "uk": "Високий рівень УФ-випромінювання (індекс ≥ 6)",
        "en": "High UV index (index ≥ 6)",
    },
    "notif_quiet_title": {
        "ru": "Режим «Не беспокоить» (тихие часы)",
        "uk": "Режим «Не турбувати» (тихі години)",
        "en": "Do Not Disturb (quiet hours)",
    },
    "notif_quiet_chk": {
        "ru": "Отключать уведомления ночью",
        "uk": "Вимкнути сповіщення вночі",
        "en": "Mute notifications at night",
    },
    # Context Menu & Tray
    "menu_detailed": {
        "ru": "Подробный прогноз…",
        "uk": "Докладний прогноз…",
        "en": "Detailed forecast…",
    },
    "menu_refresh": {
        "ru": "Обновить сейчас",
        "uk": "Оновити зараз",
        "en": "Refresh now",
    },
    # Detailed Forecast Dialog
    "detailed_title": {
        "ru": "Подробный прогноз — {city}",
        "uk": "Докладний прогноз — {city}",
        "en": "Detailed Forecast — {city}",
    },
    "switch_hourly_forecast": {
        "ru": "24ч Прогноз и давление",
        "uk": "24г Прогноз і тиск",
        "en": "24h Forecast & Barometer",
    },
    "switch_climate_norms": {
        "ru": "Климатические нормы (ERA5)",
        "uk": "Кліматичні норми (ERA5)",
        "en": "Climate Normals (ERA5)",
    },
    "switch_wind_rose": {
        "ru": "Роза ветров",
        "uk": "Роза вітрів",
        "en": "Wind Rose",
    },
    "switch_screen_hint": {
        "ru": "ЛКМ для переключения экранов (1/3 → 2/3 → 3/3)",
        "uk": "ЛКМ для перемикання екранів (1/3 → 2/3 → 3/3)",
        "en": "LMB to cycle screens (1/3 → 2/3 → 3/3)",
    },
    "wind_period_1h": {
        "ru": "1 час",
        "uk": "1 година",
        "en": "1 hour",
    },
    "wind_period_8h": {
        "ru": "8 часов",
        "uk": "8 годин",
        "en": "8 hours",
    },
    "wind_period_day": {
        "ru": "День",
        "uk": "День",
        "en": "Day",
    },
    "wind_period_night": {
        "ru": "Ночь",
        "uk": "Ніч",
        "en": "Night",
    },
    "wind_period_24h": {
        "ru": "24 часа",
        "uk": "24 години",
        "en": "24 hours",
    },
    "wind_gust_title": {
        "ru": "Порыв ветра",
        "uk": "Порив вітру",
        "en": "Wind Gust",
    },
    "wind_direction_title": {
        "ru": "Направление",
        "uk": "Напрямок",
        "en": "Direction",
    },
    "wind_beaufort_title": {
        "ru": "Шкала Бофорта",
        "uk": "Шкала Бофорта",
        "en": "Beaufort Scale",
    },
    "wind_prevailing_title": {
        "ru": "Преобладающий",
        "uk": "Переважний",
        "en": "Prevailing",
    },
    "wind_speed_scale_title": {
        "ru": "Скорость ветра",
        "uk": "Швидкість вітру",
        "en": "Wind Speed",
    },
    "wind_calm_label": {
        "ru": "Штиль",
        "uk": "Штиль",
        "en": "Calm",
    },
    "chart_hourly_spline_title": {
        "ru": "Температурный сплайн (24 ч)",
        "uk": "Температурний сплайн (24 год)",
        "en": "Temperature Spline (24h)",
    },
    "chart_daily_spline_title": {
        "ru": "Температура: день / ночь",
        "uk": "Температура: день / ніч",
        "en": "Temperature: Day / Night",
    },
    "chart_pressure_title": {
        "ru": "Барометрический график за сутки",
        "uk": "Барометричний графік за добу",
        "en": "24h Barometric Trend",
    },
    "chart_daily_pressure_title": {
        "ru": "Барометрический график",
        "uk": "Барометричний графік",
        "en": "Barometric Trend",
    },
    "forecast_tab_24h": {
        "ru": "24ч.",
        "uk": "24 год.",
        "en": "24h",
    },
    "forecast_legend_day": {
        "ru": "День",
        "uk": "День",
        "en": "Day",
    },
    "forecast_legend_night": {
        "ru": "Ночь",
        "uk": "Ніч",
        "en": "Night",
    },
    "barometer_current": {
        "ru": "Текущее давление:",
        "uk": "Поточний тиск:",
        "en": "Current pressure:",
    },
    "barometer_tendency": {
        "ru": "Барометрическая тенденция:",
        "uk": "Барометрична тенденція:",
        "en": "Barometric tendency:",
    },
    "pressure_tendency_rising": {
        "ru": "Растет ↗",
        "uk": "Зростає ↗",
        "en": "Rising ↗",
    },
    "pressure_tendency_falling": {
        "ru": "Падает ↘",
        "uk": "Падає ↘",
        "en": "Falling ↘",
    },
    "pressure_tendency_steady": {
        "ru": "Стабильно →",
        "uk": "Стабільно →",
        "en": "Steady →",
    },
    "pressure_tendency_desc_rising": {
        "ru": "к улучшению погоды и прояснению",
        "uk": "до покращення погоди та прояснення",
        "en": "towards clearing and fair weather",
    },
    "pressure_tendency_desc_falling": {
        "ru": "к усилению ветра или осадкам",
        "uk": "до посилення вітру або опадів",
        "en": "towards wind or precipitation",
    },
    "pressure_tendency_desc_steady": {
        "ru": "устойчивое состояние атмосферы",
        "uk": "стійкий стан атмосфери",
        "en": "stable atmospheric conditions",
    },
    "climate_card_title": {
        "ru": "Сравнение текущей погоды с 30-летней нормой Copernicus ERA5",
        "uk": "Порівняння поточної погоди з 30-річною нормою Copernicus ERA5",
        "en": "Current Weather vs Copernicus ERA5 30-Year Norm",
    },
    "climate_norm_range": {
        "ru": "Климатическая норма месяца: {min}°…{max}°",
        "uk": "Кліматична норма місяця: {min}°…{max}°",
        "en": "Monthly climate norm: {min}°…{max}°",
    },
    "climate_current_temp": {
        "ru": "Фактическая температура: {val}°",
        "uk": "Фактична температура: {val}°",
        "en": "Current temperature: {val}°",
    },
    "climate_anomaly_title": {
        "ru": "Аномалия температуры:",
        "uk": "Аномалія температури:",
        "en": "Temperature anomaly:",
    },
    "climate_above_norm": {
        "ru": "{val:+.1f}°C выше нормы",
        "uk": "{val:+.1f}°C вище норми",
        "en": "{val:+.1f}°C above normal",
    },
    "climate_below_norm": {
        "ru": "{val:+.1f}°C ниже нормы",
        "uk": "{val:+.1f}°C нижче норми",
        "en": "{val:+.1f}°C below normal",
    },
    "climate_near_norm": {
        "ru": "В пределах нормы (отклонение {val:+.1f}°C)",
        "uk": "В межах норми (відхилення {val:+.1f}°C)",
        "en": "Within normal range ({val:+.1f}°C)",
    },
    "climate_precip_norm": {
        "ru": "Норма осадков на месяц: {val} мм",
        "uk": "Норма опадів на місяць: {val} мм",
        "en": "Monthly precipitation norm: {val} mm",
    },
    "climate_annual_table_title": {
        "ru": "Годовой профиль климатических норм (12 месяцев)",
        "uk": "Річний профіль кліматичних норм (12 місяців)",
        "en": "Annual Climate Norm Profile (12 Months)",
    },
    "climate_attribution_label": {
        "ru": "Базовый период: 1991–2020 (глобальный климатический реанализ Copernicus C3S ERA5, сетка 0.25°)",
        "uk": "Базовий період: 1991–2020 (глобальний кліматичний реаналіз Copernicus C3S ERA5, сітка 0.25°)",
        "en": "Reference period: 1991–2020 (Copernicus C3S ERA5 global reanalysis, 0.25° grid)",
    },
    "menu_cities": {
        "ru": "Города…",
        "uk": "Міста…",
        "en": "Locations…",
    },
    "menu_locations": {
        "ru": "Города…",
        "uk": "Міста…",
        "en": "Locations…",
    },
    "locations_title": {
        "ru": "Управление городами — Info Weather",
        "uk": "Керування містами — Info Weather",
        "en": "Manage Locations — Info Weather",
    },
    "locations_search_title": {
        "ru": "Поиск нового города:",
        "uk": "Пошук нового міста:",
        "en": "Search new location:",
    },
    "locations_search_placeholder": {
        "ru": "Введите название города (например: Москва, Абакан, London)...",
        "uk": "Введіть назву міста (наприклад: Київ, Львів, London)...",
        "en": "Enter location name (e.g. London, New York)...",
    },
    "locations_saved_title": {
        "ru": "Сохранённые города:",
        "uk": "Збережені міста:",
        "en": "Saved locations:",
    },
    "locations_empty": {
        "ru": "Список пуст. Найдите и добавьте город выше.",
        "uk": "Список порожній. Знайдіть і додайте місто вище.",
        "en": "List is empty. Search and add a location above.",
    },
    "badge_home": {
        "ru": "[Домашний]",
        "uk": "[Домашній]",
        "en": "[Home]",
    },
    "badge_active": {
        "ru": "[Активный]",
        "uk": "[Активний]",
        "en": "[Active]",
    },
    "btn_select": {
        "ru": "Выбрать",
        "uk": "Вибрати",
        "en": "Select",
    },
    "btn_home": {
        "ru": "⌂ Домой",
        "uk": "⌂ Додому",
        "en": "⌂ Home",
    },
    "btn_add": {
        "ru": "+ Добавить",
        "uk": "+ Додати",
        "en": "+ Add",
    },
    "locations_not_found": {
        "ru": "Ничего не найдено",
        "uk": "Нічого не знайдено",
        "en": "Nothing found",
    },
    "tooltip_move_up": {
        "ru": "Переместить выше",
        "uk": "Перемістити вище",
        "en": "Move up",
    },
    "tooltip_move_down": {
        "ru": "Переместить ниже",
        "uk": "Перемістити нижче",
        "en": "Move down",
    },
    "tooltip_remove_city": {
        "ru": "Удалить из списка",
        "uk": "Видалити зі списку",
        "en": "Remove from list",
    },
    "menu_theme": {
        "ru": "Тема оформления",
        "uk": "Тема оформлення",
        "en": "Theme",
    },
    "theme_solar": {
        "ru": "По солнцу (авто)",
        "uk": "За сонцем (авто)",
        "en": "By solar cycle (auto)",
    },
    "theme_day": {
        "ru": "Дневная (светлая)",
        "uk": "Денна (світла)",
        "en": "Day (light)",
    },
    "theme_night": {
        "ru": "Ночная (тёмная)",
        "uk": "Нічна (темна)",
        "en": "Night (dark)",
    },
    "menu_settings": {
        "ru": "Настройки…",
        "uk": "Налаштування…",
        "en": "Settings…",
    },
    "menu_close": {
        "ru": "Закрыть",
        "uk": "Закрити",
        "en": "Close",
    },
    "tray_toggle": {
        "ru": "Показать / Скрыть виджет",
        "uk": "Показати / Сховати віджет",
        "en": "Show / Hide widget",
    },
    "tray_quit": {
        "ru": "Выход",
        "uk": "Вихід",
        "en": "Quit",
    },
}

MONTHS_SHORT = {
    "ru": ["янв.", "февр.", "март", "апр.", "май", "июнь", "июль", "авг.", "сент.", "окт.", "нояб.", "дек."],
    "uk": ["січ.", "лют.", "берез.", "квіт.", "трав.", "черв.", "лип.", "серп.", "верес.", "жовт.", "листоп.", "груд."],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}

MONTHS_FULL = {
    "ru": ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"],
    "uk": ["січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень", "вересень", "жовтень", "листопад", "грудень"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}

MONTHS_GENITIVE = {
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"],
    "uk": ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}

WEEKDAYS_SHORT = {
    "ru": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    "uk": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

WEEKDAYS_FULL = {
    "ru": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
    "uk": ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}


def detect_system_language() -> str:
    """Detect primary language code from environment or locale settings."""
    for env_var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(env_var)
        if val:
            code = val.split(".")[0].split("_")[0].lower()
            if code in SUPPORTED_LANGUAGES:
                return code
            if code.startswith("ru"):
                return "ru"
            if code.startswith("uk"):
                return "uk"
            if code.startswith("en"):
                return "en"
    try:
        loc = locale.getlocale()[0]
        if loc:
            code = loc.split(".")[0].split("_")[0].lower()
            if code in SUPPORTED_LANGUAGES:
                return code
            if code.startswith("ru"):
                return "ru"
            if code.startswith("uk"):
                return "uk"
            if code.startswith("en"):
                return "en"
    except Exception:
        pass
    return "ru"


def set_language(lang: str) -> None:
    """Set active language (falls back to 'ru' for unsupported codes)."""
    global _current_language
    if lang not in SUPPORTED_LANGUAGES:
        lang = "ru"
    _current_language = lang


def get_current_language() -> str:
    """Get active language code ('ru', 'uk' or 'en')."""
    return _current_language


def t(key: str, **kwargs: Any) -> str:
    """Translate key via BUILTIN_STRINGS and apply kwargs formatting."""
    lang = kwargs.pop("_lang", None) or _current_language
    entry = BUILTIN_STRINGS.get(key)
    if entry:
        text = entry.get(lang, entry.get("en", key))
        return text.format(**kwargs) if kwargs else text

    return key.format(**kwargs) if kwargs else key


def get_month_name(month_num: int, short: bool = False, genitive: bool = False, lang: str | None = None) -> str:
    """Get localized month name (1..12)."""
    lang = lang or _current_language
    idx = max(0, min(11, month_num - 1))
    if genitive:
        names = MONTHS_GENITIVE.get(lang, MONTHS_GENITIVE["en"])
    elif short:
        names = MONTHS_SHORT.get(lang, MONTHS_SHORT["en"])
    else:
        names = MONTHS_FULL.get(lang, MONTHS_FULL["en"])
    return names[idx]


def get_weekday_name(weekday_idx: int, short: bool = True, lang: str | None = None) -> str:
    """Get localized weekday name (0=Monday..6=Sunday)."""
    lang = lang or _current_language
    idx = weekday_idx % 7
    if short:
        names = WEEKDAYS_SHORT.get(lang, WEEKDAYS_SHORT["en"])
    else:
        names = WEEKDAYS_FULL.get(lang, WEEKDAYS_FULL["en"])
    return names[idx]


def format_day_month(day: int, month: int, lang: str | None = None) -> str:
    """Format day and month, e.g. '14 октября' or '14 October'."""
    m_name = get_month_name(month, genitive=True, lang=lang)
    return f"{day} {m_name}"


# Supported display formats for the "Date format" setting in the Units tab.
DATE_FORMAT_OPTIONS = (
    "DD.MM",
    "DD.MM.YYYY",
    "MM/DD/YYYY",
    "YYYY-MM-DD",
    "DD MMM",
)


def format_date_str(date_iso: str, fmt: str = "DD.MM", lang: str | None = None) -> str:
    """Format an ISO date string (YYYY-MM-DD) for display."""
    if not date_iso or len(date_iso) < 10:
        return ""
    try:
        dt = datetime.strptime(date_iso[:10], "%Y-%m-%d")
    except ValueError:
        return date_iso[5:].replace("-", ".") if len(date_iso) >= 10 else date_iso

    day, month, year = dt.day, dt.month, dt.year
    if fmt == "DD.MM.YYYY":
        return f"{day:02d}.{month:02d}.{year:04d}"
    if fmt == "MM/DD/YYYY":
        return f"{month:02d}/{day:02d}/{year:04d}"
    if fmt == "YYYY-MM-DD":
        return f"{year:04d}-{month:02d}-{day:02d}"
    if fmt == "DD MMM":
        month_name = get_month_name(month, short=True, lang=lang)
        return f"{day:02d} {month_name}"
    return f"{day:02d}.{month:02d}"


# Initialize with detected system language on import
set_language(detect_system_language())
