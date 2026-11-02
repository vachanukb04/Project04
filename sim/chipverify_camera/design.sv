`timescale 1ns/1ps
`default_nettype none
// Abstract RGB888 camera stream -> word-write request stream.
// SAME clock domain; not a USB, CSI receiver, CDC bridge or Mac device driver.
module p04_camera_capture #(parameter int FRAME_PIXELS=16) (
    input wire clk,rst_n,
    input wire enable, pixel_valid,pixel_sof,
    input wire [23:0] pixel_rgb,
    output wire pixel_ready,
    output wire mem_valid,input wire mem_ready,
    output wire [31:0] mem_addr,mem_data,
    output logic frame_done,frame_error,
    output logic [31:0] frame_id
);
    logic active,valid;
    logic [31:0] count,addr,data;
    assign pixel_ready=rst_n && enable && (!valid || mem_ready);
    assign mem_valid=rst_n && valid;
    assign mem_addr=addr;assign mem_data=data;
    always_ff @(posedge clk) begin
        if(!rst_n)begin
            active<=0;valid<=0;count<=0;addr<=0;data<=0;
            frame_done<=0;frame_error<=0;frame_id<=0;
        end else begin
            frame_done<=0;frame_error<=0;
            if(valid && mem_ready)begin
                valid<=0;
                if(count==$unsigned(FRAME_PIXELS))begin frame_done<=1;frame_id<=frame_id+1;end
            end
            if(pixel_valid && pixel_ready)begin
                if(pixel_sof)begin
                    if(active)frame_error<=1; // restart interrupted frame
                    active<=FRAME_PIXELS>1;count<=1;addr<=0;data<={8'b0,pixel_rgb};valid<=1;
                end else if(active)begin
                    addr<=count<<2;data<={8'b0,pixel_rgb};valid<=1;count<=count+1;
                    if(count==$unsigned(FRAME_PIXELS-1))active<=0;
                end else frame_error<=1;
            end
        end
    end
endmodule
`default_nettype wire
