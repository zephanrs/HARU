# HARU HDL - Hardware Accelerator for DTW

RTL implementation for the HARU DTW (Dynamic Time Warping) hardware accelerator in Verilog.

## Prerequisites

- Python 3.13+
- Verilator 5.x
- Make

## Setup

### 1. Create Virtual Environment

```bash
python3 -m venv venv-haru
source venv-haru/bin/activate  # On macOS/Linux
```

### 2. Install Dependencies

```bash
pip install cocotb pytest cocotbext-axi
```

## Running Tests

### Pytest (Recommended)

The recommended way to run tests is using pytest with cocotb's runner API:

```bash
cd hdl
make pytest
```

This will:
1. Create a `build/` directory if it doesn't exist
2. Build the Verilator simulation (on first run)
3. Run all tests and display results
4. Store all artifacts in `build/`

Or run pytest directly from the build directory:

```bash
mkdir -p build
cd build
pytest ../test_runner.py -v -s --tb=short
```

Benefits:
- Better test discovery and reporting
- Parallel test execution support
- Integration with modern Python test frameworks
- Detailed failure information
- All artifacts isolated in `build/` directory

### Legacy Cocotb Mode

Traditional cocotb Makefile-based testing is still supported:

```bash
make cocotb
```

## Test Structure

The test suite uses pytest with cocotb's runner API:

```
hdl/
├── test_runner.py     # Pytest runner with cocotb integration
├── pytest.ini         # Pytest configuration
├── tests/             # Test directory
│   └── test_dtw_accel.py   # Main DTW accelerator tests
└── tb/                # Test infrastructure
    └── axis_driver.py      # AXI Stream drivers
```

### Adding New Tests

1. Create a new test file in `tests/` directory (e.g., `test_new_feature.py`)
2. Import cocotb and write test functions decorated with `@cocotb.test()`:

```python
import cocotb
from cocotb.triggers import RisingEdge

@cocotb.test()
async def my_test(dut):
    """Test description"""
    # Your test code here
    await RisingEdge(dut.clk)
```

3. Run with `make pytest` - tests are auto-discovered

## Project Structure

```
hdl/
├── src/               # RTL source files
│   ├── dtw_accel.v           # Top-level accelerator
│   ├── dtw_core.v            # DTW core FSM
│   ├── dtw_core_datapath.v   # DTW datapath
│   ├── dtw_core_pe.v         # Processing element
│   ├── dtw_core_ref_mem.v    # Reference memory
│   ├── axi_lite_slave.v      # AXI-Lite interface
│   ├── axis_2_fifo.v         # AXI Stream to FIFO adapter
│   ├── fifo.v                # Generic FIFO
│   ├── fifo_2_axis.v         # FIFO to AXI Stream adapter
│   └── sim/                  # Simulation testbenches
│       └── tb_dtw_accel.v    # Top-level testbench
├── tests/             # Cocotb test files
│   └── test_dtw_accel.py     # Main DTW tests
├── tb/                # Python cocotb test infrastructure
│   └── axis_driver.py        # AXI Stream drivers
├── test_runner.py     # Pytest runner script
├── pytest.ini         # Pytest configuration
├── Makefile           # Build and simulation
└── README.md          # This file
```

## Build Artifacts

When running `make pytest`, all build artifacts are stored in the `build/` directory:
- `sim_build/` - Verilator compiled simulation binary
- `*.vcd` - Waveform files for each test
- `.pytest_cache/` - Pytest cache files
- Test result files and logs

The `build/` directory is automatically created and all test execution happens inside it.

## Clean Build

```bash
make clean
```

This removes all generated simulation files and build artifacts.

## Debugging

### Waveform Viewing

Waveforms are generated in VCD format during test execution:

```bash
# View waveforms from the build directory
cd build
gtkwave *.vcd  # or your preferred waveform viewer
```

Each test generates its own waveform file in the `build/` directory.
