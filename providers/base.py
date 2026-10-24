"""Base interfaces and data structures for weather provider clients and search."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.http import CancellationToken


@dataclass
class CurrentPoint:
    """Normalized current meteorological observation."""
    temp: float
    weather_code: int
    is_day: int
    wind_speed: float
    wind_direction: float
    wind_gusts: float | None = None
    humidity: float | None = None
    pressure_msl: float | None = None
    precipitation: float | None = None
    dew_point: float | None = None
    uv_index: float | None = None
    visibility: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CurrentPoint:
        return cls(
            temp=float(data.get("temp", 0.0)),
            weather_code=int(data.get("weather_code", 0)),
            is_day=int(data.get("is_day", 1)),
            wind_speed=float(data.get("wind_speed", 0.0)),
            wind_direction=float(data.get("wind_direction", 0.0)),
            wind_gusts=float(data["wind_gusts"]) if data.get("wind_gusts") is not None else None,
            humidity=float(data["humidity"]) if data.get("humidity") is not None else None,
            pressure_msl=float(data["pressure_msl"]) if data.get("pressure_msl") is not None else None,
            precipitation=float(data["precipitation"]) if data.get("precipitation") is not None else None,
            dew_point=float(data["dew_point"]) if data.get("dew_point") is not None else None,
            uv_index=float(data["uv_index"]) if data.get("uv_index") is not None else None,
            visibility=float(data["visibility"]) if data.get("visibility") is not None else None,
        )


@dataclass
class HourlyPoint:
    """Normalized single-hour forecast point in UTC."""
    time_iso: str  # e.g. "2026-10-14T12:00:00Z"
    temp: float
    weather_code: int
    is_day: int
    wind_speed: float
    wind_direction: float
    wind_gusts: float | None = None
    humidity: float | None = None
    pressure_msl: float | None = None
    precipitation: float | None = None
    precipitation_probability: int | None = None
    dew_point: float | None = None
    uv_index: float | None = None
    visibility: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HourlyPoint:
        return cls(
            time_iso=str(data.get("time_iso", "")),
            temp=float(data.get("temp", 0.0)),
            weather_code=int(data.get("weather_code", 0)),
            is_day=int(data.get("is_day", 1)),
            wind_speed=float(data.get("wind_speed", 0.0)),
            wind_direction=float(data.get("wind_direction", 0.0)),
            wind_gusts=float(data["wind_gusts"]) if data.get("wind_gusts") is not None else None,
            humidity=float(data["humidity"]) if data.get("humidity") is not None else None,
            pressure_msl=float(data["pressure_msl"]) if data.get("pressure_msl") is not None else None,
            precipitation=float(data["precipitation"]) if data.get("precipitation") is not None else None,
            precipitation_probability=int(data["precipitation_probability"]) if data.get("precipitation_probability") is not None else None,
            dew_point=float(data["dew_point"]) if data.get("dew_point") is not None else None,
            uv_index=float(data["uv_index"]) if data.get("uv_index") is not None else None,
            visibility=float(data["visibility"]) if data.get("visibility") is not None else None,
        )


@dataclass
class DailySummary:
    """Normalized daily aggregate forecast for city calendar day."""
    date_str: str  # "YYYY-MM-DD"
    temp_min: float
    temp_max: float
    weather_code: int
    precipitation_sum: float | None = None
    precipitation_probability_max: int | None = None
    wind_speed_max: float | None = None
    wind_gusts_max: float | None = None
    wind_direction_dominant: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailySummary:
        return cls(
            date_str=str(data.get("date_str", "")),
            temp_min=float(data.get("temp_min", 0.0)),
            temp_max=float(data.get("temp_max", 0.0)),
            weather_code=int(data.get("weather_code", 0)),
            precipitation_sum=float(data["precipitation_sum"]) if data.get("precipitation_sum") is not None else None,
            precipitation_probability_max=int(data["precipitation_probability_max"]) if data.get("precipitation_probability_max") is not None else None,
            wind_speed_max=float(data["wind_speed_max"]) if data.get("wind_speed_max") is not None else None,
            wind_gusts_max=float(data["wind_gusts_max"]) if data.get("wind_gusts_max") is not None else None,
            wind_direction_dominant=float(data["wind_direction_dominant"]) if data.get("wind_direction_dominant") is not None else None,
        )


@dataclass
class SourceForecast:
    """Complete normalized forecast payload from a single provider."""
    source_name: str  # "open_meteo" | "met_norway" | "wttr"
    fetched_at: float  # epoch timestamp
    lat: float
    lon: float
    current: CurrentPoint
    hourly: list[HourlyPoint] = field(default_factory=list)
    daily: list[DailySummary] = field(default_factory=list)
    coverage: set[str] = field(default_factory=set)
    depth_days: int = 10
    is_basic_mode: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "fetched_at": self.fetched_at,
            "lat": self.lat,
            "lon": self.lon,
            "current": self.current.to_dict(),
            "hourly": [h.to_dict() for h in self.hourly],
            "daily": [d.to_dict() for d in self.daily],
            "coverage": list(self.coverage),
            "depth_days": self.depth_days,
            "is_basic_mode": self.is_basic_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceForecast:
        cur_raw = data.get("current", {})
        current = cur_raw if isinstance(cur_raw, CurrentPoint) else CurrentPoint.from_dict(cur_raw)
        hourly = [
            h if isinstance(h, HourlyPoint) else HourlyPoint.from_dict(h)
            for h in data.get("hourly", [])
        ]
        daily = [
            d if isinstance(d, DailySummary) else DailySummary.from_dict(d)
            for d in data.get("daily", [])
        ]
        return cls(
            source_name=str(data.get("source_name", "")),
            fetched_at=float(data.get("fetched_at", 0.0)),
            lat=float(data.get("lat", 0.0)),
            lon=float(data.get("lon", 0.0)),
            current=current,
            hourly=hourly,
            daily=daily,
            coverage=set(data.get("coverage", [])),
            depth_days=int(data.get("depth_days", 10)),
            is_basic_mode=bool(data.get("is_basic_mode", False)),
        )


@dataclass
class SearchResult:
    """Geocoding search result for city lookup."""
    name: str
    country: str
    lat: float
    lon: float
    timezone: str = "auto"
    elevation: float | None = None
    country_code: str = ""
    admin1: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchResult:
        return cls(
            name=str(data.get("name", "")),
            country=str(data.get("country", "")),
            lat=float(data.get("lat", 0.0)),
            lon=float(data.get("lon", 0.0)),
            timezone=str(data.get("timezone", "auto")),
            elevation=float(data["elevation"]) if data.get("elevation") is not None else None,
            country_code=str(data.get("country_code", "")),
            admin1=str(data.get("admin1", "")),
        )


class BaseWeatherClient(ABC):
    """Abstract base class for provider network clients."""

    name: str = "base"

    @abstractmethod
    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        cancel_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> SourceForecast | None:
        """Fetch and normalize weather forecast from external service."""
        pass

    @abstractmethod
    def normalize_response(
        self,
        raw_data: dict[str, Any],
        lat: float,
        lon: float,
        fetched_at: float | None = None,
    ) -> SourceForecast:
        """Parse and normalize raw JSON response to SourceForecast."""
        pass
