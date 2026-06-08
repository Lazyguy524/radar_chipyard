# Feature21 v1.4a Density Reciprocal Exact-LUT Review

Date: 2026-04-25

Scope: offline review only. RTL/Chisel and bitstream generation are intentionally out of scope for this step.

## Files and Reports

Updated evaluation tool:

- `tools/feature21_hw_approx_eval.py`

Generated evaluation report:

- `logs/radar_nexysvideo/runtime/658-feature21-v1p4a-density-exact-lut-e2e-2026-04-25.md`

Primary data sources:

- `docs/feature_preproc_compare_20260420/feature21/golden/features_int8_21.bin`
- `docs/feature_preproc_compare_20260420/feature21/golden/inputs_raw_or_fused.bin`
- `docs/feature_preproc_compare_20260420/feature21/golden/inputs_raw_or_fused_offsets_u32.bin`
- `docs/feature_preproc_compare_20260420/feature21/golden/logits_int32.bin`
- `docs/feature_preproc_compare_20260420/feature21/golden/labels_int64.npy`
- `docs/feature_preproc_compare_20260420/feature21/qmlp_params_21.h`

## Exact LUT Mirror Definition

The new `density_recip_exact_lut` mirror models a normalized reciprocal LUT implementation rather than an ideal divider.

Input quantities:

| name | width / Q format | description |
|---|---|---|
| `count` | unsigned 9-bit integer | clamped point count, valid `0..511` |
| `span_x` | unsigned Q8.8, up to 16-bit magnitude | `max_x - min_x` |
| `span_y` | unsigned Q8.8, up to 16-bit magnitude | `max_y - min_y` |
| `area_q16p16` | unsigned Q16.16, up to 32-bit | `span_x * span_y` |

Special cases:

```text
if count == 0:
    f13 = 0
elif area_q16p16 == 0:
    f13 = 127
```

Normalization:

```text
exponent = floor(log2(area_q16p16))

if exponent >= 7:
    mant8 = area_q16p16 >> (exponent - 7)
else:
    mant8 = area_q16p16 << (7 - exponent)

mant8 = clamp(mant8, 128, 255)
lut_index = mant8 - 128
```

LUT generation:

```text
recip_lut[lut_index] = round_nearest_even(2^23 / mant8)
```

LUT format:

| item | value |
|---|---:|
| entries | 128 |
| input mantissa range | `128..255` |
| index range | `0..127` |
| output format | unsigned Q0.23 |
| output width | 17 bits |
| entry for mant8=128 | 65536 |
| entry for mant8=160 | 52429 |
| entry for mant8=192 | 43691 |
| entry for mant8=224 | 37449 |
| entry for mant8=255 | 32897 |

Reconstruction:

```text
prod = count * recip_lut[lut_index]

if exponent >= 8:
    density_q8p8 = bank_round_shift(prod, exponent - 8)
else:
    density_q8p8 = prod << (8 - exponent)
```

Final Feature21 quantization:

```text
f13 = clamp_u7(bank_round_shift(density_q8p8 * 105, 16))
```

`clamp_u7` is used because density is non-negative; final output range is `0..127`.

Rounding rule:

- LUT generation uses round-to-nearest-even.
- Dynamic right shift uses the same banker's rounding behavior as existing Feature21/QMLP helpers.
- Left shifts do not round.
- Saturation happens only at the defined special cases and the final f13 output clamp.

## Exact LUT vs Ideal Division

The older `density_recip` mode remains an ideal software division reference:

```text
density_q8p8 = round_nearest_even(count * 2^24 / area_q16p16)
```

Across the 1000-sample golden set:

| comparison | value |
|---|---:|
| f13 mismatches between ideal division and exact LUT | 6/1000 |
| maximum f13 difference | 1 LSB |

The exact LUT mirror is therefore close enough to the ideal division model for v1.4a, while being much more realistic for RTL.

## QMLP End-to-End Ablation

Command:

```bash
python3 tools/feature21_hw_approx_eval.py \
  --golden docs/feature_preproc_compare_20260420/feature21/golden \
  --input docs/feature_preproc_compare_20260420/feature21/golden \
  --mirror-mode v1p3 \
  --e2e-modes v1p3,density_recip_exact_lut,mean_recip,mean_density_recip_exact_lut,candidate_v1p4a \
  --out logs/radar_nexysvideo/runtime/658-feature21-v1p4a-density-exact-lut-e2e-2026-04-25.md
```

QMLP software inference was checked against `logits_int32.bin`:

- Golden-logit reproduction: `1000/1000` exact samples.

Results:

| mode | prediction agreement | changed predictions | mean abs logit error | approx accuracy | approx macro-F1 |
|---|---:|---:|---:|---:|---:|
| `v1p3` | 79.90% | 201/1000 | 2020.190 | 87.40% | 0.873 |
| `density_recip_exact_lut` | 95.20% | 48/1000 | 794.828 | 91.10% | 0.910 |
| `mean_recip` | 80.80% | 192/1000 | 1807.281 | 88.30% | 0.882 |
| `mean_density_recip_exact_lut` | 96.90% | 31/1000 | 381.195 | 88.60% | 0.884 |
| `candidate_v1p4a` | 97.00% | 30/1000 | 366.852 | 88.50% | 0.883 |

Changed-prediction quadrants:

