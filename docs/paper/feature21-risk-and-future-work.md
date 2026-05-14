# Feature21 Risk and Future Work

Date: 2026-05-05

This document lists likely review questions, current evidence, and thesis-safe responses. Missing data is marked `TODO` rather than inferred.

## 1. QMLP 是否需要 Hardware-Aware Training

Potential concern:

> The hardware preprocessor changes the input feature distribution. Should the QMLP be retrained with hardware-approximated features?

Current evidence:

| Item | Value |
|---|---:|
| Current v1.4a prediction agreement | 95.20% |
| Changed predictions | 48/1000 |
| Board-feature subset accuracy | 91.10% |
| Golden-feature subset accuracy | 89.70% |
| Full test fixed-point C-trace accuracy | 97.217% |
| Full test QAT student accuracy | 96.455% |

Thesis-safe response:

- Hardware-aware training is not required to validate the current hardware baseline, because the thesis evaluates approximation impact explicitly through prediction agreement.
- It is a strong future-work direction: train or fine-tune QMLP using Python-mirror or board-dumped Feature21 vectors, then compare accuracy/agreement against the current fixed model.
- Do not claim the current QMLP was trained with v1.4a hardware features unless a separate training record is added.

Suggested future experiment:

| Experiment | Goal | Status |
|---|---|---|
| Train QMLP on `density_recip_exact_lut` mirror features | Reduce residual sensitivity to hardware approximation | TODO |
| Train QMLP on `mean_density_recip_exact_lut` candidate features | Estimate benefit before RTL | TODO |
| Evaluate on board-dumped Feature21 vectors | Confirm real-hardware generalization | TODO |

## 2. Test Split / Class Balance / Accuracy vs Agreement

Potential concern:

> Are the 1000 board samples representative? What is the class balance? Why report agreement instead of only accuracy?

Known data:

| Dataset / metric | Value |
|---|---:|
| Full fixed-point C-trace test sample count | 55516 |
| Full test class counts from confusion matrix | pedestrian 16580, vehicle 38936 |
| 1000-sample board subset sample count | 1000 |
| 1000-sample board subset class balance | pedestrian 500, vehicle 500 |
| 1000-sample golden-feature accuracy | 89.70% |
| 1000-sample board-feature accuracy | 91.10% |
| 1000-sample prediction agreement | 95.20% |

Rows are true labels and columns are predicted labels.

| Input features | Confusion matrix | Accuracy |
|---|---|---:|
| Software-golden Feature21 -> software QMLP | `[[397, 103], [0, 500]]` | 89.70% |
| Board Feature21 -> software QMLP | `[[411, 89], [0, 500]]` | 91.10% |

Thesis-safe response:

- Accuracy measures correctness against labels.
- Agreement measures whether the hardware approximation preserves the software-golden QMLP decision.
- Agreement is the primary hardware-approximation metric because it isolates the preprocessor change. Accuracy should still be reported, but a small accuracy increase on a subset should not be over-interpreted as a general model improvement.
- The 1000-sample subset is balanced, so the reported confusion matrices are easier to interpret than the full imbalanced test split; however, it is still a fixed subset and should not be over-claimed as a full-test accuracy result.

补强建议:

- If time permits, repeat board-dump validation on a stratified subset or multiple random windows.

## 3. f11 `eig_major` Max Error 122 的 Root Cause

Potential concern:

> The max abs int8 error is 122. Is this a serious correctness issue?

Current evidence:

| Item | Value |
|---|---:|
| Overall max abs int8 error | 122 |
| Max-error feature | f11 `eig_major` |
| Max-error event count | 5 |
| Changed-prediction f11 mismatch count | 33/48 |
| Changed-prediction f11 MAE | 15.146 |
| Changed-prediction f11 max | 121 |
| f13 mismatches in changed predictions | 0/48 |

Observed max-error examples:

| Sample | Feature | Golden | Board | Diff |
|---:|---|---:|---:|---:|
| 332 | f11 `eig_major` | 127 | 5 | -122 |
| 333 | f11 `eig_major` | 127 | 5 | -122 |
| 336 | f11 `eig_major` | 127 | 5 | -122 |
| 591 | f11 `eig_major` | 127 | 5 | -122 |
| 592 | f11 `eig_major` | 127 | 5 | -122 |

Current interpretation:

- This is the main remaining approximation risk after the density fix.
- The root cause is the mismatch between the software covariance/eigenvalue feature and the current hardware-friendly span-derived proxy.
- This belongs to the eig/statistical geometry proxy family, not to the v1.4a density exact-LUT logic.

Software formula vs current hardware proxy:

| Item | Formula / behavior |
|---|---|
| Software f11 | `eig_max(cov([[x], [y]]))`, then Feature21 int8 quantization |
| Current hardware/Python mirror f11 proxy | `std_x_proxy = span_x >> 2`, `std_y_proxy = span_y >> 2`, `eig_major_proxy = max(std_x_proxy, std_y_proxy)` |
| Current board-vs-mirror status | Board f11 matches the Python mirror; the gap is against software golden |

