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

`timescale 1ps / 1ps

`define MAJOR_VERSION       1
`define MINOR_VERSION       0
`define REVISION            0

`define MAJOR_RANGE         31:28
`define MINOR_RANGE         27:20
`define REVISION_RANGE      19:16
`define VERSION_PAD_RANGE   15:0

module dtw_accel #(
    parameter ADDR_WIDTH            = 16,
    parameter DATA_WIDTH            = 32,

    parameter AXIS_DATA_WIDTH       = 32,
    parameter AXIS_KEEP_WIDTH       = (AXIS_DATA_WIDTH / 8),
    parameter AXIS_DATA_USER_WIDTH  = 0,
    parameter FIFO_DATA_WIDTH       = AXIS_DATA_WIDTH,
    parameter FIFO_DEPTH            = 4,
    parameter INVERT_AXI_RESET      = 1,
    parameter INVERT_AXIS_RESET     = 1
)(
    input  wire                             S_AXI_clk,
    input  wire                             S_AXI_rst,

    // Write Address Channel
    input  wire                             S_AXI_awvalid,
    input  wire [ADDR_WIDTH - 1: 0]         S_AXI_awaddr,
    output wire                             S_AXI_awready,

    // Write Data Channel
    input  wire                             S_AXI_wvalid,
    output wire                             S_AXI_wready,
    input  wire [DATA_WIDTH - 1: 0]         S_AXI_wdata,

    // Write Response Channel
    output wire                             S_AXI_bvalid,
    input  wire                             S_AXI_bready,
    output wire [1:0]                       S_AXI_bresp,

    // Read Address Channel
    input  wire                             S_AXI_arvalid,
    output wire                             S_AXI_arready,
    input  wire [ADDR_WIDTH - 1: 0]         S_AXI_araddr,

    // Read Data Channel
    output wire                             S_AXI_rvalid,
    input  wire                             S_AXI_rready,
    output wire [1:0]                       S_AXI_rresp,
    output wire [DATA_WIDTH - 1: 0]         S_AXI_rdata,

    // AXI Stream

    // Input AXI Stream
    input  wire                             SRC_AXIS_clk,
    input  wire                             SRC_AXIS_rst,
    input  wire                             SRC_AXIS_tuser,
    input  wire                             SRC_AXIS_tvalid,
    output wire                             SRC_AXIS_tready,
    input  wire                             SRC_AXIS_tlast,
    input  wire [AXIS_DATA_WIDTH - 1:0]     SRC_AXIS_tdata
);

/* ===============================
 * local parameters
 * =============================== */
// Address Map
localparam  REG_CONTROL      = 0;
localparam  REG_STATUS       = 1;
localparam  REG_REF_LEN      = 2;
localparam  REG_VERSION      = 3;
localparam  REG_KEY          = 4;
localparam  REG_REF_DIN      = 6;
localparam  REG_CYCLE_CNT    = 8;
localparam  REG_NQUERY       = 10;
localparam  REG_CURR_QID     = 11;

// DTW registers
localparam  REG_QID          = 12;
localparam  REG_COUNT        = 13;
localparam  REG_IDX          = 14;
localparam  REG_SCORE        = 15;     

localparam  integer ADDR_LSB = (DATA_WIDTH / 32) + 1;
localparam  integer ADDR_BITS = 3;

localparam  MAX_ADDR = REG_KEY;

localparam REFMEM_PTR_WIDTH = 18;

/* ===============================
 * registers/wires
 * =============================== */
// User Interface
wire                            w_axi_rst;
wire                            w_axis_rst;
wire  [ADDR_WIDTH - 1 : 0]      w_reg_address;
reg                             r_reg_invalid_addr;

wire                            w_reg_in_rdy;
reg                             r_reg_in_ack_stb;
wire  [DATA_WIDTH - 1 : 0]      w_reg_in_data;

wire                            w_reg_out_req;
reg                             r_reg_out_rdy_stb;
reg   [DATA_WIDTH - 1 : 0]      r_reg_out_data;

// DTW accel
reg   [DATA_WIDTH - 1 : 0]      r_control;
wire  [DATA_WIDTH - 1 : 0]      w_status;
reg   [DATA_WIDTH - 1 : 0]      r_ref_len;
wire  [DATA_WIDTH - 1 : 0]      w_version;
wire  [DATA_WIDTH - 1 : 0]      w_key;
reg   [DATA_WIDTH - 1 : 0]      r_dbg_ref_din;
wire  [DATA_WIDTH - 1 : 0]      w_dbg_ref_dout;
wire  [DATA_WIDTH - 1 : 0]      w_dtw_core_cycle_counter;

// new DTW accel
wire  [31:0]                    w_dtw_core_qid;
wire  [31:0]                    w_dtw_core_count;
wire  [31:0]                    w_dtw_core_idx;
wire  [DATA_WIDTH - 1 : 0]      w_dtw_core_score;


