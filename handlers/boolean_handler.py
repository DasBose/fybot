from collections.abc import Callable
import uuid
from handlers.level_handler import LevelHandler


class BooleanHandler(LevelHandler):
    """A variant of :class:`LevelHandler` that combines multiple signals into a single effective boolean value.
    All settings indicate 'on' for their duration or until unset. Use unset_all() to clear all settings."""

    def __init__(self, name: str, on_callback: Callable[[], None], off_callback: Callable[[], None]) -> None:
        super().__init__(name, lambda level: on_callback() if level != 0 else off_callback())

    def set(self, duration: int) -> str:
        setting_id = uuid.uuid4().hex
        self.set_id(duration, setting_id)
        return setting_id

    def set_id(self, duration: int, id: str) -> None:
        super().set_id(1, duration, id)

    def get(self) -> bool:
        return super().get() != 0
