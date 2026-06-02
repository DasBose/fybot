from types import TracebackType
from typing import Protocol, Self, Type


class Tens(Protocol):
    """Protocol for a TENS unit with per-channel levels and context-manager lifecycle."""

    def set(self, channel: str, level: int, duration: int = 0) -> None:
        ...
    
    def close(self) -> None:
        ...
 
    def __enter__(self) -> Self:
        ...
    
    def __exit__(self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool:
        ...
