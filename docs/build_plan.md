# RTL build plan

## Product scope

Look at an everyday object, identify it, and hear or see its name. Support the selected detector's broad set of useful categories rather than a chair-only model. The class count remains a model-selection result, not an RTL capability claimed today.

Develop in SystemVerilog with self-checking ChipVerify simulations. CPU firmware, FPGA selection, physical camera integration, and wearable optics are later work.

## Work packages and acceptance gates

| Package | Work | Exit criterion | Status |
| --- | --- | --- | --- |
| 1 Arithmetic | Scalar DOT4, eight-lane arithmetic slice, requantization, backpressure/reset behavior | Static compilation plus passing behavioral arithmetic regression | RTL and tests written; static compile passes; full ChipVerify PASS evidence pending; waveform smoke mode added after a reported 100 MB trace limit |
| 2 Model contract | Profile compact pretrained detectors and freeze one graph, label map, tensor plan, numerical rules, and accuracy target | Supported operator list, weights provenance, memory/compute estimates, and golden tensors | Planned |
| 3 Memory movement | Banked scratchpad, tile buffers, bounded DMA, ownership and error handling | Randomized access/stall/reset tests and data-integrity scoreboard pass | Planned after tile requirements are known |
| 4 Neural kernels | Convolution, depthwise convolution if needed, activation, pooling, and tensor operations | Each supported layer matches the selected model's integer reference | Planned |
| 5 GPU control | Instruction encoding, register access, lane scheduling, masks, kernel loop control and completion | Executable kernels run through a tested instruction decoder and controller | Planned; the current SIMD wrapper is not a complete GPU |
| 6 Stored-image detection | Whole-graph scheduling, box/class decoding and deterministic target selection | Held-out images produce correct labels/boxes versus the frozen reference | Planned |
| 7 CPU integration | CPU RTL, memory-mapped control and interrupts; firmware when that phase is opened | CPU can submit jobs and consume results without data races | Deferred until compute subsystem is verified |
| 8 User output | Camera input, display/name rendering and audio; FPGA and glasses when selected | Measured end-to-end identification and name output | Later integration |

Packages 1 and 2 inform one another. Arithmetic blocks can be developed before choosing a model, but their numerical contract must be reconciled with the chosen graph before claiming model compatibility. Do not freeze a lane count, SRAM macro, clock-frequency guarantee, or detection rate from unmeasured arithmetic peak alone.

## Current deliverables

- `rtl/p04_dot4.sv`: four signed INT8 products plus an explicit INT32 accumulator input.
- `rtl/p04_simd_dot4.sv`: eight lockstep arithmetic lanes and a lane mask.
- `rtl/p04_requantize.sv`: defined integer scaling, rounding, zero-point addition and clamp handling.
- `tb/tb_p04_arithmetic.sv`: self-checking transaction and numerical regression.
- `scripts/arithmetic_reference.py`: integer numerical reference.
- `tests/test_arithmetic_reference.py`: Python reference tests.
- `sim/chipverify/`: generated two-file source bundle for the web simulator.

See [the arithmetic specification](arithmetic_spec.md), [the ChipVerify run procedure](chipverify.md), and [verification status](verification_status.md).

## Next executable step

Load the latest supplied bundle into ChipVerify with top `tb_p04_arithmetic`, run the full regression with empty runtime arguments, and resolve any simulator diagnostics or functional failures. Use the separate `+WAVES` mode for a short waveform test. Preserve the console result and exact source hashes. Package 1 is not behaviorally verified until the full regression succeeds.
