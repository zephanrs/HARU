# test_helpers.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge

CLK_NS = 10  # 10ns clock everywhere

def start_dut(dut):
  """Start one shared 10ns clock and mirror to axis_clk."""
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
  """Active-LOW reset, 5 cycles low then deassert."""
  dut.rst.value = 0
  dut.axis_rst.value = 0
  for _ in range(5):
    await RisingEdge(dut.clk)
  dut.rst.value = 1
  dut.axis_rst.value = 1
  for _ in range(5):
    await RisingEdge(dut.clk)

async def reset_core(axil, reg_control, bit_reset):
  """Pulse CONTROL[bit_reset] high then low."""
  rd = await axil.read(reg_control, 4)
  ctrl = int.from_bytes(rd.data, "little")
  await axil.write(reg_control, (ctrl | (1 << bit_reset)).to_bytes(4, "little"))
  await axil.write(reg_control, (ctrl & ~(1 << bit_reset)).to_bytes(4, "little"))

async def reset_axis(dut):
  """AXIS reset jiggle, active-LOW."""
  dut.axis_rst.setimmediatevalue(1)
  for _ in range(2):
    await RisingEdge(dut.axis_clk)
  dut.axis_rst.value = 0
  for _ in range(2):
    await RisingEdge(dut.axis_clk)
  dut.axis_rst.value = 1
  for _ in range(2):
    await RisingEdge(dut.axis_clk)

async def wait_ref(axil, dut):
  for _ in range(50000):
    rd = await axil.read(0x04, 4)
    s = int.from_bytes(rd.data, "little")
    if ((s >> 1) & 1) and ((s >> 6) & 7) == 0:
      return
    await RisingEdge(dut.clk)
  raise AssertionError("timeout waiting for ref load complete")