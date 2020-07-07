import abc
import enum
import functools
import re
from typing import NamedTuple, Optional


class ReadDataFormat(abc.ABC):
    python_type = None

    @abc.abstractmethod
    def description(self):
        raise NotImplementedError

    @abc.abstractmethod
    def unpack(self, b: bytes):
        raise NotImplementedError


class WriteDataFormat(abc.ABC):
    python_type = None

    @abc.abstractmethod
    def description(self):
        raise NotImplementedError

    @abc.abstractmethod
    def pack(self, value) -> bytes:
        raise NotImplementedError


class IntDataFormat(ReadDataFormat, WriteDataFormat):
    def __init__(self, nbytes, signed):
        self.nbytes = nbytes
        self.signed = signed

    def description(self):
        s = "signed" if self.signed else "unsigned"
        n = self.nbytes * 8
        return f"{s} integer ({n} bits)"

    def pack(self, value):
        return int(value).to_bytes(self.nbytes, byteorder="big", signed=self.signed)

    def unpack(self, b: bytes):
        return int.from_bytes(b, byteorder="big", signed=self.signed)


OPENROVER_LEGACY_VERSION = 40621


@functools.total_ordering
class OpenRoverFirmwareVersion(NamedTuple):
    @classmethod
    def parse(cls, a_str):
        ver_re = re.compile(r"(\d+(?:[.]\d+){0,2})(?:-([^+])+)?(?:[+](.+))?", re.VERBOSE)
        match = ver_re.fullmatch(a_str)
        parts = [int(p) for p in match.group(0).split(".")]
        return OpenRoverFirmwareVersion(*parts)

    major: int
    minor: int = 0
    patch: int = 0

    build: str = ""
    prerelease: str = ""

    @property
    def value(self):
        return self.major * 10000 + self.minor * 100 + self.patch * 10

    def __lt__(self, other):
        return (self.major, self.minor, self.patch, other.prerelease) < (
            other.major,
            other.minor,
            other.patch,
            self.prerelease,
        )

    def __str__(self):
        return (
            f"{self.major}.{self.minor}.{self.patch}"
            + (("-" + self.prerelease) if self.prerelease else "")
            + (("+" + self.build) if self.build else "")
        )


