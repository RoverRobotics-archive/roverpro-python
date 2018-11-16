from __future__ import annotations

import abc
from dataclasses import dataclass
import struct

import typing


class DataFormat(abc.ABC):
    python_type: typing.Type

    @abc.abstractmethod
    def unpack(self, b):
        pass

    @abc.abstractmethod
    def pack(self, value):
        pass


class StructDataFormat(DataFormat):
    def __init__(self, format_: str, python_type):
        self.python_type = python_type
        self._struct = struct.Struct(format_)

    def pack(self, value):
        return self._struct.pack(value)

    def unpack(self, b):
        return self._struct.unpack(b)[0]


class DataFormatInt16(StructDataFormat):
    python_type = int
    _struct = struct.Struct('!h')


class DataFormatUInt16(StructDataFormat):
    python_type = int
    _struct = struct.Struct('!H')


class DataFormatChargerState(DataFormat):
    python_type = bool

    def pack(self, value):
        if value:
            return b'\xda\xda'
        else:
            return b'\0\0'

    def unpack(self, b):
        if bytes(b) == b'\xda\xda':
            return True
        else:
            return False


@dataclass
class BatteryStatus:
    overcharged_alarm: bool
    terminate_charge_alarm: bool
    over_temp_alarm: bool
    terminate_discharge_alarm: bool
    remaining_capacity_alarm: bool
    remaining_time_alarm: bool
    initialized: bool
    discharging: bool
    fully_charged: bool
    fully_discharged: bool


class DataFormatBatteryStatus(DataFormat):
    python_type = BatteryStatus

    def pack(self, value):
        raise NotImplementedError

    def unpack(self, b: bytes):
        assert len(b) == 2
        as_int = int.from_bytes(b, byteorder='big', signed=False)
        return BatteryStatus(
            overcharged_alarm=bool(as_int & 0x8000),
            terminate_charge_alarm=bool(as_int & 0x4000),
            over_temp_alarm=bool(as_int & 0x1000),
            terminate_discharge_alarm=bool(as_int & 0x0800),
            remaining_capacity_alarm=bool(as_int & 0x0200),
            remaining_time_alarm=bool(as_int & 0x0100),
            initialized=bool(as_int & 0x0080),
            discharging=bool(as_int & 0x0040),
            fully_charged=bool(as_int & 0x0020),
            fully_discharged=bool(as_int & 0x0010, )
        )


UINT16 = StructDataFormat('!H', int)
INT16 = StructDataFormat('!h', int)


@dataclass
class DataElement:
    index: int
    data_format: DataFormat
    name: str
    description: str = None


elements = [
    DataElement(0, UINT16, 'PWR_TOTAL_CURRENT', 'total current from battery in units of .029 Amps'),
    DataElement(2, UINT16, 'MOTOR_FB_RPM.left'),
    DataElement(4, UINT16, 'MOTOR_FB_RPM.right'),
    DataElement(6, UINT16, 'FLIPPER_FB_POSITION.pot1', 'flipper position sensor 1. 0=15 degrees; 1024=330 degrees;'),
    DataElement(8, UINT16, 'FLIPPER_FB_POSITION.pot2', 'flipper position sensor 2. 0=15 degrees; 1024=330 degrees;'),
    DataElement(10, UINT16, 'MOTOR_FB_CURRENT_left', 'left motor current in units of .029 Amps'),
    DataElement(12, UINT16, 'MOTOR_FB_CURRENT_right', 'right motor current in units of .029 Amps'),
    DataElement(14, UINT16, 'MOTOR_ENCODER_COUNT.left', 'left motor encoder count, mod 2**16'),
    DataElement(16, UINT16, 'MOTOR_ENCODER_COUNT.right', 'right motor encoder count, mod 2**16'),
    DataElement(18, UINT16, 'MOTOR_FAULT_FLAG.left'),
    DataElement(20, UINT16, 'MOTOR_TEMP.left', 'left motor temperature in Celsius'),
    DataElement(22, UINT16, 'MOTOR_TEMP.right', 'right motor temperature in Celsius'),
    DataElement(24, UINT16, 'PWR_BAT_VOLTAGE.a', 'Voltage of Battery A in units of 0.017 Volts'),
    DataElement(26, UINT16, 'PWR_BAT_VOLTAGE.b', 'Voltage of Battery B in units of 0.017 Volts'),
    DataElement(28, UINT16, 'REG_MOTOR_FB_PERIOD_LEFT', 'Left motor period in units of 45 μs'),
    DataElement(30, UINT16, 'REG_MOTOR_FB_PERIOD_RIGHT', 'Right motor period in units of 45 μs'),
    DataElement(32, UINT16, 'REG_MOTOR_FB_PERIOD_FLIPPER', 'Flipper motor period in units of 45 μs'),
    DataElement(34, UINT16, 'ROBOT_REL_SOC_A', 'Percentage charge of battery A'),
    DataElement(36, UINT16, 'ROBOT_REL_SOC_B', 'Percentage charge of battery B'),
    DataElement(38, DataFormatChargerState(), 'ROBOT_MOTOR_CHARGER_STATE', 'is battery charging?'),
    DataElement(40, UINT16, 'BUILD_NUMBER'),
    DataElement(42, UINT16, 'PWR_A_CURRENT'),
    DataElement(44, UINT16, 'PWR_B_CURRENT'),
    DataElement(46, UINT16, 'MOTOR_FLIPPER_ANGLE'),
    DataElement(48, UINT16, 'MOTOR_SIDE_FAN_SPEED', 'Side fan speed as currently commanded'),
    DataElement(50, UINT16, 'CLOSED_LOOP_CONTROL'),
    DataElement(52, DataFormatBatteryStatus(), 'BATTERY_STATUS_A'),
    DataElement(54, DataFormatBatteryStatus(), 'BATTERY_STATUS_B'),
    DataElement(56, UINT16, 'BATTERY_MODE_A'),
    DataElement(58, UINT16, 'BATTERY_MODE_B'),
    DataElement(60, UINT16, 'BATTERY_TEMP_A', 'in decikelvins above absolute 0'),
    DataElement(62, UINT16, 'BATTERY_TEMP_B', 'in decikelvins above absolute 0'),
    DataElement(64, UINT16, 'BATTERY_VOLTAGE_A', 'sampled from the smartbattery over I2C'),
    DataElement(66, UINT16, 'BATTERY_VOLTAGE_B', 'sampled from the smartbattery over I2C'),
    DataElement(68, INT16, 'BATTERY_CURRENT_A', 'current of the battery in mA. >0 = charging; <0 = discharging'),
    DataElement(70, INT16, 'BATTERY_CURRENT_B', 'current of the battery in mA. >0 = charging; <0 = discharging'),
]

OPENROVER_DATA_ELEMENTS = {e.index: e for e in elements}
