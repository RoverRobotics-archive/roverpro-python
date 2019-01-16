import asyncio
from asyncio import Future, StreamReader, Transport, Event
from typing import Any, AsyncContextManager, AsyncIterable, Dict, Optional, Tuple

from serial import SerialException
import serial_asyncio

import async_iterable_util
from openrover.util import OpenRoverException
from openrover_data import DataFormatMotorEffort, OPENROVER_DATA_ELEMENTS

SERIAL_START_BYTE = bytes([253])
DEFAULT_SERIAL_KWARGS = dict(baudrate=57600, timeout=0.5, write_timeout=0.5, stopbits=1)


def encode_packet(*args: bytes):
    payload = b''.join(args)
    return SERIAL_START_BYTE + payload + bytes([checksum(payload)])


def checksum(values):
    return 255 - sum(values) % 255


class OpenRoverProtocol(asyncio.Protocol):
    _transport: Optional[Transport] = None
    _stream_reader: StreamReader = None

    def __init__(self):
        """Low-level communication for OpenRover"""
        self._buffer = bytearray()
        self._stream_reader = StreamReader()

    def connection_made(self, transport):
        """Called when a connection is made.

        The argument is the transport representing the pipe connection.
        To receive data, wait for data_received() calls.
        When the connection is closed, connection_lost() is called.
        """
        self._buffer.clear()
        self._transport = transport
        self._stream_reader.set_transport(transport)

    def connection_lost(self, exc):
        """Called when the connection is lost or closed.

        The argument is an exception object or None (the latter
        meaning a regular EOF is received or the connection was
        aborted or closed).
        """
        if self._stream_reader is not None:
            if exc is None:
                self._stream_reader.feed_eof()
            else:
                self._stream_reader.set_exception(exc)
        super().connection_lost(exc)

        self._transport = None
        self._stream_reader = None

    def data_received(self, data: bytes):
        self._stream_reader.feed_data(data)

    def eof_received(self):
        self._stream_reader.feed_eof()
        return True

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
        _ = await self._stream_reader.readuntil(SERIAL_START_BYTE)
        packet = SERIAL_START_BYTE + await self._stream_reader.readexactly(4)

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
        self._transport.write(binary)


class OpenRoverConnectionContext(AsyncContextManager):
    _port: str
    _transport: Optional[Transport] = None
    _protocol: Optional[OpenRoverProtocol] = None
    serial_kwargs: Dict[str, Any]
    open_timeout: Optional[float]

    def __init__(self, port, open_timeout: Optional[float] = None, **kwargs):
        self._port = str(port)
        self.serial_kwargs = dict(**kwargs)
        self.open_timeout = open_timeout

    async def aopen(self) -> OpenRoverProtocol:
        assert self._transport is None
        assert self._protocol is None

        serial_kwargs = DEFAULT_SERIAL_KWARGS.copy()
        serial_kwargs.update(self.serial_kwargs)
        try:
            transport, protocol = await serial_asyncio.create_serial_connection(asyncio.get_event_loop(), url=self._port, protocol_factory=OpenRoverProtocol, **serial_kwargs)
            self._transport = transport
            self._protocol = protocol
        except SerialException as e:
            if 'FileNotFoundError' in e.args[0]:
                raise OpenRoverException("Could not connect to OpenRover device - file not found. Is it connected?", self._port) from e
            if 'PermissionError' in e.args[0]:
                raise OpenRoverException("Could not connect to OpenRover device - permission error. Is it open in another process? Does this user have OS permission?", self._port) from e
        except Exception as e:
            raise OpenRoverException("Could not open device", self._port) from e

        while self._protocol._transport is None or self._transport._protocol is None:
            if self._transport.is_closing():
                raise OpenRoverException('Device closed immediately')
            await asyncio.sleep(0.001)

        return self._protocol

    async def aclose(self):
        self._transport.close()
        while self._transport.serial is not None:
            await asyncio.sleep(0.001)

    async def __aenter__(self):
        return await self.aopen()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()
