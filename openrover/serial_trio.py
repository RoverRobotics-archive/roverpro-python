import errno
import logging
import warnings

import serial
import serial.tools
import serial.tools.list_ports
import trio

from .util import OpenRoverException


class OpenRoverWarning(RuntimeWarning):
    pass


class DeviceClosedException(serial.SerialException):
    pass


class SerialTrio(trio.abc.AsyncResource):
    _serial = None  # type: serial.Serial
    _inbound_high_water = 4000
    _outbound_high_water = 8000

    def __init__(self, port, **serial_kwargs):
        """Wrapper for pyserial that makes it work better with async"""
        self.port = port
        self.serial_kwargs = {
            "write_timeout": 0,
            "inter_byte_timeout": None,
            "timeout": 0,
            "exclusive": True,
        }
        self.serial_kwargs.update(serial_kwargs)

        try:
            self._serial = serial.Serial(self.port, **self.serial_kwargs)
        except serial.SerialException as e:
            if e.errno == errno.EAGAIN:
                raise OpenRoverException("Serial device is already open", self.port) from e
            if e.errno == errno.ENOENT:
                raise OpenRoverException(
                    "Could not connect to serial device - file not found. Is it connected?",
                    self.port,
                ) from e
            if e.errno == errno.EACCES:
                raise OpenRoverException(
                    "Access error when trying to connect to serial device. Is it open in another"
                    " process? Does this user have OS permission?",
                    self.port,
                ) from e
            if e.errno == errno.EISDIR or e.errno == errno.ENOTTY:
                raise OpenRoverException("Does not appear to be a serial device") from e
            raise OpenRoverException("Could not connect to serial device.") from e

    @property
    def in_waiting(self):
        try:
            return self._serial.in_waiting
        except Exception as e:
            if not self._serial.is_open:
                raise DeviceClosedException from e
            raise

    def _read_bytes_nowait(self, n_max):
        if self._inbound_high_water <= self.in_waiting:
            warnings.warn(
                "Incoming buffer is backlogged. Data may be lost. {} bytes".format(
                    self._serial.in_waiting
                )
            )
        return self._serial.read(n_max)

    async def read_until(self, terminator):
        terminator = bytes(terminator)
        assert terminator != b""
        line = bytearray()
        try:
            while not line.endswith(terminator):
                line.extend(self._read_bytes_nowait(1))
                await trio.sleep(0.001)
            return bytes(line)
        except trio.Cancelled:
            logging.exception(f"Abandoning data: {line}")
            self._serial.cancel_read()
            raise

    async def read_exactly(self, count):
        line = bytearray()
        while len(line) < count:
            line.extend(self._read_bytes_nowait(count - len(line)))
            await trio.sleep(0.001)
        return bytes(line)

    def write_nowait(self, data):
        self._serial.write(data)
        if self._outbound_high_water <= self._serial.out_waiting:
            warnings.warn(
                "Outgoing buffer is backlogged. Data may be lost. {} bytes".format(
                    self._serial.out_waiting
                )
            )

    async def write(self, data):
        self._serial.write(data)
        if self._outbound_high_water <= self._serial.out_waiting:
            warnings.warn(
                "Outgoing buffer is backlogged. Data may be lost. {} bytes".format(
                    self._serial.out_waiting
                )
            )
        try:
            await self.flush()
        except trio.Cancelled():
            self._serial.cancel_write()
            raise

    async def flush(self, n_bytes=0):
        """wait until the number of queued outgoing bytes is less than or equal to n_bytes"""
        assert n_bytes >= 0
        while self._serial.out_waiting > n_bytes:
            await trio.sleep(0.001)

    async def aclose(self):
        try:
            if self._serial.is_open:
                await self.flush()
        finally:
            self._serial.close()
            assert not self._serial.is_open
