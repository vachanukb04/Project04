`timescale 1ns/1ps
`default_nettype none
// Independent unsigned RGB888 -> signed RGB INT8 centering stage.
// R occupies [23:16], G [15:8], B [7:0]. q[channel] = pixel[channel]-128.
// No resize, interpolation or model-specific normalization is implied.
module p04_rgb888_to_int8 (
    input wire clk,rst_n,i_valid,
    output wire i_ready,
    input wire [23:0] i_rgb,
    output logic o_valid,
    input wire o_ready,
    output logic [23:0] o_rgb
);
    assign i_ready=rst_n && (!o_valid || o_ready);
    always_ff @(posedge clk) begin
        if (!rst_n) begin o_valid<=0;o_rgb<=0;end
        else if(i_ready) begin
            o_valid<=i_valid;
            if(i_valid)o_rgb<=i_rgb ^ 24'h808080;
        end
    end
endmodule
`default_nettype wire
