/* MIT License

Copyright (c) 2022 Po Jui Shih
Copyright (c) 2022 Hassaan Saadat
Copyright (c) 2022 Sri Parameswaran
Copyright (c) 2022 Hasindu Gamaarachchi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE. */

`timescale 1ns / 1ps

module dtw_core_datapath #(
    parameter width     = 16,
    parameter SQG_SIZE  = 256
)(
    input   wire                clk,
    input   wire                rst,
    input   wire                running,        // Run enable
    input   wire                last,           // last reference
    input   wire                load,           // Load enable

    input   wire [width-1:0]    stream_in,      // input stream

    output  reg  [width-1:0]    minval,         // Minimum value
    output  reg  [31:0]         minidx,         // Position of minimum value
    output  reg  [31:0]         ref_count       // # References procesed
);

/* ===============================
 * registers/wires
 * =============================== */

integer k;

// squiggle buffer
reg     [$clog2(SQG_SIZE):0]    s_addr;
wire                    s_load_done;
reg     [width-1:0]     s_buff          [0:SQG_SIZE-1];

// stream buffer
reg     [width-1:0]     stream_in_buff [0:1];

// PE wires
wire    [width-1:0]     nw; // NW value of PE0
wire    [width-1:0]     DTW_curr        [0:SQG_SIZE-1];
wire    [width-1:0]     p_Rword         [0:SQG_SIZE-1];

reg     [width-1:0]     DTW_prev        [0:SQG_SIZE-1];
reg     [width-1:0]     DTW_pprev       [0:SQG_SIZE-1];

// PE status signals
reg     [SQG_SIZE-1:0]  running_d;
reg     [SQG_SIZE-1:0]  last_d;

/* ===============================
 * submodules
 * =============================== */

// First PE
dtw_core_pe #(
    .width(width)
) inst_dtw_core_pe_0 (
    .clk     (clk),
    .rst     (rst),
    .running (running_d[0]),
    .x       (s_buff[0]),
    .y       (stream_in_buff[1]),
    .W       (DTW_prev[0]),
    .N       (-1),
    .NW      (nw),
    .DTWc    (DTW_curr[0]),
    .yp      (p_Rword[0])
);

// Other PEs
genvar m;
generate
for (m = 1; m < SQG_SIZE; m = m + 1) begin
	dtw_core_pe #(
        .width(width)
    ) inst_dtw_core_pe_n (
        .clk    (clk),
        .rst    (rst),
        .running (running_d[m]),
        .x      (s_buff[m]),
        .y      (p_Rword[m-1]),
        .W      (DTW_prev[m]),
        .N      (DTW_prev[m-1]),
        .NW     (DTW_pprev[m-1]),
        .DTWc   (DTW_curr[m]),
        .yp     (p_Rword[m])
    );
end
endgenerate

/* ===============================
 * asynchronous logic
 * =============================== */

assign s_load_done  = s_addr[$clog2(SQG_SIZE)];
assign nw = (!last_d[0] && last_d[1]) ? 0 : -1;

/* ===============================
 * synchronous logic
 * =============================== */

// shift PE running status
always @(posedge clk) begin
    if(rst) begin
        for (k = 0; k < SQG_SIZE; k = k + 1) begin
            running_d[k] <= 0;
        end
    end else begin
        running_d[0] <= running;
        for (k = 1; k < SQG_SIZE; k = k + 1) begin
            running_d[k] <= running_d[k-1];
        end
    end
end

// shift PE last status
always @(posedge clk) begin
    if(rst) begin
        for (k = 0; k < SQG_SIZE; k = k + 1) begin
            last_d[k] <= 1;
        end
    end else begin
        if (running)
            last_d[0] <= last;
        for (k = 1; k < SQG_SIZE; k = k + 1) begin
            if (running_d[k-1])
                last_d[k] <= last_d[k-1];
        end
    end
end

// update DTW_prev and DTW_pprev
always @(posedge clk) begin
    if (rst) begin
        for(k = 0; k < SQG_SIZE; k = k + 1) begin
            DTW_prev [k] <= -1;
            DTW_pprev[k] <= -1;
        end
    end else begin
        for(k = 0; k < SQG_SIZE; k = k + 1) begin
            if(running_d[k]) begin
                DTW_prev[k] <= DTW_curr[k];
                DTW_pprev[k] <= DTW_prev[k];
            end
        end
    end
end

// load squiggle buffer
always @(posedge clk) begin
    if (rst) begin
        for(k = 0; k < SQG_SIZE; k = k + 1) begin
            s_buff[k] <= 0;
        end
    end else if (load) begin
        if (!s_load_done) begin
            s_buff[s_addr[$clog2(SQG_SIZE)-1:0]] <= stream_in_buff[0];
        end
    end
end

// squiggle buffer address
always @(posedge clk) begin
    if (rst) begin
        s_addr <= 0;
    end else if (load) begin
        if(!s_load_done) begin
            s_addr <= s_addr + 1;
        end
    end
end

// buffer stream input
always @(posedge clk) begin
    if (rst) begin
        stream_in_buff[0] <= 0;
        stream_in_buff[1] <= 0;
    end else begin
        stream_in_buff[0] <= stream_in;
        stream_in_buff[1] <= stream_in_buff[0];
    end
end

// min score and reference index update
always @(posedge clk) begin
    if (rst) begin
        minval    <= -1;
        minidx    <= 0;
        ref_count <= 0;
    end else if (last_d[SQG_SIZE-1] && running_d[SQG_SIZE-1]) begin
        if (DTW_curr[SQG_SIZE-1] < minval) begin
            minval <= DTW_curr[SQG_SIZE-1];
            minidx <= ref_count;
        end
        ref_count <= ref_count + 1;
    end
end

endmodule