class DataFormatFirmwareVersion(ReadDataFormat):
    python_type = OpenRoverFirmwareVersion

    def unpack(self, b):
        v = UINT16.unpack(b)
        if v == OPENROVER_LEGACY_VERSION:
            return OpenRoverFirmwareVersion(1, 0, 0)
        return OpenRoverFirmwareVersion(v // 10000, v // 100 % 100, v % 10)

    def description(self):
        return (
            "XYYZZ, where X=major version, Y=minor version, Z = patch version."
            "e.g. 10502 = version 1.05.02. The special value 16421 represents pre-1.3 versions"
        )


class DataFormatChargerState(ReadDataFormat, WriteDataFormat):
    CHARGER_ACTIVE_MAGIC_BYTES = bytes.fromhex("dada")
    CHARGER_INACTIVE_MAGIC_BYTES = bytes.fromhex("0000")
    python_type = bool

    def pack(self, value):
        if value:
            return self.CHARGER_ACTIVE_MAGIC_BYTES
        else:
            return self.CHARGER_INACTIVE_MAGIC_BYTES

    def unpack(self, b):
        return bytes(b) == self.CHARGER_ACTIVE_MAGIC_BYTES

    def description(self):
        return "0xDADA if charging, else 0x0000"


class BatteryStatus(enum.Flag):
    overcharged_alarm = enum.auto()
    terminate_charge_alarm = enum.auto()
    over_temp_alarm = enum.auto()
    terminate_discharge_alarm = enum.auto()
    remaining_capacity_alarm = enum.auto()
    remaining_time_alarm = enum.auto()
    initialized = enum.auto()
    discharging = enum.auto()
    fully_charged = enum.auto()
    fully_discharged = enum.auto()


class DataFormatBatteryStatus(ReadDataFormat):
    python_type = BatteryStatus

    def unpack(self, b: bytes):
        assert len(b) == 2
        as_int = int.from_bytes(b, byteorder="big", signed=False)
        result = BatteryStatus(0)
        for mask, val in (
            (0x8000, BatteryStatus.overcharged_alarm),
            (0x4000, BatteryStatus.terminate_charge_alarm),
            (0x1000, BatteryStatus.over_temp_alarm),
            (0x0800, BatteryStatus.terminate_discharge_alarm),
            (0x0200, BatteryStatus.remaining_capacity_alarm),
            (0x0100, BatteryStatus.remaining_time_alarm),
            (0x0080, BatteryStatus.initialized),
            (0x0040, BatteryStatus.discharging),
            (0x0020, BatteryStatus.fully_charged),
            (0x0010, BatteryStatus.fully_discharged),
        ):
            if as_int & mask:
                result |= val
        return result

    def description(self):
        return "bit flags"


class DriveMode(enum.IntEnum):
    OPEN_LOOP = 0
    CLOSED_LOOP = 1


UINT16 = IntDataFormat(2, False)
INT16 = IntDataFormat(2, True)
UINT8 = IntDataFormat(1, signed=False)


class DataFormatFixedPrecision(ReadDataFormat, WriteDataFormat):
    """A fractional number packed as an integer, but representing a fractional number"""

    def __init__(self, base_type, step=1.0, zero=0.0):
        self.base_type = base_type
        # a change of 1 in the python type corresponds to a change of this many in the base type
        self.step = step
        # the value of 0 in the python type corresponds to this value in the base type
        self.zero = zero

    def unpack(self, b: bytes):
        n = self.base_type.unpack(b)
        return (n - self.zero) / self.step

    def pack(self, p):
        n = round(p * self.step + self.zero)
        return self.base_type.pack(n)

    def description(self):
        return "fractional (resolution=1/{}, zero={}) stored as {}".format(
            self.step, self.zero, self.base_type.description()
        )


class DataFormatDriveMode(ReadDataFormat):
    python_type = DriveMode

    def unpack(self, b: bytes):
        return DriveMode(UINT16.unpack(b))

    def pack(self, p: DriveMode):
        return UINT16.pack(p.value)

    def description(self):
        return DriveMode.__doc__


OLD_CURRENT_FORMAT = DataFormatFixedPrecision(UINT16, 34)

SIGNED_MILLIS_FORMAT = DataFormatFixedPrecision(INT16, 1000)
UNSIGNED_MILLIS_FORMAT = DataFormatFixedPrecision(UINT16, 1000)
OLD_VOLTAGE_FORMAT = DataFormatFixedPrecision(UINT16, 58)
FAN_SPEED_RESPONSE_FORMAT = DataFormatFixedPrecision(UINT16, 240)
DECIKELVIN_FORMAT = DataFormatFixedPrecision(UINT16, 10, zero=2731.5)
PERCENTAGE_FORMAT = DataFormatFixedPrecision(UINT16, 100)
MOTOR_EFFORT_FORMAT = DataFormatFixedPrecision(UINT8, 125, 125)
CHARGER_STATE_FORMAT = DataFormatChargerState()
FIRMWARE_VERSION_FORMAT = DataFormatFirmwareVersion()
DRIVE_MODE_FORMAT = DataFormatDriveMode()
BATTERY_STATUS_FORMAT = DataFormatBatteryStatus()


class MotorStatusFlag(enum.Flag):
    NONE = 0
    FAULT1 = enum.auto()
    FAULT2 = enum.auto()
    DECAY_MODE = enum.auto()
    REVERSE = enum.auto()
    BRAKE = enum.auto()
    COAST = enum.auto()


class DataFormatMotorStatus(ReadDataFormat):
    def description(self):
        return "motor status bit flags"

    def unpack(self, b: bytes):
        u = UINT16.unpack(b)

        bit_meanings = [
            MotorStatusFlag.FAULT1,
            MotorStatusFlag.FAULT2,
            MotorStatusFlag.DECAY_MODE,
            MotorStatusFlag.REVERSE,
            MotorStatusFlag.BRAKE,
            MotorStatusFlag.COAST,
        ]
        if len(bit_meanings) <= u.bit_length():
            raise ValueError("too many bits to unpack")

        result = MotorStatusFlag.NONE
        for i, flag in enumerate(bit_meanings):
            if u & 1 << i:
                result |= flag
        return result


class DataFormatIgnored(WriteDataFormat):
    def description(self):
        return f"Ignored data {self.n_bytes} bytes long"

    def pack(self, value=None) -> bytes:
        assert value is None
        return bytes(self.n_bytes)

    def __init__(self, n_bytes):
        self.n_bytes = n_bytes


class SystemFaultFlag(enum.Flag):
    NONE = 0
    OVERSPEED = enum.auto()
    OVERCURRENT = enum.auto()


class DataFormatSystemFault(ReadDataFormat):
    def description(self):
        return "System fault bit flags"

    def unpack(self, b: bytes):
        u = UINT16.unpack(b)

        bit_meanings = [SystemFaultFlag.OVERSPEED, SystemFaultFlag.OVERCURRENT]
        if len(bit_meanings) <= u.bit_length():
            raise ValueError("too many bits to unpack")

        result = SystemFaultFlag.NONE
        for i, flag in enumerate(bit_meanings):
            if u & 1 << i:
                result |= flag
        return result


class DataElement:
    def __init__(
        self,
        index: int,
        data_format: ReadDataFormat,
        name: str,
        description: str = None,
        not_implemented: bool = False,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ):
        self.index = index
        self.data_format = data_format
        self.name = name
        self.description = description
        self.not_implemented = not_implemented
        self.since_version = None if since is None else OpenRoverFirmwareVersion.parse(since)
        self.until_version = None if until is None else OpenRoverFirmwareVersion.parse(until)

    def supported(self, version):
        if isinstance(version, str):
            v = OpenRoverFirmwareVersion.parse(version)
        elif isinstance(version, OpenRoverFirmwareVersion):
            v = version
        else:
            raise TypeError(
                f"Expected string or OpenRoverFirmwareVersion, but got {type(version)}"
            )

        if self.not_implemented:
            return False
        if self.since_version is not None and v < self.since_version:
            return False
        if self.until_version is not None:
            if self.until_version <= v:
                return False
        return True


elements = [
    DataElement(
        0, OLD_CURRENT_FORMAT, "battery (A+B) current (external)", "total current from batteries"
    ),
    DataElement(2, UINT16, "left motor speed", not_implemented=True),
    DataElement(4, UINT16, "right motor speed", not_implemented=True),
    DataElement(
        6,
        UINT16,
        "flipper position 1",
        "flipper position sensor 1. 0=15 degrees; 1024=330 degrees;",
    ),
    DataElement(
        8,
        UINT16,
        "flipper position 2",
        "flipper position sensor 2. 0=15 degrees; 1024=330 degrees;",
    ),
    DataElement(10, OLD_CURRENT_FORMAT, "left motor current"),
    DataElement(12, OLD_CURRENT_FORMAT, "right motor current"),
    DataElement(
        14,
        UINT16,
        "left motor encoder count",
        "May overflow or underflow. Increments when motor driven forward, decrements backward",
        since="1.4",
    ),
    DataElement(
        16,
        UINT16,
        "right motor encoder count",
        "May overflow or underflow. Increments when motor driven forward, decrements backward",
        since="1.4",
    ),
    DataElement(18, UINT16, "motors fault flag", not_implemented=True),
    DataElement(20, UINT16, "left motor temperature"),
    DataElement(22, UINT16, "right motor temperature", not_implemented=True),
    DataElement(24, OLD_VOLTAGE_FORMAT, "battery A voltage (external)"),
    DataElement(26, OLD_VOLTAGE_FORMAT, "battery B voltage (external)"),
    DataElement(
        28,
        UINT16,
        "left motor encoder interval",
        "0 when motor stopped. Else proportional to motor period (inverse motor speed)",
    ),
    DataElement(
        30,
        UINT16,
        "right motor encoder interval",
        "0 when motor stopped. Else proportional to motor period (inverse motor speed)",
    ),
    DataElement(
        32,
        UINT16,
        "flipper motor encoder interval",
        "0 when motor stopped. Else proportional to motor period (inverse motor speed)",
        not_implemented=True,
    ),
    DataElement(
        34,
        PERCENTAGE_FORMAT,
        "battery A state of charge",
        "Proportional charge, 0.0=empty, 1.0=full",
    ),
    DataElement(
        36,
        PERCENTAGE_FORMAT,
        "battery B state of charge",
        "Proportional charge, 0.0=empty, 1.0=full",
    ),
    DataElement(38, CHARGER_STATE_FORMAT, "battery charging state"),
    DataElement(40, FIRMWARE_VERSION_FORMAT, "release version"),
    DataElement(42, OLD_CURRENT_FORMAT, "battery A current (external)"),
    DataElement(44, OLD_CURRENT_FORMAT, "battery B current (external)"),
    DataElement(46, UINT16, "motor flipper angle"),
    DataElement(48, FAN_SPEED_RESPONSE_FORMAT, "fan speed"),
    DataElement(50, DRIVE_MODE_FORMAT, "drive mode", until="1.7"),
    DataElement(52, BATTERY_STATUS_FORMAT, "battery A status", since="1.2"),
    DataElement(54, BATTERY_STATUS_FORMAT, "battery B status", since="1.2"),
    DataElement(56, UINT16, "battery A mode", since="1.2"),
    DataElement(58, UINT16, "battery B mode", since="1.2"),
    DataElement(60, DECIKELVIN_FORMAT, "battery A temperature (internal)", since="1.2"),
    DataElement(62, DECIKELVIN_FORMAT, "battery B temperature (internal)", since="1.2"),
    DataElement(64, UNSIGNED_MILLIS_FORMAT, "battery A voltage (internal)", since="1.2"),
    DataElement(66, UNSIGNED_MILLIS_FORMAT, "battery B voltage (internal)", since="1.2"),
    DataElement(
        68,
        SIGNED_MILLIS_FORMAT,
        "battery A current (internal)",
        ">0 = charging; <0 = discharging",
        since="1.2",
    ),
    DataElement(
        70,
        SIGNED_MILLIS_FORMAT,
        "battery B current (internal)",
        ">0 = charging; <0 = discharging",
        since="1.2",
    ),
    DataElement(72, DataFormatMotorStatus(), "left motor status", since="1.7"),
    DataElement(74, DataFormatMotorStatus(), "right motor status", since="1.7"),
    DataElement(76, DataFormatMotorStatus(), "flipper motor status", since="1.7"),
    DataElement(78, FAN_SPEED_RESPONSE_FORMAT, "fan 1 duty", since="1.9"),
    DataElement(80, FAN_SPEED_RESPONSE_FORMAT, "fan 2 duty", since="1.9"),
    DataElement(82, DataFormatSystemFault(), "system fault flags", since="1.10"),
]

OPENROVER_DATA_ELEMENTS = {e.index: e for e in elements}


def strike(s):
    return f"~~{s}~~"


def doc():
    lines = ["| # | Name | Data Type | Description |", "| - | ---- | --------- | ----------- |"]

    for de in elements:
        lines.append(
            "|"
            + "|".join(
                [
                    strike(de.index) if de.not_implemented else de.index,
                    de.name,
                    de.data_format.description(),
                    de.description,
                ]
            )
            + "|"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(doc())


def fix_encoder_delta(delta):
    MAX_ENCODER = 2 ** 16
    delta %= MAX_ENCODER
    if delta < MAX_ENCODER / 2:
        return delta
    else:
        return delta - MAX_ENCODER
