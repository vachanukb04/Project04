`timescale 1ns/1ps
`default_nettype none
module tb_p04_camera_capture;
    logic clk=0;always #5 clk=~clk;
    logic rst_n=0,enable=1,pv=0,sof=0,mready=0;
    logic [23:0] rgb=0;
    wire ready,mv,done,error;
    wire [31:0] addr,data,id;
    int writes=0,frames=0,errors=0,ticks=0;
    p04_camera_capture #(.FRAME_PIXELS(4)) dut(
        .clk(clk),.rst_n(rst_n),.enable(enable),.pixel_valid(pv),.pixel_sof(sof),
        .pixel_rgb(rgb),.pixel_ready(ready),.mem_valid(mv),.mem_ready(mready),
        .mem_addr(addr),.mem_data(data),.frame_done(done),.frame_error(error),.frame_id(id));
    always @(negedge clk)begin ticks=ticks+1;mready=(ticks%3)!=0;end
    bit blocked=0;
    logic [63:0] held;
    always @(posedge clk)begin
        if(!rst_n)blocked<=0;
        else begin
            if(blocked && (!mv || {addr,data}!==held))$fatal(1,"Write changed under stall");
            blocked<=mv&&!mready;held<={addr,data};
            if(mv&&mready)begin
                if(addr!==$unsigned(writes*4) || data!==32'h00010203+$unsigned(writes))
                    $fatal(1,"Captured pixel mismatch addr=%h data=%h",addr,data);
                writes++;
            end
        end
        #1;if(done)frames++;if(error)errors++;
    end
    task automatic pixel(input bit first,input logic[23:0] value);
        @(negedge clk);pv=1;sof=first;rgb=value;
        do @(posedge clk);while(!ready);
        @(negedge clk);pv=0;sof=0;
    endtask
    initial begin
        if($test$plusargs("WAVES"))begin $dumpfile("camera_capture.vcd");$dumpvars(0,tb_p04_camera_capture);end
        repeat(2)@(posedge clk);@(negedge clk);rst_n=1;
        pixel(1,24'h010203);pixel(0,24'h010204);pixel(0,24'h010205);pixel(0,24'h010206);
        repeat(5)@(posedge clk);#2;
        if(writes!=4 || frames!=1 || id!=1 || errors!=0)$fatal(1,"Frame completion mismatch");
        pixel(0,24'hbadbad);repeat(2)@(posedge clk);#2;
        if(errors!=1 || writes!=4)$fatal(1,"Stray pixel not rejected");
        @(negedge clk);rst_n=0;@(posedge clk);#2;
        if(mv || done || error || id!=0)$fatal(1,"Reset mismatch");
        $display("PASS Project04 camera capture stream");
        $display("pixels=4 frames=1 stray_pixel_errors=1");$finish;
    end
    initial begin #10000;$fatal(1,"Camera capture watchdog timeout");end
endmodule
`default_nettype wire
