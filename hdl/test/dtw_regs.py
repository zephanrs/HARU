"""
Cocotb tests for dtw_accel CSR (AXI-Lite)
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotbext.axi import AxiLiteBus, AxiLiteMaster

CLK_NS = 10

REG_CONTROL = 0x00
REG_STATUS  = 0x04
REG_REF_LEN = 0x08
REG_VERSION = 0x0C
REG_KEY     = 0x10

def start_clocks(dut):
  cocotb.start_soon(Clock(dut.clk,      CLK_NS, units="ns").start())
  cocotb.start_soon(Clock(dut.axis_clk, CLK_NS, units="ns").start())

async def reset(dut):
  dut.rst.value = 1
  dut.axis_rst.value = 1
  for _ in range(5):
    await RisingEdge(dut.clk)
  dut.rst.value = 0
  dut.axis_rst.value = 0
  for _ in range(5):
    await RisingEdge(dut.clk)

@cocotb.test()
async def test_read_version(dut):
  dut._log.info("test_read_version")
  start_clocks(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk, dut.rst)
  await reset(dut)

  rd = await axil.read(REG_VERSION, 4)
  version = int.from_bytes(rd.data, "little")
  dut._log.info(f"VERSION = 0x{version:08X}")
  assert version == 0x10000000

@cocotb.test()
async def test_read_key(dut):
  dut._log.info("test_read_key")
  start_clocks(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk, dut.rst)
  await reset(dut)

  rd = await axil.read(REG_KEY, 4)
  key = int.from_bytes(rd.data, "little")
  dut._log.info(f"KEY = 0x{key:08X}")
  assert key == 0x0CA7CAFE

@cocotb.test()
async def test_write_read_control(dut):
  dut._log.info("test_write_read_control")
  start_clocks(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk, dut.rst)
  await reset(dut)

  patterns = [
    0x00000000,
    0x00000001,
    0x00000002,
    0x00000004,
    0x00000007,
    0xA5A55A5A,
  ]

  for val in patterns:
    # write
    await axil.write(REG_CONTROL, val.to_bytes(4, "little"))
    await RisingEdge(dut.clk)

    # read back
    rd = await axil.read(REG_CONTROL, 4)
    rb = int.from_bytes(rd.data, "little")
    assert rb == val, f"CONTROL readback mismatch: wrote 0x{val:08X}, read 0x{rb:08X}"

    # peek internal reg and decoded control bits
    rc  = dut.dut.r_control.value.integer
    rst = dut.dut.w_dtw_core_rst.value.integer
    rs  = dut.dut.w_dtw_core_rs.value.integer
    md  = dut.dut.w_dtw_core_mode.value.integer

    assert rc == val, f"r_control mismatch: expected 0x{val:08X}, got 0x{rc:08X}"
    assert rst == ((val >> 0) & 1), f"rst bit mismatch for 0x{val:08X}"
    assert rs  == ((val >> 1) & 1), f"rs bit mismatch for 0x{val:08X}"
    assert md  == ((val >> 2) & 1), f"mode bit mismatch for 0x{val:08X}"
