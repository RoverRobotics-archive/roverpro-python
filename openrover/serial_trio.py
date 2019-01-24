from functools import partial
import logging
from typing import Callable, List

import serial, serial.tools, serial.tools.list_ports
import trio
import warnings


class OpenRoverWarning(RuntimeWarning):
    pass


class SerialTrio(trio.abc.AsyncResource):
    _serial: serial.Serial
    _inbound_high_water: int = 4000
    _outbound_high_water: int = 8000

    def __init__(self, port, **serial_kwargs):
        self.port = port
        self.serial_kwargs = dict(write_timeout=0, inter_byte_timeout=None, timeout=0, **serial_kwargs)
        try:
            self._serial = serial.Serial(self.port, **self.serial_kwargs)
        except serial.SerialException as e:
            if 'FileNotFoundError' in e.args[0]:
                raise RuntimeError("Could not connect to serial device - file not found. Is it connected?", self.port) from e
            if 'PermissionError' in e.args[0]:
                raise RuntimeError("Could not connect to serial device - permission error. Is it open in another process? Does this user have OS permission?", self.port) from e

    def _read_bytes_nowait(self, max):
        if self._inbound_high_water <= self._serial.in_waiting:
            warnings.warn(f'Incoming buffer is backlogged. Data may be lost. {self._serial.in_waiting} bytes')
        return self._serial.read(max)

    async def read_until(self, terminator):
        terminator = bytes(terminator)
        assert terminator != b''
        line = bytearray()
        try:
            while not line.endswith(terminator):
                line.extend(self._read_bytes_nowait(1))
                await trio.sleep(0.001)
            return bytes(line)
        except trio.Cancelled:
            logging.exception(f'abandoning data {line}')
            self._serial.cancel_read()
            raise

    async def read_exactly(self, count):
        line = bytearray()
        while len(line) < count:
            line.extend(self._read_bytes_nowait(count - len(line)))
            await trio.sleep(0.001)
        return bytes(line)

    async def write(self, data):
        self._serial.write(data)
        if self._outbound_high_water <= self._serial.out_waiting:
            warnings.warn(f'Outgoing buffer is backlogged. Data may be lost. {self._serial.out_waiting} bytes')
        try:
            await self.flush()
        except trio.Cancelled():
            self._serial.cancel_write()
            raise

    async def flush(self):
        while self._serial.out_waiting:
            await trio.sleep(0.001)

    async def aclose(self):
        try:
            while self._serial.out_waiting:
                await trio.sleep(0.001)
        finally:
            self._serial.close()
            assert not self._serial.is_open


def get_possible_rover_devices() -> List[Callable[[], SerialTrio]]:
    ports = []
    for comport in serial.tools.list_ports.comports():
        if comport.manufacturer != 'FTDI':
            continue
        ports.append(comport.device)
        DEFAULT_SERIAL_KWARGS = dict(baudrate=57600, stopbits=1)
        return [partial(SerialTrio, port, **DEFAULT_SERIAL_KWARGS) for port in ports]


def open_rover():
    return next(iter(get_possible_rover_devices()))()
