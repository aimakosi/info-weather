"""Qt imports for info-weather.

PySide6 is the single supported Qt binding. All UI code imports Qt names
through this module instead of importing PySide6 directly.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QBitmap,
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRegion,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFontComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# QtSvg is split into a separate package on some distros (e.g. Debian:
# python3-pyside6.qtsvg). SVG rendering degrades to None until it is installed.
QSvgRenderer = None
try:
    from PySide6.QtSvg import QSvgRenderer
except ImportError:
    QSvgRenderer = None

QT_API = "PySide6"

__all__ = [
    "QT_API",
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QObject",
    "QPoint",
    "QPointF",
    "QRectF",
    "Qt",
    "QTimer",
    "Signal",
    "QAction",
    "QBitmap",
    "QColor",
    "QFont",
    "QIcon",
    "QLinearGradient",
    "QMouseEvent",
    "QPainter",
    "QPainterPath",
    "QPen",
    "QPixmap",
    "QPolygonF",
    "QRegion",
    "QSvgRenderer",
    "QWheelEvent",
    "QApplication",
    "QCoreApplication",
    "QGuiApplication",
    "QCheckBox",
    "QColorDialog",
    "QComboBox",
    "QDialog",
    "QDoubleSpinBox",
    "QFontComboBox",
    "QFrame",
    "QGridLayout",
    "QGroupBox",
    "QHBoxLayout",
    "QLabel",
    "QLineEdit",
    "QMenu",
    "QPushButton",
    "QScrollArea",
    "QSizePolicy",
    "QSlider",
    "QSpinBox",
    "QStackedWidget",
    "QSystemTrayIcon",
    "QTabWidget",
    "QVBoxLayout",
    "QWidget",
]
