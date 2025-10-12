# dtw_regs.py
import cocotb
from cocotb.triggers import RisingEdge
from cocotbext.axi import AxiLiteBus, AxiLiteMaster
from test_helpers import start_dut, reset_dut

REG_CONTROL = 0x00
REG_STATUS  = 0x04
REG_REF_LEN = 0x08
REG_VERSION = 0x0C
REG_KEY     = 0x10

@cocotb.test()
async def test_read_version(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk, reset=None)
  await reset_dut(dut)
  rd = await axil.read(REG_VERSION, 4)
  assert int.from_bytes(rd.data, "little") == 0x10000000

@cocotb.test()
async def test_read_key(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk, reset=None)
  await reset_dut(dut)
  rd = await axil.read(REG_KEY, 4)
  assert int.from_bytes(rd.data, "little") == 0x0CA7CAFE

@cocotb.test()
async def test_write_read_control(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk, reset=None)
  await reset_dut(dut)

  patterns = [0x0, 0x1, 0x2, 0x4, 0x7, 0xA5A55A5A]
  for val in patterns:
    await axil.write(REG_CONTROL, val.to_bytes(4, "little"))
    await RisingEdge(dut.clk)
    rd = await axil.read(REG_CONTROL, 4)
    rb = int.from_bytes(rd.data, "little")
    assert rb == val
    rc  = dut.dut.r_control.value.integer
    rst = dut.dut.w_dtw_core_rst.value.integer
    rs  = dut.dut.w_dtw_core_rs.value.integer
    md  = dut.dut.w_dtw_core_mode.value.integer
    assert rc == val
    assert rst == ((val >> 0) & 1)
    assert rs  == ((val >> 1) & 1)
    assert md  == ((val >> 2) & 1)
