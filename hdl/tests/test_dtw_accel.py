# MIT License

# Copyright (c) 2022 Po Jui Shih
# Copyright (c) 2022 Hassaan Saadat
# Copyright (c) 2022 Sri Parameswaran
# Copyright (c) 2022 Hasindu Gamaarachchi

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from email.mime import base
import os
import sys
import random
import cocotb
import logging
from cocotb.clock import Clock
import time
from array import array as Array
from cocotb.triggers import Timer
from cocotb.triggers import RisingEdge
from cocotb.triggers import FallingEdge

from tb.axis_driver import AXISSource
from tb.axis_driver import AXISSink
from cocotb_bus.drivers.amba import AXI4LiteMaster
from tb.dtw_accel_driver import DtwAccelDriver

CLK_PERIOD = 2
AXIS_CLK_PERIOD = 2

MODULE_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "rtl")
MODULE_PATH = os.path.abspath(MODULE_PATH)

def setup_dut(dut):
    cocotb.fork(Clock(dut.clk, CLK_PERIOD).start())
    cocotb.fork(Clock(dut.axis_clk, AXIS_CLK_PERIOD).start())

@cocotb.coroutine
def reset_dut(dut):
    dut.rst.value = 1
    dut.axis_rst.value = 1
    yield Timer(CLK_PERIOD * AXIS_CLK_PERIOD * 2)
    dut.rst.value = 0
    dut.axis_rst.value = 0
    yield Timer(CLK_PERIOD * AXIS_CLK_PERIOD * 2)

###############################################################################
## Test read version
###############################################################################
@cocotb.test(skip = False)
def test_read_version(dut):
    """
    Test reading the version register via AXI-Lite interface.

    Verifies that the version read through AXI matches the internal design version.
    """
    # -------------------------------------------------------------------------
    # Test Setup
    # -------------------------------------------------------------------------
    dut._log.setLevel(logging.WARNING)
    dut.test_id.value = 0

    setup_dut(dut)
    axi_driver = DtwAccelDriver(dut, "aximl", dut.clk, dut.rst, debug=False)

    # Reset the DUT
    yield reset_dut(dut)

    # -------------------------------------------------------------------------
    # Test Execution
    # -------------------------------------------------------------------------
    # Read version register via AXI-Lite
    version = yield axi_driver.get_version()

    # Get actual version directly from hardware signal
    dut_version = dut.dut.w_version.value

    # Log the results
    dut._log.info("DUT Version (internal): %s", dut_version)
    dut._log.info("Version (via AXI):      0x%08X", version)

    # Wait for signals to settle
    yield Timer(CLK_PERIOD * 20)

    # -------------------------------------------------------------------------
    # Test Validation
    # -------------------------------------------------------------------------
    assert dut_version == version, \
        f"Version mismatch: DUT={dut_version:08x}, AXI={version:08x}"

###############################################################################
## Test write control
###############################################################################
@cocotb.test(skip = False)
def test_write_control(dut):
    """
    Test writing to the control register via AXI-Lite interface.

    Verifies that the control value written through AXI is correctly stored
    in the internal control register.
    """
    # -------------------------------------------------------------------------
    # Test Setup
    # -------------------------------------------------------------------------
    dut._log.setLevel(logging.WARNING)
    dut.test_id.value = 1

    setup_dut(dut)
    axi_driver = DtwAccelDriver(dut, "aximl", dut.clk, dut.rst, debug=False)

    # Reset the DUT
    yield reset_dut(dut)

    # -------------------------------------------------------------------------
    # Test Execution
    # -------------------------------------------------------------------------
    # Write test value to control register
    test_control_value = 0x01234567
    yield axi_driver.set_control(test_control_value)

    # Wait for signals to settle
    yield Timer(CLK_PERIOD * 20)

    # -------------------------------------------------------------------------
    # Test Validation
    # -------------------------------------------------------------------------
    actual_control = dut.dut.r_control.value
    assert actual_control == test_control_value, \
        f"Control register mismatch: expected=0x{test_control_value:08x}, actual=0x{actual_control:08x}"

