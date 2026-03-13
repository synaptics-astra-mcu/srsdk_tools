#!/usr/bin/python3

import sys
import os
import re
import openocd_tools
import time  # for sleep
import argparse

def print_usage():
    print("Usage: openocd_flash.py <image_flash.bin> <file_offset> <flash_offset> <flash_flag(0/1/2)>")

args = len(sys.argv)

if args < 5:
    print_usage()
    exit(-1)
else:
    file_name = sys.argv[1]
    file_offset = sys.argv[2]
    flash_offset = sys.argv[3]
    flash_flag = int(sys.argv[4], 10)

if re.match(r"0x.*", file_offset):
    file_offset = int(file_offset, 16)
else:
    file_offset = int(file_offset, 10)

if re.match(r"0x.*", flash_offset):
    flash_offset = int(flash_offset, 16)
else:
    flash_offset = int(flash_offset, 10)

# -------------------------
# Retry loop for OpenOCD
# -------------------------
max_retries = 10
retry_delay = 1  # seconds
ocd_ctrl = None

for attempt in range(max_retries):
    try:
        ocd_ctrl = openocd_tools.OPENOCD_CONTROL()
        print(f"Connected to OpenOCD")
        break
    except Exception as e:
        # print(f"OpenOCD not ready yet (attempt {attempt + 1}/{max_retries}): {e}")
        time.sleep(retry_delay)
else:
    print("ERROR: Unable to connect to OpenOCD after multiple attempts")
    exit(-1)

# -------------------------
# Flashing logic
# -------------------------
if flash_flag == 0:
    print("Flash erase flag is set. Performing full chip erase...")
    ocd_ctrl.erase_flash_only()
    exit(0)
else:
    ocd_ctrl.flash_image(file_name, file_offset, flash_offset, flash_flag)
