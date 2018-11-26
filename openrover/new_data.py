from dataclasses import dataclass
import enum
import typing
import asyncio

from openrover import OpenRover
from openrover_data import BatteryStatus


async def battery_vitals_stream(rover, delay):
    while True:
        yield (BatteryVitals(
            battery_id='',  # TODO
            voltage=rover.get_data(24) / 58,
            current=rover.get_data(42) / 34,
            alarms=rover.get_data(52).alarms,
        ), BatteryVitals(
            battery_id='',  # TODO
            voltage=rover.get_data(26) / 58,
            current=rover.get_data(44) / 34,
            alarms=rover.get_data(54).alarms,
        ))
        await asyncio.sleep(delay)


async def battery_metrics_stream(rover, delay):
    pass  # TODO


class FirmwareStatics:
    build_version: str


@dataclass
class BatteryMetrics:
    battery_id: str
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
    voltage: float
    current: float
    alarms: BatteryStatus


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
