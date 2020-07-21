import argparse
import subprocess
import sys
from pathlib import Path

import trio

from openrover import OpenRoverProtocol
from openrover.find_device import get_ftdi_device_paths
from openrover.openrover_data import OpenRoverFirmwareVersion
from openrover.openrover_protocol import CommandVerb
from openrover.serial_trio import SerialTrio

BAUDRATE = 57600

SETTINGS_VERBS = list(map(CommandVerb, [*range(3, 10), *range(11, 19)]))


def rover_command_arg_pair(arg):
    k, v = arg.split(":", 2)
    k = CommandVerb(int(k))
    if k not in SETTINGS_VERBS:
        raise ValueError
    if not 0 <= int(v) <= 255:
        raise ValueError
    return k, int(v)


async def amain():
    parser = argparse.ArgumentParser(
        description=(
            "OpenRover companion utility to upgrade firmware, configure settings, and test"
            " hardware health."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    pitstop_action = parser.add_subparsers(dest="action", required=True, metavar="action")
    flash = pitstop_action.add_parser(
        "flash", help="write the given firmware hex file onto the rover"
    )
    flash.add_argument(
        "hexfile", type=argparse.FileType("r"), help="*.hex file containing the new firmware",
    )

    checkversion = pitstop_action.add_parser(
        "checkversion", help="Check the version of firmware installed",
    )
    checkversion.add_argument(
        "min_version",
        nargs="?",
        type=OpenRoverFirmwareVersion.parse,
        help=(
            "Minimum acceptable version, in the format X / X.Y / X.Y.Z\nIf specified and the"
            " installed firmware is older than this version, we will exit with a non-zero exit"
            " code"
        ),
    )

    test = pitstop_action.add_parser(
        "test",
        help="Run tests on the rover",
        description=(
            "Run tests on the rover. Some tests are inherently unsafe and are disabled by default,"
            " but may be enabled with below flags"
        ),
    )
    test.add_argument(
        "--bootloadok",
        action="store_true",
        help="Allow tests that may alter the firmware version installed on the rover",
    )
    test.add_argument(
        "--motorok",
        action="store_true",
        help=(
            "Allow short-running tests that spin the rover wheel motors. Note the rover should"
            " have its wheels removed or be otherwise immobilized for the duration of the test so"
            " it does not drive away, rip out cables, etc."
        ),
    )
    test.add_argument(
        "--burninok",
        action="store_true",
        help=(
            "Allow the long-running burn-in test to verify hardware reliability. This will take a"
            " while (about 30 minutes). Note the rover should have its wheels removed or be"
            " otherwise immobilized for the duration of the test so it does not drive away, rip"
            " out cables, etc."
        ),
    )

    config = pitstop_action.add_parser("config", help="Update rover persistent settings")
    config.add_argument(
        "config_items",
        type=rover_command_arg_pair,
        metavar="k:v",
        nargs="*",
        help="Send configuration commands to the rover. v may be 0-255; k may be:\n\t"
        + "\n\t".join("{}={}".format(s.value, s.name) for s in SETTINGS_VERBS),
    )
    config.add_argument(
        "--commit",
        action="store_true",
        help=(
            "Persist these config options across reboot. By default, changes persist only until"
            " rover is restarted."
        ),
    )

    parser.add_argument(
        "-p",
        "--port",
        type=str,
        help="Which device to use. If omitted, we will search for a possible rover device",
        metavar="port",
    )
    args = parser.parse_args()

    port = args.port
    if port is None:
        print("Scanning for possible rover devices")
        ports = get_ftdi_device_paths()
        if len(ports) == 0:
            print("No devices found")
            sys.exit(1)
        if len(ports) > 1:
            print(f"Multiple devices found: {', '.join(ports)}")
        port = ports[0]
    print(f"Using device {port}")

    if args.action == "flash":
        async with SerialTrio(port, baudrate=BAUDRATE) as ser:
            orp = OpenRoverProtocol(ser)
            print("instructing rover to restart")
            for i in range(3):
                orp.write_nowait(0, 0, 0, CommandVerb.RESTART, 0)
            await orp.flush()

        pargs = [
            sys.executable,
            "-m",
            "booty",
            "--port",
            port,
            "--baudrate",
            str(BAUDRATE),
            "--hexfile",
            args.hexfile.name,
            "--erase",
            "--load",
            "--verify",
        ]
        print(f"invoking bootloader: {subprocess.list2cmdline(pargs)}")
        subprocess.check_call(pargs)

        print("starting firmware")
        async with SerialTrio(port, baudrate=BAUDRATE) as ser:
            ser.write_nowait(bytes.fromhex("f701004041437f"))
        print(
            "\n".join(
                [
                    r"      VROOM      ",
                    r"  _           _  ",
                    r" /#\ ------- /#\ ",
                    r" |#|  (o=o)  |#| ",
                    r" \#/ ------- \#/ ",
                    r"                 ",
                ]
            )
        )

    elif args.action == "checkversion":
        actual_version = None
        async with SerialTrio(port, baudrate=BAUDRATE) as device:
            orp = OpenRoverProtocol(device)
            orp.write_nowait(0, 0, 0, CommandVerb.GET_DATA, 40)
            with trio.move_on_after(10):
                k, version = await orp.read_one()
                if k == 40:
                    actual_version = version

        if actual_version is None:
            print("Could not get version of attached rover")
            sys.exit(1)
        else:
            print(f"Firmware version installed = {actual_version}")

        if args.min_version is not None:
            print(f"Firmware version expected >= {args.min_version}")
            if args.min_version <= actual_version:
                print(f"Passed :-)")
            if actual_version < args.min_version:
                print(f"Failed :-(")
                sys.exit(1)

    elif args.action == "config":
        async with SerialTrio(port, baudrate=57600) as device:
            orp = OpenRoverProtocol(device)
            print("Reloading settings from non-volatile memory.")
            orp.write_nowait(0, 0, 0, CommandVerb.RELOAD_SETTINGS, 0)
            for k, v in args.config_items or ():
                print(f"\tSetting {k.value} ({k.name}) = {v}")
                orp.write_nowait(0, 0, 0, k, v)
            if args.commit:
                print(
                    "Committing settings to non-volatile memories. "
                    "These new settings will persist on reboot."
                )
                orp.write_nowait(0, 0, 0, CommandVerb.COMMIT_SETTINGS, 0)
            else:
                print("These new settings will be reset on reboot.")
            await orp.flush()

    elif args.action == "test":
        argflags = []
        for argname in ("bootloadok", "burninok", "motorok"):
            if getattr(args, argname):
                argflags.append(f"--{argname}")

        from . import tests

        wd = Path(tests.__file__).parent.absolute()
        completed = await trio.run_process(
            [sys.executable, "-m", "pytest", *argflags], check=False, cwd=wd
        )
        sys.exit(completed.returncode)


def main():
    trio.run(amain)


if __name__ == "__main__":
    main()
