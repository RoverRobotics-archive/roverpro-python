# from enum import IntEnum
# import logging
# import struct
# from typing import Any, Tuple
#
# import trio
#
# from openrover.serial_trio import SerialTrio
#
# _START_OF_FRAME = 0xf7
# _END_OF_FRAME = 0x7f
# _ESC = 0xf6
# _ESC_XOR = 0x20
#
#
# class BootyProtocolError(RuntimeError):
#     pass
#
#
# class BootyCommand(IntEnum):
#     READ_PLATFORM = 0x00
#     READ_VERSION = 0x01
#     READ_ROW_LEN = 0x02
#     READ_PAGE_LEN = 0x03
#     READ_PROG_LEN = 0x04
#     READ_MAX_PROG_SIZE = 0x05
#     READ_APP_START_ADDRESS = 0x06
#     READ_BOOT_START_ADDRESS = 0x07
#     READ_ADDR = 0x20
#     READ_MAX = 0x21
#     ERASE_PAGE = 0x10
#     WRITE_ROW = 0x30
#     WRITE_MAX = 0x31
#     START_APP = 0x40
#
#
# class BootyDeviceMetadata:
#     platform: str
#     version: str
#     row_len: int
#     page_len: int
#     prog_len: int
#     max_prog_size: int
#     app_start_address: int
#     boot_start_address: int
#
#
# class BootyProtocol:
#     _process_packets_task = None
#
#     def __init__(self, serial: SerialTrio):
#         self._serial = serial
#         # responses from the robot
#         self._queue = trio.Queue()
#
#     # region Booty Protocol actions
#     async def get_device_metadata(self):
#         with trio.open_nursery() as nursery:
#             platform = self._cmd_request_data(BootyCommand.READ_PLATFORM)
#             version = self._cmd_request_data(BootyCommand.READ_VERSION)
#             row_len = self._cmd_request_data(BootyCommand.READ_ROW_LEN)
#             page_len = self._cmd_request_data(BootyCommand.READ_PAGE_LEN)
#             prog_len = self._cmd_request_data(BootyCommand.READ_PROG_LEN)
#             max_prog_size = self._cmd_request_data(BootyCommand.READ_MAX_PROG_SIZE)
#             app_start_address = self._cmd_request_data(BootyCommand.READ_APP_START_ADDRESS)
#             boot_start_address = self._cmd_request_data(BootyCommand.READ_BOOT_START_ADDRESS)
#             metadata = BootyDeviceMetadata(
#                 platform=await platform,
#                 version=await version,
#                 row_len=await row_len,
#                 page_len=await page_len,
#                 prog_len=await prog_len,
#                 max_prog_size=await max_prog_size,
#                 app_start_address=await app_start_address,
#                 boot_start_address=await boot_start_address,
#             )
#
#         logging.info(f'Platform metadata = {metadata}')
#         return metadata
#
#     def cmd_start_app(self):
#         self._cmd_write(BootyCommand.START_APP)
#
#     def cmd_write_row(self, addr, instructions):
#         self._cmd_write(BootyCommand.WRITE_ROW, addr, instructions)
#
#     def cmd_write_max(self, addr, instructions):
#         self._cmd_write(BootyCommand.WRITE_MAX, addr, instructions)
#
#     def cmd_erase_page(self, addr):
#         self._cmd_write(BootyCommand.ERASE_PAGE, addr)
#
#     async def cmd_read_addr(self, addr):
#         await self._cmd_write(BootyCommand.READ_ADDR, addr)
#         return await self._cmd_expect_response(BootyCommand.READ_ADDR)
#
#     async def cmd_read_max(self, addr):
#         await self._cmd_write(BootyCommand.READ_MAX, addr)
#         return await self._cmd_expect_response(BootyCommand.READ_MAX)
#
#     # endregion
#
#     def _pack_data(self, verb, *args):
#         payload = struct.pack('!H')
#         if verb == BootyCommand.ERASE_PAGE:
#             payload += struct.pack('!H', *args)
#         elif verb in [BootyCommand.WRITE_ROW, BootyCommand.WRITE_MAX]:
#             addr, data = args
#             payload += struct.pack('!H', addr)
#             payload += b''.join(struct.pack('!L', instr) for instr in data)
#         else:
#             # most request packets have no associated data
#             assert len(args) == 0
#
#         return payload
#
#     def _unpack_data(self, payload: bytes) -> Tuple[BootyCommand, Any]:
#         verb = BootyCommand(*struct.unpack('!H', payload[:2]))
#         data = payload[2:]
#
#         if verb in [BootyCommand.READ_PLATFORM, BootyCommand.READ_VERSION]:
#             # interpret data as a string
#             return (verb, data.rstrip(b'\0').decode('utf-8'))
#         elif verb in [BootyCommand.READ_ADDR, BootyCommand.READ_MAX]:
#             # interpret data as a list of instructions (uint32's)
#             return (verb, [x for x, in struct.iter_unpack('!L', data)])
#         else:
#             # interpret data as a uint32
#             return (verb, *struct.unpack('!L', data))
#
#     def _remove_esc_chars(self, raw_message: bytes):
#         if _START_OF_FRAME in raw_message:
#             raise BootyProtocolError('Raw message contains start of frame character', raw_message)
#         if _END_OF_FRAME in raw_message:
#             raise BootyProtocolError('Raw message contains start of frame character', raw_message)
#         if raw_message[-1] == _ESC:
#             raise BootyProtocolError('Raw message ends with escape character', raw_message)
#
#         message = bytearray()
#         escape_next = False
#         for c in raw_message:
#             if escape_next:
#                 message.append(c ^ _ESC_XOR)
#                 escape_next = False
#             elif c == _ESC:
#                 escape_next = True
#             else:
#                 message.append(c)
#         return bytes(message)
#
#     async def _cmd_request_data(self, verb: BootyCommand):
#         assert verb in [BootyCommand.READ_PLATFORM, BootyCommand.READ_VERSION, BootyCommand.READ_ROW_LEN,
#                         BootyCommand.READ_PAGE_LEN, BootyCommand.READ_PROG_LEN, BootyCommand.READ_MAX_PROG_SIZE,
#                         BootyCommand.READ_APP_START_ADDRESS, BootyCommand.READ_BOOT_START_ADDRESS]
#         await self._cmd_write(verb)
#
#         reply_verb, data = await self._queue.get()
#         if verb != reply_verb:
#             raise BootyProtocolError(f'Requested data type {verb} but received {reply_verb} in response', data)
#         return data
#
#     async def _cmd_expect_response(self, expect_verb):
#         reply_verb, data = await self._queue.get()
#         if expect_verb != reply_verb:
#             raise BootyProtocolError(f'Requested data type {expect_verb} but received {reply_verb} in response', data)
#         return data
#
#     async def _cmd_write(self, verb, *args):
#         self._writer.write(
#             bytes([_START_OF_FRAME, *self._make_tx_packet(verb, *args), _END_OF_FRAME])
#         )
#         await self._writer.drain()
#
#     def _make_tx_packet(self, verb, *args):
#         """Create a data packet, not including framing bytes"""
#         pk = bytes([verb] + self._pack_data(verb, *args))
#         pk = pk + self._fletcher16_checksum(pk)
#         pk = pk.replace(bytes([_ESC]), bytes([_ESC, _ESC_XOR ^ _ESC]))
#         pk = pk.replace(bytes([_START_OF_FRAME]), bytes([_ESC, _ESC_XOR ^ _START_OF_FRAME]))
#         pk = pk.replace(bytes([_END_OF_FRAME]), bytes([_ESC, _ESC_XOR ^ _END_OF_FRAME]))
#         return pk
#
#     def _fletcher16_checksum(self, data: bytes):
#         sum1 = 0
#         sum2 = 0
#         for b in data:
#             sum1 = (sum1 + b) % 256
#             sum2 = (sum2 + sum1) % 256
#         return bytes([sum1, sum2])
#
#     async def _receive_packet(self):
#         before_frame_contents = await self._stream_reader.readuntil(bytes([_START_OF_FRAME]))[:-1]
#         if len(before_frame_contents):
#             logging.warning(f'Discarding data before start of frame {before_frame_contents}')
#         raw_message = await self._stream_reader.readuntil(bytes([_END_OF_FRAME]))[:-1]
#         logging.debug(f'Processing packet {raw_message}')
#
#         message = self._remove_esc_chars(raw_message)
#         if len(message) < 3:
#             raise BootyProtocolError('Packet too short', raw_message)
#         payload = message[:-2]
#         checksum = message[-2:]
#         expected_checksum = self._fletcher16_checksum(payload)
#         if checksum != expected_checksum:
#             raise BootyProtocolError('Packet failed checksum check', raw_message)
#
#         return self._unpack_data(payload)
#
#     async def iter_messages(self):
#         while True:
#             try:
#                 msg = await self._receive_packet()
#                 yield msg
#             except BootyProtocolError as e:
#                 logging.warning(f'Skipping packet because of error {e}')
