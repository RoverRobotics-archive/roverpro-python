import asyncio
from functools import wraps
from typing import Awaitable, AsyncIterable, Generator

from math import isclose
import statistics
import time

import pytest

from openrover import OpenRover, OpenRoverException, iterate_openrovers, find_openrover
from openrover_data import OpenRoverFirmwareVersion
from unasync_decorator import unasync

loop = asyncio.get_event_loop()

import inspect


@pytest.fixture
@unasync
async def rover():
    async with OpenRover() as o:
        yield o
    pass


@unasync
async def test_list_openrover_devices():
    async for s in iterate_openrovers():
        assert isinstance(s, str)


def test_find_openrover():
    rover = asyncio.get_event_loop().run_until_complete(find_openrover())
    assert rover is not None
    assert isinstance(rover, str)


def test_create():
    o = OpenRover()
    assert o is not None


@unasync
async def test_get_version(rover):
    assert await rover.get_data(40) is not None


@unasync
async def test_recover_from_bad_data(rover):
    rover._connection.writer.write(b'test' * 20)
    for i in range(3):
        try:
            result = await rover.get_data(40)
            if result is not None:
                return
        except Exception as e:
            pass
    assert False


@unasync
async def test_missing_device():
    rover = OpenRover(port='missingdevice')
    with pytest.raises(OpenRoverException):
        try:
            await rover.aopen()
        except Exception as e:
            raise


@unasync
async def test_build_number():
    async with OpenRover() as rover:
        build_no = await rover.get_data(40)
        assert build_no is not None
        assert isinstance(build_no, OpenRoverFirmwareVersion)
        assert 0 <= build_no.major < 100
        assert 0 <= build_no.minor < 100
        assert 0 <= build_no.patch < 100


def test_build_number2(rover):
    async def foo():
        build_no = await rover.get_data(40)
        assert build_no is not None
        assert isinstance(build_no, OpenRoverFirmwareVersion)
        assert 0 <= build_no.major < 100
        assert 0 <= build_no.minor < 100
        assert 0 <= build_no.patch < 100

    asyncio.get_event_loop().run_until_complete(foo())


@unasync
async def test_encoder_counts():
    async with OpenRover() as rover:
        enc_counts_1 = (await rover.get_data(14), await rover.get_data(16))
        await asyncio.sleep(0.1)
        enc_counts_2 = (await rover.get_data(14), await rover.get_data(16))
        assert enc_counts_1 == enc_counts_2

        rover.set_motor_speeds(0.2, 0.2, 0.2)
        rover.send_speed()
        await asyncio.sleep(0.1)

        enc_counts_3 = (await rover.get_data(14), await rover.get_data(16))
        enc_diff = ((enc_counts_3[0] - enc_counts_2[0]) % (2 ** 16),
                    (enc_counts_3[1] - enc_counts_2[1]) % 2 ** 16)
        assert 0 < enc_diff[0] < 200
        assert 0 < enc_diff[1] < 200


@unasync
async def test_encoder_intervals_still(rover):
    await asyncio.sleep(2)
    enc_counts_left = []
    enc_counts_right = []
    enc_intervals_left = []
    enc_intervals_right = []
    rover.set_motor_speeds(0, 0, 0)

    for i in range(5):
        rover.send_speed()
        await asyncio.sleep(0.1)
        enc_counts_left.append(await rover.get_data(14))
        enc_counts_right.append(await rover.get_data(16))
        enc_intervals_left.append(await rover.get_data(28))
        enc_intervals_right.append(await rover.get_data(30))

    assert constant(enc_counts_left)
    assert constant(enc_counts_right)
    for i in enc_intervals_left:
        assert i == 0
    for i in enc_intervals_right:
        assert i == 0


def constant(L):
    return all(x == y for x, y in zip(L, L[1:]))


def strictly_increasing(L):
    return all(x < y for x, y in zip(L, L[1:]))


def strictly_decreasing(L):
    return all(x > y for x, y in zip(L, L[1:]))


@unasync
async def test_encoder_intervals_forward(rover):
    enc_counts_left = []
    enc_counts_right = []
    enc_intervals_left = []
    enc_intervals_right = []

    rover.set_motor_speeds(0.1, 0.1, 0)

    for i in range(20):
        rover.send_speed()
        time.sleep(0.1)
        enc_counts_left.append(await rover.get_data(14))
        enc_counts_right.append(await rover.get_data(16))
        enc_intervals_left.append(await rover.get_data(28))
        enc_intervals_right.append(await rover.get_data(30))

    # note this test may fail if the rover wheels have any significant resistance, since this may cause the motors to "kick" backwards
    assert strictly_increasing(enc_counts_left)
    assert strictly_increasing(enc_counts_right)

    assert 0 < statistics.mean(enc_intervals_left) < 50000
    assert 0.001 < statistics.stdev(enc_intervals_left) < statistics.mean(enc_intervals_left) * 0.1


