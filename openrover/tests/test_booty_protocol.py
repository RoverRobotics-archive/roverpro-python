import pytest

from openrover import OpenRoverProtocol, ftdi_device_context
from openrover.booty_protocol import BootyProtocol
from openrover.openrover_protocol import CommandVerbs

device = pytest.fixture(ftdi_device_context)


async def create(device):
    b = BootyProtocol(device)
    assert b is not None


@pytest.mark.skip("not yet done")
async def test_get_metadata(device):
    p = OpenRoverProtocol(device)

    await p.write(0, 0, 0, CommandVerbs.RESTART, 0)
    b = BootyProtocol(device)
