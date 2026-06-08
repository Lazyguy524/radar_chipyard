# Xradar Custom ISA Draft

Date: 2026-06-07

Status: offline Phase 1 draft. This freezes software-visible semantics for the first QMLP-oriented arithmetic subset, but it does not claim a hardware implementation yet.

## Scope

`Xradar` is a small workload-specific custom extension for the current radar Feature21 + QMLP project. The first draft targets operations that are already visible in the CPU-only QMLP and Feature21 fixed-point paths:

- packed signed int8 dot product,
- packed signed int8 MAC,
- fixed-point requant multiply, round-nearest-even, ReLU, and int8 clamp,
- byte packing for later Feature21 output helpers,
- reserved accelerator-control operations for a later `racc.*` gate.

This extension is inspired by packed-SIMD and P-extension-style dot-product ideas, but it is intentionally not a full P-extension implementation and must not be described as P-extension compliant.

## Register And Encoding Policy

Initial opcode partition:

| Opcode set | Purpose | Status |
| --- | --- | --- |
| `custom0` | `rq*` arithmetic/data instructions | Active draft. |
| `custom1` | `racc.*` accelerator-control instructions | Reserved until MMIO/polling gate is measured. |
| `custom2` | stream/address-generation experiments | Reserved. |
| `custom3` | debug/profiling or unused | Reserved. |

Draft `custom0` function map:

| Instruction | Opcode | `funct7` | `funct3` | Semantics |
| --- | --- | ---: | ---: | --- |
| `rqdot4 rd, rs1, rs2` | `custom0` | `0x00` | `0x0` | Signed 4-lane int8 dot product. |
| `rqmac4 rd, rs1, rs2` | `custom0` | `0x01` | `0x0` | Signed 4-lane int8 dot product accumulated into an implementation-defined accumulator convention. |
| `rqscale8 rd, rs1, rs2` | `custom0` | `0x02` | `0x0` | Fixed-point multiply by multiplier, round-nearest-even, ReLU, clamp to `[0, 127]`. |
| `rqpack rd, rs1, rs2` | `custom0` | `0x03` | `0x0` | Pack/clamp feature bytes. Exact multi-byte convention still pending Feature21 profiling. |

Draft `custom1` function map:

| Instruction | Opcode | `funct7` | `funct3` | Status |
| --- | --- | ---: | ---: | --- |
| `racc.cfg` | `custom1` | `0x00` | `0x0` | Reserved. |
| `racc.start` | `custom1` | `0x01` | `0x0` | Reserved. |
| `racc.wait` | `custom1` | `0x02` | `0x0` | Reserved. |
| `racc.stat` | `custom1` | `0x03` | `0x0` | Reserved. |

`racc.*` must not enter RTL until the Phase 0 MMIO/setup/polling instrumentation can show either a cycle-share reason or an instruction-count/code-size reason.

## Arithmetic Semantics

### Packed Lane Order

For all packed signed int8 arithmetic:

```text
lane0 = bits [7:0]
lane1 = bits [15:8]
lane2 = bits [23:16]
lane3 = bits [31:24]
```

Each lane is sign-extended from int8 before multiplication.

### `rqdot4`

Software reference:

```c
int32_t rqdot4(uint32_t rs1, uint32_t rs2) {
  int32_t sum = 0;
  for (unsigned lane = 0; lane < 4; ++lane) {
    sum += sext8(rs1[8*lane +: 8]) * sext8(rs2[8*lane +: 8]);
  }
  return sum;
}
```

Return value is a signed 32-bit integer sign-extended to XLEN if implemented as a scalar RISC-V instruction.

No saturation is applied to `rqdot4`.

### `rqmac4`

Phase 1 keeps `rqmac4` as a semantic alias for:

```text
rd = accumulator + rqdot4(rs1, rs2)
```

