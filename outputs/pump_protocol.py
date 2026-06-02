from types import TracebackType
from typing import Protocol, Self, Type


class Pump(Protocol):
    """Protocol for a dispensable pump with run/stop and context-manager lifecycle."""

    def dispense(self, cycles: int) -> None:
        ...

    def run(self) -> None:
        ...

    def stop(self) -> None:
        ...
    
    def __enter__(self) -> Self:
        ...
    
    def __exit__(self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool:
        ...