###############################################################################
## Test read control
###############################################################################
@cocotb.test(skip = False)
def test_read_control(dut):
    """
    Test reading from the control register via AXI-Lite interface.

    Verifies that the control value can be correctly read through AXI
    when the internal register is set directly.
    """
    # -------------------------------------------------------------------------
    # Test Setup
    # -------------------------------------------------------------------------
    dut._log.setLevel(logging.WARNING)
    dut.test_id.value = 2

    setup_dut(dut)
    axi_driver = DtwAccelDriver(dut, "aximl", dut.clk, dut.rst, debug=False)

    # Reset the DUT
    yield reset_dut(dut)

    # -------------------------------------------------------------------------
    # Test Execution
    # -------------------------------------------------------------------------
    # Set control register directly in hardware
    test_control_value = 0xFEDCBA98
    dut.dut.r_control.value = test_control_value

    # Read control register via AXI-Lite
    control_readback = yield axi_driver.get_control()

    # Wait for signals to settle
    yield Timer(CLK_PERIOD * 20)

    # -------------------------------------------------------------------------
    # Test Validation
    # -------------------------------------------------------------------------
    assert control_readback == test_control_value, \
        f"Control register readback mismatch: expected=0x{test_control_value:08x}, actual=0x{control_readback:08x}"

###############################################################################
## Test setting and reading ref len
###############################################################################
@cocotb.test(skip = False)
def test_ref_len(dut):
    """
    Test writing and reading the reference length register via AXI-Lite interface.

    Verifies that the ref_len value written through AXI is correctly stored
    in the internal register and can be read back via AXI.
    """
    # -------------------------------------------------------------------------
    # Test Setup
    # -------------------------------------------------------------------------
    dut._log.setLevel(logging.WARNING)
    dut.test_id.value = 3

    setup_dut(dut)
    axi_driver = DtwAccelDriver(dut, "aximl", dut.clk, dut.rst, debug=False)

    # Reset the DUT
    yield reset_dut(dut)

    # -------------------------------------------------------------------------
    # Test Execution
    # -------------------------------------------------------------------------
    # Write test value to ref_len register
    test_ref_len = 0x12345678
    yield axi_driver.set_ref_len(test_ref_len)

    # Read back ref_len register via AXI-Lite
    ref_len_readback = yield axi_driver.get_ref_len()

    # Wait for signals to settle
    yield Timer(CLK_PERIOD * 20)

    # -------------------------------------------------------------------------
    # Test Validation
    # -------------------------------------------------------------------------
    # Check internal register matches written value
    actual_ref_len = dut.dut.r_ref_len.value
    assert actual_ref_len == test_ref_len, \
        f"Internal ref_len mismatch: expected=0x{test_ref_len:08x}, actual=0x{actual_ref_len:08x}"

    # Check AXI readback matches written value
    assert ref_len_readback == test_ref_len, \
        f"AXI ref_len readback mismatch: expected=0x{test_ref_len:08x}, actual=0x{ref_len_readback:08x}"

###############################################################################
## Test get key
###############################################################################
@cocotb.test(skip = False)
def test_get_key(dut):
    """
    Test reading the key register via AXI-Lite interface.

    Verifies that the hardcoded key value (0x0ca7cafe) can be correctly
    read through the AXI interface.
    """
    # -------------------------------------------------------------------------
    # Test Setup
    # -------------------------------------------------------------------------
    dut._log.setLevel(logging.WARNING)
    dut.test_id.value = 4

    setup_dut(dut)
    axi_driver = DtwAccelDriver(dut, "aximl", dut.clk, dut.rst, debug=False)

    # Reset the DUT
    yield reset_dut(dut)

    # -------------------------------------------------------------------------
    # Test Execution
    # -------------------------------------------------------------------------
    # Read key register via AXI-Lite
    key_readback = yield axi_driver.get_key()

    # Wait for signals to settle
    yield Timer(CLK_PERIOD * 20)

    # -------------------------------------------------------------------------
    # Test Validation
    # -------------------------------------------------------------------------
    expected_key = 0x0ca7cafe
    assert key_readback == expected_key, \
        f"Key register mismatch: expected=0x{expected_key:08x}, actual=0x{key_readback:08x}"

