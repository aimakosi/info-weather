"""
Generate complete API fixture matrix for testing and consensus validation:
- open_meteo: best_match_normal, best_match_minimal, best_match_error
- met_norway: normal (copied from karaganda_normal), minimal, error
- wttr: normal (copied from karaganda_normal), minimal, error
"""

import json
import shutil
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "api"


def setup_fixtures():
    om_dir = FIXTURES_DIR / "open_meteo"
    met_dir = FIXTURES_DIR / "met_norway"
    wttr_dir = FIXTURES_DIR / "wttr"

    om_dir.mkdir(parents=True, exist_ok=True)
    met_dir.mkdir(parents=True, exist_ok=True)
    wttr_dir.mkdir(parents=True, exist_ok=True)

    # 1. Open-Meteo Normal
    om_normal = {
        "latitude": 49.8,
        "longitude": 73.1,
        "generationtime_ms": 0.45,
        "utc_offset_seconds": 18000,
        "timezone": "Asia/Almaty",
        "timezone_abbreviation": "+05",
        "elevation": 550.0,
        "current": {
            "time": "2026-10-14T15:00",
            "interval": 900,
            "temperature_2m": 11.2,
            "relative_humidity_2m": 62,
            "apparent_temperature": 9.8,
            "is_day": 1,
            "precipitation": 0.0,
            "weather_code": 3,
            "cloud_cover": 75,
            "pressure_msl": 1018.4,
            "surface_pressure": 954.2,
            "wind_speed_10m": 4.2,
            "wind_direction_10m": 240,
            "wind_gusts_10m": 7.8,
        },
        "hourly": {
            "time": [f"2026-10-14T{h:02d}:00" for h in range(24)],
            "temperature_2m": [6.5 + (h % 8) * 0.8 for h in range(24)],
            "relative_humidity_2m": [50 + (h % 30) for h in range(24)],
            "dew_point_2m": [1.2 + (h % 5) * 0.4 for h in range(24)],
            "apparent_temperature": [5.0 + (h % 8) * 0.8 for h in range(24)],
            "precipitation_probability": [10 if h < 12 else 45 for h in range(24)],
            "precipitation": [0.0 if h < 14 else 0.4 for h in range(24)],
            "weather_code": [2 if h < 14 else 61 for h in range(24)],
            "pressure_msl": [1018.0 - (h * 0.1) for h in range(24)],
            "surface_pressure": [954.0 - (h * 0.1) for h in range(24)],
            "visibility": [10000.0 for _ in range(24)],
            "cloud_cover": [40 + h * 2 for h in range(24)],
            "wind_speed_10m": [3.5 + (h % 4) * 0.5 for h in range(24)],
            "wind_direction_10m": [220 + (h * 3) for h in range(24)],
            "wind_gusts_10m": [6.0 + (h % 5) for h in range(24)],
            "uv_index": [0.0 if h < 7 or h > 18 else (h - 7) * 0.6 for h in range(24)],
            "is_day": [1 if 7 <= h <= 18 else 0 for h in range(24)],
        },
        "daily": {
            "time": [f"2026-10-{d:02d}" for d in range(14, 21)],
            "weather_code": [3, 61, 2, 1, 0, 3, 45],
            "temperature_2m_max": [14.0, 11.5, 9.0, 12.0, 15.2, 13.0, 10.0],
            "temperature_2m_min": [4.0, 2.5, -1.0, 1.0, 3.5, 4.0, 0.5],
            "apparent_temperature_max": [13.0, 10.0, 7.5, 11.0, 14.5, 12.0, 9.0],
            "apparent_temperature_min": [2.0, 0.5, -3.0, -1.0, 1.5, 2.0, -1.5],
            "sunrise": [f"2026-10-{d:02d}T06:45" for d in range(14, 21)],
            "sunset": [f"2026-10-{d:02d}T18:15" for d in range(14, 21)],
            "uv_index_max": [3.5, 2.1, 3.8, 4.0, 4.2, 3.1, 2.5],
            "precipitation_sum": [0.0, 3.2, 0.1, 0.0, 0.0, 0.8, 0.0],
            "precipitation_probability_max": [20, 85, 30, 10, 5, 40, 15],
            "wind_speed_10m_max": [6.2, 9.8, 5.1, 4.2, 5.5, 7.0, 4.0],
            "wind_gusts_10m_max": [10.5, 16.2, 9.0, 7.5, 9.8, 12.1, 7.0],
            "wind_direction_10m_dominant": [230, 270, 310, 200, 190, 240, 260],
        },
        "minutely_15": {
            "time": [f"2026-10-14T15:{m:02d}" for m in (0, 15, 30, 45)],
            "precipitation": [0.0, 0.0, 0.2, 0.5],
            "weather_code": [3, 3, 61, 61],
        },
    }
    with open(om_dir / "best_match_normal.json", "w", encoding="utf-8") as f:
        json.dump(om_normal, f, indent=2, ensure_ascii=False)

    # 2. Open-Meteo Minimal (без minutely_15, без UV, без видимости)
    om_minimal = {
        "latitude": 49.8,
        "longitude": 73.1,
        "current": {
            "time": "2026-10-14T15:00",
            "temperature_2m": 11.2,
            "relative_humidity_2m": 62,
            "weather_code": 3,
            "wind_speed_10m": 4.2,
            "wind_direction_10m": 240,
            "pressure_msl": 1018.4,
        },
        "daily": {
            "time": ["2026-10-14", "2026-10-15", "2026-10-16"],
            "weather_code": [3, 61, 2],
            "temperature_2m_max": [14.0, 11.5, 9.0],
            "temperature_2m_min": [4.0, 2.5, -1.0],
        },
    }
    with open(om_dir / "best_match_minimal.json", "w", encoding="utf-8") as f:
        json.dump(om_minimal, f, indent=2, ensure_ascii=False)

    # 3. Open-Meteo Error
    om_error = {"error": True, "reason": "Latitude must be in range of -90 to 90°. Given: 999.0."}
    with open(om_dir / "best_match_error.json", "w", encoding="utf-8") as f:
        json.dump(om_error, f, indent=2, ensure_ascii=False)

    # 4. MET Norway: создаем normal (копия из реального karaganda_normal), minimal, error
    if (met_dir / "karaganda_normal.json").exists():
        shutil.copy2(met_dir / "karaganda_normal.json", met_dir / "normal.json")

    met_minimal = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [73.1, 49.8, 550]},
        "properties": {
            "meta": {"updated_at": "2026-10-14T10:00:00Z"},
            "timeseries": [
                {
                    "time": "2026-10-14T12:00:00Z",
                    "data": {
                        "instant": {
                            "details": {
                                "air_pressure_at_sea_level": 1018.2,
                                "air_temperature": 11.0,
                                "relative_humidity": 65.0,
                                "wind_from_direction": 235.0,
                                "wind_speed": 4.0,
                            }
                        },
                        "next_1_hours": {"summary": {"symbol_code": "partlycloudy_day"}},
                    },
                }
            ],
        },
    }
    with open(met_dir / "minimal.json", "w", encoding="utf-8") as f:
        json.dump(met_minimal, f, indent=2, ensure_ascii=False)

    met_error = {"type": "error", "status": 400, "message": "Latitude must be between -90 and 90"}
    with open(met_dir / "error.json", "w", encoding="utf-8") as f:
        json.dump(met_error, f, indent=2, ensure_ascii=False)

    # 5. wttr.in: normal (копия из karaganda_normal), minimal, error
    if (wttr_dir / "karaganda_normal.json").exists():
        shutil.copy2(wttr_dir / "karaganda_normal.json", wttr_dir / "normal.json")

    wttr_minimal = {
        "current_condition": [
            {
                "temp_C": "11",
                "FeelsLikeC": "10",
                "humidity": "62",
                "pressure": "1018",
                "weatherCode": "116",
                "winddir16Point": "WSW",
                "windspeedKmph": "15",
            }
        ],
        "weather": [
            {
                "date": "2026-10-14",
                "maxtempC": "14",
                "mintempC": "4",
                "hourly": [
                    {
                        "time": "300",
                        "temp_C": "7",
                        "weatherCode": "116",
                        "chanceofrain": "10",
                    }
                ],
            }
        ],
    }
    with open(wttr_dir / "minimal.json", "w", encoding="utf-8") as f:
        json.dump(wttr_minimal, f, indent=2, ensure_ascii=False)

    wttr_error = {"error": "Unknown location"}
    with open(wttr_dir / "error.json", "w", encoding="utf-8") as f:
        json.dump(wttr_error, f, indent=2, ensure_ascii=False)

    print("Fixture matrix created successfully.")


if __name__ == "__main__":
    setup_fixtures()
