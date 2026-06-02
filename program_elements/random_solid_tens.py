import random
from typing import List, Tuple

from handlers.level_handler import LevelHandler


class RandomSolidTens:
    """
    Steady-state random TENS level on one or more channels. The state can be used either as on-off, or with a duration.
    As a safety measure, the duration is required even when used for on-off, so that it doesn't run forever if off is not called.
    """

    def __init__(self, level_handlers: List[LevelHandler], max_duration: int = 15):
        self.level_handlers = level_handlers
        self.max_duration = max_duration
        self.level_range = (1, 99)
        self.setting_id = "random_solid_tens"

    def set_range(self, range: Tuple[int, int]):
        self.level_range = range

    def on(self, duration: int = None) -> None:
        if duration is None:
            duration = self.max_duration
        for level_handler in self.level_handlers:
            level_handler.set_id(random.randint(self.level_range[0], self.level_range[1]), duration, self.setting_id)

    def off(self) -> None:
        for level_handler in self.level_handlers:
            level_handler.unset(self.setting_id)
