from unittest.mock import MagicMock

import pytest

from handlers.boolean_handler import BooleanHandler


@pytest.fixture
def on_callback() -> MagicMock:
    return MagicMock()


@pytest.fixture
def off_callback() -> MagicMock:
    return MagicMock()


@pytest.fixture
def handler(on_callback: MagicMock, off_callback: MagicMock) -> BooleanHandler:
    return BooleanHandler("pump", on_callback, off_callback)


def test_set_turns_on(handler: BooleanHandler, on_callback: MagicMock, off_callback: MagicMock) -> None:
    handler.set(duration=60)

    assert handler.get() is True
    on_callback.assert_called_once()
    off_callback.assert_not_called()


def test_unset_turns_off(handler: BooleanHandler, on_callback: MagicMock, off_callback: MagicMock) -> None:
    sid = handler.set(duration=60)
    on_callback.reset_mock()
    handler.unset(sid)

    assert handler.get() is False
    off_callback.assert_called_once()


def test_unset_all_turns_off(
    handler: BooleanHandler, on_callback: MagicMock, off_callback: MagicMock
) -> None:
    handler.set(duration=60)
    handler.unset_all()

    assert handler.get() is False
    off_callback.assert_called()
