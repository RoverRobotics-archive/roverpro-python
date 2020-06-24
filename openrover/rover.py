from typing import Any, Dict, Iterable, Optional

import trio
from async_generator import asynccontextmanager

from openrover.find_device import open_rover_device
from openrover.openrover_data import OPENROVER_DATA_ELEMENTS
from .openrover_protocol import CommandVerb, OpenRoverProtocol
from .serial_trio import SerialTrio
from .util import OpenRoverException


@asynccontextmanager
async def open_rover(path_to_serial: Optional[str] = None):
    args = [] if path_to_serial is None else [path_to_serial]

    async with open_rover_device(*args) as device:
        rover = Rover()
        await rover.set_device(device)
        yield rover


class Rover:
    _motor_left = 0
    _motor_right = 0
    _motor_flipper = 0

    _rover_protocol = None
    _device = None

    def __init__(self):
        """An OpenRover object"""
        self._motor_left = 0
        self._motor_right = 0
        self._motor_flipper = 0
        self._openrover_data_to_memory_channel = {
            i: trio.open_memory_channel(0) for i in OPENROVER_DATA_ELEMENTS.keys()
        }

    async def set_device(self, device: SerialTrio):
        self._device = device
        self._rover_protocol = OpenRoverProtocol(device)

    def set_motor_speeds(self, left, right, flipper):
        assert -1 <= left <= 1
        assert -1 <= right <= 1
        assert -1 <= flipper <= 1
        self._motor_left = left
        self._motor_right = right
        self._motor_flipper = flipper

    def _send_command(self, cmd, arg):
        self._rover_protocol.write_nowait(
            self._motor_left, self._motor_right, self._motor_flipper, cmd, arg
        )

    def send_speed(self):
        self._send_command(CommandVerb.NOP, 0)

    def set_fan_speed(self, fan_speed):
        assert 0 <= fan_speed <= 1
        self._send_command(CommandVerb.SET_FAN_SPEED, int(fan_speed * 240))

    def clear_system_fault(self):
        self._send_command(CommandVerb.CLEAR_SYSTEM_FAULT, 0)

    def flipper_calibrate(self):
        self._send_command(CommandVerb.FLIPPER_CALIBRATE, int(CommandVerb.FLIPPER_CALIBRATE))

    async def get_data(self, index) -> Any:
        """Get the next value for the given data index.
        The type of the returned value depends on the index passed."""
        self._send_command(CommandVerb.GET_DATA, index)
        with trio.fail_after(1):
            k, data = await self._rover_protocol.read_one()
            if k != index:
                raise OpenRoverException(
                    f"Received unexpected data. Expected {index}, received {k}:{data}"
                )

        return data

    async def get_data_items(self, indices: Iterable[int]) -> Dict[int, Any]:
        indices = sorted(set(indices))
        result = dict.fromkeys(indices)

        for index in indices:
            self._send_command(CommandVerb.GET_DATA, index)
        for index in indices:
            with trio.fail_after(1):
                k, data = await self._rover_protocol.read_one()
                if k != index:
                    raise OpenRoverException(
                        "Received unexpected data. Expected {}, received {}:{}".format(
                            index, k, data
                        )
                    )
            result[k] = data

        return result


async def get_openrover_version(port):
    try:
        with trio.fail_after(1):
            async with SerialTrio(port, baudrate=57600) as device:
                orp = OpenRoverProtocol(device)
                for i in range(2):
                    orp.write_nowait(0, 0, 0, CommandVerb.GET_DATA, 40)
                    k, version = await orp.read_one()
                    if k == 40:
                        return version
    except Exception as e:
        raise OpenRoverException("Did not respond to request for OpenRover version") from e
