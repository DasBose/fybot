from unittest.mock import MagicMock, patch

import pytest

from handlers.level_handler import LevelHandler


@pytest.fixture
def callback() -> MagicMock:
    return MagicMock()


@pytest.fixture
def handler(callback: MagicMock) -> LevelHandler:
    return LevelHandler("test", callback)


def test_set_calls_callback_with_level(handler: LevelHandler, callback: MagicMock) -> None:
    handler.set(50, duration=60)

    callback.assert_called_once_with(50)
    assert handler.get() == 50


def test_effective_level_is_max_of_active_settings(handler: LevelHandler, callback: MagicMock) -> None:
    handler.set_id(30, duration=60, id="a")
    callback.reset_mock()
    handler.set_id(80, duration=60, id="b")

    assert handler.get() == 80
    callback.assert_called_once_with(80)


def test_same_id_uses_max_level(handler: LevelHandler, callback: MagicMock) -> None:
    handler.set_id(40, duration=60, id="same")
    callback.reset_mock()
    handler.set_id(25, duration=60, id="same")

    assert handler.get() == 40
    callback.assert_not_called()


def test_unset_lowers_level(handler: LevelHandler, callback: MagicMock) -> None:
    sid_a = handler.set(90, duration=60)
    handler.set_id(40, duration=60, id="b")
    callback.reset_mock()

    handler.unset(sid_a)

    assert handler.get() == 40
    callback.assert_called_once_with(40)


def test_unset_all_clears_to_zero(handler: LevelHandler, callback: MagicMock) -> None:
    handler.set(70, duration=60)
    handler.set_id(50, duration=60, id="other")
    callback.reset_mock()

    handler.unset_all()

    assert handler.get() == 0
    callback.assert_called_once_with(0)


def test_timer_expiry_clears_setting(handler: LevelHandler, callback: MagicMock) -> None:
    import time

    handler.set(60, duration=0.02)
    callback.assert_called_with(60)

    time.sleep(0.05)

    assert handler.get() == 0
    callback.assert_called_with(0)


def test_close_calls_callback_with_zero(handler: LevelHandler, callback: MagicMock) -> None:
    handler.set(99, duration=60)
    callback.reset_mock()

    handler.close()

    callback.assert_called_once_with(0)


def test_context_manager_closes(handler: LevelHandler, callback: MagicMock) -> None:
    with handler:
        handler.set(10, duration=60)
    callback.assert_called_with(0)
