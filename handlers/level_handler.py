import threading
import uuid
from collections.abc import Callable
from loguru import logger
from types import TracebackType
from typing import Self, Type

class LevelHandler:
    """
    A handler for combining multiple signals into a single effective level.
    The effective level is the max of all active settings.

    The duration is in seconds. All public methods are synchronized on one lock.
    Timers are started only after state is registered, and only outside the lock,
    so expiry callbacks never deadlock with *set*.
    Durations are required as a safety measure. For on/off behavior, set duration slightly
    longer than the max expected duration. This will prevent the timer from expiring prematurely,
    and from running forever if unset is not called.
    """

    def __init__(self, name: str, callback: Callable[[int], None]) -> None:
        self._lock = threading.RLock()
        self._levels: dict[str, int] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._level = 0
        self._callback = callback
        self._name = name

    def set(self, level: int, duration: int) -> str:
        setting_id = uuid.uuid4().hex

        self.set_id(level, duration, setting_id)
        return setting_id
    
    def set_id(self, level: int, duration: int, id: str) -> None:
        delay = max(0.0, float(duration))

        def expire() -> None:
            with self._lock:
                self._levels.pop(id, None)
                self._timers.pop(id, None)
                self._update()

        with self._lock:
            logger.info(f"{self._name}: Setting level {level} for {id} with duration {delay}")
            if id in self._levels:
                level = max(level, self._levels[id])
            self._levels[id] = level
            if id in self._timers:
                self._timers[id].cancel()
            self._timers[id] = threading.Timer(delay, expire)
            self._timers[id].daemon = True
            self._timers[id].start()
            self._update()

    def unset(self, setting_id: str) -> None:
        with self._lock:
            logger.info(f"{self._name}: Unsetting level for {setting_id}")
            self._levels.pop(setting_id, None)
            timer = self._timers.pop(setting_id, None)
            self._update()
        if timer is not None:
            timer.cancel()

    def unset_all(self) -> None:
        with self._lock:
            logger.info(f"{self._name}: Unsetting all levels")
            timers = list(self._timers.values())
            self._levels.clear()
            self._timers.clear()
            self._update()
        for t in timers:
            t.cancel()

    def get(self) -> int:
        return self._level
    
    def _update(self) -> None:
        with self._lock:
            current = self._level
            new = 0
            if self._levels:
                new = max(self._levels.values())
            if new != current:
                self._level = new
                logger.info(f"{self._name}: Level is now {new}")
                self._callback(new)
    
    def close(self) -> None:
        with self._lock:
            logger.info(f"{self._name}: Closing handler")
            for timer in self._timers.values():
                timer.cancel()
            self._callback(0)

    def __enter__(self) -> Self:
        return self
    
    def __exit__(self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool:
        self.close()
        return False