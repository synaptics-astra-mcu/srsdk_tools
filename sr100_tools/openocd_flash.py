#!/usr/bin/env python3
"""
flash_xspi_tcl.py
---------------------------------
Python tool to program external XSPI flash on an M55-based MCU via OpenOCD,
using the TCL RPC server.

"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import shlex
import socket
import struct
import subprocess
import sys
import time
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# ----------------------- Constants & defaults -----------------------

DEFAULT_TCL_PORT = 6666
XIP_BASE = 0x3C000000                  #
SRAM_BUF = 0x33F00000                  # safe SRAM staging address
CHUNK_SIZE = 0x40000                   # 256 KiB chunks for DMA throughput
SRAM_BUF_ALT = SRAM_BUF + CHUNK_SIZE   # second staging buffer for overlap
ERASE_32K_SIZE = 32 * 1024
ERASE_64K_SIZE = 64 * 1024
ERASE_4K_SIZE = 4 * 1024
ERASE_CMD_ALL = 0xC7
ERASE_CMD_64K = 0xD8
ERASE_CMD_32K = 0x52
ERASE_CMD_4K = 0x20
WREN_CMD = 0x06
RDSR1_CMD = 0x05
RDSR2_CMD = 0x35
WRSR12_CMD = 0x01

# Timeouts
STARTUP_TIMEOUT_S = 10.0
CMD_TIMEOUT_S = 20.0
ERASE_TIMEOUT_S = 20.0
PROGRAM_TIMEOUT_S = 30.0

# ----------------------- Utilities -----------------------

def hex32(x: int) -> str:
    return f"0x{x:08X}"

def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b

# ----------------------- TCL RPC Client -----------------------

class TclRpcClient:
    """
    Lightweight client for OpenOCD's TCL RPC server.

    Responsibilities:
    - Open a TCP connection to the TCL port (default 6666).
    - Send TCL strings terminated by 0x1A and read until the same terminator.
    - Provide a simple `cmd` helper that wraps OpenOCD's `capture` command.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_TCL_PORT,
                 timeout_s: float = CMD_TIMEOUT_S):
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.sock: Optional[socket.socket] = None

    def connect(self, attempts: int = 20, delay_s: float = 0.25) -> None:
        """
        Connect to the TCL port with retry/backoff. Closes any existing socket first,
        then attempts to connect up to `attempts` times, sleeping `delay_s` between tries.
        Runs a sanity ping (`set ::ocd_rpc 1`) to confirm the server speaks TCL RPC.
        Raises ConnectionError if unsuccessful.
        """
        last_err = None
        # If already connected, close the existing socket before retrying
        if self.sock:
            self.close()

        for _ in range(attempts):
            s: Optional[socket.socket] = None
            try:
                s = socket.create_connection((self.host, self.port), timeout=self.timeout_s)
                s.settimeout(self.timeout_s)
                self.sock = s
                out = self.eval('set ::ocd_rpc 1')
                if '1' not in out:
                    raise RuntimeError(f"TCL sanity check failed: {out!r}")
                return
            except (OSError, TimeoutError, RuntimeError) as e:
                last_err = e
                if s:
                    with contextlib.suppress(Exception):
                        s.close()
                self.sock = None
                time.sleep(delay_s)
        raise ConnectionError(f"Unable to connect to OpenOCD TCL port at {self.host}:{self.port}: {last_err}")

    def close(self) -> None:
        """Close the TCP socket to the TCL server, ignoring any close errors."""
        if self.sock:
            with contextlib.suppress(Exception):
                self.sock.close()
        self.sock = None

    def _send(self, payload: str) -> None:
        """Send raw TCL text terminated with 0x1A."""
        if not self.sock:
            raise ConnectionError("TclRpcClient not connected.")
        self.sock.sendall(payload.encode('utf-8', 'ignore') + b'\x1a')

    def _recv_until_term(self) -> str:
        """
        Read from the socket until a 0x1A terminator arrives or the per-command
        timeout elapses. Returns the UTF-8 decoded response (terminator stripped).
        """
        if not self.sock:
            raise ConnectionError("TclRpcClient not connected.")
        chunks = []
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            try:
                b = self.sock.recv(4096)
                if not b:
                    raise ConnectionError("OpenOCD TCL socket closed")
                pos = b.find(b'\x1a')
                if pos >= 0:
                    chunks.append(b[:pos])
                    return b''.join(chunks).decode('utf-8', 'ignore')
                chunks.append(b)
            except socket.timeout:
                pass
        raise TimeoutError("Timeout waiting for TCL response terminator 0x1A")

    def eval(self, tcl: str) -> str:
        """Send a raw TCL script to OpenOCD and return its captured output."""
        self._send(tcl)
        return self._recv_until_term()

    def cmd(self, command: str) -> str:
        # Basic escaping for double quotes; allow Tcl substitutions (e.g., [expr {...}])
        esc = command.replace('"', '\\"')
        return self.eval(f'capture "{esc}"')

# ----------------------- OpenOCD server wrapper -----------------------

class OpenOcdServerConfig:
    """
    Simple value object describing how to launch OpenOCD.

    Fields:
    - openocd: path or name of the openocd executable.
    - cfg_path: OpenOCD configuration file to load.
    - tcl_port: TCL RPC port to bind (default 6666).
    - probe: optional adapter driver name to inject as PROBE (e.g., cmsis-dap, jlink).
    """
    def __init__(
        self,
        openocd: str,
        cfg_path: Path,
        host: str = "127.0.0.1",
        tcl_port: int = DEFAULT_TCL_PORT,
        probe: Optional[str] = None,
    ) -> None:
        self.openocd = openocd
        self.cfg_path = cfg_path
        self.host = host
        self.tcl_port = tcl_port
        self.probe = probe

