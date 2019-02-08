from pathlib import Path
import shutil
from subprocess import list2cmdline

import pytest
import trio

from openrover_protocol import OpenRoverProtocol
from serial_trio import open_first_possible_rover_device

device = pytest.fixture(open_first_possible_rover_device)

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
        pytest.fail('Rover did not respond. does it have firmware?')

    try:
        await o.write(0, 0, 0, 230, 1)  # reboot the device

        await o.write(0, 0, 0, 10, 40)
        with pytest.raises(trio.TooSlowError):
            with trio.fail_after(2):
                await o.iter_packets().__anext__()

    finally:
        # need to wait for device to come back up
        await trio.sleep(10)


async def test_bootloader(powerboard_firmware_file, booty_exe):
    # note this test can take a loooong time

    with trio.fail_after(1):
        async with open_first_possible_rover_device() as device:
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

    print('running bootloader: '+ list2cmdline(args))

    with trio.fail_after(60 * 15):

        async with trio.subprocess.Process(args, stdout=trio.subprocess.PIPE, stderr=trio.subprocess.PIPE) as booty:
            async with trio.open_nursery() as nursery:
                async def check_stdout():
                    line_generator = stream_to_lines(booty.stdout)
                    lines = []
                    try:
                        while True:
                            with trio.fail_after(15):
                                a_line = await line_generator.__anext__()
                            print('got line: '+a_line)
                            lines.append(a_line)
                    except trio.TooSlowError:
                        pytest.fail(f'booty became unresponsive after output {lines}')
                    except StopAsyncIteration:
                        pass
                    await trio.sleep(1)
                    assert any(['device verified' in a_line for a_line in lines])


                async def check_stderr():
                    error_output = await stream_to_string(booty.stderr)
                    if 'device not responding' in error_output:
                        pytest.fail('Rover did not respond to booty. Does it have a bootloader?')
                    assert error_output.strip() == ''

                async def check_retcode():
                    assert await booty.wait() == 0

                nursery.start_soon(check_stderr)
                nursery.start_soon(check_stdout)
                nursery.start_soon(check_retcode)

    async with open_first_possible_rover_device() as device:
        await trio.sleep(15)
        o = OpenRoverProtocol(device)
        await o.write(0, 0, 0, 10, 40)
        with pytest.raises(trio.TooSlowError):
            with trio.fail_after(2):
                k, version = await o.iter_packets().__anext__()
        assert k == 40
        assert (version.major, version.minor, version.patch) == (1, 5, 0)


async def stream_to_string(stream: trio.abc.ReceiveStream):
    buf = ''
    async with stream:
        while True:
            new_bytes = await stream.receive_some(1)
            if not new_bytes:
                break
            buf += new_bytes.decode()
    return buf


async def stream_to_lines(stream: trio.abc.ReceiveStream):
    buf = ''
    async with stream:
        while True:
            new_bytes = await stream.receive_some(1)
            if not new_bytes:
                break
            buf += new_bytes.decode()
            *some_lines, buf = buf.splitlines()
            for line in some_lines:
                yield line
        if buf != '':
            yield buf
