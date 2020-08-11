# Rover Pro Python Suite

This is the official Python driver for the [Rover Robotics](https://roverrobotics.com/) "Rover Pro" robot. Use this as a starting point to get up and running quickly.

Included in this package are:

1. A Python library for programmatically interfacing with the Rover over USB
2. A command line application "`pitstop`" for upgrading and configuring the Rover firmware
3. A test suite that confirms the Firmware and hardware are operating as expected.

![Rover Pro Basic](https://docs.roverrobotics.com/1-manuals/0-cover-photos/1-open-rover-basic-getting-started-vga.jpg)

## Setup

To install official releases from PyPi:

```shell script
python3 -m pip install -U pip setuptools
python3 -m pip install -U roverpro --no-cache-dir
```

On Linux, you may not have permission to access USB devices. If this is the case, run the following then restart your computer:

```shell script
sudo usermod -a -G dialout $(whoami)
```

### pitstop

Pitstop is a helper program to bootload your rover and set options. After installing the roverpro package, you can invoke it with `pitstop` or `python3 -m roverpro.pitstop`.

```text
> pitstop --help
  usage: pitstop [-h] [-p port] action ...
  
  Rover Pro companion utility to upgrade firmware, configure settings, and test hardware health.
  
  positional arguments:
    action
      flash               write the given firmware hex file onto the rover
      checkversion        Check the version of firmware installed
      test                Run tests on the rover
      config              Update rover persistent settings
  
  optional arguments:
    -h, --help            show this help message and exit
    -p port, --port port  Which device to use. If omitted, we will search for a possible rover device
```

## tests

To run tests, first attach the rover via breakout cable then run `pitstop test`.
By default, tests that involve running the motors will be skipped, since you may not want a rover ripping cables out of your computer. If you have made sure running the motors will not damage anything, these tests can be opted in with the flag `--motorok`.

```text
> pitstop test --motorok
Scanning for possible rover devices
Using device /dev/ttyUSB0
========================== test session starts ============================
platform linux -- Python 3.8.2, pytest-5.4.3, py-1.9.0, pluggy-0.13.1
rootdir: /home/dan/Documents/roverpro-python/roverpro
plugins: trio-0.6.0
collected 73 items                                                                                                                                                                                           

tests/test_bootloader.py .s                                                                                                                                                                            [  2%]
tests/test_find_device.py .....                                                                                                                                                                        [  9%]
tests/test_roverpro_protocol.py ....                                                                                                                                                                  [ 15%]
tests/test_rover.py ..................x.x.........x................Xxxx..........                                                                                                                      [ 98%]
tests/burnin/test_burnin.py s                                                                                                                                                                          [100%]

===== 64 passed, 2 skipped, 6 xfailed, 1 xpassed in 83.94s (0:01:23) =====
```


### Development setup

Manual Prerequisites:

* Python3 (recommended to install Python3.6, Python3.7, and Python3.8 if you plan on using tox for all):
  * On Ubuntu: `sudo apt install python3 python3-venv python3-pip`
  * On another OS: https://www.python.org/downloads/
* [Poetry](https://python-poetry.org/docs/#installation):
  * `curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | (python3 || python)`

Then to get and initialize the project:

```
git clone https://github.com/RoverRobotics/roverpro-python.git
cd roverpro-python
poetry install
poetry run githooks setup
```

To run a single command: `poetry run pitstop --help`

#### Useful commands

Note that you haven't called `poetry shell`, you must prepend the following with `poetry run`

<dl>
    <dt><code>pytest</code></dt>
    <dd>Test on current Python interpreter</dd>
    <dt><code>tox</code></dt>
    <dd>Test across multiple versions of Python</dd>
    <dt><code>black .</code></dt>
    <dd>Reformat code to a uniform style</dd>
    <td><code>poetry update</code></td>
    <dd>Update all dependencies to the latest released version</dd>
</dl>

### Caveats

* When running in PyCharm in debug mode, you will get a warning like "RuntimeWarning: You seem to already have a custom sys.excepthook handler installed ..." https://github.com/python-trio/trio/issues/1553
* Note this is a pyproject (PEP-517) project so it will NOT work to `pip install --editable ...` for development. Instead use `poetry install` as above.