// Control Register bits
wire                            w_dtw_core_rst;
wire                            w_dtw_core_rs;
wire                            w_dtw_core_mode;

// Status Register bits
wire                            w_dtw_core_busy;
wire                            w_dtw_core_load_done;

// Src FIFO
wire                            w_src_fifo_clear;
wire  [FIFO_DATA_WIDTH - 1:0]   w_src_fifo_w_data;
wire                            w_src_fifo_w_stb;
wire                            w_src_fifo_full;
wire                            w_src_fifo_not_full;

wire  [FIFO_DATA_WIDTH - 1:0]   w_src_fifo_r_data;
wire                            w_src_fifo_r_stb;
wire                            w_src_fifo_empty;
wire                            w_src_fifo_not_empty;

// dtw core debug
wire  [2:0]                     w_dtw_core_state;
wire  [31:0]                    w_dtw_core_nquery;
wire  [31:0]                    w_dtw_core_curr_qid;


/* ===============================
 * initialization
 * =============================== */
initial begin
    r_control = 0;
    r_ref_len = 4000;
end

/* ===============================
 * submodules
 * =============================== */
// Convert AXI Slave bus to a simple register/address strobe
axi_lite_slave #(
    .ADDR_WIDTH         (ADDR_WIDTH),
    .DATA_WIDTH         (DATA_WIDTH)
) axi_lite_reg_interface (
    .clk                (S_AXI_clk),
    .rst                (w_axi_rst),

    .i_awvalid          (S_AXI_awvalid),
    .i_awaddr           (S_AXI_awaddr),
    .o_awready          (S_AXI_awready),

    .i_wvalid           (S_AXI_wvalid),
    .o_wready           (S_AXI_wready),
    .i_wdata            (S_AXI_wdata),

    .o_bvalid           (S_AXI_bvalid),
    .i_bready           (S_AXI_bready),
    .o_bresp            (S_AXI_bresp),

    .i_arvalid          (S_AXI_arvalid),
    .o_arready          (S_AXI_arready),
    .i_araddr           (S_AXI_araddr),

    .o_rvalid           (S_AXI_rvalid),
    .i_rready           (S_AXI_rready),
    .o_rresp            (S_AXI_rresp),
    .o_rdata            (S_AXI_rdata),


    // Register Interface
    .o_reg_address      (w_reg_address),
    .i_reg_invalid_addr (r_reg_invalid_addr),

    // From Master
    .o_reg_in_rdy       (w_reg_in_rdy),
    .i_reg_in_ack_stb   (r_reg_in_ack_stb),
    .o_reg_in_data      (w_reg_in_data),

    // To Master
    .o_reg_out_req      (w_reg_out_req),
    .i_reg_out_rdy_stb  (r_reg_out_rdy_stb),
    .i_reg_out_data     (r_reg_out_data)
);


// AXIS src -> src FIFO
axis_2_fifo_adapter #(
    .AXIS_DATA_WIDTH    (AXIS_DATA_WIDTH)
) a2fa (
    .i_axis_tuser       (SRC_AXIS_tuser),
    .i_axis_tvalid      (SRC_AXIS_tvalid),
    .o_axis_tready      (SRC_AXIS_tready),
    .i_axis_tlast       (SRC_AXIS_tlast),
    .i_axis_tdata       (SRC_AXIS_tdata),

    .o_fifo_data        (w_src_fifo_w_data),
    .o_fifo_w_stb       (w_src_fifo_w_stb),
    .i_fifo_not_full    (w_src_fifo_not_full)
);

fifo #(
    .DEPTH              (FIFO_DEPTH),
    .WIDTH              (FIFO_DATA_WIDTH)
) src_fifo (
    .clk                (SRC_AXIS_clk),
    .rst                (w_axis_rst | w_src_fifo_clear),

    .i_fifo_w_stb       (w_src_fifo_w_stb),
    .i_fifo_w_data      (w_src_fifo_w_data),
    .o_fifo_full        (w_src_fifo_full),
    .o_fifo_not_full    (w_src_fifo_not_full),

    .i_fifo_r_stb       (w_src_fifo_r_stb),
    .o_fifo_r_data      (w_src_fifo_r_data),
    .o_fifo_empty       (w_src_fifo_empty),
    .o_fifo_not_empty   (w_src_fifo_not_empty)
);

// DTW core
dtw_core #(
    .WIDTH              (16),
    .AXIS_WIDTH         (AXIS_DATA_WIDTH)
) dc (
    .clk                (S_AXI_clk),
    .rst                (w_dtw_core_rst),
    .rs                 (w_dtw_core_rs),

    .ref_len            (r_ref_len),
    .op_mode            (w_dtw_core_mode),
    .busy               (w_dtw_core_busy),
    .load_done          (w_dtw_core_load_done),

    .src_fifo_clear     (w_src_fifo_clear),
    .src_fifo_rden      (w_src_fifo_r_stb),
    .src_fifo_empty     (w_src_fifo_empty),
    .src_fifo_data      (w_src_fifo_r_data),

    .dbg_state          (w_dtw_core_state),

    .dbg_cycle_counter  (w_dtw_core_cycle_counter),
    .dbg_nquery         (w_dtw_core_nquery),
    .dbg_curr_qid       (w_dtw_core_curr_qid),

    .curr_qid           (w_dtw_core_qid),
    .curr_count         (w_dtw_core_count),
    .curr_idx           (w_dtw_core_idx),
    .curr_score         (w_dtw_core_score)
);

