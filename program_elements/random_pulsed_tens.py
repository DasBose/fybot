import random
import threading
from typing import List, Tuple

from loguru import logger

from handlers.level_handler import LevelHandler


class RandomPulsedTens:
    """
    Stochastic on/off TENS pulser on one or more channels. Each pulse is a random, followed by a random off duration.
    """

    def __init__(self, level_handlers: List[LevelHandler]):
        self.level_handlers = level_handlers
        self.level_range = (1, 99)
        self.setting_id = "random_pulsed_tens"
        self.on_duration = (1, 10)
        self.off_duration = (1, 10)
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []

    def set_range(self, range: Tuple[int, int]):
        self.level_range = range

    def set_on_duration(self, range: Tuple[int, int]):
        self.on_duration = range

    def set_off_duration(self, range: Tuple[int, int]):
        self.off_duration = range

    def _sleep(self, duration: float) -> bool:
        return self._stop.wait(timeout=duration)

    def _loop(self, level_handler: LevelHandler) -> None:
        while not self._stop.is_set():
            level = random.randint(self.level_range[0], self.level_range[1])
            on_time = random.uniform(self.on_duration[0], self.on_duration[1])
            safety_duration = max(self.on_duration) + 1
            level_handler.set_id(level, safety_duration, self.setting_id)
            if self._sleep(on_time):
                break
            level_handler.unset(self.setting_id)
            off_time = random.uniform(self.off_duration[0], self.off_duration[1])
            if self._sleep(off_time):
                break
        level_handler.unset(self.setting_id)

    def on(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return
        self._stop.clear()
        for level_handler in self.level_handlers:
            thread = threading.Thread(target=self._loop, args=(level_handler,), daemon=True)
            thread.start()
            self._threads.append(thread)

    def off(self) -> None:
        self._stop.set()
        if any(thread.is_alive() for thread in self._threads):
            for thread in self._threads:
                thread.join(timeout=30)
                if thread.is_alive():
                    logger.warning(f"Timed out waiting for {thread.name} to stop")
        self._threads = []
        for level_handler in self.level_handlers:
            level_handler.unset(self.setting_id)
