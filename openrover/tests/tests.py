import time

import pytest
import serial
from serial import SerialException
import serial.tools.list_ports

from .openrover import OpenRover


@pytest.fixture
def rover():
    p = find_rover_port()
    if p is None:
        pytest.skip('Could not find attached Rover')
    o = OpenRover()
    o.open(p)

    yield o

    o.close()


def test_raw_serial():
    p = find_rover_port()
    with serial.Serial(p, baudrate=57600, stopbits=1, write_timeout=2, timeout=2, inter_byte_timeout=2) as ser:
        time.sleep(0.2)
        scratch = ser.read_all()  # often when opening the device, we get a 0x255 as an initial value on the wire
        time.sleep(0.2)
        # Hardcoded request for build number
        ser.write(bytearray([253, 125, 125, 125, 10, 40, 85]))
        reply = list(ser.read(20))
        assert reply[:3] == [253, 40, 158]


def test_create():
    o = OpenRover()
    assert o is not None


def test_missing_device():
    o = OpenRover()
    with pytest.raises(SerialException):
        o.open('missingdevice')


def find_rover_port():
    for c in serial.tools.list_ports.comports():
        if c.serial_number == 'FTA7T1MGA':
            # this is the serial number for Dan's FTDI cable.
            # just because it's plugged in doesn't actually mean there's a robot on the other end of it.
            return c.device
    return None


def test_can_connect():
    o = OpenRover()
    o.open(find_rover_port())
    o.close()


def test_build_number(rover):
    time.sleep(0.1)
    build_no = rover.get_data_synchronous(40)
    assert isinstance(build_no, int)
    assert 40000 < build_no < 50000


def test_speed(rover):
    encoder_intervals = (rover.get_data_synchronous(28), rover.get_data_synchronous(30))
    assert encoder_intervals == (0, 0)

    rover.set_motor_speeds(1, 1, 1)
    time.sleep(0.4)

    encoder_intervals = (rover.get_data_synchronous(28), rover.get_data_synchronous(30))
    assert encoder_intervals == (0, 0)

    rover.send_speed()
    time.sleep(0.4)

    encoder_intervals = (rover.get_data_synchronous(28), rover.get_data_synchronous(30))
    assert encoder_intervals != (0, 0)
