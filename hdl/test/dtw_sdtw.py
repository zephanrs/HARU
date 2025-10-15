# sDTW.py
import cocotb
from cocotb.triggers import with_timeout
from cocotbext.axi import (
  AxiLiteBus, AxiLiteMaster,
  AxiStreamBus, AxiStreamSource, AxiStreamFrame,
)
from test_helpers import *
import random
import numpy as np

def sdtw(reference, query):
  r = np.asarray(reference, dtype=np.int32)
  q = np.asarray(query, dtype=np.int32)
  
  n = int(q.size)
  m = int(r.size)
  
  INF = np.uint32(0xFFFFFFFF)
  dp = np.full((n + 1, m + 1), INF, dtype=np.uint32)
  
  dp[0, :] = np.uint32(0)
  
  for i in range(1, n + 1):
    qi = q[i - 1]
    
    for j in range(1, m + 1):
      rj = r[j - 1]
      cost = abs(qi - rj)
      
      a = dp[i - 1, j]
      b = dp[i, j - 1]
      c = dp[i - 1, j - 1]
      best = min(a, b, c)
      
      if best != INF:
        dp[i, j] = best + cost
  
  tail = dp[n, 1:m + 1]
  j = int(np.argmin(tail))
  
  return int(tail[j]), j


async def setup_sdtw(dut):
  start_dut(dut)

  axil    = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"),      dut.clk)
  axis_in = AxiStreamSource(AxiStreamBus.from_prefix(dut, "axis_in"), dut.clk)

  await reset_dut(dut)

  rd   = await axil.read(REG_CONTROL, 4)
  ctrl = int.from_bytes(rd.data, "little")
  ctrl |= (1 << CR_SDTW)
  await axil.write(REG_CONTROL, ctrl.to_bytes(4, "little"))

  await reset_core(axil, dut)

  return axil, axis_in


async def read_sdtw_status_regs(axil, expected_count=1, timeout_ns=400_000):
  async def wait_for_reg_count():
    while True:
      await cocotb.triggers.Timer(1000, "ns")
      count_bytes = await axil.read(REG_COUNT, 4)
      count = int.from_bytes(count_bytes.data, "little")
      if count == expected_count:
        break

  await with_timeout(wait_for_reg_count(), timeout_ns, "ns")

  qid_bytes   = await axil.read(REG_QID,      4)
  idx_bytes   = await axil.read(REG_IDX,      4)
  score_bytes = await axil.read(REG_SCORE,    4)
  pos_bytes   = await axil.read(REG_POS, 4)

  got_qid = int.from_bytes(qid_bytes.data,   "little")
  idx     = int.from_bytes(idx_bytes.data,   "little")
  score   = int.from_bytes(score_bytes.data, "little") & 0xFFFF
  pos     = int.from_bytes(pos_bytes.data,   "little")

  return got_qid, idx, score, pos


def gen_noise_walk(rng, length, *, start=None, step=4, lo=0, hi=1023):
  if start is None:
    x = rng.randrange(lo, hi + 1)
  else:
    x = max(lo, min(hi, start))

  out = []
  for _ in range(length):
    x = max(lo, min(hi, x + rng.randint(-step, step)))
    out.append(x)
  return out


def gen_ref_with_embedded_query(rng, query, total_len, *, lo=0, hi=1023, step=4):
  start = rng.randrange(0, total_len - SQG_SIZE + 1)

  q0 = int(query[0]) if len(query) else (lo + hi) // 2

  prefix = gen_noise_walk(rng, start, start=q0, step=step, lo=lo, hi=hi)

  core = generate_random_reference(rng, query, ref_len=SQG_SIZE)

  suffix_len = total_len - start - SQG_SIZE
  tail_start = int(core[-1]) if len(core) else q0
  suffix = gen_noise_walk(rng, suffix_len, start=tail_start, step=step, lo=lo, hi=hi)

  return prefix + core + suffix


