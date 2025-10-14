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
    parameter SQG_SIZE      = 256   // Squiggle size
)(
    // Main DTW signals
    input   wire                    clk,
    input   wire                    rst,

    output  reg                     busy,               // Idle: 0, busy: 1
    output  wire                    load_done,

    // Src FIFO signals
    output  wire                    src_fifo_clear,     // Src FIFO Clear signal
    output  reg                     src_fifo_rden,      // Src FIFO Read enable
    input   wire                    src_fifo_empty,     // Src FIFO Empty
    input   wire [31:0]             src_fifo_data,      // Src FIFO Data

    // debug signals
    output  wire [2:0]              dbg_state,

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
    DTW_Q_INIT = 0,
    DTW_Q_LOAD = 1,
    DTW_RUN    = 2;

/* ===============================
 * registers/wires
 * =============================== */
reg r_src_fifo_clear;

// counter
reg  [swidth-1:0]   counter;
reg                 done;

// DTW datapath signals
reg                 dp_running;         // dp core run enable
reg                 dp_last;
reg                 dp_load;            // dp core load enable

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
    .rst            (rst),
    .running        (dp_running),
    .last           (dp_last),
    .load           (dp_load),
    .stream_in      (src_fifo_data[15:0]),
    .minval         (curr_score),
    .minidx         (curr_idx),
    .ref_count      (curr_count)
);

/* ===============================
 * asynchronous logic
 * =============================== */
assign done = (counter == (SQG_SIZE - 1)); // counter[swidth]
assign load_done = done; 
assign src_fifo_clear = r_src_fifo_clear;
assign dbg_state = r_state;
assign dbg_nquery = r_dbg_nquery;
assign dbg_curr_qid = curr_qid;

/* ===============================
 * synchronous logic
 * =============================== */
// FSM State change
always @(posedge clk) begin
    if (rst) begin
        r_state <= DTW_Q_INIT;
    end else begin
        case (r_state)
        DTW_Q_INIT: begin
            if (!src_fifo_empty)
                r_state <= DTW_Q_LOAD;
        end
        DTW_Q_LOAD: begin
            if (done && !src_fifo_empty)
                r_state <= DTW_RUN;
        end
        DTW_RUN: begin
        end
        default: r_state <= DTW_Q_INIT;
        endcase
    end
end

// FSM output
always @(posedge clk) begin
    if (rst) begin
        busy                    <= 0;
        src_fifo_rden           <= 0;
        dp_running              <= 0;
        dp_last                 <= 1;
        dp_load                 <= 0;
        stall_counter           <= 0;
        r_src_fifo_clear        <= 1;
        curr_qid                <= 0;
        counter                 <= 0;
    end
    case (r_state)
        DTW_Q_INIT: begin
            busy                    <= 0;
            src_fifo_rden           <= 1;
            stall_counter           <= 0;
            r_src_fifo_clear        <= 0;
            curr_qid                <= src_fifo_data;
        end
        DTW_Q_LOAD: begin
            busy                    <= 1;
            stall_counter           <= 0;
            r_src_fifo_clear        <= 0;
            dp_running              <= 0;
            src_fifo_rden           <= 1;

            dp_load                 <= !src_fifo_empty;

            if (!src_fifo_empty)
                counter             <= done ? 0 : counter + 1;
        end
        DTW_RUN: begin
            busy                    <= 1;
            stall_counter           <= 0;
            r_src_fifo_clear        <= 0;
            dp_load                 <= 0;
            src_fifo_rden           <= 1;

            dp_running              <= !src_fifo_empty;
            dp_last                 <= done;

            if (!src_fifo_empty) begin
                counter             <= counter + 1;
            end
        end
        default: begin
            busy                    <= 0;
            src_fifo_rden           <= 0;
            dp_running              <= 0;
            stall_counter           <= 0;
            r_src_fifo_clear        <= 1;
        end
    endcase
end

endmodule