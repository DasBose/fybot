import threading
from types import TracebackType
from typing import Self, Type

from loguru import logger

from outputs.hardware.HR8825 import HR8825

PUMP_CONFIG = {
    "A": {
        "dir_pin": 13,
        "step_pin": 19,
        "enable_pin": 12,
        "mode_pins": (16, 17, 20)
    },
    "B": {
        "dir_pin": 24,
        "step_pin": 18,
        "enable_pin": 4,
        "mode_pins": (21, 22, 27)
    }
}

class PumpHR8825:
    """Stepper pump on channels A or B using :class:`HR8825` hardware."""

    def __init__(self, pump_id: str):
        self.pump_id = pump_id
        self.pump_config = PUMP_CONFIG[pump_id]
        dir_pin = self.pump_config["dir_pin"]
        step_pin = self.pump_config["step_pin"]
        enable_pin = self.pump_config["enable_pin"]
        mode_pins = self.pump_config["mode_pins"]
        self.hr8825 = HR8825(dir_pin, step_pin, enable_pin, mode_pins)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._want_run = False
        self._run_args: tuple[str, float, int] = ("forward", 0.005, 50)
        self._run_thread: threading.Thread | None = None
        self._starter_thread: threading.Thread | None = None

        self.hr8825.SetMicroStep("hardware", "fullstep")

    def dispense(self, cycles: int) -> None:
        steps = cycles * 200 # 200 steps per cycle for fullstep mode (1.8 degree motor)
        self.hr8825.TurnStep(Dir="forward", steps=steps, stepdelay=0.005)

    def run(self) -> None:
        self.stepper_run(direction="forward", stepdelay=0.005, steps_per_chunk=50)

    def stepper_run(self, direction: str = "forward", stepdelay: float = 0.005, steps_per_chunk: int = 50) -> None:
        """Request continuous stepping. Returns immediately without joining prior threads."""
        with self._lock:
            self._want_run = True
            self._run_args = (direction, stepdelay, steps_per_chunk)
            self._stop_event.set()
            self.hr8825.Stop()
            self._ensure_starter_locked()

    def stop(self) -> None:
        with self._lock:
            self._want_run = False
            self._stop_event.set()
            self.hr8825.Stop()

    def close(self) -> None:
        self.stop()
        with self._lock:
            starter = self._starter_thread
            run_thread = self._run_thread
        if starter is not None and starter is not threading.current_thread():
            starter.join(timeout=60.0)
            if starter.is_alive():
                logger.warning(
                    f"PumpHR8825 {self.pump_id}: Timed out waiting for starter thread; leaving hardware open"
                )
                return
        if run_thread is not None and run_thread is not threading.current_thread():
            run_thread.join(timeout=60.0)
            if run_thread.is_alive():
                logger.warning(
                    f"PumpHR8825 {self.pump_id}: Timed out waiting for run thread; leaving hardware open"
                )
                return
            with self._lock:
                if self._run_thread is run_thread:
                    self._run_thread = None
        self.hr8825.close()

    def _ensure_starter_locked(self) -> None:
        if self._starter_thread is not None and self._starter_thread.is_alive():
            return
        self._starter_thread = threading.Thread(
            target=self._restart_loop,
            name=f"pump-{self.pump_id}-starter",
            daemon=True,
        )
        self._starter_thread.start()

    def _restart_loop(self) -> None:
        try:
            while True:
                with self._lock:
                    if not self._want_run:
                        return
                    run_thread = self._run_thread

                if run_thread is not None and run_thread.is_alive():
                    run_thread.join(timeout=60.0)
                    if run_thread.is_alive():
                        logger.warning(
                            f"PumpHR8825 {self.pump_id}: Timed out waiting for run thread; not starting another"
                        )
                        with self._lock:
                            self._want_run = False
                        return

                with self._lock:
                    if self._run_thread is run_thread:
                        self._run_thread = None
                    if not self._want_run:
                        return

                    direction, stepdelay, steps_per_chunk = self._run_args
                    self._stop_event.clear()

                    def _loop(
                        dir_: str = direction,
                        delay: float = stepdelay,
                        chunk: int = steps_per_chunk,
                    ) -> None:
                        while not self._stop_event.is_set():
                            self.hr8825.TurnStep(Dir=dir_, steps=chunk, stepdelay=delay)

                    self._run_thread = threading.Thread(
                        target=_loop,
                        name=f"pump-{self.pump_id}-run",
                        daemon=True,
                    )
                    self._run_thread.start()
                    return
        finally:
            with self._lock:
                if self._starter_thread is threading.current_thread():
                    self._starter_thread = None
                # Cover the race where run() saw this starter still alive and skipped
                # spawning another, then we exit while a start is still desired.
                if not self._want_run:
                    return
                run_alive = (
                    self._run_thread is not None and self._run_thread.is_alive()
                )
                needs_start = self._stop_event.is_set() or not run_alive
                if needs_start and (
                    self._starter_thread is None or not self._starter_thread.is_alive()
                ):
                    self._ensure_starter_locked()

    def __enter__(self) -> Self:
        return self
    
    def __exit__(self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool:
        self.close()
        return False
