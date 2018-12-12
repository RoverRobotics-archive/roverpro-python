import asyncio
from asyncio import InvalidStateError
from concurrent.futures import Future
from typing import MutableMapping, Optional

from serial.tools import list_ports

from openrover.util import OpenRoverException
from protocol import OpenRoverPacketizer, SerialConnectionContext


class OpenRover:
    _motor_left = 0
    _motor_right = 0
    _motor_flipper = 0
    _port = None
    _next_data = None
    _connection = None
    _packetizer = None

    def __init__(self, port=None):
        """An OpenRover object """
        self._loop = asyncio.get_event_loop()
        self._motor_left = 0
        self._motor_right = 0
        self._motor_flipper = 0
        self._port = port
        self._connection: Optional[SerialConnectionContext] = None
        self._next_data: MutableMapping[int, Future] = dict()

    async def aopen(self):
        port = self._port
        if port is None:
            port = await find_openrover()

        self._connection = SerialConnectionContext(port, open_timeout=1)
        reader, writer = await self._connection.aopen()
        self._packetizer = OpenRoverPacketizer(reader, writer)

        self._process_data_task = asyncio.ensure_future(self.process_data())

        version = None
        for _ in range(3):
            try:
                version = await self.get_data(40, timeout=1)
                if version is not None:
                    break
            except Exception as e:
                raise OpenRoverException('Failed to open Openrover') from e
        if version is None:
            raise OpenRoverException('Device did not respond to a request for OpenRover version number. Is it an OpenRover? Is it powered on?', {'port': port})

    async def __aenter__(self):
        await self.aopen()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    async def process_data(self):
        async for k, v in self._packetizer.read_many():
            old_future = self._next_data.pop(k, None)
            if old_future is None:
                raise RuntimeWarning('value was not expected %s: %s', k, v)
            else:
                try:
                    old_future.set_result(v)
                except InvalidStateError:
                    pass

    async def consume_data(self, q):
        while True:
            key, value = await q.get()
            self._next_data[key].set_result(value)

    async def aclose(self):
        self._process_data_task.cancel()
        return await self._connection.aclose()

    def set_motor_speeds(self, left, right, flipper):
        assert -1 <= left <= 1
        assert -1 <= right <= 1
        assert -1 <= flipper <= 1
        self._motor_left = left
        self._motor_right = right
        self._motor_flipper = flipper

    def send_command(self, arg1, arg2):
        self._packetizer.write(self._motor_left, self._motor_right, self._motor_flipper, arg1, arg2)

    def send_speed(self):
        self.send_command(0, 0)

    def set_fan_speed(self, fan_speed):
        self.send_command(20, fan_speed)

    def flipper_calibrate(self):
        self.send_command(250, 250)

    def request_data(self, index):
        self.send_command(10, index)

    async def get_data(self, index, timeout: float = 0.2):
        """Get the next value for the given data value."""
        future = self._next_data.get(index)
        if future is not None:
            future.cancel()

        future = asyncio.get_event_loop().create_future()
        self._next_data[index] = future
        self.send_command(10, index)
        result = await asyncio.wait_for(future, timeout)
        return result


async def get_openrover_version(port):
    async with SerialConnectionContext(port, 1) as (reader, writer):
        p = OpenRoverPacketizer(reader, writer)
        n_attempts = 3
        for i in range(n_attempts):
            p.write(0, 0, 0, 10, 40)
            k, v = await p.read_one(1)
            if k == 40:
                return v
        raise OpenRoverException(f'Did not respond to request for OpenRover version after {n_attempts} attempts')


async def iterate_openrovers():
    """
    Iterates devices determined to be OpenRover devices.
    Throws a SerialException if candidate devices are busy
    """

    for comport in list_ports.comports():
        if comport.manufacturer == 'FTDI':
            try:
                await get_openrover_version(comport.device)
                yield comport.device

            except OpenRoverException:
                pass


async def find_openrover():
    try:
        async for i in iterate_openrovers():
            return i
    except StopIteration:
        pass

    raise OpenRoverException('No Rover device found')
