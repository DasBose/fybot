from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from handlers.button_handler import ButtonHandler


@patch("handlers.button_handler.ThreadPoolExecutor")
@patch("handlers.button_handler.Button")
def test_button_handler_wires_gpio_callbacks(
    mock_button_cls: MagicMock,
    mock_executor_cls: MagicMock,
) -> None:
    mock_button = MagicMock()
    mock_button_cls.return_value = mock_button
    mock_executor = MagicMock(spec=ThreadPoolExecutor)
    mock_executor_cls.return_value = mock_executor

    on_pressed = MagicMock()
    on_released = MagicMock()

    handler = ButtonHandler(14, on_pressed, on_released, bounce_time=0.05)

    mock_button_cls.assert_called_once_with(14, bounce_time=0.05)
    mock_executor_cls.assert_called_once_with(max_workers=2, thread_name_prefix="btn_14")
    assert mock_button.when_pressed is not None
    assert mock_button.when_released is not None
    assert handler.button_pin == 14

    handler.close()
    mock_button.close.assert_called_once()
    mock_executor.shutdown.assert_called_once_with(wait=False)


@patch("handlers.button_handler.ThreadPoolExecutor")
@patch("handlers.button_handler.Button")
def test_button_press_invokes_callback(
    mock_button_cls: MagicMock,
    mock_executor_cls: MagicMock,
) -> None:
    mock_button = MagicMock()
    mock_button_cls.return_value = mock_button
    mock_executor = MagicMock(spec=ThreadPoolExecutor)
    mock_executor_cls.return_value = mock_executor

    on_pressed = MagicMock()
    on_released = MagicMock()
    ButtonHandler(10, on_pressed, on_released)

    # when_pressed is partial(dispatch_async, executor, logged_pressed)
    press_dispatch = mock_button.when_pressed
    press_dispatch()

    mock_executor.submit.assert_called()
    submitted_fn = mock_executor.submit.call_args[0][0]
    submitted_fn()
    on_pressed.assert_called_once()


@patch("handlers.button_handler.ThreadPoolExecutor")
@patch("handlers.button_handler.Button")
def test_context_manager_closes_button(
    mock_button_cls: MagicMock,
    mock_executor_cls: MagicMock,
) -> None:
    mock_button = MagicMock()
    mock_button_cls.return_value = mock_button
    mock_executor = MagicMock(spec=ThreadPoolExecutor)
    mock_executor_cls.return_value = mock_executor

    with ButtonHandler(10, MagicMock(), MagicMock()):
        pass

    mock_button.close.assert_called_once()
    mock_executor.shutdown.assert_called_once_with(wait=False)
