# test_helpers.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

CLK_NS = 10

REG_CONTROL      = 0x00
REG_STATUS       = 0x04
REG_VERSION      = 0x08
REG_KEY          = 0x0C
REG_QID          = 0x14
REG_COUNT        = 0x18
REG_IDX          = 0x1C
REG_SCORE        = 0x20

CR_RST  = 0

def start_dut(dut):
  cocotb.start_soon(Clock(dut.clk, CLK_NS, units="ns").start())

async def reset_dut(dut):
  dut.rst.value = 0
  for _ in range(5):
    await RisingEdge(dut.clk)
  dut.rst.value = 1
  for _ in range(5):
    await RisingEdge(dut.clk)

async def reset_core(axil, dut):
  rd = await axil.read(REG_CONTROL, 4)
  ctrl = int.from_bytes(rd.data, "little")
  await axil.write(REG_CONTROL, (ctrl |  (1 << CR_RST)).to_bytes(4, "little"))
  await axil.write(REG_CONTROL, (ctrl & ~(1 << CR_RST)).to_bytes(4, "little"))

def pack_words(words):
  return bytearray().join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in words)
