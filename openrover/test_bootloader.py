from pathlib import Path
import shutil

import pytest
import trio

from openrover_protocol import OpenRoverProtocol
from serial_trio import open_rover


@pytest.fixture
async def device():
    async with open_rover() as e:
        yield e


@pytest.fixture
def powerboard_firmware_file():
    p = Path('test-resources/PowerBoard-1.5.0.hex')
    assert p.is_file()
    return p


@pytest.fixture
def booty_exe():
    p = Path(shutil.which('booty'))
    assert p.is_file()
    return p


async def test_reboot(device):
    o = OpenRoverProtocol(device)
    assert isinstance(o, OpenRoverProtocol)
    # set a long timeout in case rover is already in bootloader

    try:
        with trio.fail_after(2):
            await o.write(0, 0, 0, 10, 40)
            i, version = await o.iter_packets().__anext__()
            assert i == 40
    except trio.TooSlowError:
        assert False, 'Rover did not respond. does it have firmware?'

    try:
        await o.write(0, 0, 0, 230, 1) # reboot the device

        await o.write(0, 0, 0, 10, 40)
        with pytest.raises(trio.TooSlowError):
            with trio.fail_after(2):
                await o.iter_packets().__anext__()

    finally:
        # need to wait for device to come back up
        await trio.sleep(10)


async def test_bootloader(powerboard_firmware_file, booty_exe):
    # note this test can take a loooong time

    async with open_rover() as device:
        o = OpenRoverProtocol(device)
        await o.write(0, 0, 0, 230, 0)
        port = device.port

    # flash rover firmware
    args = [
        str(booty_exe),
        '--port', str(port),
        '--baudrate', '57600',
        '--hexfile', str(powerboard_firmware_file.absolute()),
        '--erase',
        '--load',
        '--verify'
    ]

    async with trio.subprocess.Process(args, stdout=trio.subprocess.PIPE, stderr=trio.subprocess.PIPE) as p:
        assert await p.wait() == 0
        output = (await p.stdout.receive_some(10000)).decode()
        errout = (await p.stderr.receive_some(10000)).decode()
        assert 'device not responding' not in errout,'Rover did not respond to booty. Does it have a bootloader?'
        assert 'device verified' in output

    async with open_rover() as device:
        o = OpenRoverProtocol(device)
        version = await o.get_data(40)
        assert (version.major, version.minor, version.patch) == (1, 5, 0)
