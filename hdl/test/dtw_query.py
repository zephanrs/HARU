# dtw_query.py
import cocotb
from cocotb.triggers import RisingEdge, with_timeout
from cocotbext.axi import (
  AxiLiteBus, AxiLiteMaster,
  AxiStreamBus, AxiStreamSource, AxiStreamSink, AxiStreamFrame,
)
from test_helpers import *
import random

SQG_SIZE = 256

def get_dp(dut):
  return dut.dut.dc.inst_dtw_core_datapath

async def assert_squiggle_buffer_equals(dut, expected):
  dp = get_dp(dut)
  for i, exp in enumerate(expected):
    got = dp.Squiggle_Buffer[i].value.integer
    assert got == (exp & 0xFFFF), f"Squiggle_Buffer[{i}]={got} != {(exp & 0xFFFF)}"

@cocotb.test()
async def test_load_query(dut):
  start_dut(dut)
  axil     = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"),      dut.clk)
  axis_in  = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.axis_clk)
  axis_out = AxiStreamSink  (AxiStreamBus.from_prefix(dut, "axis_out"),dut.axis_clk)

  await reset_dut(dut); await reset_core(axil); await reset_axis(dut)

  await enter_query_load_mode(axil)

  qid = 0x77
  samples = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  payload = pack_words([qid] + samples)
  await axis_in.send(AxiStreamFrame(payload))

  # Wait for DTW_RUN (state = 3) which implies dp_load_done was asserted
  await with_timeout(wait_state(axil, dut, 3), 200_000, "ns")

  await assert_squiggle_buffer_equals(dut, samples)
  assert int(dut.dut.dc.curr_qid.value) == qid

@cocotb.test()
async def test_query_bubbles(dut):
  start_dut(dut)
  axil     = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"),      dut.clk)
  axis_in  = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.axis_clk)
  axis_out = AxiStreamSink  (AxiStreamBus.from_prefix(dut, "axis_out"),dut.axis_clk)

  await reset_dut(dut); await reset_core(axil); await reset_axis(dut)

  await enter_query_load_mode(axil)

  qid = 0xA55A
  samples = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  fr = AxiStreamFrame(pack_words([qid] + samples))

  send_task = cocotb.start_soon(axis_in.send(fr))

  rng = random.Random(0xb0bb1e)
  while not send_task.done():
    await RisingEdge(dut.axis_clk)
    if rng.random() < 0.15:
      axis_in.pause = True
      hold = 1 + rng.randrange(6)
      for _ in range(hold):
        await RisingEdge(dut.axis_clk)
      axis_in.pause = False

  # Wait for DTW_RUN (state = 3) after query load completes
  await with_timeout(wait_state(axil, dut, 3), 300_000, "ns")

  dp = get_dp(dut)
  for i, exp in enumerate(samples):
    assert dp.Squiggle_Buffer[i].value.integer == (exp & 0xFFFF)
  assert int(dut.dut.dc.curr_qid.value) == qid
