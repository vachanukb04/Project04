`timescale 1ns/1ps
`default_nettype none

// One-entry elastic signed INT8 DOT4 pipeline. Byte zero is bits [7:0].
// Overflow wraps the INT32 result and raises o_overflow for that transaction.
module p04_dot4 (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                i_valid,
    output wire                i_ready,
    input  wire [31:0]         i_a,
    input  wire [31:0]         i_b,
    input  wire signed [31:0]  i_acc,
    output logic               o_valid,
    input  wire                o_ready,
    output logic signed [31:0] o_result,
    output logic               o_overflow
);
    wire signed [15:0] product [0:3];
    wire signed [33:0] extended [0:3];
    wire signed [33:0] total;
    genvar k;
    generate
        for (k = 0; k < 4; k = k + 1) begin : g_product
            assign product[k] = $signed(i_a[k*8 +: 8])
                              * $signed(i_b[k*8 +: 8]);
            assign extended[k] = $signed({{18{product[k][15]}}, product[k]});
        end
    endgenerate
    assign total = $signed({{2{i_acc[31]}}, i_acc})
                 + extended[0] + extended[1] + extended[2] + extended[3];
    assign i_ready = rst_n && (!o_valid || o_ready);

    // Active-low synchronous reset; pending transactions are discarded.
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            o_valid    <= 1'b0;
            o_result   <= '0;
            o_overflow <= 1'b0;
        end else if (i_ready) begin
            o_valid <= i_valid;
            if (i_valid) begin
                o_result   <= $signed(total[31:0]);
                o_overflow <= (total > 34'sd2147483647)
                           || (total < -34'sd2147483648);
            end
        end
    end
endmodule

`default_nettype wire
