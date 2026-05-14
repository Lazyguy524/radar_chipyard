# Feature21 Thesis Methodology

Date: 2026-05-05

This document gives a thesis-ready methodology narrative based on existing reports and logs. It intentionally avoids claiming that hardware Feature21 is fully equivalent to software Feature21.

## 1. Four-Level Verification Chain

The project uses a four-level validation chain:

```text
Software golden
    -> Python hardware mirror
    -> RTL / Chisel implementation
    -> Board dump and task-level validation
```

| Level | Role | Thesis interpretation |
|---|---|---|
| Software golden | Original Feature21 int8 features and QMLP logits/predictions from the reference software pipeline | Defines the algorithmic reference, not the exact hardware contract |
| Python HW mirror | Bit-consistent model of the hardware-friendly approximation | Bridges algorithm exploration and RTL; enables ablation before RTL changes |
| RTL / Chisel | Implements the selected approximation in the FPGA datapath | Must match the Python mirror bit-for-bit for the selected approximation |
| Board | Runs the integrated SoC and emits compact 21-byte Feature21 dumps | Confirms real hardware behavior and measures end-to-end prediction impact |

The most important verification split is:

- RTL vs Python mirror asks: did the hardware implement the intended approximation correctly?
- Software golden vs board asks: how much does the approximation differ from the original software Feature21?
- QMLP prediction agreement asks: how much do those feature differences matter for the final classification task?

## 2. Hardware-Friendly Fixed-Point Approximation

Feature21 contains operations that are expensive or awkward in FPGA streaming hardware, including divisions, reciprocal-like density computation, range/statistics terms, and eigenvalue-like geometry proxies. The hardware therefore uses fixed-point approximations rather than attempting to reproduce the full software path exactly.

For v1.4a, the controlled RTL change is limited to f13 `density_2d`. The implemented density approximation uses a normalized reciprocal LUT:

```text
area_q16p16 = span_x * span_y
mant8 normalized to 128..255
lut_index = mant8 - 128
recip_lut[index] = round_nearest_even(2^23 / mant8)
density_q8p8 reconstructed by exponent-dependent shifting
f13 = clamp_u7(bank_round_shift(density_q8p8 * 105, 16))
```

This design is hardware-friendly because the reciprocal is reduced to a small exact LUT plus shifts and fixed-width multiplications. The board result confirms that this approximation is implemented consistently: full 21-byte RTL vs Python mirror match is `1000/1000`, and f13 RTL vs Python mirror match is `1000/1000`.

## 3. Per-Feature Error Attribution

The methodology does not treat feature mismatch as a single opaque number. Instead, errors are attributed by feature and then linked to prediction flips.

For the current v1.4a board result:

| Feature | Evidence in changed predictions | Interpretation |
|---|---:|---|
| f13 `density_2d` | 0 mismatches in 48 changed predictions | Density is no longer the residual flip source |
| f11 `eig_major` | 33 mismatches, MAE 15.146, max 121 | Dominant remaining residual |
| f1 `mean_x` | 47 mismatches, MAE 3.125 | Secondary mean-related residual |
| f9 `centroid_range` | 43 mismatches, MAE 2.667 | Geometry/range residual |
| f10 `azimuth_span` | 44 mismatches, MAE 1.062 | Geometry residual |

The maximum absolute int8 error is `122`, and the max-error events are on f11 `eig_major`, not f13 density. This supports a clean conclusion: v1.4a solved the density-driven error source identified in v1p3, while the remaining approximation gap is mainly in eigen/statistical proxy features.

For f11 specifically, the software feature is covariance/eigenvalue based (`eig_max(cov([[x], [y]]))`), while the frozen hardware proxy is span-derived: `eig_major_proxy = max(span_x >> 2, span_y >> 2)`. On samples `332/333/336/591/592`, the software-side covariance major eigenvalue saturates to int8 `127`, while the board and Python mirror produce `5`. This is a documented statistical-geometry proxy limitation and should be presented as future work, not as a density or RTL-bitmatch failure.

