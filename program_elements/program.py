from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Dict, List, Tuple, Union

import threading


class BooleanOutput:
    """Named on/off output for IO Test mode."""

    def __init__(
        self,
        name: str,
        set_fn: Callable[[bool], None],
        get_fn: Callable[[], bool] | None = None,
    ):
        self.name = name
        self._set_fn = set_fn
        self._get_fn = get_fn
        self._value = False

    def set_value(self, value: bool) -> None:
        self._value = bool(value)
        self._set_fn(self._value)

    def get_value(self) -> bool:
        if self._get_fn is not None:
            return bool(self._get_fn())
        return self._value


class VariableOutput:
    """Named numeric level output for IO Test mode."""

    def __init__(
        self,
        name: str,
        min_value: int,
        max_value: int,
        set_fn: Callable[[int], None],
        get_fn: Callable[[], int] | None = None,
        default_value: int = 0,
    ):
        self.name = name
        self.min_value = min_value
        self.max_value = max_value
        self._set_fn = set_fn
        self._get_fn = get_fn
        self._value = default_value

    def set_value(self, value: int) -> None:
        if value < self.min_value or value > self.max_value:
            raise ValueError(
                f"Value {value} is out of range for output {self.name} "
                f"({self.min_value}-{self.max_value})"
            )
        self._value = int(value)
        self._set_fn(self._value)

    def get_value(self) -> int:
        if self._get_fn is not None:
            return int(self._get_fn())
        return self._value


class DigitalInput:
    """Named digital input whose state is displayed in IO Test mode."""

    def __init__(self, name: str, get_fn: Callable[[], bool]):
        self.name = name
        self._get_fn = get_fn

    def get_value(self) -> bool:
        return bool(self._get_fn())


class IntegerParameter:
    """Configurable integer setting with inclusive min/max validation."""

    def __init__(self, name: str, min_value: int, max_value: int, default_value: int):
        self.name = name
        self.min_value = min_value
        self.max_value = max_value
        self.set_value(default_value)

    def set_value(self, value: int):
        if value < self.min_value or value > self.max_value:
            raise ValueError(f"Value {value} is out of range for parameter {self.name}")
        self.value = value

    def get_value(self) -> int:
        return self.value

class BooleanParameter:
    """Configurable on/off setting."""

    def __init__(self, name: str, default_value: bool):
        self.name = name
        self.set_value(default_value)

    def set_value(self, value: bool):
        self.value = value

    def get_value(self) -> bool:
        return self.value

class EnumParameter:
    """Configurable choice from a fixed set of string values."""

    def __init__(self, name: str, values: List[str], default_value: str):
        self.name = name
        self.values = set(values)
        self.set_value(default_value)

    def set_value(self, value: str):
        if value not in self.values:
            raise ValueError(f"Invalid value {value} for parameter {self.name}")
        self.value = value

    def get_value(self) -> str:
        return self.value

class StringParameter:
    """Configurable string value."""

    def __init__(self, name: str, default_value: str):
        self.name = name
        self.set_value(default_value)

    def set_value(self, value: str):
        if value is None or value == "":
            raise ValueError(f"Invalid value {value} for parameter {self.name}")
        self.value = str(value)

    def get_value(self) -> str:
        return self.value

class RangeParameter:
    """Configurable inclusive integer range stored as (min, max)."""

    def __init__(self, name: str, min_value: int, max_value: int, default_value: Tuple[int, int]):
        self.name = name
        self.min_value = min_value
        self.max_value = max_value
        self.set_value(default_value)

    def set_value(self, value: Tuple[int, int]):
        if value[0] < self.min_value or value[0] > self.max_value or value[1] < self.min_value or value[1] > self.max_value:
            raise ValueError(f"Value {value} is out of range for parameter {self.name}")
        if value[0] > value[1]:
            raise ValueError(f"Value {value} is invalid: min value must be less or equal to max value for parameter {self.name}")
        self.value = value

    def get_value(self) -> Tuple[int, int]:
        return self.value


class Program(ABC):
    """Abstract base for fybot programs with a PARAMETERS schema and a blocking run() entry point."""

    PARAMETERS: Dict[str, Union[IntegerParameter, BooleanParameter, EnumParameter, RangeParameter]] = {}

    NAME: str = ""

    def __init__(self):
        self.main_stop_event = threading.Event()
        self.io_ready = threading.Event()
        self.boolean_outputs: Dict[str, BooleanOutput] = {}
        self.variable_outputs: Dict[str, VariableOutput] = {}
        self.inputs: Dict[str, DigitalInput] = {}

    def set_parameter(self, name: str, value: int | bool | str | Tuple[int, int]) -> None:
        self.PARAMETERS[name].set_value(value)

    def get_parameter(self, name: str) -> int | bool | str | Tuple[int, int]:
        return self.PARAMETERS[name].get_value()

    def clear_io(self) -> None:
        self.boolean_outputs.clear()
        self.variable_outputs.clear()
        self.inputs.clear()
        self.io_ready.clear()

    @abstractmethod
    def run(self) -> None:
        pass

    def io_test(self) -> None:
        """Open hardware, populate IO channel dicts, set io_ready, then wait on main_stop_event.

        Override in subclasses that support IO Test mode. Default waits with no channels.
        """
        self.io_ready.set()
        try:
            self.main_stop_event.wait()
        finally:
            self.clear_io()

    def start(self) -> None:
        self.main_stop_event.clear()
        self.run()

    def start_io_test(self) -> None:
        self.clear_io()
        self.main_stop_event.clear()
        self.io_test()

    def stop(self) -> None:
        self.main_stop_event.set()