def make_safe_query(rng, *, lo=0, hi=1023, step=4):
  x = rng.randrange((lo + hi) // 2 - 64, (lo + hi) // 2 + 65)
  out = []
  for _ in range(SQG_SIZE):
    x = max(lo, min(hi, x + rng.randint(-step, step)))
    out.append(x)
  return out


@cocotb.test()
async def test_sdtw_identity_subsequence(dut):
  axil, axis_in = await setup_sdtw(dut)

  rng = random.Random(0x1111)

  query = [((i + 5) & 0xFFFF) for i in range(SQG_SIZE)]
  total_len = rng.randrange(512, 1025)
  reference = gen_ref_with_embedded_query(rng, query, total_len)

  qid = 0x1001
  exp_score, exp_pos = sdtw(reference, query)

  await load_query(dut, axil, axis_in, qid, query)
  await load_reference(dut, axil, axis_in, reference)

  got_qid, idx, score, pos = await read_sdtw_status_regs(axil)

  assert got_qid == qid
  assert idx == 0
  assert score == exp_score
  assert pos == exp_pos


@cocotb.test()
async def test_sdtw_noisy_subsequence(dut):
  axil, axis_in = await setup_sdtw(dut)

  rng = random.Random(0x1111)

  base = [(i & 0xFFFF) for i in range(SQG_SIZE)]
  noise_choices = (-2, -1, 0, 0, 0, 0, 1, 2)
  noisy = [(x + rng.choice(noise_choices)) & 0xFFFF for x in base]

  total_len = rng.randrange(512, 1025)
  reference = gen_ref_with_embedded_query(rng, noisy, total_len)

  qid = 0x2002
  exp_score, exp_pos = sdtw(reference, noisy)

  await load_query(dut, axil, axis_in, qid, noisy)
  await load_reference(dut, axil, axis_in, reference)

  got_qid, idx, score, pos = await read_sdtw_status_regs(axil)

  assert got_qid == qid
  assert idx == 0
  assert score == exp_score
  assert pos == exp_pos


@cocotb.test()
async def test_sdtw_multiple_refs_one_query(dut):
  axil, axis_in = await setup_sdtw(dut)

  rng = random.Random(0x3333)

  query = make_safe_query(rng, lo=0, hi=1023, step=4)
  qid = 0x3003

  await load_query(dut, axil, axis_in, qid, query)

  best_score = 0xFFFF
  best_idx = -1
  best_pos = -1

  for k in range(5):
    total_len = rng.randrange(512, 1025)
    ref = gen_ref_with_embedded_query(rng, query, total_len, lo=0, hi=1023, step=4)

    exp_score, exp_pos = sdtw(ref, query)
    if exp_score <= best_score:
      best_score = exp_score
      best_idx = k
      best_pos = exp_pos

    await axis_in.send(AxiStreamFrame(pack_words(ref)))

  got_qid, idx, score, pos = await read_sdtw_status_regs(axil, expected_count=5, timeout_ns=1_200_000)

  assert got_qid == qid
  assert score == best_score
  assert idx == best_idx
  assert pos == best_pos


@cocotb.test()
async def test_sdtw_multiple_query_pairs(dut):
  axil, axis_in = await setup_sdtw(dut)

  rng = random.Random(0x4444)

  for qn in range(3):
    qid = 0x4000 + qn

    x = rng.randrange(0, 1024)
    query = []
    for _ in range(SQG_SIZE):
      x = max(0, min(0xFFFF, x + rng.randint(-4, 4)))
      query.append(x & 0xFFFF)

    await load_query(dut, axil, axis_in, qid, query)

    best_score = 0xFFFF
    best_idx = -1
    best_pos = -1

    for k in range(3):
      total_len = rng.randrange(512, 1025)
      ref = gen_ref_with_embedded_query(rng, query, total_len)

      exp_score, exp_pos = sdtw(ref, query)
      if exp_score < best_score:
        best_score = exp_score
        best_idx = k
        best_pos = exp_pos

      await axis_in.send(AxiStreamFrame(pack_words(ref)))

    got_qid, idx, score, pos = await read_sdtw_status_regs(axil, expected_count=3, timeout_ns=1_200_000)

    assert got_qid == qid
    assert idx == best_idx
    assert score == best_score
    assert pos == best_pos


@cocotb.test()
async def test_sdtw_latency_and_varlen(dut):
  axil, axis_in = await setup_sdtw(dut)

  rng = random.Random(0x5555)

  qid = 0x5005
  query = [((i + 3) & 0xFFFF) for i in range(SQG_SIZE)]

  def random_bubble_gen():
    while True:
      yield False
      for _ in range(rng.randrange(0, 4)):
        yield True

  axis_in.set_pause_generator(random_bubble_gen())

  await load_query(dut, axil, axis_in, qid, query)

  best_score = 0xFFFF
  best_idx = -1
  best_pos = -1

  for k in range(4):
    total_len = rng.randrange(512, 1025)
    ref = gen_ref_with_embedded_query(rng, query, total_len)

    exp_score, exp_pos = sdtw(ref, query)
    if exp_score < best_score:
      best_score = exp_score
      best_idx = k
      best_pos = exp_pos

    axis_in.set_pause_generator(random_bubble_gen())
    await axis_in.send(AxiStreamFrame(pack_words(ref)))

  got_qid, idx, score, pos = await read_sdtw_status_regs(axil, expected_count=4, timeout_ns=1_200_000)

  assert got_qid == qid
  assert idx == best_idx
  assert score == best_score
  assert pos == best_pos
