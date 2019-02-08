from dataclasses import dataclass
import enum
import typing
from rx import Observable

from openrover import OpenRover


class BatteryAlarmCondition(enum.Flag):
    OVERCHARGED = enum.auto()
    TERMINATE_CHARGE = enum.auto()
    OVER_TEMP = enum.auto()
    TERMINATE_DISCHARGE = enum.auto()


class OpenRoverDataStream:
    def __init__(self, rover: OpenRover):


@dataclass
class FirmwareStatics:
    build_version: str

class BatteryMetrics:
    battery_id: str
    voltage: float
    temperature: float
    capacity_remaining: float
    initialized: bool
    discharging: bool
    battery_needs_condition: bool
    fully_charged: bool
    fully_discharged: bool

@dataclass
class BatteryVitals:
    battery_id: str
    current: float
    alarm_flags: typing.Optional[BatteryAlarmCondition]

class MotorFaultCondition(enum.Enum):
    # Low load current
    LowLoadFault = enum.auto()
    # short to ground, short to supply, or shorted motor winding
    ShortFault = enum.auto()
    # undervoltage, overtemperature or logic fault
    OtherFault = enum.auto()


@dataclass
class MotorVitals:
    # a unique identifier which
    motor_id: str
    # period of the motor moving forward, in seconds. A negative value indicates backward motion
    period: float
    # encoder count of the motor
    encoder_count: int
    fault_condition: typing.Optional[MotorFaultCondition]
    # todo: current