class OpenOcdServer:
    """
    Thin wrapper to start/stop an OpenOCD subprocess and ensure the TCL port is alive.

    start():
      - Validates executable and cfg path.
      - Builds the OpenOCD argv with TCL port and optional PROBE.
      - Launches OpenOCD, then polls for process health and TCL port availability.
      - On failure, stops the process before raising.

    stop():
      - Gracefully terminates the subprocess, then kills if it does not exit promptly.
    """
    def __init__(self, config: OpenOcdServerConfig) -> None:
        self.config = config
        self.proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        if self.proc and self.proc.poll() is None:
            raise RuntimeError("OpenOCD already running; stop() it first.")

        # Resolve openocd executable
        exe = shutil.which(self.config.openocd)
        if exe is None:
            raise FileNotFoundError(f"openocd binary not found: {self.config.openocd}")

        if not self.config.cfg_path.exists():
            raise FileNotFoundError(f"OpenOCD cfg not found: {self.config.cfg_path}")

        #Load the openocd command, this could just be "openocd" if it's in PATH, or it is the path to openocd binary
        args = [exe]

        # Always set TCL port explicitly
        args += ["-c", f"tcl_port {self.config.tcl_port}"]

        # Set the probe if provided
        if self.config.probe:
            args += ["-c", f"set PROBE {self.config.probe}"]

        #pipe output to a file
        args += ["-c", f"debug_level 1"]
        args += ["-c", f'log_output "openocd.log"']

        # Now load the config script path
        args += ["-f", str(self.config.cfg_path)]

        env = os.environ.copy()

        logging.debug("Starting OpenOCD: %s", " ".join(shlex.quote(a) for a in args))
        self.proc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            bufsize=1,
        )

        try:
            # Quick health check: ensure the process stays up and TCL port is reachable
            deadline = time.monotonic() + STARTUP_TIMEOUT_S
            while time.monotonic() < deadline:
                code = self.proc.poll()
                if code is not None:
                    raise RuntimeError(f"OpenOCD exited early with code {code}")
                try:
                    with socket.create_connection((self.config.host, self.config.tcl_port), timeout=0.2):
                        return
                except OSError:
                    time.sleep(0.1)
            raise TimeoutError(f"Timed out waiting for OpenOCD TCL port {self.config.tcl_port} to come up.")
        except Exception:
            # Ensure we don’t leave a stray OpenOCD running on failure
            self.stop()
            raise

    def stop(self) -> None:
        if not self.proc:
            return
        if self.proc.poll() is None:
            with contextlib.suppress(Exception):
                self.proc.terminate()
            try:
                self.proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(Exception):
                    self.proc.kill()
        self.proc = None

# ----------------------- OpenOCD command helpers -----------------------

class Ocd:
    """
    Thin convenience wrapper over TclRpcClient for common OpenOCD commands.

    Responsibilities:
    - Provide small helpers for version/halting/resetting.
    - Wrap memory read/write (mdw/mww) with parsing and simple error handling.
    - Offer chunked image load into SRAM and image verification helpers.
    """
    def __init__(self, client: TclRpcClient) -> None:
        self.c = client

    def version(self) -> str:
        return self.c.cmd("version")

    def halt(self, ms: int = 500) -> None:
        out = self.c.cmd(f"halt {ms}")
        if "target halted" not in out and "Halted" not in out:
            logging.debug("halt output: %s", out.strip())

    def reset_init(self) -> None:
        out = self.c.cmd("reset init")
        if "failed" in out.lower() or "error" in out.lower():
            raise RuntimeError(f"reset init failed: {out.strip()}")

    def mdw(self, addr: int, count: int = 1):
        """
        Read one or more 32-bit words. Returns an int when count==1, otherwise a list[int].
        Parses each line and prefers the value after the colon (OpenOCD format: "addr: value").
        Raises if the expected number of words cannot be parsed from OpenOCD output.
        """
        out = self.c.cmd(f"mdw {hex(addr)} {count}")
        vals = []
        for line in out.splitlines():
            # Prefer the value after the colon, e.g., "0xb48a0090: 0000001e"
            m = re.search(r":\s*(0x[0-9a-fA-F]+|[0-9A-Fa-f]{8})", line)
            token = None
            if m:
                token = m.group(1)
            else:
                # Fallback: last hex-ish token on the line
                toks = re.findall(r"(0x[0-9a-fA-F]+|[0-9A-Fa-f]{8})", line)
                if toks:
                    token = toks[-1]
            if token:
                token = token if token.lower().startswith("0x") else "0x" + token
                vals.append(int(token, 16))
            if len(vals) >= count:
                break
        if len(vals) < count:
            raise RuntimeError(f"Unexpected mdw output (wanted {count} words): {out.strip()}")
        return vals[0] if count == 1 else vals

    def mww(self, addr: int, value: int) -> None:
        out = self.c.cmd(f"mww {hex(addr)} {hex(value & 0xFFFFFFFF)}")
        lower = out.lower()
        if any(k in lower for k in ("error", "fail", "unknown", "usage")):
            raise RuntimeError(f"mww failed: {out.strip()}")

    def load_image_chunk(self, file: Path, sram_addr: int, file_off: int, size: int) -> bool:
        bias_expr = f'[expr {{{hex(sram_addr)} - {hex(file_off)}}}]'
        cmd = f'load_image "{file}" {bias_expr} bin {hex(sram_addr)} {hex(size)}'
        out = self.c.cmd(cmd)
        if "unknown" in out.lower() or "usage" in out.lower() or "error" in out.lower():
            return False
        return True

    def verify_image(self, file: Path, addr: int, file_off: int = 0, size: Optional[int] = None) -> bool:
        # If size is None, let OpenOCD verify the remainder of the file from file_off.
        extra = ""
        if file_off or size is not None:
            if size is None:
                extra = f" {hex(file_off)}"
            else:
                extra = f" {hex(file_off)} {hex(size)}"
        out = self.c.cmd(f'verify_image "{file}" {hex(addr)} bin{extra}')
        lower = out.lower()
        if "verified ok" in lower or "verified" in lower:
            return True
        if "no such file" in lower:
            raise FileNotFoundError(file)
        if "checksum mismatch" in lower:
            logging.error("verify_image reported checksum mismatch; not attempting binary compare.")
            return False
        logging.warning("verify_image output:\n%s", out.strip())
        return False

# ----------------------- SR110 platform helpers -----------------------

