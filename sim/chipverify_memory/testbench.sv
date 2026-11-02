`timescale 1ns/1ps
`default_nettype none
module tb_p04_dot4_engine;
    logic clk=0;
    always #5 clk=~clk;
    logic rst_n=0, start=0;
    logic [31:0] ap=0,bp=0,dp=0;
    logic signed [31:0] acc=0;
    wire busy,done,error,overflow,rejected;
    wire ev,er,ew,sv,sr,se;
    wire [31:0] ea,ed,sd;
    wire [3:0] es;
    logic hv=0,hw=0,hr=0;
    logic [31:0] ha=0,hd=0;
    logic [3:0] hs=4'hf;
    wire mr,mv;
    int cycle_count=0, jobs=0, host_checks=0, request_stalls=0, response_stalls=0;
    always @(posedge clk) cycle_count<=cycle_count+1;
    wire request_enable=(cycle_count%3)!=0;
    wire response_enable=(cycle_count%4)!=0;
    wire engine_rsp_ready;
    assign er=busy && mr && request_enable;
    assign sv=busy && mv && response_enable;
    assign sr=busy ? (response_enable && engine_rsp_ready) : hr;
    p04_dot4_engine dut (
        .clk(clk),.rst_n(rst_n),.start(start),.a_addr(ap),.b_addr(bp),.dst_addr(dp),
        .accumulator(acc),.busy(busy),.done(done),.error(error),.overflow(overflow),.rejected(rejected),
        .mem_req_valid(ev),.mem_req_ready(er),.mem_req_write(ew),.mem_req_addr(ea),
        .mem_req_wdata(ed),.mem_req_wstrb(es),.mem_rsp_valid(sv),
        .mem_rsp_ready(engine_rsp_ready),.mem_rsp_rdata(sd),.mem_rsp_error(se)
    );
    p04_scratchpad #(.DEPTH(16)) memory (
        .clk(clk),.rst_n(rst_n),.req_valid(busy ? (ev && request_enable) : hv),
        .req_ready(mr),.req_write(busy ? ew : hw),.req_addr(busy ? ea : ha),
        .req_wdata(busy ? ed : hd),.req_wstrb(busy ? es : hs),
        .rsp_valid(mv),.rsp_ready(sr),.rsp_rdata(sd),.rsp_error(se)
    );
    always @(posedge clk) if (rst_n && busy) begin
        if (ev && !er) request_stalls++;
        if (mv && !sr) response_stalls++;
    end
    bit request_was_blocked=0;
    logic [68:0] blocked_request;
    always @(posedge clk) begin
        if (!rst_n) request_was_blocked<=0;
        else begin
            if(request_was_blocked && (!ev || {ew,ea,ed,es}!==blocked_request))
                $fatal(1,"Engine request changed while blocked");
            request_was_blocked<=ev && !er;
            blocked_request<={ew,ea,ed,es};
        end
    end

    task automatic host(input bit wr,input logic [31:0] addr,data,
                        input logic [3:0] strobes,input bit expected_error,
                        input logic [31:0] expected_data);
        if (busy) $fatal(1,"Host attempted access while engine owns memory");
        @(negedge clk); hv=1;hw=wr;ha=addr;hd=data;hs=strobes;hr=0;
        do @(posedge clk); while (!mr);
        @(negedge clk); hv=0;
        // Hold each response for two cycles and check stability.
        wait(mv); #1;
        if (se!==expected_error || (!wr && sd!==expected_data))
            $fatal(1,"Host response mismatch addr=%h data=%h error=%b",addr,sd,se);
        repeat(2) begin
            @(posedge clk); #1;
            if (!mv || se!==expected_error || (!wr && sd!==expected_data))
                $fatal(1,"Scratchpad response did not hold under backpressure");
        end
        @(negedge clk); hr=1;
        @(posedge clk); @(negedge clk);hr=0;
        host_checks++;
    endtask
    task automatic launch(input logic [31:0] a,b,d,input logic signed [31:0] initial_acc);
        @(negedge clk);ap=a;bp=b;dp=d;acc=initial_acc;start=1;
        @(posedge clk); #1;
        if (!busy) $fatal(1,"Start not accepted");
        @(negedge clk);start=0;
        // Change command pins: accepted job must use its captured configuration.
        ap=32'hffffffff;bp=32'hffffffff;dp=32'hffffffff;acc=0;
    endtask
    task automatic completion(input bit expected_error,expected_overflow);
        wait(done); #1;
        if (busy || error!==expected_error || overflow!==expected_overflow)
            $fatal(1,"Job completion flags mismatch error=%b overflow=%b",error,overflow);
        @(posedge clk);#1;if(done) $fatal(1,"Done was not a one-cycle pulse");
        jobs++;
    endtask
    initial begin
        if ($test$plusargs("WAVES")) begin
            $dumpfile("p04_memory_engine.vcd");$dumpvars(0,tb_p04_dot4_engine);
        end
        repeat(2) @(posedge clk);
        @(negedge clk);rst_n=1;
        host(1,0,32'h04030201,4'hf,0,0);
        host(1,4,32'h08070605,4'hf,0,0);
        host(1,60,32'haabbccdd,4'hf,0,0);
        host(1,60,32'h11223344,4'h5,0,0);
        host(0,60,0,0,0,32'haa22cc44);
        host(1,60,0,4'h0,0,0);
        host(0,60,0,0,0,32'haa22cc44);
        host(1,1,32'hdeadbeef,4'hf,1,0);
        host(1,64,32'hdeadbeef,4'hf,1,0);
        host(0,64,0,0,1,0);
        host(0,0,0,0,0,32'h04030201);
        launch(0,4,60,10);
        // Submit a second command while busy; it must be rejected, not queued.
        start=1;@(posedge clk);#1;
        if(!rejected || !busy) $fatal(1,"Busy command not rejected");
        @(negedge clk);start=0;
        completion(0,0);host(0,60,0,0,0,80);
        // Destination may alias a source; both reads precede the write.
        launch(0,4,0,0);completion(0,0);host(0,0,0,0,0,70);
        host(1,0,32'h80808080,4'hf,0,0);
        host(1,4,32'h80808080,4'hf,0,0);
        launch(0,4,8,32'sh7fffffff);completion(0,1);
        host(0,8,0,0,0,32'h8000ffff);
        host(1,12,32'h12345678,4'hf,0,0);
        launch(1,4,12,0);completion(1,0);
        launch(0,64,12,0);completion(1,0);
        launch(0,4,64,0);completion(1,0);
        host(0,12,0,0,0,32'h12345678);
        // Reset during operand read: no write has been issued yet.
        host(1,12,32'h12345678,4'hf,0,0);
        launch(0,4,12,0);
        rst_n=0;repeat(2) @(posedge clk);
        @(negedge clk);rst_n=1;#1;
        if(busy || done || error || overflow || rejected) $fatal(1,"Reset did not flush engine");
        host(0,12,0,0,0,32'h12345678);
        launch(0,4,12,0);completion(0,0);host(0,12,0,0,0,65536);
        if(jobs!=7 || request_stalls==0 || response_stalls==0)
            $fatal(1,"Required integration scenarios were not exercised");
        $display("PASS Project04 memory-backed DOT4 engine");
        $display("jobs=%0d host_checks=%0d request_stalls=%0d response_stalls=%0d",jobs,host_checks,request_stalls,response_stalls);
        $finish;
    end
    initial begin #100000; $fatal(1,"Memory engine watchdog timeout"); end
endmodule
`default_nettype wire
