# ChipVerify Lab workflow

Use ChipVerify Lab as the initial simulation environment. Its simulation guide lists Verilator for SystemVerilog and Icarus for Verilog:

https://chipverify.com/chipverify-lab/simulate-verify

For each implemented block:

1. Add its RTL, dependencies, and self-checking testbench to a Lab project.
2. Select SystemVerilog and the Verilator simulator where available.
3. Set the testbench top and dependency compile order using the current Lab controls.
4. Run simulation and inspect all compilation diagnostics and test results.
5. Inspect waveforms for interface timing and reset behavior.
6. Record the exact Git commit, simulator settings, and pass or failure evidence.

Record backend and version details from the actual environment when available. No ChipVerify project has been created and no compatibility or passing simulation result is claimed yet.
