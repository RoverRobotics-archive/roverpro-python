# suppress warnings and print output correctly on Ubuntu. Must be done
# before importing trio
# https://github.com/python-trio/trio/issues/1065
import sys

if sys.excepthook.__name__ == "apport_excepthook":
    sys.excepthook = sys.__excepthook__

from .openrover_protocol import OpenRoverProtocol
from .rover import open_rover, Rover
from .util import OpenRoverException

name = "openrover"

__all__ = ["OpenRoverException", "OpenRoverProtocol", "open_rover", "Rover"]
