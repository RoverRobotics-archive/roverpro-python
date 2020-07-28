import pytest

from openrover.find_device import *


def test_ftdi_device_paths():
    d = get_ftdi_device_paths()
    for name in d:
        assert isinstance(name, str)
        assert name != ""


async def test_open_any_openrover_device():
    if len(get_ftdi_device_paths()) == 0:
        pytest.skip("no FTDI devices found")

    async with open_rover_device() as device:
        assert isinstance(device, SerialTrio)
        # the device must still be open here
        assert await get_openrover_protocol_version(device) is not None

    # the device must be closed afterwards
    with pytest.raises(OpenRoverException):
        await get_openrover_protocol_version(device)


async def test_open_rover_device_sequentially_okay():
    if len(get_ftdi_device_paths()) == 0:
        pytest.skip("no FTDI devices found")

    for i in range(3):
        async with open_rover_device():
            pass


async def test_open_rover_device_nested_fails():
    if len(get_ftdi_device_paths()) == 0:
        pytest.skip("no FTDI devices found")

    async with open_rover_device() as d:
        with pytest.raises(OpenRoverException):
            async with SerialTrio(d.port):
                pass


async def test_missing_device():
    with pytest.raises(OpenRoverException):
        async with SerialTrio("/dev/nosuchdevice") as d2:
            pass
