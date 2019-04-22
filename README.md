# OpenRover Python3 Driver

This is the official Python driver for the [Rover Robotics](https://roverrobotics.com/) "Open Rover Basic" robot. Use this as a starting point to get up and running quickly.

## Setup
To install official releases from PyPi:

```
python -m pip install -U pip setuptools
python -m pip install -U openrover --no-cache-dir
```

### Utilities
### pitstop
Pitstop is a new utility to bootload your rover and set options. After installing, you can invoke it with `pitstop` or `python3 -m openrover.pitstop`.

```
> pitstop --help
usage: pitstop [-h] [-p port] [-f path/to/firmware.hex] [-m version]
               [-u k:v [k:v ...]]

OpenRover companion utility to bootload robot and configure settings.

optional arguments:
  -h, --help            show this help message and exit
  -p port, --port port  Which device to use. If omitted, we will search for a possible rover device
  -f path/to/firmware.hex, --flash path/to/firmware.hex
                        Load the specified firmware file onto the rover
  -m version, --minimumversion version
                        Check that the rover reports at least the given version
                        version may be in the form N.N.N, N.N, or N
  -u k:v [k:v ...], --updatesettings k:v [k:v ...]
                        Send additional commands to the rover. v may be 0-255; k may be:
                                3=SET_POWER_POLLING_INTERVAL_MS
                                4=SET_OVERCURRENT_THRESHOLD_100MA
                                5=SET_OVERCURRENT_TRIGGER_DURATION_5MS
                                6=SET_OVERCURRENT_RECOVERY_THRESHOLD_100MA
                                7=SET_OVERCURRENT_RECOVERY_DURATION_5MS
                                8=SET_PWM_FREQUENCY_KHZ
                                9=SET_BRAKE_ON_ZERO_SPEED_COMMAND
                                11=SET_BRAKE_ON_DRIVE_TIMEOUT
                                12=SET_MOTOR_SLOW_DECAY_MODE
                                13=SET_TIME_TO_FULL_SPEED
```

### tests

To run tests, first attach the rover via breakout cable then run either `openrover-test` or `python3 -m openrover.test`.
By default, tests that involve running the motors will be skipped, since you may not want a rover ripping cables out of your computer. If you have made sure running the motors will not damage anything, these tests can be opted in with the flag `--motorok`.

```
> openrover-test
==================== test session starts =====================
platform win32 -- Python 3.7.3, pytest-4.3.1, py-1.8.0, pluggy-0.9.0
rootdir: ..., inifile:
plugins: trio-0.5.2
collected 32 items

..\openrover\tests\test_bootloader.py .s                [  6%]
..\openrover\tests\test_data.py ..                      [ 12%]
..\openrover\tests\test_find_device.py ....             [ 25%]
..\openrover\tests\test_openrover_protocol.py ....      [ 37%]
..\openrover\tests\test_rover.py .......sssss......ss   [100%]

=========== 24 passed, 8 skipped in 89.14 seconds ============
```

![OpenRover Basic](https://docs.roverrobotics.com/1-manuals/0-cover-photos/1-open-rover-basic-getting-started-vga.jpg)