###############################################################################
## Test loading the reference
###############################################################################
@cocotb.test(skip = False)
def test_load_ref(dut):
    """
    Test the reference loading functionality via AXI Stream interface.

    Verifies that reference data streamed in via AXI Stream is correctly
    stored in the DTW core's reference memory when in load reference mode.
    """
    # -------------------------------------------------------------------------
    # Test Setup
    # -------------------------------------------------------------------------
    dut._log.setLevel(logging.WARNING)
    dut.test_id.value = 5

    setup_dut(dut)
    axi_driver = DtwAccelDriver(dut, "aximl", dut.clk, dut.rst, debug=False)
    axis_source = AXISSource(dut, "axis_in", dut.axis_clk, dut.axis_rst)

    # Reset the DUT
    yield reset_dut(dut)
    yield axi_driver.core_reset()
    yield axis_source.reset()
    yield Timer(CLK_PERIOD * 10)

    # -------------------------------------------------------------------------
    # Test Execution
    # -------------------------------------------------------------------------
    # Configure DTW core for reference loading mode
    yield axi_driver.set_opmode(1)  # Load reference mode

    # Verify opmode was set correctly
    control_reg = yield axi_driver.get_control()
    assert dut.dut.w_dtw_core_mode.value == 1, "DTW core mode should be 1 (load ref)"
    assert control_reg == (1 << 2), "Control register opmode bits incorrect"

    # Set reference length
    ref_length = 200
    yield axi_driver.set_ref_len(ref_length)
    assert dut.dut.r_ref_len.value == ref_length, "Internal ref_len mismatch"

    ref_len_readback = yield axi_driver.get_ref_len()
    assert ref_len_readback == ref_length, "AXI ref_len readback mismatch"

    # Start the reference loading process
    yield axi_driver.set_rs(1)
    assert dut.dut.w_dtw_core_rs.value == 1, "Run/stop signal should be set"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should be empty initially"

    # Send reference data via AXI Stream
    reference_data = [[i + 20 for i in range(200)]]
    yield axis_source.send_raw_data(reference_data)

    # Wait for data to be loaded into reference memory
    yield Timer(CLK_PERIOD * 250)

    # -------------------------------------------------------------------------
    # Test Validation
    # -------------------------------------------------------------------------
    # Verify reference memory contents
    for i in range(0, 200):
        actual_value = dut.dut.dc.inst_dtw_core_ref_mem.MEM[i].value.integer
        expected_value = reference_data[0][i]
        assert actual_value == expected_value, \
            f"Ref mem[{i}] mismatch: expected={expected_value}, actual={actual_value}"

    # Verify loading completed successfully
    assert dut.dut.dc.r_load_done.value.integer == 1, "Load done flag should be set"
    assert dut.dut.dc.r_state.value.integer == 0, "DTW core should return to IDLE state"


