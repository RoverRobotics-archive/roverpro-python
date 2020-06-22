import statistics
from math import isclose

import pytest
import trio

from openrover.openrover_data import (
    fix_encoder_delta,
    MotorStatusFlag,
    OPENROVER_DATA_ELEMENTS,
    OpenRoverFirmwareVersion,
    SystemFaultFlag,
)
from openrover.rover import open_rover, Rover
from openrover.util import OpenRoverException, RoverDeviceNotFound


@pytest.fixture
async def rover():
    try:
        async with open_rover() as r:
            yield r
    except RoverDeviceNotFound:
        pytest.skip("This test requires a rover device but none was found")


async def test_find_openrover(rover):
    assert rover is not None
    assert isinstance(rover, Rover)


async def test_get_version(rover):
    version = await rover.get_data(40)
    assert isinstance(version, OpenRoverFirmwareVersion)

    version2 = await rover.get_data(40)
    assert version == version2
    assert 0 <= version.major <= 100
    assert 0 <= version.minor <= 100
    assert 0 <= version.patch <= 100


async def test_recover_from_bad_data(rover):
    await rover._rover_protocol._serial.write(b"test" * 20)

    for i in range(3):
        try:
            result = await rover.get_data(40)
            if result is not None:
                return
        except Exception as e:
            pass
    assert False


async def test_missing_device():
    with pytest.raises(OpenRoverException):
        async with open_rover("missing_device"):
            pass


@pytest.mark.parametrize("fan_speed_cmd", [0.1, 0.4, 0.7])
async def test_fan_speed(rover, fan_speed_cmd):
    version = await rover.get_data(40)

    rover.set_fan_speed(fan_speed_cmd)
    assert await rover.get_data(48) == fan_speed_cmd

    if (version.major, version.minor) < (1, 10):
        await trio.sleep(1)
        # manual fan duty should revert to zero after  timeout
        assert await rover.get_data(48) == 0
    else:
        speeds_a = []
        speeds_b = []

        # wait a moment for fan duty to catch up with commanded value
        await trio.sleep(0.1)

        for i in range(int(fan_speed_cmd * 40)):
            speeds_a.append(await rover.get_data(78))
            speeds_b.append(await rover.get_data(80))
            await trio.sleep(0.5)

        # fan speeds should all be between 0 and 1
        assert all(0 <= x <= 1 for x in speeds_a)
        assert all(0 <= x <= 1 for x in speeds_b)

        # fan duty should start at the commanded value
        assert speeds_a[0] == pytest.approx(fan_speed_cmd, abs=0.05)
        assert speeds_b[0] == pytest.approx(fan_speed_cmd, abs=0.05)

        # fan duty should decrease
        assert speeds_a == sorted(speeds_a, reverse=True)
        assert speeds_b == sorted(speeds_b, reverse=True)

        # fan duty should end near zero
        assert speeds_a[-1] == pytest.approx(0, abs=0.05)
        assert speeds_b[-1] == pytest.approx(0, abs=0.05)


async def test_get_all_data_elements(rover):
    for i, de in OPENROVER_DATA_ELEMENTS.items():
        if not de.not_implemented:
            v = await rover.get_data(i)
            assert v is not None


@pytest.mark.motor
async def test_overspeed_fault(rover):
    rover.clear_system_fault()
    assert await rover.get_data(82) == SystemFaultFlag.NONE

    enc_counts_left = []
    enc_counts_right = []
    enc_intervals_left = []
    enc_intervals_right = []
    rover.set_motor_speeds(1.0, 1.0, 0)
    for _ in range(50):
        rover.send_speed()
        await trio.sleep(0.1)
        data = await rover.get_data_items([14, 16, 28, 30])
        enc_counts_left.append(data[14])
        enc_counts_right.append(data[16])
        enc_intervals_left.append(data[28])
        enc_intervals_right.append(data[30])

    # motors running at full speed
    for x in enc_intervals_left[5:20]:
        assert x < 100
    for x in enc_intervals_right[5:20]:
        assert x < 100

    # motors should come to a stop
    for x in enc_intervals_left[40:]:
        assert x > 1000 or x == 0
    for x in enc_intervals_right[40:]:
        assert x > 1000 or x == 0

    assert await rover.get_data(82) == SystemFaultFlag.OVERSPEED

    enc_intervals_left2 = []
    enc_intervals_right2 = []
    rover.set_motor_speeds(0.2, 0.2, 0)
    for _ in range(10):
        rover.send_speed()
        await trio.sleep(0.1)
        assert rover.get_data(28)
        data = await rover.get_data_items([28, 30])
        enc_intervals_left2.append(data[28])
        enc_intervals_right2.append(data[30])

    # fault condition still active so motor speeds should be ignored
    assert all(x == 0 or x > 1000 for x in enc_intervals_left2)
    assert all(x == 0 or x > 1000 for x in enc_intervals_right2)
    assert await rover.get_data(82) == SystemFaultFlag.OVERSPEED

    rover.clear_system_fault()
    assert await rover.get_data(82) == SystemFaultFlag.NONE


