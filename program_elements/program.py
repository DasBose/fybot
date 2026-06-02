from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Union

import threading


class IntegerParameter:
    """Configurable integer setting with inclusive min/max validation."""

    def __init__(self, name: str, min_value: int, max_value: int, default_value: int):
        self.name = name
        self.min_value = min_value
        self.max_value = max_value
        self.value = default_value

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
        self.value = default_value

    def set_value(self, value: bool):
        self.value = value

    def get_value(self) -> bool:
        return self.value

class EnumParameter:
    """Configurable choice from a fixed set of string values."""

    def __init__(self, name: str, values: List[str], default_value: str):
        self.name = name
        self.values = set(values)
        self.value = default_value

    def set_value(self, value: str):
        if value not in self.values:
            raise ValueError(f"Invalid value {value} for parameter {self.name}")
        self.value = value

    def get_value(self) -> str:
        return self.value

class RangeParameter:
    """Configurable inclusive integer range stored as (min, max)."""

    def __init__(self, name: str, min_value: int, max_value: int, default_value: Tuple[int, int]):
        self.name = name
        self.min_value = min_value
        self.max_value = max_value
        self.value = default_value

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
    
    def set_parameter(self, name: str, value: int | bool | str | Tuple[int, int]) -> None:
        self.PARAMETERS[name].set_value(value)
    
    def get_parameter(self, name: str) -> int | bool | str | Tuple[int, int]:
        return self.PARAMETERS[name].get_value()
    
    @abstractmethod
    def run(self) -> None:
        pass
    
    def stop(self) -> None:
        self.main_stop_event.set()
