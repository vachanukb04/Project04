`timescale 1ns/1ps
`default_nettype none
// Fixed 16x16 RGB, 768 -> 32 ReLU -> up to 16 classes.
// All inference, approximate softmax confidence, and crop attributes are RTL.
// Config writes are accepted only while idle. Reset does not erase model RAM.
module p04_camera_mlp (
 input wire clk, rst_n,
 input wire cfg_valid, input wire [1:0] cfg_kind,
 input wire [14:0] cfg_addr, input wire signed [31:0] cfg_data,
 input wire start, input wire [4:0] class_count, input wire [7:0] min_confidence,
 input wire pixel_valid, input wire [23:0] pixel_rgb, output wire pixel_ready,
 output wire busy, output reg result_valid,
 output reg [7:0] class_id, confidence, mean_r, mean_g, mean_b, brightness, color_id
);
 localparam IDLE=0, LOAD=1, HIDDEN=2, OUTPUTS=3, FIND=4, PROB=5, REPORT=6;
 reg [2:0] state;
 reg signed [7:0] w1 [0:24575], w2 [0:511];
 reg signed [31:0] b1 [0:31], b2 [0:15];
 reg signed [7:0] pixels [0:767];
 reg [6:0] hidden [0:31];
 reg signed [31:0] logits [0:15];
 integer p, i, h, c, classes, best_index;
 reg [7:0] threshold;
 reg signed [31:0] acc, best;
 reg [31:0] sum_r,sum_g,sum_b,prob_sum;
 reg signed [31:0] total;
 integer r,g,b,luma;
 function automatic [15:0] exp_approx(input integer delta);
 integer bin;
 begin
  bin=delta>>>9; // logits Q11: quarter-unit bins, floor toward max
  case(bin)
   0: exp_approx=16'd65535;
   1: exp_approx=16'd51039;
   2: exp_approx=16'd39749;
   3: exp_approx=16'd30957;
   4: exp_approx=16'd24109;
   5: exp_approx=16'd18776;
   6: exp_approx=16'd14623;
   7: exp_approx=16'd11388;
   8: exp_approx=16'd8869;
   9: exp_approx=16'd6907;
   10: exp_approx=16'd5379;
   11: exp_approx=16'd4190;
   12: exp_approx=16'd3263;
   13: exp_approx=16'd2541;
   14: exp_approx=16'd1979;
   15: exp_approx=16'd1541;
   16: exp_approx=16'd1200;
   17: exp_approx=16'd935;
   18: exp_approx=16'd728;
   19: exp_approx=16'd567;
   20: exp_approx=16'd442;
   21: exp_approx=16'd344;
   22: exp_approx=16'd268;
   23: exp_approx=16'd209;
   24: exp_approx=16'd162;
   25: exp_approx=16'd127;
   26: exp_approx=16'd99;
   27: exp_approx=16'd77;
   28: exp_approx=16'd60;
   29: exp_approx=16'd47;
   30: exp_approx=16'd36;
   31: exp_approx=16'd28;
   default: exp_approx=0;
  endcase
 end
 endfunction
 assign busy=state!=IDLE;
 assign pixel_ready=state==LOAD && rst_n;
 always @(posedge clk) begin
  if(!rst_n)begin
   state<=IDLE;result_valid<=0;class_id<=255;confidence<=0;
   mean_r<=0;mean_g<=0;mean_b<=0;brightness<=0;color_id<=0;
   p<=0;i<=0;h<=0;c<=0;classes<=0;threshold<=0;acc<=0;best<=0;best_index<=0;
   sum_r<=0;sum_g<=0;sum_b<=0;prob_sum<=0;
  end else begin
   result_valid<=0;
   if(state==IDLE && cfg_valid)begin
    case(cfg_kind)
     0: if(cfg_addr<24576)w1[cfg_addr]<=cfg_data[7:0];
     1: if(cfg_addr<32)b1[cfg_addr]<=cfg_data;
     2: if(cfg_addr<512)w2[cfg_addr]<=cfg_data[7:0];
     3: if(cfg_addr<16)b2[cfg_addr]<=cfg_data;
    endcase
   end
   case(state)
    IDLE: if(start && !cfg_valid && class_count>=2 && class_count<=16)begin
     classes<=class_count;threshold<=min_confidence;state<=LOAD;p<=0;
     sum_r<=0;sum_g<=0;sum_b<=0;
    end
    LOAD: if(pixel_valid)begin
     pixels[3*p]   <=$signed({1'b0,pixel_rgb[23:20]})-8;
     pixels[3*p+1] <=$signed({1'b0,pixel_rgb[15:12]})-8;
     pixels[3*p+2] <=$signed({1'b0,pixel_rgb[7:4]})-8;
     sum_r<=sum_r+pixel_rgb[23:16];sum_g<=sum_g+pixel_rgb[15:8];sum_b<=sum_b+pixel_rgb[7:0];
     if(p==255)begin state<=HIDDEN;h<=0;i<=0;acc<=b1[0];end
     else p<=p+1;
    end
    HIDDEN: begin
     total=acc+pixels[i]*w1[h*768+i];
     if(i==767)begin
      if(total<=0)hidden[h]<=0;
      else if((total>>>4)>127)hidden[h]<=127;
      else hidden[h]<=total>>>4;
      i<=0;
      if(h==31)begin state<=OUTPUTS;c<=0;acc<=b2[0];end
      else begin h<=h+1;acc<=b1[h+1];end
     end else begin acc<=total;i<=i+1;end
    end
    OUTPUTS: begin
     total=acc+$signed({1'b0,hidden[i]})*w2[c*32+i];
     if(i==31)begin
      logits[c]<=total;i<=0;
      if(c==classes-1)begin state<=FIND;c<=0;best<=-32'sh7fffffff;best_index<=0;end
      else begin c<=c+1;acc<=b2[c+1];end
     end else begin acc<=total;i<=i+1;end
    end
    FIND: begin
     if(logits[c]>best)begin best<=logits[c];best_index<=c;end
     if(c==classes-1)begin state<=PROB;c<=0;prob_sum<=0;end else c<=c+1;
    end
    PROB: begin
     prob_sum<=prob_sum+exp_approx(best-logits[c]);
     if(c==classes-1)state<=REPORT;else c<=c+1;
    end
    REPORT: begin
     // Maximum class always contributes exp(0), so denominator is nonzero.
     confidence<=(32'd65535*255)/prob_sum;
     if(((32'd65535*255)/prob_sum)>=threshold)class_id<=best_index;else class_id<=255;
     r=sum_r>>8;g=sum_g>>8;b=sum_b>>8;luma=(77*r+150*g+29*b)>>8;
     mean_r<=r;mean_g<=g;mean_b<=b;brightness<=luma;
     if(luma<50)color_id<=0;else if(luma>205 && r-g<20 && g-r<20 && r-b<20 && b-r<20)color_id<=1;
     else if(r>g+20 && r>b+20)color_id<=3;
     else if(g>r+20 && g>b+20)color_id<=4;
     else if(b>r+20 && b>g+20)color_id<=5;
     else color_id<=2;
     result_valid<=1;state<=IDLE;
    end
   endcase
  end
 end
endmodule
`default_nettype wire
