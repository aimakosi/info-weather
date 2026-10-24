"""PySide6 Preferences and Settings Dialog for info-weather."""

from __future__ import annotations

import copy
from typing import Any, Callable

from core.autostart import disable_autostart, enable_autostart, is_autostart_enabled
from core.config import DEFAULT_CONFIGURATION
from core.i18n import DATE_FORMAT_OPTIONS, format_date_str, set_language, t
from core.logging import get_logger
from ui.qt_compat import (
    QApplication,
    QCheckBox,
    QColor,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFont,
    QFontComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPixmap,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    Qt,
    QTabWidget,
    QtCore,
    QVBoxLayout,
    QWidget,
)
from ui.utils import discover_icon_themes, is_system_light_theme, set_current_icon_theme

logger = get_logger("ui.dialogs.settings")


class SettingsDialogQt(QDialog):
    """Preferences and settings dialog in Qt / KDE."""

    def __init__(
        self,
        parent: QWidget | None,
        config_manager: Any,
        on_config_changed: Callable[[], None] | None = None,
        parent_window: QWidget | None = None,
    ):
        super().__init__(parent or parent_window)
        self.config_manager = config_manager
        self.on_config_changed = on_config_changed
        self._parent_widget: QWidget | None = parent or parent_window
        self._tab_pages: list[tuple[QWidget, QWidget]] = []

        # Synchronize active i18n language with config before building UI
        app_lang = self.config_manager.get("app_language", "ru")
        set_language(app_lang)

        self.setWindowTitle(t("settings_title"))
        self.resize(580, 620)

        self._build_ui()
        self._apply_theme()
        self._connect_system_theme()

    def position_relative_to_widget(self, anchor_widget: QWidget | None = None) -> None:
        """Position settings dialog so it never overlaps or obscures the anchor widget window."""
        target = anchor_widget or self._parent_widget or self.parentWidget()
        if not target or not hasattr(target, "frameGeometry"):
            return

        widget_rect = target.frameGeometry()
        dialog_size = self.size()
        if dialog_size.width() <= 100 or dialog_size.height() <= 100:
            dialog_size = QtCore.QSize(580, 620)

        screen = target.screen() or self.screen() or QApplication.primaryScreen()
        screen_rect = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)

        margin = 12
        dw = dialog_size.width()
        dh = dialog_size.height()

        on_right_half = widget_rect.center().x() >= screen_rect.center().x()

        candidates: list[QtCore.QPoint] = []

        # 1. Horizontal placements (side-by-side preferred)
        left_x = widget_rect.left() - dw - margin
        left_y = max(screen_rect.top() + margin, min(widget_rect.top(), screen_rect.bottom() - dh - margin))

        right_x = widget_rect.right() + margin
        right_y = max(screen_rect.top() + margin, min(widget_rect.top(), screen_rect.bottom() - dh - margin))

        if on_right_half:
            candidates.append(QtCore.QPoint(left_x, left_y))
            candidates.append(QtCore.QPoint(right_x, right_y))
        else:
            candidates.append(QtCore.QPoint(right_x, right_y))
            candidates.append(QtCore.QPoint(left_x, left_y))

        # 2. Vertical placements (below or above)
        below_y = widget_rect.bottom() + margin
        below_x = max(screen_rect.left() + margin, min(widget_rect.left(), screen_rect.right() - dw - margin))
        candidates.append(QtCore.QPoint(below_x, below_y))

        above_y = widget_rect.top() - dh - margin
        above_x = max(screen_rect.left() + margin, min(widget_rect.left(), screen_rect.right() - dw - margin))
        candidates.append(QtCore.QPoint(above_x, above_y))

        target_pt: QtCore.QPoint | None = None

        # Priority 1: fully on screen AND no intersection
        for pt in candidates:
            r = QtCore.QRect(pt, dialog_size)
            if screen_rect.contains(r) and not r.intersects(widget_rect):
                target_pt = pt
                break

        # Priority 2: clamped to screen if it STILL does not intersect widget
        if target_pt is None:
            for pt in candidates:
                cx = max(screen_rect.left() + margin, min(pt.x(), screen_rect.right() - dw - margin))
                cy = max(screen_rect.top() + margin, min(pt.y(), screen_rect.bottom() - dh - margin))
                r = QtCore.QRect(cx, cy, dw, dh)
                if not r.intersects(widget_rect):
                    target_pt = QtCore.QPoint(cx, cy)
                    break

        # Priority 3: raw candidate that does not intersect widget (even if outside screen)
        if target_pt is None:
            for pt in candidates:
                r = QtCore.QRect(pt, dialog_size)
                if not r.intersects(widget_rect):
                    target_pt = pt
                    break

        # Fallback: candidate with minimum intersection area
        if target_pt is None:
            best_pt = candidates[0]
            min_overlap = float("inf")
            for pt in candidates:
                r = QtCore.QRect(pt, dialog_size)
                inter = r.intersected(widget_rect)
                area = inter.width() * inter.height() if not inter.isEmpty() else 0
                if area < min_overlap:
                    min_overlap = area
                    best_pt = pt
            target_pt = best_pt

        self.move(target_pt)

    def present(self) -> None:
        self.position_relative_to_widget()
        self.show()
        self.raise_()
        self.activateWindow()

    def _notify(self) -> None:
        if self.on_config_changed:
            self.on_config_changed()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("SettingsTabWidget")
        self._populate_tabs()
        main_layout.addWidget(self.tabs)

        # Bottom row
        self.btn_close = QPushButton(t("btn_close"))
        self.btn_close.setObjectName("BtnSettingsClose")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)
        main_layout.addWidget(self.btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _populate_tabs(self) -> None:
        while self.tabs.count() > 0:
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if w:
                w.deleteLater()
        self._tab_pages.clear()
        self.tabs.addTab(self._build_general_tab(), t("tab_general"))
        self.tabs.addTab(self._build_theme_tab(), t("tab_theme"))
        self.tabs.addTab(self._build_layout_tab(), t("tab_layout"))
        self.tabs.addTab(self._build_units_tab(), t("tab_units"))
        self.tabs.addTab(self._build_provider_tab(), t("tab_providers"))
        self.tabs.addTab(self._build_notifications_tab(), t("tab_notifications"))

    def retranslate_ui(self) -> None:
        curr_tab = self.tabs.currentIndex()
        self.setWindowTitle(t("settings_title"))
        if hasattr(self, "btn_close"):
            self.btn_close.setText(t("btn_close"))
        self._populate_tabs()
        if 0 <= curr_tab < self.tabs.count():
            self.tabs.setCurrentIndex(curr_tab)
        self._apply_theme()

    def _connect_system_theme(self) -> None:
        """Re-apply appearance when KDE/Qt system color scheme changes."""
        try:
            app = QApplication.instance()
            hints = app.styleHints() if app else None
            if hints is not None and hasattr(hints, "colorSchemeChanged"):
                hints.colorSchemeChanged.connect(self._on_system_theme_changed)
            if app is not None and hasattr(app, "paletteChanged"):
                app.paletteChanged.connect(self._on_system_theme_changed)
        except Exception as e:
            logger.debug("System color scheme signal unavailable: %s", e)

    def _on_system_theme_changed(self, *_args: Any) -> None:
        skin_cfg = self.config_manager.get("skin", {})
        if skin_cfg.get("theme_mode") == "auto_system":
            self._apply_theme()

    def _is_light_theme(self) -> bool:
        skin_cfg = self.config_manager.get("skin", {})
        theme_mode = skin_cfg.get("theme_mode", "auto_solar")
        if theme_mode == "day":
            return True
        if theme_mode == "night":
            return False
        if theme_mode == "auto_system":
            return is_system_light_theme()
        if theme_mode == "auto_solar":
            try:
                from core.astronomy import determine_solar_time_of_day
                # Theme only needs the local hour; use the active city when known
                city = self.config_manager.get("current_city") or self.config_manager.get("home_city")
                lat, lon = 55.75, 37.61
                for c in self.config_manager.get("cities", []) or []:
                    if isinstance(c, dict) and (c.get("name") == city or c.get("id") == city):
                        lat = float(c.get("lat", lat))
                        lon = float(c.get("lon", lon))
                        break
                return determine_solar_time_of_day(lat, lon)[0] == "day"
            except Exception:
                return False
        return False

    def _apply_theme(self) -> None:
        """Synchronize the appearance of all settings tabs with the current theme."""
        is_light = self._is_light_theme()
        theme_name = "light" if is_light else "dark"
        self.setProperty("theme", theme_name)
        self.tabs.setProperty("theme", theme_name)
        for scroll, container in self._tab_pages:
            scroll.setProperty("theme", theme_name)
            container.setProperty("theme", theme_name)
            # Descendant selectors depend on the container's dynamic property,
            # so children must be re-polished after a theme switch.
            for widget in [scroll, container, *container.findChildren(QWidget)]:
                widget.style().unpolish(widget)
                widget.style().polish(widget)

        self.style().unpolish(self)
        self.style().polish(self)
        self.tabs.style().unpolish(self.tabs)
        self.tabs.style().polish(self.tabs)
        if hasattr(self, "btn_close"):
            self.btn_close.style().unpolish(self.btn_close)
            self.btn_close.style().polish(self.btn_close)

    # -------------------------------------------------------------------------
    # Tab 1: Theme & Appearance
    # -------------------------------------------------------------------------
    @staticmethod
    def _skin_defaults() -> dict[str, Any]:
        return copy.deepcopy(DEFAULT_CONFIGURATION.get("skin", {}))

    @staticmethod
    def _format_defaults() -> dict[str, Any]:
        return copy.deepcopy(DEFAULT_CONFIGURATION.get("formats", {}))

    def _set_skin_value(self, key: str, value: Any) -> None:
        skin = dict(self.config_manager.get("skin", {}))
        if skin.get(key) == value:
            return
        skin[key] = value
        self.config_manager.set("skin", skin)
        self._notify()

    def _set_format_value(self, key: str, value: Any) -> None:
        formats = dict(self.config_manager.get("formats", {}))
        if formats.get(key) == value:
            return
        formats[key] = value
        self.config_manager.set("formats", formats)
        self._notify()

    def _set_landmark_value(self, key: str, value: Any) -> None:
        landmark = dict(self.config_manager.get("landmark", {}))
        if landmark.get(key) == value:
            return
        landmark[key] = value
        self.config_manager.set("landmark", landmark)
        self._notify()

    def _update_seasonal_preview(self, mode: str) -> None:
        if hasattr(self, "lbl_seasonal_preview"):
            from core.seasonal import resolve_seasonal_theme_image
            p = resolve_seasonal_theme_image(mode)
            if p and p.is_file():
                pix = QPixmap(str(p))
                if not pix.isNull():
                    scaled = pix.scaled(
                        210,
                        118,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.lbl_seasonal_preview.setPixmap(scaled)
                    return
            self.lbl_seasonal_preview.setPixmap(QPixmap())
            self.lbl_seasonal_preview.setText("—")

    def _set_network_value(self, key: str, value: Any) -> None:
        network = dict(self.config_manager.get("network", {}))
        if network.get(key) == value:
            return
        network[key] = value
        self.config_manager.set("network", network)
        self._notify()

    def _set_window_behavior_value(self, key: str, value: Any) -> None:
        behavior = dict(self.config_manager.get("window_behavior", {}))
        if behavior.get(key) == value:
            return
        behavior[key] = value
        self.config_manager.set("window_behavior", behavior)
        self._notify()

    def _make_reset_button(self, on_reset: Callable[[], None]) -> QPushButton:
        """Small per-row button restoring a single setting to its default."""
        btn = QPushButton("✕")
        btn.setToolTip(t("btn_reset_default"))
        btn.setFixedSize(26, 26)
        btn.setStyleSheet("padding: 0px;")
        btn.clicked.connect(on_reset)
        return btn

    def _add_setting_row(
        self,
        grid: QGridLayout,
        row: int,
        label_text: str,
        widget: QWidget,
        reset_slot: Callable[[], None] | None = None,
    ) -> None:
        grid.addWidget(QLabel(label_text), row, 0)
        grid.addWidget(widget, row, 1)
        if reset_slot is not None:
            grid.addWidget(self._make_reset_button(reset_slot), row, 2)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: Any) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    @staticmethod
    def _style_color_button(btn: QPushButton, color_hex: str) -> None:
        color = QColor(color_hex)
        if not color.isValid():
            color = QColor("#ef4444")
        lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
        text_color = "#0f172a" if lum > 150 else "#f8fafc"
        btn.setText(color.name())
        btn.setStyleSheet(
            "QPushButton {"
            f" background-color: {color.name()}; color: {text_color};"
            " border: 1px solid rgba(0, 0, 0, 0.35); border-radius: 6px;"
            " padding: 4px 8px; font-weight: bold;"
            "}"
        )

    def _set_weekend_color(self, color_hex: str) -> None:
        color = QColor(color_hex)
        if not color.isValid():
            return
        self._style_color_button(self.btn_weekend_color, color.name())
        self._set_skin_value("weekend_color", color.name())

    def _choose_weekend_color(self) -> None:
        skin = self.config_manager.get("skin", {})
        current = QColor(str(skin.get("weekend_color", "#ef4444")))
        if not current.isValid():
            current = QColor("#ef4444")
        color = QColorDialog.getColor(current, self, t("btn_choose_color"))
        if color.isValid():
            self._set_weekend_color(color.name())

    def _reset_weekend_color(self) -> None:
        self._set_weekend_color(str(self._skin_defaults().get("weekend_color", "#ef4444")))

    def _set_wind_color(self, color_hex: str) -> None:
        color = QColor(color_hex)
        if not color.isValid():
            return
        self._style_color_button(self.btn_wind_color, color.name())
        self._set_skin_value("wind_arrow_color", color.name())

    def _choose_wind_color(self) -> None:
        skin = self.config_manager.get("skin", {})
        current = QColor(str(skin.get("wind_arrow_color", "#ef4444")))
        if not current.isValid():
            current = QColor("#ef4444")
        color = QColorDialog.getColor(current, self, t("btn_choose_color"))
        if color.isValid():
            self._set_wind_color(color.name())

    def _reset_wind_color(self) -> None:
        self._set_wind_color(str(self._skin_defaults().get("wind_arrow_color", "#ef4444")))

    def _on_weekend_edited(self) -> None:
        self._set_format_value("weekend", self.edit_weekend.text().strip())

    def _reset_weekend(self) -> None:
        default = str(self._format_defaults().get("weekend", "Sa, Su"))
        self.edit_weekend.setText(default)
        self._set_format_value("weekend", default)

    @staticmethod
    def _font_family(font: QFont) -> str:
        """Return a clean family name (QFontComboBox may append a foundry)."""
        family = font.family().strip()
        if family.endswith("]") and " [" in family:
            family = family.rsplit(" [", 1)[0].strip()
        return family

    def _on_main_font_changed(self, font: QFont) -> None:
        self._set_skin_value("font_family", self._font_family(font))

    def _on_small_font_changed(self, font: QFont) -> None:
        self._set_skin_value("small_font_family", self._font_family(font))

    def _reset_main_font(self) -> None:
        default = str(self._skin_defaults().get("font_family", "Serif"))
        self.combo_font_main.setCurrentFont(QFont(default))
        self._set_skin_value("font_family", default)

    def _reset_small_font(self) -> None:
        default = str(self._skin_defaults().get("small_font_family", "Serif"))
        self.combo_font_small.setCurrentFont(QFont(default))
        self._set_skin_value("small_font_family", default)

    def _build_theme_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("TabScroll")
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("TabContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._tab_pages.append((scroll, container))
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        skin_cfg = self.config_manager.get("skin", {})
        formats_cfg = self.config_manager.get("formats", {})
        skin_defaults = self._skin_defaults()

        def _make_grid(group: QGroupBox) -> QGridLayout:
            grid = QGridLayout(group)
            grid.setContentsMargins(10, 8, 10, 8)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(6)
            grid.setColumnStretch(1, 1)
            return grid

        # 1. Display: icon theme, theme mode, launch mode
        grp_display = QGroupBox(t("theme_group_display"))
        grid = _make_grid(grp_display)

        self.combo_icons = QComboBox()
        available_themes = discover_icon_themes()
        curr_theme = skin_cfg.get("icons_name", "svg")
        theme_descriptions = {
            "svg": t("theme_icons_svg"),
            "Meteocons_monochrome": t("theme_icons_meteocons"),
            "WeatherIcons": "Weather Icons",
        }
        for idx, t_id in enumerate(available_themes):
            self.combo_icons.addItem(theme_descriptions.get(t_id, t_id), t_id)
            if t_id == curr_theme:
                self.combo_icons.setCurrentIndex(idx)

        def _on_icons_changed(index: int):
            theme_id = self.combo_icons.itemData(index)
            if theme_id:
                set_current_icon_theme(theme_id)
                self._set_skin_value("icons_name", theme_id)

        self.combo_icons.currentIndexChanged.connect(_on_icons_changed)
        self._add_setting_row(
            grid, 0, t("theme_icons_title"), self.combo_icons,
            lambda: self._set_combo_data(self.combo_icons, skin_defaults.get("icons_name", "svg")),
        )

        self.combo_mode = QComboBox()
        theme_modes = [
            ("auto_solar", t("theme_mode_solar")),
            ("day", t("theme_mode_day")),
            ("night", t("theme_mode_night")),
        ]
        curr_mode = skin_cfg.get("theme_mode", "auto_solar")
        if curr_mode not in ("auto_solar", "day", "night"):
            curr_mode = "auto_solar"
        for idx, (m_val, m_text) in enumerate(theme_modes):
            self.combo_mode.addItem(m_text, m_val)
            if m_val == curr_mode:
                self.combo_mode.setCurrentIndex(idx)

        def _on_mode_changed(index: int):
            val = self.combo_mode.itemData(index)
            if val:
                self._set_skin_value("theme_mode", val)
                self._apply_theme()

        self.combo_mode.currentIndexChanged.connect(_on_mode_changed)
        self._add_setting_row(
            grid, 1, t("theme_mode_title"), self.combo_mode,
            lambda: self._set_combo_data(self.combo_mode, skin_defaults.get("theme_mode", "auto_solar")),
        )

        self.combo_launch_mode = QComboBox()
        launch_modes = [
            ("both", t("launch_mode_both")),
            ("widget_only", t("launch_mode_widget_only")),
            ("indicator_only", t("launch_mode_indicator_only")),
        ]
        curr_launch_mode = self.config_manager.get("display_mode", "both")
        for idx, (m_val, m_text) in enumerate(launch_modes):
            self.combo_launch_mode.addItem(m_text, m_val)
            if m_val == curr_launch_mode:
                self.combo_launch_mode.setCurrentIndex(idx)

        def _on_launch_mode_changed(index: int):
            val = self.combo_launch_mode.itemData(index)
            if val:
                self.config_manager.set("display_mode", val)
                self._notify()

        self.combo_launch_mode.currentIndexChanged.connect(_on_launch_mode_changed)
        self.combo_launch_mode.setToolTip(t("theme_launch_mode_desc"))
        self._add_setting_row(
            grid, 2, t("theme_launch_mode_title"), self.combo_launch_mode,
            lambda: self._set_combo_data(self.combo_launch_mode, DEFAULT_CONFIGURATION.get("display_mode", "both")),
        )

        layout.addWidget(grp_display)

        # 2. Typography: main font and small (forecast) font
        grp_fonts = QGroupBox(t("theme_group_typography"))
        grid = _make_grid(grp_fonts)

        self.combo_font_main = QFontComboBox()
        self.combo_font_main.setCurrentFont(QFont(str(skin_cfg.get("font_family", "Serif"))))
        self.combo_font_main.currentFontChanged.connect(self._on_main_font_changed)
        self._add_setting_row(grid, 0, t("theme_font_main"), self.combo_font_main, self._reset_main_font)

        self.combo_font_small = QFontComboBox()
        self.combo_font_small.setCurrentFont(QFont(str(skin_cfg.get("small_font_family", "Serif"))))
        self.combo_font_small.currentFontChanged.connect(self._on_small_font_changed)
        self.combo_font_small.setToolTip(t("theme_font_small_desc"))
        self._add_setting_row(grid, 1, t("theme_font_small"), self.combo_font_small, self._reset_small_font)

        layout.addWidget(grp_fonts)

        # 3. Weekend: day-name color and weekend day definition
        grp_weekend = QGroupBox(t("theme_group_weekend"))
        grid = _make_grid(grp_weekend)

        self.btn_weekend_color = QPushButton()
        self.btn_weekend_color.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_weekend_color.clicked.connect(self._choose_weekend_color)
        self._style_color_button(self.btn_weekend_color, str(skin_cfg.get("weekend_color", "#ef4444")))
        self._add_setting_row(
            grid, 0, t("theme_weekend_color"), self.btn_weekend_color, self._reset_weekend_color,
        )

        self.edit_weekend = QLineEdit(str(formats_cfg.get("weekend", "Sa, Su") or "Sa, Su"))
        self.edit_weekend.setPlaceholderText("Sa, Su")
        self.edit_weekend.setToolTip(t("theme_weekend_hint"))
        self.edit_weekend.editingFinished.connect(self._on_weekend_edited)
        self._add_setting_row(grid, 1, t("theme_weekend_days"), self.edit_weekend, self._reset_weekend)

        layout.addWidget(grp_weekend)

        # 4. Wind rose: arrow color
        grp_wind = QGroupBox(t("theme_group_wind_rose"))
        grid = _make_grid(grp_wind)

        self.btn_wind_color = QPushButton()
        self.btn_wind_color.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wind_color.clicked.connect(self._choose_wind_color)
        self._style_color_button(
            self.btn_wind_color,
            str(skin_cfg.get("wind_arrow_color", "#ef4444")),
        )
        self._add_setting_row(
            grid, 0, t("theme_wind_arrow_color"), self.btn_wind_color, self._reset_wind_color,
        )

        layout.addWidget(grp_wind)

        # 5. Seasonal Themes: Floating card with natural seasonal decorations
        seasonal_cfg = self.config_manager.get("seasonal_theme", {})
        grp_seasonal = QGroupBox(t("theme_group_seasonal"))
        grid_seasonal = _make_grid(grp_seasonal)

        # Enable checkbox
        chk_seasonal_enable = QCheckBox(t("theme_seasonal_enable"))
        chk_seasonal_enable.setChecked(bool(seasonal_cfg.get("enabled", True)))

        def _on_seasonal_toggled(v: bool):
            cfg = dict(self.config_manager.get("seasonal_theme", {}))
            cfg["enabled"] = v
            self.config_manager.set("seasonal_theme", cfg)
            self._notify()

        chk_seasonal_enable.toggled.connect(_on_seasonal_toggled)
        self._add_setting_row(grid_seasonal, 0, "", chk_seasonal_enable, lambda: chk_seasonal_enable.setChecked(True))

        # Mode / Season selector
        self.combo_seasonal_mode = QComboBox()
        seasonal_modes = [
            ("auto", t("theme_seasonal_auto")),
            ("winter", t("theme_seasonal_winter")),
            ("spring", t("theme_seasonal_spring")),
            ("summer", t("theme_seasonal_summer")),
            ("autumn", t("theme_seasonal_autumn")),
        ]
        curr_mode = str(seasonal_cfg.get("mode", "auto"))
        for s_key, s_label in seasonal_modes:
            self.combo_seasonal_mode.addItem(s_label, s_key)
        self._set_combo_data(self.combo_seasonal_mode, curr_mode)

        def _on_seasonal_mode_changed(idx: int):
            val = self.combo_seasonal_mode.itemData(idx)
            if val:
                cfg = dict(self.config_manager.get("seasonal_theme", {}))
                cfg["mode"] = str(val)
                self.config_manager.set("seasonal_theme", cfg)
                self._update_seasonal_preview(str(val))
                self._notify()

        self.combo_seasonal_mode.currentIndexChanged.connect(_on_seasonal_mode_changed)
        self._add_setting_row(grid_seasonal, 1, t("theme_seasonal_mode"), self.combo_seasonal_mode, lambda: self._set_combo_data(self.combo_seasonal_mode, "auto"))

        # Thumbnail preview label
        self.lbl_seasonal_preview = QLabel()
        self.lbl_seasonal_preview.setFixedSize(220, 122)
        self.lbl_seasonal_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_seasonal_preview.setStyleSheet("border: 1px solid rgba(148, 163, 184, 0.35); border-radius: 8px; background: rgba(15, 23, 42, 0.40);")
        self._add_setting_row(grid_seasonal, 2, "", self.lbl_seasonal_preview, None)
        self._update_seasonal_preview(curr_mode)

        layout.addWidget(grp_seasonal)

        # 6. Dynamic weather particle effects (Rain, Snow, Thunderstorm, Fog, etc.)
        landmark_cfg = self.config_manager.get("landmark", {})
        grp_effects = QGroupBox(t("theme_group_effects"))
        grid_effects = _make_grid(grp_effects)

        # Weather effects selector (Automatic or None)
        self.combo_effect = QComboBox()
        effect_options = [
            ("auto", t("theme_landmark_effect_auto")),
            ("none", t("theme_landmark_effect_none")),
        ]
        curr_effect = str(landmark_cfg.get("active_effect", "auto"))
        if not landmark_cfg.get("weather_effects", True):
            curr_effect = "none"
        if curr_effect not in ("auto", "none"):
            curr_effect = "auto"
        for idx, (e_id, e_name) in enumerate(effect_options):
            self.combo_effect.addItem(e_name, e_id)
            if e_id == curr_effect:
                self.combo_effect.setCurrentIndex(idx)

        def _on_effect_changed(index: int):
            val = self.combo_effect.itemData(index)
            if val:
                self._set_landmark_value("active_effect", val)
                self._set_landmark_value("weather_effects", val != "none")

        def _reset_effect():
            self._set_combo_data(self.combo_effect, "auto")
            self._set_landmark_value("active_effect", "auto")
            self._set_landmark_value("weather_effects", True)

        self.combo_effect.currentIndexChanged.connect(_on_effect_changed)
        self._add_setting_row(
            grid_effects, 0, t("theme_landmark_test_effect"), self.combo_effect, _reset_effect
        )

        layout.addWidget(grp_effects)

        # 6. Geometry: scale and opacity
        grp_geometry = QGroupBox(t("theme_group_geometry"))
        grid = _make_grid(grp_geometry)

        curr_scale = float(skin_cfg.get("scale", 1.0))
        lbl_scale_val = QLabel(t("theme_scale_current", val=curr_scale))
        slider_scale = QSlider(Qt.Orientation.Horizontal)
        slider_scale.setRange(8, 15)  # 0.8 to 1.5
        slider_scale.setValue(int(curr_scale * 10))
        scale_row = QWidget()
        scale_row_l = QHBoxLayout(scale_row)
        scale_row_l.setContentsMargins(0, 0, 0, 0)
        scale_row_l.setSpacing(8)
        scale_row_l.addWidget(slider_scale, 1)
        scale_row_l.addWidget(lbl_scale_val)

        def _on_scale(v: int):
            val = round(v / 10.0, 1)
            lbl_scale_val.setText(t("theme_scale_current", val=val))
            self._set_skin_value("scale", val)

        slider_scale.valueChanged.connect(_on_scale)
        default_scale = float(skin_defaults.get("scale", 1.0))
        self._add_setting_row(
            grid, 0, t("theme_scale_title"), scale_row,
            lambda: slider_scale.setValue(int(default_scale * 10)),
        )

        curr_op = float(skin_cfg.get("opacity", 1.0))
        lbl_op_val = QLabel(t("theme_opacity_current", val=int(curr_op * 100)))
        slider_op = QSlider(Qt.Orientation.Horizontal)
        slider_op.setRange(30, 100)
        slider_op.setValue(int(curr_op * 100))
        op_row = QWidget()
        op_row_l = QHBoxLayout(op_row)
        op_row_l.setContentsMargins(0, 0, 0, 0)
        op_row_l.setSpacing(8)
        op_row_l.addWidget(slider_op, 1)
        op_row_l.addWidget(lbl_op_val)

        def _on_op(v: int):
            lbl_op_val.setText(t("theme_opacity_current", val=v))
            self._set_skin_value("opacity", round(v / 100.0, 2))

        slider_op.valueChanged.connect(_on_op)
        default_opacity = float(skin_defaults.get("opacity", 1.0))
        self._add_setting_row(
            grid, 1, t("theme_opacity_title"), op_row,
            lambda: slider_op.setValue(int(default_opacity * 100)),
        )

        layout.addWidget(grp_geometry)

        scroll.setWidget(container)
        return scroll

    # -------------------------------------------------------------------------
    # Tab 2: Layout / View (Вид & Смещение блоков X/Y)
    # -------------------------------------------------------------------------
    def _build_layout_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("TabScroll")
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("TabContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._tab_pages.append((scroll, container))
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        lbl_desc = QLabel(f"<b>{t('layout_desc_title')}</b><br>"
                          f"<span style='color: #64748b; font-size: 11px;'>{t('layout_desc_sub')}</span>")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        # Presets Buttons
        preset_box = QHBoxLayout()
        preset_box.addWidget(QLabel(t("layout_presets")))
        btn_std = QPushButton(t("preset_standard"))
        btn_std.clicked.connect(lambda: self._apply_layout_preset("standard"))
        preset_box.addWidget(btn_std)

        btn_compact = QPushButton(t("preset_compact"))
        btn_compact.clicked.connect(lambda: self._apply_layout_preset("compact"))
        preset_box.addWidget(btn_compact)

        btn_full = QPushButton(t("preset_full"))
        btn_full.clicked.connect(lambda: self._apply_layout_preset("full"))
        preset_box.addWidget(btn_full)
        layout.addLayout(preset_box)

        # Window behavior
        behavior_cfg = self.config_manager.get("window_behavior", {}) or {}
        grp_behavior = QGroupBox(t("layout_behavior_title"))
        l_behavior = QVBoxLayout(grp_behavior)
        l_behavior.setContentsMargins(10, 8, 10, 8)
        l_behavior.setSpacing(4)

        self.chk_lock_position = QCheckBox(t("layout_lock_position"))
        self.chk_lock_position.setToolTip(t("layout_lock_position_desc"))
        self.chk_lock_position.setChecked(bool(behavior_cfg.get("lock_position", False)))
        self.chk_lock_position.stateChanged.connect(
            lambda state: self._set_window_behavior_value(
                "lock_position", bool(state == Qt.CheckState.Checked.value)
            )
        )
        l_behavior.addWidget(self.chk_lock_position)

        self.chk_on_all_desktops = QCheckBox(t("layout_on_all_desktops"))
        self.chk_on_all_desktops.setToolTip(t("layout_on_all_desktops_desc"))
        self.chk_on_all_desktops.setChecked(bool(behavior_cfg.get("on_all_desktops", False)))
        self.chk_on_all_desktops.stateChanged.connect(
            lambda state: self._set_window_behavior_value(
                "on_all_desktops", bool(state == Qt.CheckState.Checked.value)
            )
        )
        l_behavior.addWidget(self.chk_on_all_desktops)

        self.chk_always_on_top = QCheckBox(t("layout_always_on_top"))
        self.chk_always_on_top.setToolTip(t("layout_always_on_top_desc"))
        self.chk_always_on_top.setChecked(bool(behavior_cfg.get("always_on_top", False)))
        self.chk_always_on_top.stateChanged.connect(
            lambda state: self._set_window_behavior_value(
                "always_on_top", bool(state == Qt.CheckState.Checked.value)
            )
        )
        l_behavior.addWidget(self.chk_always_on_top)

        self.chk_show_in_taskbar = QCheckBox(t("layout_show_in_taskbar"))
        self.chk_show_in_taskbar.setToolTip(t("layout_show_in_taskbar_desc"))
        self.chk_show_in_taskbar.setChecked(bool(behavior_cfg.get("show_in_taskbar", False)))
        self.chk_show_in_taskbar.stateChanged.connect(
            lambda state: self._set_window_behavior_value(
                "show_in_taskbar", bool(state == Qt.CheckState.Checked.value)
            )
        )
        l_behavior.addWidget(self.chk_show_in_taskbar)

        layout.addWidget(grp_behavior)

        # Individual Block Rows
        self._add_block_control(layout, t("blk_title_now"), "now", can_toggle=False)
        self._add_block_control(layout, t("blk_title_wind"), "wind", can_toggle=True, extra_type="wind")
        self._add_block_control(layout, t("blk_title_additional"), "additional_info", can_toggle=True)
        self._add_block_control(layout, t("blk_title_tomorrow"), "tomorrow", can_toggle=True)
        self._add_block_control(layout, t("blk_title_today"), "today", can_toggle=True)
        self._add_block_control(layout, t("blk_title_astronomy"), "astronomy", can_toggle=True, extra_type="astronomy")
        self._add_block_control(layout, t("blk_title_daily"), "daily", can_toggle=True, extra_type="daily")

        scroll.setWidget(container)
        return scroll

    def _add_block_control(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        block_key: str,
        can_toggle: bool = True,
        extra_type: str | None = None,
    ) -> None:
        view_cfg = dict(self.config_manager.get("view_blocks", {}))
        cfg = dict(view_cfg.get(block_key, {}))

        grp = QGroupBox(title)
        vbox = QVBoxLayout(grp)
        vbox.setContentsMargins(10, 8, 10, 8)
        vbox.setSpacing(6)

        # Toggle row
        top_row = QHBoxLayout()
        if can_toggle:
            chk_enabled = QCheckBox(t("blk_toggle_show"))
            chk_enabled.setChecked(bool(cfg.get("enabled", True)))

            def _on_toggle(state: int, k=block_key):
                v = dict(self.config_manager.get("view_blocks", {}))
                b = dict(v.get(k, {}))
                b["enabled"] = bool(state == Qt.CheckState.Checked.value)
                v[k] = b
                self.config_manager.set("view_blocks", v)
                self._notify()

            chk_enabled.stateChanged.connect(_on_toggle)
            top_row.addWidget(chk_enabled)
        else:
            top_row.addWidget(QLabel(t("blk_always_on")))

        top_row.addStretch(1)
        vbox.addLayout(top_row)

        # Offsets Row (X and Y)
        offset_row = QHBoxLayout()
        offset_row.addWidget(QLabel(t("offset_x")))
        spin_x = QSpinBox()
        spin_x.setRange(-400, 400)
        spin_x.setSingleStep(5)
        spin_x.setValue(int(cfg.get("offset_x", 0)))

        def _on_x(val: int, k=block_key):
            v = dict(self.config_manager.get("view_blocks", {}))
            b = dict(v.get(k, {}))
            b["offset_x"] = val
            v[k] = b
            self.config_manager.set("view_blocks", v)
            self._notify()

        spin_x.valueChanged.connect(_on_x)
        offset_row.addWidget(spin_x)

        offset_row.addWidget(QLabel(t("offset_y")))
        spin_y = QSpinBox()
        spin_y.setRange(-200, 200)
        spin_y.setSingleStep(5)
        spin_y.setValue(int(cfg.get("offset_y", 0)))

        def _on_y(val: int, k=block_key):
            v = dict(self.config_manager.get("view_blocks", {}))
            b = dict(v.get(k, {}))
            b["offset_y"] = val
            v[k] = b
            self.config_manager.set("view_blocks", v)
            self._notify()

        spin_y.valueChanged.connect(_on_y)
        offset_row.addWidget(spin_y)

        btn_reset = QPushButton("✕")
        btn_reset.setToolTip(t("btn_close"))
        btn_reset.setFixedWidth(28)
        btn_reset.clicked.connect(lambda: (spin_x.setValue(0), spin_y.setValue(0)))
        offset_row.addWidget(btn_reset)

        vbox.addLayout(offset_row)

        # Extra block specific controls
        if extra_type == "wind":
            wind_row = QHBoxLayout()
            wind_row.addWidget(QLabel(t("opt_wind_angle")))
            spin_ang = QSpinBox()
            spin_ang.setRange(-180, 180)
            spin_ang.setSingleStep(5)
            spin_ang.setValue(int(cfg.get("angle", 0)))

            def _on_ang(val: int):
                v = dict(self.config_manager.get("view_blocks", {}))
                b = dict(v.get("wind", {}))
                b["angle"] = val
                v["wind"] = b
                self.config_manager.set("view_blocks", v)
                self._notify()

            spin_ang.valueChanged.connect(_on_ang)
            wind_row.addWidget(spin_ang)
            wind_row.addStretch(1)
            vbox.addLayout(wind_row)

        elif extra_type == "daily":
            daily_row = QHBoxLayout()
            daily_row.addWidget(QLabel(t("opt_days_count")))
            spin_days = QSpinBox()
            spin_days.setRange(1, 5)
            spin_days.setValue(min(max(1, int(cfg.get("days", 5))), 5))

            def _on_days(val: int):
                v = dict(self.config_manager.get("view_blocks", {}))
                b = dict(v.get("daily", {}))
                b["days"] = val
                v["daily"] = b
                self.config_manager.set("view_blocks", v)
                self._notify()

            spin_days.valueChanged.connect(_on_days)
            daily_row.addWidget(spin_days)

            chk_rain = QCheckBox(t("opt_daily_precip_prob"))
            chk_rain.setChecked(bool(cfg.get("show_precip_prob", False)))

            def _on_rain(state: int):
                v = dict(self.config_manager.get("view_blocks", {}))
                b = dict(v.get("daily", {}))
                b["show_precip_prob"] = bool(state == Qt.CheckState.Checked.value)
                v["daily"] = b
                self.config_manager.set("view_blocks", v)
                self._notify()

            chk_rain.stateChanged.connect(_on_rain)
            daily_row.addWidget(chk_rain)

            vbox.addLayout(daily_row)

        elif extra_type == "astronomy":
            astro_row = QHBoxLayout()
            chk_moon = QCheckBox(t("opt_show_moon_phase"))
            chk_moon.setChecked(bool(cfg.get("show_moon", True)))

            def _on_moon(state: int):
                v = dict(self.config_manager.get("view_blocks", {}))
                b = dict(v.get("astronomy", {}))
                b["show_moon"] = bool(state == Qt.CheckState.Checked.value)
                v["astronomy"] = b
                self.config_manager.set("view_blocks", v)
                self._notify()

            chk_moon.stateChanged.connect(_on_moon)
            astro_row.addWidget(chk_moon)

            chk_geomag = QCheckBox(t("opt_show_geomagnetic"))
            chk_geomag.setChecked(bool(cfg.get("show_geomagnetic", True)))

            def _on_geomag(state: int):
                v = dict(self.config_manager.get("view_blocks", {}))
                b = dict(v.get("astronomy", {}))
                b["show_geomagnetic"] = bool(state == Qt.CheckState.Checked.value)
                v["astronomy"] = b
                self.config_manager.set("view_blocks", v)
                self._notify()

            chk_geomag.stateChanged.connect(_on_geomag)
            astro_row.addWidget(chk_geomag)
            astro_row.addStretch(1)
            vbox.addLayout(astro_row)

        parent_layout.addWidget(grp)

    def _apply_layout_preset(self, preset_name: str) -> None:
        view = copy.deepcopy(self.config_manager.get("view_blocks", {}))
        if preset_name == "compact":
            for k in view:
                view[k]["enabled"] = k in ("now", "today")
        elif preset_name == "full":
            for k in view:
                view[k]["enabled"] = True
        elif preset_name == "standard":
            for k in view:
                view[k]["enabled"] = k in ("now", "wind", "additional_info", "daily")

        if "daily" in view and isinstance(view["daily"], dict):
            view["daily"]["horizontal"] = True

        self.config_manager.set("view_blocks", view)
        self._notify()

    # -------------------------------------------------------------------------
    # Tab 3: Units
    # -------------------------------------------------------------------------
    def _build_units_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("TabScroll")
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("TabContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._tab_pages.append((scroll, container))
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        units = self.config_manager.get("units", {})

        # Temperature
        grp_t = QGroupBox(t("units_temp_title"))
        l_t = QVBoxLayout(grp_t)
        combo_t = QComboBox()
        t_opts = [("C", t("unit_celsius")), ("F", t("unit_fahrenheit"))]
        curr_t = units.get("temp", "C")
        for idx, (val, label) in enumerate(t_opts):
            combo_t.addItem(label, val)
            if val == curr_t:
                combo_t.setCurrentIndex(idx)

        def _on_temp(idx: int):
            u = dict(self.config_manager.get("units", {}))
            u["temp"] = combo_t.itemData(idx)
            self.config_manager.set("units", u)
            self._notify()

        combo_t.currentIndexChanged.connect(_on_temp)
        l_t.addWidget(combo_t)
        layout.addWidget(grp_t)

        # Wind
        grp_w = QGroupBox(t("units_wind_title"))
        l_w = QVBoxLayout(grp_w)
        combo_w = QComboBox()
        w_opts = [
            ("m/s", t("unit_ms")),
            ("km/h", t("unit_kmh")),
            ("mph", t("unit_mph")),
            ("kn", t("unit_knots")),
            ("beaufort", t("unit_beaufort")),
        ]
        curr_w = units.get("wind", "m/s")
        for idx, (val, label) in enumerate(w_opts):
            combo_w.addItem(label, val)
            if val == curr_w:
                combo_w.setCurrentIndex(idx)

        def _on_wind(idx: int):
            u = dict(self.config_manager.get("units", {}))
            u["wind"] = combo_w.itemData(idx)
            self.config_manager.set("units", u)
            self._notify()

        combo_w.currentIndexChanged.connect(_on_wind)
        l_w.addWidget(combo_w)
        layout.addWidget(grp_w)

        # Pressure
        grp_p = QGroupBox(t("units_pressure_title"))
        l_p = QVBoxLayout(grp_p)
        combo_p = QComboBox()
        p_opts = [
            ("mmHg", t("unit_mmhg")),
            ("hPa", t("unit_hpa")),
            ("inHg", t("unit_inhg")),
        ]
        curr_p = units.get("pressure", "mmHg")
        for idx, (val, label) in enumerate(p_opts):
            combo_p.addItem(label, val)
            if val == curr_p:
                combo_p.setCurrentIndex(idx)

        def _on_press(idx: int):
            u = dict(self.config_manager.get("units", {}))
            u["pressure"] = combo_p.itemData(idx)
            self.config_manager.set("units", u)
            self._notify()

        combo_p.currentIndexChanged.connect(_on_press)
        l_p.addWidget(combo_p)
        layout.addWidget(grp_p)

        # Date format
        grp_date = QGroupBox(t("units_date_format_title"))
        l_date = QVBoxLayout(grp_date)
        lbl_date_desc = QLabel(
            f"<span style='color: #64748b; font-size: 11px;'>{t('units_date_format_desc')}</span>"
        )
        lbl_date_desc.setWordWrap(True)
        l_date.addWidget(lbl_date_desc)

        self.combo_date_format = QComboBox()
        formats_cfg = self.config_manager.get("formats", {}) or {}
        curr_date_fmt = str(formats_cfg.get("date_format", "DD.MM") or "DD.MM")
        ui_lang = self.config_manager.get("app_language", "ru")
        if ui_lang not in ("ru", "uk", "en"):
            ui_lang = "ru"
        for idx, fmt_id in enumerate(DATE_FORMAT_OPTIONS):
            self.combo_date_format.addItem(
                format_date_str("2026-10-16", fmt_id, lang=ui_lang),
                fmt_id,
            )
            if fmt_id == curr_date_fmt:
                self.combo_date_format.setCurrentIndex(idx)

        def _on_date_format(idx: int):
            fmt_id = self.combo_date_format.itemData(idx)
            if fmt_id:
                self._set_format_value("date_format", fmt_id)

        self.combo_date_format.currentIndexChanged.connect(_on_date_format)
        l_date.addWidget(self.combo_date_format)
        layout.addWidget(grp_date)

        scroll.setWidget(container)
        return scroll

    # -------------------------------------------------------------------------
    # Tab 4: Providers / Data Source
    # -------------------------------------------------------------------------
    def _build_provider_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("TabScroll")
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("TabContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._tab_pages.append((scroll, container))
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Data Source selector
        grp_src = QGroupBox(t("prov_source_title"))
        l_src = QVBoxLayout(grp_src)

        lbl_src_desc = QLabel(
            f"<span style='color: #64748b; font-size: 11px;'>{t('prov_source_desc')}</span>"
        )
        lbl_src_desc.setWordWrap(True)
        l_src.addWidget(lbl_src_desc)

        combo_src = QComboBox()
        src_opts = [
            ("consensus", "Consensus (Open-Meteo + MET Norway + wttr.in)"),
            ("open_meteo", "Open-Meteo"),
            ("met_norway", "MET Norway"),
            ("wttr", "wttr.in"),
        ]
        curr_src = self.config_manager.get("data_source", "consensus")
        for idx, (val, label) in enumerate(src_opts):
            combo_src.addItem(label, val)
            if val == curr_src:
                combo_src.setCurrentIndex(idx)

        def _on_src_changed(idx: int):
            val = combo_src.itemData(idx)
            self.config_manager.set("data_source", val)
            self._notify()

        combo_src.currentIndexChanged.connect(_on_src_changed)
        l_src.addWidget(combo_src)
        layout.addWidget(grp_src)

        # Open-Meteo Model selector
        grp_model = QGroupBox(t("prov_model_title"))
        l_model = QVBoxLayout(grp_model)

        lbl_model_desc = QLabel(
            f"<span style='color: #64748b; font-size: 11px;'>{t('prov_model_desc')}</span>"
        )
        lbl_model_desc.setWordWrap(True)
        l_model.addWidget(lbl_model_desc)

        combo_model = QComboBox()
        model_opts = [
            ("best_match", t("model_best_match")),
            ("ecmwf_ifs025", "ECMWF IFS 0.25°"),
            ("gfs_seamless", "GFS Seamless (NOAA)"),
            ("icon_seamless", "ICON Seamless (DWD)"),
            ("gem_seamless", "GEM"),
            ("jma_seamless", "JMA"),
            ("meteofrance_seamless", "Météo-France"),
        ]
        curr_model = self.config_manager.get("open_meteo_model", "best_match")
        for idx, (val, label) in enumerate(model_opts):
            combo_model.addItem(label, val)
            if val == curr_model:
                combo_model.setCurrentIndex(idx)

        def _on_model_changed(idx: int):
            val = combo_model.itemData(idx)
            self.config_manager.set("open_meteo_model", val)
            self._notify()

        combo_model.currentIndexChanged.connect(_on_model_changed)
        l_model.addWidget(combo_model)
        layout.addWidget(grp_model)

        # Network transport settings
        grp_net = QGroupBox(t("prov_network_title"))
        grid = QGridLayout(grp_net)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)

        net_cfg = self.config_manager.get("network", {}) or {}
        net_defaults = copy.deepcopy(DEFAULT_CONFIGURATION.get("network", {}))

        def _net_num(key: str, default: float) -> float:
            try:
                return float(net_cfg.get(key, default))
            except (TypeError, ValueError):
                return default

        lbl_net_desc = QLabel(
            f"<span style='color: #64748b; font-size: 11px;'>{t('prov_network_desc')}</span>"
        )
        lbl_net_desc.setWordWrap(True)
        grid.addWidget(lbl_net_desc, 0, 0, 1, 3)

        self.spin_net_timeout = QDoubleSpinBox()
        self.spin_net_timeout.setRange(1.0, 60.0)
        self.spin_net_timeout.setDecimals(1)
        self.spin_net_timeout.setSingleStep(0.5)
        self.spin_net_timeout.setValue(_net_num("timeout_seconds", 8.0))
        self.spin_net_timeout.valueChanged.connect(
            lambda v: self._set_network_value("timeout_seconds", round(float(v), 1))
        )
        self._add_setting_row(
            grid, 1, t("opt_net_timeout"), self.spin_net_timeout,
            lambda: self.spin_net_timeout.setValue(float(net_defaults.get("timeout_seconds", 8.0))),
        )

        self.spin_net_dns = QDoubleSpinBox()
        self.spin_net_dns.setRange(0.0, 30.0)
        self.spin_net_dns.setDecimals(1)
        self.spin_net_dns.setSingleStep(0.5)
        self.spin_net_dns.setValue(_net_num("dns_timeout_seconds", 5.0))
        self.spin_net_dns.setToolTip(t("opt_net_dns_hint"))
        self.spin_net_dns.valueChanged.connect(
            lambda v: self._set_network_value("dns_timeout_seconds", round(float(v), 1))
        )
        self._add_setting_row(
            grid, 2, t("opt_net_dns_timeout"), self.spin_net_dns,
            lambda: self.spin_net_dns.setValue(float(net_defaults.get("dns_timeout_seconds", 5.0))),
        )

        self.spin_net_retries = QSpinBox()
        self.spin_net_retries.setRange(0, 5)
        self.spin_net_retries.setValue(int(_net_num("retries", 1)))
        self.spin_net_retries.valueChanged.connect(
            lambda v: self._set_network_value("retries", int(v))
        )
        self._add_setting_row(
            grid, 3, t("opt_net_retries"), self.spin_net_retries,
            lambda: self.spin_net_retries.setValue(int(net_defaults.get("retries", 1))),
        )

        self.spin_net_fetch = QDoubleSpinBox()
        self.spin_net_fetch.setRange(1.0, 300.0)
        self.spin_net_fetch.setDecimals(0)
        self.spin_net_fetch.setSingleStep(5.0)
        self.spin_net_fetch.setValue(_net_num("fetch_timeout_seconds", 30.0))
        self.spin_net_fetch.valueChanged.connect(
            lambda v: self._set_network_value("fetch_timeout_seconds", round(float(v), 1))
        )
        self._add_setting_row(
            grid, 4, t("opt_net_fetch_timeout"), self.spin_net_fetch,
            lambda: self.spin_net_fetch.setValue(float(net_defaults.get("fetch_timeout_seconds", 30.0))),
        )

        self.chk_prefer_ipv4 = QCheckBox(t("opt_net_prefer_ipv4"))
        self.chk_prefer_ipv4.setChecked(bool(net_cfg.get("prefer_ipv4", True)))
        self.chk_prefer_ipv4.stateChanged.connect(
            lambda state: self._set_network_value(
                "prefer_ipv4", bool(state == Qt.CheckState.Checked.value)
            )
        )
        grid.addWidget(self.chk_prefer_ipv4, 5, 0, 1, 2)
        grid.addWidget(
            self._make_reset_button(
                lambda: self.chk_prefer_ipv4.setChecked(
                    bool(net_defaults.get("prefer_ipv4", True))
                )
            ),
            5, 2,
        )
        layout.addWidget(grp_net)

        scroll.setWidget(container)
        return scroll

    # -------------------------------------------------------------------------
    # Tab 5: Notifications
    # -------------------------------------------------------------------------
    def _build_notifications_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("TabScroll")
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("TabContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._tab_pages.append((scroll, container))
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        notif_cfg = self.config_manager.get("notifications", {})

        chk_master = QCheckBox(t("notif_master"))
        chk_master.setChecked(bool(notif_cfg.get("enabled", True)))

        def _on_master(state: int):
            nc = dict(self.config_manager.get("notifications", {}))
            nc["enabled"] = bool(state == Qt.CheckState.Checked.value)
            self.config_manager.set("notifications", nc)
            self._notify()

        chk_master.stateChanged.connect(_on_master)
        layout.addWidget(chk_master)

        grp_types = QGroupBox(t("notif_types_title"))
        l_types = QVBoxLayout(grp_types)
        types_cfg = notif_cfg.get("types", {})
        ev_defs = [
            ("rain_snow_1h", t("notif_rain_snow_1h")),
            ("frost", t("notif_frost")),
            ("strong_wind", t("notif_strong_wind")),
            ("sharp_temperature_change", t("notif_sharp_temperature_change")),
            ("high_uv", t("notif_high_uv")),
        ]

        for k, label in ev_defs:
            chk = QCheckBox(label)
            chk.setChecked(bool(types_cfg.get(k, True)))

            def _on_ev(state: int, key=k):
                nc = dict(self.config_manager.get("notifications", {}))
                t_dict = dict(nc.get("types", {}))
                t_dict[key] = bool(state == Qt.CheckState.Checked.value)
                nc["types"] = t_dict
                self.config_manager.set("notifications", nc)
                self._notify()

            chk.stateChanged.connect(_on_ev)
            l_types.addWidget(chk)

        layout.addWidget(grp_types)

        grp_quiet = QGroupBox(t("notif_quiet_title"))
        l_quiet = QVBoxLayout(grp_quiet)
        quiet_cfg = notif_cfg.get("quiet_hours", {})
        chk_quiet = QCheckBox(t("notif_quiet_chk"))
        chk_quiet.setChecked(bool(quiet_cfg.get("enabled", False)))

        def _on_quiet(state: int):
            nc = dict(self.config_manager.get("notifications", {}))
            q_dict = dict(nc.get("quiet_hours", {}))
            q_dict["enabled"] = bool(state == Qt.CheckState.Checked.value)
            nc["quiet_hours"] = q_dict
            self.config_manager.set("notifications", nc)
            self._notify()

        chk_quiet.stateChanged.connect(_on_quiet)
        l_quiet.addWidget(chk_quiet)
        layout.addWidget(grp_quiet)

        scroll.setWidget(container)
        return scroll

    # -------------------------------------------------------------------------
    # Tab 6: General & Autostart
    # -------------------------------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("TabScroll")
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("TabContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._tab_pages.append((scroll, container))
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Language (Язык интерфейса и погоды)
        grp_lang = QGroupBox(t("opt_language"))
        l_lang = QVBoxLayout(grp_lang)
        lbl_lang_desc = QLabel(f"<span style='color: #64748b; font-size: 11px;'>{t('opt_language_desc')}</span>")
        lbl_lang_desc.setWordWrap(True)
        l_lang.addWidget(lbl_lang_desc)

        self.combo_language = QComboBox()
        self.combo_app_lang = self.combo_language  # compatibility alias
        self.combo_weather_lang = self.combo_language  # compatibility alias

        lang_opts = [
            ("en", "English"),
            ("uk", "Українська"),
            ("ru", "Русский"),
        ]
        curr_lang = self.config_manager.get("app_language", "ru")
        if curr_lang == "auto" or curr_lang not in ("ru", "uk", "en"):
            from core.i18n import get_current_language
            curr_lang = get_current_language()
            if curr_lang not in ("ru", "uk", "en"):
                curr_lang = "ru"

        target_idx = 2  # default to 'ru' if not found
        for idx, (code, title) in enumerate(lang_opts):
            self.combo_language.addItem(title, code)
            if code == curr_lang:
                target_idx = idx

        self.combo_language.setCurrentIndex(target_idx)

        def _on_lang_changed(idx: int):
            code = self.combo_language.itemData(idx)
            from core.i18n import get_current_language
            if code and (code != self.config_manager.get("app_language") or code != get_current_language()):
                self.config_manager.set("app_language", code)
                self.config_manager.set("weather_language", code)
                set_language(code)
                self.retranslate_ui()
                self._notify()

        self.combo_language.activated.connect(_on_lang_changed)
        self.combo_language.currentIndexChanged.connect(_on_lang_changed)
        l_lang.addWidget(self.combo_language)
        layout.addWidget(grp_lang)

        # 3. Autostart
        grp_auto = QGroupBox(t("opt_autostart"))
        l_auto = QVBoxLayout(grp_auto)
        chk_auto = QCheckBox(t("opt_autostart_chk"))
        chk_auto.setChecked(self.config_manager.get("autostart", False) or is_autostart_enabled())

        def _on_auto(state: int):
            val = bool(state == Qt.CheckState.Checked.value)
            self.config_manager.set("autostart", val)
            delay = self.config_manager.get("autostart_delay_sec", 0)
            if val:
                enable_autostart(delay_sec=delay)
            else:
                disable_autostart()
            self._notify()

        chk_auto.stateChanged.connect(_on_auto)
        l_auto.addWidget(chk_auto)
        layout.addWidget(grp_auto)

        # Update Interval
        grp_upd = QGroupBox(t("opt_update_interval"))
        l_upd = QVBoxLayout(grp_upd)
        combo_upd = QComboBox()
        int_opts = [
            (15, t("interval_15m")),
            (30, t("interval_30m")),
            (60, t("interval_60m")),
            (120, t("interval_120m")),
        ]
        curr_int = self.config_manager.get("update_interval_minutes", 60)
        for idx, (val, label) in enumerate(int_opts):
            combo_upd.addItem(label, val)
            if val == curr_int:
                combo_upd.setCurrentIndex(idx)

        def _on_int(idx: int):
            val = combo_upd.itemData(idx)
            self.config_manager.set("update_interval_minutes", val)
            self._notify()

        combo_upd.currentIndexChanged.connect(_on_int)
        l_upd.addWidget(combo_upd)
        layout.addWidget(grp_upd)

        scroll.setWidget(container)
        return scroll


SettingsDialog = SettingsDialogQt
