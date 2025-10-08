import os
import sys
import pytest
import importlib
from pathlib import Path

import cocotb
from cocotb.runner import get_runner

TOP_MODULE        = "tb_dtw_accel"
TEST_GLOB_PATTERN = "test_*.py"

#=========================================================================
# Get tests that start with "test_"
#=========================================================================

def get_tests(module):
    return [
        func.__name__ for func in vars(module).values()
        if isinstance(func, cocotb.regression.Test)
    ]

# Get the paths of the project
proj_path    = Path(__file__).resolve().parent
src_path     = proj_path / "src"
test_path    = proj_path / "tests"

# Ensure that the project directory is in the Python path
if str(proj_path) not in sys.path:
    sys.path.insert(0, str(proj_path))

# Get all tests for pytest to instantiate cocotb tests
tests = []
test_modules = [f"tests.{test_module.stem}" for test_module in test_path.glob(TEST_GLOB_PATTERN)]

# Import the test modules dynamically
for module_name in test_modules:
    if module_name not in sys.modules:
        importlib.import_module(module_name)
    module = sys.modules[module_name]
    tests += get_tests(module)

#=========================================================================
# Test runner setup
#=========================================================================

def setup_runner():
    """Set up the test environment and run pytest."""

    # Get the simulation tool (default is Verilator)
    sim = os.getenv("SIM", "verilator")

    sources = [
        src_path / "dtw_accel.v",
        src_path / "axi_lite_slave.v",
        src_path / "axis_2_fifo.v",
        src_path / "fifo.v",
        src_path / "fifo_2_axis.v",
        src_path / "dtw_core.v",
        src_path / "dtw_core_datapath.v",
        src_path / "dtw_core_ref_mem.v",
        src_path / "dtw_core_pe.v",
        src_path / "sim" / "tb_dtw_accel.v"
    ]

    verilator_build_args = [
        "--trace",          # Enable waveform generation
        "--trace-structs",  # Enable structure tracing
        "--Wno-fatal",      # Do not treat warnings as fatal (errors)
        "-Wno-WIDTHEXPAND",
        "-Wno-WIDTHTRUNC",
        "-Wno-ASCRANGE",
        "-Wno-CASEINCOMPLETE",
        "-Wno-INITIALDLY",
        f"-I{src_path}",
    ]

    # Build the simulation
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        build_args=verilator_build_args,
        hdl_toplevel=TOP_MODULE,
        waves=True,
        verbose=True,
        always=True,
    )

    return runner

runner = setup_runner()

@pytest.mark.parametrize("test_case", tests)
def test_runner(test_case):
    """Set up the test environment and run pytest."""

    # Build directory should already exist from setup
    build_dir = proj_path / "build"

    # runner.test() will handle pass/fail internally and print results
    # It may raise SystemExit on failure
    runner.test(
        hdl_toplevel=TOP_MODULE,
        test_dir=str(build_dir),  # Run tests from build directory
        testcase=test_case,
        waves=True,
        test_module=",".join(test_modules),  # Concatenate all test module names
    )

if __name__ == "__main__":
    print("Running tests...")
    pytest.main([__file__, "-v", "-s"])
