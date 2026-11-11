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

import gc
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


@pytest.fixture(scope="session", autouse=True)
def _qt_widget_cleanup():
    """Destroy leftover top-level widgets while Qt is still fully alive.

    PySide6 6.12 can segfault during interpreter shutdown when visible
    top-level widgets survive until then (shiboken then deletes native objects
    in an arbitrary order, crashing after pytest has already reported success).
    Closing and deleting them deterministically keeps the process exit status
    clean.
    """
    yield

    try:
        from ui.qt_compat import QApplication, QtCore
    except ImportError:
        return

    app = QApplication.instance()
    if app is None:
        return

    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    app.processEvents()
    QApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()
    app.processEvents()
