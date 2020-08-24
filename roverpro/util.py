from typing import Iterable, Tuple


class RoverException(Exception):
    pass


class RoverDeviceNotFound(RoverException):
    def __init__(self, devices_and_failures: Iterable[Tuple[str, Exception]]):
        self.devices_and_failures = devices_and_failures
        super().__init__()
