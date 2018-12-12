# OpenRover Python3 Driver

This is the official Python driver for the [Rover Robotics](https://roverrobotics.com/) "Open Rover Basic" robot. Use this as a starting point to get up and running quickly.

## Setup

Assuming you [already have *Pipenv*](https://pipenv.readthedocs.io/en/latest/install/#installing-pipenv), and a compatible version of Python (3.7 or 3.6), set up a new virtual environment:

```
mkdir myproject
cd myproject
pipenv --python 3.7
```

To activate that virtual environment, `pipenv shell` in that directory.

To install official releases from PyPi:
```
pip3 install openrover
```

To install specific releases from git for development, use the git url:
```
pip3 install -e git+https://github.com/RoverRobotics/openrover_python_driver/tree/<some branch>#egg=openrover
```

To run all tests, first attach the rover via breakout cable then run either `openrover-test` or `python3 -m openrover.test`.

![OpenRover Basic](https://docs.roverrobotics.com/1-manuals/0-cover-photos/1-open-rover-basic-getting-started-vga.jpg)