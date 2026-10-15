#!/usr/bin/env python3
# Release the SPI flash of a halted TLSR825x from deep power-down (0xAB) and
# print its first 64 bytes. Does not modify the flash.
#
# Usage: copy next to TLSR825xComFlasher.py (pvvx/TlsrComSwireWriter), halt the
# chip first (see README, "Updating an already flashed device"), then run:
#   python flash_wake_read.py COM21
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import serial
import TLSR825xComFlasher as flasher

if len(sys.argv) != 2:
	print('Usage: %s <serial port>' % sys.argv[0])
	sys.exit(1)

flasher.debug = False
port = serial.Serial(sys.argv[1], 921600)
port.reset_input_buffer()
port.timeout = 0.1

if not flasher.set_sws_auto_speed(port):
	print('No SWS link: halt the chip first (see README)')
	sys.exit(1)

flasher.rd_sws_wr_addr_usbcom(port, 0x0d, bytearray([0x00]))  # SPI cns low
flasher.rd_sws_wr_addr_usbcom(port, 0x0c, bytearray([0xAB]))  # release from deep power-down
flasher.rd_sws_wr_addr_usbcom(port, 0x0d, bytearray([0x01]))  # SPI cns high

data = io.BytesIO()
if not flasher.FlashReadBlock(port, data, 0, 64):
	print('Flash read failed')
	sys.exit(1)

print()
print(data.getvalue().hex())