@unasync
async def test_fan_speed(rover):
    for i in range(0, 241, 20):
        rover.set_fan_speed(i)
        await asyncio.sleep(0.1)
        assert i == await rover.get_data(48)


@unasync
async def test_encoder_intervals_backward(rover):
    enc_counts_left = []
    enc_counts_right = []
    enc_intervals_left = []
    enc_intervals_right = []

    rover.set_motor_speeds(-0.1, -0.1, 0)

    for i in range(20):
        rover.send_speed()
        await asyncio.sleep(0.1)
        enc_counts_left.append(await rover.get_data(14))
        enc_counts_right.append(await rover.get_data(16))
        enc_intervals_left.append(await rover.get_data(28))
        enc_intervals_right.append(await rover.get_data(30))

    # note this test may fail if the rover wheels have any significant resistance, since this may cause the motors to "kick" backwards
    assert strictly_decreasing(enc_counts_left)
    assert strictly_decreasing(enc_counts_right)

    assert 0 < statistics.mean(enc_intervals_left) < 50000
    assert 0.001 < statistics.stdev(enc_intervals_left) < statistics.mean(enc_intervals_left) * 0.1


@unasync
async def test_power_system_feedback_charging(rover):
    is_charging = await rover.get_data(38)
    if is_charging == False:
        pytest.skip('Robot is not on charging dock')
    assert is_charging == True

    battery_voltage_a_i2c = await rover.get_data(64)
    assert 14 < battery_voltage_a_i2c / 1000 < 18  # voltage should be between 14-18 V

    battery_voltage_b_i2c = await rover.get_data(66)
    assert 14 < battery_voltage_b_i2c / 1000 < 18

    battery_temp_a = await rover.get_data(60)
    battery_temp_b = await rover.get_data(62)
    assert 0 < (battery_temp_a / 10 - 273.15) < 100
    assert 0 < (battery_temp_b / 10 - 273.15) < 100

    # TODO
    """
    battery_current_a = await rover.get_data(42)
    battery_current_b = await rover.get_data(44)
    battery_current_a_i2c = await rover.get_data(68)
    battery_current_b_i2c = await rover.get_data(70)
    if is_charging:
        assert battery_current_a_i2c >= 0
        assert battery_current_b_i2c >= 0
    else:
        assert battery_current_a_i2c < 0
        assert battery_current_b_i2c < 0

    battery_current_total = await rover.get_data(0)
    assert abs(battery_current_a + battery_current_b - battery_current_total) < 4
    assert 3 < await rover.get_data(0) < 100  # total current
    """


@unasync
async def test_power_system_feedback_notcharging(rover):
    is_charging = await rover.get_data(38)
    if is_charging == True:
        pytest.skip('Robot is on charging dock')
    assert is_charging == False

    battery_voltage_a = await rover.get_data(24) / 58
    battery_voltage_a_i2c = await rover.get_data(64) / 1000
    assert 14 < battery_voltage_a_i2c < 18  # voltage should be between 14-18 V
    assert 14 < battery_voltage_a < 18
    # must agree within 5% or 50mV
    assert isclose(battery_voltage_a_i2c, battery_voltage_a, rel_tol=0.05, abs_tol=0.05)

    battery_soc_a = await rover.get_data(34)
    battery_soc_b = await rover.get_data(34)
    assert 0 <= battery_soc_a <= 100
    assert 0 <= battery_soc_b <= 100
    assert abs(battery_soc_a - battery_soc_b) < 10

    battery_voltage_b = await rover.get_data(26) / 58
    battery_voltage_b_i2c = await rover.get_data(66) / 1000
    assert 14 < battery_voltage_b_i2c < 18
    assert 14 < battery_voltage_b < 18
    # must agree within 5% or 50mV
    assert isclose(battery_voltage_b_i2c, battery_voltage_b, rel_tol=0.05, abs_tol=0.05)

    battery_temp_a = await rover.get_data(60) / 10 - 273.15
    battery_temp_b = await rover.get_data(62) / 10 - 273.15
    # check batteries are between 10 and 55 degrees C
    assert 10 < (battery_temp_a) < 55
    assert 10 < (battery_temp_b) < 55

    battery_current_a = await rover.get_data(42) / 34
    battery_current_b = await rover.get_data(44) / 34
    battery_current_a_i2c = await rover.get_data(68) / 1000
    battery_current_b_i2c = await rover.get_data(70) / 1000
    # discharging battery should have negative current
    assert battery_current_a_i2c < 0
    assert battery_current_b_i2c < 0
    # must agree within 5% or 50mA
    assert isclose(battery_current_a, abs(battery_current_a_i2c), rel_tol=0.05, abs_tol=0.05)
    assert isclose(battery_current_b, abs(battery_current_b_i2c), rel_tol=0.05, abs_tol=0.05)

    battery_current_total = await rover.get_data(0) / 34
    assert isclose(battery_current_a + battery_current_b, battery_current_total, rel_tol=0.05, abs_tol=.05)
