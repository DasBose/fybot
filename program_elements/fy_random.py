import random
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from time import sleep

from loguru import logger

from handlers.callback_dispatch import dispatch_async
from handlers.fy_handler import FYHandler
from outputs.fyapi_client import ControlRequest


class FYRandom:
    """Background loop that plays random FY patterns with pausable sessions and optional mode-change callbacks."""

    _callback_max_workers: int = 4

    def __init__(
        self,
        user: str,
        password: str,
        device_name: str,
        speed_range: tuple[int, int] = (50, 100),
        duration_range: tuple[int, int] = (15, 60),
        included_patterns: list[str] | None = None,
        excluded_patterns: list[str] | None = None,
        mode_change_callback: Callable[[], None] | None = None,
    ):
        self.user = user
        self.password = password
        self.device_name = device_name
        self.fy_handler = FYHandler(user, password, device_name)
        self.speed_range = speed_range
        self.duration_range = duration_range
        self.mode_change_callback = mode_change_callback
        self._callback_executor: ThreadPoolExecutor | None = None
        self.thread: threading.Thread | None = None
        self._session_id = 0

        self.flags = {
            "normal_running": threading.Event(),
            "normal_paused": threading.Event(),
            "stop": threading.Event(),
        }
        self.flags["normal_running"].set()

        excluded_set = set(excluded_patterns or [])
        available_patterns = self.fy_handler.patterns()

        if included_patterns is None:
            self.random_patterns = [available_patterns[p] for p in available_patterns.keys() if p not in excluded_set]
        else:
            selected_patterns = [pattern for pattern in included_patterns if pattern not in excluded_set]
            missing_patterns = [pattern for pattern in selected_patterns if pattern not in available_patterns]
            if missing_patterns:
                missing = ", ".join(missing_patterns)
                raise ValueError(f"Pattern(s) not found in {self.device_name}: {missing}")
            self.random_patterns = [available_patterns[pattern] for pattern in selected_patterns]

        if not self.random_patterns:
            raise ValueError(
                f"No patterns available for random mode on {self.device_name}"
            )

    def _ensure_callback_executor(self) -> None:
        if self._callback_executor is None:
            self._callback_executor = ThreadPoolExecutor(
                max_workers=self._callback_max_workers,
                thread_name_prefix=f"fy_cb_{self.device_name}",
            )

    def _shutdown_callback_executor(self) -> None:
        if self._callback_executor is not None:
            self._callback_executor.shutdown(wait=False, cancel_futures=True)
            self._callback_executor = None

    def _session_valid(self, session: int) -> bool:
        return session == self._session_id

    def _run_callback_sync(self, callback: Callable[[], None] | None) -> None:
        if callback is not None:
            callback()

    def _dispatch_callback(self, callback: Callable[[], None] | None, session: int | None = None) -> None:
        """Run a user callback on the program's thread pool without blocking the caller."""
        if callback is not None and self._callback_executor is not None:
            target_session = self._session_id if session is None else session

            def guarded_callback() -> None:
                if not self._session_valid(target_session):
                    logger.debug(f"Skipping stale callback on {self.device_name} for session {target_session}")
                    return
                callback()

            dispatch_async(self._callback_executor, guarded_callback)

    def _normal_mode(self) -> None:
        run_session = self._session_id
        while not self.flags["stop"].is_set():
            while not self.flags["normal_running"].is_set():
                if self.flags["stop"].is_set():
                    break
                self.flags["normal_paused"].set()
                logger.info(f"Pausing normal mode on {self.device_name}")
                while not self.flags["normal_running"].is_set() and not self.flags["stop"].is_set():
                    self.flags["normal_running"].wait(timeout=1)
                self.flags["normal_paused"].clear()
            if self.flags["stop"].is_set():
                break
            control_request = self._random_control_request()
            duration = random.randint(self.duration_range[0], self.duration_range[1])
            logger.info(f"Changing mode to {control_request.pattern} with speed {control_request.speed} for {duration} seconds")
            self.fy_handler.control_device(control_request)
            if self.flags["stop"].is_set():
                break
            self._dispatch_callback(self.mode_change_callback, session=run_session)
            
            for i in range(duration):
                if self.flags["stop"].is_set():
                    break
                if not self.flags["normal_running"].is_set():
                    break
                sleep(1)
        self.fy_handler.stop()
    
    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError(
                f"Cannot start {self.device_name}: previous run still active; call stop() first"
            )
        logger.info(f"Starting {self.device_name}")
        self._ensure_callback_executor()
        self._session_id += 1
        self.flags["normal_paused"].clear()
        self.flags["stop"].clear()
        self.flags["normal_running"].set()
        self.thread = threading.Thread(target=self._normal_mode, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self._session_id += 1
        self.flags["stop"].set()
        if self.thread is None or not self.thread.is_alive():
            self._shutdown_callback_executor()
            self.fy_handler.stop()
            return
        logger.info(f"Stopping {self.device_name}")
        self.thread.join(timeout=120)
        if self.thread.is_alive():
            logger.warning(f"Timed out waiting for {self.device_name} thread to stop")
        self.thread = None
        self._shutdown_callback_executor()
        self.fy_handler.stop()

    def _random_control_request(self) -> ControlRequest:
        return ControlRequest(pattern=random.choice(self.random_patterns), speed=round(random.uniform(self.speed_range[0]/100, self.speed_range[1]/100), 2), strokeLength=1.0, strokeMin=0.0)
        
