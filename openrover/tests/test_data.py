from openrover.openrover_data import FAN_SPEED_RESPONSE_FORMAT, MOTOR_EFFORT_FORMAT


def test_fan_speed_format():
    assert list(FAN_SPEED_RESPONSE_FORMAT.pack(0)) == [0, 0]
    assert list(FAN_SPEED_RESPONSE_FORMAT.pack(0.5)) == [0, 120]
    assert list(FAN_SPEED_RESPONSE_FORMAT.pack(1)) == [0, 240]


def test_motor_effort():
    assert list(MOTOR_EFFORT_FORMAT.pack(-1)) == [0]
    assert list(MOTOR_EFFORT_FORMAT.pack(0)) == [125]
    assert list(MOTOR_EFFORT_FORMAT.pack(+1)) == [250]
