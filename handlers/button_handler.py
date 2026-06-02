from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from types import TracebackType
from typing import Self, Type

from gpiozero import Button
from loguru import logger

from handlers.callback_dispatch import dispatch_async


class ButtonHandler:
    """GPIO button that runs press and release callbacks on a dedicated thread pool."""

    def __init__(
        self,
        button_pin: int,
        on_pressed: Callable[[], None],
        on_released: Callable[[], None],
        bounce_time: float | None = 0.05,
    ):
        self.button_pin = button_pin
        self.on_pressed = on_pressed
        self.on_released = on_released
        self.button = Button(button_pin, bounce_time=bounce_time)
        workers = 2 # one for press, one for release
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"btn_{button_pin}")

        def logged_pressed() -> None:
            logger.info(f"GPIO {self.button_pin}: pressed")
            on_pressed()

        def logged_released() -> None:
            logger.info(f"GPIO {self.button_pin}: released")
            on_released()

        self.button.when_pressed = partial(dispatch_async, self.executor, logged_pressed)
        self.button.when_released = partial(dispatch_async, self.executor, logged_released)


    def close(self):
        self.button.close()
        self.executor.shutdown(wait=False)
        logger.info(f"GPIO {self.button_pin}: closed")

    def __enter__(self) -> Self:
        return self
    
    def __exit__(self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool:
        self.close()
        return False