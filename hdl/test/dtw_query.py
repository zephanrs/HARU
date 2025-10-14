import cocotb
from cocotb.triggers import RisingEdge, with_timeout
from cocotbext.axi import (
  AxiLiteBus, AxiLiteMaster,
  AxiStreamBus, AxiStreamSource, AxiStreamFrame,
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
  axis_in  = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.clk)

  await reset_dut(dut); await reset_core(axil)
  await axil.write(REG_REF_LEN, (1).to_bytes(4, "little"))

  await enter_query_load_mode(axil)

  qid = 0x77
  samples = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  payload = pack_words([qid] + samples)
  await axis_in.send(AxiStreamFrame(payload))

  await with_timeout(wait_state(axil, dut, 3), 300_000, "ns")

  await assert_squiggle_buffer_equals(dut, samples)
  assert int(dut.dut.dc.curr_qid.value) == qid

@cocotb.test()
async def test_query_bubbles(dut):
    start_dut(dut)
    axil     = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"),      dut.clk)
    axis_in  = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.clk)

    await reset_dut(dut)
    await reset_core(axil)
    await axil.write(REG_REF_LEN, (1).to_bytes(4, "little"))

    await enter_query_load_mode(axil)

    qid = 0xA55A
    samples = [(i & 0xFFFF) for i in range(SQG_SIZE)]
    payload = pack_words([qid] + samples)

    rng = random.Random(0xb0bb1e)

    def variable_idle_gen():
        while True:
            yield False
            for _ in range(rng.randrange(7)):
                yield True

    axis_in.set_pause_generator(variable_idle_gen())

    await axis_in.send(AxiStreamFrame(payload))

    await with_timeout(wait_state(axil, dut, 3), 300_000, "ns")

    dp = get_dp(dut)
    for i, exp in enumerate(samples):
        got = dp.Squiggle_Buffer[i].value.integer
        assert got == (exp & 0xFFFF), f"Squiggle_Buffer[{i}]={got} != {(exp & 0xFFFF)}"
    assert int(dut.dut.dc.curr_qid.value) == qid
