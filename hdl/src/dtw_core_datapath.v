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

    input   wire [width-1:0]    Input_squiggle, // Squiggle sample
    input   wire [width-1:0]    Rword,          // Reference sample
    input   wire [31:0]         ref_len,        // Reference length
    output  wire                done,           // Query search done
    output  wire                load_done,

    output  wire [width-1:0]    minval,         // Minimum value
    output  wire [31:0]         minidx,         // Position of minimum value
    output  wire [31:0]         ref_count       // # References procesed
);

/* ===============================
 * registers/wires
 * =============================== */
integer k;

reg     [31:0]          cycle_counter;
reg     [8:0]           squiggle_buffaddress;

reg     [width-1:0]     Squiggle_Buffer [0:SQG_SIZE-1];
reg     [width-1:0]     ref_buff0;
reg     [width-1:0]     ref_buff1;
reg     [width-1:0]     query_buff;

wire    [width-1:0]     DTW_curr        [0:SQG_SIZE-1];
wire    [width-1:0]     p_Rword         [0:SQG_SIZE-1];

reg     [width-1:0]     DTW_prev        [0:SQG_SIZE-1];
reg     [width-1:0]     DTW_pprev       [0:SQG_SIZE-1];

reg     [SQG_SIZE-1:0]  running_d;
reg     [SQG_SIZE-1:0]  last_d;

reg     [width-1:0]     Minval;
reg     [31:0]          Minidx;
reg     [31:0]          Ref_count;

/* ===============================
 * submodules
 * =============================== */
wire [width-1:0] nw;
// nw activation
assign nw = (!last_d[0] && last_d[1]) ? 0 : -1;
// First PE
dtw_core_pe #(
    .width(width)
) inst_dtw_core_pe_0 (
    .clk  (clk),
    .rst  (rst),
    .running (running_d[0]),
    .x    (Squiggle_Buffer[0]),
    .y    (ref_buff1),
    .W    (DTW_prev[0]),
    .N    (-1),
    .NW   (nw),
    .DTWc (DTW_curr[0]),
    .yp   (p_Rword[0])
);

wire runningd0 = running_d[0];
wire runningdl = running_d[SQG_SIZE-1];

wire lastd0 = last_d[0];
wire lastdl = last_d[SQG_SIZE-1];

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
        .x      (Squiggle_Buffer[m]),
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
assign minval     = Minval;
assign minidx     = Minidx;
assign ref_count  = Ref_count;
assign done       = (cycle_counter >= ref_len);
assign dbg_cycle_counter = cycle_counter;
assign load_done  = squiggle_buffaddress[8];

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

// Buffer input squiggle (twice)
always @(posedge clk) begin
    if (rst) begin
        query_buff <= 0;
    end else begin
        query_buff <= Input_squiggle;
    end
end


// Load squiggle sample value
always @(posedge clk) begin
    if (rst) begin
        for(k = 0; k < SQG_SIZE; k = k + 1) begin
            Squiggle_Buffer[k] <= 0;
        end
    end else if (load) begin
        if (!load_done) begin
            Squiggle_Buffer[squiggle_buffaddress[7:0]] <= query_buff;
        end
    end
end

// Squiggle buffer address handling
always @(posedge clk) begin
    if (rst) begin
        squiggle_buffaddress <= 0;
    end else if (load) begin
        if(!load_done) begin
            squiggle_buffaddress <= squiggle_buffaddress + 1;
        end
    end
end

// reference sample load
always @(posedge clk) begin
    if (rst) begin
        ref_buff0 <= 0;
        ref_buff1 <= 0;
    end else begin
        ref_buff0 <= Rword;
        ref_buff1 <= ref_buff0;
    end
end

// cycle counter handling
always @(posedge clk) begin
    if (rst) begin
        cycle_counter <=  0;
    end else if (running_d[SQG_SIZE-1]) begin
        cycle_counter <= cycle_counter + 1;
    end
end

// Min value and position update
always @(posedge clk) begin
    if (rst) begin
        Minval <= -1;
        Minidx <= 0;
        Ref_count <= 0;
    end else if (last_d[SQG_SIZE-1] && running_d[SQG_SIZE-1]) begin
        Minval <= DTW_curr[SQG_SIZE-1];
        Minidx <= 0;
        Ref_count <= Ref_count + 1;
    end
end

endmodule