Max-error sample proxy evidence:

| Sample | Points | Golden f11 | Board f11 | Mirror f11 | q8.8 span_x | q8.8 span_y | Proxy q8.8 `max(span>>2)` | Quantized proxy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 332 | 17 | 127 | 5 | 5 | 11727 | 1039 | 2931 | 5 |
| 333 | 20 | 127 | 5 | 5 | 11975 | 1051 | 2993 | 5 |
| 336 | 21 | 127 | 5 | 5 | 13126 | 840 | 3281 | 5 |
| 591 | 23 | 127 | 5 | 5 | 13677 | 10797 | 3419 | 5 |
| 592 | 22 | 127 | 5 | 5 | 13575 | 12295 | 3393 | 5 |

Diagnostic covariance check over the same Q8.8-converted points:

| Sample | N | Unbiased `eig_max` | `eig_max / 2.43614531` | Software-side tendency | Proxy value in input units | Board f11 |
|---:|---:|---:|---:|---|---:|---:|
| 332 | 17 | 326.402 | 134.0 | saturates to 127 | 11.452 | 5 |
| 333 | 20 | 414.026 | 170.0 | saturates to 127 | 11.694 | 5 |
| 336 | 21 | 315.735 | 129.6 | saturates to 127 | 12.818 | 5 |
| 591 | 23 | 483.181 | 198.3 | saturates to 127 | 13.356 | 5 |
| 592 | 22 | 696.136 | 285.8 | saturates to 127 | 13.257 | 5 |

The diagnostic check uses the existing raw input files and the same float32-to-Q8.8 conversion used by the Python hardware mirror. It is used for attribution only; it does not introduce a new hardware claim.

补强建议:

- Add intermediate debug for covariance/eigen proxy terms in the Python mirror.
- Consider a v1.5 study focused only on std/eig proxies.

Status: closed as a limitation/future-work item. No RTL change is made in the frozen v1.4a baseline.

## 4. Resource / Timing 表格缺失项

Potential concern:

> Are resource and timing numbers complete enough for a thesis?

Available:

| Scope | Available metrics |
|---|---|
| Standalone Feature21 synth | LUT, FF, DSP, BRAM, LUTRAM, WNS/TNS/WHS/THS |
| Full routed SoC | Hierarchical LUT/FF/RAM/DSP for harness, `radarDMA`, `radarDMA/feature21`; WNS/TNS/WHS/THS |

Missing or optional:

| Missing item | Status |
|---|---|
| Power estimate | TODO |
| Frequency sweep after v1.4a | TODO |
| Before/after resource delta vs v1.3 full routed design | TODO |
| Standalone vs full implementation resource normalization | TODO |
| DSP pipelining warning discussion | Available qualitatively; quantitative impact TODO |

补强建议:

- Add one final table with v1.3 vs v1.4a resource deltas if the v1.3 implementation report is available.
- Keep the v1.4a routed timing claim conservative: WNS `+0.349 ns` at 20 ns, worst path not in Feature21 density logic.

## 5. CPU Baseline 是否需要补

Potential concern:

> Without a CPU baseline, how do we know the hardware preprocessor is useful?

Current status:

| Baseline | Status |
|---|---|
| Feature21 hardware cycles | Available: 397 / 387 / 589 avg/min/max |
| CPU-only Feature21 preprocessing latency | TODO |
| CPU-only QMLP pure forward summary | Available: avg `165343` cycles/inference, but not a directly comparable Feature21 preprocessing baseline |
| End-to-end CPU vs hardware wall-clock | TODO |

Additional hardware context:

| Metric | Value |
|---|---:|
| 1000-sample total points | 26642 |
| Average points/sample | 26.642 |
| Approx hardware Feature21 cycles/point | 14.90 |

Thesis-safe response:

- If the thesis contribution is approximation/validation methodology and FPGA integration, the current hardware cycles are useful but not a complete acceleration claim.
- Do not claim speedup without a directly comparable CPU Feature21 baseline.
- The available CPU-only result is for QMLP pure forward, not Feature21 preprocessing, so it cannot be used as a Feature21 speedup denominator.

补强建议:

- Add bare-metal CPU Feature21 preprocessing on the same 1000 samples.
- Report cycles/sample and cycles/point.
- Separate preprocessing latency from DMA/control overhead.

## 6. `mean_recip` 为什么暂缓

Potential concern:

> `mean_density_recip_exact_lut` improves feature match and agreement. Why not add it?

Evidence:

| Mode | Feature match | Prediction agreement | Changed predictions | Status |
|---|---:|---:|---:|---|
| `density_recip_exact_lut` | 67.10% | 95.20% | 48/1000 | Current RTL baseline |
| `mean_density_recip_exact_lut` | 79.57% | 96.90% | 31/1000 | Offline only |
| `candidate_v1p4a` | 83.08% | 97.00% | 30/1000 | Offline only |

