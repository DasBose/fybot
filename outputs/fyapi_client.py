from __future__ import annotations

from dataclasses import dataclass
from loguru import logger
from typing import Any
from urllib.parse import unquote, urlparse
from uuid import UUID

import requests

BASE_URL = "https://api.fuckyeah.uk"
CSRF_COOKIE_PATH = "/sanctum/csrf-cookie"
ORIGIN = "https://my.fuckyeah.uk"

def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def _uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _parse_pattern(data: dict[str, Any]) -> Pattern:
    return Pattern(
        id=_uuid(data["id"]),
        name=data["name"],
        description=data["description"],
        type=data["type"],
    )


def _parse_device(data: dict[str, Any]) -> Device:
    patterns_raw = data.get("patterns") or []
    patterns = [_parse_pattern(p) for p in patterns_raw]
    return Device(
        id=_uuid(data["id"]),
        name=data["name"],
        patterns=patterns,
    )


def _parse_user(data: dict[str, Any]) -> UserResponse:
    return UserResponse(
        id=_uuid(data["id"]),
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data["email"],
    )


class FYAPIClient:
    """
    JSON REST client for the FY API. Uses a persistent :class:`requests.Session`
    so cookies (e.g. session tokens) are kept across calls.

    Laravel / Sanctum-style CSRF: before state-changing requests, call
    ``GET csrf_cookie_path`` (default ``/sanctum/csrf-cookie``) so the server
    sets ``XSRF-TOKEN``; the session then sends ``X-XSRF-TOKEN`` decoded from
    that cookie.
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        *,
        csrf_cookie_path: str = CSRF_COOKIE_PATH,
        stateful_origin: str = ORIGIN,
    ) -> None:
        self._base = base_url
        self._csrf_cookie_path = csrf_cookie_path
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        self._session.headers["Origin"] = stateful_origin
        self._session.headers["Referer"] = f"{stateful_origin}/"

    def _send_request(self, method: str, url: str, **kwargs) -> requests.Response:
        m = method.upper()
        if m in ("POST", "PUT", "PATCH", "DELETE"):
            self._prefetch_csrf_cookie()
            self._sync_xsrf_header_from_cookies()
        logger.debug(f"FY Client: {method} {url} {kwargs}")
        r = self._session.request(method, url, **kwargs)
        logger.debug(f"FY Client: {r.status_code}")
        return r

    def _sync_xsrf_header_from_cookies(self) -> None:
        raw = self._session.cookies.get("XSRF-TOKEN")
        if raw:
            self._session.headers["X-XSRF-TOKEN"] = unquote(raw)

    def _prefetch_csrf_cookie(self) -> None:
        if not self._csrf_cookie_path:
            return
        path = self._csrf_cookie_path
        if not path.startswith("/"):
            path = f"/{path}"
        r = self._session.get(self._url(path), timeout=30)
        r.raise_for_status()
        self._sync_xsrf_header_from_cookies()

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._base}{path}"

    def login(self, login_request: LoginRequest) -> bool:
        r = self._send_request("POST", self._url("/login"), json={
            "email": login_request.email,
            "password": login_request.password,
        }, timeout=10)
        r.raise_for_status()
        return True

    def get_user(self) -> UserResponse:
        r = self._send_request("GET", self._url("/user"), timeout=10)
        r.raise_for_status()
        return _parse_user(r.json())

    def get_devices(self) -> DevicesResponse:
        r = self._send_request("GET", self._url("/v1/devices"), timeout=10)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            devices = [_parse_device(d) for d in data]
        else:
            raw = data.get("devices", data)
            if not isinstance(raw, list):
                raw = []
            devices = [_parse_device(d) for d in raw]
        return DevicesResponse(devices=devices)

    def control(self, device_id: UUID, control_request: ControlRequest) -> bool:
        maybe: dict[str, Any] = {
            "pattern": str(control_request.pattern)
            if control_request.pattern is not None
            else None,
            "r1": control_request.r1,
            "r2": control_request.r2,
            "speed": control_request.speed,
            "strokeLength": control_request.strokeLength,
            "strokeMin": control_request.strokeMin,
        }
        payload = {k: v for k, v in maybe.items() if v is not None}
        r = self._send_request("POST", self._url(f"/v1/devices/{device_id}/control"), json=payload, timeout=10)
        r.raise_for_status()
        return True


@dataclass
class LoginRequest:
    """Credentials for FY API login."""

    email: str
    password: str


@dataclass
class UserResponse:
    """Authenticated user profile returned by the API."""

    id: UUID
    first_name: str
    last_name: str
    email: str


@dataclass
class DevicesResponse:
    """List of devices owned by the authenticated user."""

    devices: list[Device]


@dataclass
class Device:
    """A single FY device and its available stimulation patterns."""

    id: UUID
    name: str
    patterns: list[Pattern]


@dataclass
class Pattern:
    """Named stimulation pattern available on a device."""

    id: UUID
    name: str
    description: str
    type: str


@dataclass
class ControlRequest:
    """Payload for POST /v1/devices/{id}/control (pattern, speeds, stroke parameters)."""

    pattern: UUID | None = None
    r1: str | None = None
    r2: str | None = None
    speed: float | None = None
    strokeLength: float | None = None
    strokeMin: float | None = None
