# Arithmetic interface specification v0.1

This is the numerical and cycle contract for the initial arithmetic slice. It does not define a trained detector or a complete GPU ISA.

## Shared transaction behavior

- Clock: `clk`, rising-edge active.
- Reset: `rst_n`, active-low **synchronous** reset. Assert across a rising edge to clear output validity and data. Reset discards any pending output.
- Input transfer: `i_valid && i_ready` sampled on a rising edge.
- Output transfer: `o_valid && o_ready` sampled on a rising edge.
- Storage: one registered output slot per block. An accepted input becomes visible after its accepting edge; it can be consumed on the next edge at the earliest.
- Throughput: at most one transaction per clock when the consumer is ready. This is interface throughput, not a measured frequency or full inference rate.
- Readiness: `i_ready = rst_n && (!o_valid || o_ready)`.
- Stalls: while `o_valid && !o_ready`, the output payload, metadata and validity remain stable. The input source must hold a blocked valid request stable until acceptance or reset.
- Simultaneous output consumption and input replacement are supported. A bubble clears validity when the slot can advance. Payload values when invalid are not meaningful except that reset clears them.
- Ready is combinational; the rest of an integrated pipeline must avoid creating a combinational ready loop.

## p04_dot4

| Port | Width and meaning |
| --- | --- |
| `i_a`, `i_b` | 32-bit packed words, each containing four signed two's-complement INT8 values |
| `i_acc` | Signed INT32 accumulator input; not hidden persistent accumulator state |
| `o_result` | Signed INT32 wrapped result |
| `o_overflow` | True when the full mathematical result falls outside signed INT32 |

Byte zero occupies bits `[7:0]`. The operation is:

```text
wide = i_acc + signed(a[7:0])*signed(b[7:0])
             + signed(a[15:8])*signed(b[15:8])
             + signed(a[23:16])*signed(b[23:16])
             + signed(a[31:24])*signed(b[31:24])
o_result = low 32 bits of wide
o_overflow = wide outside [-2147483648, 2147483647]
```

The datapath uses 16-bit products and a 34-bit signed sum. Overflow reporting supports debug; inference software must prove accumulator bounds or split reductions rather than treating wrapped output as a correct neural-network value.

## p04_simd_dot4

Eight DOT4 lanes execute in lockstep. `i_a`, `i_b`, `i_acc` and `o_result` are 256-bit buses. Lane zero occupies bits `[31:0]`. `i_mask` and `o_mask` contain eight bits, one per lane.

An enabled lane computes DOT4. A disabled lane preserves its input accumulator and reports no overflow. The output mask is registered with the result and holds during a stall. One shared ready/valid interface applies to the entire vector; individual lanes cannot accept or retire independently.

One accepted vector represents up to 32 INT8 MACs. The wrapper contains arithmetic lanes only: no instruction memory, instruction decoder, kernel scheduler, scratchpad or external-memory controller is implemented yet.

## p04_requantize

| Port | Width and meaning |
| --- | --- |
| `i_acc` | Signed INT32 |
| `i_multiplier` | Nonnegative 31-bit integer, 0 through 2147483647 |
| `i_shift` | Unsigned six-bit right shift, 0 through 63 |
| `i_zero_point` | Signed INT8 output zero point |
| `i_clamp_min`, `i_clamp_max` | Signed INT8 activation limits |
| `o_result` | Signed INT8 quantized output |
| `o_error` | Invalid clamp ordering |

```text
product = exact signed product of acc and multiplier
scaled = product / 2**shift, rounded to nearest integer
         with exact halfway cases rounded away from zero
result = clamp(scaled + zero_point, clamp_min, clamp_max)
```

Examples: `+1 / 2` rounds to `+1`; `-1 / 2` rounds to `-1`; `+3 / 2` rounds to `+2`; `-3 / 2` rounds to `-2`. Shift zero performs no rounding. A zero multiplier produces the clamped zero point. A 65-bit magnitude/rounding path and 66-bit signed offset/clamp path avoid intermediate narrowing before saturation.

When `clamp_min > clamp_max`, the request completes normally with `o_error=1` and `o_result=0`; there is no silent swap of limits. An equal min and max is legal. There is no implicit Q31 format or negative multiplier support.

This initial rounding contract is **not a claim of bit-exact LiteRT, ONNX, or any pretrained-model compatibility**. An exporter must prove an exact mapping or the arithmetic contract must be versioned and adjusted. Activation input zero-point compensation and INT32 bias addition are not performed by the raw DOT4 block; they must be represented correctly by the later convolution implementation.

## Timing and implementation status

These are synthesizable-style RTL blocks with one registered output stage. The requantizer currently contains a wide multiplier and variable shifter in one combinational path. No synthesis, SRAM mapping, timing closure, power estimation, FPGA utilization or ASIC signoff has been performed. Pipelining that path later requires updating the latency contract and scoreboard.
