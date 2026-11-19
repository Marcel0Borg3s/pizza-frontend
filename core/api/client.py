"""HTTP client for the pizza_drf API.

Every call happens on the server. The browser never receives the API base URL,
an authorization header or a payload created with privileged data.

Basic usage::

    from core.api import ApiError, api_client

    try:
        client = api_client.post("clients/", json=payload)
    except ApiError as exc:
        for field, messages in exc.field_errors.items():
            ...
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Mapping
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_TELEMETRY: deque[dict[str, Any]] = deque(maxlen=20)
_TELEMETRY_LOCK = threading.Lock()


class ApiError(Exception):
    """Raised when the API rejects a request or cannot be reached.

    ``status_code`` is ``None`` when the failure happened before an HTTP
    response (timeout, connection refused, invalid JSON).
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details: dict[str, Any] = dict(details or {})

    @property
    def is_offline(self) -> bool:
        """True when the API could not be reached at all."""
        return self.status_code is None

    @property
    def field_errors(self) -> dict[str, list[str]]:
        """Map DRF validation errors to ``{field: [messages]}``."""
        errors: dict[str, list[str]] = {}
        for field, value in self.details.items():
            if field in {"detail", "non_field_errors"}:
                continue
            if isinstance(value, (list, tuple)):
                errors[field] = [str(item) for item in value]
            else:
                errors[field] = [str(value)]
        return errors


def _record_call(method: str, path: str, status_code: int | None, elapsed_ms: float) -> None:
    """Keep a small in-memory trace of API calls for the owner panel."""
    with _TELEMETRY_LOCK:
        _TELEMETRY.appendleft(
            {
                "method": method.upper(),
                "path": path,
                "status_code": status_code,
                "elapsed_ms": round(elapsed_ms, 1),
            }
        )


def recent_calls() -> list[dict[str, Any]]:
    """Return the most recent API calls (newest first, without bodies)."""
    with _TELEMETRY_LOCK:
        return list(_TELEMETRY)


class ApiClient:
    """Minimal JSON client with timeouts, typed errors and call telemetry."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.PIZZA_API_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.PIZZA_API_TIMEOUT

    # -- internals ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        token = getattr(settings, "PIZZA_API_TOKEN", "")
        if token:
            scheme = getattr(settings, "PIZZA_API_AUTH_SCHEME", "Token")
            headers["Authorization"] = f"{scheme} {token}"
        return headers

    @staticmethod
    def _error_message(payload: Any, fallback: str) -> str:
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail.strip():
                return detail
            for value in payload.values():
                if isinstance(value, (list, tuple)) and value:
                    return str(value[0])
                if isinstance(value, str) and value.strip():
                    return value
        return fallback

    # -- public API --------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        """Perform a request and return the decoded JSON body (or ``None``)."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        started = time.perf_counter()
        try:
            response = httpx.request(
                method.upper(),
                url,
                params=params,
                json=json,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            elapsed = (time.perf_counter() - started) * 1000
            _record_call(method, path, None, elapsed)
            logger.warning("Timeout on %s %s after %.1fms", method.upper(), path, elapsed)
            raise ApiError(f"A API não respondeu em {self.timeout:g}s. Tente novamente.") from exc
        except httpx.HTTPError as exc:
            elapsed = (time.perf_counter() - started) * 1000
            _record_call(method, path, None, elapsed)
            logger.warning("Connection error on %s %s: %s", method.upper(), path, exc)
            raise ApiError(
                "Não foi possível conectar à API. Verifique se o pizza_drf está rodando."
            ) from exc

        elapsed = (time.perf_counter() - started) * 1000
        _record_call(method, path, response.status_code, elapsed)

        payload: Any = None
        if response.content:
            try:
                payload = response.json()
            except ValueError:
                payload = None

        if response.status_code >= 400:
            message = self._error_message(
                payload, f"A API respondeu com status {response.status_code}."
            )
            logger.info(
                "API error %s %s -> %s (%s)",
                method.upper(),
                path,
                response.status_code,
                message,
            )
            raise ApiError(
                message,
                status_code=response.status_code,
                details=payload if isinstance(payload, dict) else None,
            )

        return payload

    def get(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, *, json: Any = None) -> Any:
        return self.request("POST", path, json=json)

    def patch(self, path: str, *, json: Any = None) -> Any:
        return self.request("PATCH", path, json=json)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)


api_client = ApiClient()