@pytest.mark.parametrize("motor_effort", [0, -0.1, +0.1, -0.2, +0.2, 0])
@pytest.mark.motor
async def test_encoder_intervals(rover, motor_effort):
    enc_counts_left = []
    enc_counts_right = []
    enc_intervals_left = []
    enc_intervals_right = []

    rover.set_motor_speeds(motor_effort, motor_effort, 0)

    for _ in range(30):
        rover.send_speed()
        await trio.sleep(0.1)

    for _ in range(10):
        rover.send_speed()
        await trio.sleep(0.1)
        data = await rover.get_data_items([14, 16, 28, 30])
        enc_counts_left.append(data[14])
        enc_counts_right.append(data[16])
        enc_intervals_left.append(data[28])
        enc_intervals_right.append(data[30])

    encoder_delta_left = [
        fix_encoder_delta(a - b) for a, b in zip(enc_counts_left[1:], enc_counts_left)
    ]
    encoder_delta_right = [
        fix_encoder_delta(a - b) for a, b in zip(enc_counts_right[1:], enc_counts_right)
    ]

    if motor_effort == 0:
        assert all(i == 0 for i in encoder_delta_left)
        assert all(i == 0 for i in encoder_delta_right)

        assert all(i == 0 or i > 500 for i in enc_intervals_left)
        assert all(i == 0 or i > 500 for i in enc_intervals_right)
    else:
        assert all(20 < i / motor_effort < 500 for i in encoder_delta_left)
        assert all(20 < i / motor_effort < 500 for i in encoder_delta_right)

        assert 0.005 < (1 / statistics.mean(enc_intervals_left)) / abs(motor_effort) < 0.05
        assert 0.005 < (1 / statistics.mean(enc_intervals_right)) / abs(motor_effort) < 0.05


async def test_currents(rover):
    await trio.sleep(3)
    battery_current_a = await rover.get_data(42)
    battery_current_b = await rover.get_data(44)
    battery_current_a_i2c = await rover.get_data(68)
    battery_current_b_i2c = await rover.get_data(70)

    # must agree within 5% or 200mA
    assert isclose(battery_current_a, abs(battery_current_a_i2c), rel_tol=0.05, abs_tol=0.2)
    assert isclose(battery_current_b, abs(battery_current_b_i2c), rel_tol=0.05, abs_tol=0.2)

    battery_current_total = await rover.get_data(0)
    assert isclose(
        battery_current_a + battery_current_b, battery_current_total, rel_tol=0.05, abs_tol=0.2
    )


async def test_soc(rover):
    battery_soc_a = await rover.get_data(34)
    battery_soc_b = await rover.get_data(36)
    assert 0 <= battery_soc_a <= 1
    assert 0 <= battery_soc_b <= 1
    assert isclose(battery_soc_a, battery_soc_b, rel_tol=0.1, abs_tol=0.1)


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


async def test_voltages(rover):
    battery_voltage_a = await rover.get_data(24)
    battery_voltage_a_i2c = await rover.get_data(64)
    assert 12 < battery_voltage_a_i2c < 16.5
    assert 12 < battery_voltage_a < 16.5
    # must agree within 5% or 50mV
    assert isclose(battery_voltage_a_i2c, battery_voltage_a, rel_tol=0.05, abs_tol=0.05)

    battery_voltage_b = await rover.get_data(26)
    battery_voltage_b_i2c = await rover.get_data(66)
    assert 12 < battery_voltage_b_i2c < 16.5
    assert 12 < battery_voltage_b < 16.5
    # must agree within 5% or 50mV
    assert isclose(battery_voltage_b_i2c, battery_voltage_b, rel_tol=0.05, abs_tol=0.05)


async def test_temperatures(rover):
    fan_temp = await rover.get_data(20)
    assert 10 < fan_temp < 55

    battery_temp_a = await rover.get_data(60)
    battery_temp_b = await rover.get_data(62)

    # Rated operating temperature check batteries are between 10 and 55 degrees C
    assert 10 < battery_temp_a < 55
    assert 10 < battery_temp_b < 55
    assert abs(battery_temp_a - battery_temp_b) < 5


async def test_motor_status_braked(rover):
    rover.set_motor_speeds(0, 0, 0)
    statuses = (await rover.get_data(72), await rover.get_data(74), await rover.get_data(76))
    for s in statuses:
        assert isinstance(s, MotorStatusFlag)
        assert MotorStatusFlag.BRAKE in s


@pytest.mark.motor
@pytest.mark.parametrize("forward", [True, False], ids=["forward", "reverse"])
async def test_motor_status_moving(rover, forward):
    speed = 0.2
    if forward:
        rover.set_motor_speeds(+speed, -speed, +speed)
    else:
        rover.set_motor_speeds(-speed, +speed, -speed)

    for i in range(10):
        rover.send_speed()
        await trio.sleep(0.15)

    statuses = (await rover.get_data(72), await rover.get_data(74), await rover.get_data(76))

    for s in statuses:
        assert isinstance(s, MotorStatusFlag)
        if forward:
            assert MotorStatusFlag.REVERSE not in s
        else:
            assert MotorStatusFlag.REVERSE in s

        assert MotorStatusFlag.BRAKE not in s
