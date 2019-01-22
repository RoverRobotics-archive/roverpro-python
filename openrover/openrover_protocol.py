import asyncio
from asyncio import CancelledError, Queue, StreamReader, Transport, StreamWriter
import logging
from typing import Optional, Tuple

from openrover.util import OpenRoverException
from openrover_data import MOTOR_EFFORT_FORMAT, OPENROVER_DATA_ELEMENTS

SERIAL_START_BYTE = bytes([253])


def encode_packet(*args: bytes):
    payload = b''.join(args)
    return SERIAL_START_BYTE + payload + bytes([checksum(payload)])


def checksum(values):
    return 255 - sum(values) % 255


class OpenRoverProtocol():
    _stream_reader: StreamReader = None
    _lock: asyncio.Lock

    def __init__(self, reader: StreamReader, writer: StreamWriter):
        """Low-level communication for OpenRover"""
        self._reader = reader
        self._writer = writer
        self._lock = asyncio.Lock()

    async def iter_messages(self):
        try:
            await asyncio.wait_for(self._lock.acquire(), 0)
            try:
                while True:
                    msg = await self._read_one_packet()
                    yield msg
            finally:
                self._lock.release()
        except TimeoutError:
            raise OpenRoverException('Two processes trying to read from message stream at the same time!')

    async def _read_one_packet(self) -> Tuple[int, bytes]:
        _ = await self._reader.readuntil(SERIAL_START_BYTE)
        packet = SERIAL_START_BYTE + await self._reader.readexactly(4)

        if packet[4] == checksum(packet[1:4]):
            k = packet[1]
            v = OPENROVER_DATA_ELEMENTS[k].data_format.unpack(packet[2:4])
            return (k, v)
        else:
            raise OpenRoverException('Bad checksum. Discarding data ' + repr(packet))

    async def write(self, motor_left, motor_right, flipper, arg1, arg2):
        binary = encode_packet(MOTOR_EFFORT_FORMAT.pack(motor_left),
                               MOTOR_EFFORT_FORMAT.pack(motor_right),
                               MOTOR_EFFORT_FORMAT.pack(flipper),
                               bytes([arg1]),
                               bytes([arg2]))
        self._writer.write(binary)
        await self._writer.drain()
