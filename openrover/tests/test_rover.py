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
        except (OpenRoverException, trio.TooSlowError):
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
        pytest.xfail("Fan speed control not implemented.")
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
        pytest.xfail("System Fault Flag not implemented in this version")

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
    ("elt_a", "elt_b", "delta"),
    (
        pytest.param(52, 54, None, id="battery status"),
        pytest.param(34, 36, 0.03, id="state of charge"),
        pytest.param(60, 62, 3, id="temperature"),
        pytest.param(24, 26, 0.01, id="voltage (external)", marks=pytest.mark.xfail),
        pytest.param(64, 66, 0.01, id="voltage (internal)"),
        pytest.param(42, 44, 0.05, id="current (external)", marks=pytest.mark.xfail),
        pytest.param(68, 70, 0.05, id="current (internal)"),
    ),
)
async def test_batteries_similar(rover, elt_a, elt_b, delta):
    value_a = await rover.get_data(elt_a)
    value_b = await rover.get_data(elt_b)
    if delta is None:
        assert value_a == value_b
    else:
        assert value_a == pytest.approx(value_b, abs=delta)


SANE_RANGE = {
    0: (0, 2),
    6: (0, 1023),
    8: (0, 1023),
    10: (0, 1),
    12: (0, 1),
    14: (0, 2 ** 16 - 1),
    16: (0, 2 ** 16 - 1),
    20: (10, 70),
    22: (10, 70),
    24: (12, 16.5),
    26: (12, 16.5),
    28: (0, 2 ** 16 - 1),
    30: (0, 2 ** 16 - 1),
    34: (0, 1),
    36: (0, 1),
    42: (0, 1),
    44: (0, 1),
    60: (10, 55),
    62: (10, 55),
    64: (12, 16.5),
    66: (12, 16.5),
    68: (-16.5, +16.5),
    70: (-16.5, +16.5),
}


@pytest.mark.parametrize(
    ["elt"], [(k,) for k in SANE_RANGE.keys()], ids=lambda elt: OPENROVER_DATA_ELEMENTS[elt].name
)
async def test_sane_value(rover, elt):
    v = await rover.get_data(40)
    if not OPENROVER_DATA_ELEMENTS[elt].supported(v):
        pytest.xfail(f"Data element {elt} not implemented in firmware {v}")
    lo, hi = SANE_RANGE[elt]
    value = await rover.get_data(elt)
    assert lo <= value <= hi


@pytest.mark.parametrize("battery", ["A", "B"])
async def test_power_currents_charging(rover, battery):
    is_charging = await rover.get_data(38)
    assert is_charging in [True, False]

    v = await rover.get_data(40)

    if OPENROVER_DATA_ELEMENTS[68].supported(v) and OPENROVER_DATA_ELEMENTS[70].supported(v):
        battery_current_i2c = await rover.get_data({"A": 68, "B": 70}[battery])
        if is_charging:
            # charging battery has positive current
            assert battery_current_i2c >= 0
        else:
            # discharging battery should have negative current
            assert battery_current_i2c <= 0


@pytest.mark.xfail(reason="suspected hardware problems with analog measurements")
@pytest.mark.parametrize(
    ("elt_analog", "elt_i2c"), (pytest.param(24, 64, id="A"), pytest.param(26, 66, id="B")),
)
async def test_power_analog_i2c_voltages_agree(rover, elt_analog, elt_i2c):
    value_analog = await rover.get_data(elt_analog)
    value_i2c = await rover.get_data(elt_i2c)
    assert value_analog == pytest.approx(value_i2c, abs=0.05)


@pytest.mark.xfail(reason="suspected hardware problems with analog measurements")
@pytest.mark.parametrize(
    ("elt_analog", "elt_i2c"), (pytest.param(42, 68, id="A"), pytest.param(44, 70, id="B")),
)
async def test_power_analog_i2c_currents_agree(rover, elt_analog, elt_i2c):
    value_analog = await rover.get_data(elt_analog)
    value_i2c = await rover.get_data(elt_i2c)
    assert value_analog == pytest.approx(abs(value_i2c), abs=0.02)


async def test_fan_temperatures_equal(rover):
    fan_temp = await rover.get_data(20)
    fan_temp2 = await rover.get_data(22)
    assert fan_temp == pytest.approx(fan_temp2, abs=5)


motor_direction_param = [
    pytest.param(+1, id="forward", marks=pytest.mark.motor),
    pytest.param(-1, id="reverse", marks=pytest.mark.motor),
    pytest.param(0, id="still"),
]


@pytest.mark.parametrize("right", motor_direction_param)
@pytest.mark.parametrize("left", motor_direction_param)
async def test_motor_status(rover, left, right):
    v = await rover.get_data(40)
    if not all(OPENROVER_DATA_ELEMENTS[i].supported(v) for i in (72, 74)):
        pytest.xfail("Motor status flags not implemented in this version")
    rover.set_motor_speeds(left * 0.2, right * 0.2, 0)
    for i in range(3):
        rover.send_speed()
        await trio.sleep(0.1)

    l_status, r_status = (await rover.get_data(72), await rover.get_data(74))

    assert (left == 0) == (MotorStatusFlag.BRAKE in l_status)
    assert (right == 0) == (MotorStatusFlag.BRAKE in r_status)

    if left < 0:
        assert MotorStatusFlag.REVERSE in l_status
    if left > 0:
        assert MotorStatusFlag.REVERSE not in l_status

    if right > 0:
        assert MotorStatusFlag.REVERSE in r_status
    if right < 0:
        assert MotorStatusFlag.REVERSE not in r_status
