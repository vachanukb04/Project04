`timescale 1ns/1ps
`default_nettype none

// Eight lockstep DOT4 lanes. Lane zero occupies bits [31:0].
// Masked lanes preserve their input accumulator and cannot report overflow.
module p04_simd_dot4 (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         i_valid,
    output wire         i_ready,
    input  wire [7:0]   i_mask,
    input  wire [255:0] i_a,
    input  wire [255:0] i_b,
    input  wire [255:0] i_acc,
    output wire         o_valid,
    input  wire         o_ready,
    output logic [7:0]  o_mask,
    output wire [255:0] o_result,
    output wire [7:0]   o_overflow
);
    wire [7:0] lane_ready;
    wire [7:0] lane_valid;
    assign i_ready = lane_ready[0];
    assign o_valid = lane_valid[0];

    genvar lane;
    generate
        for (lane = 0; lane < 8; lane = lane + 1) begin : g_lane
            wire signed [31:0] lane_result;
            assign o_result[lane*32 +: 32] = $unsigned(lane_result);
            p04_dot4 u_dot4 (
                .clk(clk), .rst_n(rst_n),
                .i_valid(i_valid), .i_ready(lane_ready[lane]),
                .i_a(i_mask[lane] ? i_a[lane*32 +: 32] : 32'b0),
                .i_b(i_b[lane*32 +: 32]),
                .i_acc($signed(i_acc[lane*32 +: 32])),
                .o_valid(lane_valid[lane]), .o_ready(o_ready),
                .o_result(lane_result),
                .o_overflow(o_overflow[lane])
            );
        end
    endgenerate

    always_ff @(posedge clk) begin
        if (!rst_n)
            o_mask <= '0;
        else if (i_valid && i_ready)
            o_mask <= i_mask;
    end
endmodule

`default_nettype wire
