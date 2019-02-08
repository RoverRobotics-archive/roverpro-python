import trio

from openrover_data import OpenRoverFirmwareVersion
from openrover_protocol import OpenRoverProtocol
from serial_trio import open_first_possible_rover_device

n = 800



async def test_protocol_write_read_immediate():
    n_received = 0

    async with open_first_possible_rover_device() as port:
        protocol = OpenRoverProtocol(port)
        messages = protocol.iter_packets()
        for i in range(n):
            with trio.fail_after(1):
                await protocol.write(0, 0, 0, 10, 40)
                key, version = await messages.__anext__()
                assert key == 40
                assert isinstance(version, OpenRoverFirmwareVersion)
                assert isinstance(version.value, int)
                assert 0 < version.value
                n_received += 1

    print(f'success ratio {n_received / n}')
    assert 0.9 < n_received / n <= 1


async def test_protocol_writes_then_reads():
    n_received = 0

    async with open_first_possible_rover_device() as port:
        protocol = OpenRoverProtocol(port)
        messages = protocol.iter_packets()

        async with trio.open_nursery() as nursery:
            for i in range(n):
                nursery.start_soon(protocol.write, 0, 0, 0, 10, 40)
            try:
                for i in range(n):
                    with trio.fail_after(1):
                        key, version = await messages.__anext__()
                        assert key == 40
                        assert isinstance(version, OpenRoverFirmwareVersion)
                        assert isinstance(version.value, int)
                        assert 0 < version.value
                        n_received += 1
            except trio.TooSlowError:
                pass

    print(f'success ratio {n_received / n}')
    assert 0.9 < n_received / n <= 1
