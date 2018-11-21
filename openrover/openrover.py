from time import sleep
from typing import Callable, Iterable, List

from serial import Serial
import serial.threaded
from serial.tools import list_ports

from .openrover_data import OPENROVER_DATA_ELEMENTS

DEFAULT_SERIAL_KWARGS = dict(baudrate=57600, timeout=0.5, write_timeout=0.5, stopbits=1)


class OpenRoverProtocol(serial.threaded.Protocol):
    SERIAL_START_BYTE = 253
    on_data_read: Callable[[str, int], None] = None
    transport = None  #

    @classmethod
    def checksum(cls, values):
        return 255 - sum(values) % 255

    def __init__(self):
        """Serial communication implementation details for OpenRover"""
        self.buffer = bytearray()
        self.transport = None
        self.on_data_read = None

    def connection_made(self, transport):
        """Store transport"""
        self.transport = transport

    def connection_lost(self, exc):
        pass

    def data_received(self, data):
        """Called with snippets received from the serial port.
        Decodes the data and forwards it on """
        self.buffer.extend(data)

        while True:
            #  ignore any data until we find the start byte
            start_byte_index = self.buffer.find(bytearray([self.SERIAL_START_BYTE]))
            self.buffer[:start_byte_index] = []

            if len(self.buffer) < 5:
                return

            packet = bytearray(self.buffer[:5])
            self.buffer[:5] = []

            if packet[4] == self.checksum(packet[1:4]):
                k = packet[1]
                v = OPENROVER_DATA_ELEMENTS[k].data_format.unpack(packet[2:4])

                on_data_read = self.on_data_read
                if on_data_read is not None:
                    on_data_read(k, v)
            else:
                pass  # packet is bad. ignore it

    @classmethod
    def encode_speed(cls, speed_as_float):
        return int(round(speed_as_float * 125)) + 125

    @classmethod
    def encode_packet(cls, motor_left, motor_right, flipper, arg1, arg2):
        payload = [cls.encode_speed(motor_left),
                   cls.encode_speed(motor_right),
                   cls.encode_speed(flipper),
                   arg1,
                   arg2]
        return bytes([cls.SERIAL_START_BYTE] + payload + [cls.checksum(payload)])

    def write(self, *args):
        return self.transport.write(self.encode_packet(*args))


class OpenRover:
    _motor_left = 0
    _motor_right = 0
    _motor_flipper = 0
    _latest_data = None
    _reader_thread = None
    _protocol = None
    _port = None

    def __init__(self, port=None):
        """An OpenRover object """
        self._motor_left = 0
        self._motor_right = 0
        self._motor_flipper = 0
        self._latest_data = dict()
        self._port = port

    def open(self, **serial_kwargs):
        port = self._port
        if port is None:
            port = find_openrover()

        kwargs = DEFAULT_SERIAL_KWARGS.copy()
        kwargs.update(serial_kwargs)
        serial_device = serial.Serial(port, **kwargs)
        if not get_openrover_version(serial_device):
            raise ValueError(f'Device {port} did not respond to a request for OpenRover version number. Is it an OpenRover? Is it powered on?')
        self._reader_thread = serial.threaded.ReaderThread(serial_device, OpenRoverProtocol)
        self._reader_thread.start()
        self._reader_thread.connect()
        self._protocol = self._reader_thread.protocol
        self._protocol.on_data_read = self.on_new_openrover_data

    def close(self):
        self._reader_thread.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        # don't suppress any errors
        return False

    def on_new_openrover_data(self, key, value):
        self._latest_data[key] = value

    def set_motor_speeds(self, left, right, flipper):
        assert -1 <= left <= 1
        assert -1 <= right <= 1
        assert -1 <= flipper <= 1
        self._motor_left = left
        self._motor_right = right
        self._motor_flipper = flipper

    def send_command(self, arg1, arg2):
        self._protocol.write(self._motor_left, self._motor_right, self._motor_flipper, arg1, arg2)

    def send_speed(self):
        self.send_command(0, 0)

    def set_fan_speed(self, fan_speed):
        self.send_command(20, fan_speed)

    def flipper_calibrate(self):
        self.send_command(250, 250)

    def request_data(self, index):
        self.send_command(10, index)

    def get_data_synchronous(self, index):
        self.request_data(index)
        sleep(0.05)
        return self.get_data(index)

    def get_data(self, index):
        return self._latest_data.get(index)


class OpenRoverException(Exception):
    pass


def get_openrover_version(s: Serial):
    """Checks if the given device is an OpenRover device.
    If it is, returns the build number.
    Otherwise raises an OpenRoverException"""
    _ = s.readall()
    s.write(bytes([253, 125, 125, 125, 10, 40, 85]))
    test_value = bytes([253, 40])
    device_output = s.read_until(test_value)
    if device_output.endswith(test_value):
        version_bytes = s.read(3)
        return (version_bytes[0] << 8) + version_bytes[1]
    else:
        raise OpenRoverException


def iterate_openrovers():
    """
    Returns a list of devices determined to be OpenRover devices.
    Throws a SerialException if candidate devices are busy
    """
    for c in list_ports.comports():
        is_openrover = False
        port = c.device

        if c.manufacturer == 'FTDI':
            s = Serial(port, **DEFAULT_SERIAL_KWARGS)
            try:
                get_openrover_version(s)
                is_openrover = True
            except OpenRoverException:
                pass
            finally:
                s.close()

        if is_openrover:
            yield port


def find_openrover():
    """
    Find the first OpenRover device and return its port
    """
    try:
        return next(iterate_openrovers())
    except StopIteration:
        pass

    raise OpenRoverException
