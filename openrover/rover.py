import logging
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from async_generator import asynccontextmanager
import trio

from openrover.find_device import open_any_openrover_device
from openrover.openrover_data import OPENROVER_DATA_ELEMENTS
from .openrover_protocol import CommandVerbs, OpenRoverProtocol
from .serial_trio import DeviceClosedException, SerialTrio
from .util import OpenRoverException


@asynccontextmanager
async def open_rover(path_to_serial: Optional[str] = None):
    async with trio.open_nursery() as nursery:
        if path_to_serial is None:
            device_cxt = open_any_openrover_device()
        else:
            device_cxt = SerialTrio(path_to_serial)

        async with device_cxt as device:
            rover = Rover(nursery)
            await rover.set_device(device)
            yield rover


class Rover:
    _motor_left = 0
    _motor_right = 0
    _motor_flipper = 0

    _nursery = None
    _rover_protocol = None
    _openrover_data_to_memory_channel: Mapping[int, Tuple[trio.abc.SendChannel, trio.abc.ReceiveChannel]]

    def __init__(self, nursery):
        """An OpenRover object"""
        self._motor_left = 0
        self._motor_right = 0
        self._motor_flipper = 0
        self._nursery = nursery
        self._openrover_data_to_memory_channel = {i: trio.open_memory_channel(5) for i in OPENROVER_DATA_ELEMENTS.keys()}

    async def set_device(self, device: SerialTrio):
        self._device = device
        self._rover_protocol = OpenRoverProtocol(device)
        self._nursery.start_soon(self.process_messages)

    async def process_messages(self):
        try:
            while True:
                k, v = await self._rover_protocol.read_one()
                try:
                    snd, rcv = self._openrover_data_to_memory_channel[k]
                    snd.send_nowait(v)
                except Exception as e:
                    logging.warning(f"could not handle incoming data {k}:{v} {e}")
        except DeviceClosedException:
            pass

    def set_motor_speeds(self, left, right, flipper):
        assert -1 <= left <= 1
        assert -1 <= right <= 1
        assert -1 <= flipper <= 1
        self._motor_left = left
        self._motor_right = right
        self._motor_flipper = flipper

    async def _send_command(self, cmd, arg):
        await self._rover_protocol.write(self._motor_left, self._motor_right, self._motor_flipper, cmd, arg)

    async def send_speed(self):
        await self._send_command(CommandVerbs.NOP, 0)

    async def set_fan_speed(self, fan_speed):
        assert 0 <= fan_speed <= 1
        await self._send_command(CommandVerbs.SET_FAN_SPEED, int(fan_speed * 240))

    async def flipper_calibrate(self):
        await self._send_command(CommandVerbs.FLIPPER_CALIBRATE, int(CommandVerbs.FLIPPER_CALIBRATE))

    async def get_data(self, index):
        """Get the next value for the given data index."""
        await self._send_command(CommandVerbs.GET_DATA, index)
        send_channel, rcv_channel = self._openrover_data_to_memory_channel[index]
        return await rcv_channel.receive()

    async def get_data_items(self, indices: Iterable[int]) -> Dict[int, Any]:
        return {i: await self.get_data(i) for i in set(indices)}


async def get_openrover_version(port):
    try:
        async with trio.fail_after(1):
            async with SerialTrio(port) as device:
                orp = OpenRoverProtocol(device)
                while True:
                    await orp.write(0, 0, 0, CommandVerbs.GET_DATA, 40)
                    k, version = await orp.read_one()
                    if k == 40:
                        return version
    except Exception as e:
        raise OpenRoverException(f'Did not respond to request for OpenRover version') from e
