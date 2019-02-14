import trio

from openrover.find_device import open_any_openrover_device
from openrover.openrover_data import OpenRoverFirmwareVersion
from openrover.openrover_protocol import CommandVerbs, OpenRoverProtocol

n = 100


async def test_protocol_write_read_immediate():
    n_received = 0
    async with open_any_openrover_device() as device:
        protocol = OpenRoverProtocol(device)
        for i in range(n):
            with trio.fail_after(1):
                await protocol.write(0, 0, 0, CommandVerbs.GET_DATA, 40)
                key, version = await protocol.read_one()
                assert key == 40
                assert isinstance(version, OpenRoverFirmwareVersion)
                assert isinstance(version.value, int)
                assert 0 < version.value
                n_received += 1

    print(f'success ratio {n_received / n}')
    assert 0.9 < n_received / n <= 1


async def test_protocol_writes_then_reads():
    n_received = 0

    async with open_any_openrover_device() as device:
        protocol = OpenRoverProtocol(device)

        async with trio.open_nursery() as nursery:
            for i in range(n):
                nursery.start_soon(protocol.write, 0, 0, 0, CommandVerbs.GET_DATA, 40)
                try:
                    for i in range(n):
                        with trio.fail_after(1):
                            key, version = await protocol.read_one()
                            assert key == 40
                            assert isinstance(version, OpenRoverFirmwareVersion)
                            assert isinstance(version.value, int)
                            assert 0 < version.value
                            n_received += 1
                except trio.TooSlowError:
                    pass

        print(f'success ratio {n_received / n}')
        assert 0.9 < n_received / n <= 1