###############################################################################
## Test query processing
###############################################################################
@cocotb.test(skip = True)
def test_load_query(dut):
    # -------------------------------------------------------------------------
    # Test Setup
    # -------------------------------------------------------------------------
    dut._log.setLevel(logging.WARNING)
    dut.test_id.value = 6

    setup_dut(dut)
    axi_driver = DtwAccelDriver(dut, "aximl", dut.clk, dut.rst, debug=False)
    axis_source = AXISSource(dut, "axis_in", dut.axis_clk, dut.axis_rst)
    axis_sink = AXISSink(dut, "axis_out", dut.axis_clk, dut.axis_rst)

    # Reset all components
    yield reset_dut(dut)
    yield axi_driver.core_reset()
    yield axis_source.reset()
    yield axis_sink.reset()
    yield Timer(CLK_PERIOD * 10)

    # -------------------------------------------------------------------------
    # Test Execution - Part 1: Load Reference
    # -------------------------------------------------------------------------
    # Configure for reference loading mode
    yield axi_driver.set_opmode(1)  # Load reference mode
    control_reg = yield axi_driver.get_control()
    assert dut.dut.w_dtw_core_mode.value == 1, "Should be in load reference mode"
    assert control_reg == (1 << 2), "Control register opmode bits incorrect"

    # Load reference and query data from files
    reference_data = [[i + 20 for i in range(256)]]

    # Create query data with proper format: ID, padding, then actual query values
    query_data = [[]]
    query_data[0].append(3)  # Query ID
    query_data[0].append(0)  # Padding
    for i in range(256):
        query_data[0].append(i + 20)  # Actual query data values

    # Set reference length
    ref_length = len(reference_data[0])
    yield axi_driver.set_ref_len(ref_length)
    assert dut.dut.r_ref_len.value == ref_length, "Internal ref_len mismatch"
    assert dut.dut.dc.r_state.value.integer == 0, "DTW core should be in IDLE state"

    # Start reference loading
    yield axi_driver.set_rs(1)
    assert dut.dut.w_dtw_core_rs.value == 1, "Run/stop signal should be set"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should be empty"

    # Send reference data via AXI Stream
    yield axis_source.send_raw_data(reference_data)
    yield Timer(CLK_PERIOD * (5 + ref_length))

    # Verify reference loading completed
    assert dut.dut.dc.r_state.value.integer == 0, "Should return to IDLE after loading"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should be empty"

    # -------------------------------------------------------------------------
    # Test Execution - Part 2: Process Query
    # -------------------------------------------------------------------------
    # Switch to query processing mode
    yield axi_driver.set_opmode(0)  # Query processing mode
    control_reg = yield axi_driver.get_control()
    assert dut.dut.w_dtw_core_mode.value == 0, "Should be in query mode"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should be empty"

    # Start receiving output and send query data
    dut._log.info("Starting axis_sink.receive() before sending query data")

    # Fork receive task and send query data
    recv_coro = cocotb.fork(axis_sink.receive())
    yield axis_source.send_raw_data(query_data)

    # Wait for DTW computation and data output to complete
    yield Timer(CLK_PERIOD * (266 + ref_length))

    # Wait for the receive coroutine to complete (with timeout)
    yield recv_coro.join()

    # -------------------------------------------------------------------------
    # Test Validation
    # -------------------------------------------------------------------------
    # Read and verify DTW results
    dut._log.info(f"axis_out_tvalid: {dut.axis_out_tvalid.value}")
    dut._log.info(f"axis_out_tready: {dut.axis_out_tready.value}")
    dut._log.info(f"Received frames count: {len(axis_sink.recv_frames)}")
    dut._log.info(f"Sink FIFO empty: {dut.dut.w_sink_fifo_empty.value}")
    dut._log.info(f"Sink FIFO full: {dut.dut.w_sink_fifo_full.value}")

    result_data = axis_sink.read_data()
    dut._log.info(f"Result data: {result_data}")

    assert len(result_data) == 1, "Should have one result packet"
    assert len(result_data[0]) == 3, "Result should contain [query_id, position, distance]"

    # Expected results for this specific test data
    assert result_data[0][0] == 3, f"Query ID mismatch: expected=3, actual={result_data[0][0]}"
    assert result_data[0][1] == 24466, f"Match position mismatch: expected=24466, actual={result_data[0][1]}"
    assert result_data[0][2] == 2639, f"DTW distance mismatch: expected=2639, actual={result_data[0][2]}"

