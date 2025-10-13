# dtw_ref.py
import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotbext.axi import (
  AxiLiteBus, AxiLiteMaster,
  AxiStreamBus, AxiStreamSource, AxiStreamFrame,
)
from test_helpers import *
import random

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

@cocotb.test()
async def test_ref_bubbles(dut):
    start_dut(dut)
    axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk)
    axis = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.axis_clk)
    await reset_dut(dut); await reset_core(axil); await reset_axis(dut)

    ref_length = 256
    await axil.write(REG_REF_LEN, ref_length.to_bytes(4, "little"))
    await axil.write(REG_CONTROL, ((1 << CR_MODE) | (1 << CR_RS)).to_bytes(4, "little"))

    rng = random.Random(0xD7B7B)
    words = [i + 20 for i in range(ref_length)]

    i = 0
    while i < ref_length:
        n = rng.randint(1, 8)
        payload = b"".join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in words[i:i+n])
        await axis.send(AxiStreamFrame(payload))
        for _ in range(rng.randint(0, 5)):
            await RisingEdge(dut.axis_clk)
        i += n

    await wait_state(axil, dut, 0)

    mem = dut.dut.dc.inst_dtw_core_ref_mem.MEM
    for i, exp in enumerate(words):
        assert mem[i].value.integer == (exp & 0xFFFF)
    assert int(dut.dut.dc.r_load_done.value) == 1
    assert int(dut.dut.dc.r_state.value) == 0