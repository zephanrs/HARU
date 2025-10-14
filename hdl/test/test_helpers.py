# test_helpers.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge

CLK_NS = 10

REG_CONTROL      = 0x00
REG_STATUS       = 0x04
REG_REF_LEN      = 0x08
REG_VERSION      = 0x0C
REG_KEY          = 0x10
REG_REF_ADDR     = 0x14
REG_REF_DIN      = 0x18
REG_REF_DOUT     = 0x1C
REG_CYCLE_CNT    = 0x20
REG_CORE_REF_ADDR= 0x24
REG_NQUERY       = 0x28
REG_CURR_QID     = 0x2C
REG_QID          = 0x30
REG_COUNT        = 0x34
REG_IDX          = 0x38
REG_SCORE        = 0x3c

CR_RESET = 0
CR_RS    = 1
CR_MODE  = 2   # 1 = LOAD_QUERY, 0 = NORMAL (stream reference)

def start_dut(dut):
  cocotb.start_soon(Clock(dut.clk, CLK_NS, units="ns").start())

async def reset_dut(dut):
  dut.rst.value = 0
  for _ in range(5):
    await RisingEdge(dut.clk)
  dut.rst.value = 1
  for _ in range(5):
    await RisingEdge(dut.clk)

async def reset_core(axil):
  rd = await axil.read(REG_CONTROL, 4)
  ctrl = int.from_bytes(rd.data, "little")
  await axil.write(REG_CONTROL, (ctrl |  (1 << CR_RESET)).to_bytes(4, "little"))
  await axil.write(REG_CONTROL, (ctrl & ~(1 << CR_RESET)).to_bytes(4, "little"))

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

    ctrl &= ~(1 << CR_RS)
    await axil.write(REG_CONTROL, ctrl.to_bytes(4, "little"))

def pack_words(words):
  return bytearray().join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in words)
