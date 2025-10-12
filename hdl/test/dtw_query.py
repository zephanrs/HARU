# dtw_query.py
import cocotb
from cocotb.triggers import RisingEdge, with_timeout
from cocotbext.axi import (
  AxiLiteBus, AxiLiteMaster,
  AxiStreamBus, AxiStreamSource, AxiStreamSink, AxiStreamFrame,
)
from test_helpers import *
import random

CLK_NS = 10
SQG_SIZE = 256
offset = 173

async def setup(dut):
  start_dut(dut)

  axil     = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"),      dut.clk,      reset=None)
  axis_in  = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.axis_clk, reset=None)
  axis_out = AxiStreamSink  (AxiStreamBus.from_prefix(dut, "axis_out"),dut.axis_clk, reset=None)

  await reset_dut(dut)
  return axil, axis_in, axis_out

async def load_reference(axil, axis_in, dut, ref_words):
  await reset_core(axil)
  await reset_axis(dut)

  rd   = await axil.read(REG_CONTROL, 4)
  ctrl = int.from_bytes(rd.data, "little")
  ctrl |=  (1 << CR_MODE)
  ctrl &= ~(1 << CR_RS)

  await axil.write(REG_CONTROL, ctrl.to_bytes(4, "little"))
  await axil.write(REG_REF_LEN, len(ref_words).to_bytes(4, "little"))

  ctrl |= (1 << CR_RS)
  await axil.write(REG_CONTROL, ctrl.to_bytes(4, "little"))

  payload = bytearray().join((w & 0xFFFFFFFF).to_bytes(4, "little", signed=False) for w in ref_words)
  await axis_in.send(AxiStreamFrame(payload))

  await with_timeout(wait_state(axil, dut, 0), 200_000, "ns")

async def enter_query_mode(axil):
  rd   = await axil.read(REG_CONTROL, 4)
  ctrl = int.from_bytes(rd.data, "little")

  ctrl &= ~(1 << CR_MODE)
  ctrl |=  (1 << CR_RS)

  await axil.write(REG_CONTROL, ctrl.to_bytes(4, "little"))

async def send_query(axis_in, qid, samples):
  packet  = [qid, 0] + samples

  payload = bytearray().join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in packet)

  fr = AxiStreamFrame(payload)
  await axis_in.send(fr)

async def check_result(axis_out, exp_qid, exp_pos, timeout_ns):
  frame = await with_timeout(axis_out.recv(), timeout_ns, "ns")
  data  = bytes(frame)

  words = [int.from_bytes(data[i:i+4], "little") for i in range(0, len(data), 4)]
  assert len(words) >= 3, f"short result: {words}"

  got_qid, position, distance = words[0], words[1], (words[2] & 0xFFFF)

  assert got_qid == exp_qid, f"qid {got_qid} != {exp_qid}"
  assert position == exp_pos, f"position {position} != {exp_pos}"
  assert distance == 0, f"distance {distance} != 0"

@cocotb.test()
async def test_load_query(dut):
  axil, axis_in, axis_out = await setup(dut)

  ref_words = [(i & 0xFFFF) for i in range(512)]
  await load_reference(axil, axis_in, dut, ref_words)

  assert int(dut.dut.dc.r_load_done.value) == 1
  assert int(dut.dut.dc.r_state.value) == 0

  await enter_query_mode(axil)

  qid = 7
  query_samples = ref_words[offset:offset+SQG_SIZE]
  await send_query(axis_in, qid, query_samples)

  await with_timeout(wait_state(axil, dut, 3), 100_000, "ns")

  dp = dut.dut.dc.inst_dtw_core_datapath
  while int(dp.running_d[SQG_SIZE].value) == 0:
    await RisingEdge(dut.clk)

  buf = dp.Squiggle_Buffer
  for i in range(SQG_SIZE):
    got = buf[i].value.integer
    exp = query_samples[i] & 0xFFFF
    assert got == exp, f"Squiggle_Buffer[{i}]={got} != {exp}"

  await check_result(axis_out, qid, offset + SQG_SIZE - 1, 50_000)

@cocotb.test()
async def test_multiple_query(dut):
  N_QUERIES = 4
  REF_LEN = 1024

  axil, axis_in, axis_out = await setup(dut)

  ref_words = [(i & 0xFFFF) for i in range(REF_LEN)]
  await load_reference(axil, axis_in, dut, ref_words)
  await enter_query_mode(axil)

  random.seed(42)
  max_start = REF_LEN - SQG_SIZE

  for k in range(N_QUERIES):
    qid   = 100 + k
    start = random.randint(0, max_start)
    samples = ref_words[start:start + SQG_SIZE]

    await send_query(axis_in, qid, samples)
    await with_timeout(wait_state(axil, dut, 3), 200_000, "ns")

    await check_result(axis_out, qid, start + SQG_SIZE - 1, 300_000)

@cocotb.test()
async def test_noisy_query_alignment(dut):
  axil, axis_in, axis_out = await setup(dut)

  ref_words = [(i & 0xFFFF) for i in range(512)]
  await load_reference(axil, axis_in, dut, ref_words)
  await enter_query_mode(axil)

  random.seed(123)

  start = 173
  base = ref_words[start:start + SQG_SIZE]

  noise_choices = (-2, -1, 0, 0, 0, 0, 1, 2)

  deltas = [random.choice(noise_choices) for _ in range(SQG_SIZE)]
  noisy  = [ (x + d) & 0xFFFF for x, d in zip(base, deltas) ]

  expected_distance = sum(abs(d) for d in deltas)
  exp_pos = start + SQG_SIZE - 1

  qid = 33
  await send_query(axis_in, qid, noisy)

  await with_timeout(wait_state(axil, dut, 3), 200_000, "ns")

  frame = await with_timeout(axis_out.recv(), 200_000, "ns")
  data  = bytes(frame)

  words = [int.from_bytes(data[i:i+4], "little") for i in range(0, len(data), 4)]
  assert len(words) >= 3, f"short result: {words}"

  got_qid, position, distance = words[0], words[1], (words[2] & 0xFFFF)

  assert got_qid == qid, f"qid {got_qid} != {qid}"

  pos_err = abs(position - exp_pos)
  assert pos_err <= 5, f"position {position} too far from {exp_pos} (err {pos_err} > 5)"

  dist_err = abs(int(distance) - int(expected_distance))
  assert dist_err <= 30, f"distance {distance} too far from expected {expected_distance} (err {dist_err} > 30)"