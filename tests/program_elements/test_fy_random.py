from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from outputs.fyapi_client import ControlRequest
from program_elements.fy_random import FYRandom

PATTERN_A = UUID("00000000-0000-0000-0000-000000000001")
PATTERN_B = UUID("00000000-0000-0000-0000-000000000002")
PATTERN_MERCY = UUID("00000000-0000-0000-0000-000000000003")


def _patterns() -> dict[str, UUID]:
    return {"Alpha": PATTERN_A, "Beta": PATTERN_B, "Mercy": PATTERN_MERCY}


@patch("program_elements.fy_random.FYHandler")
def test_init_uses_all_patterns_when_included_not_specified(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()

    fy = FYRandom("user", "pass", "Device", excluded_patterns=["Mercy"])

    assert len(fy.random_patterns) == 2
    assert PATTERN_MERCY not in fy.random_patterns


@patch("program_elements.fy_random.FYHandler")
def test_init_uses_included_patterns(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()

    fy = FYRandom("user", "pass", "Device", included_patterns=["Alpha"])

    assert fy.random_patterns == [PATTERN_A]


@patch("program_elements.fy_random.FYHandler")
def test_init_raises_when_included_pattern_missing(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()

    with pytest.raises(ValueError, match="Pattern\\(s\\) not found in Device: Missing"):
        FYRandom("user", "pass", "Device", included_patterns=["Missing"])


@patch("program_elements.fy_random.FYHandler")
def test_init_raises_when_random_pool_empty(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()

    with pytest.raises(ValueError, match="No patterns available for random mode on Device"):
        FYRandom("user", "pass", "Device", excluded_patterns=["Alpha", "Beta", "Mercy"])


@patch("program_elements.fy_random.FYHandler")
def test_random_control_request(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()
    fy = FYRandom("user", "pass", "Device", speed_range=(50, 100))

    with (
        patch("program_elements.fy_random.random.choice", return_value=PATTERN_B),
        patch("program_elements.fy_random.random.uniform", return_value=0.75),
    ):
        request = fy._random_control_request()

    assert request == ControlRequest(
        pattern=PATTERN_B, speed=0.75, strokeLength=1.0, strokeMin=0.0
    )


@patch("program_elements.fy_random.FYHandler")
def test_session_valid(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()
    fy = FYRandom("user", "pass", "Device")
    fy._session_id = 3

    assert fy._session_valid(3) is True
    assert fy._session_valid(2) is False


@patch("program_elements.fy_random.FYHandler")
def test_dispatch_callback_skips_stale_session(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()
    fy = FYRandom("user", "pass", "Device")
    fy._session_id = 2
    fy._callback_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="test_fy_cb")

    callback = MagicMock()
    try:
        fy._dispatch_callback(callback, session=1)
        fy._callback_executor.shutdown(wait=True)
    finally:
        fy._callback_executor = None

    callback.assert_not_called()


@patch("program_elements.fy_random.FYHandler")
def test_dispatch_callback_runs_for_current_session(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()
    fy = FYRandom("user", "pass", "Device")
    fy._session_id = 2
    fy._callback_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="test_fy_cb")

    callback = MagicMock()
    try:
        fy._dispatch_callback(callback, session=2)
        fy._callback_executor.shutdown(wait=True)
    finally:
        fy._callback_executor = None

    callback.assert_called_once()


@patch("program_elements.fy_random.sleep")
@patch("program_elements.fy_random.FYHandler")
def test_normal_mode_controls_device_and_stops(
    mock_fy_handler_cls: MagicMock, mock_sleep: MagicMock
) -> None:
    mock_handler = mock_fy_handler_cls.return_value
    mock_handler.patterns.return_value = _patterns()
    callback = MagicMock()
    fy = FYRandom("user", "pass", "Device", mode_change_callback=callback)
    fy._ensure_callback_executor()
    fy._session_id = 1

    mock_handler.control_device.return_value = True

    def stop_on_first_sleep(_seconds: int) -> None:
        fy.flags["stop"].set()

    mock_sleep.side_effect = stop_on_first_sleep

    with (
        patch("program_elements.fy_random.random.randint", return_value=1),
        patch("program_elements.fy_random.random.choice", return_value=PATTERN_A),
        patch("program_elements.fy_random.random.uniform", return_value=0.6),
        patch.object(fy, "_dispatch_callback") as mock_dispatch,
    ):
        fy._normal_mode()
        fy._callback_executor.shutdown(wait=True)

    mock_handler.control_device.assert_called_once()
    mock_dispatch.assert_called_once_with(callback, session=1)
    mock_handler.stop.assert_called_once()


@patch("program_elements.fy_random.threading.Thread")
@patch("program_elements.fy_random.FYHandler")
def test_start_launches_daemon_thread(mock_fy_handler_cls: MagicMock, mock_thread_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = False
    mock_thread_cls.return_value = mock_thread

    fy = FYRandom("user", "pass", "Device")
    fy.start()

    mock_thread_cls.assert_called_once()
    assert mock_thread_cls.call_args.kwargs["daemon"] is True
    mock_thread.start.assert_called_once()
    assert fy._session_id == 1


@patch("program_elements.fy_random.FYHandler")
def test_start_raises_when_thread_still_alive(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()
    fy = FYRandom("user", "pass", "Device")
    fy.thread = MagicMock()
    fy.thread.is_alive.return_value = True

    with pytest.raises(RuntimeError, match="previous run still active"):
        fy.start()


@patch("program_elements.fy_random.FYHandler")
def test_stop_without_active_thread_stops_handler(mock_fy_handler_cls: MagicMock) -> None:
    mock_handler = mock_fy_handler_cls.return_value
    mock_handler.patterns.return_value = _patterns()
    fy = FYRandom("user", "pass", "Device")

    fy.stop()

    mock_handler.stop.assert_called_once()
    assert fy.flags["stop"].is_set()
