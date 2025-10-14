import cocotb
from cocotb.triggers import RisingEdge, with_timeout
from cocotbext.axi import AxiLiteBus, AxiLiteMaster, AxiStreamBus, AxiStreamSource, AxiStreamFrame
from test_helpers import *
import random

SQG_SIZE = 256

async def wait_cycles(clk, n):
  for _ in range(n):
    await RisingEdge(clk)

@cocotb.test()
async def test_set_ref_len(dut):
  start_dut(dut)
  axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "aximl"), dut.clk)
  await reset_dut(dut)

  val = 64
  await axil.write(REG_REF_LEN, val.to_bytes(4, "little"))
  rd = await axil.read(REG_REF_LEN, 4)
  assert int.from_bytes(rd.data, "little") == val

async def check_ref_stream_into_pe0(dut, reference_words):
  dp = dut.dut.dc.inst_dtw_core_datapath
  pe0_y = dp.inst_dtw_core_pe_0.y

  while True:
    await RisingEdge(dut.clk)
    if int(dp.running_d[1].value) == 1 and int(dp.running_d[2].value) == 0:
      got0 = pe0_y.value.integer & 0xFFFF
      exp0 = reference_words[0] & 0xFFFF
      assert got0 == exp0, f"PE0.y first word {got0} != {exp0}"
      idx = 1
      break

  while idx < len(reference_words):
    await RisingEdge(dut.clk)
    if int(dut.dut.dc.dp_running.value) == 1:
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
  await reset_core(axil)
  await axil.write(REG_REF_LEN, (SQG_SIZE).to_bytes(4, "little"))

  qid = 5
  query = [(i & 0xFFFF) for i in range(SQG_SIZE)]

  await enter_query_load_mode(axil)
  await axis.send(AxiStreamFrame(pack_words([qid] + query)))
  await with_timeout(wait_state(axil, dut, 3), 200_000, "ns")

  await wait_cycles(dut.clk, 100)

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
  await reset_core(axil)
  await axil.write(REG_REF_LEN, (SQG_SIZE).to_bytes(4, "little"))

  qid = 7
  query = [(i & 0xFFFF) for i in range(SQG_SIZE)]

  await enter_query_load_mode(axil)
  await axis.send(AxiStreamFrame(pack_words([qid] + query)))
  await with_timeout(wait_state(axil, dut, 3), 200_000, "ns")

  ref = [i + 20 for i in range(SQG_SIZE)]
  fr = AxiStreamFrame(pack_words(ref))
  send_task = cocotb.start_soon(axis.send(fr))

  rng = random.Random(0xb0bb1e)
  while not send_task.done():
    await RisingEdge(dut.clk)
    if rng.random() < 0.20:
      axis.pause = True
      for _ in range(1 + rng.randrange(6)):
        await RisingEdge(dut.clk)
      axis.pause = False

  await check_ref_stream_into_pe0(dut, ref)
  await send_task
