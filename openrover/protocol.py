import asyncio
from asyncio import StreamReader, StreamWriter
from typing import Any, AsyncContextManager, AsyncIterable, Dict, Optional, Tuple

from serial import SerialException
import serial_asyncio

import async_iterable_util
from openrover.util import OpenRoverException
from openrover_data import OPENROVER_DATA_ELEMENTS, DataFormatMotorEffort, UINT8

SERIAL_START_BYTE = bytes([253])


def encode_packet(*args: bytes):
    payload = b''.join(args)
    return SERIAL_START_BYTE + payload + bytes([checksum(payload)])


def checksum(values):
    return 255 - sum(values) % 255


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
            self._stream_wrappers = stream_wrappers
            return stream_wrappers

        except SerialException as e:
            if 'FileNotFoundError' in e.args[0]:
                raise OpenRoverException("OpenRover device not found. Is it connected?", self._port) from e
            raise OpenRoverException("Could not open device", self._port) from e
        except Exception as e:
            raise OpenRoverException("Could not open device", self._port) from e

    async def aclose(self):
        r, w = self._stream_wrappers
        del self._stream_wrappers
        w.close()

        try:
            await r.wait_closed()  # only available in 3.7
        except AttributeError:
            while not r.at_eof():
                await asyncio.sleep(0.001)

        self._device_lock.release()

    async def __aenter__(self):
        return await self.aopen()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()


class OpenRoverPacketizer():
    def __init__(self, reader, writer):
        """Serial communication implementation details for OpenRover"""
        self._reader: StreamReader = reader
        self._writer: StreamWriter = writer

    def read_many(self, n: Optional[int] = None, sequence_timeout: Optional[float] = None, item_timeout: Optional[float] = None):
        result = self.read_all()
        if sequence_timeout is not None:
            result = async_iterable_util.timeout_all(sequence_timeout, result)
        if n is not None:
            result = async_iterable_util.limit(n, result)
        if item_timeout is not None:
            result = async_iterable_util.timeout_each(item_timeout, result)
        return result

    async def read_all(self):
        while True:
            yield await self._read()

    async def read_one(self, timeout: Optional[float]):
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

    def write(self, motor_left, motor_right, flipper, arg1, arg2):
        """Arrange to have the data written"""
        motor_speed_format = DataFormatMotorEffort()
        binary = encode_packet(motor_speed_format.pack(motor_left),
                               motor_speed_format.pack(motor_right),
                               motor_speed_format.pack(flipper),
                               bytes([arg1]),
                               bytes([arg2]))
        self._writer.write(binary)
