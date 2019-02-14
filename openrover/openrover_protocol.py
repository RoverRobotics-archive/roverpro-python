from enum import IntEnum
from typing import Tuple

import trio

from .openrover_data import MOTOR_EFFORT_FORMAT, OPENROVER_DATA_ELEMENTS
from .serial_trio import SerialTrio
from .util import OpenRoverException

SERIAL_START_BYTE = bytes([253])


class CommandVerbs(IntEnum):
    NOP = 0
    GET_DATA = 10
    SET_FAN_SPEED = 20
    RESTART = 230
    SET_DRIVE_MODE = 240
    FLIPPER_CALIBRATE = 250


def encode_packet(*args: bytes):
    payload = b''.join(args)
    return SERIAL_START_BYTE + payload + bytes([checksum(payload)])


def checksum(values):
    return 255 - sum(values) % 255


class OpenRoverProtocol:
    def __init__(self, serial: SerialTrio):
        """Low-level communication for OpenRover"""
        self._serial = serial
        # A packet involves multiple read operations, so we must lock the device for reading
        self._read_lock = trio.StrictFIFOLock()

    async def read_one(self) -> Tuple[int, bytes]:
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

    async def write(self, motor_left: float, motor_right: float, flipper: float, command_verb: CommandVerbs, command_arg: int):
        binary = encode_packet(MOTOR_EFFORT_FORMAT.pack(motor_left),
                               MOTOR_EFFORT_FORMAT.pack(motor_right),
                               MOTOR_EFFORT_FORMAT.pack(flipper),
                               bytes([command_verb, command_arg]))
        await self._serial.write(binary)
