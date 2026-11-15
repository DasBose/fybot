from dataclasses import dataclass
from typing import Dict, Self, Type
from types import TracebackType
from uuid import UUID

from fuckyeah import Device, FuckYeahClient


@dataclass
class ControlRequest:
    """Payload for a device control command (pattern, speeds, stroke parameters)."""

    pattern: UUID | None = None
    r1: str | None = None
    r2: str | None = None
    speed: float | None = None
    strokeLength: float | None = None
    strokeMin: float | None = None


class FYHandler:
    """
    Authenticated session to one FY device for pattern listing and control commands.
    The device is identified by name, and the session is authenticated by an API token.
    The session is used to list patterns and control the device.
    """

    def __init__(self, token: str, device_name: str):
        self.client = FuckYeahClient(token)
        self.device = self._get_device_by_name(device_name)

    def _get_device_by_name(self, device_name: str) -> Device:
        for device in self.client.list_devices():
            if device.name == device_name:
                return self.client.get_device(device)
        raise ValueError(f"Device with name {device_name} not found")

    def patterns(self) -> Dict[str, str]:
        return {pattern.name: pattern.id for pattern in self.device.patterns or ()}

    def control_device(self, control_request: ControlRequest) -> None:
        pattern = control_request.pattern
        self.client.run_pattern(
            self.device.id,
            pattern_id=None if pattern is None else str(pattern),
            speed=control_request.speed,
            stroke_min=control_request.strokeMin,
            stroke_length=control_request.strokeLength,
            r1=control_request.r1,
            r2=control_request.r2,
        )

    def stop(self) -> None:
        self.client.stop_device(self.device.id)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool:
        self.close()
        return False
