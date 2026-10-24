#!/usr/bin/env python3
"""
Fetch real API fixtures for Open-Meteo, MET Norway, and wttr.in.
Saves responses to tests/fixtures/api/ for offline testing and coverage validation.
"""

import json
import logging
import time
from pathlib import Path

from core.http import HttpClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fetch_fixtures")

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "api"

CITIES = {
    "karaganda": {"lat": 49.8028, "lon": 73.1025, "altitude": 550, "name": "Karaganda"},
    "oslo": {"lat": 59.9139, "lon": 10.7522, "altitude": 20, "name": "Oslo"},
}


def fetch_open_meteo(client: HttpClient, city_key: str, coords: dict) -> None:
    dest_dir = FIXTURES_DIR / "open_meteo"
    dest_dir.mkdir(parents=True, exist_ok=True)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "is_day",
            "precipitation",
            "weather_code",
            "cloud_cover",
            "pressure_msl",
            "surface_pressure",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
        ],
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "dew_point_2m",
            "apparent_temperature",
            "precipitation_probability",
            "precipitation",
            "weather_code",
            "pressure_msl",
            "surface_pressure",
            "visibility",
            "cloud_cover",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "uv_index",
            "is_day",
        ],
        "daily": [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "sunrise",
            "sunset",
            "uv_index_max",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "wind_direction_10m_dominant",
        ],
        "timezone": "auto",
        "forecast_days": 10,
    }

    try:
        logger.info("Fetching Open-Meteo for %s...", city_key)
        data = client.fetch_json(url, params=params, retries=2)
        target = dest_dir / f"{city_key}_normal.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Saved %s", target)
    except Exception as e:
        logger.error("Failed Open-Meteo (%s): %s", city_key, e)


def fetch_met_norway(client: HttpClient, city_key: str, coords: dict) -> None:
    dest_dir = FIXTURES_DIR / "met_norway"
    dest_dir.mkdir(parents=True, exist_ok=True)

    url = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
    params = {
        "lat": coords["lat"],
        "lon": coords["lon"],
        "altitude": coords["altitude"],
    }
    # MET Norway strictly requires unique UA with project or contact email
    headers = {"User-Agent": "info-weather-project/0.1.0 github.com/aimakosi/info-weather contact:aimakosi@users.noreply.github.com"}

    try:
        logger.info("Fetching MET Norway for %s...", city_key)
        data = client.fetch_json(url, params=params, extra_headers=headers, retries=2)
        target = dest_dir / f"{city_key}_normal.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Saved %s", target)
    except Exception as e:
        logger.error("Failed MET Norway (%s): %s", city_key, e)


def fetch_wttr(client: HttpClient, city_key: str, coords: dict) -> None:
    dest_dir = FIXTURES_DIR / "wttr"
    dest_dir.mkdir(parents=True, exist_ok=True)

    city_name = coords["name"]
    url = f"https://wttr.in/{city_name}"
    params = {"format": "j1"}

    try:
        logger.info("Fetching wttr.in for %s...", city_name)
        data = client.fetch_json(url, params=params, retries=2, backoff_sec=2.0)
        target = dest_dir / f"{city_key}_normal.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Saved %s", target)
    except Exception as e:
        logger.error("Failed wttr.in (%s): %s", city_name, e)


def main():
    client = HttpClient(min_request_interval=1.0)
    for city_key, coords in CITIES.items():
        fetch_open_meteo(client, city_key, coords)
        fetch_met_norway(client, city_key, coords)
        fetch_wttr(client, city_key, coords)
        time.sleep(1.0)
    logger.info("Fixture collection complete.")


if __name__ == "__main__":
    main()