## 4. Task-Level Prediction Agreement as a Design Metric

Feature-byte equality is not the only relevant design metric for an approximate preprocessor. The final system uses Feature21 as input to QMLP classification, so the thesis evaluates both feature-level error and task-level prediction stability.

Current v1.4a board result:

| Metric | Value |
|---|---:|
| Software-golden vs board feature match | 67.10% |
| Mean abs int8 error | 0.791 |
| Max abs int8 error | 122 |
| QMLP prediction agreement | 95.20% |
| Changed predictions | 48/1000 |
| Golden-feature subset accuracy | 89.70% |
| Board-feature subset accuracy | 91.10% |

Prediction agreement is used as a design metric because it directly measures whether the hardware-approximated feature vector preserves the final class decision of the software-golden feature vector. Accuracy is also reported, but agreement is the cleaner hardware-approximation metric because it isolates the effect of the preprocessor approximation from dataset/model generalization.

## 5. Why 67.10% Feature Match and 95.20% QMLP Agreement Can Coexist

The two numbers measure different things:

- `67.10%` feature match is byte-level equality over all 21 int8 features and 1000 samples.
- `95.20%` QMLP agreement is sample-level prediction equality after the QMLP consumes the whole feature vector.

This is reasonable for several reasons.

First, many feature mismatches are small. The current mean absolute int8 error is only `0.791`, so a large number of byte mismatches are off-by-small-value differences rather than large semantic changes.

Second, QMLP classification is margin-based. A feature vector can differ at several bytes while still staying on the same side of the decision boundary.

Third, not every feature has equal task importance for every sample. After the density fix, f13 has only `4/1000` software-vs-board mismatches and `0/48` mismatches among changed predictions. The remaining flips concentrate around f11 `eig_major` and geometry/statistics proxies.

Fourth, feature-level match counts every byte equally, while task-level agreement measures the final decision. A mismatch in a low-impact feature or a low-sensitivity region can reduce feature match without changing the predicted class.

Therefore, the correct thesis claim is not "hardware Feature21 is equivalent to software Feature21." The correct claim is: "the selected hardware approximation is bit-consistent with its Python mirror and preserves QMLP predictions for 95.20% of the evaluated 1000 samples."

## 6. Recommended Thesis Wording

Use:

> The hardware Feature21 block is a fixed-point, hardware-friendly approximation of the software Feature21 extractor. Its RTL behavior is verified against a bit-consistent Python hardware mirror, and its classification impact is evaluated through QMLP prediction agreement.

Avoid:

> The hardware Feature21 block is fully equivalent to the software Feature21 implementation.

Use:

> On the 1000-sample board dump, v1.4a achieves 1000/1000 full-vector agreement against the Python exact-LUT mirror, 67.10% byte-level agreement against the original software Feature21, and 95.20% QMLP prediction agreement.

Avoid:

> The board Feature21 implementation exactly reproduces all software-golden features.

## 7. Boundary of the Current Claim

The current thesis baseline is v1.4a density exact-LUT. It does not include:

- `mean_recip` in RTL,
- `range_piecewise` in RTL,
- std/eig proxy redesign,
- a claim that board-side QMLP hardware classification was used for the 1000-sample agreement metric.

The 1000-sample QMLP agreement metric is computed by feeding board-dumped Feature21 vectors into software QMLP inference.

## 8. Source Reports

| Topic | Source |
|---|---|
| Final summary | `logs/radar_nexysvideo/runtime/feature21-project-final-summary.md` |
| v1.4a board validation | `logs/radar_nexysvideo/runtime/664-feature21-v1p4a-density-compact-validation-1000-2026-04-26.md` |
| Residual attribution | `logs/radar_nexysvideo/runtime/feature21-v1p4a-residual-error-attribution-1000.md` |
| Software ablation | `logs/radar_nexysvideo/runtime/658-feature21-v1p4a-density-exact-lut-e2e-2026-04-25.md` |
| Feature spec and f11 formula | `docs/feature_preproc_compare_20260420/feature21/feature_spec_21.md` |
