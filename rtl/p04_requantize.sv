`timescale 1ns/1ps
`default_nettype none

// q = clamp(round_nearest_ties_away(acc * multiplier / 2**shift) + zero_point).
// multiplier is a NONNEGATIVE 31-bit integer; shift is unsigned 0..63.
// This explicit project contract is not a claim of LiteRT bit equivalence.
module p04_requantize (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               i_valid,
    output wire               i_ready,
    input  wire signed [31:0] i_acc,
    input  wire [30:0]        i_multiplier,
    input  wire [5:0]         i_shift,
    input  wire signed [7:0]  i_zero_point,
    input  wire signed [7:0]  i_clamp_min,
    input  wire signed [7:0]  i_clamp_max,
    output logic              o_valid,
    input  wire               o_ready,
    output logic signed [7:0] o_result,
    output logic              o_error
);
    wire signed [63:0] product;
    wire [64:0] magnitude;
    wire [64:0] half;
    wire [64:0] rounded_magnitude;
    wire signed [65:0] rounded;
    wire signed [65:0] shifted;
    wire signed [65:0] minimum;
    wire signed [65:0] maximum;
    wire config_error;
    wire signed [7:0] quantized;

    assign product = i_acc * $signed({1'b0, i_multiplier});
    assign magnitude = product[63]
                     ? (~{product[63], product} + 65'd1)
                     : {product[63], product};
    assign half = (i_shift == 0) ? 65'd0 : (65'd1 << (i_shift - 6'd1));
    assign rounded_magnitude = (magnitude + half) >> i_shift;
    assign rounded = product[63] ? -$signed({1'b0, rounded_magnitude})
                                 : $signed({1'b0, rounded_magnitude});
    assign shifted = rounded + $signed({{58{i_zero_point[7]}}, i_zero_point});
    assign minimum = $signed({{58{i_clamp_min[7]}}, i_clamp_min});
    assign maximum = $signed({{58{i_clamp_max[7]}}, i_clamp_max});
    assign config_error = (i_clamp_min > i_clamp_max);
    assign quantized = config_error ? 8'sd0
                     : (shifted < minimum) ? i_clamp_min
                     : (shifted > maximum) ? i_clamp_max
                     : $signed(shifted[7:0]);
    assign i_ready = rst_n && (!o_valid || o_ready);

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            o_valid  <= 1'b0;
            o_result <= '0;
            o_error  <= 1'b0;
        end else if (i_ready) begin
            o_valid <= i_valid;
            if (i_valid) begin
                o_result <= quantized;
                o_error  <= config_error;
            end
        end
    end
endmodule

`default_nettype wire
