`timescale 1ns/1ps
`default_nettype none
// Template; generate the complete bench using scripts/bundle_image_nn.py.
module tb_p04_image_nn;
    logic clk=0;always #5 clk=~clk;
    logic rst_n=0,start=0;
    logic [31:0] ap=0,bp=0,dp=0;
    logic signed [31:0] acc=0;
    logic [15:0] words=0;
    wire busy,done,error,overflow,rejected;
    wire ev,er,ew,sv,sr,se,engine_rsp_ready,mr,mv;
    wire [31:0] ea,ed,sd;
    wire [3:0] es;
    logic hv=0,hw=0,hr=0;
    logic [31:0] ha=0,hd=0;
    int ticks=0,jobs=0,checks=0;
    always @(posedge clk)ticks<=ticks+1;
    wire req_gate=(ticks%3)!=0;
    wire rsp_gate=(ticks%4)!=0;
    assign er=busy && mr && req_gate;
    assign sv=busy && mv && rsp_gate;
    assign sr=busy ? (rsp_gate && engine_rsp_ready) : hr;
    p04_conv_patch_engine dut (
        .clk(clk),.rst_n(rst_n),.start(start),.a_addr(ap),.b_addr(bp),.dst_addr(dp),
        .accumulator(acc),.word_count(words),.busy(busy),.done(done),.error(error),
        .overflow(overflow),.rejected(rejected),.mem_req_valid(ev),.mem_req_ready(er),
        .mem_req_write(ew),.mem_req_addr(ea),.mem_req_wdata(ed),.mem_req_wstrb(es),
        .mem_rsp_valid(sv),.mem_rsp_ready(engine_rsp_ready),.mem_rsp_rdata(sd),.mem_rsp_error(se)
    );
    p04_scratchpad #(.DEPTH(128)) memory (
        .clk(clk),.rst_n(rst_n),.req_valid(busy ? (ev && req_gate) : hv),
        .req_ready(mr),.req_write(busy ? ew : hw),.req_addr(busy ? ea : ha),
        .req_wdata(busy ? ed : hd),.req_wstrb(busy ? es : 4'hf),
        .rsp_valid(mv),.rsp_ready(sr),.rsp_rdata(sd),.rsp_error(se)
    );
    logic pv=0,por=1;
    logic [23:0] pixel=0;
    wire pir,pov;
    wire [23:0] pixel_q;
    p04_rgb888_to_int8 prep(.clk(clk),.rst_n(rst_n),.i_valid(pv),.i_ready(pir),
        .i_rgb(pixel),.o_valid(pov),.o_ready(por),.o_rgb(pixel_q));
    task automatic host(input bit wr,input logic [31:0] addr,data,
                        input bit expected_error,input logic [31:0] expected);
        if(busy)$fatal(1,"Memory ownership violation");
        @(negedge clk);hv=1;hw=wr;ha=addr;hd=data;hr=0;
        do @(posedge clk);while(!mr);
        @(negedge clk);hv=0;wait(mv);#1;
        if(se!==expected_error || (!wr && sd!==expected))
            $fatal(1,"Memory mismatch address=%h got=%h expected=%h error=%b",addr,sd,expected,se);
        @(negedge clk);hr=1;@(posedge clk);@(negedge clk);hr=0;checks++;
    endtask
    task automatic run_job(input logic [31:0] a,b,d,input logic [15:0] n,
                           input logic signed [31:0] bias,input bit err,ov);
        @(negedge clk);ap=a;bp=b;dp=d;words=n;acc=bias;start=1;
        @(posedge clk);#1;
        @(negedge clk);start=0;
        ap=32'hffffffff;bp=32'hffffffff;dp=32'hffffffff;words=0;acc=0;
        if(jobs==0 && busy)begin
            start=1;@(posedge clk);#1;
            if(!rejected)$fatal(1,"Busy convolution command not rejected");
            @(negedge clk);start=0;
        end
        if(!done)wait(done);
        #1;
        if(busy || error!==err || overflow!==ov)$fatal(1,"Convolution job flags error=%b overflow=%b",error,overflow);
        @(posedge clk);#1;if(done)$fatal(1,"Done pulse too long");jobs++;
    endtask
    bit blocked=0;
    logic [68:0] prior_request;
    always @(posedge clk) begin
        if(!rst_n)blocked<=0;
        else begin
            if(blocked && (!ev || {ew,ea,ed,es}!==prior_request))$fatal(1,"Request changed under stall");
            blocked<=ev&&!er;prior_request<={ew,ea,ed,es};
        end
    end
    initial begin
        if($test$plusargs("WAVES"))begin $dumpfile("p04_image_nn.vcd");$dumpvars(0,tb_p04_image_nn);end
        repeat(2)@(posedge clk);@(negedge clk);rst_n=1;
        // 256 RGB input triplets. Independent subtract-128 reference.
        for(int p=0;p<256;p++)begin
            @(negedge clk);pv=1;pixel={8'(p),8'(255-p),8'(p^85)};
            @(posedge clk);#1;
            if(!pov || $signed(pixel_q[23:16])!==8'(p-128)
               || $signed(pixel_q[15:8])!==8'(127-p)
               || $signed(pixel_q[7:0])!==8'((p^85)-128))$fatal(1,"Pixel conversion mismatch");
        end
        @(negedge clk);pv=0;por=0;#1;
        if(!pov)$fatal(1,"Expected held pixel");
        repeat(3)begin @(posedge clk);#1;if(!pov || pir)$fatal(1,"Pixel stall mismatch");end
        @(negedge clk);por=1;@(posedge clk);#1;if(pov)$fatal(1,"Pixel output did not drain");
        // Image output (0,0), learned channel 0
        host(1,32'd0,32'h00000000,0,0);
        host(1,32'd4,32'h89008e90,0,0);
        host(1,32'd8,32'h0000008d,0,0);
        host(1,32'd12,32'h00989900,0,0);
        host(1,32'd16,32'h00009790,0,0);
        host(1,32'd20,32'h99940000,0,0);
        host(1,32'd24,32'h00938f00,0,0);
        host(1,32'd128,32'h2c141f00,0,0);
        host(1,32'd132,32'h662c5e7f,0,0);
        host(1,32'd136,32'hebdbff47,0,0);
        host(1,32'd140,32'he2c4abdf,0,0);
        host(1,32'd144,32'h0407cdb9,0,0);
        host(1,32'd148,32'hddd4f2ff,0,0);
        host(1,32'd152,32'h00e8dcf2,0,0);
        run_job(0,128,256,7,32'h00000000,0,0);
        host(0,256,0,0,32'hfffff894);
        $display("image_patch=0 expected_acc=-1900 matched");
        // Image output (0,0), learned channel 1
        host(1,32'd0,32'h00000000,0,0);
        host(1,32'd4,32'h89008e90,0,0);
        host(1,32'd8,32'h0000008d,0,0);
        host(1,32'd12,32'h00989900,0,0);
        host(1,32'd16,32'h00009790,0,0);
        host(1,32'd20,32'h99940000,0,0);
        host(1,32'd24,32'h00938f00,0,0);
        host(1,32'd128,32'hdfd7c2fb,0,0);
        host(1,32'd132,32'he2fbe481,0,0);
        host(1,32'd136,32'hf3fd08ef,0,0);
        host(1,32'd140,32'hdf0ac2f7,0,0);
        host(1,32'd144,32'hf915e5e7,0,0);
        host(1,32'd148,32'h1dda14fe,0,0);
        host(1,32'd152,32'h00241e1f,0,0);
        run_job(0,128,256,7,32'h00000000,0,0);
        host(0,256,0,0,32'h00006c4d);
        $display("image_patch=1 expected_acc=27725 matched");
        // Image output (16,16), learned channel 0
        host(1,32'd0,32'h9490928f,0,0);
        host(1,32'd4,32'h8b918e8e,0,0);
        host(1,32'd8,32'h89898c8a,0,0);
        host(1,32'd12,32'h8a8f858c,0,0);
        host(1,32'd16,32'h87898c83,0,0);
        host(1,32'd20,32'h88858986,0,0);
        host(1,32'd24,32'h00858688,0,0);
        host(1,32'd128,32'h2c141f00,0,0);
        host(1,32'd132,32'h662c5e7f,0,0);
        host(1,32'd136,32'hebdbff47,0,0);
        host(1,32'd140,32'he2c4abdf,0,0);
        host(1,32'd144,32'h0407cdb9,0,0);
        host(1,32'd148,32'hddd4f2ff,0,0);
        host(1,32'd152,32'h00e8dcf2,0,0);
        run_job(0,128,256,7,32'h00000000,0,0);
        host(0,256,0,0,32'h00001277);
        $display("image_patch=2 expected_acc=4727 matched");
        // Image output (16,16), learned channel 1
        host(1,32'd0,32'h9490928f,0,0);
        host(1,32'd4,32'h8b918e8e,0,0);
        host(1,32'd8,32'h89898c8a,0,0);
        host(1,32'd12,32'h8a8f858c,0,0);
        host(1,32'd16,32'h87898c83,0,0);
        host(1,32'd20,32'h88858986,0,0);
        host(1,32'd24,32'h00858688,0,0);
        host(1,32'd128,32'hdfd7c2fb,0,0);
        host(1,32'd132,32'he2fbe481,0,0);
        host(1,32'd136,32'hf3fd08ef,0,0);
        host(1,32'd140,32'hdf0ac2f7,0,0);
        host(1,32'd144,32'hf915e5e7,0,0);
        host(1,32'd148,32'h1dda14fe,0,0);
        host(1,32'd152,32'h00241e1f,0,0);
        run_job(0,128,256,7,32'h00000000,0,0);
        host(0,256,0,0,32'h0000aa1b);
        $display("image_patch=3 expected_acc=43547 matched");
        // Image output (64,80), learned channel 0
        host(1,32'd0,32'h02cbd5f5,0,0);
        host(1,32'd4,32'hf5e6f0d0,0,0);
        host(1,32'd8,32'he4e505d0,0,0);
        host(1,32'd12,32'hf3f7e716,0,0);
        host(1,32'd16,32'hd5fbdcfd,0,0);
        host(1,32'd20,32'hddd60ec9,0,0);
        host(1,32'd24,32'h00caeff6,0,0);
        host(1,32'd128,32'h2c141f00,0,0);
        host(1,32'd132,32'h662c5e7f,0,0);
        host(1,32'd136,32'hebdbff47,0,0);
        host(1,32'd140,32'he2c4abdf,0,0);
        host(1,32'd144,32'h0407cdb9,0,0);
        host(1,32'd148,32'hddd4f2ff,0,0);
        host(1,32'd152,32'h00e8dcf2,0,0);
        run_job(0,128,256,7,32'h00000000,0,0);
        host(0,256,0,0,32'hffffed12);
        $display("image_patch=4 expected_acc=-4846 matched");
        // Image output (64,80), learned channel 1
        host(1,32'd0,32'h02cbd5f5,0,0);
        host(1,32'd4,32'hf5e6f0d0,0,0);
        host(1,32'd8,32'he4e505d0,0,0);
        host(1,32'd12,32'hf3f7e716,0,0);
        host(1,32'd16,32'hd5fbdcfd,0,0);
        host(1,32'd20,32'hddd60ec9,0,0);
        host(1,32'd24,32'h00caeff6,0,0);
        host(1,32'd128,32'hdfd7c2fb,0,0);
        host(1,32'd132,32'he2fbe481,0,0);
        host(1,32'd136,32'hf3fd08ef,0,0);
        host(1,32'd140,32'hdf0ac2f7,0,0);
        host(1,32'd144,32'hf915e5e7,0,0);
        host(1,32'd148,32'h1dda14fe,0,0);
        host(1,32'd152,32'h00241e1f,0,0);
        run_job(0,128,256,7,32'h00000000,0,0);
        host(0,256,0,0,32'h000037c2);
        $display("image_patch=5 expected_acc=14274 matched");
        // Image output (120,100), learned channel 0
        host(1,32'd0,32'h7f7d7d7d,0,0);
        host(1,32'd4,32'h7f7f7c7f,0,0);
        host(1,32'd8,32'h7d7d7d7f,0,0);
        host(1,32'd12,32'h7f7c7f7f,0,0);
        host(1,32'd16,32'h7d7d7f7f,0,0);
        host(1,32'd20,32'h7c7f7e7d,0,0);
        host(1,32'd24,32'h007f7e7e,0,0);
        host(1,32'd128,32'h2c141f00,0,0);
        host(1,32'd132,32'h662c5e7f,0,0);
        host(1,32'd136,32'hebdbff47,0,0);
        host(1,32'd140,32'he2c4abdf,0,0);
        host(1,32'd144,32'h0407cdb9,0,0);
        host(1,32'd148,32'hddd4f2ff,0,0);
        host(1,32'd152,32'h00e8dcf2,0,0);
        run_job(0,128,256,7,32'h00000000,0,0);
        host(0,256,0,0,32'hfffff9cc);
        $display("image_patch=6 expected_acc=-1588 matched");
        // Image output (120,100), learned channel 1
        host(1,32'd0,32'h7f7d7d7d,0,0);
        host(1,32'd4,32'h7f7f7c7f,0,0);
        host(1,32'd8,32'h7d7d7d7f,0,0);
        host(1,32'd12,32'h7f7c7f7f,0,0);
        host(1,32'd16,32'h7d7d7f7f,0,0);
        host(1,32'd20,32'h7c7f7e7d,0,0);
        host(1,32'd24,32'h007f7e7e,0,0);
        host(1,32'd128,32'hdfd7c2fb,0,0);
        host(1,32'd132,32'he2fbe481,0,0);
        host(1,32'd136,32'hf3fd08ef,0,0);
        host(1,32'd140,32'hdf0ac2f7,0,0);
        host(1,32'd144,32'hf915e5e7,0,0);
        host(1,32'd148,32'h1dda14fe,0,0);
        host(1,32'd152,32'h00241e1f,0,0);
        run_job(0,128,256,7,32'h00000000,0,0);
        host(0,256,0,0,32'hffff42dc);
        $display("image_patch=7 expected_acc=-48420 matched");
        // Directed reductions: two packed words and sticky overflow.
        host(1,0,32'h01010101,0,0);host(1,4,32'h01010101,0,0);
        host(1,128,32'h01010101,0,0);host(1,132,32'h01010101,0,0);
        run_job(0,128,256,2,5,0,0);host(0,256,0,0,13);
        host(1,0,32'h80808080,0,0);host(1,4,32'h80808080,0,0);
        host(1,128,32'h80808080,0,0);host(1,132,32'h80808080,0,0);
        run_job(0,128,256,2,32'sh7fffffff,0,1);host(0,256,0,0,32'h8001ffff);
        run_job(0,128,256,0,0,1,0);
        run_job(32'hfffffffc,128,256,2,0,1,0);
        host(1,508,0,0,0);
        run_job(0,508,256,2,0,1,0); // second weight read outside physical RAM
        host(0,256,0,0,32'h8001ffff); // failed jobs must not overwrite destination
        if(jobs!=13)$fatal(1,"Wrong job count");
        $display("PASS Project04 real-image convolution patches");
        $display("real_image_patches=8 jobs=%0d pixel_triplets=256 host_checks=%0d",jobs,checks);
        $display("Scope: first learned convolution accumulations only; object labels come from software reference");
        $finish;
    end
    initial begin #1000000;$fatal(1,"Image NN watchdog timeout");end
endmodule
`default_nettype wire
