from typing import Dict
from uuid import UUID

from outputs.fyapi_client import ControlRequest, Device, FYAPIClient, LoginRequest

fy_url = "https://api.fuckyeah.uk"

class FYHandler:
    """
    Authenticated session to one FY device for pattern listing and control commands.
    The device is identified by name, and the session is authenticated by email and password.
    The session is used to list patterns and control the device.
    """

    def __init__(self, email: str, password: str, device_name: str):
        self.fyapi_client = FYAPIClient(fy_url)
        self.fyapi_client.login(LoginRequest(email=email, password=password))
        self.user = self.fyapi_client.get_user()
        self.device = self._get_device_by_name(device_name)

    def _get_device_by_name(self, device_name: str) -> Device:
        devices = self.fyapi_client.get_devices()
        for device in devices.devices:
            if device.name == device_name:
                return device
        raise ValueError(f"Device with name {device_name} not found")
    
    def patterns(self) -> Dict[str, UUID]:
        return {pattern.name: pattern.id for pattern in self.device.patterns}

    def control_device(self, control_request: ControlRequest) -> bool:
        return self.fyapi_client.control(self.device.id, control_request)
    
    def stop(self) -> bool:
        return self.fyapi_client.control(self.device.id, ControlRequest(pattern=None, r1=None, r2=None, speed=0.0, strokeLength=0.01, strokeMin=0.0))
