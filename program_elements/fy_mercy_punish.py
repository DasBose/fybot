import threading
from collections.abc import Callable

from loguru import logger

from outputs.fyapi_client import ControlRequest
from program_elements.fy_random import FYRandom


class FYMercyPunish(FYRandom):
    """FYRandom extended with mercy, penalty, and punish modes (which refer to specified FY patterns), plus callbacks for each mode."""

    _callback_max_workers: int = 8

    def __init__(
        self,
        user: str,
        password: str,
        device_name: str,
        mercy_mode: str,
        penalty_mode: str,
        punish_mode: str,
        speed_range: tuple[int, int] = (50, 100),
        duration_range: tuple[int, int] = (15, 60),
        included_patterns: list[str] | None = None,
        excluded_patterns: list[str] | None = None,
        mode_change_callback: Callable[[], None] | None = None,
        mercy_mode_callback: Callable[[], None] | None = None,
        penalty_mode_callback: Callable[[], None] | None = None,
        punish_mode_callback: Callable[[], None] | None = None,
        normal_mode_callback: Callable[[], None] | None = None,
    ):
        excluded_modes = [mercy_mode, penalty_mode, punish_mode]
        parent_excluded_patterns = list(excluded_patterns or []) + excluded_modes
        super().__init__(
            user,
            password,
            device_name,
            speed_range,
            duration_range,
            included_patterns,
            parent_excluded_patterns,
            mode_change_callback,
        )
        available_patterns = self.fy_handler.patterns()
        missing_modes = [pattern for pattern in [mercy_mode, penalty_mode, punish_mode] if pattern not in available_patterns]
        if missing_modes:
            raise ValueError(
                f"Pattern(s) not found in {self.device_name}: {', '.join(missing_modes)}"
            )
        self.mercy_mode = available_patterns[mercy_mode]
        self.penalty_mode = available_patterns[penalty_mode]
        self.punish_mode = available_patterns[punish_mode]
        self.mercy_mode_callback = mercy_mode_callback
        self.penalty_mode_callback = penalty_mode_callback
        self.punish_mode_callback = punish_mode_callback
        self.normal_mode_callback = normal_mode_callback

        self.locks = {
            "special_mode": threading.Lock(),
        }

    def _abort_special_mode(self, session: int, phase: str) -> None:
        logger.info(f"{self.device_name}: Aborting {phase} (session {session} != {self._session_id})")
        self._run_callback_sync(self.normal_mode_callback)
        self.fy_handler.stop()

    def _finish_special_mode(self, session: int) -> None:
        logger.info(f"{self.device_name}: Resuming normal mode")
        self.flags["normal_running"].set()
        self._run_callback_sync(self.normal_mode_callback)

    def _mercy_and_penalty(self, session: int, mercy_duration: int, penalty_duration: int) -> None:
        with self.locks["special_mode"]:
            logger.info(f"Pausing normal mode on {self.device_name}")
            self.flags["normal_running"].clear()
            self.flags["normal_paused"].wait()
            if not self._session_valid(session):
                self._abort_special_mode(session, "mercy and penalty")
                return
            logger.info(f"{self.device_name}: Running mercy mode for {mercy_duration} seconds")
            self.fy_handler.control_device(ControlRequest(pattern=self.mercy_mode, speed=0.5, strokeLength=1.0, strokeMin=0.0))
            self._dispatch_callback(self.mercy_mode_callback, session=session)
            self.flags["stop"].wait(timeout=mercy_duration)
            if not self._session_valid(session):
                self._abort_special_mode(session, "mercy")
                return
            logger.info(f"{self.device_name}: Running penalty mode for {penalty_duration} seconds")
            self.fy_handler.control_device(ControlRequest(pattern=self.penalty_mode, speed=1.0, strokeLength=1.0, strokeMin=0.0))
            self._dispatch_callback(self.penalty_mode_callback, session=session)
            self.flags["stop"].wait(timeout=penalty_duration)
            if not self._session_valid(session):
                self._abort_special_mode(session, "penalty")
                return
            self._finish_special_mode(session)

    def _punish(self, session: int, duration: int) -> None:
        with self.locks["special_mode"]:
            logger.info(f"{self.device_name}: Pausing normal mode")
            self.flags["normal_running"].clear()
            self.flags["normal_paused"].wait()
            if not self._session_valid(session):
                self._abort_special_mode(session, "punish")
                return
            logger.info(f"{self.device_name}: Running punish mode for {duration} seconds")
            self.fy_handler.control_device(ControlRequest(pattern=self.punish_mode, speed=1.0, strokeLength=1.0, strokeMin=0.0))
            self._dispatch_callback(self.punish_mode_callback, session=session)
            self.flags["stop"].wait(timeout=duration)
            if not self._session_valid(session):
                self._abort_special_mode(session, "punish")
                return
            self._finish_special_mode(session)
    
    def mercy_and_penalty(self, mercy_duration: int, penalty_duration: int) -> None:
        session = self._session_id
        threading.Thread(
            target=self._mercy_and_penalty,
            args=(session, mercy_duration, penalty_duration),
            daemon=True,
        ).start()
    
    def punish(self, duration: int) -> None:
        session = self._session_id
        threading.Thread(
            target=self._punish,
            args=(session, duration),
            daemon=True,
        ).start()