The exact architectural accumulator convention is not frozen yet. The first RoCC prototype may simply return `acc + dot` if one source register can hold the accumulator, or may omit `rqmac4` and use `rqdot4` plus scalar add. The execute-stage version must respect the 2-read/1-write register-file constraint.

### `rqscale8`

The QMLP v1 semantics are:

```text
product = int64(acc) * int64(multiplier)
rounded = round_nearest_even(product / 2^16)
relu = max(rounded, 0)
rd = min(relu, 127)
```

This matches the current QMLP hidden-layer activation order:

```text
integer multiply -> round-nearest-even -> ReLU -> clamp
```

The current QMLP constants are:

| Layer | Multiplier | Shift |
| --- | ---: | ---: |
| L1 | `1516` | `16` |
| L2 | `608` | `16` |

L3 returns int32 logits and does not use `rqscale8`.

Round-nearest-even reference:

```text
q_abs = abs(product) >> shift
rem = abs(product) & ((1 << shift) - 1)
half = 1 << (shift - 1)
rounded_abs = q_abs + (rem > half || (rem == half && (q_abs & 1)))
rounded = product < 0 ? -rounded_abs : rounded_abs
```

### `rqpack`

`rqpack` is reserved for Feature21 output packing and clamp helpers. The QMLP-only fallback test currently uses ordinary C packing helpers, not a frozen `rqpack` architectural contract.

## QMLP Static Operation Model

Current QMLP dimensions:

| Layer | Shape | MACs | Packed `rqdot4` groups | Scalar tail MACs |
| --- | --- | ---: | ---: | ---: |
| L1 | `64 x 21` | 1344 | 320 | 64 |
| L2 | `32 x 64` | 2048 | 512 | 0 |
| L3 | `2 x 32` | 64 | 16 | 0 |
| Total | - | 3456 | 848 | 64 |

Packed MAC coverage:

```text
(848 * 4) / 3456 = 98.14%
```

This means `rqdot4` can replace 3392 scalar int8 multiply terms with 848 packed dot instructions in the current QMLP shape. This is an instruction-count and arithmetic-operation compression argument only; whole-workload speedup still requires measured cycle fractions and finite-kernel-speedup Amdahl analysis.

The current hidden-layer scaling count is:

```text
L1 64 + L2 32 = 96 rqscale8-equivalent operations
```

## Software Golden

Reference files:

- `tests/radar_xradar_fallback.h`
- `tests/radar-xradar-fallback-host.c`

Host validation command:

```bash
make -C tests xradar-host-test
make -C tests xradar-static-model
```

Current host result:

```text
[XRADAR-FALLBACK] counts rqdot4=848 scalar_tail_macs=64 rqscale8=96 total_macs=3456 packed_mac_coverage_x100=9814
[XRADAR-FALLBACK] PASSED
```

The fallback checks:

- basic `rqdot4` signed lane semantics,
- negative ReLU behavior in `rqscale8`,
- positive int8 clamp behavior in `rqscale8`,
- golden input logits against the packaged QMLP golden,
- all 8 existing synthetic QMLP cases against a scalar reference.

The static model additionally prints the finite-speedup Amdahl sensitivity table used by the Phase 0 gate.

## Current Go / No-Go Interpretation

Offline evidence supports keeping `rqdot4` and `rqscale8` as first-class candidates:

- `rqdot4` has high static packed-MAC coverage for the QMLP kernel.
- `rqscale8` exactly matches the current hidden-layer fixed-point activation contract.
- The software fallback is bit-exact for the current QMLP test set.

Offline evidence does not yet prove:

- CPU cycle share of dot/MAC versus quant/control.
- RoCC or execute-stage speedup.
- end-to-end board latency improvement.
- `racc.*` usefulness.
- Gemmini resource/timing competitiveness.

Therefore the next implementation step should still be conservative:

1. Keep `rqdot4` and `rqscale8` semantics frozen in software.
2. Add or run profiling when board/UART access is available.
3. Prototype RoCC only after the Phase 0 gate accepts a measured or explicitly instruction-count-driven goal.
