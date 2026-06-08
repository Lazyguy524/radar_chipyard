# Feature21 v1.4a Density Reciprocal Micro-Architecture Proposal

Date: 2026-04-25

Scope: proposal only. Do not modify Chisel/RTL in this step.

## Current Evidence

Input data source:

- `docs/feature_preproc_compare_20260420/feature21/golden/inputs_raw_or_fused.bin`
- `docs/feature_preproc_compare_20260420/feature21/golden/inputs_raw_or_fused_offsets_u32.bin`
- `docs/feature_preproc_compare_20260420/feature21/golden/features_int8_21.bin`
- `docs/feature_preproc_compare_20260420/feature21/qmlp_params_21.h`

Full 1000-sample offline result from:

- `logs/radar_nexysvideo/runtime/657-feature21-v1p4-density-recip-ablation-2026-04-25.md`

Feature-level ablation:

| mode | feature match | exact vectors | mean abs err | max abs err |
|---|---:|---:|---:|---:|
| `v1p3` | 62.45% | 0/1000 | 1.304 | 126 |
| `mean_recip` | 74.91% | 1/1000 | 0.990 | 126 |
| `range_piecewise` | 64.71% | 0/1000 | 1.270 | 126 |
| `density_recip` | 67.09% | 3/1000 | 0.791 | 122 |
| `mean_range_piecewise` | 78.43% | 1/1000 | 0.921 | 126 |
| `mean_density_recip` | 79.56% | 22/1000 | 0.477 | 122 |
| `range_density_recip` | 69.35% | 4/1000 | 0.757 | 122 |
| `candidate_v1p4a` | 83.07% | 35/1000 | 0.408 | 122 |

QMLP end-to-end ablation:

| mode | prediction agreement | changed predictions | approx accuracy | approx macro-F1 |
|---|---:|---:|---:|---:|
| `v1p3` | 79.90% | 201/1000 | 87.40% | 0.873 |
| `mean_recip` | 80.80% | 192/1000 | 88.30% | 0.882 |
| `range_piecewise` | 80.00% | 200/1000 | 87.10% | 0.870 |
| `density_recip` | 95.20% | 48/1000 | 91.10% | 0.910 |
| `mean_range_piecewise` | 81.20% | 188/1000 | 88.30% | 0.882 |
| `mean_density_recip` | 96.90% | 31/1000 | 88.60% | 0.884 |
| `range_density_recip` | 95.00% | 50/1000 | 90.70% | 0.906 |
| `candidate_v1p4a` | 97.00% | 30/1000 | 88.50% | 0.883 |

Changed-prediction quadrants:

| mode | pred same, f13 same | pred same, f13 mismatch | pred changed, f13 same | pred changed, f13 mismatch |
|---|---:|---:|---:|---:|
| `v1p3` | 17 | 782 | 2 | 199 |
| `mean_recip` | 18 | 790 | 1 | 191 |
| `range_piecewise` | 17 | 783 | 2 | 198 |
| `density_recip` | 946 | 6 | 48 | 0 |
| `mean_range_piecewise` | 18 | 794 | 1 | 187 |
| `mean_density_recip` | 963 | 6 | 31 | 0 |
| `range_density_recip` | 944 | 6 | 50 | 0 |
| `candidate_v1p4a` | 964 | 6 | 30 | 0 |

Interpretation:

- The current v1p3 count-proxy density is classification-relevant. It appears in 199/201 v1p3 changed predictions.
- Once density reciprocal is enabled, f13 no longer appears in changed-prediction samples for the evaluated modes.
- The remaining candidate_v1p4a flips are dominated by std/eig/range proxy errors, especially f3, f8, f9, f10, and f11.

## Dataset Range Observed

From the 1000-sample golden input set after float-to-Q8.8 conversion:

| quantity | min | max |
|---|---:|---:|
| points per sample | 3 | 82 |
| `span_x` Q8.8 | 18 | 14594 |
| `span_y` Q8.8 | 4 | 12295 |
| `area_q16p16 = span_x * span_y` | 144 | 166904625 |

Observed area quantiles:

| quantile | area_q16p16 | area_float |
|---:|---:|---:|
| 50% | 873440 | 13.3276 |
| 90% | 4875406 | 74.3928 |
| 95% | 8824632 | 134.6532 |
| 99% | 23226720 | 354.4116 |
| 100% | 166904625 | 2546.7625 |

The RTL should still support the full representable span range, not just the observed dataset range.

## Target Formula

Software mirror formula:

```text
area_q16p16 = max(span_x, 0) * max(span_y, 0)

if count == 0:
    density_feature = 0
elif area_q16p16 == 0:
    density_feature = 127
else:
    density_q8p8 = round_nearest_even(count * 2^24 / area_q16p16)
    density_feature = clamp_s8_symmetric(round_nearest_even(density_q8p8 * 105 / 2^16))
```

This preserves the current Feature21 quantization constant:

```text
quant_q8p8(v) = clamp_s8_symmetric(bankers_round_shift(v * 105, 16))
```

## Proposed Reciprocal LUT Architecture

Use a normalized reciprocal LUT instead of a full divider.

Inputs:

- `count`: unsigned 9-bit, valid range `0..511`.
- `span_x`, `span_y`: non-negative unsigned 16-bit Q8.8 span magnitudes.
- `area_q16p16`: unsigned 32-bit product.

Special cases:

