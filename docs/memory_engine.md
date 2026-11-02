# Memory backed DOT4 engine

## Implemented interface

`p04_scratchpad` is a single-port memory with parameter `DEPTH` (positive word count, default 256). Each word contains 32 bits. Addresses are unsigned **byte addresses**: valid addresses are aligned multiples of four below `4*DEPTH`. Four write strobes independently update bytes, least significant byte first. A zero-strobe write is acknowledged without changing memory. Invalid or misaligned requests return an error and do not access memory.

One request is accepted on a rising edge with `req_valid && req_ready`. Its registered response becomes visible after that edge. There is one response slot, held stable until `rsp_valid && rsp_ready`. A response may be consumed while the next request is accepted. Writes commit when their request is accepted, and write responses contain zero read data. Read data is the addressed word. Reset is active-low synchronous: it clears response state, **not memory contents**. Unwritten words are uninitialized; callers must load them before reading. This behavioral RAM has not been mapped to an FPGA RAM or ASIC macro.

`p04_dot4_engine` captures `a_addr`, `b_addr`, `dst_addr`, and signed INT32 `accumulator` on a rising edge with `start && !busy`. Hold these command inputs stable at that edge; subsequent changes do not affect the job. Keep start as a one-cycle command pulse. The controller reads one packed four-INT8 A word and one B word, invokes the existing `p04_dot4`, and writes the wrapped INT32 result to the destination. Source and destination may alias because both reads complete before the write.

- `busy` remains high throughout the job.
- `done` is a one-cycle pulse after a read error or the destination write response. Successful done means the write has completed.
- `error` reports a memory response error and remains latched until the next accepted job or reset.
- `overflow` reports DOT4 INT32 overflow; the wrapped result is still written. It remains latched until the next accepted job or reset.
- `rejected` pulses for a start sampled while busy. The active job proceeds unchanged; the second command is not queued and does not corrupt its error status.
- The memory request payload stays stable during backpressure. Only one memory request is outstanding.

The engine uses an external memory request/response port so that stalls can be tested. The testbench arbitrates a host preload/readback interface and the engine onto one scratchpad port. Host access must finish, including response consumption, before engine start. Host access while busy is excluded. A production SoC arbiter or MMIO command block is not implemented here.

Reset must reach the engine and memory response interface together to discard outstanding transactions. A write already accepted before reset remains committed; reset cannot roll it back. Completion after reset must never be inferred for an aborted job. No watchdog is in the hardware controller: an unresponsive memory keeps a job busy until reset; the testbench provides a simulation watchdog.

## Simulation

Use a **separate** ChipVerify project or replace both editor contents with:

- `sim/chipverify_memory/design.sv`
- `sim/chipverify_memory/testbench.sv`

Choose Verilator (SystemVerilog). Compile arguments:

```text
--timing --top-module tb_p04_dot4_engine
```

Leave runtime arguments empty for the first run. Require:

```text
PASS Project04 memory-backed DOT4 engine
jobs=7 host_checks=... request_stalls=... response_stalls=...
```

Any fatal error, timeout or file-size error overrides the platform's green banner. This suite is short: it has no 65536-pair exhaustive loop. Optional waveforms use compile arguments `--timing --trace-vcd --trace-depth 1 --top-module tb_p04_dot4_engine` and runtime `+WAVES`, producing `p04_memory_engine.vcd`.

The test checks normal result 80, destination/source aliasing, overflow, masked and zero-strobe writes, the last legal word, misalignment and range errors, command capture, busy-start rejection, response holding, request stability, deterministic request/response stalls, reset during operand fetch, memory retention and successful restart. Reset is tested before the aborted job writes; rollback of an already committed write is not claimed.

## Validation status

Static parsing, type checking and elaboration pass with zero diagnostics using pyslang 12.1.0. The generated source bundle is checked against canonical files. **Behavioral simulation of this new integration suite is pending execution in ChipVerify.** It is not yet a measured hardware performance result, a complete GPU or object detector.

Rebuild and check:

```sh
python3 scripts/bundle_memory_engine.py
python3 scripts/bundle_memory_engine.py --check
python3 scripts/check_memory_sv.py
```

The optional static checker uses `requirements-check.txt`. The previous arithmetic suite and its source bundles remain independent of this integration suite.
