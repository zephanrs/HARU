import pathlib
import re
import pytest
from cocotb_test.simulator import run

# …/haru/hdl
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
HDL       = REPO_ROOT / "src"
TEST_DIR  = REPO_ROOT / "test"
SIM_BUILD = str(REPO_ROOT / "build")

# Find all cocotb test files: dtw_*.py
TEST_FILES = sorted(TEST_DIR.glob("dtw_*.py"))

# Regex: @cocotb.test(...) then (async )?def test_name(
TEST_PATTERN = re.compile(
  r"@cocotb\.test(?:\s*\([^)]*\))?\s*?\n\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(",
  re.MULTILINE,
)

def discover_pairs():
  pairs, ids = [], []
  for f in TEST_FILES:
    text = f.read_text()
    names = TEST_PATTERN.findall(text)
    if not names:
      pairs.append((f.stem, None))
      ids.append(f"{f.stem}::(no_tests_found)")
    else:
      for t in names:
        pairs.append((f.stem, t))
        ids.append(f"{f.stem}::{t}")
  return pairs, ids

PARAMS, IDS = discover_pairs()

# RTL sources
VERILOG_SOURCES = [
  str(HDL / "axi_defines.v"),
  str(HDL / "axi_lite_slave.v"),
  str(HDL / "fifo.v"),
  str(HDL / "axis_2_fifo.v"),
  str(HDL / "fifo_2_axis.v"),
  str(HDL / "dtw_core_pe.v"),
  str(HDL / "dtw_core_ref_mem.v"),
  str(HDL / "dtw_core_datapath.v"),
  str(HDL / "dtw_core.v"),
  str(HDL / "dtw_accel.v"),
  str(HDL / "sim" / "tb_dtw_accel.v"),
]

@pytest.mark.parametrize("top", ["tb_dtw_accel"])
@pytest.mark.parametrize(("cocotb_module", "testcase"), PARAMS, ids=IDS)
def test_build_and_run(top, cocotb_module, testcase, request):
  waves = request.config.getoption("--waves", default=False)

  compile_args = ["-g2012", f"-I{HDL}"]
  sim_args = ["+trace"] if waves else []

  run(
    simulator="icarus",
    verilog_sources=VERILOG_SOURCES,
    toplevel=top,
    module=cocotb_module,
    testcase=testcase,
    toplevel_lang="verilog",
    compile_args=compile_args,
    sim_args=sim_args,
    sim_build=SIM_BUILD,
    python_search=[str(TEST_DIR)],
    extra_env={
      "PYTHONPATH": str(TEST_DIR),
      "COCOTB_RESOLVE_X": "RANDOM",
    },
  )
