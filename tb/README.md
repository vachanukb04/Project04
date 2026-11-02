# Verification

`tb_p04_arithmetic.sv` is the self-checking regression for DOT4, the eight-lane SIMD slice and requantization. It contains independent wide-integer reference functions, deterministic stimuli, ready/valid scoreboards, directed corner cases, all 65536 scalar byte pairs, coverage gates and a watchdog.

Top module: `tb_p04_arithmetic`. Compile sources in `sim/arithmetic.f`, or use the two files in `sim/chipverify/`. The default mode runs the full 66600-cycle regression without explicit VCD dumping. Runtime argument `+WAVES` selects a separate 520-cycle waveform smoke test, including a drain phase. The hosting simulator may independently generate waveforms.

The short waveform test is not exhaustive. Its PASS line explicitly says `waveform smoke test (not full regression)`. For the full regression, require `PASS Project04 arithmetic regression` and `exhaustive_byte_pairs=65536`. See [the two run configurations](../docs/chipverify.md).

**Full behavioral RTL verification is pending:** the user reported a run that hit ChipVerify's waveform file-size limit without providing the project-specific PASS output. Static compilation passes. See [verification status](../docs/verification_status.md) for exactly which checks have completed.
