"""Shared pytest fixtures for the info-weather test suite.

Network isolation: unit tests must never touch the real network. Real HTTP
requests from background fetch threads (geomagnetic data, UI refreshes) can
hang on CI runners, and a long-lived daemon thread racing the garbage
collector caused segfaults on Python 3.10 (inside shiboken/PySide6 GC).

``tests/test_http.py`` is excluded from the transport stub: it exercises the
HTTP layer itself with a patched ``urllib.request.urlopen``.
``tests/test_geomagnetic.py`` is excluded from the background-fetch stub: it
verifies the async callback path explicitly with mocked clients.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.http import WeatherHttpError


@pytest.fixture(autouse=True)
def _no_network(request: pytest.FixtureRequest):
    module_name = getattr(request.module, "__name__", "")

    if module_name == "test_http":
        yield
        return

    patches = [
        patch(
            "core.http.HttpClient.fetch_json",
            side_effect=WeatherHttpError("network disabled in unit tests"),
        ),
    ]

    if module_name != "test_geomagnetic":
        # Prevent background daemon threads from being spawned at all.
        patches += [
            patch("core.geomagnetic.fetch_geomagnetic_activity_async"),
            patch("core.geomagnetic.fetch_geomagnetic_forecast_async"),
        ]

    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()
