from typing import Iterable, Tuple


class OpenRoverException(Exception):
    pass


class RoverDeviceNotFound(OpenRoverException):
    def __init__(self, devices_and_failures: Iterable[Tuple[str, Exception]]):
        self.devices_and_failures = devices_and_failures
        super().__init__()
