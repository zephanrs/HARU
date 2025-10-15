# dtw_ref.py
import cocotb
from cocotb.triggers import RisingEdge
from cocotbext.axi import (
    AxiLiteBus, AxiLiteMaster,
    AxiStreamBus, AxiStreamSource, AxiStreamFrame,
)
from test_helpers import *
import random

async def wait_cycles(clk, n):
  for _ in range(n):
    await RisingEdge(clk)

async def check_ref_stream_into_pe0(dut, reference_words):
  dp = dut.dut.dc.inst_dtw_core_datapath
  pe0_y = dp.inst_dtw_core_pe_0.y

  idx = 0
  while idx < len(reference_words):
    await RisingEdge(dut.clk)
    if int(dp.running_d[0].value) == 1:
      got = pe0_y.value.integer & 0xFFFF
      exp = reference_words[idx] & 0xFFFF
      assert got == exp, f"PE0.y word {got} != {exp} at ref index {idx}"
      idx += 1

@cocotb.test()
async def test_load_reference(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk)
  axis = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.clk)

  await reset_dut(dut)
  await reset_core(axil, dut)

  qid = 5
  query = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  await axis.send(AxiStreamFrame(pack_words([qid] + query)))

  ref = [i + 20 for i in range(SQG_SIZE)]
  send_task = cocotb.start_soon(axis.send(AxiStreamFrame(pack_words(ref))))

  await check_ref_stream_into_pe0(dut, ref)
  await send_task

@cocotb.test()
async def test_reference_bubbles(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk)
  axis = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.clk)

  await reset_dut(dut)
  await reset_core(axil, dut)

  qid = 7
  query = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  await axis.send(AxiStreamFrame(pack_words([qid] + query)))

  await wait_cycles(dut.clk, 10)

  ref = [i + 20 for i in range(SQG_SIZE)]
  payload = pack_words(ref)

  rng = random.Random(0xb0bb1e)

  def variable_idle_gen():
    while True:
      yield False
      for _ in range(rng.randrange(7)):
        yield True

  axis.set_pause_generator(variable_idle_gen())

  send_task = cocotb.start_soon(axis.send(AxiStreamFrame(payload)))
  await check_ref_stream_into_pe0(dut, ref)
  await send_task

  await wait_cycles(dut.clk, 10)
