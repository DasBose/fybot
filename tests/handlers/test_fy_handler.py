from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from handlers.fy_handler import FYHandler
from outputs.fyapi_client import ControlRequest, Device, DevicesResponse, Pattern, UserResponse

DEVICE_ID = UUID("00000000-0000-0000-0000-000000000001")
PATTERN_ID = UUID("00000000-0000-0000-0000-000000000002")
USER_ID = UUID("00000000-0000-0000-0000-000000000003")


def _make_device(name: str = "TestDevice") -> Device:
    return Device(
        id=DEVICE_ID,
        name=name,
        patterns=[
            Pattern(id=PATTERN_ID, name="Mercy", description="", type="mode"),
        ],
    )


def _make_user() -> UserResponse:
    return UserResponse(
        id=USER_ID,
        first_name="Test",
        last_name="User",
        email="user@example.com",
    )


@patch("handlers.fy_handler.FYAPIClient")
def test_init_logs_in_and_resolves_device(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.get_user.return_value = _make_user()
    mock_client.get_devices.return_value = DevicesResponse(devices=[_make_device()])

    handler = FYHandler("user@example.com", "secret", "TestDevice")

    mock_client_cls.assert_called_once()
    mock_client.login.assert_called_once()
    assert mock_client.login.call_args[0][0].email == "user@example.com"
    mock_client.get_user.assert_called_once()
    assert handler.device.name == "TestDevice"


@patch("handlers.fy_handler.FYAPIClient")
def test_init_raises_when_device_missing(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.get_user.return_value = _make_user()
    mock_client.get_devices.return_value = DevicesResponse(devices=[])

    with pytest.raises(ValueError, match="Device with name Missing not found"):
        FYHandler("user@example.com", "secret", "Missing")


@patch("handlers.fy_handler.FYAPIClient")
def test_patterns_returns_name_to_uuid_map(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.get_user.return_value = _make_user()
    mock_client.get_devices.return_value = DevicesResponse(devices=[_make_device()])

    handler = FYHandler("user@example.com", "secret", "TestDevice")

    assert handler.patterns() == {"Mercy": PATTERN_ID}


@patch("handlers.fy_handler.FYAPIClient")
def test_control_device_delegates_to_client(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.get_user.return_value = _make_user()
    mock_client.get_devices.return_value = DevicesResponse(devices=[_make_device()])
    mock_client.control.return_value = True

    handler = FYHandler("user@example.com", "secret", "TestDevice")
    request = ControlRequest(pattern=PATTERN_ID, speed=0.5)
    result = handler.control_device(request)

    mock_client.control.assert_called_once_with(DEVICE_ID, request)
    assert result is True


@patch("handlers.fy_handler.FYAPIClient")
def test_stop_sends_zero_speed_control(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.get_user.return_value = _make_user()
    mock_client.get_devices.return_value = DevicesResponse(devices=[_make_device()])
    mock_client.control.return_value = True

    handler = FYHandler("user@example.com", "secret", "TestDevice")
    handler.stop()

    mock_client.control.assert_called_once()
    device_id, request = mock_client.control.call_args[0]
    assert device_id == DEVICE_ID
    assert request.pattern is None
    assert request.speed == 0.0
