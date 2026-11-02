`timescale 1ns/1ps
module tb_p04_visual_memory;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,cfg_valid=0,start=0,pixel_valid=0;
 reg [15:0] cfg_addr=0;
 reg [3:0] cfg_data=0;
 reg [6:0] example_count=0;
 reg [23:0] pixel_rgb=0;
 wire pixel_ready,busy,result_valid;
 wire [7:0] best_slot,similarity,mean_r,mean_g,mean_b,brightness,color_id;
 wire [13:0] best_distance;
 p04_visual_memory dut(.*);
 reg [3:0] memories[0:49151];
 reg [23:0] frame[0:255];
 string memory_path,frame_path,result_path,descriptor_path;
 integer count_arg,n,fd;
 initial begin
  if(!$value$plusargs("MEMORY=%s",memory_path))$fatal(1,"Missing MEMORY");
  if(!$value$plusargs("FRAME=%s",frame_path))$fatal(1,"Missing FRAME");
  if(!$value$plusargs("RESULT=%s",result_path))$fatal(1,"Missing RESULT");
  if(!$value$plusargs("DESCRIPTOR=%s",descriptor_path))$fatal(1,"Missing DESCRIPTOR");
  if(!$value$plusargs("COUNT=%d",count_arg))$fatal(1,"Missing COUNT");
  if(count_arg<0 || count_arg>64)$fatal(1,"Bad example count");
  example_count=count_arg;
  $readmemh(frame_path,frame);
  if(count_arg>0)$readmemh(memory_path,memories,0,count_arg*768-1);
  repeat(3)@(negedge clk);rst_n=1;
  for(n=0;n<count_arg*768;n=n+1)begin
   @(negedge clk);cfg_valid=1;cfg_addr=n;cfg_data=memories[n];
  end
  @(negedge clk);cfg_valid=0;start=1;
  @(negedge clk);start=0;pixel_valid=1;pixel_rgb=24'h123456;
  repeat(3)@(negedge clk);
  pixel_valid=0;rst_n=0;@(negedge clk);
  if(busy || result_valid || best_slot!=255)$fatal(1,"Reset failed");
  rst_n=1;start=1;@(negedge clk);start=0;
  for(n=0;n<256;n=n+1)begin
   if(!pixel_ready)$fatal(1,"Unexpected pixel stall");
   pixel_valid=1;pixel_rgb=frame[n];@(negedge clk);
   if(n%19==0)begin pixel_valid=0;@(negedge clk);end
  end
  pixel_valid=0;wait(result_valid);@(negedge clk);
  if((^{best_slot,similarity,best_distance,mean_r,mean_g,mean_b,brightness,color_id})===1'bx)$fatal(1,"Unknown result");
  fd=$fopen(result_path,"w");if(!fd)$fatal(1,"Cannot open result");
  $fdisplay(fd,"%0d %0d %0d %0d %0d %0d %0d %0d",best_slot,similarity,best_distance,mean_r,mean_g,mean_b,brightness,color_id);
  $fclose(fd);
  fd=$fopen(descriptor_path,"w");if(!fd)$fatal(1,"Cannot open descriptor");
  for(n=0;n<768;n=n+1)begin
   if((^dut.descriptor[n])===1'bx)$fatal(1,"Unknown descriptor");
   $fdisplay(fd,"%h",dut.descriptor[n]);
  end
  $fclose(fd);$display("PASS Project04 RTL visual memory");$finish;
 end
 initial begin #4000000;$fatal(1,"Timeout");end
endmodule
