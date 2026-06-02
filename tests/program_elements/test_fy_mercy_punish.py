from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from outputs.fyapi_client import ControlRequest
from program_elements.fy_mercy_punish import FYMercyPunish

PATTERN_A = UUID("00000000-0000-0000-0000-000000000001")
PATTERN_B = UUID("00000000-0000-0000-0000-000000000002")
PATTERN_MERCY = UUID("00000000-0000-0000-0000-000000000003")
PATTERN_PENALTY = UUID("00000000-0000-0000-0000-000000000004")
PATTERN_PUNISH = UUID("00000000-0000-0000-0000-000000000005")


def _patterns() -> dict[str, UUID]:
    return {
        "Alpha": PATTERN_A,
        "Beta": PATTERN_B,
        "Mercy": PATTERN_MERCY,
        "Penalty": PATTERN_PENALTY,
        "Punish": PATTERN_PUNISH,
    }


@patch("program_elements.fy_random.FYHandler")
def test_init_raises_when_special_mode_missing(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = {
        "Alpha": PATTERN_A,
        "Beta": PATTERN_B,
        "Mercy": PATTERN_MERCY,
        "Penalty": PATTERN_PENALTY,
    }

    with pytest.raises(ValueError, match="Pattern\\(s\\) not found in Device: Punish"):
        FYMercyPunish(
            "user",
            "pass",
            "Device",
            mercy_mode="Mercy",
            penalty_mode="Penalty",
            punish_mode="Punish",
        )


@patch("program_elements.fy_random.FYHandler")
def test_init_raises_when_special_mode_missing_dedupes_names(
    mock_fy_handler_cls: MagicMock,
) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = {
        "Alpha": PATTERN_A,
        "Mercy": PATTERN_MERCY,
        "Penalty": PATTERN_PENALTY,
    }

    with pytest.raises(ValueError, match="Pattern\\(s\\) not found in Device: Missing"):
        FYMercyPunish(
            "user",
            "pass",
            "Device",
            mercy_mode="Mercy",
            penalty_mode="Missing",
            punish_mode="Missing",
        )


@patch("program_elements.fy_random.FYHandler")
def test_init_excludes_special_modes_from_random_pool(mock_fy_handler_cls: MagicMock) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()

    fy = FYMercyPunish(
        "user",
        "pass",
        "Device",
        mercy_mode="Mercy",
        penalty_mode="Penalty",
        punish_mode="Punish",
    )

    assert PATTERN_MERCY not in fy.random_patterns
    assert PATTERN_PENALTY not in fy.random_patterns
    assert PATTERN_PUNISH not in fy.random_patterns
    assert set(fy.random_patterns) == {PATTERN_A, PATTERN_B}


@patch("program_elements.fy_random.FYHandler")
def test_mercy_and_penalty_runs_modes_in_order(mock_fy_handler_cls: MagicMock) -> None:
    mock_handler = mock_fy_handler_cls.return_value
    mock_handler.patterns.return_value = _patterns()
    fy = FYMercyPunish(
        "user",
        "pass",
        "Device",
        mercy_mode="Mercy",
        penalty_mode="Penalty",
        punish_mode="Punish",
    )
    fy._session_id = 1
    fy.flags["normal_running"].set()
    fy.flags["normal_paused"].set()

    with (
        patch.object(fy.flags["stop"], "wait"),
        patch.object(fy, "_dispatch_callback") as mock_dispatch,
        patch.object(fy, "_finish_special_mode") as mock_finish,
    ):
        fy._mercy_and_penalty(session=1, mercy_duration=5, penalty_duration=10)

    calls = mock_handler.control_device.call_args_list
    assert calls[0][0][0] == ControlRequest(
        pattern=PATTERN_MERCY, speed=0.5, strokeLength=1.0, strokeMin=0.0
    )
    assert calls[1][0][0] == ControlRequest(
        pattern=PATTERN_PENALTY, speed=1.0, strokeLength=1.0, strokeMin=0.0
    )
    assert mock_dispatch.call_count == 2
    mock_finish.assert_called_once_with(1)


@patch("program_elements.fy_random.FYHandler")
def test_mercy_and_penalty_aborts_on_stale_session(mock_fy_handler_cls: MagicMock) -> None:
    mock_handler = mock_fy_handler_cls.return_value
    mock_handler.patterns.return_value = _patterns()
    normal_callback = MagicMock()
    fy = FYMercyPunish(
        "user",
        "pass",
        "Device",
        mercy_mode="Mercy",
        penalty_mode="Penalty",
        punish_mode="Punish",
        normal_mode_callback=normal_callback,
    )
    fy._session_id = 2
    fy.flags["normal_running"].set()
    fy.flags["normal_paused"].set()

    fy._mercy_and_penalty(session=1, mercy_duration=5, penalty_duration=10)

    normal_callback.assert_called_once()
    mock_handler.stop.assert_called_once()
    mock_handler.control_device.assert_not_called()


@patch("program_elements.fy_random.FYHandler")
def test_punish_runs_punish_mode(mock_fy_handler_cls: MagicMock) -> None:
    mock_handler = mock_fy_handler_cls.return_value
    mock_handler.patterns.return_value = _patterns()
    fy = FYMercyPunish(
        "user",
        "pass",
        "Device",
        mercy_mode="Mercy",
        penalty_mode="Penalty",
        punish_mode="Punish",
    )
    fy._session_id = 3
    fy.flags["normal_running"].set()
    fy.flags["normal_paused"].set()

    with (
        patch.object(fy.flags["stop"], "wait"),
        patch.object(fy, "_dispatch_callback") as mock_dispatch,
        patch.object(fy, "_finish_special_mode") as mock_finish,
    ):
        fy._punish(session=3, duration=30)

    mock_handler.control_device.assert_called_once_with(
        ControlRequest(pattern=PATTERN_PUNISH, speed=1.0, strokeLength=1.0, strokeMin=0.0)
    )
    mock_dispatch.assert_called_once_with(fy.punish_mode_callback, session=3)
    mock_finish.assert_called_once_with(3)


@patch("program_elements.fy_mercy_punish.threading.Thread")
@patch("program_elements.fy_random.FYHandler")
def test_mercy_and_penalty_starts_background_thread(
    mock_fy_handler_cls: MagicMock, mock_thread_cls: MagicMock
) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()
    mock_thread = MagicMock()
    mock_thread_cls.return_value = mock_thread

    fy = FYMercyPunish(
        "user",
        "pass",
        "Device",
        mercy_mode="Mercy",
        penalty_mode="Penalty",
        punish_mode="Punish",
    )
    fy._session_id = 4

    fy.mercy_and_penalty(mercy_duration=5, penalty_duration=10)

    mock_thread_cls.assert_called_once()
    assert mock_thread_cls.call_args.kwargs["daemon"] is True
    assert mock_thread_cls.call_args.kwargs["target"] == fy._mercy_and_penalty
    assert mock_thread_cls.call_args.kwargs["args"] == (4, 5, 10)
    mock_thread.start.assert_called_once()


@patch("program_elements.fy_mercy_punish.threading.Thread")
@patch("program_elements.fy_random.FYHandler")
def test_punish_starts_background_thread(
    mock_fy_handler_cls: MagicMock, mock_thread_cls: MagicMock
) -> None:
    mock_fy_handler_cls.return_value.patterns.return_value = _patterns()
    mock_thread = MagicMock()
    mock_thread_cls.return_value = mock_thread

    fy = FYMercyPunish(
        "user",
        "pass",
        "Device",
        mercy_mode="Mercy",
        penalty_mode="Penalty",
        punish_mode="Punish",
    )
    fy._session_id = 7

    fy.punish(duration=60)

    mock_thread_cls.assert_called_once()
    assert mock_thread_cls.call_args.kwargs["target"] == fy._punish
    assert mock_thread_cls.call_args.kwargs["args"] == (7, 60)
    mock_thread.start.assert_called_once()
