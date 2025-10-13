# test_helpers.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge

CLK_NS = 10

REG_CONTROL = 0x00
REG_STATUS  = 0x04
REG_REF_LEN = 0x08
REG_VERSION = 0x0C
REG_KEY     = 0x10

CR_RESET = 0
CR_RS    = 1
CR_MODE  = 2   # 1 = LOAD_QUERY, 0 = NORMAL (stream reference)

def start_dut(dut):
  cocotb.start_soon(Clock(dut.clk, CLK_NS, units="ns").start())
  async def _mirror():
    dut.axis_clk.value = dut.clk.value
    while True:
      await RisingEdge(dut.clk)
      dut.axis_clk.value = 1
      await FallingEdge(dut.clk)
      dut.axis_clk.value = 0
  cocotb.start_soon(_mirror())

async def reset_dut(dut):
  dut.rst.value = 0
  dut.axis_rst.value = 0
  for _ in range(5):
    await RisingEdge(dut.clk)
  dut.rst.value = 1
  dut.axis_rst.value = 1
  for _ in range(5):
    await RisingEdge(dut.clk)

async def reset_core(axil):
  rd = await axil.read(REG_CONTROL, 4)
  ctrl = int.from_bytes(rd.data, "little")
  await axil.write(REG_CONTROL, (ctrl |  (1 << CR_RESET)).to_bytes(4, "little"))
  await axil.write(REG_CONTROL, (ctrl & ~(1 << CR_RESET)).to_bytes(4, "little"))

async def reset_axis(dut):
  dut.axis_rst.setimmediatevalue(1)
  for _ in range(2):
    await RisingEdge(dut.axis_clk)
  dut.axis_rst.value = 0
  for _ in range(2):
    await RisingEdge(dut.axis_clk)
  dut.axis_rst.value = 1
  for _ in range(2):
    await RisingEdge(dut.axis_clk)

async def wait_state(axil, dut, state=0):
  for _ in range(100000):
    rd = await axil.read(REG_STATUS, 4)
    s = int.from_bytes(rd.data, "little")
    if ((s >> 6) & 7) == state:
      return
    await RisingEdge(dut.clk)
  raise AssertionError(f"timeout waiting for state={state}")

async def enter_query_load_mode(axil):
  rd = await axil.read(REG_CONTROL, 4)
  ctrl = int.from_bytes(rd.data, "little")
  ctrl |=  (1 << CR_MODE)
  ctrl |=  (1 << CR_RS)
  await axil.write(REG_CONTROL, ctrl.to_bytes(4, "little"))

def pack_words(words):
  return bytearray().join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in words)
