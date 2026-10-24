"""PySide6 Dialog for searching and managing favorite weather cities."""

from __future__ import annotations

import threading
from typing import Any, Callable

from core.i18n import t
from core.logging import get_logger
from ui.qt_compat import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QObject,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)

logger = get_logger("ui.dialogs.city_search")


class SearchWorkerSignals(QObject):
    results_ready = Signal(str, list)


class CitySearchDialogQt(QDialog):
    """Dialog for searching and managing favorite weather cities."""

    def __init__(
        self,
        parent: QWidget | None,
        config_manager: Any,
        weather_provider: Any,
        on_city_changed: Callable[[dict[str, Any]], None] | None = None,
        parent_window: QWidget | None = None,
    ):
        super().__init__(parent or parent_window)
        self.setObjectName("CitySearchDialog")
        self.setWindowTitle(t("locations_title"))
        self.resize(540, 560)
        self.setMinimumWidth(480)

        self.config_manager = config_manager
        self.provider = weather_provider
        self.on_city_changed = on_city_changed

        self.signals = SearchWorkerSignals()
        self.signals.results_ready.connect(self._display_search_results)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._trigger_search)
        self._active_search_token: Any | None = None

        self._build_ui()
        self._apply_theme()
        self._refresh_cities_list()

    def present(self) -> None:
        self._apply_theme()
        self._refresh_cities_list()
        self.show()
        self.raise_()
        self.activateWindow()

    def showEvent(self, event: Any) -> None:
        self._apply_theme()
        self._refresh_cities_list()
        super().showEvent(event)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(12)

        # 1. Search Box
        self.lbl_search = QLabel(f"<b>{t('locations_search_title')}</b>")
        self.lbl_search.setObjectName("SearchSectionHeader")
        main_layout.addWidget(self.lbl_search)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("CitySearchEdit")
        self.search_edit.setPlaceholderText(t("locations_search_placeholder"))
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_edit.returnPressed.connect(self._trigger_search)
        main_layout.addWidget(self.search_edit)

        # Search Results Area
        self.results_scroll = QScrollArea()
        self.results_scroll.setObjectName("ResultsScrollArea")
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFixedHeight(150)
        self.results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_scroll.setVisible(False)

        self.results_container = QWidget()
        self.results_container.setObjectName("ResultsContainer")
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(6, 6, 6, 6)
        self.results_layout.setSpacing(6)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.results_scroll.setWidget(self.results_container)
        main_layout.addWidget(self.results_scroll)

        # Divider
        self.divider_line = QFrame()
        self.divider_line.setObjectName("DividerLine")
        self.divider_line.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(self.divider_line)

        # 2. Saved Cities Section
        self.lbl_saved = QLabel(f"<b>{t('locations_saved_title')}</b>")
        self.lbl_saved.setObjectName("SavedSectionHeader")
        main_layout.addWidget(self.lbl_saved)

        self.cities_scroll = QScrollArea()
        self.cities_scroll.setObjectName("CitiesScrollArea")
        self.cities_scroll.setWidgetResizable(True)
        self.cities_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cities_container = QWidget()
        self.cities_container.setObjectName("CitiesContainer")
        self.cities_layout = QVBoxLayout(self.cities_container)
        self.cities_layout.setContentsMargins(6, 6, 6, 6)
        self.cities_layout.setSpacing(6)
        self.cities_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cities_scroll.setWidget(self.cities_container)
        main_layout.addWidget(self.cities_scroll)

        # 3. Bottom Close Button
        self.btn_close = QPushButton(t("btn_close"))
        self.btn_close.setObjectName("BtnCloseDialog")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)
        main_layout.addWidget(self.btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def retranslate_ui(self) -> None:
        """Update localized UI text elements."""
        self.setWindowTitle(t("locations_title"))
        if hasattr(self, "lbl_search"):
            self.lbl_search.setText(f"<b>{t('locations_search_title')}</b>")
        if hasattr(self, "search_edit"):
            self.search_edit.setPlaceholderText(t("locations_search_placeholder"))
        if hasattr(self, "lbl_saved"):
            self.lbl_saved.setText(f"<b>{t('locations_saved_title')}</b>")
        if hasattr(self, "btn_close"):
            self.btn_close.setText(t("btn_close"))
        self._refresh_cities_list()

    def _is_light_theme(self) -> bool:
        if not self.config_manager:
            return False
        skin = self.config_manager.get("skin", {})
        mode = skin.get("theme_mode", "auto_solar")
        if mode == "day":
            return True
        if mode == "night":
            return False
        if mode == "auto_system":
            from ui.utils import is_system_light_theme
            return is_system_light_theme()
        if mode == "auto_solar":
            from core.astronomy import determine_solar_time_of_day
            cities = self.config_manager.get("cities", [])
            current_city = self.config_manager.get("current_city")
            lat, lon = 55.75, 37.61
            for c in cities:
                if isinstance(c, dict) and c.get("name") == current_city:
                    try:
                        lat = float(c.get("lat", lat))
                        lon = float(c.get("lon", lon))
                    except (ValueError, TypeError):
                        pass
                    break
            else:
                if cities and isinstance(cities[0], dict):
                    try:
                        lat = float(cities[0].get("lat", lat))
                        lon = float(cities[0].get("lon", lon))
                    except (ValueError, TypeError):
                        pass
            return determine_solar_time_of_day(lat, lon)[0] == "day"
        return False

    def _apply_theme(self) -> None:
        """Apply dark/night or light theme styles to the dialog and child elements."""
        is_light = self._is_light_theme()
        theme_name = "light" if is_light else "dark"
        self.setProperty("theme", theme_name)

        if is_light:
            bg_dlg = "#f8fafc"
            bg_card = "#ffffff"
            bg_card_hover = "#f1f5f9"
            bg_active = "rgba(16, 185, 129, 0.12)"
            border_card = "#cbd5e1"
            border_card_hover = "#0284c7"
            border_active = "#10b981"
            text_primary = "#0f172a"
            text_secondary = "#475569"
            text_header = "#0284c7"
            input_bg = "#ffffff"
            input_border = "#cbd5e1"
            input_focus = "#0284c7"
            divider = "rgba(0, 0, 0, 0.12)"
            scroll_border = "#cbd5e1"
            sb_handle = "rgba(0, 0, 0, 0.22)"
            sb_handle_hover = "rgba(2, 132, 199, 0.55)"
            btn_sec_bg = "#f1f5f9"
            btn_sec_border = "#cbd5e1"
            btn_sec_text = "#0f172a"
            btn_sec_hover_bg = "#e2e8f0"
            btn_sec_hover_border = "#0284c7"
            btn_home_bg = "rgba(2, 132, 199, 0.10)"
            btn_home_border = "rgba(2, 132, 199, 0.35)"
            btn_home_text = "#0284c7"
            btn_home_hover_bg = "rgba(2, 132, 199, 0.20)"
            btn_del_bg = "rgba(239, 68, 68, 0.08)"
            btn_del_border = "rgba(239, 68, 68, 0.30)"
            btn_del_text = "#dc2626"
            btn_del_hover_bg = "rgba(239, 68, 68, 0.18)"
            btn_pri_bg = "#0284c7"
            btn_pri_border = "#0284c7"
            btn_pri_hover_bg = "#0369a1"
        else:
            bg_dlg = "#0f172a"
            bg_card = "rgba(255, 255, 255, 0.05)"
            bg_card_hover = "rgba(255, 255, 255, 0.09)"
            bg_active = "rgba(16, 185, 129, 0.14)"
            border_card = "rgba(255, 255, 255, 0.10)"
            border_card_hover = "rgba(56, 189, 248, 0.40)"
            border_active = "rgba(16, 185, 129, 0.45)"
            text_primary = "#f8fafc"
            text_secondary = "#94a3b8"
            text_header = "#38bdf8"
            input_bg = "#1e293b"
            input_border = "rgba(255, 255, 255, 0.18)"
            input_focus = "#38bdf8"
            divider = "rgba(255, 255, 255, 0.15)"
            scroll_border = "rgba(255, 255, 255, 0.10)"
            sb_handle = "rgba(255, 255, 255, 0.22)"
            sb_handle_hover = "rgba(56, 189, 248, 0.55)"
            btn_sec_bg = "rgba(255, 255, 255, 0.08)"
            btn_sec_border = "rgba(255, 255, 255, 0.15)"
            btn_sec_text = "#f8fafc"
            btn_sec_hover_bg = "rgba(255, 255, 255, 0.16)"
            btn_sec_hover_border = "#38bdf8"
            btn_home_bg = "rgba(56, 189, 248, 0.12)"
            btn_home_border = "rgba(56, 189, 248, 0.35)"
            btn_home_text = "#38bdf8"
            btn_home_hover_bg = "rgba(56, 189, 248, 0.25)"
            btn_del_bg = "rgba(239, 68, 68, 0.12)"
            btn_del_border = "rgba(239, 68, 68, 0.30)"
            btn_del_text = "#f87171"
            btn_del_hover_bg = "rgba(239, 68, 68, 0.25)"
            btn_pri_bg = "#0284c7"
            btn_pri_border = "#38bdf8"
            btn_pri_hover_bg = "#0369a1"

        style_sheet = f"""
            QDialog#CitySearchDialog {{
                background-color: {bg_dlg};
                color: {text_primary};
            }}
            #CitySearchDialog QLabel#SearchSectionHeader,
            #CitySearchDialog QLabel#SavedSectionHeader {{
                color: {text_header};
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }}
            #CitySearchDialog QLineEdit#CitySearchEdit {{
                background-color: {input_bg};
                border: 1px solid {input_border};
                border-radius: 8px;
                padding: 7px 12px;
                color: {text_primary};
                font-size: 13px;
                selection-background-color: #0284c7;
            }}
            #CitySearchDialog QLineEdit#CitySearchEdit:focus {{
                border: 1px solid {input_focus};
                background-color: {input_bg};
            }}
            #CitySearchDialog QScrollArea#CitiesScrollArea,
            #CitySearchDialog QScrollArea#ResultsScrollArea {{
                background: transparent;
                background-color: transparent;
                border: 1px solid {scroll_border};
                border-radius: 8px;
            }}
            #CitySearchDialog QScrollArea#CitiesScrollArea > QWidget,
            #CitySearchDialog QScrollArea#ResultsScrollArea > QWidget,
            #CitySearchDialog QScrollArea#CitiesScrollArea > QWidget > QWidget,
            #CitySearchDialog QScrollArea#ResultsScrollArea > QWidget > QWidget,
            #CitySearchDialog QWidget#CitiesContainer,
            #CitySearchDialog QWidget#ResultsContainer {{
                background: transparent;
                background-color: transparent;
            }}
            #CitySearchDialog QFrame#DividerLine {{
                color: {divider};
                background-color: {divider};
                border: none;
                max-height: 1px;
            }}
            #CitySearchDialog QFrame#CityRow,
            #CitySearchDialog QFrame#CityResultRow {{
                background-color: {bg_card};
                border: 1px solid {border_card};
                border-radius: 8px;
            }}
            #CitySearchDialog QFrame#CityRow:hover,
            #CitySearchDialog QFrame#CityResultRow:hover {{
                background-color: {bg_card_hover};
                border-color: {border_card_hover};
            }}
            #CitySearchDialog QFrame#CityRow[active="true"] {{
                background-color: {bg_active};
                border: 1px solid {border_active};
            }}
            #CitySearchDialog QLabel#CityTitleLabel,
            #CitySearchDialog QLabel#ResultTitleLabel {{
                color: {text_primary};
                background: transparent;
            }}
            #CitySearchDialog QLabel#EmptyHint,
            #CitySearchDialog QLabel#NotFoundHint {{
                color: {text_secondary};
                background: transparent;
                font-style: italic;
                padding: 10px;
            }}
            #CitySearchDialog QPushButton#BtnSelectCity {{
                background-color: {btn_pri_bg};
                border: 1px solid {btn_pri_border};
                border-radius: 6px;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 4px 10px;
            }}
            #CitySearchDialog QPushButton#BtnSelectCity:hover {{
                background-color: {btn_pri_hover_bg};
            }}
            #CitySearchDialog QPushButton#BtnAddCity {{
                background-color: {btn_home_bg};
                border: 1px solid {btn_home_border};
                border-radius: 6px;
                color: {btn_home_text};
                font-weight: 600;
                font-size: 12px;
                padding: 4px 10px;
            }}
            #CitySearchDialog QPushButton#BtnAddCity:hover {{
                background-color: {btn_home_hover_bg};
                border-color: {btn_home_text};
            }}
            #CitySearchDialog QPushButton#BtnHomeCity {{
                background-color: {btn_home_bg};
                border: 1px solid {btn_home_border};
                border-radius: 6px;
                color: {btn_home_text};
                font-weight: 500;
                font-size: 12px;
                padding: 4px 10px;
            }}
            #CitySearchDialog QPushButton#BtnHomeCity:hover {{
                background-color: {btn_home_hover_bg};
                border-color: {btn_home_text};
            }}
            #CitySearchDialog QPushButton#BtnUpCity,
            #CitySearchDialog QPushButton#BtnDownCity {{
                background-color: {btn_sec_bg};
                border: 1px solid {btn_sec_border};
                border-radius: 6px;
                color: {btn_sec_text};
                font-size: 10px;
                font-weight: bold;
                padding: 2px;
            }}
            #CitySearchDialog QPushButton#BtnUpCity:hover,
            #CitySearchDialog QPushButton#BtnDownCity:hover {{
                background-color: {btn_sec_hover_bg};
                border-color: {btn_sec_hover_border};
            }}
            #CitySearchDialog QPushButton#BtnDelCity {{
                background-color: {btn_del_bg};
                border: 1px solid {btn_del_border};
                border-radius: 6px;
                color: {btn_del_text};
                font-weight: bold;
                font-size: 12px;
                padding: 2px;
            }}
            #CitySearchDialog QPushButton#BtnDelCity:hover {{
                background-color: {btn_del_hover_bg};
                border-color: #ef4444;
            }}
            #CitySearchDialog QPushButton#BtnCloseDialog {{
                background-color: {btn_sec_bg};
                border: 1px solid {btn_sec_border};
                border-radius: 6px;
                color: {btn_sec_text};
                font-weight: 600;
                padding: 6px 20px;
            }}
            #CitySearchDialog QPushButton#BtnCloseDialog:hover {{
                background-color: {btn_sec_hover_bg};
                border-color: {btn_sec_hover_border};
            }}
            #CitySearchDialog QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 8px;
                margin: 2px 0 2px 0;
            }}
            #CitySearchDialog QScrollBar::handle:vertical {{
                background: {sb_handle};
                min-height: 24px;
                border-radius: 4px;
            }}
            #CitySearchDialog QScrollBar::handle:vertical:hover {{
                background: {sb_handle_hover};
            }}
            #CitySearchDialog QScrollBar::add-line:vertical,
            #CitySearchDialog QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            #CitySearchDialog QScrollBar::add-page:vertical,
            #CitySearchDialog QScrollBar::sub-page:vertical {{
                background: none;
            }}
            #CitySearchDialog QScrollBar:horizontal {{
                height: 0px;
                border: none;
            }}
        """
        self.setStyleSheet(style_sheet)
        if hasattr(self, "cities_scroll") and self.cities_scroll.viewport():
            self.cities_scroll.viewport().setObjectName("CitiesScrollViewport")
            self.cities_scroll.viewport().setStyleSheet("QWidget#CitiesScrollViewport { background: transparent; }")
        if hasattr(self, "results_scroll") and self.results_scroll.viewport():
            self.results_scroll.viewport().setObjectName("ResultsScrollViewport")
            self.results_scroll.viewport().setStyleSheet("QWidget#ResultsScrollViewport { background: transparent; }")

        self.style().unpolish(self)
        self.style().polish(self)

    def closeEvent(self, event: Any) -> None:
        if self._active_search_token is not None:
            self._active_search_token.cancel()
        super().closeEvent(event)

    def _on_search_text_changed(self, text: str) -> None:
        query = text.strip()
        if len(query) < 2:
            if self._active_search_token is not None:
                self._active_search_token.cancel()
            self.results_scroll.setVisible(False)
            self._debounce_timer.stop()
            return
        self._debounce_timer.start(350)

    def _trigger_search(self) -> None:
        query = self.search_edit.text().strip()
        if len(query) < 2:
            return

        # Cancel any previous in-flight city search
        if self._active_search_token is not None:
            self._active_search_token.cancel()

        from core.http import CancellationToken
        token = CancellationToken()
        self._active_search_token = token

        def _worker(cancel_tok: CancellationToken):
            try:
                results = self.provider.search_cities(query, cancel_token=cancel_tok, limit=5)
                if not cancel_tok.is_cancelled:
                    self.signals.results_ready.emit(query, results)
            except InterruptedError:
                logger.debug("City search for '%s' cancelled", query)
            except Exception as e:
                if not cancel_tok.is_cancelled:
                    logger.warning("Error searching cities: %s", e)

        threading.Thread(target=_worker, args=(token,), daemon=True).start()

    def _display_search_results(self, query: str, results: list[Any]) -> None:
        # Drop stale results: the user may have typed on since this search started
        if query != self.search_edit.text().strip():
            return

        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not results:
            lbl = QLabel(t("locations_not_found"))
            lbl.setObjectName("NotFoundHint")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_layout.addWidget(lbl)
            self.results_scroll.setVisible(True)
            return

        is_light = self._is_light_theme()
        coord_color = "#64748b" if is_light else "#94a3b8"

        for res in results:
            row = QFrame()
            row.setObjectName("CityResultRow")
            h_layout = QHBoxLayout(row)
            h_layout.setContentsMargins(8, 6, 8, 6)
            h_layout.setSpacing(8)

            loc_info = f"{res.name}"
            if getattr(res, "country", None):
                loc_info += f", {res.country}"
            if getattr(res, "admin1", None):
                loc_info += f" ({res.admin1})"
            coord_str = f"({res.lat:.2f}, {res.lon:.2f})"

            lbl = QLabel(f"<b>{loc_info}</b> <small style='color: {coord_color};'>{coord_str}</small>")
            lbl.setObjectName("ResultTitleLabel")
            lbl.setWordWrap(True)
            lbl.setMinimumWidth(0)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            h_layout.addWidget(lbl, stretch=1)

            city_dict = {
                "name": res.name,
                "lat": res.lat,
                "lon": res.lon,
                "country": getattr(res, "country", "") or "",
                "admin1": getattr(res, "admin1", "") or "",
                "timezone": getattr(res, "timezone", "auto") or "auto",
            }

            btn_add = QPushButton(t("btn_add"))
            btn_add.setObjectName("BtnAddCity")
            btn_add.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_add.clicked.connect(lambda checked=False, c=city_dict: self._add_city(c))
            h_layout.addWidget(btn_add)

            btn_sel = QPushButton(t("btn_select"))
            btn_sel.setObjectName("BtnSelectCity")
            btn_sel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn_sel.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_sel.clicked.connect(lambda checked=False, c=city_dict: self._select_city_direct(c))
            h_layout.addWidget(btn_sel)

            self.results_layout.addWidget(row)

        self.results_scroll.setVisible(True)

    def _add_city(self, city_dict: dict[str, Any]) -> None:
        cities = list(self.config_manager.get("cities", []))
        for existing in cities:
            if abs(existing.get("lat", 0) - city_dict["lat"]) < 0.05 and abs(existing.get("lon", 0) - city_dict["lon"]) < 0.05:
                return

        cities.append(city_dict)
        self.config_manager.set("cities", cities)
        if not self.config_manager.get("current_city"):
            self.config_manager.set("current_city", city_dict["name"])
        if not self.config_manager.get("home_city"):
            self.config_manager.set("home_city", city_dict["name"])

        self._refresh_cities_list()

    def _select_city_direct(self, city_dict: dict[str, Any]) -> None:
        self._add_city(city_dict)
        self._set_active_city(city_dict, close_dialog=True)

    def _refresh_cities_list(self) -> None:
        while self.cities_layout.count():
            item = self.cities_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cities = list(self.config_manager.get("cities", [])) if self.config_manager else []
        home_city = self.config_manager.get("home_city", "") if self.config_manager else ""
        current_city = self.config_manager.get("current_city", "") if self.config_manager else ""
        is_light = self._is_light_theme()

        if not cities:
            lbl = QLabel(t("locations_empty"))
            lbl.setObjectName("EmptyHint")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cities_layout.addWidget(lbl)
            return

        badge_home_color = "#0284c7" if is_light else "#38bdf8"
        badge_active_color = "#059669" if is_light else "#10b981"
        badge_home_bg = "rgba(2, 132, 199, 0.12)" if is_light else "rgba(56, 189, 248, 0.15)"
        badge_active_bg = "rgba(5, 150, 105, 0.12)" if is_light else "rgba(16, 185, 129, 0.15)"

        for idx, c in enumerate(cities):
            row = QFrame()
            row.setObjectName("CityRow")
            c_name = c.get("name", "Unknown")
            c_lat = c.get("lat")
            c_lon = c.get("lon")
            c_country = c.get("country", "")

            from data.resources import localize_city
            curr_lang = self.config_manager.get("weather_language") or self.config_manager.get("app_language", "ru") if self.config_manager else "ru"
            loc_name, loc_country = localize_city(
                name=c_name,
                lat=c_lat,
                lon=c_lon,
                country=c_country,
                lang=curr_lang,
            )

            is_active = (c_name == current_city)
            if not is_active and c_lat is not None and c_lon is not None and self.provider:
                try:
                    active_info = self.provider.get_active_city_info()
                    if abs(float(active_info.get("lat", 0.0)) - float(c_lat)) < 0.15 and abs(float(active_info.get("lon", 0.0)) - float(c_lon)) < 0.15:
                        is_active = True
                except Exception:
                    pass

            if is_active:
                row.setProperty("active", "true")

            h_layout = QHBoxLayout(row)
            h_layout.setContentsMargins(10, 8, 10, 8)
            h_layout.setSpacing(8)

            badges = []
            if c.get("name") == home_city:
                badges.append(
                    f"<span style='color: {badge_home_color}; background-color: {badge_home_bg}; "
                    f"padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;'>"
                    f"{t('badge_home')}</span>"
                )
            if is_active:
                badges.append(
                    f"<span style='color: {badge_active_color}; background-color: {badge_active_bg}; "
                    f"padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;'>"
                    f"{t('badge_active')}</span>"
                )

            loc = loc_name
            if loc_country:
                loc += f", {loc_country}"

            badge_str = " " + " ".join(badges) if badges else ""
            lbl = QLabel(f"<b>{loc}</b>{badge_str}")
            lbl.setObjectName("CityTitleLabel")
            lbl.setWordWrap(True)
            lbl.setMinimumWidth(0)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            h_layout.addWidget(lbl, stretch=1)

            if not is_active:
                btn_act = QPushButton(t("btn_select"))
                btn_act.setObjectName("BtnSelectCity")
                btn_act.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_act.clicked.connect(lambda checked=False, city=c: self._set_active_city(city, close_dialog=True))
                h_layout.addWidget(btn_act)

            if c.get("name") != home_city:
                btn_home = QPushButton(t("btn_home"))
                btn_home.setObjectName("BtnHomeCity")
                btn_home.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_home.clicked.connect(lambda checked=False, city=c: self._set_home_city(city))
                h_layout.addWidget(btn_home)

            if len(cities) > 1:
                if idx > 0:
                    btn_up = QPushButton("▲")
                    btn_up.setObjectName("BtnUpCity")
                    btn_up.setToolTip(t("tooltip_move_up"))
                    btn_up.setFixedSize(28, 28)
                    btn_up.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_up.clicked.connect(lambda checked=False, i=idx: self._move_city(i, -1))
                    h_layout.addWidget(btn_up)
                else:
                    spacer_up = QWidget()
                    spacer_up.setObjectName("SpacerUpCity")
                    spacer_up.setFixedSize(28, 28)
                    h_layout.addWidget(spacer_up)

                if idx < len(cities) - 1:
                    btn_down = QPushButton("▼")
                    btn_down.setObjectName("BtnDownCity")
                    btn_down.setToolTip(t("tooltip_move_down"))
                    btn_down.setFixedSize(28, 28)
                    btn_down.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_down.clicked.connect(lambda checked=False, i=idx: self._move_city(i, 1))
                    h_layout.addWidget(btn_down)
                else:
                    spacer_down = QWidget()
                    spacer_down.setObjectName("SpacerDownCity")
                    spacer_down.setFixedSize(28, 28)
                    h_layout.addWidget(spacer_down)

            btn_del = QPushButton("✕")
            btn_del.setObjectName("BtnDelCity")
            btn_del.setToolTip(t("tooltip_remove_city"))
            btn_del.setFixedSize(28, 28)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.clicked.connect(lambda checked=False, i=idx: self._remove_city(i))
            h_layout.addWidget(btn_del)

            self.cities_layout.addWidget(row)

    def _set_active_city(self, city: dict[str, Any], close_dialog: bool = True) -> None:
        self.config_manager.set("current_city", city.get("name", ""))
        self._refresh_cities_list()
        if self.on_city_changed:
            self.on_city_changed(city)
        if close_dialog:
            self.accept()

    def _set_home_city(self, city: dict[str, Any]) -> None:
        self.config_manager.set("home_city", city.get("name", ""))
        self._refresh_cities_list()

    def _move_city(self, index: int, delta: int) -> None:
        cities = list(self.config_manager.get("cities", []))
        new_idx = index + delta
        if 0 <= new_idx < len(cities):
            cities[index], cities[new_idx] = cities[new_idx], cities[index]
            self.config_manager.set("cities", cities)
            self._refresh_cities_list()

    def _remove_city(self, index: int) -> None:
        cities = list(self.config_manager.get("cities", []))
        if 0 <= index < len(cities):
            removed = cities.pop(index)
            self.config_manager.set("cities", cities)
            if self.config_manager.get("current_city") == removed.get("name"):
                if cities:
                    self.config_manager.set("current_city", cities[0]["name"])
                    if self.on_city_changed:
                        self.on_city_changed(cities[0])
                else:
                    self.config_manager.set("current_city", "")
            self._refresh_cities_list()


CitySearchDialog = CitySearchDialogQt