class SR110:

    def __init__(self, ocd: Ocd) -> None:
        self.ocd = ocd

    def init_rwtc_cfg_0p9(self) -> None:
        # Status & control updates
        self.ocd.halt(500)

        self.ocd.mww(0xB48A0094, 0x01)  # Clear the rwtc update done status bit in gear1_cfg_RWTC_UPDATE_STS

        # Prepare for RWTC config update, gear1_cfg_RWTC_UPDATE_CTRL
        val = self.ocd.mdw(0xB48A0090)
        val &= ~0x3
        val |= 0x0
        self.ocd.mww(0xB48A0090, val)

        #Set RWTC for 0.9V operation
        self.ocd.mww(0xB5007018, 0xA26CA20B)    # LP_PROC_CLK_RST_LPP_RWTC_CTRL0
        self.ocd.mww(0xB500701C, 0x6C2C2)       # LP_PROC_CLK_RST_LPP_RWTC_CTRL1
        self.ocd.mww(0xB48A0080, 0xA26CA20B)    # LPS_GEAR1_G1_RWTC_CTRL0
        self.ocd.mww(0xB48A0084, 0x6C2C2)       # LPS_GEAR1_G1_RWTC_CTRL1
        self.ocd.mww(0x50330100, 0xA26CA20B)    # GLOBAL_SOC_RWTC_CTRL0
        self.ocd.mww(0x50330104, 0x6C2C2)       # GLOBAL_SOC_RWTC_CTRL1

        # Trigger RWTC config update, gear1_cfg_RWTC_UPDATE_CTRL
        val = self.ocd.mdw(0xB48A0090)
        val &= ~(0X01 << 0x01)
        val |= 0x2
        self.ocd.mww(0xB48A0090, val)

        # Wait for RWTC update done with a timeout
        status = self.ocd.mdw(0xB48A0094)  # read gear1_cfg_RWTC_UPDATE_STS
        deadline = time.monotonic() + 5.0
        while status == 0 and time.monotonic() < deadline:
            time.sleep(0.001)
            status = self.ocd.mdw(0xB48A0094)
        if status == 0:
            raise TimeoutError("RWTC status did not update within 5s")

        # Set PMU output to 0.9V AON_Main_PMU_CNTRL3
        val = self.ocd.mdw(0x50350090)
        val &= ~(0x07 << 0x10) #Clear VOUT
        val |= ((0x05 & 0x07) << 0x10) #Set VOUT to 0.9V
        self.ocd.mww(0x50350090, val)
        time.sleep(1) #Wait for voltage to settle

        # Clear the divide by 2 on the gear 3 clock gear1_cfg_ref_pll
        val = self.ocd.mdw(0xB48A0004)
        val &= ~(0x01 << 0x03)
        val |=  0x00
        self.ocd.mww(0xB48A0004, val)

        # Clear divider on CPU clock global_cfg_core_clk_ctrl
        val = self.ocd.mdw(0x50330720)
        val &= ~(0x01 << 0x02)
        val |= 0x00
        self.ocd.mww(0x50330720, val)

# ----------------------- XSPI / DMA sequences -----------------------

