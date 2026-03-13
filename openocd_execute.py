#!/usr/bin/python3
import sys
import os
import re
import openocd_tools
import argparse
def print_usage():
    print("Usage: openocd_execute.py <PC_address> <-ram/-flash>")

args = len(sys.argv)

if(args < 2):
    print_usage()
    exit(-1)
else:
    pc_address = sys.argv[1]

if(args == 3):
    build = sys.argv[2]
else:
    build = ""

if (re.match(r"0x.*", pc_address)):
	pc_address = int(pc_address, 16)
else:
	pc_address = int(pc_address, 10)

ocd_ctrl = openocd_tools.OPENOCD_CONTROL()

ocd_ctrl.ocd.runCommand("reset halt")
print("\nTarget has been halted")
ocd_ctrl.init_rwtc_cfg_0p9()
print("\nInitialized SYSPLL0_CLKOUT as 24MHz in the clock tree")

if(build == "-flash"):
    ocd_ctrl.initXSPIC(0)
    print("\nInitialized XSPI flash")

ocd_ctrl.ocd.runCommand("set_reg {pc "+str(hex(pc_address))+"}")
print("\nPC set to"+str(hex(pc_address)))
ocd_ctrl.ocd.runCommand("resume")
print("\nTarget resumed")