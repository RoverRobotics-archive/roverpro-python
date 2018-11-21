import time
from typing import Iterable

import pytest
from pytest import xfail
import serial
import serial.tools.list_ports
from openrover import OpenRover, iterate_openrovers, find_openrover


@pytest.fixture
def rover():
    try:
        p = find_openrover()
    except StopIteration:
        pytest.skip('Could not find attached Rover')
    o = OpenRover()
    o.open(p)

    yield o

    o.close()


def test_list_openrover_devices():
    for s in iterate_openrovers():
        assert isinstance(s, str)


def test_create():
    o = OpenRover()
    assert o is not None


def test_missing_device():
    o = OpenRover()
    with pytest.raises(serial.SerialException):
        o.open('missingdevice')


def test_build_number(rover):
    time.sleep(0.1)
    build_no = rover.get_data_synchronous(40)
    assert isinstance(build_no, int)
    assert 40000 < build_no < 50000


# not yet working
@pytest.mark.xfail
def test_encoder_intervals(rover):
    time.sleep(1)
    encoder_intervals = (rover.get_data_synchronous(28), rover.get_data_synchronous(30))
    assert encoder_intervals == (0, 0)

    rover.set_motor_speeds(0.2, 0.2, 0)
    time.sleep(0.1)
    encoder_intervals_2 = (rover.get_data_synchronous(28), rover.get_data_synchronous(30))
    assert encoder_intervals_2[0] > 0
    assert encoder_intervals_2[1] > 0

    time.sleep(1)
    rover.set_motor_speeds(-0.2, -0.2, 0)
    time.sleep(0.1)
    encoder_intervals_2 = (rover.get_data_synchronous(28), rover.get_data_synchronous(30))
    assert abs(encoder_intervals_2[0]) > 0
    assert abs(encoder_intervals_2[1]) > 0


def test_encoder_counts(rover):
    enc_counts_1 = (rover.get_data_synchronous(14), rover.get_data_synchronous(16))
    time.sleep(0.1)
    enc_counts_2 = (rover.get_data_synchronous(14), rover.get_data_synchronous(16))
    assert enc_counts_1 == enc_counts_2

    rover.set_motor_speeds(0.2, 0.2, 0.2)
    rover.send_speed()
    time.sleep(0.1)

    enc_counts_3 = (rover.get_data_synchronous(14), rover.get_data_synchronous(16))

    assert 0 < ((enc_counts_3[0] - enc_counts_2[0] + 2 ** 16) % (2 ** 16)) < 200

