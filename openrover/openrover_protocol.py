import logging
from typing import Tuple

import trio

from openrover.util import OpenRoverException
from openrover_data import MOTOR_EFFORT_FORMAT, OPENROVER_DATA_ELEMENTS
from serial_trio import SerialTrio

SERIAL_START_BYTE = bytes([253])


def encode_packet(*args: bytes):
    payload = b''.join(args)
    return SERIAL_START_BYTE + payload + bytes([checksum(payload)])


def checksum(values):
    return 255 - sum(values) % 255


class OpenRoverProtocol():
    def __init__(self, serial: SerialTrio):
        """Low-level communication for OpenRover"""
        self._serial = serial
        self._read_lock = trio.StrictFIFOLock()

    async def iter_packets(self):
        while True:
            try:
                msg = await self._read_one_packet()
                yield msg
            except OpenRoverException as e:
                logging.exception(str(e))

    async def _read_one_packet(self) -> Tuple[int, bytes]:
        async with self._read_lock:
            _ = await self._serial.read_until(SERIAL_START_BYTE)
            packet = SERIAL_START_BYTE + await self._serial.read_exactly(4)
            assert len(packet) == 5
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
        await self._serial.write(binary)
