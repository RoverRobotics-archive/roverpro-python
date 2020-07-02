import statistics

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
    if version < OpenRoverFirmwareVersion(1, 9):
        await trio.sleep(3)
        # manual fan duty should revert to zero after timeout
        assert await rover.get_data(48) == 0
    elif version < OpenRoverFirmwareVersion(1, 10):
        pytest.skip("Fan speed control not implemented.")
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
    version = await rover.get_data(40)

    for i, de in OPENROVER_DATA_ELEMENTS.items():
        if de.supported(version):
            v = await rover.get_data(i)
            assert v is not None


@pytest.mark.motor
async def test_overspeed_fault(rover):
    v = await rover.get_data(40)
    if not OPENROVER_DATA_ELEMENTS[82].supported(v):
        pytest.skip("System Fault Flag not implemented in this version")

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
    version = await rover.get_data(40)
    counts_supported = all(OPENROVER_DATA_ELEMENTS[i].supported(version) for i in (14, 16))

    enc_counts_left = []
    enc_counts_right = []
    enc_intervals_left = []
    enc_intervals_right = []

    rover.set_motor_speeds(motor_effort, motor_effort, 0)

    for _ in range(30):
        rover.send_speed()
        await trio.sleep(0.1)

    element_ids = [28, 30]
    if counts_supported:
        element_ids += [14, 16]

    for _ in range(10):
        rover.send_speed()
        await trio.sleep(0.1)

        data = await rover.get_data_items(element_ids)
        if counts_supported:
            enc_counts_left.append(data[14])
            enc_counts_right.append(data[16])

        enc_intervals_left.append(data[28])
        enc_intervals_right.append(data[30])

    if motor_effort == 0:
        assert all(i == 0 or i > 500 for i in enc_intervals_left)
        assert all(i == 0 or i > 500 for i in enc_intervals_right)
    else:
        assert 0.005 < (1 / statistics.mean(enc_intervals_left)) / abs(motor_effort) < 0.05
        assert 0.005 < (1 / statistics.mean(enc_intervals_right)) / abs(motor_effort) < 0.05

    if counts_supported:
        encoder_delta_left = [
            fix_encoder_delta(a - b) for a, b in zip(enc_counts_left[1:], enc_counts_left)
        ]
        encoder_delta_right = [
            fix_encoder_delta(a - b) for a, b in zip(enc_counts_right[1:], enc_counts_right)
        ]
        if motor_effort == 0:
            assert all(i == 0 for i in encoder_delta_left)
            assert all(i == 0 for i in encoder_delta_right)
        else:
            assert all(20 < i / motor_effort < 500 for i in encoder_delta_left)
            assert all(20 < i / motor_effort < 500 for i in encoder_delta_right)


@pytest.mark.parametrize(
    "duty",
    [0.0, pytest.param(0.2, marks=pytest.mark.motor), pytest.param(0.5, marks=pytest.mark.motor)],
)
async def test_power_currents(rover, duty):
    await trio.sleep(1)
    rover.set_motor_speeds(duty, duty, 0)
    for i in range(10):
        rover.send_speed()
        await trio.sleep(0.1)
    battery_current_total = await rover.get_data(0)
    battery_current_a = await rover.get_data(42)
    battery_current_b = await rover.get_data(44)
    battery_current_a_i2c = await rover.get_data(68)
    battery_current_b_i2c = await rover.get_data(70)

    assert battery_current_a + battery_current_b == pytest.approx(battery_current_total, abs=0.2)
    assert battery_current_a == pytest.approx(abs(battery_current_a_i2c), abs=0.2)
    assert battery_current_b == pytest.approx(abs(battery_current_b_i2c), abs=0.2)


async def test_power_equal_soc(rover):
    battery_soc_a = await rover.get_data(34)
    battery_soc_b = await rover.get_data(36)
    assert battery_soc_a == pytest.approx(battery_soc_b, abs=0.08)


async def test_power_equal_current(rover):
    battery_current_a_i2c = await rover.get_data(68)
    battery_current_b_i2c = await rover.get_data(70)
    assert battery_current_a_i2c == pytest.approx(battery_current_b_i2c, abs=0.08)


async def test_power_equal_voltage(rover):
    battery_voltage_a_i2c = await rover.get_data(64)
    battery_voltage_b_i2c = await rover.get_data(66)
    assert battery_voltage_a_i2c == pytest.approx(battery_voltage_b_i2c, abs=0.08)


@pytest.mark.parametrize("battery", ["A", "B"])
async def test_power_soc(rover, battery):
    soc = await rover.get_data({"A": 34, "B": 36}[battery])
    assert 0 <= soc <= 1


@pytest.mark.parametrize("battery", ["A", "B"])
async def test_power_currents_charging(rover, battery):
    is_charging = await rover.get_data(38)
    assert is_charging in [True, False]
    battery_current_i2c = await rover.get_data({"A": 68, "B": 70}[battery])
    if is_charging:
        # charging battery has positive current
        assert battery_current_i2c >= 0
    else:
        # discharging battery should have negative current
        assert battery_current_i2c <= 0


@pytest.mark.parametrize("battery", ["A", "B"])
async def test_power_analog_i2c_voltages(rover, battery):
    battery_voltage_analog = await rover.get_data({"A": 24, "B": 26}[battery])
    battery_voltage_i2c = await rover.get_data({"A": 64, "B": 66}[battery])
    assert 12 < battery_voltage_i2c < 16.5
    assert 12 < battery_voltage_analog < 16.5

    assert battery_voltage_i2c == pytest.approx(battery_voltage_analog, abs=0.1)


async def test_fan_temperatures_equal(rover):
    fan_temp = await rover.get_data(20)
    fan_temp2 = await rover.get_data(22)
    assert 10 < fan_temp < 80
    assert 10 < fan_temp2 < 80
    assert fan_temp == pytest.approx(fan_temp2, abs=5)


async def test_battery_temperatures_equal(rover):
    battery_temp_a = await rover.get_data(60)
    battery_temp_b = await rover.get_data(62)

    # Rated operating temperature check batteries are between 10 and 55 degrees C
    assert 10 < battery_temp_a < 55
    assert 10 < battery_temp_b < 55
    assert battery_temp_a == pytest.approx(battery_temp_b, abs=5)


async def test_motor_status_braked(rover):
    v = await rover.get_data(40)
    if not all(OPENROVER_DATA_ELEMENTS[i].supported(v) for i in (72, 74, 76)):
        pytest.skip("Motor status flags not implemented in this version")

    rover.set_motor_speeds(0, 0, 0)
    statuses = (await rover.get_data(72), await rover.get_data(74), await rover.get_data(76))
    for s in statuses:
        assert isinstance(s, MotorStatusFlag)
        assert MotorStatusFlag.BRAKE in s


@pytest.mark.motor
@pytest.mark.parametrize("forward", [True, False], ids=["forward", "reverse"])
async def test_motor_status_moving(rover, forward):
    v = await rover.get_data(40)
    if not all(OPENROVER_DATA_ELEMENTS[i].supported(v) for i in (72, 74, 76)):
        pytest.skip("Motor status flags not implemented in this version")
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
