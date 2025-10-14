/*
Distributed under the MIT license.
Copyright (c) 2022 Elton Shih (beebdev@gmail.com)

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

/*
 * Author: Elton Shih (beebdev@gmail.com)
 * Description: Core implementation for pipelined subsequence DTW algorithm
 *
 * Changes:     Author         Description
 *  03/31/2022  Elton Shih     Initial Commit
 */

`timescale 1ns / 1ps

module dtw_core #(
    parameter WIDTH         = 16,   // Data width
    parameter AXIS_WIDTH    = 32,   // AXI data width
    parameter SQG_SIZE      = 256,  // Squiggle size
    parameter REF_INIT      = 0,
    parameter REFMEM_PTR_WIDTH = 20
)(
    // Main DTW signals
    input   wire                    clk,
    input   wire                    rst,
    input   wire                    rs,

    input   wire [AXIS_WIDTH-1 : 0] ref_len,
    input   wire                    op_mode,            // Reference mode: 0, query mode: 1
    output  reg                     busy,               // Idle: 0, busy: 1
    output  wire                    load_done,

    // Src FIFO signals
    output  wire                    src_fifo_clear,     // Src FIFO Clear signal
    output  reg                     src_fifo_rden,      // Src FIFO Read enable
    input   wire                    src_fifo_empty,     // Src FIFO Empty
    input   wire [31:0]             src_fifo_data,      // Src FIFO Data

    // Sink FIFO signals
    output  reg                     sink_fifo_wren,     // Sink FIFO Write enable
    input   wire                    sink_fifo_full,     // Sink FIFO Full
    output  reg [31:0]              sink_fifo_data,     // Sink FIFO Data
    output  reg                     sink_fifo_last,     // Sink FIFO Last

    // debug signals
    output  wire [2:0]              dbg_state,
    output  wire [REFMEM_PTR_WIDTH-1:0]             dbg_addr_ref,

    output  wire [31:0]             dbg_cycle_counter,
    output  wire [31:0]             dbg_nquery,
    output  wire [31:0]             dbg_curr_qid,

    // new dtw signals
    output  reg  [31:0]             curr_qid,
    output  wire [31:0]             curr_count,
    output  wire [31:0]             curr_idx,
    output  wire [31:0]             curr_score
);

// temp stuff to delete
assign dbg_cycle_counter = 0;

/* ===============================
 * local parameters
 * =============================== */
// Squiggle size
localparam swidth = $clog2(SQG_SIZE);

// Operation mode
localparam
    MODE_NORMAL = 1'b0,
    MODE_LOAD_QUERY = 1'b1;

// FSM states
localparam [2:0] // n states
    IDLE       = 0,
    DTW_Q_INIT = 1,
    DTW_Q_LOAD = 2,
    DTW_RUN    = 3,
    DTW_DONE   = 4;

/* ===============================
 * registers/wires
 * =============================== */
reg r_src_fifo_clear;

// Ref mem signals
reg  [REFMEM_PTR_WIDTH-1:0] addr_ref;          // Read address for refmem 

// counter
reg  [swidth:0]     counter;
reg                 done;

// DTW datapath signals
reg                 dp_rst;             // dp core reset
reg                 dp_running;         // dp core run enable
reg                 dp_last;
reg                 dp_load;            // dp core load enable
wire                dp_done;            // dp core done
wire                dp_load_done;       // dp core load done

// FSM state
reg [2:0] r_state;

// Others
reg [1:0] stall_counter;
reg [31:0] r_dbg_nquery;

/* ===============================
 * submodules
 * =============================== */

// DTW datapath
dtw_core_datapath #(
    .width      (WIDTH),
    .SQG_SIZE   (SQG_SIZE)
) inst_dtw_core_datapath (
    .clk            (clk),
    .rst            (dp_rst),
    .running        (dp_running),
    .last           (dp_last),
    .load           (dp_load),
    .Input_squiggle (src_fifo_data[15:0]),
    .Rword          (src_fifo_data[15:0]),
    .ref_len        (ref_len),
    .done           (dp_done),
    .load_done      (dp_load_done),
    .minval         (curr_score),
    .minidx         (curr_idx),
    .ref_count      (curr_count)
);

/* ===============================
 * asynchronous logic
 * =============================== */
assign done = (counter == SQG_SIZE); // counter[swidth]
assign load_done = done; 
assign src_fifo_clear = r_src_fifo_clear;
assign dbg_state = r_state;
assign dbg_addr_ref = addr_ref;
assign dbg_nquery = r_dbg_nquery;
assign dbg_curr_qid = curr_qid;

/* ===============================
 * synchronous logic
 * =============================== */
// FSM State change
always @(posedge clk) begin
    if (rst) begin
        r_state <= IDLE;
    end else begin
        case (r_state)
        IDLE: begin
            if (rs && op_mode == MODE_LOAD_QUERY && dp_load_done == 0)
                r_state <= DTW_Q_INIT;
        end
        DTW_Q_INIT: begin
            if (!src_fifo_empty)
                r_state <= DTW_Q_LOAD;
        end
        DTW_Q_LOAD: begin
            if (done && !src_fifo_empty)
                r_state <= DTW_RUN;
        end
        DTW_RUN: begin
            if (dp_done)
                r_state <= DTW_DONE;
        end
        DTW_DONE: begin
        end
        default: r_state <= IDLE;
        endcase
    end
end

// FSM output
always @(posedge clk) begin
    case (r_state)
    IDLE: begin
        busy                    <= 0;
        src_fifo_rden           <= 0;
        sink_fifo_wren          <= 0;
        addr_ref                <= 0;
        dp_rst                  <= 1;
        dp_running              <= 0;
        dp_last                 <= 1;
        dp_load                 <= 0;
        stall_counter           <= 0;
        r_src_fifo_clear        <= 1;
        sink_fifo_last          <= 0;
        curr_qid                <= 0;
        counter                 <= 1;
    end
    DTW_Q_INIT: begin
        busy                    <= 1;
        src_fifo_rden           <= 1;
        sink_fifo_wren          <= 0;
        dp_rst                  <= 0;
        stall_counter           <= 0;
        r_src_fifo_clear        <= 0;
        curr_qid                <= src_fifo_data;
    end
    DTW_Q_LOAD: begin
        busy                    <= 1;
        sink_fifo_wren          <= 0;
        dp_rst                  <= 0;
        stall_counter           <= 0;
        r_src_fifo_clear        <= 0;
        dp_running              <= 0;
        addr_ref                <= 0;
        src_fifo_rden           <= 1;

        dp_load                 <= !src_fifo_empty;

        if (!src_fifo_empty)
            counter             <= done ? 1 : counter + 1;
    end
    DTW_RUN: begin
        busy                    <= 1;
        sink_fifo_wren          <= 0;
        dp_rst                  <= 0;
        stall_counter           <= 0;
        r_src_fifo_clear        <= 0;
        dp_load                 <= 0;
        src_fifo_rden           <= 1;

        dp_running              <= !src_fifo_empty;

        if (!done && !src_fifo_empty) begin
            counter             <= counter + 1;
            dp_last             <= 0;
        end else if (done) begin
            if (!src_fifo_empty) begin
                dp_last         <= 1;
            end
        end

    end
    DTW_DONE: begin
        busy                    <= 1;
        src_fifo_rden           <= 0;
        dp_rst                  <= 0;
        dp_running              <= 0;

        // Serialize output
        if (!sink_fifo_full) begin
            stall_counter       <= stall_counter + 1;

            if (stall_counter == 0) begin
                sink_fifo_last  <= 0;
                sink_fifo_wren  <= 1;
                sink_fifo_data  <= curr_qid;
            end else if (stall_counter == 1) begin
                sink_fifo_last  <= 0;
                sink_fifo_wren  <= 1;
                sink_fifo_data  <= curr_idx;
            end else if (stall_counter == 2) begin
                sink_fifo_last  <= 0;
                sink_fifo_wren  <= 1;
                sink_fifo_data  <= {16'b0, curr_score};
            end else begin
                sink_fifo_last  <= 1;
                sink_fifo_wren  <= 0;
                sink_fifo_data  <= 0;
                r_dbg_nquery    <= r_dbg_nquery + 1;
            end
        end 
    end
    default: begin
        busy                    <= 0;
        src_fifo_rden           <= 0;
        sink_fifo_wren          <= 0;
        addr_ref                <= 0;
        dp_rst                  <= 1;
        dp_running              <= 0;
        stall_counter           <= 0;
        r_src_fifo_clear        <= 1;
        sink_fifo_last          <= 0;
    end
    endcase
end

endmodule