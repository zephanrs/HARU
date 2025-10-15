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

    input   wire                    sdtw,

    // status signals
    output  reg                     busy,               // Idle: 0, busy: 1
    output  wire                    load_done,
    output  reg  [1:0]              curr_state,

    // src axi-stream
    input   wire                    src_axis_tvalid,
    output  reg                     src_axis_tready,
    input   wire                    src_axis_tlast,
    input   wire [AXIS_WIDTH-1:0]   src_axis_tdata,

    // output signals
    output  reg  [31:0]             curr_qid,
    output  wire [31:0]             curr_count,
    output  wire [31:0]             curr_idx,
    output  wire [31:0]             curr_pos,
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
    .stream_in      (src_axis_tdata[15:0]),
    .minval         (curr_score[15:0]),
    .minidx         (curr_idx),
    .minpos         (curr_pos),
    .ref_count      (curr_count),
    .sdtw           (sdtw)
);

/* ===============================
 * asynchronous logic
 * =============================== */

assign done = (counter == 255); // swidth'(SQG_SIZE-1) isn't synthesizable
assign load_done = (curr_state == DTW_RUN); 
assign curr_score[31:16] = 0;

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
                if (src_axis_tvalid && src_axis_tready)
                    curr_state <= DTW_Q_LOAD;
            end
            DTW_Q_LOAD: begin
                if (done && src_axis_tvalid)
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
        src_axis_tready         <= 0;
        dp_running              <= 0;
        dp_last                 <= 1;
        dp_load                 <= 0;
        curr_qid                <= 0;
        counter                 <= 0;
    end else case (curr_state)
        DTW_Q_INIT: begin
            src_axis_tready         <= 1;
            curr_qid                <= src_axis_tdata;
        end
        DTW_Q_LOAD: begin
            busy                    <= 1;
            dp_load                 <= src_axis_tvalid;

            if (src_axis_tvalid)
                counter             <= counter + 1;
        end
        DTW_RUN: begin
            dp_load                 <= 0;
            dp_running              <= src_axis_tvalid;
            dp_last                 <= src_axis_tlast;
        end
        default: begin end
    endcase
end

endmodule
