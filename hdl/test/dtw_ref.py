# dtw_ref.py
import cocotb
from cocotb.triggers import RisingEdge, with_timeout
from cocotbext.axi import AxiLiteBus, AxiLiteMaster, AxiStreamBus, AxiStreamSource, AxiStreamFrame
from test_helpers import *
import random

SQG_SIZE = 256

@cocotb.test()
async def test_set_ref_len(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk)
  await reset_dut(dut)

  val = 64
  await axil.write(REG_REF_LEN, val.to_bytes(4, "little"))
  rd = await axil.read(REG_REF_LEN, 4)
  assert int.from_bytes(rd.data, "little") == val

@cocotb.test()
async def test_load_reference(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk)
  axis = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.axis_clk)
  await reset_dut(dut); await reset_core(axil); await reset_axis(dut)

  await axil.write(REG_REF_LEN, (SQG_SIZE).to_bytes(4, "little"))

  qid = 5
  query = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  await enter_query_load_mode(axil)
  await axis.send(AxiStreamFrame(pack_words([qid] + query)))

  await with_timeout(wait_state(axil, dut, 1), 200_000, "ns")

  ref = [i + 20 for i in range(SQG_SIZE)]
  await axis.send(AxiStreamFrame(pack_words(ref)))

  await with_timeout(wait_state(axil, dut, 4), 200_000, "ns")

  mem = dut.dut.dc.inst_dtw_core_ref_mem.MEM
  for i, exp in enumerate(ref):
    got = mem[i].value.integer
    assert got == (exp & 0xFFFF), f"ref_mem[{i}]={got} != {(exp & 0xFFFF)}"

@cocotb.test()
async def test_reference_bubbles(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk)
  axis = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.axis_clk)
  await reset_dut(dut); await reset_core(axil); await reset_axis(dut)

  await axil.write(REG_REF_LEN, (SQG_SIZE).to_bytes(4, "little"))

  qid = 7
  query = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  await enter_query_load_mode(axil)
  await axis.send(AxiStreamFrame(pack_words([qid] + query)))
  await with_timeout(wait_state(axil, dut, 1), 200_000, "ns")

  ref = [i + 20 for i in range(SQG_SIZE)]
  fr = AxiStreamFrame(pack_words(ref))
  send_task = cocotb.start_soon(axis.send(fr))

  rng = random.Random(0xb0bb1e)
  while not send_task.done():
    await RisingEdge(dut.axis_clk)
    if rng.random() < 0.20:
      axis.pause = True
      hold = 1 + rng.randrange(6)
      for _ in range(hold):
        await RisingEdge(dut.axis_clk)
      axis.pause = False

  await with_timeout(wait_state(axil, dut, 4), 300_000, "ns")

  mem = dut.dut.dc.inst_dtw_core_ref_mem.MEM
  for i, exp in enumerate(ref):
    assert mem[i].value.integer == (exp & 0xFFFF)