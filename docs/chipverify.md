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
7. For the full regression, keep runtime arguments empty and do not add tracing flags. The testbench has a 1 ms watchdog and runs 66600 stimulus cycles; a browser/server quota can stop a run before completion. A missing waveform is expected for this mode.

## Short waveform run

Use the latest `sim/chipverify/testbench.sv` from GitHub: the earlier version traced the entire regression and could exceed ChipVerify's 100 MB output limit.

| Setting | Value |
| --- | --- |
| Compilation arguments | `--timing --trace-vcd --trace-depth 1 --top-module tb_p04_arithmetic` |
| Runtime arguments | `+WAVES` |
| Test length | 512 directed/random stimulus cycles plus 8 drain cycles |
| Expected completion | `PASS Project04 waveform smoke test (not full regression)` |
| Expected exhaustive count | `exhaustive_byte_pairs=0` |
| Waveform file | `p04_arithmetic.vcd` |

`+WAVES` now selects a separate short test, not a full-regression trace. Its checks still cover ready/valid behavior, stalls, reset, signed arithmetic, masks and requantization, but do not execute the exhaustive byte-pair phase. A waveform-smoke PASS must never be recorded as a full-regression PASS. The full regression without `+WAVES` still requires all 65536 pairs.

Verilator documents that `--trace-depth 1` limits recording to top-level signals. The `$dumpvars` depth argument does not provide the same reliable control for Verilator. See the [Verilator tracing FAQ](https://verilator.org/guide/latest/faq.html). The bounded cycle count reduces waveform growth; the file size on ChipVerify has not yet been measured for this version.

The hosting site may independently enable tracing. If a file-size limit, timeout or core dump appears, treat that run as failed or incomplete even if the site also displays a green success banner. Require the correct PASS line and counts.

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