- `count == 0`: output `0`.
- `area_q16p16 == 0` and `count > 0`: output `127`.
- final output saturates to signed symmetric int8 range `[-127, 127]`; density is non-negative, so practical range is `0..127`.

Normalization:

```text
e = floor(log2(area_q16p16))
mant8 = area_q16p16 >> max(e - 7, 0)
mant8 = clamp(mant8, 128, 255)
area_q16p16 ~= mant8 * 2^(e - 7)
```

LUT:

```text
recip_lut[mant8 - 128] = round_nearest_even(2^23 / mant8)
```

LUT input range:

- address: `mant8[7:0]`, valid normalized range `128..255`.
- table entries: 128.

LUT output format:

- `recip_q0p23`: unsigned 17-bit value.
- maximum at mant8=128: `65536`.
- minimum at mant8=255: `32896`.

Density reconstruction:

```text
prod = count * recip_q0p23

if e >= 8:
    density_q8p8 = round_nearest_even(prod >> (e - 8))
else:
    density_q8p8 = prod << (8 - e)

density_feature = clamp_u7(round_nearest_even(density_q8p8 * 105 / 2^16))
```

Rounding:

- Use the same banker's rounding helper already mirrored by `bank_round_shift`.
- Dynamic right shifts must preserve round-to-nearest-even behavior.
- Left shifts do not round; they must saturate before final int8 packing if intermediate width overflows.

Saturation:

- `density_q8p8` can be saturated to a safe unsigned intermediate, for example 24 bits, before final quantization.
- Final density feature clamps to `0..127`.
- Since f13 is non-negative, do not emit negative density values.

## Pipeline and Finalization Cycles

Recommended single-DSP scheduled pipeline:

| cycle | operation | notes |
|---:|---|---|
| F0 | register `count`, `span_x`, `span_y` | spans are available after point scan |
| F1 | multiply `span_x * span_y` | one DSP48 or fabric multiplier |
| F2 | leading-one detect, normalize mantissa, LUT read | LUT can be distributed ROM |
| F3 | multiply `count * recip_q0p23` | reuse the same DSP48 if scheduled |
| F4 | exponent shift with banker's rounding | dynamic barrel shift |
| F5 | multiply-by-105 via shift-add, banker's rounding by 16 | no DSP required |
| F6 | saturate and write f13 byte | ready for output packing |

Estimated density-only finalization latency:

- 6 to 7 cycles after the final input point.
- Can be 4 to 5 cycles if area multiply and count reciprocal multiply use separate DSPs.
- Board-level impact is expected to be small because current measured preprocessor cycles are hundreds of cycles per sample on the golden subset, and output packing already needs multiple beats.

## Resource Estimate

Density reciprocal only, single-DSP scheduled version:

| resource | estimate | risk |
|---|---:|---|
| DSP48 | 1 | low |
| reciprocal LUT | 128 x 17 bits = 2176 bits | low |
| registers | 120 to 200 FF | low |
| LUT logic | 250 to 450 LUT | medium-low |
| finalization cycles | +6 to +7 | low |

Main LUT contributors:

- leading-one detector for 32-bit `area_q16p16`
- mantissa extraction mux
- dynamic right shifter with banker's rounding
- final saturation and output muxing

If sharing with mean reciprocal:

- mean reciprocal needs either one shared DSP over four mean lanes, or four parallel DSPs.
- Conservative v1.4a choice: one shared DSP for mean lanes plus density scheduled afterward.
- Estimated combined finalization:
  - mean reciprocal: 4 multiply cycles for x, y, doppler, rcs
  - density reciprocal: 2 multiply cycles
  - range_piecewise: combinational shift-add in the point scan or final path
  - total added finalization: about +10 to +14 cycles with one shared DSP

## Timing Risk

Low-risk timing choices:

- Register the area product before leading-one detection.
- Register the reciprocal LUT output.
- Register the dynamic shifter output before final quantization.
- Keep multiply-by-105 as shift-add in a registered stage.
- Do not place area multiply, leading-one detect, LUT read, dynamic shift, and quantization in one cycle.

Expected timing risk:

- Density reciprocal alone: controllable.
- Mean reciprocal plus density with one shared DSP: controllable if scheduled over multiple finalization cycles.
- Fully parallel mean plus density: higher DSP cost and more routing pressure; not recommended for the first v1.4a RTL pass.

## RTL Entry Criteria

Proceed to Chisel implementation only if all are accepted:

1. Use the normalized reciprocal LUT design above, not a general divider.
2. Allow multi-cycle finalization.
3. Reuse at most one DSP48 for density reciprocal in the first implementation.
4. Add a software mirror mode matching the exact LUT contents before RTL review.
5. Add RTL/unit tests for zero area, small area saturation, large area underflow, and round-half-even boundaries.
6. Preserve the existing AXI-stream packet shape and board-level DMA protocol.

## Recommendation

Density should be included in the v1.4a RTL plan if the design accepts a multi-cycle finalization stage. The evidence is strong:

- `density_recip` alone improves QMLP prediction agreement from 79.90% to 95.20%.
- `mean_density_recip` reaches 96.90%.
- `candidate_v1p4a` reaches 97.00%.
- f13 is present in 199/201 v1p3 changed predictions, but 0/30 candidate_v1p4a changed predictions.

The proposed LUT-based reciprocal avoids a full divider and appears resource/timing controlled enough for a first Chisel implementation pass.
