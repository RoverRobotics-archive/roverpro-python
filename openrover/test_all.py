import asyncio
import statistics
import time

from math import isclose
import pytest

from openrover import OpenRover, OpenRoverException
from openrover_data import OpenRoverFirmwareVersion
from unasync_decorator import unasync

loop = asyncio.get_event_loop()


@pytest.fixture
@unasync
async def rover():
    async with OpenRover() as o:
        yield o
    pass


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
    rover._rover_protocol._writer.write(b'test' * 20)

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


@unasync
async def test_encoder_counts():
    async with OpenRover() as rover:
        enc_counts_1 = (await rover.get_data(14), await rover.get_data(16))
        await asyncio.sleep(0.3)
        enc_counts_2 = (await rover.get_data(14), await rover.get_data(16))
        assert enc_counts_1 == enc_counts_2

        rover.set_motor_speeds(0.2, 0.2, 0.2)
        rover.send_speed()
        await asyncio.sleep(0.3)

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
        data = await rover.get_data_items([14, 16, 28, 30])
        enc_counts_left.append(data[14])
        enc_counts_right.append(data[16])
        enc_intervals_left.append(data[28])
        enc_intervals_right.append(data[30])

    # note this test may fail if the rover wheels have any significant resistance, since this may cause the motors to "kick" backwards
    assert strictly_decreasing(enc_counts_left)
    assert strictly_decreasing(enc_counts_right)

    assert 0 < statistics.mean(enc_intervals_left) < 50000
    assert 0.001 < statistics.stdev(enc_intervals_left) < statistics.mean(enc_intervals_left) * 0.1


@unasync
async def test_currents(rover):
    battery_current_a = await rover.get_data(42)
    battery_current_b = await rover.get_data(44)
    battery_current_a_i2c = await rover.get_data(68)
    battery_current_b_i2c = await rover.get_data(70)

    # must agree within 5% or 200mA
    assert isclose(battery_current_a, abs(battery_current_a_i2c), rel_tol=0.05, abs_tol=0.2)
    assert isclose(battery_current_b, abs(battery_current_b_i2c), rel_tol=0.05, abs_tol=0.2)

    battery_current_total = await rover.get_data(0)
    assert isclose(battery_current_a + battery_current_b, battery_current_total, rel_tol=0.05, abs_tol=.05)


@unasync
async def test_soc(rover):
    battery_soc_a = await rover.get_data(34)
    battery_soc_b = await rover.get_data(34)
    assert 0 <= battery_soc_a <= 1
    assert 0 <= battery_soc_b <= 1
    assert isclose(battery_soc_a, battery_soc_b, rel_tol=0.1, abs_tol=0.1)


@unasync
async def test_currents_charging(rover):
    is_charging = await rover.get_data(38)
    assert is_charging in [True, False]

    battery_current_a_i2c = await rover.get_data(68)
    battery_current_b_i2c = await rover.get_data(70)
    if is_charging:
        # charging battery has positive current
        assert battery_current_a_i2c >= 0
        assert battery_current_b_i2c >= 0
    else:
        # discharging battery should have negative current
        assert battery_current_a_i2c <= 0
        assert battery_current_b_i2c <= 0


@unasync
async def test_voltages(rover):
    battery_voltage_a = await rover.get_data(24)
    battery_voltage_a_i2c = await rover.get_data(64)
    assert 14 < battery_voltage_a_i2c < 18  # voltage should be between 14-18 V
    assert 14 < battery_voltage_a < 18
    # must agree within 5% or 50mV
    assert isclose(battery_voltage_a_i2c, battery_voltage_a, rel_tol=0.05, abs_tol=0.05)

    battery_voltage_b = await rover.get_data(26)
    battery_voltage_b_i2c = await rover.get_data(66)
    assert 14 < battery_voltage_b_i2c < 18
    assert 14 < battery_voltage_b < 18
    # must agree within 5% or 50mV
    assert isclose(battery_voltage_b_i2c, battery_voltage_b, rel_tol=0.05, abs_tol=0.05)


@unasync
async def test_temperatures(rover):
    fan_temp = await rover.get_data(20)
    assert 10 < fan_temp < 55

    battery_temp_a = await rover.get_data(60)
    battery_temp_b = await rover.get_data(62)

    # Rated operating temperature check batteries are between 10 and 55 degrees C
    assert 10 < battery_temp_a < 55
    assert 10 < battery_temp_b < 55
    assert abs(battery_temp_a - battery_temp_b) < 5
