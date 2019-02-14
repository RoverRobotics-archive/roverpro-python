from typing import Iterable, Sequence, Tuple

from async_generator import asynccontextmanager
from serial.tools.list_ports import comports
import trio

from openrover.serial_trio import SerialTrio
from .openrover_protocol import CommandVerbs, OpenRoverProtocol
from .util import OpenRoverException

DEFAULT_SERIAL_KWARGS = dict(baudrate=57600, stopbits=1)


def get_ftdi_device_paths() -> Sequence[str]:
    ports = []
    for comport in comports():
        if comport.manufacturer != 'FTDI':
            continue
        ports.append(comport.device)

    return ports


def ftdi_device_context() -> SerialTrio:
    """use this as `async with ftdi_device_context() as c:` """
    port = next(iter(get_ftdi_device_paths()))
    return SerialTrio(port, **DEFAULT_SERIAL_KWARGS)


class OpenRoverDeviceNotFoundException(OpenRoverException):
    def __init__(self, devices_and_failures: Iterable[Tuple[str, Exception]]):
        self.devices_and_failures = devices_and_failures
        super().__init__()


async def get_openrover_protocol_version(device: SerialTrio):
    try:
        with trio.fail_after(1):
            orp = OpenRoverProtocol(device)
            while True:
                await orp.write(0, 0, 0, CommandVerbs.GET_DATA, 40)
                k, version = await orp.read_one()
                if k == 40:
                    return version
    except trio.TooSlowError as e:
        raise OpenRoverException(f'Device did not respond to a request for version. Is it on?') from e
    except Exception as e:
        raise OpenRoverException(f'Device did not return a valid openrover version', e) from e


@asynccontextmanager
async def open_any_openrover_device():
    """Enumerates serial devices until it finds on ethat responds to a request for OpenRover version. Returns that device"""
    exc_args = []
    for port in get_ftdi_device_paths():
        async with SerialTrio(port, **DEFAULT_SERIAL_KWARGS) as device:
            try:
                await get_openrover_protocol_version(device)
                yield device
                return
            except Exception as e:
                exc_args.append((port, e))
    raise OpenRoverDeviceNotFoundException(exc_args)
