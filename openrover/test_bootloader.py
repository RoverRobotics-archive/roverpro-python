import asyncio
from asyncio import futures
from pathlib import Path
import shutil
import subprocess
import warnings

import pytest
from serial.tools import list_ports

from openrover import OpenRover
from protocol import OpenRoverProtocol, OpenRoverConnectionContext
from unasync_decorator import unasync


@pytest.fixture
def port():
    ports = [comport.device for comport in list_ports.comports() if comport.manufacturer == 'FTDI']
    if len(ports) > 1:
        warnings.warn(f'Multiple ports found, {ports} using {ports[0]}')
    return ports[0]


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


@unasync
async def test_reboot_skipping_firmware(port):
    async with OpenRoverConnectionContext(port, 1) as o:
        assert isinstance(o, OpenRoverProtocol)
        # set a long timeout in case rover is already in bootloader
        try:
            o.write(0, 0, 0, 10, 40)
            i, version = await o.read_one(timeout=15)
            assert i == 40
            assert (version.major, version.minor) >= (1, 4), 'Bootloader requires OpenRover firmware version>1.4.0'
        except futures.TimeoutError:
            assert False, 'Rover did not respond. does it have firmware?'
        o.write(0, 0, 0, 230, 1)

    await asyncio.sleep(5)
    # check that rover reboots quickly (skips firmware)
    async with OpenRover(port) as o:
        version = await o.get_data(40, timeout=5)


@unasync
async def test_bootloader(port, powerboard_firmware_file, booty_exe):
    # note this test can take a loooong time
    async with OpenRoverConnectionContext(port, 1) as o:
        assert isinstance(o, OpenRoverProtocol)
        o.write(0, 0, 0, 230, 0)

    # flash rover firmware
    args = [
        str(booty_exe),
        '--port', port,
        '--baudrate', '57600',
        '--hexfile', str(powerboard_firmware_file.absolute()),
        '--erase',
        '--load',
        '--verify'
    ]
    retcode, stdout = subprocess.getstatusoutput(args)
    assert retcode == 0
    assert 'device verified' in stdout

    await asyncio.sleep(30)
    async with OpenRover() as o:
        version = await o.get_data(40)
        assert (version.major, version.minor, version.patch) == (1, 5, 0)
