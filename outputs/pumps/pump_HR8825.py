import threading
from types import TracebackType
from typing import Self, Type

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
        self._stop_event = threading.Event()
        self._run_thread: threading.Thread | None = None

        self.hr8825.SetMicroStep("hardware", "fullstep")

    def dispense(self, cycles: int) -> None:
        steps = cycles * 200 # 200 steps per cycle for fullstep mode (1.8 degree motor)
        self.hr8825.TurnStep(Dir="forward", steps=steps, stepdelay=0.005)

    def run(self) -> None:
        self.stepper_run(direction="forward", stepdelay=0.005, steps_per_chunk=50)

    def stepper_run(self, direction: str = "forward", stepdelay: float = 0.005, steps_per_chunk: int = 50) -> None:
        self._stop_event.set()
        self.hr8825.Stop()
        if self._run_thread is not None:
            self._run_thread.join(timeout=60.0)
            self._run_thread = None

        self._stop_event.clear()

        def _loop():
            while not self._stop_event.is_set():
                self.hr8825.TurnStep(Dir=direction, steps=steps_per_chunk, stepdelay=stepdelay)

        self._run_thread = threading.Thread(target=_loop, daemon=True)
        self._run_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.hr8825.Stop()

    def __enter__(self) -> Self:
        return self
    
    def __exit__(self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool:
        self.stop()
        return False