class XspiController:
    def __init__(self, ocd: Ocd) -> None:
        self.ocd = ocd
        self.XSPI_BASE = 0x5031B000
        self.REG_CMD0 = self.XSPI_BASE + 0x000
        self.REG_CMD1 = self.XSPI_BASE + 0x004
        self.REG_CMD2 = self.XSPI_BASE + 0x008
        self.REG_CMD3 = self.XSPI_BASE + 0x00C
        self.REG_CMD4 = self.XSPI_BASE + 0x010
        self.REG_CMD_STATUS = self.XSPI_BASE + 0x044       # cmd_status
        self.REG_CTRL_STATUS = self.XSPI_BASE + 0x100      # ctrl_status
        self.REG_INTR_STATUS = self.XSPI_BASE + 0x110      # intr_status
        self.REG_CTRL_CONFIG = self.XSPI_BASE + 0x230      # ctrl_config (work_mode)
        self.REG_GLOBAL_SEQ_CFG = self.XSPI_BASE + 0x390
        self.REG_GLOBAL_SEQ_CFG_1 = self.XSPI_BASE + 0x394
        self.REG_DIRECT_ACCESS_CFG = self.XSPI_BASE + 0x398
        self.REG_DIRECT_ACCESS_RMP = self.XSPI_BASE + 0x39C
        self.REG_DIRECT_ACCESS_RMP_1 = self.XSPI_BASE + 0x3A0
        self.REG_PROG_SEQ_CFG_0 = self.XSPI_BASE + 0x420
        self.REG_PROG_SEQ_CFG_1 = self.XSPI_BASE + 0x424
        self.REG_PROG_SEQ_CFG_2 = self.XSPI_BASE + 0x428
        self.REG_READ_SEQ_CFG_0 = self.XSPI_BASE + 0x430
        self.REG_READ_SEQ_CFG_1 = self.XSPI_BASE + 0x434
        self.REG_READ_SEQ_CFG_2 = self.XSPI_BASE + 0x438
        self.REG_STAT_SEQ_CFG_0 = self.XSPI_BASE + 0x450
        self.REG_STAT_SEQ_CFG_1 = self.XSPI_BASE + 0x454
        self.REG_STAT_SEQ_CFG_2 = self.XSPI_BASE + 0x458
        self.REG_STAT_SEQ_CFG_3 = self.XSPI_BASE + 0x45C
        self.REG_STAT_SEQ_CFG_5 = self.XSPI_BASE + 0x464
        self.REG_STAT_SEQ_CFG_7 = self.XSPI_BASE + 0x46C
        self.REG_STAT_SEQ_CFG_8 = self.XSPI_BASE + 0x470
        # Controller +0x1000 window
        self.REG_DLL_PHY_CTRL = self.XSPI_BASE + 0x1034
        self.REG_WP_SETTINGS = self.XSPI_BASE + 0x1000
        # PHY (+0x2000 window)
        self.XSPI_PHY_BASE = self.XSPI_BASE + 0x2000
        self.REG_PHY_DQ_TIMING = self.XSPI_PHY_BASE + 0x000
        self.REG_PHY_DQS_TIMING = self.XSPI_PHY_BASE + 0x004
        self.REG_PHY_GATE_LPBK_CTRL = self.XSPI_PHY_BASE + 0x008
        self.REG_PHY_DLL_MASTER_CTRL = self.XSPI_PHY_BASE + 0x00C
        self.REG_PHY_DLL_SLAVE_CTRL = self.XSPI_PHY_BASE + 0x010
        self.REG_PHY_DLL_MISC = self.XSPI_PHY_BASE + 0x080

    def _enter_stig(self) -> None:
        # ctrl_config.work_mode = 1 (STIG)
        self.ocd.mww(self.REG_CTRL_CONFIG, 0x20)

    def _enter_direct(self) -> None:
        # ctrl_config.work_mode = 0 (DIRECT)
        self.ocd.mww(self.REG_CTRL_CONFIG, 0x00)

    def _wait_cmd_idle(self, timeout_s: float = 0.1) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            cs = self.ocd.mdw(self.REG_CTRL_STATUS, 1)
            if (cs & 0xffff) == 0:
                return True
            time.sleep(0.001)
        return False

    def _intr_clear_all(self) -> None:
        # Clear all interrupt/status sticky bits (w1c)
        self.ocd.mww(self.REG_INTR_STATUS, 0xFFFFFFFF)

    def _stig_read_status_byte(self, opcode: int) -> int:
        self._enter_stig()
        self._intr_clear_all()

        # opcode-only command
        # cmd: opcode only, 0 addr/data
        self.ocd.mww(self.REG_CMD4, 0x00000000)
        self.ocd.mww(self.REG_CMD3, (opcode & 0xFF) << 16)
        self.ocd.mww(self.REG_CMD2, 0x00000000)
        self.ocd.mww(self.REG_CMD1, 0x00000001)  # phase count = 1
        self.ocd.mww(self.REG_CMD0, 0x00000000)

        # glue for 1-byte in
        self.ocd.mww(self.REG_CMD4, 0x00000000)
        self.ocd.mww(self.REG_CMD3, 0x00000000)
        self.ocd.mww(self.REG_CMD2, 0x00010000)  # 1 byte data in
        self.ocd.mww(self.REG_CMD1, 0x0100007F)  # issue read
        self.ocd.mww(self.REG_CMD0, 0x00000000)

        if not self._wait_cmd_idle(0.1):
            raise TimeoutError("Timeout waiting for STIG read status command to complete.")
        cmd_status = self.ocd.mdw(self.REG_CMD_STATUS)
        return (cmd_status >> 16) & 0xFF

    def read_sr1(self) -> int:
        return self._stig_read_status_byte(RDSR1_CMD)

    def read_sr2(self) -> int:
        return self._stig_read_status_byte(RDSR2_CMD)

    def write_enable(self) -> bool:
        self._enter_stig()
        self._intr_clear_all()

        self.ocd.mww(self.REG_CMD4, 0x00000000)
        self.ocd.mww(self.REG_CMD3, (WREN_CMD & 0xFF) << 16)
        self.ocd.mww(self.REG_CMD2, 0x00000000)
        self.ocd.mww(self.REG_CMD1, 0x00000000)
        self.ocd.mww(self.REG_CMD0, 0x00000000)

        if not self._wait_cmd_idle(0.1):
            raise TimeoutError("Timeout waiting for STIG write enable command to complete.")
        sr1 = self.read_sr1()
        return (sr1 & 0x2) != 0

    def _wrsr12(self, sr1: int, sr2: int) -> None:
        """
        Write Status Register-1 and -2 (command 0x01). Uses 2 data bytes: SR1 then SR2.
        Caller must ensure WEL is set beforehand.
        """
        self._enter_stig()
        self._intr_clear_all()

        # opcode-only, followed by 2 data bytes
        self.ocd.mww(self.REG_CMD4, (sr1 & 0xFF) << 24 | (sr2 & 0xFF) << 16)
        self.ocd.mww(self.REG_CMD3, (WRSR12_CMD & 0xFF) << 16)
        self.ocd.mww(self.REG_CMD2, 0x00000000)
        self.ocd.mww(self.REG_CMD1, 0x00020000)  # 2 bytes out
        self.ocd.mww(self.REG_CMD0, 0x00000000)

        if not self._wait_cmd_idle(0.1):
            raise TimeoutError("Timeout waiting for STIG WRSR command to complete.")

    def enable_QE_bit(self) -> bool:
        """
        Set QE (SR2 bit1) per GD25LE128E: RDSR1/RDSR2, WREN, WRSR1+2 with QE=1, poll WIP, verify.
        """
        sr1 = self.read_sr1()
        sr2 = self.read_sr2()
        if (sr2 & (1 << 1)):
            return True  # already set (QE is bit1 of SR2 per datasheet)

        if not self.write_enable():
            raise RuntimeError("WREN not set before QE WRSR.")

        sr2_new = sr2 | (1 << 1)  # set QE
        self._wrsr12(sr1, sr2_new)

        # Poll WIP until clear
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if (self.read_sr1() & 0x01) == 0:
                break
            time.sleep(0.01)
        else:
            raise TimeoutError("Timeout waiting for QE WRSR to complete.")

        return (self.read_sr2() & (1 << 1)) != 0

    def erase_block(self, flash_off: int, erase_cmd: int = ERASE_CMD_32K,
                    timeout_s: float = ERASE_TIMEOUT_S) -> bool:
        # Enter STIG and enable write
        self._enter_stig()
        if not self.write_enable():
            raise RuntimeError("WREN not set during erase block.")
        self._intr_clear_all()

        # 24-bit address -> cmd1 gets A[7:0] in bits [31:24]
        # cmd2 gets A[23:8] in bits [23:0]
        addr = flash_off & 0xFFFFFF
        cmd1 = ((addr & 0xFF) << 24)
        cmd2 = (addr >> 8) & 0xFFFFFF
        # opcode in cmd3[23:16], 3 address bytes in cmd3[31:28] = 3
        cmd3 = ((erase_cmd & 0xFF) << 16) | (0 << 24) | (3 << 28)
        cmd4 = 0x00000000

        self.ocd.mww(self.REG_CMD4, cmd4)
        self.ocd.mww(self.REG_CMD3, cmd3)
        self.ocd.mww(self.REG_CMD2, cmd2)
        self.ocd.mww(self.REG_CMD1, cmd1)
        self.ocd.mww(self.REG_CMD0, 0x00000000)

        if not self._wait_cmd_idle(0.1):
            raise TimeoutError("Timeout waiting for STIG erase command to take.")

        # Poll WIP (SR1 bit0) until clear
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            sr1 = self.read_sr1()
            if (sr1 & 0x01) == 0:
                return True
            time.sleep(0.01)
        return False

    def erase_all(self, timeout_s: float = 120.0) -> bool:
        # Issue chip erase (no address bytes)
        self._enter_stig()
        if not self.write_enable():
            raise RuntimeError("WREN not set during chip erase.")
        self._intr_clear_all()

        # opcode-only command
        self.ocd.mww(self.REG_CMD4, 0x00000000)
        self.ocd.mww(self.REG_CMD3, (ERASE_CMD_ALL & 0xFF) << 16)
        self.ocd.mww(self.REG_CMD2, 0x00000000)
        self.ocd.mww(self.REG_CMD1, 0x00000000)
        self.ocd.mww(self.REG_CMD0, 0x00000000)

        if not self._wait_cmd_idle(0.1):
            raise TimeoutError("Timeout waiting for STIG chip erase command to take.")

        # Poll WIP (SR1 bit0) until clear
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            sr1 = self.read_sr1()
            if (sr1 & 0x01) == 0:
                return True
            time.sleep(0.05)
        return False


    def xspic_clk_enable(self) -> None:
        # Enable XSPI_CFG clock, XSPI core clock (divider ctrl), and AXI clock
        val = self.ocd.mdw(0x50330704)                 # GLOBAL_CLK_ENABLE2
        self.ocd.mww(0x50330704, val | 0x01)           # XSPI CFG clock enable (bit0)

        val = self.ocd.mdw(0x50330730)                 # GLOBAL_XSPI_CORE_CLK_CTRL
        self.ocd.mww(0x50330730, val | 0x01)           # enable core clock

        val = self.ocd.mdw(0x50330700)                 # GLOBAL_CLK_ENABLE1
        self.ocd.mww(0x50330700, val | 0x80)           # AXI clock enable (bit7)

    def xspic_clk_disable(self) -> None:
        #CFG_CLK
        val = self.ocd.mdw(0x50330704)                 # GLOBAL_CLK_ENABLE2
        self.ocd.mww(0x50330704, val & ~0x01)           # XSPI CFG clock disable (bit0)

        val = self.ocd.mdw(0x50330730)                 # GLOBAL_XSPI_CORE_CLK_CTRL
        self.ocd.mww(0x50330730, val & ~0x01)           # disable core clock

        val = self.ocd.mdw(0x50330700)                 # GLOBAL_CLK_ENABLE1
        self.ocd.mww(0x50330700, val & ~0x80)           # AXI clock disable (bit7)

    def xspic_reset(self):
        self.xspic_clk_disable()
        self.ocd.mww(0x50330680, 0x20)			# GLOBAL_PERIF_RST_OFFSET
        time.sleep(0.5)							#give time for rest to take
        self.xspic_clk_enable()
        self.ocd.mww(0x50330680, 0x0)			# GLOBAL_PERIF_RST_OFFSET
        time.sleep(0.5)							#give time for reset to release

    def direct_prog_cfg(self) -> None:
        # Program sequence / status sequence setup
        # Configure XSPI controller
        self.ocd.mww(self.REG_PROG_SEQ_CFG_0, 0x3002)    # quad write enable + addr cnt fields
        self.ocd.mww(self.REG_PROG_SEQ_CFG_1, 0x0)       # no extended cmd
        self.ocd.mww(self.REG_PROG_SEQ_CFG_2, 0x0)       # default latency/mask

        self.ocd.mww(self.REG_STAT_SEQ_CFG_0, 0x0)       # status seq phase1 cfg
        self.ocd.mww(self.REG_STAT_SEQ_CFG_1, 0x0)       # status seq dummy/addr
        self.ocd.mww(self.REG_STAT_SEQ_CFG_2, 0x05000005)# status cmd values (dev_rdy/prog_fail)
        self.ocd.mww(self.REG_STAT_SEQ_CFG_3, 0x0)       # status cmd ext values
        self.ocd.mww(self.REG_STAT_SEQ_CFG_5, 0x40)      # dev_rdy enable/index
        self.ocd.mww(self.REG_STAT_SEQ_CFG_7, 0x0)       # dev_rdy address
        self.ocd.mww(self.REG_STAT_SEQ_CFG_8, 0x0)       # prog_fail address

    def direct_read_cfg(self) -> None:
        self.ocd.mww(self.REG_READ_SEQ_CFG_0, 0x062230EB)  # read opcode/addr/dummy/edge config
        self.ocd.mww(self.REG_READ_SEQ_CFG_1, 0x0)         # no mode-bits, no ext cmd
        self.ocd.mww(self.REG_READ_SEQ_CFG_2, 0x0)         # latency cfg

    def direct_remap_addr(self) -> None:
        self.ocd.mww(self.REG_GLOBAL_SEQ_CFG, 0x8F)         # direct mode config (profile, endianness)
        self.ocd.mww(self.REG_GLOBAL_SEQ_CFG_1, 0x0)        # profile-specific fields default
        self.ocd.mww(self.REG_DIRECT_ACCESS_CFG, 0x1000)    # set XIP/AHB window size
        self.ocd.mww(self.REG_DIRECT_ACCESS_RMP, XIP_BASE)  # remap base addr
        self.ocd.mww(self.REG_DIRECT_ACCESS_RMP_1, 0x0)     # remap upper bits

