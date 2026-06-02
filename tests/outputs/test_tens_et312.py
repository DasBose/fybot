from unittest.mock import MagicMock

import pytest

from outputs.tens.tens_et312 import READY_VALUE, TensET312


@pytest.fixture
def device() -> TensET312:
    tens = object.__new__(TensET312)
    tens.conn = MagicMock()
    return tens


def test_wait_ready_returns_when_device_ready(device: TensET312) -> None:
    device.conn.read.return_value = READY_VALUE

    device._wait_ready(0x4070, timeout=1.0)

    device.conn.read.assert_called_with(0x4070)


def test_wait_ready_times_out_when_read_never_ready(device: TensET312) -> None:
    device.conn.read.return_value = 0

    with pytest.raises(TimeoutError, match="Timed out waiting for ready"):
        device._wait_ready(0x4070, timeout=0.05)


def test_read_reraises_on_serial_error(device: TensET312) -> None:
    device.conn.read.side_effect = OSError("serial error")

    with pytest.raises(OSError, match="serial error"):
        device._read(0x4070)
