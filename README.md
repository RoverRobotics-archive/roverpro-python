# OpenRover Python3 Driver

This is the official Python driver for the [Rover Robotics](https://roverrobotics.com/) "Open Rover Basic" robot. Use this as a starting point to get up and running quickly.

## Setup

Make sure you have Python 3.6 or later installed

Update your build tools before installing if you have not done so in a while:
```
pip install --upgrade pip setuptools wheel
```

To install official releases from PyPi:
```
pip install openrover
```

To install releases from git:
```
pip install git+https://github.com/RoverRobotics/openrover_python_driver
```

To run all tests, first attach the rover via breakout cable then run:
```
py setup test
```

![OpenRover Basic](https://docs.roverrobotics.com/1-manuals/0-cover-photos/1-open-rover-basic-getting-started-vga.jpg)