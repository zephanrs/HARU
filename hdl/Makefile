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


# Pytest runner mode (recommended)
.PHONY: pytest
pytest:
	@mkdir -p build
	@cd build && pytest ../test_runner.py -v -s --tb=short

# defaults
SIM ?= verilator
TOPLEVEL_LANG ?= verilog
SIM_BUILD ?= build/sim_build

# Traditional cocotb mode (legacy)
.PHONY: cocotb
cocotb:
	@mkdir -p build
	@$(MAKE) sim SIM_BUILD=build/sim_build COCOTB_RESULTS_FILE=build/results.xml

ifneq ($(TOPLEVEL_LANG),verilog)
all:
	@echo "Skipping; DTW accel does not support VHDL at the top-level"
clean::

else

ifeq ($(SIM),icarus)
COMPILE_ARGS+=-I$(PWD)/src/
else ifeq ($(SIM),verilator)
COMPILE_ARGS+=-Wno-fatal
COMPILE_ARGS+=--trace --trace-structs
COMPILE_ARGS+=-I$(PWD)/src/
else
COMPILE_ARGS+=+incdir+$(PWD)/src/
endif

#DUT
VERILOG_SOURCES += $(PWD)/src/dtw_accel.v \
				   $(PWD)/src/axi_lite_slave.v \
				   $(PWD)/src/axis_2_fifo.v \
				   $(PWD)/src/fifo.v \
				   $(PWD)/src/fifo_2_axis.v \
				   $(PWD)/src/dtw_core.v \
				   $(PWD)/src/dtw_core_datapath.v \
				   $(PWD)/src/dtw_core_ref_mem.v \
				   $(PWD)/src/dtw_core_pe.v \

#Test Bench
VERILOG_SOURCES += $(PWD)/src/sim/tb_dtw_accel.v

TOPLEVEL = tb_dtw_accel
GPI_IMPL := vpi

MODULE = tests.test_dtw_accel

include $(shell cocotb-config --makefiles)/Makefile.sim

endif

# Clean up all build artifacts
clean::
	rm -rf .pytest_cache __pycache__ tests/__pycache__ tb/__pycache__ build
