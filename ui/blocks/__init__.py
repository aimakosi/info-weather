"""PySide6 Blocks package for info-weather."""

from ui.blocks.additional_info_block import (
    AdditionalInfoBlock,
    AdditionalInfoBlockWidget,
    MetricsBlock,
)
from ui.blocks.astronomy_block import AstronomyBlock, AstronomyBlockWidget
from ui.blocks.daily_block import DailyBlock, DailyBlockWidget, HourlyBlock
from ui.blocks.day_periods_block import DayPeriodsBlock, DayPeriodsBlockWidget, TodayBlock
from ui.blocks.header_block import HeaderBlock, HeaderBlockWidget
from ui.blocks.wind_block import WindBlock, WindBlockWidget

__all__ = [
    "HeaderBlockWidget",
    "HeaderBlock",
    "DailyBlockWidget",
    "DailyBlock",
    "HourlyBlock",
    "WindBlockWidget",
    "WindBlock",
    "DayPeriodsBlockWidget",
    "DayPeriodsBlock",
    "TodayBlock",
    "AdditionalInfoBlockWidget",
    "AdditionalInfoBlock",
    "MetricsBlock",
    "AstronomyBlockWidget",
    "AstronomyBlock",
]
