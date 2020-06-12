import statistics

import pytest
import trio

from openrover.find_device import open_rover_device
from openrover.openrover_data import OpenRoverFirmwareVersion
from openrover.openrover_protocol import CommandVerb, OpenRoverProtocol
from openrover.util import RoverDeviceNotFound

n = 100


@pytest.fixture
async def protocol():
    try:
        async with open_rover_device() as r:
            yield OpenRoverProtocol(r)
    except RoverDeviceNotFound:
        pytest.skip("This test requires a rover device but none was found")


async def test_rtt(protocol):
    times = []
    for _ in range(n):
        protocol.write_nowait(0, 0, 0, CommandVerb.GET_DATA, 40)
        await protocol.flush()
        t0 = trio.current_time()
        await protocol.read_one()
        t1 = trio.current_time()
        times.append(t1 - t0)
    assert 0.010 < statistics.mean(times) < 0.030
    assert 0 < statistics.stdev(times) < 0.030


async def test_protocol_write_read_immediate(protocol):
    n_received = 0

    for i in range(n):
        protocol.write_nowait(0, 0, 0, CommandVerb.GET_DATA, 40)
        with trio.fail_after(1):
            key, version = await protocol.read_one()
            assert key == 40
            assert isinstance(version, OpenRoverFirmwareVersion)
            assert isinstance(version.value, int)
            assert 0 < version.value
            n_received += 1

    print(f"success ratio {(n_received / n)}")
    assert 0.9 < n_received / n <= 1


async def test_protocol_writes_then_reads(protocol):
    n_received = 0
    for _ in range(n):
        protocol.write_nowait(0, 0, 0, CommandVerb.GET_DATA, 40)
    try:
        for i in range(n):
            with trio.fail_after(5):
                key, version = await protocol.read_one()
                assert key == 40
                assert isinstance(version, OpenRoverFirmwareVersion)
                assert isinstance(version.value, int)
                assert 0 < version.value
                n_received += 1
    except trio.TooSlowError:
        pass

    print(f"success ratio {(n_received / n)}")
    assert 0.9 < n_received / n <= 1


async def test_responses_sequential(protocol):
    keys = [14, 16, 28, 30]

    for k in keys:
        protocol.write_nowait(0, 0, 0, CommandVerb.GET_DATA, k)

    result_keys = []
    for i in range(4):
        with trio.fail_after(1):
            k, _ = await protocol.read_one()
        result_keys.append(k)
    assert keys == result_keys
