# dtw_ref.py
import cocotb
from cocotb.triggers import Timer
from cocotbext.axi import (
  AxiLiteBus, AxiLiteMaster,
  AxiStreamBus, AxiStreamSource, AxiStreamFrame,
)
from test_helpers import *

@cocotb.test()
async def test_set_ref_len(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk, reset=None)
  await reset_dut(dut)
  val = 64
  await axil.write(REG_REF_LEN, val.to_bytes(4, "little"))
  rd = await axil.read(REG_REF_LEN, 4)
  assert int.from_bytes(rd.data, "little") == val

@cocotb.test()
async def test_load_reference(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk, reset=None)
  axis = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.axis_clk, reset=None)
  await reset_dut(dut)

  await reset_core(axil)
  await reset_axis(dut)
  await Timer(CLK_NS * 10, units="ns")

  rd = await axil.read(REG_CONTROL, 4)
  ctrl = int.from_bytes(rd.data, "little")
  ctrl |= (1 << CR_MODE)     # LOAD_REF
  ctrl &= ~(1 << CR_RS)
  await axil.write(REG_CONTROL, ctrl.to_bytes(4, "little"))

  ref_length = 256
  await axil.write(REG_REF_LEN, ref_length.to_bytes(4, "little"))

  rd = await axil.read(REG_CONTROL, 4)
  ctrl = int.from_bytes(rd.data, "little") | (1 << CR_RS)
  await axil.write(REG_CONTROL, ctrl.to_bytes(4, "little"))

  words = [i + 20 for i in range(ref_length)]
  payload = bytearray().join(
    (w & 0xFFFFFFFF).to_bytes(4, "little", signed=False) for w in words
  )
  await axis.send(AxiStreamFrame(payload))

  await wait_state(axil, dut, 0)

  mem = dut.dut.dc.inst_dtw_core_ref_mem.MEM
  for i in range(ref_length):
    got = mem[i].value.integer
    exp = words[i] & 0xFFFF
    assert got == exp, f"ref_mem[{i}]={got} != {exp}"
  assert int(dut.dut.dc.r_load_done.value) == 1
  assert int(dut.dut.dc.r_state.value) == 0
