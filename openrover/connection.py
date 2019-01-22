import asyncio
from asyncio import Transport, Protocol
import logging
from typing import Any, AsyncContextManager, Dict, Optional, Tuple, Callable, Union

from dataclasses import dataclass
import serial
from serial import SerialException
from serial_asyncio import SerialTransport, open_serial_connection

from openrover.util import OpenRoverException
from openrover_protocol import OpenRoverProtocol

DEFAULT_SERIAL_KWARGS = dict(baudrate=57600, timeout=0.5, write_timeout=0.5, stopbits=1)


@dataclass
class StreamPair():
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter


class OpenRoverConnection(AsyncContextManager):
    """
    Convenience class for opening and closing an openrover.
    Use as:
    async with OpenRoverConnection('COM3') as (reader,writer):
        ...
    """
    _port: str
    _serial_kwargs: Dict[str, Any]
    _open_timeout: Optional[float]

    def __init__(self, port, open_timeout: Optional[float] = 1, **kwargs):
        self._port = str(port)
        self._serial_kwargs = dict(**kwargs)
        self._open_timeout = open_timeout

    async def aopen(self):
        serial_kwargs = DEFAULT_SERIAL_KWARGS.copy()
        serial_kwargs.update(self._serial_kwargs)
        try:
            rw = await open_serial_connection(url=self._port, **serial_kwargs)
            reader,writer = rw

        except SerialException as e:
            if 'FileNotFoundError' in e.args[0]:
                raise OpenRoverException("Could not connect to OpenRover device - file not found. Is it connected?", self._port) from e
            if 'PermissionError' in e.args[0]:
                raise OpenRoverException("Could not connect to OpenRover device - permission error. Is it open in another process? Does this user have OS permission?", self._port) from e
            raise
        except Exception as e:
            raise OpenRoverException("Could not open device", self._port) from e

        self._rw = (reader, writer)
        return self._rw

    async def aclose(self):
        r, w = self._rw
        await w.drain()
        w.close()
        await w.transport.wait_closed()

    async def __aenter__(self):
        return await self.aopen()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        t = self._rw[1].transport.serial
        await self.aclose()
