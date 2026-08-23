import random
from pathlib import Path

import yaml
from loguru import logger

from handlers.fy_handler import FYHandler
from outputs.fyapi_client import ControlRequest
from program_elements.program import (
    StringParameter,
    IntegerParameter,
    Program,
    RangeParameter,
)

_ROOT = Path(__file__).resolve().parents[1]
_local_config = yaml.safe_load((_ROOT / "local_config.yaml").read_text(encoding="utf-8"))
FY_USER = _local_config["FY_USER"]
FY_PASSWORD = _local_config["FY_PASSWORD"]
FY_DEVICE_NAME = _local_config["FY_DEVICE_NAME"]

class SequentialPatterns(Program):
    """
    This program runs a loop of FY patterns in sequence, with variable speed and duration. It does not require a Raspberry Pi, and can be used from any computer.
    """

    NAME = "Sequential Patterns"

    PARAMETERS = {
        "speed_range": RangeParameter(name="FY speed range for random patterns (%)", min_value=1, max_value=100, default_value=(50, 100)),
        "duration_range": RangeParameter(name="FY duration range for random patterns (seconds)", min_value=15, max_value=3600, default_value=(15, 60)),
        "pattern_list": StringParameter(name="Comma-separated list of FY patterns", default_value="Smooth, Vibe, Tease, Thrusting"),
        "start_delay": IntegerParameter(name="Start delay (seconds)", min_value=0, max_value=100, default_value=0),
    }

    def __init__(self):
        super().__init__()

    def run(self) -> None:
        pattern_list = self.get_parameter("pattern_list").split(",")
        pattern_list = [pattern.strip() for pattern in pattern_list]
        fy_handler = FYHandler(FY_USER, FY_PASSWORD, FY_DEVICE_NAME)
        try:
            try:
                pattern_ids = [fy_handler.patterns()[pattern] for pattern in pattern_list]
            except KeyError as e:
                logger.error(f"Pattern not found: {e}")
                raise ValueError(f"Pattern not found: {e}") from e

            start_delay = self.get_parameter("start_delay")
            if start_delay > 0:
                logger.info(f"Waiting {start_delay} seconds before starting...")
                self.main_stop_event.wait(timeout=start_delay)
                if self.main_stop_event.is_set():
                    logger.info("Stop event received, not starting...")
                    return

            while not self.main_stop_event.is_set():
                for pattern_id in pattern_ids:
                    speed_range = self.get_parameter("speed_range")
                    duration_range = self.get_parameter("duration_range")
                    speed = round(random.uniform(speed_range[0]/100, speed_range[1]/100), 2)
                    duration = random.randint(duration_range[0], duration_range[1])
                    logger.info(f"Changing mode to {pattern_id} with speed {speed} for {duration} seconds")
                    fy_handler.control_device(ControlRequest(pattern=pattern_id, speed=speed, strokeLength=1.0, strokeMin=0.0))
                    self.main_stop_event.wait(timeout=duration)
                    if self.main_stop_event.is_set():
                        logger.info("Stop event received, stopping...")
                        break
        finally:
            fy_handler.stop()
            logger.info("Program stopped")
