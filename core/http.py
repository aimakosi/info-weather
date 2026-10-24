"""
Unified HTTP client layer for info-weather.
Encapsulates timeouts, retries with backoff, rate limiting,
User-Agent headers, gzip decoding, JSON parsing, cancellation tokens,
and typed exceptions using stdlib urllib.
"""

from __future__ import annotations

import gzip
import http.client
import json
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from typing import Any

from core.logging import get_logger

logger = get_logger("core.http")

# Константы по умолчанию
DEFAULT_TIMEOUT = 8.0
DEFAULT_RETRIES = 1
DEFAULT_DNS_TIMEOUT = 5.0
DEFAULT_PREFER_IPV4 = True
DEFAULT_TOTAL_FETCH_TIMEOUT = 30.0
DEFAULT_USER_AGENT = "info-weather/0.1.0 (Linux; KDE Plasma; contact: aimakosi@users.noreply.github.com)"
DEFAULT_MIN_REQUEST_INTERVAL = 1.0  # секунды между запросами к одному хосту


def _resolve_host(host: str, port: int, timeout: float) -> list[tuple[Any, ...]]:
    """Resolve host with a hard deadline.

    ``socket.getaddrinfo`` has no timeout parameter, so a broken resolver can
    block for minutes even when the surrounding socket timeout is small.
    Resolution runs in a daemon thread and the caller stops waiting after
    ``timeout`` seconds.
    """
    if timeout <= 0:
        return socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)

    outcome: dict[str, Any] = {}

    def _worker() -> None:
        try:
            outcome["infos"] = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        except Exception as exc:  # pragma: no cover - depends on system resolver
            outcome["error"] = exc

    thread = threading.Thread(target=_worker, name="info-weather-dns", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError(f"DNS resolution timed out for {host} after {timeout:.1f}s")
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("infos", [])


def _create_connection_preferring_ipv4(
    address: tuple[str, int],
    timeout: float | None = None,
    source_address: tuple[str, int] | None = None,
    prefer_ipv4: bool = True,
    dns_timeout: float = DEFAULT_DNS_TIMEOUT,
) -> socket.socket:
    """Drop-in replacement for ``socket.create_connection``.

    - bounds DNS resolution with ``dns_timeout``;
    - tries IPv4 addresses first when ``prefer_ipv4`` is enabled;
    - applies one deadline to all connection attempts.
    """
    host, port = address
    infos = _resolve_host(host, port, dns_timeout)
    if prefer_ipv4:
        infos.sort(key=lambda info: 0 if info[0] == socket.AF_INET else 1)
    if not infos:
        raise OSError(f"getaddrinfo returns an empty list for {host}")

    deadline = time.monotonic() + timeout if timeout else None
    # Give each address a fair chance (IPv4 may be broken while IPv6 works and
    # vice versa) while still respecting one overall deadline.
    per_address = timeout
    if timeout is not None and len(infos) > 1:
        per_address = max(1.0, timeout / len(infos))
    last_error: OSError | None = None
    for family, socktype, proto, _canonname, sockaddr in infos:
        sock: socket.socket | None = None
        try:
            remaining = per_address
            if deadline is not None:
                remaining = min(per_address, deadline - time.monotonic())
                if remaining <= 0:
                    break
            sock = socket.socket(family, socktype, proto)
            if remaining is not None:
                sock.settimeout(remaining)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            if deadline is not None:
                # Let the TLS handshake use the rest of the overall budget.
                sock.settimeout(max(0.1, deadline - time.monotonic()))
            return sock
        except OSError as exc:
            last_error = exc
            if sock is not None:
                sock.close()

    if last_error is not None:
        raise last_error
    raise TimeoutError(f"Connection timed out for {host}")


class _BoundedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection with bounded DNS and optional IPv4 preference."""

    prefer_ipv4: bool = DEFAULT_PREFER_IPV4
    dns_timeout: float = DEFAULT_DNS_TIMEOUT

    def _create_connection(
        self,
        address: tuple[str, int],
        timeout: float | None = None,
        source_address: tuple[str, int] | None = None,
    ) -> socket.socket:
        return _create_connection_preferring_ipv4(
            address,
            timeout=timeout,
            source_address=source_address,
            prefer_ipv4=self.prefer_ipv4,
            dns_timeout=self.dns_timeout,
        )


class _BoundedHTTPSHandler(urllib.request.HTTPSHandler):
    """urllib handler wired to :class:`_BoundedHTTPSConnection`."""

    def __init__(
        self,
        prefer_ipv4: bool = DEFAULT_PREFER_IPV4,
        dns_timeout: float = DEFAULT_DNS_TIMEOUT,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._connection_class = type(
            "_ConfiguredBoundedHTTPSConnection",
            (_BoundedHTTPSConnection,),
            {"prefer_ipv4": prefer_ipv4, "dns_timeout": dns_timeout},
        )

    def https_open(self, req: urllib.request.Request) -> Any:
        return self.do_open(self._connection_class, req, context=self._context)


class WeatherHttpError(Exception):
    """Base error for weather HTTP transport."""


class WeatherTimeoutError(WeatherHttpError):
    """Request timed out."""


class WeatherRateLimitError(WeatherHttpError):
    """HTTP 429 Too Many Requests."""


class WeatherParseError(WeatherHttpError):
    """Failed to decode or parse response."""


class CancellationToken:
    """Thread-safe cancellation token for request groups (e.g. city switch or exit)."""

    def __init__(self, request_id: str = "") -> None:
        self.request_id = request_id
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()


class HttpClient:
    """Unified HTTP transport for providers."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        default_timeout: float = DEFAULT_TIMEOUT,
        min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL,
        default_retries: int = DEFAULT_RETRIES,
        prefer_ipv4: bool = DEFAULT_PREFER_IPV4,
        dns_timeout: float = DEFAULT_DNS_TIMEOUT,
    ) -> None:
        self.user_agent = user_agent
        self.default_timeout = default_timeout
        self.min_request_interval = min_request_interval
        self.default_retries = max(0, int(default_retries))
        self.prefer_ipv4 = prefer_ipv4
        self.dns_timeout = max(0.0, float(dns_timeout))

        self._lock = threading.Lock()
        self._last_request_time: dict[str, float] = {}

        # A custom opener is only needed when IPv4 preference or a bounded
        # DNS resolution is requested. Otherwise keep stdlib urlopen behavior.
        self._opener: urllib.request.OpenerDirector | None = None
        self._rebuild_opener()

    def _rebuild_opener(self) -> None:
        if self.prefer_ipv4 or self.dns_timeout > 0:
            self._opener = urllib.request.build_opener(
                _BoundedHTTPSHandler(
                    prefer_ipv4=self.prefer_ipv4,
                    dns_timeout=self.dns_timeout,
                )
            )
        else:
            self._opener = None

    @classmethod
    def from_config(cls, config_manager: Any = None) -> HttpClient:
        """Build a client from the ``network`` section of the application config."""
        client = cls(prefer_ipv4=False, dns_timeout=0)
        client.configure_from_config(config_manager)
        return client

    def configure_from_config(self, config_manager: Any = None) -> None:
        """Apply the ``network`` config section to an existing client."""
        network_cfg: dict[str, Any] = {}
        if config_manager is not None:
            network_cfg = config_manager.get("network", {}) or {}

        def _num(key: str, default: float) -> float:
            try:
                return float(network_cfg.get(key, default))
            except (TypeError, ValueError):
                return default

        retries_raw = network_cfg.get("retries", DEFAULT_RETRIES)
        try:
            retries = int(retries_raw)
        except (TypeError, ValueError):
            retries = DEFAULT_RETRIES

        self.default_timeout = _num("timeout_seconds", DEFAULT_TIMEOUT)
        self.default_retries = max(0, retries)
        self.dns_timeout = max(0.0, _num("dns_timeout_seconds", DEFAULT_DNS_TIMEOUT))
        self.prefer_ipv4 = bool(network_cfg.get("prefer_ipv4", DEFAULT_PREFER_IPV4))
        self._rebuild_opener()

    def _open(
        self,
        request: urllib.request.Request,
        timeout: float,
    ) -> Any:
        if self._opener is not None:
            return self._opener.open(request, timeout=timeout)
        return urllib.request.urlopen(request, timeout=timeout)

    def fetch_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
        retries: int | None = None,
        backoff_sec: float = 1.0,
        token: CancellationToken | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Fetch JSON from URL with query parameters, retries, and cancellation check.
        Returns parsed dictionary or raises WeatherHttpError.
        """
        if token and token.is_cancelled:
            raise WeatherHttpError(f"Request {token.request_id} was cancelled before sending")

        full_url = url
        if params:
            query_string = urllib.parse.urlencode(params, doseq=True)
            separator = "&" if "?" in url else "?"
            full_url = f"{url}{separator}{query_string}"

        parsed_url = urllib.parse.urlparse(full_url)
        host = parsed_url.netloc

        # Локальный rate limit по хосту
        self._apply_rate_limit(host)

        req_timeout = timeout if timeout is not None else self.default_timeout
        retry_count = self.default_retries if retries is None else retries
        attempts = max(1, retry_count + 1)

        for attempt in range(1, attempts + 1):
            if token and token.is_cancelled:
                raise WeatherHttpError(f"Request {token.request_id} was cancelled during retries")

            try:
                headers = {
                    "User-Agent": self.user_agent,
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "application/json",
                }
                if extra_headers:
                    headers.update(extra_headers)

                request = urllib.request.Request(full_url, headers=headers)
                logger.debug("HTTP GET %s (attempt %d/%d)", full_url, attempt, attempts)

                with self._open(request, timeout=req_timeout) as response:
                    raw_bytes = response.read()

                    # Распаковка gzip/deflate при необходимости
                    content_encoding = response.headers.get("Content-Encoding", "").lower()
                    try:
                        if content_encoding == "gzip" or raw_bytes[:2] == b"\x1f\x8b":
                            raw_bytes = gzip.decompress(raw_bytes)
                        elif content_encoding == "deflate":
                            try:
                                raw_bytes = zlib.decompress(raw_bytes)
                            except zlib.error:
                                # Some servers send raw deflate without the zlib header.
                                raw_bytes = zlib.decompress(raw_bytes, -zlib.MAX_WBITS)
                    except Exception as e:
                        raise WeatherParseError(f"Decompression failed ({content_encoding}): {e}") from e

                    try:
                        text = raw_bytes.decode("utf-8")
                    except UnicodeDecodeError as e:
                        raise WeatherParseError(f"Encoding error: {e}") from e

                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError as e:
                        raise WeatherParseError(f"Invalid JSON response: {e}") from e

                    if not isinstance(data, (dict, list)):
                        raise WeatherParseError(f"Expected JSON object or list, got {type(data)}")

                    return data

            except urllib.error.HTTPError as e:
                logger.warning("HTTP %d for %s: %s", e.code, full_url, e.reason)
                if e.code == 429:
                    if attempt < attempts:
                        time.sleep(backoff_sec * (2 ** (attempt - 1)))
                        continue
                    raise WeatherRateLimitError(f"Rate limit exceeded (429) for {host}") from e
                if 500 <= e.code <= 599:
                    if attempt < attempts:
                        time.sleep(backoff_sec * attempt)
                        continue
                raise WeatherHttpError(f"HTTP error {e.code}: {e.reason}") from e

            except (urllib.error.URLError, TimeoutError) as e:
                logger.warning("Network/Timeout error for %s: %s", full_url, e)
                if attempt < attempts:
                    time.sleep(backoff_sec * attempt)
                    continue
                if isinstance(e, TimeoutError) or "timed out" in str(e).lower():
                    raise WeatherTimeoutError(f"Connection timed out for {full_url}") from e
                raise WeatherHttpError(f"Network error: {e}") from e

            except WeatherHttpError:
                raise

            except Exception as e:
                logger.error("Unexpected error fetching %s: %s", full_url, e)
                raise WeatherHttpError(f"Unexpected transport failure: {e}") from e

        raise WeatherHttpError(f"Failed to fetch {full_url} after {attempts} attempts")

    def _apply_rate_limit(self, host: str) -> None:
        """Enforce minimum spacing between queries to the same host."""
        sleep_needed = 0.0
        with self._lock:
            now = time.monotonic()
            last_time = self._last_request_time.get(host, 0.0)
            elapsed = now - last_time
            if elapsed < self.min_request_interval:
                sleep_needed = self.min_request_interval - elapsed
            self._last_request_time[host] = now + sleep_needed

        if sleep_needed > 0:
            time.sleep(sleep_needed)


# Глобальный синглтон HTTP-клиента
default_http_client = HttpClient()


def get_default_http_client() -> HttpClient:
    """Return default shared HttpClient instance."""
    return default_http_client

