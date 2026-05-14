# Feature21 Thesis Experiment Summary

Date: 2026-05-05

This document is a thesis-facing summary of existing reports and logs only. It does not modify RTL/Chisel, does not generate a bitstream, and does not add `mean_recip`.

## 1. Version-Level Feature21 Comparison

| Version / source | Evaluation scope | Samples | Software-golden feature match | Exact vectors | Mean abs int8 error | Max abs int8 error | QMLP agreement | Changed predictions | Cycles avg/min/max |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v1.3 fixed-point | Historical board golden subset | 16 | 73.50% | 0/16 | 1.181 | 73 | TODO: not available in this board log | TODO | 404 / 356 / 690 |
| v1p3 fixed-point mirror | Python HW mirror, same 1000-sample subset | 1000 | 62.45% | 0/1000 | 1.304 | 126 | 79.90% | 201/1000 | N/A |
| v1.4a density exact-LUT | Board compact 21-byte dump | 1000 | 67.10% | 3/1000 | 0.791 | 122 | 95.20% | 48/1000 | 397 / 387 / 589 |

Notes:

- The v1.3 board row is a 16-sample characterization; it should not be directly compared as a statistically equivalent 1000-sample board experiment.
- The v1p3 1000-sample row is a Python hardware mirror result, not a board dump.
- The v1.4a row is the current final board result for the thesis baseline.

## 2. Software Ablation

Feature-level fidelity is measured against software-golden Feature21 int8 vectors on the same 1000-sample subset.

| Mode | Feature match | Exact vectors | Mean abs int8 error | Max abs int8 error | Status |
|---|---:|---:|---:|---:|---|
| `v1p3` | 62.45% | 0/1000 | 1.304 | 126 | Baseline fixed-point mirror |
| `density_recip_exact_lut` | 67.10% | 3/1000 | 0.791 | 122 | Implemented and board-confirmed as v1.4a |
| `mean_density_recip_exact_lut` | 79.57% | 23/1000 | 0.477 | 122 | Offline candidate only; no RTL claim |
| `candidate_v1p4a` | 83.08% | 35/1000 | 0.408 | 122 | Offline candidate only; includes mean + range + density |

QMLP end-to-end ablation on the same 1000 samples:

| Mode | Prediction agreement | Changed predictions | Approx accuracy | Golden accuracy | Mean abs logit error | Max abs logit error | f13 in changed predictions |
|---|---:|---:|---:|---:|---:|---:|---:|
| `v1p3` | 79.90% | 201/1000 | 87.40% | 89.70% | 2020.190 | 10430 | 199/201 |
| `density_recip_exact_lut` | 95.20% | 48/1000 | 91.10% | 89.70% | 794.828 | 6344 | 0/48 |
| `mean_density_recip_exact_lut` | 96.90% | 31/1000 | 88.60% | 89.70% | 381.195 | 7321 | 0/31 |
| `candidate_v1p4a` | 97.00% | 30/1000 | 88.50% | 89.70% | 366.852 | 7301 | 0/30 |

Interpretation:

- Density exact-LUT is the only ablation in this set that has been implemented and board-confirmed.
- `mean_density_recip_exact_lut` and `candidate_v1p4a` are useful future directions, but they must not be presented as current hardware results.
- Accuracy is label accuracy on this 1000-sample subset. Agreement measures whether the approximated-feature QMLP prediction matches the software-golden-feature QMLP prediction.

## 3. Board RTL vs Python Mirror

| Check | Result |
|---|---:|
| Board samples | 1000 |
| Python mirror mode | `density_recip_exact_lut` |
| Full 21-byte RTL vs Python mirror match | 1000/1000 |
| Full-vector feature match rate | 100.00% |
| f13 `density_2d` RTL vs Python mirror match | 1000/1000 |
| Mean abs int8 error vs Python mirror | 0.000 |
| Max abs int8 error vs Python mirror | 0 |

This validates that the v1.4a RTL behavior is bit-consistent with the Python hardware mirror for the 1000-sample board dump.

## 4. Software Golden vs Board Feature21

| Metric | Value |
|---|---:|
| Samples | 1000 |
| Feature bytes compared | 21000 |
| Matched feature bytes | 14091 |
| Mismatched feature bytes | 6909 |
| Feature match rate | 67.10% |
| Exact 21-byte vectors | 3/1000 |
| Mean abs int8 error | 0.791 |
| Max abs int8 error | 122 |
| f13 `density_2d` software-vs-board match | 996/1000 |

The 67.10% feature match is an approximation-fidelity metric against the original software Feature21, not an RTL correctness failure. RTL correctness for the chosen approximation is captured by the 1000/1000 mirror match above.

## 5. QMLP Agreement / Accuracy / Changed Predictions

| Metric | Value |
|---|---:|
| Method | Software QMLP inference fed by board-dumped Feature21 vectors |
| Golden-logit reproduction in software path | 1000/1000 exact samples |
| Prediction agreement | 95.20% |
| Changed predictions | 48/1000 |
| Golden-feature subset accuracy | 89.70% |
| Board-feature subset accuracy | 91.10% |
| Mean abs logit error | 794.828 |
| Max abs logit error | 6344 |

Changed prediction quadrant vs f13:

| Quadrant | Count |
|---|---:|
| Prediction same, f13 same | 948 |
| Prediction same, f13 mismatch | 4 |
| Prediction changed, f13 same | 48 |
| Prediction changed, f13 mismatch | 0 |

Conclusion: after v1.4a, f13 density is no longer the source of residual prediction flips.

