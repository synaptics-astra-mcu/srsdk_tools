#!/usr/bin/python3

import os, pexpect
from pexpect.exceptions import TIMEOUT
#from src.qautil import surround_text
from pathlib import Path
import telnetlib
import re
import pexpect.popen_spawn
import time
import sys

sram_addr = 0x33F00000

class OPENOCD:
	def __init__(self):
		self.shellPrompt = "5312# "

	def killOpenocdServer(self):
		# pid = os.popen("ps -ef |grep openocd\ |grep -v grep|gawk -e '{print $2}'").read()
		# tt = re.sub(r"\n"," ", pid)
		# if pid:
		# 	os.system("kill -9 "+tt+" 2>&1")
		return 0

	def startOpenocdServer(self):
		# if re.match(".*_swd.*", self.target):
		# 	log = os.system("openocd -f {} -f interface/ftdi/olimex-arm-jtag-swd.cfg -f {} 2>&1 &".format(self.config, self.target))
		# else:
		# 	log = os.system("openocd -f {} -f {} 2>&1 &".format(self.config, self.target))
		# #print(log)
		# time.sleep(0.3)
		self.tn = telnetlib.Telnet('localhost', 4444)
		self.tn.read_until(b"> ")
		print("\nTelnet connection success")
		return 0

	def runCommand(self, command):
		str1 = command+"\n"
		#print(command)
		self.tn.write(str1.encode('ascii'))
		self.tn.read_until(b"> ")
		time.sleep(0.05)
		return 0
   
	def _flush_telnet(self):
		try:
			self.tn.read_very_eager()
		except EOFError:
			pass

	def readMem(self, addr):
		self._flush_telnet()
		str1 = "mdw " + str(addr) + "\n"
		self.tn.write(str1.encode('ascii'))
		val = self.tn.read_until(b"> ")

		# Decode and clean up the response
		response = val.decode('ascii', errors='ignore')

		# Try to find the memory value in the response
		# Expected format: "0xB48A0090: 12345678"
		match = re.search(r'0x[0-9a-fA-F]+:\s*([0-9a-fA-F]+)', response)

		if match:
			ret = int(match.group(1), 16)
			return ret
		else:
			raise ValueError(f"Could not parse memory read response: {repr(response)}")

	def readNMem(self, addr, len):
		str1 = "mdw "+hex(addr)+" "+hex(len)+"\n"
		self.tn.write(str1.encode('ascii'))
		val = self.tn.read_until(b"> ")
		val2 = re.sub(r".*:", r"",str(val))
		val3 = re.sub(r" (\w\w)(\w\w)(\w\w)(\w\w)", r"\4\3\2\1", str(val2))
		ret = re.sub(r"([0-9a-f]+).*", r"\1",str(val3))
		return ret

