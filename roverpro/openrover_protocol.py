import enum
from typing import Any, Tuple

import trio

from .openrover_data import MOTOR_EFFORT_FORMAT, OPENROVER_DATA_ELEMENTS
from .serial_trio import SerialTrio
from .util import OpenRoverException

SERIAL_START_BYTE = bytes.fromhex("fd")


class CommandVerb(enum.IntEnum):
    NOP = 0
    GET_DATA = 10
    SET_FAN_SPEED = 20
    RESTART = 230
    CLEAR_SYSTEM_FAULT = 232
    SET_DRIVE_MODE = 240
    FLIPPER_CALIBRATE = 250
    RELOAD_SETTINGS = 1
    COMMIT_SETTINGS = 2
    SET_POWER_POLLING_INTERVAL_MS = 3
    SET_OVERCURRENT_THRESHOLD_100MA = 4
    SET_OVERCURRENT_TRIGGER_DURATION_5MS = 5
    SET_OVERCURRENT_RECOVERY_THRESHOLD_100MA = 6
    SET_OVERCURRENT_RECOVERY_DURATION_5MS = 7
    SET_PWM_FREQUENCY_KHZ = 8
    SET_BRAKE_ON_ZERO_SPEED_COMMAND = 9
    SET_BRAKE_ON_DRIVE_TIMEOUT = 11
    SET_MOTOR_SLOW_DECAY_MODE = 12
    SET_TIME_TO_FULL_SPEED_DECISECONDS = 13
    SET_PWM_FREQUENCY_100HZ = 14
    SET_SPEED_LIMIT_PERCENT = 15
    SET_OVERSPEED_ENCODER_THRESHOLD_ENCODER_100HZ = 16
    SET_OVERSPEED_DURATION_100MS = 17
    SET_BRAKE_ON_FAULT = 18


def encode_packet(*args: bytes):
    payload = b"".join(args)
    return SERIAL_START_BYTE + payload + bytes([checksum(payload)])


def checksum(values):
    return 255 - sum(values) % 255


class OpenRoverProtocol:
    def __init__(self, serial: SerialTrio):
        """Low-level communication for OpenRover"""
        self._serial = serial
        # A packet involves multiple read operations, so we must lock the device for reading
        self._read_lock = trio.StrictFIFOLock()

    async def read_one(self) -> Tuple[int, Any]:
        raw_data = await self._read_one_raw()
        data_element_index = raw_data[0]
        element_descriptor = OPENROVER_DATA_ELEMENTS[data_element_index]
        data_element_value = element_descriptor.data_format.unpack(raw_data[1:])
        return data_element_index, data_element_value

    async def _read_one_raw(self) -> bytes:
        """Reads a packet, verifies its checksum, and returns the packet payload"""
        async with self._read_lock:
            _ = await self._serial.read_until(SERIAL_START_BYTE)

            payload = await self._serial.read_exactly(3)

            (actual_checksum,) = await self._serial.read_exactly(1)

            expected_checksum = checksum(payload)
            if actual_checksum == expected_checksum:
                return payload
            else:
                raise OpenRoverException(
                    "Bad checksum {}, expected {}. Discarding data {}".format(
                        list(actual_checksum), list(expected_checksum), list(payload)
                    )
                )

    async def flush(self):
        await self._serial.flush(0)

    def write_nowait(
        self,
        motor_left: float,
        motor_right: float,
        flipper: float,
        command_verb: CommandVerb,
        command_arg: int,
    ):
        binary = encode_packet(
            MOTOR_EFFORT_FORMAT.pack(motor_left),
            MOTOR_EFFORT_FORMAT.pack(motor_right),
            MOTOR_EFFORT_FORMAT.pack(flipper),
            bytes([command_verb, command_arg]),
        )
        self._serial.write_nowait(binary)
