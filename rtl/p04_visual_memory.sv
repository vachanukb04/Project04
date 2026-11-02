`timescale 1ns/1ps
`default_nettype none
// Episodic visual memory, NOT a pretrained semantic detector or weight trainer.
// Query descriptor: 16x16 RGB high nibbles, row-major. Search: exact L1 distance.
module p04_visual_memory (
 input wire clk,rst_n,
 input wire cfg_valid,input wire [15:0] cfg_addr,input wire [3:0] cfg_data,
 input wire start,input wire [6:0] example_count,
 input wire pixel_valid,input wire [23:0] pixel_rgb,output wire pixel_ready,
 output wire busy,output reg result_valid,
 output reg [7:0] best_slot,similarity,
 output reg [13:0] best_distance,
 output reg [7:0] mean_r,mean_g,mean_b,brightness,color_id
);
 localparam IDLE=0,LOAD=1,SEARCH=2,REPORT=3;
 reg [1:0] state;
 reg [3:0] memories[0:49151],descriptor[0:767];
 integer p,i,slot,count,diff,distance,total,best,r,g,b,luma;
 reg [31:0] sum_r,sum_g,sum_b;
 assign busy=state!=IDLE;
 assign pixel_ready=rst_n && state==LOAD;
 always @(posedge clk)begin
  if(!rst_n)begin
   state<=IDLE;result_valid<=0;best_slot<=255;similarity<=0;best_distance<=11520;
   mean_r<=0;mean_g<=0;mean_b<=0;brightness<=0;color_id<=0;
   p<=0;i<=0;slot<=0;count<=0;distance<=0;best<=11521;
   sum_r<=0;sum_g<=0;sum_b<=0;
  end else begin
   result_valid<=0;
   if(state==IDLE && cfg_valid && cfg_addr<49152)memories[cfg_addr]<=cfg_data;
   case(state)
    IDLE:if(start && !cfg_valid && example_count<=64)begin
     count<=example_count;p<=0;sum_r<=0;sum_g<=0;sum_b<=0;state<=LOAD;
     best<=11521;best_slot<=255;similarity<=0;best_distance<=11520;
    end
    LOAD:if(pixel_valid)begin
     descriptor[p*3]<=pixel_rgb[23:20];descriptor[p*3+1]<=pixel_rgb[15:12];descriptor[p*3+2]<=pixel_rgb[7:4];
     sum_r<=sum_r+pixel_rgb[23:16];sum_g<=sum_g+pixel_rgb[15:8];sum_b<=sum_b+pixel_rgb[7:0];
     if(p==255)begin
      i<=0;slot<=0;distance<=0;
      if(count==0)state<=REPORT;else state<=SEARCH;
     end else p<=p+1;
    end
    SEARCH:begin
     diff=$signed({1'b0,descriptor[i]})-$signed({1'b0,memories[slot*768+i]});
     if(diff<0)diff=-diff;
     total=distance+diff;
     if(i==767)begin
      if(total<best)begin best<=total;best_slot<=slot;end
      i<=0;distance<=0;
      if(slot==count-1)state<=REPORT;else slot<=slot+1;
     end else begin distance<=total;i<=i+1;end
    end
    REPORT:begin
     if(count!=0)begin best_distance<=best;similarity<=255-(best*255)/11520;end
     r=sum_r>>8;g=sum_g>>8;b=sum_b>>8;luma=(77*r+150*g+29*b)>>8;
     mean_r<=r;mean_g<=g;mean_b<=b;brightness<=luma;
     if(luma<50)color_id<=0;
     else if(luma>205 && r-g<20 && g-r<20 && r-b<20 && b-r<20)color_id<=1;
     else if(r>g+20 && r>b+20)color_id<=3;
     else if(g>r+20 && g>b+20)color_id<=4;
     else if(b>r+20 && b>g+20)color_id<=5;else color_id<=2;
     result_valid<=1;state<=IDLE;
    end
   endcase
  end
 end
endmodule
`default_nettype wire
