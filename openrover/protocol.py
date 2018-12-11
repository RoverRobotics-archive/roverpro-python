import asyncio
from asyncio import StreamReader, StreamWriter
from typing import Any, AsyncContextManager, AsyncIterable, Dict, Optional, Tuple

from serial import SerialException
import serial_asyncio

from openrover.exceptions import OpenRoverException
from openrover_data import OPENROVER_DATA_ELEMENTS

SERIAL_START_BYTE = bytes([253])


def encode_packet(motor_left, motor_right, flipper, arg1, arg2):
    payload = [encode_speed(motor_left),
               encode_speed(motor_right),
               encode_speed(flipper),
               arg1,
               arg2]
    return SERIAL_START_BYTE + bytes(payload + [checksum(payload)])


def checksum(values):
    return 255 - sum(values) % 255


def encode_speed(speed_as_float):
    return int(round(speed_as_float * 125)) + 125


_device_locks = dict()

DEFAULT_SERIAL_KWARGS = dict(baudrate=57600, timeout=0.5, write_timeout=0.5, stopbits=1)


class SerialConnectionContext(AsyncContextManager):
    _port: str
    serial_kwargs: Dict[str, Any]
    open_timeout: Optional[int]
    _device_lock: asyncio.Lock
    _stream_wrappers: Optional[Tuple[asyncio.StreamReader, asyncio.StreamWriter]] = None

    def __init__(self, port, open_timeout=None, **kwargs):
        self._port = str(port)
        self.serial_kwargs = dict(**kwargs)
        self.open_timeout = open_timeout
        self._device_lock = _device_locks.setdefault(port, asyncio.Lock())

    def is_open(self):
        return self._stream_wrappers[0] is not None

    @property
    def reader(self):
        return self._stream_wrappers[0]

    @property
    def writer(self):
        return self._stream_wrappers[1]

    async def aopen(self):
        await asyncio.wait_for(self._device_lock.acquire(), self.open_timeout)
        try:
            serial_kwargs = DEFAULT_SERIAL_KWARGS.copy()
            serial_kwargs.update(self.serial_kwargs)

            stream_wrappers = await serial_asyncio.open_serial_connection(url=self._port, **serial_kwargs)
        except SerialException as e:
            if 'FileNotFoundError' in e.args[0]:
                raise OpenRoverException("OpenRover device not found. Is it connected?", self._port) from e
            pass

            raise OpenRoverException("Could not open device") from e

        self._stream_wrappers = stream_wrappers
        return stream_wrappers

    async def aclose(self):
        r, w = self._stream_wrappers
        del self._stream_wrappers
        w.close()
        await w.wait_closed()
        self._device_lock.release()

    async def __aenter__(self):
        return await self.aopen()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()


async def aiterable_item_timeout(delay: float, aiterable: AsyncIterable):
    assert delay >= 0
    iter = aiterable.__aiter__()
    try:
        while True:
            item = await asyncio.wait_for(asyncio.create_task(iter.__anext__()), delay)
            yield item
    except asyncio.TimeoutError:
        pass
    except StopAsyncIteration:
        raise


async def aiterable_limit(limit: int, aiterable: AsyncIterable):
    assert limit >= 0
    iter = aiterable.__aiter__()
    try:
        for i in range(limit):
            yield await iter.__anext__()
    except StopAsyncIteration:
        raise


async def aiterable_sequence_timeout(delay: float, aiterable: AsyncIterable):
    assert delay >= 0
    iter = aiterable.__aiter__()
    sleep_task = asyncio.create_task(asyncio.sleep(delay))
    try:
        while True:
            next_task = asyncio.create_task(iter.__anext__())
            await asyncio.wait([sleep_task, next_task], return_when=asyncio.FIRST_COMPLETED)
            if next_task.done():
                yield next_task.result()
            if sleep_task.done():
                next_task.cancel()
                return
    except StopAsyncIteration:
        sleep_task.cancel()
        raise


class OpenRoverPacketizer():
    def __init__(self, reader, writer):
        """Serial communication implementation details for OpenRover"""
        self._reader: StreamReader = reader
        self._writer: StreamWriter = writer

    def read_many(self, limit: Optional[int] = None, sequence_timeout: Optional[float] = None, item_timeout: Optional[float] = None):
        result = self.read_all()
        if sequence_timeout is not None:
            result = aiterable_sequence_timeout(sequence_timeout, result)
        if limit is not None:
            result = aiterable_limit(limit, result)
        if item_timeout is not None:
            result = aiterable_item_timeout(item_timeout, result)
        return result

    async def read_all(self):
        while True:
            yield await self._read()

    async def read_one(self, timeout: Optional[int]):
        return await asyncio.wait_for(self._read(), timeout)

    async def _read(self) -> Tuple[int, bytes]:
        _ = await self._reader.readuntil(SERIAL_START_BYTE)
        packet = SERIAL_START_BYTE + await self._reader.readexactly(4)

        if packet[4] == checksum(packet[1:4]):
            k = packet[1]
            v = OPENROVER_DATA_ELEMENTS[k].data_format.unpack(packet[2:4])
            return (k, v)
        else:
            raise OpenRoverException('Bad checksum. Discarding data ' + repr(packet))

    async def write_many(self, messages: AsyncIterable):
        async for args in messages:
            self.write(*args)

    def write(self, *args):
        """Arrange to have the data written"""
        binary = encode_packet(*args)
        self._writer.write(binary)
