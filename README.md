# OpenRover Python Suite

This is the official Python driver for the [Rover Robotics](https://roverrobotics.com/) "Open Rover Basic" robot. Use this as a starting point to get up and running quickly.

Included in this package are:

1. A Python library for programmatically interfacing with the Rover over USB
2. A command line application "`pitstop`" for upgrading and configuring the Rover firmware
3. A test suite that confirms the Firmware and hardware are operating as expected.

## Setup

To install official releases from PyPi:

```shell script
python3 -m pip install -U pip setuptools
python3 -m pip install -U openrover --no-cache-dir
```

On Linux, you may not have permission to access USB devices. If this is the case, run the following then restart your computer:

```shell script
sudo usermod -a -G dialout $(whoami)
```

### Development setup

Manual Prerequisites:

* Python3 (recommended to install Python3.6, Python3.7, and Python3.8)
* [Poetry](https://python-poetry.org/docs/#installation) 

Instead, we recommend:

```
git clone https://github.com/RoverRobotics/openrover-python.git
cd openrover-python
poetry install
```

#### Useful commands

For testing, it is recommended to use `tox`, which can run tests on multiple Python interpreters.

<dl>
    <dt><code>pytest</code></dt>
    <dd>Test on current Python interpreter</dd>
    <dt><code>tox</code></dt>
    <dd>Test on all supported Python minor versions</dd>
    <dt><code>black .</code></dt>
    <dd>Reformat code to a uniform style</dd>
    <dt><code>githooks setup</code></dt>
    <dd>Install git pre-commit hook to automatically run <code>black</code></dd>
</dl>

### Caveats

* When running in PyCharm in debug mode, you will get a warning like "RuntimeWarning: You seem to already have a custom sys.excepthook handler installed ..." https://github.com/python-trio/trio/issues/1553
* Note this is a pyproject (PEP-517) project so it will NOT work to `pip install --editable ...`


### pitstop

Pitstop is a new utility to bootload your rover and set options. After installing, you can invoke it with `pitstop` or `python3 -m openrover.pitstop`.

```text
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

```text
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
