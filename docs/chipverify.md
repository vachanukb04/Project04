# ChipVerify Lab workflow

Use ChipVerify Lab as the initial simulation environment. Its simulation guide lists Verilator for SystemVerilog and Icarus for Verilog:

https://chipverify.com/chipverify-lab/simulate-verify

## Run the first arithmetic regression

1. Sign in to ChipVerify Lab using your own account. Its sign-in page states that continuing accepts its Terms and Conditions.
2. Create a project for the arithmetic milestone.
3. Add `sim/chipverify/design.sv` and `sim/chipverify/testbench.sv` from this repository. If your workspace uses the default `design.v` and `testbench.v` editors, paste the corresponding full bundle into each editor and select the SystemVerilog backend.
4. Select **Verilator (SystemVerilog)** and compile the design before the testbench.
5. Use compilation arguments `--timing --top-module tb_p04_arithmetic`. Leave runtime arguments empty for the first run.
6. Run simulation. A successful completed test prints `PASS Project04 arithmetic regression`, accepted counts, `exhaustive_byte_pairs=65536`, scenario counts and then finishes. Any fatal error, timeout, compilation failure or missing PASS is a failure or incomplete run.
7. Optionally use runtime argument `+WAVES` to request a VCD. The testbench has a 1 ms watchdog and runs 66600 stimulus cycles; a browser/server quota can stop a run before completion.

Do not compile both the bundle and the canonical RTL files together: that duplicates module definitions. To use canonical files instead, compile the four paths in `sim/arithmetic.f` with the same top.

Regenerate bundles after editing canonical sources:

```sh
python3 scripts/bundle_chipverify.py
python3 scripts/bundle_chipverify.py --check
```

## General block workflow

For each implemented block:

1. Add its RTL, dependencies, and self-checking testbench to a Lab project.
2. Select SystemVerilog and the Verilator simulator where available.
3. Set the testbench top and dependency compile order using the current Lab controls.
4. Run simulation and inspect all compilation diagnostics and test results.
5. Inspect waveforms for interface timing and reset behavior.
6. Record the exact Git commit, simulator settings, and pass or failure evidence.

Record backend and version details from the actual environment when available. The initial bundle was loaded into an unsigned browser workspace; requesting simulation produced a Google sign-in requirement. No saved ChipVerify project or passing behavioral run is claimed. The waveform viewer also reported that WebGL was unavailable in that browser, independently of the simulation sign-in requirement.

See [verification status](verification_status.md) and [the arithmetic contract](arithmetic_spec.md).
