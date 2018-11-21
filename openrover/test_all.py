from collections import Counter
from math import isclose
import time
from typing import Iterable

import pytest
from pytest import xfail
import serial
import serial.tools.list_ports
from openrover import OpenRover, iterate_openrovers, find_openrover
import statistics


@pytest.fixture
def rover():
    with OpenRover() as o:
        yield o


def test_list_openrover_devices():
    for s in iterate_openrovers():
        assert isinstance(s, str)


def test_create():
    o = OpenRover()
    assert o is not None


def test_missing_device():
    o = OpenRover(port='missingdevice')
    with pytest.raises(serial.SerialException):
        o.open()


def test_build_number(rover):
    build_no = rover.get_data_synchronous(40)
    assert isinstance(build_no, int)
    assert 40000 < build_no < 50000


def test_encoder_counts(rover):
    enc_counts_1 = (rover.get_data_synchronous(14), rover.get_data_synchronous(16))
    time.sleep(0.1)
    enc_counts_2 = (rover.get_data_synchronous(14), rover.get_data_synchronous(16))
    assert enc_counts_1 == enc_counts_2

    rover.set_motor_speeds(0.2, 0.2, 0.2)
    rover.send_speed()
    time.sleep(0.1)

    enc_counts_3 = (rover.get_data_synchronous(14), rover.get_data_synchronous(16))
    enc_diff = ((enc_counts_3[0] - enc_counts_2[0]) % (2 ** 16),
                (enc_counts_3[1] - enc_counts_2[1]) % 2 ** 16)
    assert 0 < enc_diff[0] < 200
    assert 0 < enc_diff[1] < 200


def test_encoder_intervals_still(rover):
    time.sleep(1)
    enc_counts_left = []
    enc_counts_right = []
    enc_intervals_left = []
    enc_intervals_right = []
    rover.set_motor_speeds(0, 0, 0)

    for i in range(5):
        rover.send_speed()
        time.sleep(0.1)
        enc_counts_left.append(rover.get_data_synchronous(14))
        enc_counts_right.append(rover.get_data_synchronous(16))
        enc_intervals_left.append(rover.get_data_synchronous(28))
        enc_intervals_right.append(rover.get_data_synchronous(30))

    assert constant(enc_counts_left)
    assert constant(enc_counts_right)
    assert all(i == 0 for i in enc_intervals_left)
    assert all(i == 0 for i in enc_intervals_right)


def constant(L):
    return all(x == y for x, y in zip(L, L[1:]))


def strictly_increasing(L):
    return all(x < y for x, y in zip(L, L[1:]))


def strictly_decreasing(L):
    return all(x > y for x, y in zip(L, L[1:]))


def test_encoder_intervals_forward(rover):
    enc_counts_left = []
    enc_counts_right = []
    enc_intervals_left = []
    enc_intervals_right = []

    rover.set_motor_speeds(0.1, 0.1, 0)

    for i in range(20):
        rover.send_speed()
        time.sleep(0.1)
        enc_counts_left.append(rover.get_data_synchronous(14))
        enc_counts_right.append(rover.get_data_synchronous(16))
        enc_intervals_left.append(rover.get_data_synchronous(28))
        enc_intervals_right.append(rover.get_data_synchronous(30))

    assert strictly_increasing(enc_counts_left)
    assert strictly_increasing(enc_counts_right)

    assert 0 < statistics.mean(enc_intervals_left) < 50000
    assert 0.001 < statistics.stdev(enc_intervals_left) < statistics.mean(enc_intervals_left) * 0.1


def test_fan_speed(rover):
    for i in range(0, 241, 20):
        rover.set_fan_speed(i)
        time.sleep(0.1)
        assert i == rover.get_data_synchronous(48)


def test_encoder_intervals_backward(rover):
    enc_counts_left = []
    enc_counts_right = []
    enc_intervals_left = []
    enc_intervals_right = []

    rover.set_motor_speeds(-0.1, -0.1, 0)

    for i in range(20):
        rover.send_speed()
        time.sleep(0.1)
        enc_counts_left.append(rover.get_data_synchronous(14))
        enc_counts_right.append(rover.get_data_synchronous(16))
        enc_intervals_left.append(rover.get_data_synchronous(28))
        enc_intervals_right.append(rover.get_data_synchronous(30))

    assert strictly_decreasing(enc_counts_left)
    assert strictly_decreasing(enc_counts_right)

    assert 0 < statistics.mean(enc_intervals_left) < 50000
    assert 0.001 < statistics.stdev(enc_intervals_left) < statistics.mean(enc_intervals_left) * 0.1