| mode | pred same, f13 same | pred same, f13 mismatch | pred changed, f13 same | pred changed, f13 mismatch |
|---|---:|---:|---:|---:|
| `v1p3` | 17 | 782 | 2 | 199 |
| `density_recip_exact_lut` | 948 | 4 | 48 | 0 |
| `mean_recip` | 18 | 790 | 1 | 191 |
| `mean_density_recip_exact_lut` | 965 | 4 | 31 | 0 |
| `candidate_v1p4a` | 966 | 4 | 30 | 0 |

Interpretation:

- Density is a v1.4a priority because replacing the v1p3 count proxy with exact-LUT reciprocal removes f13 from all changed-prediction cases in this dataset.
- `mean_recip` improves feature fidelity, but does not remove the f13-driven classification flips.
- `candidate_v1p4a` is now a realistic hardware candidate: mean reciprocal + piecewise range + exact-LUT density.
- Remaining classification flips after candidate_v1p4a are not density-driven; they are mainly std/eig/range proxy issues.

## Resource Estimate

Density exact-LUT reciprocal only:

| resource | estimate | risk |
|---|---:|---|
| DSP48 | 1 if area and count-recip multiplications are time-shared | low |
| LUT ROM | 128 x 17 bits = 2176 bits | low |
| FF | 120 to 220 | low |
| LUT logic | 300 to 550 | medium-low |
| extra finalization cycles | +6 to +8 | low |

Likely logic contributors:

- 32-bit leading-one detector for `area_q16p16`
- mantissa extraction mux
- 128-entry reciprocal ROM
- dynamic round-to-nearest-even shifter
- final multiply-by-105 shift-add path
- f13 saturation and feature byte writeback mux

Combined v1.4a estimate with one shared DSP:

| block | cycles |
|---|---:|
| mean reciprocal for x/y/doppler/rcs | +4 to +8 |
| density area multiply | +1 |
| density LUT normalize/read | +1 to +2 |
| density count * reciprocal | +1 |
| density shift/quant/clamp | +2 to +3 |
| range_piecewise | 0 extra if placed in point-scan range path |

Expected additional finalization: about `+10..16` cycles with conservative registers.

## Timing Review

The density exact-LUT path is timing-controllable if implemented as a multi-cycle finalization sequence.

Do not combine these into a single cycle:

- area multiply
- leading-one detect
- reciprocal LUT read
- count reciprocal multiply
- dynamic rounded shift
- final quantization

Recommended timing cuts:

1. register `span_x`, `span_y`, `count`
2. register `area_q16p16`
3. register `{exponent, mant8, lut_index}`
4. register `recip_q0p23`
5. register `count * recip`
6. register `density_q8p8`
7. register final f13 byte

## Suggested Chisel FSM States

Existing preprocessor FSM lives in `RadarAXISFeature21Preprocessor` and currently uses:

```text
sIdle -> sAccum -> sMeanX -> sMeanY -> sMeanDoppler -> sMeanRcs
      -> sFeatureSelect -> sFeatureQuant -> sEmit
```

Suggested v1.4a finalization states:

```text
sFinalizeStart
sMeanRecipX
sMeanRecipY
sMeanRecipDoppler
sMeanRecipRcs
sDensityAreaMul
sDensityNormalize
sDensityLutRead
sDensityMul
sDensityShiftRound
sDensityQuantClamp
sFeatureSelect
sFeatureQuant
sEmit
```

For the first RTL pass:

- Keep the existing feature selection/packing protocol.
- Replace f13 source only after `sDensityQuantClamp`.
- Keep range_piecewise local to the range approximation helper.
- Keep mean reciprocal multi-cycle and shared; avoid four parallel mean dividers/multipliers.
- Add counters or debug status bits only if needed for bring-up, not as part of the public packet protocol.

## Files to Touch in the Actual RTL Step

When implementation begins, expected files are:

| file | expected change |
|---|---|
| `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala` | implement Feature21 v1.4a helpers, LUT ROM, FSM states, f13 source |
| `tests/feature21_hw_approx_reference.h` | add exact-LUT C reference helpers for board/unit comparison |
| `tests/radar-axi-dma-feature21-golden.c` | compare/report full f13 and candidate-mode expectations if board test is extended |
| `tools/feature21_hw_approx_eval.py` | already has exact-LUT mirror; use as source of truth for test vectors |
| `docs/feature21_hardware/plan/*` | update design notes after RTL review |

Do not change in the first RTL pass:

- AXI stream input/output packet shape
- DMA MM2S/S2MM protocol
- QMLP interface width/order
- bitstream generation scripts
- board bring-up scripts, unless a new test binary is explicitly added

## Decision

The exact-LUT density reciprocal is suitable as a v1.4a priority item.

Reasons:

1. It changes the classification story: prediction agreement improves from `79.90%` to `95.20%` with density alone.
2. It removes f13 from changed-prediction cases: `199/201` in v1p3 becomes `0/48` with exact-LUT density.
3. It closely tracks the ideal division model: only `6/1000` f13 values differ, max difference `1`.
4. It avoids a general divider and uses one time-shared DSP plus a small ROM.
5. The extra finalization latency is small relative to current sample-level processing and can be hidden before output packing.

Recommended next step before editing RTL:

- Freeze this LUT rule as the v1.4a hardware contract.
- Generate a small fixed vector set covering zero area, tiny area saturation, observed max area, and round-half-even boundaries.
- Then implement the Chisel FSM and compare RTL simulation output byte-for-byte against `density_recip_exact_lut`.
