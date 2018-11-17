from time import sleep
from typing import Callable
import serial.threaded

from .openrover_data import OPENROVER_DATA_ELEMENTS


class OpenRoverProtocol(serial.threaded.Protocol):
    SERIAL_START_BYTE = 253
    on_data_read: Callable[[str, int], None] = None
    transport = None  #

    @staticmethod
    def checksum(values):
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

    @staticmethod
    def encode_speed(speed_as_float):
        return int(round(speed_as_float * 125) + 125)

    def write(self, motor_left, motor_right, flipper, arg1, arg2):
        payload = [self.encode_speed(motor_left),
                   self.encode_speed(motor_right),
                   self.encode_speed(flipper),
                   arg1,
                   arg2]
        packet = bytearray([self.SERIAL_START_BYTE] + payload + [self.checksum(payload)])
        return self.transport.write(packet)


class OpenRover:
    _motor_left = 0
    _motor_right = 0
    _motor_flipper = 0
    _latest_data = None
    _reader_thread = None
    _protocol = None

    def __init__(self):
        """An OpenRover object """
        self._motor_left = 0
        self._motor_right = 0
        self._motor_flipper = 0
        self._latest_data = dict()

    def open(self, port, **serial_kwargs):
        kwargs = dict(baudrate=57600, timeout=0.5, write_timeout=0.5, stopbits=1)
        kwargs.update(serial_kwargs)
        serial_device = serial.Serial(port, **kwargs)
        self._reader_thread = serial.threaded.ReaderThread(serial_device, OpenRoverProtocol)
        self._reader_thread.start()
        self._reader_thread.connect()
        self._protocol = self._reader_thread.protocol
        self._protocol.on_data_read = self.on_new_openrover_data

    def close(self):
        self._reader_thread.close()

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
        assert 0 <= arg1 <= 255
        assert 0 <= arg2 <= 255

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