###############################################################################
## Test query processing
###############################################################################
@cocotb.test(skip = True)
def test_load_query_multiple(dut):
    """
    Test DTW processing with multiple consecutive queries.

    Loads reference data from file, then processes two identical queries
    sequentially to verify the accelerator can handle back-to-back queries.
    (Skipped - requires external data files)
    """
    # -------------------------------------------------------------------------
    # Test Setup
    # -------------------------------------------------------------------------
    dut._log.setLevel(logging.WARNING)
    dut.test_id.value = 6

    setup_dut(dut)
    axi_driver = DtwAccelDriver(dut, "aximl", dut.clk, dut.rst, debug=False)
    axis_source = AXISSource(dut, "axis_in", dut.axis_clk, dut.axis_rst)
    axis_sink = AXISSink(dut, "axis_out", dut.axis_clk, dut.axis_rst)

    # Reset all components
    yield reset_dut(dut)
    yield axi_driver.core_reset()
    yield axis_source.reset()
    yield axis_sink.reset()
    yield Timer(CLK_PERIOD * 10)

    # -------------------------------------------------------------------------
    # Test Execution - Part 1: Load Reference
    # -------------------------------------------------------------------------
    # Configure for reference loading mode
    yield axi_driver.set_opmode(1)  # Load reference mode
    control_reg = yield axi_driver.get_control()
    assert dut.dut.w_dtw_core_mode.value == 1, "Should be in load reference mode"
    assert control_reg == (1 << 2), "Control register opmode bits incorrect"

    # Load reference and query data from files
    reference_data = [[]]
    query_data = [[]]

    with open("data/reference.txt", "r") as f:
        for line in f:
            reference_data[0].append(int(line, base=2))

    with open("data/query_with_id.txt", "r") as f:
        for i, line in enumerate(f):
            query_data[0].append(int(line, base=2))
            if i == 250:
                break

    # Insert padding after query ID
    query_data[0].insert(1, 0)

    # Set reference length
    ref_length = len(reference_data[0])
    yield axi_driver.set_ref_len(ref_length)
    assert dut.dut.r_ref_len.value == ref_length, "Internal ref_len mismatch"
    assert dut.dut.dc.r_state.value.integer == 0, "DTW core should be in IDLE state"

    # Start reference loading
    yield axi_driver.set_rs(1)
    assert dut.dut.w_dtw_core_rs.value == 1, "Run/stop signal should be set"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should be empty"

    # Send reference data via AXI Stream
    yield axis_source.send_raw_data(reference_data)
    yield Timer(CLK_PERIOD * (5 + ref_length))

    # Verify reference loading completed
    assert dut.dut.dc.r_state.value.integer == 0, "Should return to IDLE after loading"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should be empty"

    # -------------------------------------------------------------------------
    # Test Execution - Part 2: Process Multiple Queries
    # -------------------------------------------------------------------------
    # Switch to query processing mode
    yield axi_driver.set_opmode(0)  # Query processing mode
    control_reg = yield axi_driver.get_control()
    assert dut.dut.w_dtw_core_mode.value == 0, "Should be in query mode"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should be empty"

    # Start receiving outputs for both queries
    cocotb.fork(axis_sink.receive())
    cocotb.fork(axis_sink.receive())

    # Send first query
    yield axis_source.send_raw_data(query_data)
    yield Timer(CLK_PERIOD * (261 + ref_length))

    # Send second query
    yield axis_source.send_raw_data(query_data)
    yield Timer(CLK_PERIOD * (261 + ref_length))

    # -------------------------------------------------------------------------
    # Test Validation
    # -------------------------------------------------------------------------
    # Read and verify DTW results for both queries
    result_data = axis_sink.read_data()

    assert len(result_data) == 2, "Should have two result packets (one per query)"
    assert len(result_data[0]) == 3, "First result should contain [query_id, position, distance]"
    assert len(result_data[1]) == 3, "Second result should contain [query_id, position, distance]"

    # Verify first query results
    assert result_data[0][0] == 3, f"Query 1 ID mismatch: expected=3, actual={result_data[0][0]}"
    assert result_data[0][1] == 24466, f"Query 1 position mismatch: expected=24466, actual={result_data[0][1]}"
    assert result_data[0][2] == 2639, f"Query 1 distance mismatch: expected=2639, actual={result_data[0][2]}"

    # Verify second query results (should be identical since same query was sent)
    assert result_data[1][0] == 3, f"Query 2 ID mismatch: expected=3, actual={result_data[1][0]}"
    assert result_data[1][1] == 24466, f"Query 2 position mismatch: expected=24466, actual={result_data[1][1]}"
    assert result_data[1][2] == 2639, f"Query 2 distance mismatch: expected=2639, actual={result_data[1][2]}"

