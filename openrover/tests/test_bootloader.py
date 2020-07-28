import shutil
import subprocess
from pathlib import Path
from subprocess import list2cmdline

import pytest
import trio

import openrover
from openrover.find_device import open_rover_device
from openrover.openrover_data import OpenRoverFirmwareVersion
from openrover.openrover_protocol import CommandVerb, OpenRoverProtocol
from openrover.util import RoverDeviceNotFound


@pytest.fixture
async def device():
    try:
        async with open_rover_device() as dev:
            yield dev
    except RoverDeviceNotFound:
        pytest.skip("No openrover device found")


@pytest.fixture
def powerboard_firmware_file():
    p = Path(openrover.__path__[0], "tests/resources/PowerBoard-1.5.0.hex")
    assert p.is_file()
    return p


@pytest.fixture
def booty_exe():
    maybe_booty = shutil.which("booty")
    if maybe_booty is None:
        pytest.skip(
            "Could not test bootloader. Booty executable does not exist or is not in the"
            " executable path."
        )
    p = Path(maybe_booty)
    assert p.is_file()
    return p


async def test_reboot(device):
    orp = OpenRoverProtocol(device)
    try:
        orp.write_nowait(0, 0, 0, CommandVerb.RESTART, 0)

        # check that the device did turn off
        orp.write_nowait(0, 0, 0, CommandVerb.GET_DATA, 40)
        with pytest.raises(trio.TooSlowError):
            with trio.fail_after(1):
                await orp.read_one()

        # check that the device comes back up and starts responding to request for version
        with trio.fail_after(30):
            while True:
                orp.write_nowait(0, 0, 0, CommandVerb.GET_DATA, 40)
                with trio.move_on_after(1):
                    k, v = await orp.read_one()
                    if k == 40:
                        return
    except BaseException:
        await trio.sleep(30)
        raise


@pytest.mark.bootload
async def test_bootloader(powerboard_firmware_file, booty_exe):
    async with open_rover_device() as device:
        orp = OpenRoverProtocol(device)
        orp.write_nowait(0, 0, 0, CommandVerb.RESTART, 0)
        port = device.port
        # flash rover firmware
        args = [
            str(booty_exe),
            "--port",
            str(port),
            "--baudrate",
            "57600",
            "--hexfile",
            str(powerboard_firmware_file.absolute()),
            "--erase",
            "--load",
            "--verify",
        ]

    print("running bootloader: " + list2cmdline(args))

    with trio.fail_after(60 * 15):
        async with await trio.open_process(
            args, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ) as booty:
            async with trio.open_nursery() as nursery:

                async def check_stdout():
                    line_generator = stream_to_lines(booty.stdout)
                    lines = []
                    try:
                        while True:
                            with trio.fail_after(30):
                                a_line = await line_generator.__anext__()
                            lines.append(a_line)
                    except trio.TooSlowError:
                        pytest.fail(f"booty became unresponsive after output {lines}")
                    except StopAsyncIteration:
                        pass
                    await trio.sleep(1)
                    assert any(["device verified" in a_line for a_line in lines])

                async def check_stderr():
                    error_output = await stream_to_string(booty.stderr)
                    if "device not responding" in error_output:
                        pytest.fail("Rover did not respond to booty. Does it have a bootloader?")
                    assert error_output.strip() == ""

                async def check_retcode():
                    assert await booty.wait() == 0, "Booty exited with nonzero return code"

                nursery.start_soon(check_stderr)
                nursery.start_soon(check_stdout)
                nursery.start_soon(check_retcode)

    with trio.fail_after(30):
        while True:
            with trio.move_on_after(1):
                orp.write_nowait(0, 0, 0, CommandVerb.GET_DATA, 40)
                k, version = await orp.read_one()
                assert k == 40
                assert isinstance(version, OpenRoverFirmwareVersion)
                assert (version.major, version.minor, version.patch) == (1, 5, 0)


async def stream_to_string(stream: trio.abc.ReceiveStream):
    buf = ""
    async with stream:
        while True:
            new_bytes = await stream.receive_some(1)
            if not new_bytes:
                break
            buf += new_bytes.decode()
    return buf


async def stream_to_lines(stream: trio.abc.ReceiveStream):
    buf = ""
    async with stream:
        while True:
            new_bytes = await stream.receive_some(1)
            if not new_bytes:
                break
            buf += new_bytes.decode()
            *some_lines, buf = buf.splitlines()
            for line in some_lines:
                yield line
        if buf != "":
            yield buf
