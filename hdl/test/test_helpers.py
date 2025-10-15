# test_helpers.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import with_timeout, RisingEdge
from cocotbext.axi import (
  AxiLiteBus, AxiLiteMaster,
  AxiStreamBus, AxiStreamSource, AxiStreamFrame,
)
from test_helpers import *
import random
import numpy as np

CLK_NS = 10

REG_CONTROL      = 0x00
REG_STATUS       = 0x04
REG_VERSION      = 0x08
REG_KEY          = 0x0C
REG_QID          = 0x14
REG_COUNT        = 0x18
REG_IDX          = 0x1C
REG_POS          = 0x20
REG_SCORE        = 0x24

CR_RST  = 0
CR_SDTW = 1
SQG_SIZE = 256

def start_dut(dut):
  cocotb.start_soon(Clock(dut.clk, CLK_NS, units="ns").start())

async def reset_dut(dut):
  dut.rst.value = 0
  for _ in range(5):
    await RisingEdge(dut.clk)
  dut.rst.value = 1
  for _ in range(5):
    await RisingEdge(dut.clk)

async def reset_core(axil, dut):
  rd = await axil.read(REG_CONTROL, 4)
  ctrl = int.from_bytes(rd.data, "little")
  await axil.write(REG_CONTROL, (ctrl |  (1 << CR_RST)).to_bytes(4, "little"))
  await axil.write(REG_CONTROL, (ctrl & ~(1 << CR_RST)).to_bytes(4, "little"))

def pack_words(words):
  return bytearray().join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in words)

def generate_random_reference(rng, query, ref_len=256):
  mu = float(SQG_SIZE) / float(ref_len)
  p1 = 0.5
  p2 = max(0.0, min(0.5, (mu - 0.5) / 2.0))
  p0 = 0.5 - p2

  ref = []
  r = 0
  for _ in range(ref_len):
    x = query[r]
    p = rng.random()
    if p < p2:
      r = min(r + 2, SQG_SIZE - 1)
    elif p < (p2 + p1):
      r = min(r + 1, SQG_SIZE - 1)
    y = x + rng.randint(-4, 4)
    if y < 0:
      y = 0
    ref.append(y & 0xFFFF)

  return ref

async def load_query(dut, axil, axis_in, qid, samples):
  await reset_core(axil, dut)
  await axis_in.send(AxiStreamFrame(pack_words([qid] + samples)))

async def load_reference(dut, axil, axis_in, ref_words):
  await axis_in.send(AxiStreamFrame(pack_words(ref_words)))
