"""
Unit tests for core.http (HttpClient and CancellationToken).
"""

import gzip
import io
import json
import socket
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

import core.http as http_module
from core.http import (
    CancellationToken,
    HttpClient,
    WeatherHttpError,
    WeatherParseError,
    WeatherRateLimitError,
)


class TestHttpClient(unittest.TestCase):
    def setUp(self):
        # Disable the custom transport so urllib.request.urlopen stays patchable.
        self.client = HttpClient(
            user_agent="test-agent",
            default_timeout=2.0,
            min_request_interval=0.01,
            prefer_ipv4=False,
            dns_timeout=0,
        )

    def test_cancellation_token_before_request(self):
        """Проверка отмены запроса до его отправки."""
        token = CancellationToken(request_id="req-123")
        token.cancel()
        self.assertTrue(token.is_cancelled)

        with self.assertRaises(WeatherHttpError) as cm:
            self.client.fetch_json("https://example.com/api", token=token)
        self.assertIn("cancelled before sending", str(cm.exception))

    @patch("urllib.request.urlopen")
    def test_successful_json_fetch(self, mock_urlopen):
        """Проверка успешного получения и декодирования JSON."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"temperature": 22.5, "city": "Karaganda"}).encode("utf-8")
        mock_resp.headers = {}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        data = self.client.fetch_json("https://api.open-meteo.com/v1/forecast", params={"latitude": 49.8, "longitude": 73.1})
        self.assertEqual(data["temperature"], 22.5)
        self.assertEqual(data["city"], "Karaganda")

    @patch("urllib.request.urlopen")
    def test_gzip_decompression(self, mock_urlopen):
        """Проверка автоматической распаковки gzip ответа."""
        raw_json = json.dumps({"source": "MET Norway", "wind": 5.4}).encode("utf-8")
        compressed = gzip.compress(raw_json)

        mock_resp = MagicMock()
        mock_resp.read.return_value = compressed
        mock_resp.headers = {"Content-Encoding": "gzip"}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        data = self.client.fetch_json("https://api.met.no/weatherapi/locationforecast/2.0/compact")
        self.assertEqual(data["source"], "MET Norway")
        self.assertEqual(data["wind"], 5.4)

    @patch("urllib.request.urlopen")
    def test_deflate_decompression(self, mock_urlopen):
        """Проверка автоматической распаковки deflate/zlib ответа."""
        import zlib

        raw_json = json.dumps({"source": "Open-Meteo", "temp": 0.5}).encode("utf-8")
        compressed = zlib.compress(raw_json)

        mock_resp = MagicMock()
        mock_resp.read.return_value = compressed
        mock_resp.headers = {"Content-Encoding": "deflate"}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        data = self.client.fetch_json("https://api.open-meteo.com/v1/forecast")
        self.assertEqual(data["source"], "Open-Meteo")
        self.assertEqual(data["temp"], 0.5)

    @patch("urllib.request.urlopen")
    def test_invalid_json_raises_parse_error(self, mock_urlopen):
        """Проверка обработки некорректного JSON ответа."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html>502 Bad Gateway</html>"
        mock_resp.headers = {}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with self.assertRaises(WeatherParseError):
            self.client.fetch_json("https://wttr.in/Oslo?format=j1", retries=0)

    @patch("urllib.request.urlopen")
    def test_rate_limit_429_backoff_and_error(self, mock_urlopen):
        """Проверка обработки 429 Too Many Requests с retry."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.open-meteo.com",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(b"{}"),
        )

        with self.assertRaises(WeatherRateLimitError):
            self.client.fetch_json("https://api.open-meteo.com/v1/forecast", retries=1, backoff_sec=0.01)
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_from_config_reads_network_section(self):
        config = MagicMock()
        config.get.return_value = {
            "timeout_seconds": 3.5,
            "dns_timeout_seconds": 0,
            "retries": 2,
            "prefer_ipv4": False,
        }
        client = HttpClient.from_config(config)
        self.assertEqual(client.default_timeout, 3.5)
        self.assertEqual(client.default_retries, 2)
        self.assertFalse(client.prefer_ipv4)
        self.assertEqual(client.dns_timeout, 0)
        self.assertIsNone(client._opener)

        # Re-applying config to a running client updates it in place
        config.get.return_value = {
            "timeout_seconds": 12.0,
            "dns_timeout_seconds": 2.5,
            "retries": 0,
            "prefer_ipv4": True,
        }
        client.configure_from_config(config)
        self.assertEqual(client.default_timeout, 12.0)
        self.assertEqual(client.default_retries, 0)
        self.assertTrue(client.prefer_ipv4)
        self.assertEqual(client.dns_timeout, 2.5)
        self.assertIsNotNone(client._opener)

    @patch("urllib.request.urlopen")
    def test_default_retries_used(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.headers = {}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.side_effect = [urllib.error.URLError("timed out"), mock_resp]

        client = HttpClient(
            default_retries=2,
            min_request_interval=0,
            prefer_ipv4=False,
            dns_timeout=0,
        )
        data = client.fetch_json("https://example.com/api", backoff_sec=0)
        self.assertTrue(data["ok"])
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_ipv4_addresses_are_tried_first(self):
        infos = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 443, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
        created_families = []

        class FakeSocket:
            def __init__(self, family, socktype, proto):
                created_families.append(family)

            def settimeout(self, timeout):
                pass

            def bind(self, address):
                pass

            def connect(self, address):
                pass

            def close(self):
                pass

        with patch.object(http_module, "_resolve_host", return_value=infos), \
                patch.object(http_module.socket, "socket", FakeSocket):
            sock = http_module._create_connection_preferring_ipv4(
                ("example.com", 443), timeout=1.0, prefer_ipv4=True
            )

        self.assertIsInstance(sock, FakeSocket)
        self.assertEqual(created_families[0], socket.AF_INET)

    def test_dns_resolution_timeout(self):
        def slow_getaddrinfo(*args, **kwargs):
            import time as _time
            _time.sleep(0.2)
            return []

        with patch.object(http_module.socket, "getaddrinfo", side_effect=slow_getaddrinfo):
            with self.assertRaises(TimeoutError):
                http_module._resolve_host("example.com", 443, timeout=0.02)


if __name__ == "__main__":
    unittest.main()
