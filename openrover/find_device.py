from typing import Awaitable, Optional, Sequence

import trio
from async_generator import asynccontextmanager
from serial.tools.list_ports import comports

from openrover.openrover_data import OpenRoverFirmwareVersion
from openrover.serial_trio import SerialTrio
from openrover.util import RoverDeviceNotFound
from .openrover_protocol import CommandVerb, OpenRoverProtocol
from .util import OpenRoverException

"""Communication settings for connecting to OpenRover hardware"""
DEFAULT_SERIAL_KWARGS = dict(baudrate=57600, stopbits=1)


def get_ftdi_device_paths() -> Sequence[str]:
    return [comport.device for comport in comports() if comport.manufacturer == "FTDI"]


async def get_openrover_protocol_version(
    device: SerialTrio,
) -> Awaitable[OpenRoverFirmwareVersion]:
    try:
        with trio.fail_after(1):
            orp = OpenRoverProtocol(device)
            while True:
                orp.write_nowait(0, 0, 0, CommandVerb.GET_DATA, 40)
                k, version = await orp.read_one()
                if k == 40:
                    return version
    except trio.TooSlowError as e:
        raise OpenRoverException(
            "Device did not respond to a request for version. Is it on?"
        ) from e
    except Exception as e:
        raise OpenRoverException("Device did not return a valid openrover version", e) from e


@asynccontextmanager
async def open_rover_device(*ports_to_try: Optional[str]):
    """
    Enumerates serial devices until it finds one that responds to a request for OpenRover version. Returns that device.
    :param ports_to_try: if provided, the devices to attempt to open (e.g. 'COM3'). Otherwise, all FTDI devices will be attempted
    :return: A SerialTrio device to use as a rover. If no appropriate device is found, will raise a RoverDeviceNotFound exception
    """
    exc_args = []
    for port in ports_to_try or get_ftdi_device_paths():
        async with SerialTrio(port, **DEFAULT_SERIAL_KWARGS) as device:
            try:
                await get_openrover_protocol_version(device)
                yield device
                return
            except OpenRoverException as e:
                exc_args.append((port, e))
    raise RoverDeviceNotFound(exc_args)
