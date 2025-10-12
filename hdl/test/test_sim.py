# test_sim.py
import os
import sys
import re
import pytest
import importlib
from pathlib import Path

import cocotb
from cocotb.runner import get_runner

top_module        = "tb_dtw_accel"
test_glob_pattern = "dtw_*.py"

proj_path = Path(__file__).resolve().parents[1]
src_path  = proj_path / "src"
test_path = proj_path / "test"
build_dir = proj_path / "build"

sources = [
  src_path / "axi_defines.v",
  src_path / "axi_lite_slave.v",
  src_path / "fifo.v",
  src_path / "axis_2_fifo.v",
  src_path / "fifo_2_axis.v",
  src_path / "dtw_core_pe.v",
  src_path / "dtw_core_ref_mem.v",
  src_path / "dtw_core_datapath.v",
  src_path / "dtw_core.v",
  src_path / "dtw_accel.v",
  src_path / "sim" / "tb_dtw_accel.v",
]

# same helper as your reference style
def get_tests(module):
  return [
    func.__name__ for func in vars(module).values()
    if isinstance(func, cocotb.regression.Test)
  ]

# ensure tests can be imported directly
if str(test_path) not in sys.path:
  sys.path.insert(0, str(test_path))

# discover modules and their cocotb tests
tests = []
test_modules = []
for p in sorted(test_path.glob(test_glob_pattern)):
  modname = p.stem
  if modname not in sys.modules:
    importlib.import_module(modname)
  test_modules.append(modname)
  tests += get_tests(sys.modules[modname])

def setup_runner():
  sim = os.getenv("SIM", "icarus")
  runner = get_runner(sim)

  build_args = []
  if sim.lower() == "icarus":
    build_args = ["-g2012", f"-I{src_path}"]

  runner.build(
    sources=[str(s) for s in sources],
    hdl_toplevel=top_module,
    build_args=build_args,
    waves=True,     # wave dumping can still be toggled per-test below
    verbose=True,
    always=True,
  )
  return runner

runner = setup_runner()

@pytest.mark.parametrize("test_case", tests or ["(no_tests_found)"])
def test_runner(test_case, request):
  # honor --waves and --tc from conftest.py
  waves = request.config.getoption("--waves")
  tc    = request.config.getoption("--tc")

  if test_case == "(no_tests_found)":
    pytest.skip("no cocotb tests found")

  if tc and test_case != tc:
    pytest.skip(f"--tc specified: skipping {test_case}")

  # set env here (runner.test in this version has no 'env=' kwarg)
  os.environ["PYTHONPATH"] = str(test_path)
  os.environ.setdefault("COCOTB_RESOLVE_X", "RANDOM")

  runner.test(
    hdl_toplevel=top_module,
    test_module=",".join(test_modules),
    testcase=test_case,
    test_dir=str(build_dir),
    waves=waves,
    verbose=True,
  )

if __name__ == "__main__":
  print("running tests…")
  pytest.main([__file__, "-v", "-s"])
