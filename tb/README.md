# Verification

`tb_p04_arithmetic.sv` is the self-checking regression for DOT4, the eight-lane SIMD slice and requantization. It contains independent wide-integer reference functions, deterministic stimuli, ready/valid scoreboards, directed corner cases, all 65536 scalar byte pairs, coverage gates and a watchdog.

Top module: `tb_p04_arithmetic`. Compile sources in `sim/arithmetic.f`, or use the two files in `sim/chipverify/`. Default operation avoids explicit VCD dumping; optional runtime argument `+WAVES` enables it. The hosting simulator may independently generate waveforms.

**The behavioral RTL regression has not run yet:** ChipVerify requires sign-in. Static compilation passes. See [verification status](../docs/verification_status.md) for exactly which checks have completed.
