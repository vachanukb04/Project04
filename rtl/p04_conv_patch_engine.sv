`timescale 1ns/1ps
`default_nettype none
// Packed convolution patch: accumulate word_count DOT4 pairs, then write one INT32 result.
// Arrays are contiguous packed signed INT8 words. Zero-pad unused tail bytes.
module p04_conv_patch_engine (
    input wire clk, rst_n, start,
    input wire [31:0] a_addr, b_addr, dst_addr,
    input wire signed [31:0] accumulator,
    input wire [15:0] word_count,
    output wire busy, output logic done, error, overflow, rejected,
    output wire mem_req_valid, input wire mem_req_ready,
    output wire mem_req_write,
    output wire [31:0] mem_req_addr, mem_req_wdata,
    output wire [3:0] mem_req_wstrb,
    input wire mem_rsp_valid, output wire mem_rsp_ready,
    input wire [31:0] mem_rsp_rdata, input wire mem_rsp_error
);
    typedef enum logic [3:0] {IDLE, READ_A, WAIT_A, READ_B, WAIT_B,
                             ISSUE_DOT, WAIT_DOT, WRITE_RESULT, WAIT_WRITE} state_t;
    state_t state;
    logic [31:0] a_ptr, b_ptr, dst_ptr, a_word, b_word, result;
    logic signed [31:0] acc;
    logic [15:0] remaining;
    wire [32:0] span = {17'b0,word_count} << 2;
    wire bad_command = word_count==0 || (a_addr[1:0]!=0) || (b_addr[1:0]!=0) || (dst_addr[1:0]!=0)
        || ({1'b0,a_addr}+span > 33'h100000000)
        || ({1'b0,b_addr}+span > 33'h100000000);
    wire dot_ready, dot_valid, dot_overflow;
    wire signed [31:0] dot_result;
    assign busy = state != IDLE;
    assign mem_req_valid = rst_n && ((state==READ_A)||(state==READ_B)||(state==WRITE_RESULT));
    assign mem_req_write = state==WRITE_RESULT;
    assign mem_req_addr = state==READ_A ? a_ptr : state==READ_B ? b_ptr : dst_ptr;
    assign mem_req_wdata = result;
    assign mem_req_wstrb = 4'hf;
    assign mem_rsp_ready = rst_n && ((state==WAIT_A)||(state==WAIT_B)||(state==WAIT_WRITE));
    p04_dot4 u_dot (
        .clk(clk), .rst_n(rst_n), .i_valid(rst_n && state==ISSUE_DOT),
        .i_ready(dot_ready), .i_a(a_word), .i_b(b_word), .i_acc(acc),
        .o_valid(dot_valid), .o_ready(state==WAIT_DOT),
        .o_result(dot_result), .o_overflow(dot_overflow)
    );
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            state<=IDLE; done<=0; error<=0; overflow<=0; rejected<=0;
            a_ptr<=0; b_ptr<=0; dst_ptr<=0; a_word<=0; b_word<=0; acc<=0; result<=0; remaining<=0;
        end else begin
            done<=0; rejected<=0;
            if (start && busy) rejected<=1;
            case (state)
                IDLE: if (start) begin
                    a_ptr<=a_addr; b_ptr<=b_addr; dst_ptr<=dst_addr; acc<=accumulator;
                    overflow<=0; remaining<=word_count;
                    if (bad_command) begin error<=1; done<=1; state<=IDLE; end
                    else begin error<=0; state<=READ_A; end
                end
                READ_A: if (mem_req_ready) state<=WAIT_A;
                WAIT_A: if (mem_rsp_valid) begin
                    if (mem_rsp_error) begin error<=1; done<=1; state<=IDLE; end
                    else begin a_word<=mem_rsp_rdata; state<=READ_B; end
                end
                READ_B: if (mem_req_ready) state<=WAIT_B;
                WAIT_B: if (mem_rsp_valid) begin
                    if (mem_rsp_error) begin error<=1; done<=1; state<=IDLE; end
                    else begin b_word<=mem_rsp_rdata; state<=ISSUE_DOT; end
                end
                ISSUE_DOT: if (dot_ready) state<=WAIT_DOT;
                WAIT_DOT: if (dot_valid) begin
                    overflow<=overflow || dot_overflow;
                    if (remaining==1) begin result<=$unsigned(dot_result); state<=WRITE_RESULT; end
                    else begin
                        acc<=dot_result; remaining<=remaining-1'b1;
                        a_ptr<=a_ptr+32'd4; b_ptr<=b_ptr+32'd4; state<=READ_A;
                    end
                end
                WRITE_RESULT: if (mem_req_ready) state<=WAIT_WRITE;
                WAIT_WRITE: if (mem_rsp_valid) begin
                    error<=mem_rsp_error; done<=1; state<=IDLE;
                end
                default: begin state<=IDLE; error<=1; done<=1; end
            endcase
        end
    end
endmodule
`default_nettype wire
