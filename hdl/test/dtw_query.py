import cocotb
from cocotb.triggers import RisingEdge, with_timeout
from cocotbext.axi import (
  AxiLiteBus, AxiLiteMaster,
  AxiStreamBus, AxiStreamSource, AxiStreamSink, AxiStreamFrame,
)
from test_helpers import *
import random
import numpy as np


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


async def check_result(axis_out, exp_qid, exp_score, timeout_ns):
  frame = await with_timeout(axis_out.recv(), timeout_ns, "ns")
  data  = bytes(frame)

  words = [int.from_bytes(data[i:i+4], "little") for i in range(0, len(data), 4)]
  assert len(words) >= 3, f"short result: {words}"

  got_qid, position, distance = words[0], words[1], (words[2] & 0xFFFF)

  assert got_qid == exp_qid, f"qid {got_qid} != {exp_qid}"
  assert int(distance) == int(exp_score), f"score {distance} != {exp_score}"


def dtw(reference, query):
  r = np.asarray(reference, dtype=np.uint16)
  q = np.asarray(query,     dtype=np.uint16)

  n = int(q.size)
  m = int(r.size)

  INF = np.uint16(0xFFFF)
  dp = np.full((n + 1, m + 1), INF, dtype=np.uint16)

  dp[0, 0] = np.uint16(0)

  for i in range(1, n + 1):
    qi = q[i - 1]

    for j in range(1, m + 1):
      rj = r[j - 1]

      hi = np.maximum(qi, rj, dtype=np.uint16)
      lo = np.minimum(qi, rj, dtype=np.uint16)
      cost = np.uint16(hi - lo)

      a = dp[i - 1, j]
      b = dp[i,     j - 1]
      c = dp[i - 1, j - 1]
      best_prev = a if a <= b else b
      best_prev = best_prev if best_prev <= c else c

      if best_prev == INF:
        dp[i, j] = INF
      else:
        dp[i, j] = np.uint16(best_prev + cost)

  best_distance = int(dp[n, m])
  best_end_pos = m - 1

  return best_distance, best_end_pos


@cocotb.test()
async def test_load_query(dut):
  axil, axis_in, axis_out = await setup(dut)

  ref_words = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  await load_reference(axil, axis_in, dut, ref_words)

  assert int(dut.dut.dc.r_load_done.value) == 1
  assert int(dut.dut.dc.r_state.value) == 0

  await enter_query_mode(axil)

  qid = 7
  query_samples = ref_words

  await send_query(axis_in, qid, query_samples)

  await with_timeout(wait_state(axil, dut, 3), 100_000, "ns")
  await wait_for_dtw_run_window(dut, SQG_SIZE)

  await assert_squiggle_buffer_equals(dut, query_samples)
  await check_result(axis_out, qid, 0, 50_000)


@cocotb.test()
async def test_noisy_query_alignment(dut):
  axil, axis_in, axis_out = await setup(dut)

  ref_words = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  await load_reference(axil, axis_in, dut, ref_words)

  await enter_query_mode(axil)

  random.seed(123)

  base = ref_words

  noise_choices = (-2, -1, 0, 0, 0, 0, 1, 2)
  deltas = [random.choice(noise_choices) for _ in range(SQG_SIZE)]
  noisy  = [ (x + d) & 0xFFFF for x, d in zip(base, deltas) ]

  expected_distance, _ = dtw(ref_words, noisy)

  qid = 33
  await send_query(axis_in, qid, noisy)

  await with_timeout(wait_state(axil, dut, 3), 200_000, "ns")

  await check_result(axis_out, qid, expected_distance, 200_000)


@cocotb.test()
async def test_query_bubble(dut):
  axil, axis_in, axis_out = await setup(dut)

  ref_words = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  await load_reference(axil, axis_in, dut, ref_words)

  assert int(dut.dut.dc.r_load_done.value) == 1
  assert int(dut.dut.dc.r_state.value) == 0

  await enter_query_mode(axil)

  qid = 0xA55A
  query_samples = ref_words

  packet  = [qid] + list(query_samples)
  payload = bytearray().join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in packet)
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

  rng = random.Random(2025)
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
  await check_result(axis_out, qid, 0, 300_000)
