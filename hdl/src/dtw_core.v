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
    parameter WIDTH         = 16,   // data width
    parameter AXIS_WIDTH    = 32,   // axi data width
    parameter SQG_SIZE      = 256   // squiggle size
)(
    // main dtw signals
    input   wire                    clk,
    input   wire                    rst,

    output  reg                     busy,               // Idle: 0, busy: 1
    output  wire                    load_done,
    output  reg  [1:0]              curr_state,

    // src fifo signals
    output  reg                     src_fifo_clear,     // src fifo Clear signal
    output  reg                     src_fifo_rden,      // src fifo Read enable
    input   wire                    src_fifo_empty,     // src fifo Empty
    input   wire [31:0]             src_fifo_data,      // src fifo Data

    // output signals
    output  reg  [31:0]             curr_qid,
    output  wire [31:0]             curr_count,
    output  wire [31:0]             curr_idx,
    output  wire [31:0]             curr_score
);

/* ===============================
 * local parameters
 * =============================== */

// squiggle size
localparam swidth = $clog2(SQG_SIZE);

// fsm states
localparam [1:0]
    DTW_Q_INIT = 0,
    DTW_Q_LOAD = 1,
    DTW_RUN    = 2;

/* ===============================
 * registers/wires
 * =============================== */

// counter
reg  [swidth-1:0]   counter;
reg                 done;

// dtw datapath signals
reg                 dp_running;         // dp core run enable
reg                 dp_last;            // dp core last reference event
reg                 dp_load;            // dp core load enable

/* ===============================
 * submodules
 * =============================== */

// dtw datapath
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
assign load_done = (curr_state == DTW_RUN); 

/* ===============================
 * synchronous logic
 * =============================== */

// fsm state change
always @(posedge clk) begin
    if (rst) begin
        curr_state <= DTW_Q_INIT;
    end else begin
        case (curr_state)
            DTW_Q_INIT: begin
                if (!src_fifo_empty)
                    curr_state <= DTW_Q_LOAD;
            end
            DTW_Q_LOAD: begin
                if (done && !src_fifo_empty)
                    curr_state <= DTW_RUN;
            end
            default: begin end
        endcase
    end
end

// fsm output
always @(posedge clk) begin
    if (rst) begin
        busy                    <= 0;
        src_fifo_rden           <= 0;
        dp_running              <= 0;
        dp_last                 <= 1;
        dp_load                 <= 0;
        src_fifo_clear          <= 1;
        curr_qid                <= 0;
        counter                 <= 0;
    end else case (curr_state)
        DTW_Q_INIT: begin
            src_fifo_rden           <= 1;
            src_fifo_clear          <= 0;
            curr_qid                <= src_fifo_data;
        end
        DTW_Q_LOAD: begin
            busy                    <= 1;
            dp_load                 <= !src_fifo_empty;

            if (!src_fifo_empty)
                counter             <= done ? 0 : counter + 1;
        end
        DTW_RUN: begin
            dp_load                 <= 0;
            dp_running              <= !src_fifo_empty;
            dp_last                 <= done;

            if (!src_fifo_empty) begin
                counter             <= counter + 1;
            end
        end
        default: begin end
    endcase
end

endmodule