import pytest
from serial import SerialException

from openrover import OpenRover


def test_create():
    o = OpenRover()
    assert o is not None


def test_missing_device():
    o = OpenRover()
    with pytest.raises(SerialException):
        o.open('missingdevice')
