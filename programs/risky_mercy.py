import random
import threading
from functools import partial
from pathlib import Path
from time import time

import yaml
from loguru import logger

from handlers.boolean_handler import BooleanHandler
from handlers.button_handler import ButtonHandler
from handlers.level_handler import LevelHandler
from outputs.pumps.pump_HR8825 import PumpHR8825
from outputs.tens.tens_et312 import TensET312
from program_elements.fy_mercy_punish import FYMercyPunish
from program_elements.program import (
    BooleanParameter,
    EnumParameter,
    StringParameter,
    IntegerParameter,
    Program,
    RangeParameter,
)
from program_elements.random_pulsed_tens import RandomPulsedTens
from program_elements.random_solid_tens import RandomSolidTens

_ROOT = Path(__file__).resolve().parents[1]
_local_config = yaml.safe_load((_ROOT / "local_config.yaml").read_text(encoding="utf-8"))
FY_USER = _local_config["FY_USER"]
FY_PASSWORD = _local_config["FY_PASSWORD"]
FY_DEVICE_NAME = _local_config["FY_DEVICE_NAME"]

FYAUX1 = 14
FYAUX2 = 10
BUTTON_1 = 8
BUTTON_2 = 5

class RiskyMercy(Program):
    """
    This program runs a loop of random FY patterns with a mild shock and a little lube each time it changes, plus lube and shock based on the aux outputs of the pattern.
    It also has a mercy button that interrupts the loop with a slow mode and lots of lube, followed by a penalty mode (hard, fast, and with more intense shocks).
    But the danger is that every press of the mercy button runs the risk of triggering a punishment mode instead, which is an extended version of the penalty mode with
    more intense shocks and a heavy dose of hot sauce instead of lube. The more recent the last request for mercy, the higher the risk of punishment.
    """

    NAME = "Risky Mercy"

    PARAMETERS = {
        "speed_range": RangeParameter(name="FY speed range for random patterns (%)", min_value=1, max_value=100, default_value=(50, 100)),
        "duration_range": RangeParameter(name="FY duration range for random patterns (seconds)", min_value=15, max_value=3600, default_value=(15, 60)),
        "mercy_pattern": StringParameter(name="Mercy mode pattern", default_value="Mercy"),
        "penalty_pattern": StringParameter(name="Penalty mode pattern", default_value="Penalty"),
        "punish_pattern": StringParameter(name="Punishment mode pattern", default_value="Penalty"),
        "base_punishment_risk": IntegerParameter(name="Base punishment risk (%)", min_value=0, max_value=100, default_value=20),
        "mercy_cooldown": IntegerParameter(name="Mercy cooldown (seconds)", min_value=1, max_value=3600, default_value=480),
        "mercy_gradual_cooldown": BooleanParameter(name="Mercy gradual cooldown", default_value=True),
        "first_mercy": EnumParameter(name="First mercy", values=["Free", "Base", "Delayed"], default_value="Free"),
        "mercy_duration": RangeParameter(name="Mercy duration (seconds)", min_value=15, max_value=3600, default_value=(15, 60)),
        "mercy_penalty_multiplier": IntegerParameter(name="Mercy penalty multiplier", min_value=1, max_value=10, default_value=1),
        "punishment_duration": IntegerParameter(name="Punishment duration (seconds)", min_value=15, max_value=3600, default_value=120),
        "pulsed_tens_channel": EnumParameter(name="Pulsed tens channel", values=["A", "B", "Both", "None"], default_value="A"),
        "aux_tens_channel": EnumParameter(name="Aux-driven tens channel", values=["A", "B", "Both", "None"], default_value="A"),
        "default_pulsed_tens_range": RangeParameter(name="Default pulsed tens range (1-127)", min_value=1, max_value=127, default_value=(50, 80)),
        "default_aux_tens_range": RangeParameter(name="Default aux-driven tens range (1-127)", min_value=1, max_value=127, default_value=(60, 90)),
        "penalty_pulsed_tens_range": RangeParameter(name="Penalty pulsed tens range (1-127)", min_value=1, max_value=127, default_value=(70, 90)),
        "penalty_aux_tens_range": RangeParameter(name="Penalty aux-drive tens range (1-127)", min_value=1, max_value=127, default_value=(80, 100)),
        "punishment_pulsed_tens_range": RangeParameter(name="Punishment pulsed tens range (1-127)", min_value=1, max_value=127, default_value=(80, 100)),
        "punishment_aux_tens_range": RangeParameter(name="Punishment aux-driven tens range (1-127)", min_value=1, max_value=127, default_value=(90, 110)),
        "penalty_pulsed_tens_on_duration": RangeParameter(name="Penalty pulsed tens on duration (seconds)", min_value=1, max_value=15, default_value=(1, 3)),
        "penalty_pulsed_tens_off_duration": RangeParameter(name="Penalty pulsed tens off duration (seconds)", min_value=1, max_value=15, default_value=(1, 3)),
        "punishment_pulsed_tens_on_duration": RangeParameter(name="Punishment pulsed tens on duration (seconds)", min_value=1, max_value=15, default_value=(2, 6)),
        "punishment_pulsed_tens_off_duration": RangeParameter(name="Punishment pulsed tens off duration (seconds)", min_value=1, max_value=15, default_value=(1, 3)),
        "mercy_lube_pump_duration": IntegerParameter(name="Lube pump duration on mercy (seconds)", min_value=1, max_value=3600, default_value=15),
        "random_lube_pump_duration": IntegerParameter(name="Lube pump duration on change of random mode (seconds)", min_value=0, max_value=3600, default_value=2),
        "punishment_hot_sauce_pump_duration": IntegerParameter(name="Hot sauce pump duration on punishment (seconds)", min_value=0, max_value=3600, default_value=20),
        "random_shock_length_range": RangeParameter(name="Shock length range on change of random mode (seconds)", min_value=0, max_value=15, default_value=(1, 8)),
    }

    def __init__(self):
        super().__init__()

    def run(self) -> None:
        with (
            PumpHR8825("A") as lube_pump,
            PumpHR8825("B") as hot_sauce_pump,
            TensET312() as tens_unit,
            BooleanHandler("lube_pump", lube_pump.run, lube_pump.stop) as lube_pump_handler,
            BooleanHandler("hot_sauce_pump", hot_sauce_pump.run, hot_sauce_pump.stop) as hot_sauce_pump_handler,
            LevelHandler("tens_handler_a", partial(tens_unit.set, "a")) as tens_handler_a,
            LevelHandler("tens_handler_b", partial(tens_unit.set, "b")) as tens_handler_b,
        ):
            if self.get_parameter("pulsed_tens_channel") == "A":
                random_pulsed_tens = RandomPulsedTens([tens_handler_a])
            elif self.get_parameter("pulsed_tens_channel") == "B":
                random_pulsed_tens = RandomPulsedTens([tens_handler_b])
            elif self.get_parameter("pulsed_tens_channel") == "Both":
                random_pulsed_tens = RandomPulsedTens([tens_handler_a, tens_handler_b])
            else:
                random_pulsed_tens = RandomPulsedTens([])
            if self.get_parameter("aux_tens_channel") == "A":
                random_solid_tens = RandomSolidTens([tens_handler_a])
            elif self.get_parameter("aux_tens_channel") == "B":
                random_solid_tens = RandomSolidTens([tens_handler_b])
            elif self.get_parameter("aux_tens_channel") == "Both":
                random_solid_tens = RandomSolidTens([tens_handler_a, tens_handler_b])
            else:
                random_solid_tens = RandomSolidTens([])
            random_solid_tens.set_range(self.get_parameter("default_aux_tens_range"))
            
            def mercy_callback() -> None:
                random_pulsed_tens.set_range(self.get_parameter("default_pulsed_tens_range"))
                random_solid_tens.set_range(self.get_parameter("default_aux_tens_range"))
                random_pulsed_tens.off()
                random_solid_tens.off()
                lube_pump_handler.set(self.get_parameter("mercy_lube_pump_duration"))

            def penalty_callback() -> None:
                random_pulsed_tens.set_range(self.get_parameter("penalty_pulsed_tens_range"))
                random_pulsed_tens.set_on_duration(self.get_parameter("penalty_pulsed_tens_on_duration"))
                random_pulsed_tens.set_off_duration(self.get_parameter("penalty_pulsed_tens_off_duration"))
                random_pulsed_tens.on()
                random_solid_tens.set_range(self.get_parameter("penalty_aux_tens_range"))
            
            def punish_callback() -> None:
                hot_sauce_pump_handler.set(self.get_parameter("punishment_hot_sauce_pump_duration"))
                random_pulsed_tens.set_range(self.get_parameter("punishment_pulsed_tens_range"))
                random_pulsed_tens.set_on_duration(self.get_parameter("punishment_pulsed_tens_on_duration"))
                random_pulsed_tens.set_off_duration(self.get_parameter("punishment_pulsed_tens_off_duration"))
                random_pulsed_tens.on()
                random_solid_tens.set_range(self.get_parameter("punishment_aux_tens_range"))
            
            def normal_callback() -> None:
                random_pulsed_tens.off()
                random_solid_tens.off()
                random_pulsed_tens.set_range(self.get_parameter("default_pulsed_tens_range"))
                random_solid_tens.set_range(self.get_parameter("default_aux_tens_range"))
            
            def random_callback() -> None:
                shock_length = random.randint(self.get_parameter("random_shock_length_range")[0], self.get_parameter("random_shock_length_range")[1])
                lube_pump_handler.set(self.get_parameter("random_lube_pump_duration"))
                random_solid_tens.on(shock_length + 1)

            fy_mercy_punish = FYMercyPunish(
                user=FY_USER,
                password=FY_PASSWORD,
                device_name=FY_DEVICE_NAME,
                mercy_mode=self.get_parameter("mercy_pattern"),
                penalty_mode=self.get_parameter("penalty_pattern"),
                punish_mode=self.get_parameter("punish_pattern"),
                speed_range=self.get_parameter("speed_range"),
                duration_range=self.get_parameter("duration_range"),
                mercy_mode_callback=mercy_callback,
                penalty_mode_callback=penalty_callback,
                punish_mode_callback=punish_callback,
                normal_mode_callback=normal_callback,
                mode_change_callback=random_callback,
            )

            mercy_request_lock = threading.Lock()
            mercy_cooldown = self.get_parameter("mercy_cooldown")
            if self.get_parameter("first_mercy") == "Free":
                last_mercy_time: float | None = None
            elif self.get_parameter("first_mercy") == "Base":
                last_mercy_time: float = time() - mercy_cooldown
            else:
                last_mercy_time: float = time()
            started = False

            def request_mercy() -> None:
                """Pause the normal-mode loop, run mercy_mode, then resume normal_mode."""
                nonlocal last_mercy_time
                if not started:
                    logger.info("Mercy ignored: program not started")
                    return
                with mercy_request_lock:
                    logger.info("Requesting mercy")
                    try:
                        base_punishment_risk = self.get_parameter("base_punishment_risk")
                        if last_mercy_time is not None:
                            time_since_last_mercy = time() - last_mercy_time
                            cooldown_ratio = max(
                                0.0,
                                min(1.0, (mercy_cooldown - time_since_last_mercy) / mercy_cooldown),
                            )
                            if self.get_parameter("mercy_gradual_cooldown"):
                                punishment_risk = base_punishment_risk + cooldown_ratio * (100 - base_punishment_risk)
                            elif cooldown_ratio > 0.001:
                                punishment_risk = 100
                            else:
                                punishment_risk = base_punishment_risk
                            logger.info(f"Time since last mercy: {time_since_last_mercy}")
                        else:
                            logger.info("No previous mercy")
                            punishment_risk = 0
                        logger.info(f"Punishment risk: {punishment_risk}")
                        risk = random.uniform(1, 100)
                        if risk <= punishment_risk:
                            logger.info(f"Rolled {risk}, Punishing.")
                            fy_mercy_punish.punish(self.get_parameter("punishment_duration"))
                        else:
                            last_mercy_time = time()
                            logger.info(f"Rolled {risk}, Mercying.")
                            mercy_duration = random.randint(self.get_parameter("mercy_duration")[0], self.get_parameter("mercy_duration")[1])
                            penalty_multiplier = self.get_parameter("mercy_penalty_multiplier")
                            fy_mercy_punish.mercy_and_penalty(mercy_duration, mercy_duration * penalty_multiplier)
                    except Exception:
                        logger.exception(f"Error in mercy mode")

            def on_start_pressed() -> None:
                nonlocal started
                if not started:
                    logger.info("Button pressed, starting...")
                    started = True
                    fy_mercy_punish.start()
                else:
                    logger.info("Button pressed, stopping...")
                    started = False
                    fy_mercy_punish.stop()
                    random_pulsed_tens.off()
                    random_solid_tens.off()
                    lube_pump_handler.unset_all()
                    hot_sauce_pump_handler.unset_all()
            

            with (
                ButtonHandler(FYAUX1, partial(lube_pump_handler.set_id, 60, "aux1"), partial(lube_pump_handler.unset, "aux1")),
                ButtonHandler(FYAUX2, random_solid_tens.on, random_solid_tens.off),
                ButtonHandler(BUTTON_2, request_mercy, lambda: None),
                ButtonHandler(BUTTON_1, on_start_pressed, lambda: None),
            ):
                try:
                    logger.info("Waiting for start button (GPIO 14)...")
                    self.main_stop_event.wait()
                except KeyboardInterrupt:
                    logger.info("Exiting...")
                    fy_mercy_punish.stop()
                    random_pulsed_tens.off()
                    random_solid_tens.off()
                    lube_pump_handler.unset_all()
                    hot_sauce_pump_handler.unset_all()
