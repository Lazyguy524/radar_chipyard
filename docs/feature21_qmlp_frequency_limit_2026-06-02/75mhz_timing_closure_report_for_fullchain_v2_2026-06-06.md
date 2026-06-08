# Feature21/QMLP 75 MHz Timing Closure Report for FullChain v2

Date: 2026-06-06

## Purpose

This report archives the Feature21 + QMLP 75 MHz timing-closure work as a design input for later FullChain v2 optimization. It separates durable engineering lessons from the long rolling debug log, so future FullChain v2 work can reuse the path-prioritization and implementation-strategy evidence without reopening large Vivado logs.

Primary rolling context:

- `docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md`

Current promoted 75 MHz artifacts:

- Bitstream: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/NexysVideoHarness.bit`
- Timing: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/report/timing.txt`
- Bitstream SHA256: `530cceaee2e9d433b5829d32340012fd1ee107c9b16adc4115013f6e2f8cb665`
- Timing SHA256: `d5a81563a12c8977e60584621f7ccd4cc946293de1f5e46e5ef4b0023aea9482`

## Current Best 75 MHz Result

The current promoted 75 MHz candidate is timing-clean, but the guardband is thin:

| Metric | Value |
| --- | ---: |
| WNS | `+0.040 ns` |
| TNS | `0.000 ns` |
| Setup failing endpoints | `0` |
| WHS | `+0.017 ns` |
| THS | `0.000 ns` |
| Hold failing endpoints | `0` |

Worst final setup path:

| Field | Value |
| --- | --- |
| Source | `rockettile/frontend/icache/s2_dout_0_reg[15]` |
| Destination | `rockettile/core/ex_reg_rs_msb_0_reg[49]` |
| Path class | Rocket frontend/icache/fetch-queue/control into execute decode |
| Slack | `+0.040 ns` |
| Requirement | `13.333 ns` |
| Data path delay | `12.461 ns` |
| Logic delay | `2.204 ns` |
| Route delay | `10.257 ns` |
| Route share | about `82.3%` |
| Logic levels | `13` |

Interpretation: after the accelerator and TSI cuts, the remaining limiter is a route-dominated Rocket frontend/core path. It is no longer a direct QMLP, Feature21 ordinary quantization, or UART-TSI TL-A path.

## Closure Timeline

| Stage | Result | Key finding |
| --- | ---: | --- |
| Historical 75 MHz baseline | WNS `-3.059 ns` | Dominated by `fbus/tsi2tl -> fbus/buffer` TL-A request path. |
| 60 MHz after UART-TSI boundary buffer | WNS `-1.578 ns` | QMLP, Feature21, and buffered TSI all became near-coequal failures. |
| QMLP MAC staging + Feature21 quant/write split | 60 MHz WNS `+0.018 ns` | Accelerator datapath cuts were effective but margin remained very thin. |
| Feature21 density/general quant split | 60 MHz WNS `+0.162 ns` | 60 MHz preferred candidate; worst path moved back to buffered TSI. |
| TSI read-request pipeline + QMLP balanced requant | 75 MHz WNS `+0.021 ns` | 75 MHz first closed; final path shifted to Rocket frontend/core. |
| MoreGlobalIterations route variant | 75 MHz WNS `+0.040 ns` | Best observed 75 MHz candidate; promoted into generated `obj`. |
| Later route/physopt variants | max WNS `+0.040 ns` | No tested directive exceeded the promoted candidate. |

## RTL Changes That Mattered

### UART-TSI / Front Bus

Implemented timing cuts:

- Added `TLBuffer(BufferParams.pipe)` at the UART-TSI FBUS coupling boundary in `PeripheryUARTTSI.scala`.
- Added internal TL-A request staging in `TSIToTileLink.scala`.
- Split read request preparation into measure, size, prepare, and request phases.
- Fixed the multi-beat read bug introduced by the first A-register-only experiment.

Effect:

- Historical 75 MHz top path through raw `TSIToTileLink` request generation was removed from the final top path list.
- TSI remains a functional validation watch item because the bring-up/readback FSM changed.

### QMLP

Implemented timing cuts:

- Added per-layer MAC prep states:
  - `Load -> Prep -> Mac`
- Registered selected activation lanes and weight lanes through:
  - `macDataRegs`
  - `macWeightRegs`
  - `biasStageReg`
- Replaced the linear fixed-point requant shift-add fold with a balanced fixed-width sum helper.

Effect:

- The previous `outIdx/inIdx -> async ROM -> lane multiply/sum -> accReg` path no longer appears as a final leading 75 MHz path.
- QMLP is not currently the timing limiter.

### Feature21

Implemented timing cuts:

- Split feature byte generation:
  - `sFeatureSelect -> sFeatureQuantMul -> sFeatureQuantRound -> sFeatureWrite`
- Added:
  - `featureQuantProductReg`
  - `featureByteReg`
- Split density quantization through:
  - `densityQuantProductReg`

Rejected experiment:

- A deeper density area/product DSP pipeline was tried and reverted.
- It failed timing at 75 MHz with WNS `-0.169 ns`, did not absorb into DSP internal pipeline registers, and moved DRC warnings rather than solving them.

Effect:

- Ordinary Feature21 quant/writeback no longer leads timing.
- Feature21 density tail can still reappear as a secondary near-top path in bad route shapes.

