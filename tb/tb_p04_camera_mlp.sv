`timescale 1ns/1ps
module tb_p04_camera_mlp;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,cfg_valid=0,start=0,pixel_valid=0;
 reg [1:0] cfg_kind=0;
 reg [14:0] cfg_addr=0;
 reg signed [31:0] cfg_data=0;
 reg [4:0] class_count=2;
 reg [7:0] min_confidence=153;
 reg [23:0] pixel_rgb=0;
 wire pixel_ready,busy,result_valid;
 wire [7:0] class_id,confidence,mean_r,mean_g,mean_b,brightness,color_id;
 p04_camera_mlp dut(.*);
 reg [7:0] w1[0:24575],w2[0:511];
 reg [31:0] b1[0:31],b2[0:15];
 reg [23:0] frame[0:255];
 string model_dir,frame_path,result_path;
 integer n,fd,classes_arg,threshold_arg;
 task config_word(input integer kind,addr,input reg [31:0] data);
 begin @(negedge clk);cfg_valid=1;cfg_kind=kind;cfg_addr=addr;cfg_data=data;end
 endtask
 initial begin
  if(!$value$plusargs("MODEL=%s",model_dir))$fatal(1,"Missing MODEL");
  if(!$value$plusargs("FRAME=%s",frame_path))$fatal(1,"Missing FRAME");
  if(!$value$plusargs("RESULT=%s",result_path))$fatal(1,"Missing RESULT");
  if(!$value$plusargs("CLASSES=%d",classes_arg))$fatal(1,"Missing CLASSES");
  if(!$value$plusargs("THRESHOLD=%d",threshold_arg))threshold_arg=153;
  if(classes_arg<2 || classes_arg>16 || threshold_arg<0 || threshold_arg>255)$fatal(1,"Bad configuration");
  class_count=classes_arg;min_confidence=threshold_arg;
  $readmemh({model_dir,"/w1.hex"},w1);$readmemh({model_dir,"/b1.hex"},b1);
  $readmemh({model_dir,"/w2.hex"},w2);$readmemh({model_dir,"/b2.hex"},b2);
  $readmemh(frame_path,frame);
  repeat(3)@(negedge clk);rst_n=1;
  for(n=0;n<24576;n=n+1)config_word(0,n,{{24{w1[n][7]}},w1[n]});
  for(n=0;n<32;n=n+1)config_word(1,n,b1[n]);
  for(n=0;n<512;n=n+1)config_word(2,n,{{24{w2[n][7]}},w2[n]});
  for(n=0;n<16;n=n+1)config_word(3,n,b2[n]);
  // Cancel a partial frame with reset; model RAM must survive for the real frame.
  @(negedge clk);cfg_valid=0;start=1;
  @(negedge clk);start=0;pixel_valid=1;pixel_rgb=24'habcdef;
  repeat(3)@(negedge clk);
  pixel_valid=0;rst_n=0;
  @(negedge clk);
  if(busy || result_valid || class_id!=255)$fatal(1,"Reset did not clear an in-flight frame");
  rst_n=1;start=1;
  @(negedge clk);start=0;
  for(n=0;n<256;n=n+1)begin
   if(!pixel_ready)$fatal(1,"Pixel receiver stalled unexpectedly");
   pixel_valid=1;pixel_rgb=frame[n];
   @(negedge clk);
   // Exercise input bubbles as well as consecutive samples.
   if(n%17==0)begin pixel_valid=0;@(negedge clk);end
  end
  pixel_valid=0;
  wait(result_valid);@(negedge clk);
  if((^{class_id,confidence,mean_r,mean_g,mean_b,brightness,color_id}) === 1'bx)$fatal(1,"Unknown result / invalid model files");
  fd=$fopen(result_path,"w");if(!fd)$fatal(1,"Cannot open result");
  $fdisplay(fd,"%0d %0d %0d %0d %0d %0d %0d",class_id,confidence,mean_r,mean_g,mean_b,brightness,color_id);
  $fclose(fd);$display("PASS Project04 RTL camera MLP completed");$finish;
 end
 initial begin #2000000;$fatal(1,"Timeout");end
endmodule