class OPENOCD_CONTROL:
	def __init__(self):
		self.ocd = OPENOCD()
		retries = 3
		while retries > 0:
			try:
				self.ocd.killOpenocdServer()
				ret = self.ocd.startOpenocdServer()
				if ret != 0:
					print("start of openocd failed; retry")
					retries -=1
					continue
			except TIMEOUT:
				print("start of openocd failed due to timeout; retry")
				retries -= 1
				continue
			break
		if retries == 0:
			print("could not start openocd; abort")
			self.killOpenocdServer()
			exit -1

	def xspic_clk_enable(self):
		#CFG_CLK
		val = self.ocd.readMem(0x50330704)
		val = val | 0x01								#GLOBAL_CLK_ENABLE2__XSPI_CFG_CLK_EN_POS = 0
		self.ocd.runCommand("mww 0x50330704 "+str(val))

		#CORE_CLK
		val = self.ocd.readMem(0x50330730)
		val = val | 0x01
		self.ocd.runCommand("mww 0x50330730 "+str(val))

		#AXI_CLK
		val = self.ocd.readMem(0x50330700)
		val = val | 0x80								#GLOBAL_CLK_ENABLE1__XSPI_AXI_CLK_EN_POS = 7
		self.ocd.runCommand("mww 0x50330700 "+str(val))

	def xspic_clk_disable(self):

		#CFG_CLK
		bit_mask = ~(1<<0)
		val = self.ocd.readMem(0x50330704)
		val = val & bit_mask								# GLOBAL_CLK_ENABLE2__XSPI_CFG_CLK_EN_POS = 0
		self.ocd.runCommand("mww 0x50330704 "+str(val))

		#CORE_CLK
		bit_mask = ~(1<<0)
		val = self.ocd.readMem(0x50330730)
		val = val & bit_mask
		self.ocd.runCommand("mww 0x50330730 "+str(val))

		#AXI_CLK
		bit_mask = ~(1<<7)
		val = self.ocd.readMem(0x50330700)
		val = val & bit_mask								# GLOBAL_CLK_ENABLE1__XSPI_AXI_CLK_EN_POS = 7
		self.ocd.runCommand("mww 0x50330700 "+str(val))

	def xspic_reset(self):
		self.xspic_clk_disable()
		self.ocd.runCommand("mww 0x50330680 0x20")			# GLOBAL_PERIF_RST_OFFSET
		self.xspic_clk_enable()
		self.ocd.runCommand("mww 0x50330680 0x0")			# GLOBAL_PERIF_RST_OFFSET

	def xspic_write_enable(self):
		cmd3 = 0x06 << 0x10
		self.ocd.runCommand("mww 0x5031B004 0x0")                   # XSPI_CTRL_cmd_reg1_OFFSET
		self.ocd.runCommand("mww 0x5031B008 0x0")                   # XSPI_CTRL_cmd_reg2_OFFSET
		self.ocd.runCommand("mww 0x5031B00C "+str(cmd3))          	# XSPI_CTRL_cmd_reg3_OFFSET
		self.ocd.runCommand("mww 0x5031B010 0x0")                   # XSPI_CTRL_cmd_reg4_OFFSET
		self.ocd.runCommand("mww 0x5031B000 0x0")                   # XSPI_CTRL_cmd_reg0_OFFSET
		time.sleep(0.005) #wait 500ms

	def xspic_enable_QE_bit(self):
		self.ocd.runCommand("mww 0x5031B010 0x0")       	# XSPI_CTRL_cmd_reg4_OFFSET
		self.ocd.runCommand("mww 0x5031B00C 0x2010000") 	# XSPI_CTRL_cmd_reg3_OFFSET
		self.ocd.runCommand("mww 0x5031B008 0x0")       	# XSPI_CTRL_cmd_reg2_OFFSET
		self.ocd.runCommand("mww 0x5031B004 0x200")     	# XSPI_CTRL_cmd_reg1_OFFSET
		self.ocd.runCommand("mww 0x5031B000 0x0")       	# XSPI_CTRL_cmd_reg0_OFFSET

	def xspic_direct_prog_cfg(self):
		#xspic_direct_prog_pp_cfg
		self.ocd.runCommand("mww 0x5031B420 0x3002")    	# XSPI_CTRL_prog_seq_cfg_0_OFFSET
		self.ocd.runCommand("mww 0x5031B424 0x0")       	# XSPI_CTRL_prog_seq_cfg_0_OFFSET
		#xspic_direct_stat_cfg
		self.ocd.runCommand("mww 0x5031B450 0x0")       	# XSPI_CTRL_stat_seq_cfg_0_OFFSET
		self.ocd.runCommand("mww 0x5031B454 0x0")       	# XSPI_CTRL_stat_seq_cfg_1_OFFSET
		self.ocd.runCommand("mww 0x5031B458 0x5000005") 	# XSPI_CTRL_stat_seq_cfg_2_OFFSET
		self.ocd.runCommand("mww 0x5031B45C 0x0")       	# XSPI_CTRL_stat_seq_cfg_3_OFFSET
		self.ocd.runCommand("mww 0x5031B464 0x40")      	# XSPI_CTRL_stat_seq_cfg_5_OFFSET
		self.ocd.runCommand("mww 0x5031B46C 0x0")       	# XSPI_CTRL_stat_seq_cfg_7_OFFSET
		self.ocd.runCommand("mww 0x5031B470 0x0")       	# XSPI_CTRL_stat_seq_cfg_8_OFFSET

	def xspic_direct_remap_addr(self):
		self.ocd.runCommand("mww 0x5031B390 0x8F")          # XSPI_CTRL_global_seq_cfg_OFFSET
		self.ocd.runCommand("mww 0x5031B394 0x0")           # XSPI_CTRL_global_seq_cfg_1_OFFSET
		self.ocd.runCommand("mww 0x5031B398 0x1000")        # XSPI_CTRL_direct_access_cfg_OFFSET
		self.ocd.runCommand("mww 0x5031B39C 0x3C000000")    # XSPI_CTRL_direct_access_rmp_OFFSET
		self.ocd.runCommand("mww 0x5031B3A0 0x0")           # XSPI_CTRL_direct_access_rmp_1_OFFSET

	def xspic_direct_read_cfg(self):
		self.ocd.runCommand("mww 0x5031B430 0x62230EB")     # XSPI_CTRL_read_seq_cfg_0_OFFSET
		self.ocd.runCommand("mww 0x5031B434 0x0")           # XSPI_CTRL_read_seq_cfg_1_OFFSET
		self.ocd.runCommand("mww 0x5031B438 0x0")           # XSPI_CTRL_read_seq_cfg_2_OFFSET

	def init_rwtc_cfg_0p9(self):
		self.ocd.runCommand("halt")
		self.ocd.runCommand("mww 0xB48A0094 0x01")			# LPS_GEAR1_RWTC_UPDATE_STS_OFFSET

		bit_mask = ~(0X03)
		val = self.ocd.readMem(0xB48A0090)
		val = val & bit_mask								# LPS_GEAR1_RWTC_UPDATE_CTRL_OFFSET
		val = val | 0x0
		self.ocd.runCommand("mww 0xB48A0090 "+str(hex(val)))

		self.ocd.runCommand("mww 0xB5007018 0xA26CA20B")	# LP_PROC_CLK_RST_LPP_RWTC_CTRL0_OFFSET
		self.ocd.runCommand("mww 0xB500701C 0x6C2C2")		# LP_PROC_CLK_RST_LPP_RWTC_CTRL1_OFFSET
		self.ocd.runCommand("mww 0xB48A0080 0xA26CA20B")	# LPS_GEAR1_G1_RWTC_CTRL0_OFFSET
		self.ocd.runCommand("mww 0xB48A0084 0x6C2C2")		# LPS_GEAR1_G1_RWTC_CTRL1_OFFSET
		self.ocd.runCommand("mww 0x50330100 0xA26CA20B")	# GLOBAL_SOC_RWTC_CTRL0_OFFSET
		self.ocd.runCommand("mww 0x50330104 0x6C2C2")		# GLOBAL_SOC_RWTC_CTRL1_OFFSET

		bit_mask = ~(0X01 << 0x01)
		val = self.ocd.readMem(0xB48A0090)
		val = val & bit_mask
		val = val | 0x2
		self.ocd.runCommand("mww 0xB48A0090 "+str(hex(val)))

		status = self.ocd.readMem(0xB48A0094)
		while(status == 0):
			status = self.ocd.readMem(0xB48A0094)

		bit_mask = ~(0X07 << 0x10)							# AON_MAIN_AON_MAIN_PMU_CNTL3
		val = self.ocd.readMem(0x50350090)
		val = val & bit_mask
		val = val | ((0x5 & 0x7) << 0x10)
		self.ocd.runCommand("mww 0x50350090 "+str(val))
		time.sleep(1)

		bit_mask = ~(0X01 << 0x03)							# LPS_GEAR1_REF_PLL
		val = self.ocd.readMem(0xB48A0004)
		val = val & bit_mask
		val = val | 0x0
		self.ocd.runCommand("mww 0xB48A0004 "+str(val))

		bit_mask = ~(0X01 << 0x02)							# GLOBAL_CPU_CLK_CTRL
		val = self.ocd.readMem(0x50330720)
		val = val & bit_mask
		val = val | 0x0
		self.ocd.runCommand("mww 0x50330720 "+str(val))

	def dma_init(self):

		val = self.ocd.readMem(0x50330700)
		val = val & ~(1 << 4)
		val = val | (1 << 4)
		self.ocd.runCommand("mww 0x50330700 "+str(val))			# DMA0 clk enable

		val = self.ocd.readMem(0x50330658)
		val = val & ~(1 << 2)
		val = val | (1 << 2)
		self.ocd.runCommand("mww 0x50330658 "+str(val))  		# GLOBAL_TOP_STICKY_RST

		val = self.ocd.readMem(0x50330640)
		val = val & ~(1 << 0)
		val = val | (1 << 0)
		self.ocd.runCommand("mww 0x50330640 "+str(val))  		# GLOBAL_DMA0_RST

		val = self.ocd.readMem(0x50330640)
		val = val & ~(1 << 0)
		val = val | (0 << 0)
		self.ocd.runCommand("mww 0x50330640 "+str(val))  		# GLOBAL_DMA0_RST

		self.ocd.runCommand("mww 0x50322008 0x0")  				# DMA0_SCFG_TRIGINSEC0_OFFSET

		self.ocd.runCommand("mww 0x50302054 0xFFFFFFFF")  		# SOC_SOC_REG_DMA0_TRIG_EN_OFFSET

	def dma_channel_config(self, offset, size):

		flash_addr = 0x3C000000 + offset
		# flash_addr = offset
		flash_size = (size << 16) | (size)

		self.ocd.runCommand("mww 0x50323028 0x000F0822")				# DMA0_DMACH0_CH_SRCTRANSCFG
		self.ocd.runCommand("mww 0x50323010 "+str(hex(sram_addr)))				# DMA0_DMACH0_CH_SRCADDR_OFFSET
		self.ocd.runCommand("mww 0x5032302C 0x000F0877")				# DMA0_DMACH0_CH_DESTRANSCFG
		self.ocd.runCommand("mww 0x50323018 "+str(hex(flash_addr)))		# DMA0_DMACH0_CH_DESADDR_OFFSET

		self.ocd.runCommand("mww 0x50323020 "+str(hex(flash_size)))		# DMA0_DMACH0_CH_XSIZE
		self.ocd.runCommand("mww 0x5032300C 0x00200200")				# DMA0_DMACH0_CH_CTRL
		self.ocd.runCommand("mww 0x50323030 0x00010001")				# DMA0_DMACH0_CH_AUTOCFG

	def dma_channel_start(self):
		self.ocd.runCommand("mww 0x50323008 0x00000003")				# DMA0_DMACH0_CH_INTREN

		self.ocd.runCommand("mww 0x50323000 0x00000001")				# DMA0_DMACH0_CH_CMD


	def initXSPIC(self, flash_erase):

		do_erase = flash_erase

		#sxpi clk enable
		self.xspic_clk_enable()

		#set CORE_CLK
		self.ocd.runCommand("mww 0x50330730 0x35")

		#init IO
		self.ocd.runCommand("mww 0x5033885C 0x1B")     		# GLOBAL_XSPI_DATA0_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50338860 0x1B")     		# GLOBAL_XSPI_DATA1_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50338864 0x1B")     		# GLOBAL_XSPI_DATA2_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50338868 0x1B")     		# GLOBAL_XSPI_DATA3_CTRL_OFFSET
		self.ocd.runCommand("mww 0x5033886C 0x1B")     		# GLOBAL_XSPI_DATA4_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50338870 0x1B")     		# GLOBAL_XSPI_DATA5_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50338874 0x1B")     		# GLOBAL_XSPI_DATA6_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50338878 0x1B")     		# GLOBAL_XSPI_DATA7_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50338880 0x1B")     		# GLOBAL_XSPI_CLK_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50338884 0x1B")     		# GLOBAL_XSPI_CLK_N_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50338888 0x1B")     		# GLOBAL_XSPI_CS0_CTRL_OFFSET

		#Init bootstrap
		self.ocd.runCommand("mww 0x50330A6C 0xA")           # GLOBAL_PERIF_XSPI_RB_VALID_TIME_OFFSET
		self.ocd.runCommand("mww 0x50330A5C 0x2")           # GLOBAL_PERIF_XSPI_CTRL0_OFFSET
		self.ocd.runCommand("mww 0x50330A68 0x498EB")       # GLOBAL_PERIF_XSPI_CTRL3_OFFSET
		self.ocd.runCommand("mww 0x50330A64 0x30E")         # GLOBAL_PERIF_XSPI_CTRL2_OFFSET
		self.ocd.runCommand("mww 0x50330A70 0x101")         # GLOBAL_PERIF_XSPI_PHY_DQ_TIMING_OFFSET
		self.ocd.runCommand("mww 0x50330A74 0x700404")      # GLOBAL_PERIF_XSPI_PHY_DQS_TIMING_OFFSET
		self.ocd.runCommand("mww 0x50330A78 0x200030")      # GLOBAL_PERIF_XSPI_PHY_GATE_LPBK_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50330A7C 0x800000")      # GLOBAL_PERIF_XSPI_PHY_DLL_MASTER_CTRL_OFFSET
		self.ocd.runCommand("mww 0x50330A80 0x00007801")    # GLOBAL_PERIF_XSPI_PHY_DLL_SLAVE_CTRL_OFFSET

		#xspi reset
		self.xspic_reset()
		time.sleep(0.5) #wait 500ms

		#Phy Init
		self.ocd.runCommand("mww 0x50330A60 0x2")           # GLOBAL_PERIF_XSPI_CTRL1_OFFSET
		self.ocd.runCommand("mww 0x5031C034 0x30707")       # XSPI_CTRL_dll_phy_ctrl_OFFSET
		self.ocd.runCommand("mww 0x5031D000 0x101")         # XSPI_PHY_phy_dq_timing_reg_OFFSET
		self.ocd.runCommand("mww 0x5031D004 0x700404")      # XSPI_PHY_phy_dqs_timing_reg_OFFSET
		self.ocd.runCommand("mww 0x5031D008 0x200030")      # XSPI_PHY_phy_gate_lpbk_ctrl_reg_OFFSET
		self.ocd.runCommand("mww 0x5031D00C 0x800000")      # XSPI_PHY_phy_dll_master_ctrl_reg_OFFSET
		self.ocd.runCommand("mww 0x5031D010 0x3300")        # XSPI_PHY_phy_dll_slave_ctrl_reg_OFFSET
		self.ocd.runCommand("mww 0x5031D080 0x4000")        # XSPI_PHY_phy_ctrl_reg_OFFSET
		self.ocd.runCommand("mww 0x5031C034 0x707")         # XSPI_CTRL_dll_phy_ctrl_OFFSET
		self.ocd.runCommand("mww 0x5031C034 0x1000707")     # XSPI_CTRL_dll_phy_ctrl_OFFSET
		time.sleep(0.5) #wait 500ms

		self.ocd.runCommand("mww 0x5031B230 0x20")			# STIG mode
		self.ocd.runCommand("mww 0x5031C000 0x01")			# disable wp_enable_setting
		self.xspic_write_enable()
		self.xspic_enable_QE_bit()
		if(do_erase == 1):
			self.xspic_send_chip_erase()
			print("\nPerformed full flash erase")
		self.xspic_direct_remap_addr()
		self.xspic_direct_read_cfg()
		self.xspic_direct_prog_cfg()
		time.sleep(0.5) #wait 500ms
		self.ocd.runCommand("mww 0x5031B230 0x0")			#direct mode

	def xspic_send_chip_erase(self):

		self.xspic_write_enable()

		# CHIP ERASE
		cmd3 = 0x60 << 0x10
		# self.ocd.runCommand("mww 0x5031B004 0x0")                   # XSPI_CTRL_cmd_reg1_OFFSET
		# self.ocd.runCommand("mww 0x5031B008 0x0")                   # XSPI_CTRL_cmd_reg2_OFFSET
		# # self.ocd.runCommand("mww 0x5031B00C "+str(cmd3))          	# XSPI_CTRL_cmd_reg3_OFFSET
		# self.ocd.runCommand("mww 0x5031B00C 0x600000")
		# self.ocd.runCommand("mww 0x5031B010 0x0")                   # XSPI_CTRL_cmd_reg4_OFFSET
		# self.ocd.runCommand("mww 0x5031B000 0x0")                   # XSPI_CTRL_cmd_reg0_OFFSET
		# time.sleep(2)
		self.ocd.runCommand("mww 0x5031B010 0x0")                   # XSPI_CTRL_cmd_reg4_OFFSET
		self.ocd.runCommand("mww 0x5031B00C 0x600000")
		self.ocd.runCommand("mww 0x5031B008 0x0")                   # XSPI_CTRL_cmd_reg2_OFFSET
		self.ocd.runCommand("mww 0x5031B004 0x0")                   # XSPI_CTRL_cmd_reg1_OFFSET
		# self.ocd.runCommand("mww 0x5031B00C "+str(cmd3))          	# XSPI_CTRL_cmd_reg3_OFFSET
		self.ocd.runCommand("mww 0x5031B000 0x0")                   # XSPI_CTRL_cmd_reg0_OFFSET
		# time.sleep(2)
		self.xspic_wait_while_busy()

	def xspic_wait_while_busy(self):
		# Read status register until busy bit (bit 0) is cleared
		status = 1
		while status & 0x01:
			self.ocd.runCommand("mww 0x5031B004 0x0")  # cmd_reg1
			self.ocd.runCommand("mww 0x5031B008 0x0")  # cmd_reg2
			self.ocd.runCommand("mww 0x5031B00C 0x050000")  # cmd: 0x05 << 16
			self.ocd.runCommand("mww 0x5031B010 0x0")  # cmd_reg4
			self.ocd.runCommand("mww 0x5031B000 0x0")  # trigger
			time.sleep(0.002)
			status = self.ocd.readMem("0x5031B020") & 0xFF  # XSPI_CTRL_cmd_read_data_REG
			# print(f"SPI status reg: 0x{status:02X}")
			sys.stdout.flush()
	def xspic_wait_for_instr_end(self, timeout_ms=100):
		"""
		Wait for XSPI STIG instruction to complete.
		Equivalent to xspic_stig_wait_for_instr_end() in C code.
		"""

		XSPI_CTRL_CMD_STATUS = 0x5031B044
		start_time = time.time()

		while True:
			stig_status = self.ocd.readMem(hex(XSPI_CTRL_CMD_STATUS)) & 0xFFFFFFFF

			# print(f"[xspic_wait_for_instr_end] STIG status = 0x{stig_status:08X}")

			# Exit if STIG instruction has finished (non-zero means done)
			if stig_status != 0:
				return True

			# Timeout check (convert seconds to ms)
			if (time.time() - start_time) * 1000 > timeout_ms:
				print("Timeout waiting for STIG instruction end!")
				return False

			# Short delay before polling again (1 ms)
			time.sleep(0.001)

	def xspic_erase_region(self, start_addr, total_size):
		"""
		Erases the flash region needed for the image.
		Equivalent to xspic_stig_cmd_erase() in C, but extended for multiple sectors.
		"""
		# Each erase = 64KB sector (change to 4KB if your flash uses 0x1000)
		print(f"Start address: 0x{start_addr:X}")
		sector_size = 0x10000
		# 4KB
		# sector_size = 0x1000
		end_addr = start_addr + total_size
		aligned_start = start_addr & ~(sector_size - 1)
		aligned_end = (end_addr + sector_size - 1) & ~(sector_size - 1)

		print(f"Erasing flash region from 0x{aligned_start:X} to 0x{aligned_end:X}")

		for addr in range(aligned_start, aligned_end, sector_size):
			print(f"\nErasing sector @ 0x{addr:X}")

			# --- Busy check ---
			while self.ocd.readMem("0x5031B100") & 0x1:
				print("Controller busy, waiting...")
				time.sleep(0.002)

			# --- Workmode check ---
			workmode = self.ocd.readMem("0x5031B230") & 0xFF
			if workmode != 0x20:
				# print("[xspic_erase_region] Switching to STIG mode...")
				self.ocd.runCommand("mww 0x5031B230 0x00000020")
				time.sleep(0.001)

			# --- Read Status: CMD Reg ---
			self.ocd.runCommand("mww 0x5031B010 0x00000000")
			self.ocd.runCommand("mww 0x5031B00C 0x00050000")
			self.ocd.runCommand("mww 0x5031B008 0x00000000")
			self.ocd.runCommand("mww 0x5031B004 0x00000001")
			self.ocd.runCommand("mww 0x5031B000 0x00000000")
			time.sleep(0.002)

			# --- Read Status: Glue Reg ---
			self.ocd.runCommand("mww 0x5031B010 0x00000000")
			self.ocd.runCommand("mww 0x5031B00C 0x00000000")
			self.ocd.runCommand("mww 0x5031B008 0x00010000")
			self.ocd.runCommand("mww 0x5031B004 0x0100007F")
			self.ocd.runCommand("mww 0x5031B000 0x00000000")
			time.sleep(0.002)

			# --- Write Enable ---
			self.ocd.runCommand("mww 0x5031B004 0x00000000")
			self.ocd.runCommand("mww 0x5031B008 0x00000000")
			self.ocd.runCommand("mww 0x5031B00C 0x00060000")
			self.ocd.runCommand("mww 0x5031B010 0x00000000")
			self.ocd.runCommand("mww 0x5031B000 0x00000000")
			time.sleep(0.002)

			# --- Erase Command ---
			opcode = 0xD8  # 0x20 = 4KB erase; 0xD8 = 64KB erase
			addr24 = addr & 0xFFFFFF

			cmd_reg0 = 0x00000000
			cmd_reg1 = ((addr24 & 0xFF) << 24)
			cmd_reg2 = (addr24 >> 8)
			cmd_reg3 = ((opcode & 0xFF) << 16) | (3 << 28)  # 3 address bytes
			cmd_reg4 = 0x00000000

			self.ocd.runCommand(f"mww 0x5031B010 {cmd_reg4:#010x}")
			self.ocd.runCommand(f"mww 0x5031B00C {cmd_reg3:#010x}")
			self.ocd.runCommand(f"mww 0x5031B008 {cmd_reg2:#010x}")
			self.ocd.runCommand(f"mww 0x5031B004 {cmd_reg1:#010x}")
			self.ocd.runCommand(f"mww 0x5031B000 {cmd_reg0:#010x}")

			# --- Wait for instruction to complete ---
			self.xspic_wait_for_instr_end()

			# --- Wait while busy (poll flash WIP bit) ---
			self.xspic_wait_while_busy()

		# --- Switch back to DIRECT mode before reading flash ---
		# print("Switching to Direct mode for readback...")
		self.ocd.runCommand("mww 0x5031B230 0x00000000")
		time.sleep(0.001)

		# Verify that the mode changed
		mode_after = self.ocd.readMem("0x5031B230") & 0xFF
		# print(f"[xspic_erase_region] Current work mode after switch: 0x{mode_after:02X}")

		# --- Read from mapped flash to verify erase ---
		val1 = self.ocd.readMem(hex(0x3C000000))
		# print(f"After erase read starting @0x{0x3C000000:X}: 0x{val1:08X}")
		print(f"Sector erase completed, proceeding to flash the binary")

	def erase_flash_only(self):
		self.ocd.runCommand("halt")
		print("Target halted")
		self.init_rwtc_cfg_0p9()
		self.initXSPIC(flash_erase=1)

	def flash_image(self, file_name, file_offset, flash_offset, flash_erase):
		self.ocd.runCommand("halt")
		print("\nTarget has been halted")
		self.init_rwtc_cfg_0p9()
		print("\nInitialized SYSPLL0_CLKOUT as 24MHz in the clock tree")

		ram = sram_addr
		chunk_size = 0x6000
		file_stats = os.stat(file_name)
		total_size = file_stats.st_size

		if file_offset != 0:
			total_size -= file_offset
		erase_size = total_size + 0x10000

		if flash_erase == 2:
			self.initXSPIC(flash_erase=1)
		elif flash_erase == 1:
			self.initXSPIC(flash_erase=0)
			print("\nInitialized XSPI flash")
			print(f"\nImage size: 0x{total_size:X}")
			print(f"Erasing region before flashing...")
			self.xspic_erase_region(flash_offset, erase_size)

		print(f"\nNow loading image {file_name} at memory 0x{0x3C000000 + flash_offset:X}")

		fo = file_offset
		offset = flash_offset
		remaining = total_size

		self.dma_init()

		while remaining > 0:
			current_chunk = min(chunk_size, remaining)

			self.ocd.runCommand(f'load_image "{file_name}" [expr {{{hex(ram)} - {hex(fo)}}}] bin {ram} {current_chunk}')

			self.dma_channel_config(offset, current_chunk)
			self.dma_channel_start()

			fo += current_chunk
			offset += current_chunk
			remaining -= current_chunk

			progress = int((total_size - remaining) / total_size * 100)
			print(f"Flashing progress: {progress}%")
			sys.stdout.flush()

			# Wait for DMA to finish
			val = 1
			while val:
				val = self.ocd.readMem("0x50323000")

		self.initXSPIC(0)
