# RTL

| Module | Function |
| --- | --- |
| `p04_dot4.sv` | Four signed INT8 products plus explicit INT32 accumulator; wrapped result and overflow flag |
| `p04_simd_dot4.sv` | Eight lockstep DOT4 lanes with lane masking |
| `p04_requantize.sv` | Integer scaling, rounding, zero point and INT8 activation clamp |

All three use one-entry ready/valid output buffering and active-low synchronous reset. See [the interface and numerical contract](../docs/arithmetic_spec.md).

Static compilation is checked; behavioral simulation is pending. The SIMD block is an arithmetic slice, not a complete GPU. No neural-network, frequency, area or power result is claimed.
