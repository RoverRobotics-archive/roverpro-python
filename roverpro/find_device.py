from typing import Awaitable, Optional, Sequence

import trio
from async_generator import asynccontextmanager
from serial.tools.list_ports import comports

from roverpro.rover_data import RoverFirmwareVersion
from roverpro.serial_trio import SerialTrio
from roverpro.util import RoverDeviceNotFound
from .rover_protocol import CommandVerb, RoverProtocol
from .util import RoverException

"""Communication settings for connecting to Rover Pro hardware"""
DEFAULT_SERIAL_KWARGS = dict(baudrate=57600, stopbits=1)


def get_ftdi_device_paths() -> Sequence[str]:
    return [comport.device for comport in comports() if comport.manufacturer == "FTDI"]


async def get_rover_protocol_version(device: SerialTrio,) -> Awaitable[RoverFirmwareVersion]:
    try:
        with trio.fail_after(1):
            orp = RoverProtocol(device)
            while True:
                orp.write_nowait(0, 0, 0, CommandVerb.GET_DATA, 40)
                k, version = await orp.read_one()
                if k == 40:
                    return version
    except trio.TooSlowError as e:
        raise RoverException("Device did not respond to a request for version. Is it on?") from e
    except Exception as e:
        raise RoverException("Device did not return a valid version", e) from e


@asynccontextmanager
async def open_rover_device(*ports_to_try: Optional[str]):
    """
    Enumerates serial devices until it finds one that responds to a request for Rover firmware version. Returns that device.
    :param ports_to_try: if provided, the devices to attempt to open (e.g. 'COM3'). Otherwise, all FTDI devices will be attempted
    :return: A SerialTrio device to use as a rover. If no appropriate device is found, will raise a RoverDeviceNotFound exception
    """
    exc_args = []
    for port in ports_to_try or get_ftdi_device_paths():
        async with SerialTrio(port, **DEFAULT_SERIAL_KWARGS) as device:
            try:
                await get_rover_protocol_version(device)
                yield device
                return
            except RoverException as e:
                exc_args.append((port, e))
    raise RoverDeviceNotFound(exc_args)
