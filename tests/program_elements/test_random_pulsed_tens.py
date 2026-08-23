from unittest.mock import MagicMock, patch

import pytest

from program_elements.random_pulsed_tens import RandomPulsedTens


@pytest.fixture
def level_handler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def pulsed_tens(level_handler: MagicMock) -> RandomPulsedTens:
    return RandomPulsedTens([level_handler])


def test_set_range(pulsed_tens: RandomPulsedTens) -> None:
    pulsed_tens.set_range((10, 50))
    assert pulsed_tens.level_range == (10, 50)


def test_set_on_duration(pulsed_tens: RandomPulsedTens) -> None:
    pulsed_tens.set_on_duration((0, 3))
    assert pulsed_tens.on_duration == (0, 3)


def test_set_off_duration(pulsed_tens: RandomPulsedTens) -> None:
    pulsed_tens.set_off_duration((2, 8))
    assert pulsed_tens.off_duration == (2, 8)


def test_loop_runs_one_pulse_cycle(level_handler: MagicMock, pulsed_tens: RandomPulsedTens) -> None:
    pulsed_tens._stop.clear()
    sleep_calls = 0

    def sleep_then_stop(_duration: float) -> bool:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            pulsed_tens._stop.set()
        return False

    with (
        patch.object(pulsed_tens, "_sleep", side_effect=sleep_then_stop),
        patch("program_elements.random_pulsed_tens.random.randint", return_value=42),
        patch("program_elements.random_pulsed_tens.random.uniform", side_effect=[2.0, 3.0]),
    ):
        pulsed_tens._loop(level_handler)

    level_handler.set_id.assert_called_once_with(42, 11, pulsed_tens.setting_id)
    level_handler.unset.assert_called_with(pulsed_tens.setting_id)


def test_loop_stops_when_sleep_reports_stop(level_handler: MagicMock, pulsed_tens: RandomPulsedTens) -> None:
    pulsed_tens._stop.clear()

    with (
        patch.object(pulsed_tens, "_sleep", return_value=True),
        patch("program_elements.random_pulsed_tens.random.randint", return_value=10),
        patch("program_elements.random_pulsed_tens.random.uniform", return_value=1.0),
    ):
        pulsed_tens._loop(level_handler)

    level_handler.set_id.assert_called_once()
    level_handler.unset.assert_called_once_with(pulsed_tens.setting_id)


def test_loop_clamps_level_with_offset_to_0_127(
    level_handler: MagicMock, pulsed_tens: RandomPulsedTens
) -> None:
    pulsed_tens._stop.clear()
    pulsed_tens.set_range((100, 100))
    pulsed_tens.set_offset(50)

    with (
        patch.object(pulsed_tens, "_sleep", return_value=True),
        patch("program_elements.random_pulsed_tens.random.randint", return_value=100),
        patch("program_elements.random_pulsed_tens.random.uniform", return_value=1.0),
    ):
        pulsed_tens._loop(level_handler)

    level_handler.set_id.assert_called_once_with(127, 11, pulsed_tens.setting_id)


@patch("program_elements.random_pulsed_tens.threading.Thread")
def test_on_starts_thread_per_handler(
    mock_thread_cls: MagicMock, level_handler: MagicMock, pulsed_tens: RandomPulsedTens
) -> None:
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = False
    mock_thread_cls.return_value = mock_thread

    pulsed_tens.on()

    mock_thread_cls.assert_called_once()
    mock_thread.start.assert_called_once()
    assert len(pulsed_tens._threads) == 1


def test_on_skips_when_threads_already_alive(pulsed_tens: RandomPulsedTens) -> None:
    alive_thread = MagicMock()
    alive_thread.is_alive.return_value = True
    pulsed_tens._threads = [alive_thread]

    with patch("program_elements.random_pulsed_tens.threading.Thread") as mock_thread_cls:
        pulsed_tens.on()

    mock_thread_cls.assert_not_called()


def test_off_stops_threads_and_unsets_handlers(level_handler: MagicMock, pulsed_tens: RandomPulsedTens) -> None:
    thread = MagicMock()
    thread.is_alive.return_value = True
    pulsed_tens._threads = [thread]

    pulsed_tens.off()

    assert pulsed_tens._stop.is_set()
    thread.join.assert_called_once_with(timeout=30)
    assert pulsed_tens._threads == []
    level_handler.unset.assert_called_once_with(pulsed_tens.setting_id)