### 1000-Sample Class Balance and Confusion Matrices

Data source:

- Board dump: `logs/radar_nexysvideo/runtime/664-feature21-v1p4a-density-compact-dump-1000-retry-2026-04-26-2026-04-26-152018.log`
- Labels: `docs/feature_preproc_compare_20260420/feature21/golden/labels_int64.npy`
- Software-golden features: `docs/feature_preproc_compare_20260420/feature21/golden/features_int8_21.bin`
- QMLP params: `docs/feature_preproc_compare_20260420/feature21/qmlp_params_21.h`

Class mapping follows `model_metrics.json`: label `0 = pedestrian`, label `1 = vehicle`.

| Class | Count | Share |
|---|---:|---:|
| pedestrian | 500 | 50.00% |
| vehicle | 500 | 50.00% |
| total | 1000 | 100.00% |

Rows are true labels and columns are predicted labels.

Software-golden Feature21 -> software QMLP:

| True \ Pred | pedestrian | vehicle | Total |
|---|---:|---:|---:|
| pedestrian | 397 | 103 | 500 |
| vehicle | 0 | 500 | 500 |
| total | 397 | 603 | 1000 |

Board Feature21 -> software QMLP:

| True \ Pred | pedestrian | vehicle | Total |
|---|---:|---:|---:|
| pedestrian | 411 | 89 | 500 |
| vehicle | 0 | 500 | 500 |
| total | 411 | 589 | 1000 |

The board-feature accuracy is higher on this fixed subset by `14/1000` samples, but this is not claimed as a general model improvement. The primary hardware-approximation metric remains prediction agreement (`95.20%`).

## 6. Runtime Cycles and CPU Baseline Status

| Samples | Cycles avg | Cycles min | Cycles max | Total points |
|---:|---:|---:|---:|---:|
| 100 | 396 | 387 | 591 | TODO |
| 500 | 395 | 387 | 589 | TODO |
| 1000 | 397 | 387 | 589 | 26642 |

For the 1000-sample board dump, average points/sample is `26642 / 1000 = 26.642`, so the measured hardware Feature21 latency corresponds to approximately `397 / 26.642 = 14.90 cycles/point`. This is descriptive hardware latency context only.

CPU-only baseline status:

| Baseline item | Value / status |
|---|---|
| CPU-only Feature21 preprocessing cycles/sample | TODO: no reliable existing program/log found |
| CPU-only Feature21 preprocessing cycles/point | TODO: no reliable existing program/log found |
| CPU Feature21 vs hardware Feature21 speedup | TODO: do not claim |
| Existing CPU-only QMLP pure forward | avg `165343` cycles/inference; not a Feature21 preprocessing baseline |

Because no directly comparable CPU-only Feature21 preprocessing baseline was found in the existing logs, this summary does not claim a CPU-vs-hardware Feature21 speedup.

## 7. Resource and Timing Context

Standalone Feature21 synthesis, `xc7a200tsbg484-1`, 20 ns target:

| Metric | Value |
|---|---:|
| Slice LUTs | 2655 |
| Slice registers / FF | 1026 |
| DSP48E1 | 2 |
| Block RAM tile | 0 |
| LUTRAM | 0 |
| WNS | +4.050 ns |
| TNS | 0.000 ns |
| Hold slack WHS | +0.142 ns |

Full routed SoC implementation:

| Scope | LUTs | Logic LUTs | LUTRAM | SRL | FF | RAMB36 | RAMB18 | DSP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `NexysVideoHarness` | 30865 | 26845 | 3726 | 294 | 19056 | 2 | 14 | 12 |
| `radarDMA` | 8000 | 7905 | 8 | 87 | 5814 | 2 | 2 | 2 |
| `radarDMA/feature21` | 2493 | 2493 | 0 | 0 | 1101 | 0 | 0 | 2 |

| Full routed timing metric | Value |
|---|---:|
| WNS | +0.349 ns |
| TNS | 0.000 ns |
| Setup failing endpoints | 0 |
| WHS | +0.050 ns |
| THS | 0.000 ns |
| Hold failing endpoints | 0 |

The reported worst setup path is in the TSI/front-bus buffering path, not in the Feature21 density path.

## 8. Source Reports

| Topic | Source |
|---|---|
| v1.3 board subset | `logs/radar_nexysvideo/runtime/654-feature21-golden-subset-summary-2026-04-25.md` |
| Software ablation and QMLP e2e | `logs/radar_nexysvideo/runtime/658-feature21-v1p4a-density-exact-lut-e2e-2026-04-25.md` |
| v1.4a 1000-sample board validation | `logs/radar_nexysvideo/runtime/664-feature21-v1p4a-density-compact-validation-1000-2026-04-26.md` |
| Residual attribution | `logs/radar_nexysvideo/runtime/feature21-v1p4a-residual-error-attribution-1000.md` |
| 1000-sample labels / class balance | `docs/feature_preproc_compare_20260420/feature21/golden/labels_int64.npy`, `docs/feature_preproc_compare_20260420/feature21/model_metrics.json` |
| CPU-only QMLP reference, not Feature21 | `logs/radar_nexysvideo/runtime/350-qmlp-cpu-only-pure-forward-summary-2026-04-09.md` |
| Standalone synthesis | `logs/radar_nexysvideo/runtime/661-feature21-v1p4a-density-synth-precheck-summary-2026-04-26.md` |
| Full implementation summary | `logs/radar_nexysvideo/runtime/662-feature21-v1p4a-density-bitstream-and-board-attempt-summary-2026-04-26.md` |
