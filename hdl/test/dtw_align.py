import cocotb
from cocotb.triggers import with_timeout
from cocotbext.axi import (
  AxiLiteBus, AxiLiteMaster,
  AxiStreamBus, AxiStreamSource, AxiStreamFrame,
)
from test_helpers import *
import random
import numpy as np

SQG_SIZE = 256


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
      cost = np.uint16(abs(int(qi) - int(rj)))
      a = dp[i - 1, j]
      b = dp[i, j - 1]
      c = dp[i - 1, j - 1]
      best = min(a, b, c)
      dp[i, j] = INF if best == INF else np.uint16(best + cost)

  return int(dp[n, m]), m - 1


async def setup(dut):
  start_dut(dut)

  axil     = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"),      dut.clk)
  axis_in  = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.clk)

  await reset_dut(dut)
  await reset_core(axil)

  return axil, axis_in


async def load_query(dut, axil, axis_in, qid, samples, ref_len):
  await axil.write(REG_REF_LEN, int(ref_len).to_bytes(4, "little"))

  await enter_query_load_mode(axil)
  await axis_in.send(AxiStreamFrame(pack_words([qid] + samples)))

  await with_timeout(wait_state(axil, dut, 1), 200_000, "ns")


async def load_reference(dut, axil, axis_in, ref_words):
  await axis_in.send(AxiStreamFrame(pack_words(ref_words)))


async def read_status_regs(axil):
  async def wait_for_reg_count():
    while True:
      await cocotb.triggers.Timer(1000, "ns")
      count_bytes = await axil.read(REG_COUNT, 4)
      count = int.from_bytes(count_bytes.data, "little")
      if count == 1:
        break

  await with_timeout(wait_for_reg_count(), 400_000, "ns")

  qid_bytes   = await axil.read(REG_QID,   4)
  idx_bytes   = await axil.read(REG_IDX,   4)
  score_bytes = await axil.read(REG_SCORE, 4)
  got_qid = int.from_bytes(qid_bytes.data,   "little")
  idx     = int.from_bytes(idx_bytes.data,   "little")
  score   = int.from_bytes(score_bytes.data, "little") & 0xFFFF
  return got_qid, idx, score


@cocotb.test()
async def test_align_identity(dut):
  axil, axis_in = await setup(dut)

  ref = [((i+10) & 0xFFFF) for i in range(SQG_SIZE)]
  qid = 7

  await load_query(dut, axil, axis_in, qid, ref, len(ref))
  await load_reference(dut, axil, axis_in, ref)

  got_qid, idx, dist = await read_status_regs(axil)
  assert got_qid == qid
  assert idx == 0
  assert dist == 0


@cocotb.test()
async def test_align_noisy(dut):
  axil, axis_in = await setup(dut)

  base = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  qid = 33
  noise_choices = (-2, -1, 0, 0, 0, 0, 1, 2)
  rng = random.Random(123)
  noisy = [(x + rng.choice(noise_choices)) & 0xFFFF for x in base]
  exp, _ = dtw(base, noisy)

  await load_query(dut, axil, axis_in, qid, noisy, len(base))
  await load_reference(dut, axil, axis_in, base)

  got_qid, idx, dist = await read_status_regs(axil)
  assert got_qid == qid
  assert idx == 0
  assert dist == exp


@cocotb.test()
async def test_align_misaligned(dut):
  axil, axis_in = await setup(dut)

  ref = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  shift = 16
  qid = 0x1234
  query = ref[shift:] + [0] * shift
  exp, _ = dtw(ref, query)

  await load_query(dut, axil, axis_in, qid, query, len(ref))
  await load_reference(dut, axil, axis_in, ref)

  got_qid, idx, dist = await read_status_regs(axil)
  assert got_qid == qid
  assert idx == 0
  assert dist == exp


# @cocotb.test()
# async def test_align_random_cases(dut):
#   axil, axis_in = await setup(dut)

#   rng = random.Random(2027)
#   for k in range(4):
#     ref = [rng.randrange(0, 1025) for _ in range(SQG_SIZE)]

#     q = []
#     r = 0
#     for _ in range(SQG_SIZE):
#       x = ref[r]
#       p = rng.random()
#       if p < 0.25:
#         r = min(r + 2, SQG_SIZE - 1)
#       elif p < 0.75:
#         r = min(r + 1, SQG_SIZE - 1)
#       y = x + rng.randint(-8, 8)
#       if y < 0:
#         y = 0
#       q.append(y & 0xFFFF)

#     exp, _ = dtw(ref, q)
#     assert exp < 65000

#     qid = 0x9000 + k
#     await load_query(dut, axil, axis_in, qid, q, len(ref))
#     await load_reference(dut, axil, axis_in, ref)

#     got_qid, idx, dist = await read_status_regs(axil)
#     assert got_qid == qid
#     assert idx == 0
#     assert dist == exp


@cocotb.test()
async def test_align_latency_insensitive(dut):
    axil, axis_in = await setup(dut)

    rng = random.Random(0xB0BB1E)
    qid = 0xCAFE
    ref = [(i & 0xFFFF) for i in range(SQG_SIZE)]

    await load_query(dut, axil, axis_in, qid, ref, len(ref))

    payload = pack_words(ref)
    frame = AxiStreamFrame(payload)

    def variable_pause_gen():
        while True:
            yield False
            for _ in range(rng.randrange(7)):
                yield True

    axis_in.set_pause_generator(variable_pause_gen())
    await axis_in.send(frame)

    got_qid, idx, dist = await read_status_regs(axil)
    assert got_qid == qid, f"Got QID {got_qid:#x}, expected {qid:#x}"
    assert idx == 0, f"Expected index 0, got {idx}"
    assert dist == 0, f"Expected distance 0, got {dist}"


@cocotb.test()
async def test_edge_alignment(dut):
    axil, axis_in = await setup(dut)

    qid = 0xBEEF
    query = [0 for _ in range(SQG_SIZE)]
    reference = [10 for _ in range(SQG_SIZE)]
    for i in range(4):
        reference[-1 - i] = 0

    exp_dist, _ = dtw(reference, query)

    def every_beat_bubble_gen():
        while True:
            yield False
            yield True

    axis_in.set_pause_generator(every_beat_bubble_gen())

    await load_query(dut, axil, axis_in, qid, query, len(reference))
    await load_reference(dut, axil, axis_in, reference)

    got_qid, idx, dist = await read_status_regs(axil)
    assert got_qid == qid
    assert idx == 0
    assert dist == exp_dist
