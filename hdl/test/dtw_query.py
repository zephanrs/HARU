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
offset = 0


def get_dp(dut):
  return dut.dut.dc.inst_dtw_core_datapath


async def wait_for_dtw_run_window(dut, sqg_size=256):
  dp = get_dp(dut)
  while int(dp.running_d[sqg_size].value) == 0:
    await RisingEdge(dut.clk)


async def assert_squiggle_buffer_equals(dut, expected):
  dp = get_dp(dut)
  buf = dp.Squiggle_Buffer
  for i, exp in enumerate(expected):
    got = buf[i].value.integer
    exp &= 0xFFFF
    assert got == exp, f"Squiggle_Buffer[{i}]={got} != {exp}"


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
  packet  = [qid] + samples
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
  await wait_for_dtw_run_window(dut, SQG_SIZE)

  await assert_squiggle_buffer_equals(dut, query_samples)
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


@cocotb.test()
async def test_load_query_gap_after_qid(dut):
  axil, axis_in, axis_out = await setup(dut)

  ref_words = [(i & 0xFFFF) for i in range(512)]
  await load_reference(axil, axis_in, dut, ref_words)

  assert int(dut.dut.dc.r_load_done.value) == 1
  assert int(dut.dut.dc.r_state.value) == 0

  await enter_query_mode(axil)

  qid = 77
  query_samples = ref_words[offset:offset+SQG_SIZE]

  payload = bytearray().join(
      (w & 0xFFFFFFFF).to_bytes(4, "little") for w in ([qid] + query_samples)
  )
  fr = AxiStreamFrame(payload)

  send_task = cocotb.start_soon(axis_in.send(fr))

  sent = 0
  while sent < 1:
    await RisingEdge(dut.axis_clk)
    if int(dut.axis_in_tvalid.value) and int(dut.axis_in_tready.value):
      sent += 1

  axis_in.pause = True
  for _ in range(10):
    await RisingEdge(dut.axis_clk)
  axis_in.pause = False

  await send_task

  await with_timeout(wait_state(axil, dut, 3), 200_000, "ns")
  await wait_for_dtw_run_window(dut, SQG_SIZE)

  await assert_squiggle_buffer_equals(dut, query_samples)
  await check_result(axis_out, qid, offset + SQG_SIZE - 1, 300_000)


@cocotb.test()
async def test_query_with_random_bubbles(dut):
  axil, axis_in, axis_out = await setup(dut)

  REF_LEN = 1024
  ref_words = [(i & 0xFFFF) for i in range(REF_LEN)]
  await load_reference(axil, axis_in, dut, ref_words)
  await enter_query_mode(axil)

  rng = random.Random(2025)
  start = rng.randrange(0, REF_LEN - SQG_SIZE + 1)

  qid = 0xA55A
  query_samples = ref_words[start:start + SQG_SIZE]

  packet  = [qid] + list(query_samples)
  payload = bytearray().join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in packet)
  fr = AxiStreamFrame(payload)

  send_task = cocotb.start_soon(axis_in.send(fr))

  pause_prob = 0.10
  max_pause_cycles = 5

  while not send_task.done():
    await RisingEdge(dut.axis_clk)
    if rng.random() < pause_prob:
      axis_in.pause = True
      hold = 1 + rng.randrange(max(1, max_pause_cycles))
      for _ in range(hold):
        await RisingEdge(dut.axis_clk)
      axis_in.pause = False

  await send_task

  await with_timeout(wait_state(axil, dut, 3), 300_000, "ns")
  await wait_for_dtw_run_window(dut, SQG_SIZE)

  await assert_squiggle_buffer_equals(dut, query_samples)
  await check_result(axis_out, qid, start + SQG_SIZE - 1, 300_000)