/* ===============================
 * asynchronous logic
 * =============================== */
assign w_axi_rst                        = INVERT_AXI_RESET  ? ~S_AXI_rst    : S_AXI_rst;
assign w_axis_rst                       = INVERT_AXIS_RESET ? ~SRC_AXIS_rst : SRC_AXIS_rst;
assign w_version[`MAJOR_RANGE]          = `MAJOR_VERSION;
assign w_version[`MINOR_RANGE]          = `MINOR_VERSION;
assign w_version[`REVISION_RANGE]       = `REVISION;
assign w_version[`VERSION_PAD_RANGE]    = 0;
assign w_key                            = 32'h0ca7cafe;

assign w_dtw_core_rst                   = r_control[0];
assign w_dtw_core_rs                    = r_control[1];
assign w_dtw_core_mode                  = r_control[2];

assign w_status[0]                      = w_dtw_core_busy;
assign w_status[1]                      = w_dtw_core_load_done;
assign w_status[2]                      = w_src_fifo_empty;
assign w_status[3]                      = w_src_fifo_full;
assign w_status[5:4]                    = 2'b00;
assign w_status[8:6]                    = w_dtw_core_state;
assign w_status[31:9]                   = 0;

/* ===============================
 * synchronous logic
 * =============================== */
always @ (posedge S_AXI_clk) begin
    // De-assert Strobes
    r_reg_in_ack_stb    <=  0;
    r_reg_out_rdy_stb   <=  0;
    r_reg_invalid_addr  <=  0;

    if (w_axi_rst) begin
        r_reg_out_data  <=  0;

        // Reset registers
        r_control       <=  0;
        r_ref_len       <=  0;
    end else begin
        if (w_reg_in_rdy) begin
            // M_AXI to here
            case (w_reg_address[ADDR_LSB + ADDR_BITS:ADDR_LSB])
            REG_CONTROL: begin
                r_control <= w_reg_in_data;
            end
            REG_STATUS: begin
            end
            REG_REF_LEN: begin
                r_ref_len <= w_reg_in_data;
            end
            REG_VERSION: begin
            end
            REG_KEY: begin
            end
            REG_REF_DIN: begin
                r_dbg_ref_din <= w_reg_in_data;
            end
            REG_CYCLE_CNT: begin
            end
            REG_NQUERY: begin
            end
            REG_CURR_QID: begin
            end
            REG_QID: begin
            end
            REG_IDX: begin
            end
            REG_SCORE: begin
            end
            default: begin // unknown address
                $display ("Unknown address: 0x%h", w_reg_address);
                r_reg_invalid_addr <= 1;
            end
            endcase
            r_reg_in_ack_stb <= 1; // Tell AXI Slave we are done with the data
        end else if (w_reg_out_req) begin
            // Here to M_AXI
            case (w_reg_address[ADDR_LSB + ADDR_BITS:ADDR_LSB])
            REG_CONTROL: begin
                r_reg_out_data <= r_control;
            end
            REG_STATUS: begin
                r_reg_out_data <= w_status;
            end
            REG_REF_LEN: begin
                r_reg_out_data <= r_ref_len;
            end
            REG_VERSION: begin
                r_reg_out_data <= w_version;
            end
            REG_KEY: begin
                r_reg_out_data <= w_key;
            end
            REG_REF_DIN: begin
                r_reg_out_data <= r_dbg_ref_din;
            end
            REG_CYCLE_CNT: begin
                r_reg_out_data <= w_dtw_core_cycle_counter;
            end
            REG_NQUERY: begin
                r_reg_out_data <= w_dtw_core_nquery;
            end
            REG_CURR_QID: begin
                r_reg_out_data <= w_dtw_core_curr_qid;
            end
            REG_QID: begin
                r_reg_out_data <= w_dtw_core_qid;
            end
            REG_COUNT: begin
                r_reg_out_data <= w_dtw_core_count;
            end
            REG_IDX: begin
                r_reg_out_data <= w_dtw_core_idx;
            end
            REG_SCORE: begin
                r_reg_out_data <= w_dtw_core_score;
            end
            default: begin // Unknown address
                r_reg_out_data      <= 32'h00;
                r_reg_invalid_addr  <= 1;
            end
            endcase
            r_reg_out_rdy_stb <= 1; // Tell AXI Slave to send back this packet
        end
    end
end

endmodule