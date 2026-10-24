"""Unit tests for internationalization (i18n) engine."""

from __future__ import annotations

import unittest

from core.i18n import (
    DATE_FORMAT_OPTIONS,
    format_date_str,
    format_day_month,
    get_current_language,
    get_month_name,
    get_weekday_name,
    set_language,
    t,
)


class TestI18n(unittest.TestCase):
    def setUp(self):
        self._orig_lang = get_current_language()

    def tearDown(self):
        set_language(self._orig_lang)

    def test_default_language_is_ru(self):
        self.assertIn(get_current_language(), ("ru", "en"))

    def test_switch_language(self):
        set_language("en")
        self.assertEqual(get_current_language(), "en")
        self.assertEqual(t("weather_today"), "Today")

        set_language("ru")
        self.assertEqual(get_current_language(), "ru")
        self.assertEqual(t("weather_today"), "Сегодня")

    def test_explicit_lang_override_in_t(self):
        set_language("ru")
        # With _lang override
        self.assertEqual(t("weather_today", _lang="en"), "Today")
        self.assertEqual(t("weather_today", _lang="ru"), "Сегодня")

    def test_missing_translation_returns_key(self):
        self.assertEqual(t("non_existent_key_12345"), "non_existent_key_12345")

    def test_weekday_names_ru_and_en(self):
        # Monday is index 0
        self.assertEqual(get_weekday_name(0, short=False, lang="ru"), "Понедельник")
        self.assertEqual(get_weekday_name(0, short=True, lang="ru"), "Пн")
        self.assertEqual(get_weekday_name(0, short=False, lang="en"), "Monday")
        self.assertEqual(get_weekday_name(0, short=True, lang="en"), "Mon")

        # Sunday is index 6
        self.assertEqual(get_weekday_name(6, short=True, lang="ru"), "Вс")
        self.assertEqual(get_weekday_name(6, short=True, lang="en"), "Sun")

    def test_month_names_ru_and_en(self):
        self.assertEqual(get_month_name(1, lang="ru"), "январь")
        self.assertEqual(get_month_name(1, lang="en"), "January")
        self.assertEqual(get_month_name(12, lang="ru"), "декабрь")
        self.assertEqual(get_month_name(12, lang="en"), "December")

    def test_switch_language_uk(self):
        set_language("uk")
        self.assertEqual(get_current_language(), "uk")
        self.assertEqual(t("weather_today"), "Сьогодні")
        self.assertEqual(t("weather_wind"), "Вітер")

    def test_weekday_names_uk(self):
        self.assertEqual(get_weekday_name(0, short=False, lang="uk"), "Понеділок")
        self.assertEqual(get_weekday_name(0, short=True, lang="uk"), "Пн")
        self.assertEqual(get_weekday_name(4, short=True, lang="uk"), "Пт")
        self.assertEqual(get_weekday_name(6, short=True, lang="uk"), "Нд")

    def test_month_names_uk(self):
        self.assertEqual(get_month_name(1, lang="uk"), "січень")
        self.assertEqual(get_month_name(10, lang="uk"), "жовтень")
        self.assertEqual(format_day_month(15, 10, lang="uk"), "15 жовтня")

    def test_date_formats(self):
        self.assertEqual(len(DATE_FORMAT_OPTIONS), 5)
        self.assertEqual(format_date_str("2026-10-16", "DD.MM", lang="ru"), "16.10")
        self.assertEqual(format_date_str("2026-10-16", "DD.MM.YYYY", lang="ru"), "16.10.2026")
        self.assertEqual(format_date_str("2026-10-16", "MM/DD/YYYY", lang="ru"), "10/16/2026")
        self.assertEqual(format_date_str("2026-10-16", "YYYY-MM-DD", lang="ru"), "2026-10-16")
        self.assertEqual(format_date_str("2026-10-16", "DD MMM", lang="ru"), "16 окт.")
        self.assertEqual(format_date_str("2026-10-16", "DD MMM", lang="en"), "16 Oct")
        self.assertEqual(format_date_str("", "DD.MM"), "")
        self.assertEqual(format_date_str("bad", "DD.MM"), "")

    def test_date_format_title_translations(self):
        self.assertEqual(t("units_date_format_title", _lang="ru"), "Формат даты")
        self.assertEqual(t("units_date_format_title", _lang="uk"), "Формат дати")
        self.assertEqual(t("units_date_format_title", _lang="en"), "Date format")


if __name__ == "__main__":
    unittest.main()
