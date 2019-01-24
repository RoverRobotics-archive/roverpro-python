import asyncio
from asyncio import InvalidStateError
from concurrent.futures import Future
import logging
from typing import Any, Dict, Iterable, MutableMapping

from serial.tools import list_ports

from openrover.util import OpenRoverException
from openrover_protocol import OpenRoverProtocol


class OpenRover:
    _motor_left = 0
    _motor_right = 0
    _motor_flipper = 0
    _port = None
    _next_data = None
    _rover_protocol = None

    def __init__(self, port=None):
        """An OpenRover object """
        self._loop = asyncio.get_event_loop()
        self._motor_left = 0
        self._motor_right = 0
        self._motor_flipper = 0
        self._port = port
        self._next_data: MutableMapping[int, Future] = dict()

    async def aopen(self):
        port = self._port
        if port is None:
            port = await find_openrover()

        self._connection = OpenRoverConnection(port, open_timeout=1)
        r, w = await self._connection.aopen()
        self._rover_protocol = OpenRoverProtocol(r, w)
        self._process_data_task = asyncio.ensure_future(self.process_data())

    async def __aenter__(self):
        await self.aopen()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    async def process_data(self):
        try:
            async for k, v in self._rover_protocol.iter_packets():
                old_future = self._next_data.pop(k, None)
                if old_future is None:
                    raise RuntimeWarning('value was not expected %s: %s', k, v)
                else:
                    try:
                        old_future.set_result(v)
                    except InvalidStateError:
                        pass
        except Exception as e:
            raise

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

    async def send_command(self, arg1, arg2):
        await self._rover_protocol.write(self._motor_left, self._motor_right, self._motor_flipper, arg1, arg2)

    async def send_speed(self):
        await self.send_command(0, 0)

    async def set_fan_speed(self, fan_speed):
        await self.send_command(20, fan_speed)

    async def flipper_calibrate(self):
        await self.send_command(250, 250)

    def request_data(self, index):
        self.send_command(10, index)

    async def get_data(self, index):
        """Get the next value for the given data index."""
        old_future = self._next_data.get(index)
        if old_future is not None:
            old_future.cancel()

        new_future = asyncio.get_event_loop().create_future()
        self._next_data[index] = new_future
        await asyncio.wait([self.send_command(10, index), new_future], timeout=1)
        return await asyncio.wait_for(new_future, 1)

    async def get_data_items(self, indices: Iterable[int]) -> Dict[int, Any]:
        keys = list(set(indices))
        futures = []
        for i in keys:
            old_future = self._next_data.get(i)
            if old_future is not None:
                old_future.cancel()
            f = asyncio.get_event_loop().create_future()
            self._next_data[i] = f
            self.request_data(i)
            futures.append(f)
        values = await asyncio.wait_for(asyncio.gather(*futures), timeout=0.2)
        return dict(zip(keys, values))


async def get_openrover_version(port):
    async def get_openrover_version_untimed():
        async with OpenRoverConnection(port, open_timeout=3) as (reader, writer):
            protocol = OpenRoverProtocol(reader, writer)
            await protocol.write(0, 0, 0, 10, 40)
            async for k, v in protocol.iter_packets():
                if k == 40:
                    return v

    try:
        version = await get_openrover_version_untimed()
        return version
    except Exception as e:
        raise OpenRoverException(f'Did not respond to request for OpenRover version') from e

