import asyncio

from connection import OpenRoverConnection
from openrover import find_openrover
from openrover_data import OpenRoverFirmwareVersion
from openrover_protocol import OpenRoverProtocol
from unasync_decorator import unasync

loop = asyncio.get_event_loop()
port = loop.run_until_complete(find_openrover())
n = 400


@unasync
async def test_protocol_read_write_immediate():
    n_received = 0

    async with OpenRoverConnection(port) as (reader, writer):
        protocol = OpenRoverProtocol(reader, writer)
        messages = protocol.iter_messages()
        for i in range(n):
            await asyncio.wait_for(protocol.write(0, 0, 0, 10, 40), timeout=1)
            try:
                key, version = await asyncio.wait_for(messages.__anext__(), timeout=1)
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
async def test_protocol_writes_then_reads():
    n_received = 0

    async with OpenRoverConnection(port) as (reader, writer):
        protocol = OpenRoverProtocol(reader, writer)
        await asyncio.wait([protocol.write(0, 0, 0, 10, 40) for _ in range(n)], return_when=asyncio.ALL_COMPLETED)

        messages = protocol.iter_messages()

        for i in range(n):
            try:
                key, version = await asyncio.wait_for(messages.__anext__(), timeout=1)
                assert key == 40
                assert isinstance(version, OpenRoverFirmwareVersion)
                assert isinstance(version.value, int)
                assert 0 < version.value
                n_received += 1
            except asyncio.TimeoutError:
                break
    print(f'success ratio {n_received / n}')
    assert 0.9 < n_received / n <= 1
