from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from handlers.fy_handler import ControlRequest, FYHandler

TOKEN = "fy_test_token"
DEVICE_ID = "device-1"
PATTERN_ID = "pattern-1"


def _make_device(name: str = "TestDevice") -> SimpleNamespace:
    return SimpleNamespace(
        id=DEVICE_ID,
        name=name,
        patterns=(SimpleNamespace(id=PATTERN_ID, name="Mercy"),),
    )


def _client_with_device(name: str = "TestDevice") -> MagicMock:
    listed = SimpleNamespace(name=name)
    detailed = _make_device(name)
    client = MagicMock()
    client.list_devices.return_value = [listed]
    client.get_device.return_value = detailed
    return client


@patch("handlers.fy_handler.FuckYeahClient")
def test_init_resolves_device(mock_client_cls: MagicMock) -> None:
    mock_client = _client_with_device()
    mock_client_cls.return_value = mock_client

    handler = FYHandler(TOKEN, "TestDevice")

    mock_client_cls.assert_called_once_with(TOKEN)
    mock_client.list_devices.assert_called_once_with()
    mock_client.get_device.assert_called_once_with(mock_client.list_devices.return_value[0])
    assert handler.device.name == "TestDevice"


@patch("handlers.fy_handler.FuckYeahClient")
def test_init_raises_when_device_missing(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.list_devices.return_value = []

    with pytest.raises(ValueError, match="Device with name Missing not found"):
        FYHandler(TOKEN, "Missing")


@patch("handlers.fy_handler.FuckYeahClient")
def test_patterns_returns_name_to_id_map(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = _client_with_device()

    handler = FYHandler(TOKEN, "TestDevice")

    assert handler.patterns() == {"Mercy": PATTERN_ID}


@patch("handlers.fy_handler.FuckYeahClient")
def test_control_device_delegates_to_client(mock_client_cls: MagicMock) -> None:
    mock_client = _client_with_device()
    mock_client_cls.return_value = mock_client

    handler = FYHandler(TOKEN, "TestDevice")
    request = ControlRequest(pattern=PATTERN_ID, speed=0.5)
    handler.control_device(request)

    mock_client.run_pattern.assert_called_once_with(
        DEVICE_ID,
        pattern_id=PATTERN_ID,
        speed=0.5,
        stroke_min=None,
        stroke_length=None,
        r1=None,
        r2=None,
    )


@patch("handlers.fy_handler.FuckYeahClient")
def test_stop_stops_device(mock_client_cls: MagicMock) -> None:
    mock_client = _client_with_device()
    mock_client_cls.return_value = mock_client

    handler = FYHandler(TOKEN, "TestDevice")
    handler.stop()

    mock_client.stop_device.assert_called_once_with(DEVICE_ID)