Thesis-safe response:

- `mean_recip` is promising, but adding it now would change the final hardware baseline and require a fresh RTL, timing, board, and residual-attribution cycle.
- Current project stage prioritizes convergence and defensible reporting.
- The v1.4a density result already has a clean validation story: density was identified as a major v1p3 error source, fixed in RTL, and confirmed 1000/1000 against the mirror.

Future work:

- Implement `mean_recip` as a separate versioned experiment.
- Require mirror match, board dump, QMLP agreement, resource/timing, and new-flip attribution before claiming it.

## 7. `range_piecewise` 为什么跳过

Potential concern:

> Why skip `range_piecewise` if it is hardware-friendly?

Evidence:

| Mode | Prediction agreement | Changed predictions | New changed predictions vs current 48 |
|---|---:|---:|---:|
| `density_recip_exact_lut` | 95.20% | 48/1000 | 0 |
| `range_piecewise` | 80.00% | 200/1000 | 168 |
| `range_density_recip` | 95.00% | 50/1000 | 6 |
| `candidate_v1p4a` | 97.00% | 30/1000 | 9 |

Thesis-safe response:

- `range_piecewise` alone is not safe on the current evidence because it introduces many prediction flips.
- Its benefit appears dependent on being combined with other approximation changes, so it should not be mixed into the final v1.4a baseline.

Future work:

- Study range features together with f11/f12 eigen proxies and decision-margin sensitivity.
- Only move to RTL after a range-specific residual report shows no large new-flip risk.

## 8. Std/Eig Proxy 作为 Future Work

Potential concern:

> If f11 dominates residual error, should std/eig approximation be the next target?

Current evidence:

| Feature group | Evidence |
|---|---|
| f11 `eig_major` | Dominant changed-sample residual; max abs error source |
| f3/f4/f15/f19 std proxies | Smaller but visible residual contributors |
| f13 density | No longer causes changed predictions |

Future-work direction:

- Build a v1.5 approximation study for std/eig features.
- Compare current proxy vs a more accurate fixed-point covariance/eigen approximation.
- Evaluate both feature error and QMLP agreement, not feature error alone.
- Consider hardware-aware training after the proxy is stable.

Suggested acceptance gates:

| Gate | Required result |
|---|---|
| Python mirror ablation | Improved f11 error without large new prediction flips |
| RTL implementation | 1000/1000 match against mirror |
| Board validation | Feature dump and QMLP agreement on same 1000-sample subset |
| Resource/timing | No timing regression; resource delta reported |

## 9. Claims to Avoid

Avoid these claims:

- Hardware Feature21 is fully equivalent to software Feature21.
- v1.4a includes `mean_recip` or `range_piecewise`.
- The 1000-sample QMLP agreement was measured by board-side QMLP hardware classification.
- Feature match 67.10% means the RTL is incorrect.
- Board-feature accuracy 91.10% proves a general model accuracy improvement.

Use these claims:

- v1.4a density exact-LUT RTL matches the Python hardware mirror for `1000/1000` full 21-byte board samples.
- Software-golden vs board Feature21 match is `67.10%`, reflecting a controlled fixed-point approximation.
- Board-dumped Feature21 vectors preserve QMLP predictions for `95.20%` of the 1000 evaluated samples.
- Remaining changed predictions are mainly associated with f11 `eig_major` and geometry/statistics proxy errors, not f13 density.

## 10. Source Reports

| Topic | Source |
|---|---|
| Board validation | `logs/radar_nexysvideo/runtime/664-feature21-v1p4a-density-compact-validation-1000-2026-04-26.md` |
| Residual attribution | `logs/radar_nexysvideo/runtime/feature21-v1p4a-residual-error-attribution-1000.md` |
| Software ablation | `logs/radar_nexysvideo/runtime/658-feature21-v1p4a-density-exact-lut-e2e-2026-04-25.md` |
| Model metrics | `docs/feature_preproc_compare_20260420/feature21/model_metrics.json` |
| 1000-sample labels | `docs/feature_preproc_compare_20260420/feature21/golden/labels_int64.npy` |
| Feature spec and f11 formula | `docs/feature_preproc_compare_20260420/feature21/feature_spec_21.md` |
| CPU-only QMLP reference, not Feature21 | `logs/radar_nexysvideo/runtime/350-qmlp-cpu-only-pure-forward-summary-2026-04-09.md` |
| Standalone synthesis | `logs/radar_nexysvideo/runtime/661-feature21-v1p4a-density-synth-precheck-summary-2026-04-26.md` |
| Full implementation summary | `logs/radar_nexysvideo/runtime/662-feature21-v1p4a-density-bitstream-and-board-attempt-summary-2026-04-26.md` |