## Physical Implementation Results

Current winner:

| Route directive | Post-route physopt directive | Final WNS | Status |
| --- | --- | ---: | --- |
| `MoreGlobalIterations` | `Explore` | `+0.040 ns` | Promoted |
| `MoreGlobalIterations` | `AggressiveExplore` | `+0.040 ns` | Tied |
| `MoreGlobalIterations` | `ExploreWithHoldFix` | `+0.040 ns` | Tied |

Rejected or non-improving variants:

| Variant | Final WNS | Note |
| --- | ---: | --- |
| Baseline refreshed flow | `+0.021 ns` | Timing clean but worse than promoted candidate. |
| `AggressiveExplore + AggressiveExplore` | `+0.021 ns` | No improvement. |
| `WLDrivenBlockPlacement + MoreGlobalIterations + Explore` | `+0.000 ns` | Timing-clean but no guardband. |
| `MoreGlobalIterations + AlternateFlowWithRetiming` | `-0.061 ns` | Failed; QoR retiming hint did not help from this placement. |
| `MoreGlobalIterations + AlternateReplication` | `-0.061 ns` | Failed. |
| `MoreGlobalIterations + AggressiveFanoutOpt` | `-0.061 ns` | Failed. |
| `NoTimingRelaxation + Explore` | `-0.043 ns` | Failed and reduced hold margin. |
| `HigherDelayCost + Explore` | `-0.027 ns` | Failed. |
| `AdvancedSkewModeling + Explore` | `-0.099 ns` | Failed. |
| `Explore + AddRetime` | `-0.177 ns` | Failed. |
| `Explore + AggressiveFanoutOpt` | `-0.177 ns` | Failed. |
| `ExtraTimingOpt + MoreGlobalIterations + AggressiveExplore` full impl | `-0.420 ns` | Failed. |

Conclusion: route/physopt directive exploration produced a small improvement from `+0.021 ns` to `+0.040 ns`, but repeated adjacent directives did not approach `+0.100 ns`.

## Transferable Lessons for FullChain v2

1. Do not assume the accelerator arithmetic is the only frequency limiter.

Feature21/QMLP initially looked accelerator-bound, but once QMLP, Feature21, and TSI cuts landed, the final 75 MHz limiter moved to Rocket frontend/core routing. FullChain v2 should expect similar path rotation after local arithmetic cuts.

2. Register protocol boundaries early.

The UART-TSI boundary buffer and internal TL-A staging changed the critical path class. FullChain v2 should aggressively register:

- AXI/TileLink request-generation outputs.
- AXIS width-conversion boundaries.
- DMA descriptor/control-status fanout.
- Any fanout-heavy frame/control fields.

3. Split quantization and writeback.

The best Feature21 improvements came from separating:

- multiply/product,
- round/clamp,
- indexed byte writeback.

FullChain v2 CFAR/FFT/post-processing logic should use the same rule for thresholding, scaling, packing, and dynamic indexed writes.

4. Avoid "DSP pipeline" edits unless the generated primitive actually absorbs the registers.

The failed density DSP pipeline edit added stages but did not solve DSP DRC warnings. Future work should verify generated primitive absorption, not just source-level register insertion.

5. Treat post-route physopt as a finishing tool, not the main design method.

Post-route physopt recovered about `0.9 ns` in the successful 75 MHz flow, but directive changes after the fact only found `+0.019 ns` over the baseline. FullChain v2 should seek structural slack before implementation tuning.

6. Require board validation after timing-oriented FSM edits.

TSI timing changes touched the UART-TSI read FSM. Timing closure alone is not enough; board validation must include:

- UART-TSI load/readback/selfcheck.
- DMA E2E golden comparison.
- Feature/QMLP or FullChain golden output checks.

## Recommended FullChain v2 Optimization Inputs

For a FullChain v2 high-frequency pass, start with this checklist:

| Priority | Action | Expected value |
| --- | --- | --- |
| P0 | Extract top 20 setup paths after current 50 MHz FullChain v2 implementation. | Identify whether limiter is FFT/cache, CFAR, DMA/control, or Rocket/SoC. |
| P0 | Add per-stage timing counters and frame-boundary event counters. | Separate software-visible latency from pure hardware stage latency. |
| P1 | Register control/status fanout and AXIS/TL/AXI boundaries. | Low-risk structural timing relief. |
| P1 | Split compare/threshold/pack/writeback paths in CFAR and output formatting. | Mirrors Feature21 quant/writeback success. |
| P1 | Keep route directive `MoreGlobalIterations` as a known useful candidate. | Useful but not sufficient by itself. |
| P2 | Consider smaller or decoupled Rocket/core config only after accelerator paths are clean. | Current final 75 MHz limiter is Rocket route dominated. |
| P2 | Consider floorplanning only after path classes stabilize. | The final path is route dominated; floorplanning may help but needs stable hierarchy. |

## Evidence Index

Local reports and logs:

- Rolling summary: `docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md`
- Promoted 75 MHz timing: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/report/timing.txt`
- 75 MHz QoR audit: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-06/75mhz-wns-margin-qor-2026-06-06/`
- 75 MHz physopt variants: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/`
- 2026-06-06 physopt variants: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-06/75mhz-wns-margin-physopt-2026-06-06/`

