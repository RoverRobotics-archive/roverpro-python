import asyncio
from asyncio import ensure_future

import pytest

from openrover import find_openrover
from openrover_data import OpenRoverFirmwareVersion
from protocol import OpenRoverConnectionContext
from unasync_decorator import unasync

port = asyncio.get_event_loop().run_until_complete(find_openrover())
n = 2000


@unasync
async def test_packetizer_read_write_immediate():
    n_received = 0

    async with OpenRoverConnectionContext(port) as protocol:
        for i in range(n):
            protocol.write(0, 0, 0, 10, 40)
            try:
                key, version = await asyncio.wait_for(protocol._read(), timeout=1)
                assert key == 40
                assert isinstance(version, OpenRoverFirmwareVersion)
                assert isinstance(version.value, int)
                assert 0 < version.value
                n_received += 1
            except asyncio.TimeoutError:
                pass
    print(f'success ratio {n_received / n}')
    assert 0.9 < n_received / n <= 1


@unasync
async def test_simultaneous_get():
    # check that if we try to get multiple values at the same time, it throws an exception
    async with OpenRoverConnectionContext(port) as packetizer:
        packetizer.write(0, 0, 0, 10, 40)
        # packetizer.write(0, 0, 0, 10, 40)
        t1 = ensure_future(packetizer.read_one(0.2))
        t2 = ensure_future(packetizer.read_one(0.2))
        k, v = await t1
        assert k == 40
        assert isinstance(v, OpenRoverFirmwareVersion)
        with pytest.raises(RuntimeError):
            await t2


@unasync
async def test_timeout():
    async with OpenRoverConnectionContext(port) as packetizer:
        t1 = ensure_future(packetizer.read_one(0.2))
        with pytest.raises(asyncio.TimeoutError):
            await t1


@unasync
async def test_packetizer_writes_then_reads():
    n_received = 0

    async with OpenRoverConnectionContext(port) as packetizer:
        for i in range(n):
            packetizer.write(0, 0, 0, 10, 40)
            await packetizer._writer.drain()
        for i in range(n):
            try:
                key, version = await asyncio.wait_for(packetizer._read(), timeout=0.5)
                assert key == 40
                assert isinstance(version, OpenRoverFirmwareVersion)
                assert isinstance(version.value, int)
                assert 0 < version.value
                n_received += 1
            except asyncio.TimeoutError:
                break
    print(f'success ratio {n_received / n}')
    assert 0.9 < n_received / n <= 1