def test_power_system_feedback_charging(rover):
    is_charging = rover.get_data_synchronous(38)
    if is_charging == False:
        pytest.skip('Robot is not on charging dock')
    assert is_charging == True

    battery_voltage_a_i2c = rover.get_data_synchronous(64)
    assert 14 < battery_voltage_a_i2c / 1000 < 18  # voltage should be between 14-18 V

    battery_voltage_b_i2c = rover.get_data_synchronous(66)
    assert 14 < battery_voltage_b_i2c / 1000 < 18

    battery_temp_a = rover.get_data_synchronous(60)
    battery_temp_b = rover.get_data_synchronous(62)
    assert 0 < (battery_temp_a / 10 - 273.15) < 100
    assert 0 < (battery_temp_b / 10 - 273.15) < 100

    # TODO
    """
    battery_current_a = rover.get_data_synchronous(42)
    battery_current_b = rover.get_data_synchronous(44)
    battery_current_a_i2c = rover.get_data_synchronous(68)
    battery_current_b_i2c = rover.get_data_synchronous(70)
    if is_charging:
        assert battery_current_a_i2c >= 0
        assert battery_current_b_i2c >= 0
    else:
        assert battery_current_a_i2c < 0
        assert battery_current_b_i2c < 0

    battery_current_total = rover.get_data_synchronous(0)
    assert abs(battery_current_a + battery_current_b - battery_current_total) < 4
    assert 3 < rover.get_data_synchronous(0) < 100  # total current
    """


def test_power_system_feedback_notcharging(rover):
    is_charging = rover.get_data_synchronous(38)
    if is_charging == True:
        pytest.skip('Robot is on charging dock')
    assert is_charging == False

    battery_voltage_a = rover.get_data_synchronous(24) / 58
    battery_voltage_a_i2c = rover.get_data_synchronous(64) / 1000
    assert 14 < battery_voltage_a_i2c < 18  # voltage should be between 14-18 V
    assert 14 < battery_voltage_a < 18
    # must agree within 5% or 50mV
    assert isclose(battery_voltage_a_i2c, battery_voltage_a, rel_tol=0.05, abs_tol=0.05)

    battery_soc_a = rover.get_data_synchronous(34)
    battery_soc_b = rover.get_data_synchronous(34)
    assert 0 <= battery_soc_a <= 100
    assert 0 <= battery_soc_b <= 100
    assert abs(battery_soc_a - battery_soc_b) < 10

    battery_voltage_b = rover.get_data_synchronous(26) / 58
    battery_voltage_b_i2c = rover.get_data_synchronous(66) / 1000
    assert 14 < battery_voltage_b_i2c < 18
    assert 14 < battery_voltage_b < 18
    # must agree within 5% or 50mV
    assert isclose(battery_voltage_b_i2c, battery_voltage_b, rel_tol=0.05, abs_tol=0.05)

    battery_temp_a = rover.get_data_synchronous(60) / 10 - 273.15
    battery_temp_b = rover.get_data_synchronous(62) / 10 - 273.15
    # check batteries are between 10 and 55 degrees C
    assert 10 < (battery_temp_a) < 55
    assert 10 < (battery_temp_b) < 55

    battery_current_a = rover.get_data_synchronous(42) / 34
    battery_current_b = rover.get_data_synchronous(44) / 34
    battery_current_a_i2c = rover.get_data_synchronous(68) / 1000
    battery_current_b_i2c = rover.get_data_synchronous(70) / 1000
    # discharging battery should have negative current
    assert battery_current_a_i2c < 0
    assert battery_current_b_i2c < 0
    # must agree within 5% or 50mA
    assert isclose(battery_current_a, abs(battery_current_a_i2c), rel_tol=0.05, abs_tol=0.05)
    assert isclose(battery_current_b, abs(battery_current_b_i2c), rel_tol=0.05, abs_tol=0.05)

    battery_current_total = rover.get_data_synchronous(0) / 34
    assert isclose(battery_current_a + battery_current_b, battery_current_total, rel_tol=0.05, abs_tol=.05)
