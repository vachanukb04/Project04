# Verification status

## Memory engine integration

The scratchpad and memory-backed DOT4 controller are implemented with a separate integration testbench. Its four canonical files pass static compilation with zero diagnostics using pyslang 12.1.0; its generated bundle passes consistency checking. Behavioral execution of **this new suite** is pending ChipVerify. See [the memory-engine specification and run instructions](memory_engine.md). The arithmetic-run history below is separate from this new integration status.

## Completed checks

- Python numerical reference: **7 unittest methods passed**, covering packed signed operands, wrap/overflow, rounding ties and neighbors, zero/extreme multipliers, all shift values, activation clamps, invalid configuration and invalid reference API inputs.
- Static SystemVerilog compilation: **4 canonical source files parsed, type-checked and elaborated with zero diagnostics** using pyslang 12.1.0.
- Generated ChipVerify bundle consistency: checked against canonical sources with `scripts/bundle_chipverify.py --check`.

These checks are not a behavioral RTL simulation.

## Pending behavioral regression

ChipVerify Lab was opened, the design and testbench bundles were loaded, Verilator was selected, and a simulation was requested. The platform responded: **Please sign in with Google to run simulations**. Its subsequent sign-in page also states that continuing agrees to ChipVerify's Terms and Conditions. No behavioral simulator result or passing RTL regression is claimed.

The user subsequently reported a successful platform status in Safari, followed by a traced run reporting **VCD output exceeded 100 MB**, **File size limit exceeded**, and a core-dump/timeout message alongside a green success banner. The project-specific PASS line and counters have not been supplied. The resource-limited run is incomplete or failed evidence; it does not establish an arithmetic PASS or an RTL arithmetic failure.

The testbench now separates the full untraced regression from a `+WAVES` smoke run of 520 cycles. Only the full run can print `PASS Project04 arithmetic regression` and must report `exhaustive_byte_pairs=65536`. The waveform run prints `PASS Project04 waveform smoke test (not full regression)` and reports zero exhaustive pairs. Static compilation and bundle consistency were rechecked for this change; the revised modes still need execution in ChipVerify.

The testbench is designed to exercise:

- Every one of the 65536 signed INT8 bit-pattern pairs in one DOT4 byte position with the other products zero.
- Directed four-product extremes, mixed signs, zero values, and INT32 overflow.
- Directed and deterministic random eight-lane vectors, active masks, inactive accumulator preservation, and lane-specific overflow.
- Positive and negative rounding ties, shift zero and large shifts, zero multiplier, signed zero points, saturation, activation clamps, and invalid clamp ordering.
- Input bubbles, output stalls, held requests, simultaneous consume/replace and reset with pending data.
- A drained final state, required scenario counters, explicit failures and a watchdog.

The random seed is `32'hc0ffee04`; the test is deterministic. Scenario counts printed by the bench are evidence only after a completed simulator run. Exhaustive pair coverage does not imply exhaustive coverage of four-byte combinations, accumulator states or pipeline transactions.

## Reproduce non-simulation checks

```sh
python3 -m unittest discover -s tests -v
python3 scripts/bundle_chipverify.py --check
pip install -r requirements-check.txt
python3 scripts/check_sv.py
```

## Evidence to record after simulation

Record the Git commit, bundle hashes, simulator/version, compile/runtime arguments, all warnings, exit result, PASS summary and printed counts. Then change this page to distinguish the completed run from the earlier authentication blocker. Keep model accuracy and hardware timing evidence separate from arithmetic functional checks.
