# suppress warnings and print output correctly on Ubuntu. Must be done
# before importing trio
# https://github.com/python-trio/trio/issues/1065
import sys

if sys.excepthook.__name__ == "apport_excepthook":
    sys.excepthook = sys.__excepthook__

from .rover_protocol import RoverProtocol
from .rover import open_rover, Rover
from .util import RoverException

name = "roverpro"

__all__ = ["RoverException", "RoverProtocol", "open_rover", "Rover"]