# ----------------------- DMA controller -----------------------

class DmaController:
    """
    Manages DMA0 setup and transfers into the XSPI direct window.
    """
    def __init__(self, ocd: Ocd, xip_base: int = XIP_BASE) -> None:
        self.ocd = ocd
        self.xip_base = xip_base

        self.REG_CH_CMD = 0x50323000
        self.REG_CH_INTREN = 0x50323008
        self.REG_CH_CTRL = 0x5032300C
        self.REG_CH_SRCADDR = 0x50323010
        self.REG_CH_DESADDR = 0x50323018
        self.REG_CH_XSIZE = 0x50323020
        self.REG_CH_XSIZEHI = 0x50323024
        self.REG_CH_SRCTRANSCFG = 0x50323028
        self.REG_CH_DESTRANSCFG = 0x5032302C
        self.REG_CH_XADDRINC = 0x50323030

        self.REG_CLK_ENABLE1 = 0x50330700
        self.REG_TOP_STICKY_RST = 0x50330658
        self.REG_TOP_RST = 0x50330640
        self.REG_DMA_TRIGINSEC0 = 0x50322008
        self.REG_DMA_TRIG_EN = 0x50302054

    def init(self) -> None:
        # DMA0 clock enable
        val = self.ocd.mdw(self.REG_CLK_ENABLE1)
        self.ocd.mww(self.REG_CLK_ENABLE1, val | (1 << 4))

        # TOP sticky reset deassert for DMA0
        val = self.ocd.mdw(self.REG_TOP_STICKY_RST)
        self.ocd.mww(self.REG_TOP_STICKY_RST, val | (1 << 2))

        # Toggle DMA0 reset
        val = self.ocd.mdw(self.REG_TOP_RST)
        self.ocd.mww(self.REG_TOP_RST, val | (1 << 0))
        val = self.ocd.mdw(self.REG_TOP_RST)
        self.ocd.mww(self.REG_TOP_RST, val & ~(1 << 0))

        # Only allow secure world triggers;
        self.ocd.mww(self.REG_DMA_TRIGINSEC0, 0x0)
        self.ocd.mww(self.REG_DMA_TRIG_EN, 0xFFFFFFFF)   # Enable all triggers

    def channel_config(self, flash_off: int, size: int, src_addr: int = SRAM_BUF) -> None:
        flash_addr = self.xip_base + flash_off
        transfer_units = (size // 4) & 0xFFFFFFFF  # count in words

        # Split the transfer length across XSIZE/XSIZEHI (src/dst packed)
        srcxsize_low = transfer_units & 0xFFFF
        srcxsize_high = (transfer_units >> 16) & 0xFFFF
        desxsize_low = srcxsize_low
        desxsize_high = srcxsize_high

        xsize = (desxsize_low << 16) | srcxsize_low
        xsizehi = (desxsize_high << 16) | srcxsize_high

        self.ocd.mww(self.REG_CH_SRCTRANSCFG, 0x000F4822)    # src: burst=16, priv, secure, normal WT transient
        self.ocd.mww(self.REG_CH_SRCADDR, src_addr)          # src base (SRAM buffer)
        self.ocd.mww(self.REG_CH_DESTRANSCFG, 0x000F4877)    # dest: burst=16, priv, non-secure, normal attrs
        self.ocd.mww(self.REG_CH_DESADDR, flash_addr)        # dest base (XSPI direct window)
        self.ocd.mww(self.REG_CH_XSIZE, xsize)               # xfer count low (src/dst)
        self.ocd.mww(self.REG_CH_XSIZEHI, xsizehi)           # xfer count high (src/dst)
        self.ocd.mww(self.REG_CH_CTRL, 0x00200202)           # 1D, DONE end-of-cmd, word TRANSIZE
        self.ocd.mww(self.REG_CH_XADDRINC, 0x00010001)       # increment src/dst per beat (1 word)

    def channel_start(self) -> None:
        self.ocd.mww(self.REG_CH_INTREN, 0x00000003)
        self.ocd.mww(self.REG_CH_CMD, 0x00000001)
        #ensure the start is latched
        for _ in range(10):
            if self.ocd.mdw(self.REG_CH_CMD) == 0x00000001:
                break
            time.sleep(0.001)

    def wait_done(self, timeout_s: float = 5.0) -> bool:
        # Poll DMA0 CH_CMD until 0 (idle)
        deadline = time.monotonic() + timeout_s
        last_cmd = None
        while time.monotonic() < deadline:
            try:
                val = self.ocd.mdw(self.REG_CH_CMD)
                last_cmd = val
            except Exception:
                time.sleep(0.005)
                continue
            if val == 0:
                return True
            time.sleep(0.002)
        logging.debug("DMA wait timeout; last CH_CMD=0x%08X", last_cmd or 0)
        return False

# ----------------------- Flash programmer -----------------------

class FlashProgrammer:
    def __init__(self, ocd: Ocd) -> None:
        self.ocd = ocd
        self.xspi = XspiController(ocd)
        self.dma = DmaController(ocd)

    def bringup(self) -> None:

        # XSPI clocks and IO/PHY init (mirrors sr110 script)
        self.xspi.xspic_clk_enable()

        # Optionally set CORE_CLK divider explicitly (sr110 sets 0x35)
        self.ocd.mww(0x50330730, 0x35)

        # IO pads for XSPI lanes + clock + CS#
        for off in [0x5033885C,0x50338860,0x50338864,0x50338868,0x5033886C,0x50338870,0x50338874,0x50338878,
                    0x50338880,0x50338884]:
            self.ocd.mww(off, 0x1B)
        self.ocd.mww(0x50338888, 0x30)  # CS
        # XSPI timing/PHY defaults (global_cfg block @0x50330000)
        global_cfg_base = 0x50330000
        self.ocd.mww(global_cfg_base + 0x0A6C, 0xA)        # PERIF_XSPI_RB_VALID_TIME: sysclk cycles until device ready
        self.ocd.mww(global_cfg_base + 0x0A5C, 0x2)        # PERIF_XSPI_CTRL0: controller cfg (profile/reset opts)
        self.ocd.mww(global_cfg_base + 0x0A68, 0x498EB)    # PERIF_XSPI_CTRL3: read seq cmd/ios/edges
        self.ocd.mww(global_cfg_base + 0x0A64, 0x30E)      # PERIF_XSPI_CTRL2: addr/dummy settings
        self.ocd.mww(global_cfg_base + 0x0A70, 0x101)      # PERIF_XSPI_PHY_DQ_TIMING
        self.ocd.mww(global_cfg_base + 0x0A74, 0x700404)   # PERIF_XSPI_PHY_DQS_TIMING
        self.ocd.mww(global_cfg_base + 0x0A78, 0x200030)   # PERIF_XSPI_PHY_GATE_LPBK_CTRL
        self.ocd.mww(global_cfg_base + 0x0A7C, 0x800000)   # PERIF_XSPI_PHY_DLL_MASTER_CTRL
        self.ocd.mww(global_cfg_base + 0x0A80, 0x00007801) # PERIF_XSPI_PHY_DLL_SLAVE_CTRL

        self.xspi.xspic_reset()
        time.sleep(0.5)

        # PHY DLL bring-up: program PHY window (+0x2000) and lock DLL via dll_phy_ctrl (+0x1000)
        self.ocd.mww(global_cfg_base + 0x0A60, 0x2)        # PERIF_XSPI_CTRL1: PHY enable bits (SR110 recipe)
        self.ocd.mww(self.xspi.REG_DLL_PHY_CTRL, 0x0030707)     # dll_phy_ctrl: clear master DLL reset / prep update
        self.ocd.mww(self.xspi.REG_PHY_DQ_TIMING, 0x101)        # PHY_DQ_TIMING (live PHY window)
        self.ocd.mww(self.xspi.REG_PHY_DQS_TIMING, 0x700404)    # PHY_DQS_TIMING (live PHY window)
        self.ocd.mww(self.xspi.REG_PHY_GATE_LPBK_CTRL, 0x200030)# PHY_GATE_LPBK_CTRL (live PHY window)
        self.ocd.mww(self.xspi.REG_PHY_DLL_MASTER_CTRL, 0x800000)# PHY_DLL_MASTER_CTRL (live PHY window)
        self.ocd.mww(self.xspi.REG_PHY_DLL_SLAVE_CTRL, 0x3300)  # PHY_DLL_SLAVE_CTRL (live PHY window)
        self.ocd.mww(self.xspi.REG_PHY_DLL_MISC, 0x4000)        # dll status/control (per recipe)
        self.ocd.mww(self.xspi.REG_DLL_PHY_CTRL, 0x00000707)    # dll_phy_ctrl: release reset
        self.ocd.mww(self.xspi.REG_DLL_PHY_CTRL, 0x001030707)   # dll_phy_ctrl: lock/enable

        self.ocd.mww(self.xspi.REG_CTRL_CONFIG, 0x20)           # controller cfg (per recipe)
        self.ocd.mww(self.xspi.REG_WP_SETTINGS, 0x01)           # wp_settings: drive WP# high (per recipe)

        if not self.xspi.write_enable():
            raise RuntimeError("WREN not set during configuraiton.")
        if not self.xspi.enable_QE_bit():
            raise RuntimeError("QE bit not set during configuraiton.")

        # Configure direct access windows
        self.xspi.direct_remap_addr()
        self.xspi.direct_read_cfg()
        self.xspi.direct_prog_cfg()

        time.sleep(0.5)

        # DMA init
        self.dma.init()

    def _load_chunk_into_sram(self, path: Path, file_off: int, size: int, sram_addr: int) -> None:
        ok = self.ocd.load_image_chunk(path, sram_addr, file_off, size)
        if not ok:
            raise RuntimeError("load_image failed; no slow SRAM load fallback available.")

    def _program_chunk_via_dma(self, flash_off: int, size: int, sram_addr: int) -> None:
        # Configure + start DMA
        self.dma.channel_config(flash_off, size, sram_addr)
        self.dma.channel_start()

    def erase_range(self, flash_off: int, total: int) -> None:
        """
        Erase using a stepped strategy:
        - 4 KiB sectors until 32 KiB aligned.
        - One 32 KiB block if needed to reach 64 KiB alignment.
        - As many 64 KiB blocks as possible.
        - Tail with 32 KiB if needed, then 4 KiB for the remainder.
        """
        off = flash_off
        end = flash_off + total

        def erase_chunk(addr: int, size: int, cmd: int) -> None:
            logging.info("[erase] %s bytes @ %s using cmd 0x%02X", hex32(size), hex32(addr), cmd)
            if not self.xspi.erase_block(addr, cmd, timeout_s=ERASE_TIMEOUT_S):
                raise RuntimeError(f"Erase timeout at {hex32(addr)}")

        # 4 KiB until 32 KiB aligned
        while off < end and (off % ERASE_32K_SIZE != 0):
            erase_chunk(off, ERASE_4K_SIZE, ERASE_CMD_4K)
            off += ERASE_4K_SIZE

        # If not 64 KiB aligned and at least 32 KiB remains, do one 32 KiB to reach 64 KiB boundary
        if off < end and (off % ERASE_64K_SIZE != 0) and (end - off) >= ERASE_32K_SIZE:
            erase_chunk(off, ERASE_32K_SIZE, ERASE_CMD_32K)
            off += ERASE_32K_SIZE

        # Use as many 64 KiB blocks as possible
        while off < end and (end - off) >= (ERASE_64K_SIZE):
            erase_chunk(off, ERASE_64K_SIZE, ERASE_CMD_64K)
            off += ERASE_64K_SIZE

        # If at least 32 KiB remains, use one 32 KiB block
        if off < end and (end - off) >= ERASE_32K_SIZE:
            erase_chunk(off, ERASE_32K_SIZE, ERASE_CMD_32K)
            off += ERASE_32K_SIZE

        # Finish the tail with 4 KiB sectors
        while off < end:
            chunk = min(ERASE_4K_SIZE, end - off)
            erase_chunk(off, chunk, ERASE_CMD_4K)
            off += chunk

    def erase_all(self) -> None:
        logging.info("Erasing entire flash via chip-erase opcode...")
        if not self.xspi.erase_all():
            raise RuntimeError("Chip erase timed out.")

    def program_file(self, path: Path, flash_off: int, file_off: int = 0, pre_erased: bool = False) -> None:
        path = str(Path(path)).replace("\\", "/")
        size = os.stat(path).st_size - file_off
        if size <= 0:
            raise ValueError("Image size is zero or file_off beyond EOF.")
        if flash_off % (4 *1024) != 0:
            logging.warning("Flash offset %s is not 4 KiB aligned; 4 KiB erases will start at %s and may affect preceding data.",
                            hex32(flash_off), hex32(flash_off - (flash_off % (4 *1024))))
        if flash_off & 0x3:
            raise ValueError(f"DMA requires 4-byte aligned flash offset; got {hex32(flash_off)}")

        cleanup_path: Optional[Path] = None
        if size & 0x3:
            pad = 4 - (size & 0x3)
            logging.warning("Size %s not word-aligned; padding %d byte(s) with 0xFF for DMA.", hex32(size), pad)
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                with open(path, "rb") as f:
                    f.seek(file_off)
                    tmp.write(f.read())
                tmp.write(b"\xFF" * pad)
                cleanup_path = Path(tmp.name)
            path = cleanup_path
            file_off = 0
            size += pad
        logging.info("Programming %s bytes from %s (file_off=%s) to flash @ %s",
                     size, path, hex32(file_off), hex32(flash_off))

        if not pre_erased:
            self.erase_range(flash_off, size)

        self.xspi._enter_direct()

        chunks = ceil_div(size, CHUNK_SIZE)
        buffers = [SRAM_BUF, SRAM_BUF_ALT]
        buf_idx = 0
        processed = 0
        chunk_id = 1
        remaining = size
        next_file_off = file_off

        # Preload the first chunk into SRAM so the DMA engine can immediately run.
        cur_size = min(CHUNK_SIZE, remaining)
        cur_file_off = next_file_off
        self._load_chunk_into_sram(path, cur_file_off, cur_size, buffers[buf_idx])
        next_file_off += cur_size
        remaining -= cur_size

        while cur_size > 0:
            cur_flash = flash_off + processed
            pct = int(((processed + cur_size) * 100) / size)
            logging.info("[write %d/%d] file_off=%s -> flash=%s size=%s (%d%%)",
                         chunk_id, chunks, hex32(cur_file_off), hex32(XIP_BASE + cur_flash),
                         hex32(cur_size), pct)

            if not self.xspi._wait_cmd_idle(0.1):
                raise TimeoutError("Timeout waiting for XSPI controller to go idle before program.")

            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                sr1 = self.xspi.read_sr1()
                if (sr1 & 0x01) == 0:
                    break
                time.sleep(0.01)
            else:
                raise TimeoutError("Timeout waiting for flash ready (WIP clear) before program.")

            if not self.xspi.write_enable():
                raise RuntimeError("WREN did not latch before program.")

            self.xspi._enter_direct()
            self._program_chunk_via_dma(cur_flash, cur_size, buffers[buf_idx])

            # Prime the next buffer while the DMA engine pushes the current chunk.
            next_buf = 1 - buf_idx
            next_size = 0
            next_chunk_file_off = next_file_off
            if remaining > 0:
                next_size = min(CHUNK_SIZE, remaining)
                next_chunk_file_off = next_file_off
                self._load_chunk_into_sram(path, next_chunk_file_off, next_size, buffers[next_buf])
                remaining -= next_size
                next_file_off += next_size
            #else:
             #   time.sleep(0.1)

            if not self.dma.wait_done(timeout_s=PROGRAM_TIMEOUT_S):
                raise TimeoutError("Timeout waiting for DMA completion.")

            processed += cur_size
            chunk_id += 1

            if processed >= size:
                break

            buf_idx = next_buf
            cur_size = next_size
            cur_file_off = next_chunk_file_off

        #time.sleep(0.1)
        # Ensure controller and flash are idle before verify
        if not self.xspi._wait_cmd_idle(0.1):
            raise TimeoutError("Timeout waiting for XSPI controller idle after programming.")
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if (self.xspi.read_sr1() & 0x01) == 0:
                break
            time.sleep(0.01)
        else:
            raise TimeoutError("Timeout waiting for flash ready (WIP clear) after programming.")
        # read_sr1/_stig_read_status leaves the controller in STIG mode; switch back to DIRECT for verify
        self.xspi._enter_direct()

        logging.info("Programming done. Verifying...")
        self.ocd.halt(100)
        base = XIP_BASE + flash_off
        logging.info("verify %s, at %s, offset of %s",
                         path, hex(base), hex(file_off))
        verify_path = path
        if file_off:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                with open(path, "rb") as f:
                    f.seek(file_off)
                    tmp.write(f.read())
                verify_path = str(Path(tmp.name)).replace("\\", "/")
        try:
            if not self.ocd.verify_image(verify_path, base):
                raise RuntimeError("verify_image failed; contents mismatch.")
            logging.info("Verify OK.")
        finally:
            if verify_path != path:
                with contextlib.suppress(Exception):
                    os.remove(verify_path)
            if cleanup_path and cleanup_path != path:
                with contextlib.suppress(Exception):
                    os.remove(cleanup_path)

# ----------------------- CLI -----------------------

def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Program external XSPI flash via OpenOCD (TCL RPC).")
    p.add_argument("--openocd", default="openocd", help="Path to openocd executable.")
    p.add_argument("--cfg_path", required=True, type=Path, help="OpenOCD config (.cfg).")
    p.add_argument("--image", required=False, type=Path, help="Binary image to program/verify.")
    p.add_argument("--flash-offset", default="0x0", help="Flash offset (e.g., 0x0).")
    p.add_argument("--file-offset", default="0x0", help="File offset into --image (default 0).")
    p.add_argument("--tcl_port", type=int, default=DEFAULT_TCL_PORT, help="OpenOCD TCL port (default 6666).")
    p.add_argument("--tcl_host", default="127.0.0.1", help="OpenOCD TCL host (default 127.0.0.1).")
    p.add_argument("--probe", default="cmsis-dap", help="Adapter driver, e.g. cmsis-dap or jlink (passed as PROBE env).")
    p.add_argument("--erase-all", action="store_true", default=False, help="Erase entire flash before programming (chip erase opcode).")
    p.add_argument("--erase-only", action="store_true", default=False, help="Erase entire flash and exit (implies --erase-all).")
    p.add_argument("--verify-only", action="store_true", default=False, help="Only verify flash contents against image (uses offsets).")
    p.add_argument("--log-level", default="INFO", help="Logging level (DEBUG/INFO/WARN/ERROR).")
    return p.parse_args(argv)

def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(levelname)s: %(message)s")

    if not args.cfg_path.exists():
        logging.error("Config not found: %s", args.cfg_path)
        return 2
    if not args.erase_only and not args.image:
        logging.error("--image is required unless using --erase-only.")
        return 2
    if args.image and not args.image.exists():
        logging.error("Image not found: %s", args.image)
        return 2

    try:
        flash_off = int(args.flash_offset, 0)
        file_off  = int(args.file_offset, 0)
    except ValueError:
        logging.error("Invalid --flash-offset or --file-offset (use integers like 0x1000).")
        return 2

    server = OpenOcdServer(OpenOcdServerConfig(
        openocd=args.openocd,
        cfg_path=args.cfg_path,
        host=args.tcl_host,
        tcl_port=args.tcl_port,
        probe=args.probe
    ))

    client = TclRpcClient(host=args.tcl_host, port=args.tcl_port, timeout_s=CMD_TIMEOUT_S)
    ocd = Ocd(client)

    try:
        server.start()

        client.connect()
        logging.info("Connected to OpenOCD: %s", ocd.version().splitlines()[0])

        #initalize SR110
        sr110 = SR110(ocd)
        sr110.init_rwtc_cfg_0p9()

        # Then XSPI/DMA bring-up and program
        prog = FlashProgrammer(ocd)
        prog.bringup()

        pre_erased = False
        if args.erase_only:
            prog.erase_all()
            logging.info("Erase-only requested; exiting after chip erase.")
            return 0

        if args.erase_all:
            prog.erase_all()
            pre_erased = True

        if args.verify_only:
            prog.ocd.halt(100)
            base = XIP_BASE + flash_off
            prog.xspi._enter_direct()
            verify_size = os.stat(args.image).st_size - file_off
            logging.info("Verify-only: %s at %s (file_off=%s size=%s)", args.image, hex(base), hex(file_off), hex(verify_size))
            verify_path = args.image
            if file_off:
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    with open(args.image, "rb") as f:
                        f.seek(file_off)
                        tmp.write(f.read())
                    verify_path = Path(tmp.name)
            try:
                if not prog.ocd.verify_image(verify_path, base):
                    raise RuntimeError("verify_image failed; contents mismatch.")
                logging.info("Verify OK.")
            finally:
                if verify_path != args.image:
                    with contextlib.suppress(Exception):
                        os.remove(verify_path)
            return 0

        prog.program_file(args.image, flash_off, file_off, pre_erased=pre_erased)

        logging.info("All done.")
        return 0
    except KeyboardInterrupt:
        logging.error("Interrupted by user.")
        return 130
    except Exception as e:
        logging.error("FAIL: %s", e)
        return 1
    finally:
        client.close()
        server.stop()

if __name__ == "__main__":
    sys.exit(main())
