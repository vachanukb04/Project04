`timescale 1ns/1ps
`default_nettype none
// Single-port synchronous word memory. Requests use BYTE addresses.
// Writes commit at request acceptance; every request receives one response.
module p04_scratchpad #(parameter int DEPTH = 256) (
    input wire clk, rst_n,
    input wire req_valid, output wire req_ready,
    input wire req_write, input wire [31:0] req_addr, req_wdata,
    input wire [3:0] req_wstrb,
    output logic rsp_valid, input wire rsp_ready,
    output logic [31:0] rsp_rdata, output logic rsp_error
);
    logic [31:0] mem [0:DEPTH-1];
    wire bad_addr = (req_addr[1:0] != 0) || (req_addr[31:2] >= 30'($unsigned(DEPTH)));
    assign req_ready = rst_n && (!rsp_valid || rsp_ready);
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            rsp_valid <= 0; rsp_rdata <= 0; rsp_error <= 0;
        end else if (req_ready) begin
            rsp_valid <= req_valid;
            if (req_valid) begin
                rsp_error <= bad_addr;
                rsp_rdata <= 0;
                if (!bad_addr) begin
                    if (req_write) begin
                        for (int b=0; b<4; b++)
                            if (req_wstrb[b]) mem[req_addr[31:2]][b*8 +: 8] <= req_wdata[b*8 +: 8];
                    end else rsp_rdata <= mem[req_addr[31:2]];
                end
            end
        end
    end
    // Memory contents deliberately survive reset and are uninitialized at startup.
endmodule
`default_nettype wire