###############################################################################
## Test query processing
###############################################################################
@cocotb.test(skip = False)
def test_load_small_query(dut):
    """
    Test DTW query processing with a small query against a large reference.

    Loads a 4000-element reference pattern, then processes a small 8-element
    query to verify DTW computation produces the expected match position and distance.
    """
    # -------------------------------------------------------------------------
    # Test Setup
    # -------------------------------------------------------------------------
    dut._log.setLevel(logging.WARNING)
    dut.test_id.value = 6

    setup_dut(dut)
    axi_driver = DtwAccelDriver(dut, "aximl", dut.clk, dut.rst, debug=False)
    axis_source = AXISSource(dut, "axis_in", dut.axis_clk, dut.axis_rst)
    axis_sink = AXISSink(dut, "axis_out", dut.axis_clk, dut.axis_rst)

    # Reset all components
    yield reset_dut(dut)
    yield axi_driver.core_reset()
    yield axis_source.reset()
    yield axis_sink.reset()
    yield Timer(CLK_PERIOD * 10)

    # -------------------------------------------------------------------------
    # Test Execution - Part 1: Load Reference
    # -------------------------------------------------------------------------
    # Configure for reference loading mode
    yield axi_driver.set_opmode(1)  # Load reference mode
    control_reg = yield axi_driver.get_control()
    assert dut.dut.w_dtw_core_mode.value == 1, "Should be in load reference mode"
    assert control_reg == (1 << 2), "Control register opmode bits incorrect"

    # Generate reference and query data
    reference_data = [[]]
    query_data = [[]]

    # Create a 4000-element reference with repeating pattern
    for i in range(4000):
        reference_data[0].append(i % 1000)

    # Create an 8-element query: ID=1, padding=0, then 6 values from ref[200:206]
    query_data[0].append(1)  # Query ID
    query_data[0].append(0)  # Padding
    for i in range(6):
        query_data[0].append(reference_data[0][i + 200])

    # Set reference length
    ref_length = len(reference_data[0])
    yield axi_driver.set_ref_len(ref_length)
    assert dut.dut.r_ref_len.value == ref_length, "Internal ref_len mismatch"
    assert dut.dut.dc.r_state.value.integer == 0, "DTW core should be in IDLE state"

    # Start reference loading
    yield axi_driver.set_rs(1)
    assert dut.dut.w_dtw_core_rs.value == 1, "Run/stop signal should be set"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should be empty"

    # Send reference data via AXI Stream
    yield axis_source.send_raw_data(reference_data)
    yield Timer(CLK_PERIOD * (5 + ref_length))

    # Verify reference loading completed
    assert dut.dut.dc.r_state.value.integer == 0, "Should return to IDLE after loading"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should be empty"

    # -------------------------------------------------------------------------
    # Test Execution - Part 2: Process Query
    # -------------------------------------------------------------------------
    # Switch to query processing mode
    yield axi_driver.set_opmode(0)  # Query processing mode
    assert dut.dut.dc.r_state.value.integer == 2, "Should enter WAIT_FOR_QUERY state"

    control_reg = yield axi_driver.get_control()
    assert dut.dut.w_dtw_core_mode.value == 0, "Should be in query mode"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should be empty"

    # Wait for mode transition to complete
    yield Timer(CLK_PERIOD * (261 + ref_length))
    assert dut.dut.dc.r_state.value.integer == 2, "Should remain in WAIT_FOR_QUERY"
    assert dut.dut.w_src_fifo_empty == 1, "Source FIFO should still be empty"

    # Start receiving output and send query data
    cocotb.fork(axis_sink.receive())
    yield axis_source.send_raw_data(query_data)

    # Wait for DTW computation to complete
    yield Timer(CLK_PERIOD * (262 + ref_length))

    # -------------------------------------------------------------------------
    # Test Validation
    # -------------------------------------------------------------------------
    # Read and verify DTW results
    result_data = axis_sink.read_data()
    dut._log.info(f"DTW result: {result_data}")

    assert len(result_data) == 1, "Should have one result packet"
    assert len(result_data[0]) == 3, "Result should contain [query_id, position, distance]"

    # Expected results: query_id=1, position=450, distance=0
    # (Note: position calculation may include offsets in hardware)
    assert result_data[0][0] == 1, f"Query ID mismatch: expected=1, actual={result_data[0][0]}"
    assert result_data[0][1] == 450, f"Match position mismatch: expected=450, actual={result_data[0][1]}"
    assert result_data[0][2] == 0, f"DTW distance mismatch: expected=0, actual={result_data[0][2]}"