# Radar RTL Implementation Logic Review

Date: 2026-06-08

Scope: readable implementation review for the current Scala/Chisel-generated RTL path around Feature21, QMLP, DMA/MMIO, UART-TSI, and the proposed RISC-V/Xradar optimization direction. This is not a new hardware change; it is a source-and-report based understanding document plus a board-test coverage checklist.

## Current Conclusion

The current RTL is not an opaque generated blob from a logic perspective. The important accelerator and bring-up paths are written in Chisel with explicit state machines, Decoupled ready/valid handshakes, counters, and timing-oriented pipeline registers.

What can be confirmed offline:

- QMLP, Feature21, the AXI4-to-AXI4-Lite/MMIO bridge, and UART-TSI-to-TileLink all have visible FSMs.
- The latest timing-closure work added real pipeline cuts in QMLP, Feature21, and UART-TSI.
- The promoted 75 MHz implementation is timing-clean at WNS `+0.040 ns`, TNS `0.000 ns`, WHS `+0.017 ns`.
- The remaining 75 MHz worst path is Rocket frontend/icache/fetch-queue/control into execute decode, not the ordinary QMLP, Feature21, or UART-TSI TL-A path.

What cannot be fully claimed from source alone:

- Dynamic correctness under all backpressure patterns.
- UART-TSI read/write selfcheck after the timing-oriented FSM staging.
- Full Feature21 raw-point-to-QMLP hardware chain coverage.
- MMIO setup versus polling versus DMA transfer cycle split.
- `racc.*` usefulness or any custom-instruction wall-clock speedup.

## QMLP RTL Logic

Source: `fpga/src/main/scala/nexysvideo/RadarQMLP.scala`

Main module: `RadarAXISQMLP`

The QMLP block is an AXI-Stream style accelerator wrapped in Chisel `Decoupled` interfaces:

- input: `Flipped(Decoupled(new RadarAXISWord))`
- output: `Decoupled(new RadarAXISWord)`
- control: `ctrlEnable`, `clearCounters`
- observability: `inBeats`, `outBeats`, `frameCount`, `lastKeep`, `runCycles`, `lastLogit0`, `lastLogit1`, `status`, `capabilities`

Handshake behavior:

- `io.in.ready := (state === sIdle || state === sRecv) && io.ctrlEnable`
- `io.out.valid := outValidReg`
- input capture is driven by `io.in.fire`
- output retirement is driven by `io.out.fire`

State sequence:

| Phase | States | Function |
| --- | --- | --- |
| Receive | `sIdle`, `sRecv` | Capture up to 4 input AXIS beats into internal word banks; respect `keep` and `last`. |
| Layer 1 | `sL1Load`, `sL1Prep`, `sL1Mac`, `sL1QuantMul`, `sL1QuantRound`, `sL1Write` | Bias load, 4-lane packed MAC steps over 21 inputs, fixed-point requant, round-nearest-even, ReLU/clamp, activation writeback. |
| Layer 2 | `sL2Load`, `sL2Prep`, `sL2Mac`, `sL2QuantMul`, `sL2QuantRound`, `sL2Write` | Same pattern over 64 inputs and 32 outputs. |
| Layer 3 | `sL3Load`, `sL3Prep`, `sL3Mac`, `sL3Write`, `sL3Pack` | Compute two int32 logits without hidden-layer clamp, then pack both logits into one 64-bit output word. |
| Emit | `sEmit` | Hold output valid until downstream consumes it. |

Timing-oriented registers visible in source:

| Register | Role |
| --- | --- |
| `biasStageReg` | Separates bias ROM read from MAC initialization. |
| `macDataRegs`, `macWeightRegs` | Registers 4-lane activation and weight inputs before the multiply tree. |
| `quantProductReg` | Splits fixed-point multiplier or shift-add product from rounding. |
| `quantRoundedReg` | Splits rounding from activation writeback. |
| `outValidReg`, `outBitsReg` | Decouples output packet generation from downstream ready. |

Current interpretation:

- The QMLP implementation already considers pipeline staging and ready/valid behavior.
- It is single-sample sequential over output neurons, with a 4-lane int8 PE grouping inside each dot product.
- The current timing closure shows QMLP is not the leading 75 MHz limiter.
- It still needs dynamic tests for output backpressure, partial `keep`, short-frame behavior, and repeated clear/enable transitions.

## Feature21 RTL Logic

Source: `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`

Main module: `RadarAXISFeature21Preprocessor`

The Feature21 preprocessor is also a `Decoupled` AXIS-style block:

- input: raw point beats
- output: 4 beats of packed feature bytes
- control: `ctrlEnable`, `clearCounters`
- observability: `inBeats`, `outBeats`, `frameCount`, `lastKeep`, `status`, `capabilities`

Handshake behavior:

- `io.in.ready := io.ctrlEnable && (state === sIdle || state === sAccum)`
- `io.out.valid := outValidReg`
- point accumulation only advances on `io.in.fire`
- output emission only advances on `io.out.fire`

State sequence:

| Phase | States | Function |
| --- | --- | --- |
| Accumulation | `sIdle`, `sAccum` | Read expected point count, clamp to 511, accumulate sums/min/max/range-like approximations until count or `last`. |
| Mean | `sMeanX`, `sMeanY`, `sMeanDoppler`, `sMeanRcs` | Compute shift-based approximate means. |
| Density | `sDensityArea`, `sDensityNormalize`, `sDensityMul`, `sDensityShift`, `sDensityQuantMul`, `sDensityQuantRound` | Compute span area, LUT reciprocal normalization, density feature, and quantization. |
| Feature quant | `sFeatureSelect`, `sFeatureQuantMul`, `sFeatureQuantRound`, `sFeatureWrite` | Select 21 features, split mux/multiply/round/writeback across cycles. |
| Emit | `sEmit` | Emit 4 packed 64-bit feature words. |

Timing-oriented registers visible in source:

| Register | Role |
| --- | --- |
| `densityQuantProductReg`, `densityFeatureReg` | Splits density quantization and feature-byte use. |
| `featureQ8p8Reg`, `featureDensityReg` | Splits feature selection from quantization. |
| `featureQuantProductReg` | Splits feature multiply from rounding/clamp. |
| `featureByteReg` | Splits rounded byte from `featureByteRegs` writeback. |
| `outValidReg`, `outBitsReg` | Holds output under downstream backpressure. |

Current interpretation:

- Feature21 has an explicit FSM and timing-aware stage separation.
- The current ordinary Feature21 quant/writeback path is not the leading 75 MHz limiter.
- Feature21 density-tail logic can still reappear as a secondary near-top path in some poor routing variants, so it remains a watch item.

## DMA, MMIO, And Local CSR Logic

Source: `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`

Main modules:

- `RadarAXI4ToAXI4LiteBridge`
- `RadarAXIDMA`
- Xilinx `radar_axi_dma` blackbox
- local CSR steering for preproc/QMLP control and status

The AXI bridge has an explicit FSM:

| State | Function |
| --- | --- |
| `sIdle` | Accept a read or begin collecting write address/data. |
| `sWriteCollect` | Allow AW and W channels to arrive independently. |
| `sWriteIssue` | Forward legal 32-bit aligned writes to Xilinx AXI4-Lite or local CSR space; reject unsupported transfers with SLVERR. |
| `sWriteResp` | Return AXI B response. |
| `sReadIssue` | Forward legal reads to Xilinx AXI4-Lite or local CSR space; reject unsupported transfers with SLVERR. |
| `sReadResp` | Return AXI R response. |

Local CSR map highlights:

| Address | Meaning |
| --- | --- |
| `0x00` | preproc control; bit 0 enable, bit 1 clear counters pulse. |
| `0x04` | preproc mode; includes `feature21` mode. |
| `0x08`, `0x0c` | preproc parameters. |
| `0x10` to `0x24` | preproc or Feature21 status/counters/capabilities. |
| `0x40` | QMLP control; bit 0 direct QMLP enable, bit 1 clear counters pulse, bit 2 route DMA stream through preproc before QMLP. |
| `0x44` to `0x64` | QMLP status, counters, logits, run cycles, capabilities. |
| `0x68`, `0x6c` | local constants: feature/QMLP geometry indicators. |

Debug/coverage flags exist for DMA stream activity:

- MM2S AR/R valid/ready/fire
- MM2S stream beats and TLAST
- S2MM write beats and WLAST
- Xilinx DMA packet EOF and IOC bits

Current interpretation:

- The current design is primarily an MMIO-controlled DMA/AXIS accelerator path.
- It exposes useful status/counter state, but current software still needs board profiling to split setup, polling, and transfer/compute costs accurately.

## UART-TSI / TileLink Bring-Up Logic

Sources:

- `generators/testchipip/src/main/scala/tsi/PeripheryUARTTSI.scala`
- `generators/testchipip/src/main/scala/tsi/TSIToTileLink.scala`

Functional role:

- UART-TSI is the board bring-up/test/debug memory-transaction path.
- It loads code/data and can do readback/selfcheck through TileLink.
- It is not the QMLP compute datapath, but it shares the SoC/fbus timing environment and previously dominated high-frequency timing failures.

Current structure:

- `PeripheryUARTTSI.scala` couples `TSIToTileLink` to the selected TL bus through `TLBuffer(BufferParams.pipe)`.
- `TSIToTileLink.scala` converts serial TSI commands into TileLink `Get`/`Put` requests.
- The read path now has staged states: `s_read_measure`, `s_read_size`, `s_read_prepare`, `s_read_req`.
- TileLink A-channel bits are held in `aBitsReg`, with request validity held in `aValidReg`.

Current interpretation:

- The timing-oriented TSI changes are structurally real.
- Because these edits changed the read/write FSM path used by board load/readback, timing closure alone is not sufficient; UART-TSI selfcheck remains a required board coverage item.

## Untested Or Under-Tested Cases To Cover Later

The following table is intended as a board-test and simulation coverage checklist.

| Area | Case | Why It Matters | Suggested Evidence |
| --- | --- | --- | --- |
| UART-TSI | Program load through UART-TSI at 75 MHz | Confirms staged TSI FSM still supports normal bring-up. | `scripts/run_nexysvideo_uart_tsi.sh` can load a small hello/selfcheck binary. |
| UART-TSI | `+selfcheck` readback after load | Specifically covers TSI read path staging. | Runner log showing readback/selfcheck pass. |
| UART-TSI | Mixed small/unaligned reads and writes if runner supports them | TSI size/mask logic was historically timing-hot and now staged. | Dedicated host/TSI smoke test or existing selfcheck with readback details. |
| QMLP AXIS | Normal 4-beat input frame with `last` on beat 4 | Main expected QMLP input shape. | `radar-axi-dma-qmlp-validation.riscv` pass. |
| QMLP AXIS | Early `last` before 4 beats | Source transitions allow `last` to trigger compute early; need behavior confirmation. | Directed simulation or board microtest. |
| QMLP AXIS | Partial `keep` on the final beat | `mergeAxisWord` respects byte `keep`; must verify stale byte behavior is intentional. | Directed simulation with known logits. |
| QMLP AXIS | Output backpressure | `outValidReg` should hold logits until `io.out.fire`. | Chisel/cocotb-style Decoupled stall test or ILA. |
| QMLP control | Disable/re-enable while idle and while receiving | Confirms control register semantics and no stale input reuse. | Board microtest plus status/counter reads. |
| QMLP counters | Clear counters pulse during idle and after run | Software depends on `inBeats`, `outBeats`, `frameCount`, `runCycles`. | MMIO readback before/after clear. |
| Feature21 | `expectedPoints=0` | Source intentionally goes directly to mean/feature generation. | Golden check for all-zero or defined output. |
| Feature21 | `expectedPoints=1` | Exercises first-point min/max/range handling. | Directed board/sim golden. |
| Feature21 | Small counts around powers of two: 2, 3, 4, 7, 8, 9 | Exercises shift-based mean approximation boundaries. | Feature21 golden subset comparison. |
| Feature21 | Count clamp above 511 | Source clamps expected count to 511. | Directed microtest with overlarge count. |
| Feature21 | Early `last` before expected count | Source exits accumulation on `last`; must verify intended partial-frame behavior. | Directed microtest. |
| Feature21 | Downstream output backpressure | `sEmit` should hold output until consumed. | Decoupled stall simulation or ILA. |
| Feature21 | Density area zero | Source maps zero area with nonzero points to density 127. | Golden directed case. |
| DMA/MMIO | Legal 32-bit aligned writes and reads to Xilinx DMA regs | Confirms bridge forwarding path. | Existing DMA validation pass plus status reads. |
| DMA/MMIO | Local CSR reads/writes at `0x00` to `0x6c` | Confirms local steering map and strobes. | Small MMIO register test. |
| DMA/MMIO | Unsupported burst/size/unaligned access returns SLVERR | Bridge has explicit rejection logic. | Simulation preferred; board software may not expose response cleanly. |
| DMA/MMIO | AW before W, W before AW, and same-cycle AW/W | Bridge captures AW/W independently. | AXI-level simulation. |
| DMA stream | MM2S/S2MM TLAST/WLAST and IOC flags | Debug flags exist but need runtime evidence. | Board log or ILA from QMLP DMA profile. |
| Full chain | Feature21 raw points into QMLP logits | Avoid confusing Feature21 dump plus software QMLP with hardware full chain. | A dedicated full-chain hardware validation run. |
| Performance | CPU-only QMLP cycle-share profile | Required before claiming `rqdot4` whole-workload speedup. | Run `radar-qmlp-cpu-profile.riscv` on board. |
| Performance | QMLP MMIO/DMA polling split | Required before judging `racc.*`. | Run `radar-axi-dma-qmlp-mmio-profile.riscv` on board. |
| Gemmini | LeanGemmini timing/utilization on same target | Required before claiming Gemmini unsuitable or competitive. | Recover or generate timing/utilization reports. |

Queued board commands when UART is available:

```bash
scripts/run_nexysvideo_uart_tsi.sh \
  --bin tests/radar-qmlp-cpu-profile.riscv \
  --log-name phase0-radar-qmlp-cpu-profile-2026-06-07

scripts/run_nexysvideo_uart_tsi.sh \
  --bin tests/radar-axi-dma-qmlp-mmio-profile.riscv \
  --log-name phase0-qmlp-mmio-profile-2026-06-07
```

## RISC-V Optimization Direction: What We Have Been Doing

The prior RISC-V work is currently a design-space and offline-golden effort, not a committed hardware RTL implementation yet.

There are two separate directions:

| Direction | Current Status | Coupling Style | What It Optimizes |
| --- | --- | --- | --- |
| `rq*` arithmetic custom instructions | Active software/ISA draft and host golden. No RoCC or execute-stage RTL yet. | RISC-V custom ISA, likely first via RoCC, possibly later execute-stage logic. | CPU-only QMLP arithmetic instruction count, dot/MAC work, fixed-point scale/round/clamp. |
| `racc.*` accelerator-control instructions | Reserved. MMIO/polling profile wrapper exists, but board data missing. | Custom instruction or CSR/RoCC bridge to existing accelerator control. | MMIO writes/reads, DMA setup, polling loops, small-batch control overhead. |

The existing hardware accelerator path in the design is MMIO + DMA + AXIS:

- software configures DMA and local QMLP/Feature21 CSRs via MMIO,
- Xilinx AXI DMA moves input/output streams,
- Feature21 and QMLP consume/produce AXIS-style streams,
- status/counters are read back via local CSR addresses.

The proposed `Xradar` path is not meant to replace that immediately. It asks which coupling point is thesis-worthy:

1. Keep the existing MMIO + DMA accelerator and only improve measurement/reporting.
2. Add `rqdot4` / `rqscale8` as custom arithmetic instructions for the CPU fallback path.
3. Add `racc.*` control instructions only if small-batch MMIO/polling overhead is proven meaningful.
4. Compare against Gemmini as a dense-GEMM design-space endpoint, without overclaiming until timing/utilization evidence exists.

## Custom Instruction vs MMIO + DMA Accelerator

| Question | Custom arithmetic instructions: `rqdot4`, `rqscale8` | MMIO + DMA accelerator: current QMLP/Feature21 path | Accelerator-control instructions: `racc.*` |
| --- | --- | --- | --- |
| Best workload shape | Small kernels, CPU fallback, low batch, tight loops. | Streaming batches, offloaded Feature21/QMLP pipeline, data movement large enough to amortize setup. | Small-batch accelerator calls where setup/polling dominates. |
| Main benefit | Fewer scalar instructions and smaller loop body; possible cycle reduction. | High compute offload and reuse of existing validated hardware. | Fewer MMIO transactions, less polling/control overhead, cleaner software path. |
| Main risk | Whole-workload speedup limited by measured dot/MAC cycle share; execute-stage timing may be risky. | Control overhead can dominate tiny batches; DMA transfer/compute overlap is hard to split from software only. | Innovation is weaker if it only compresses MMIO; usefulness unproven without profiling. |
| Evidence already available | Static QMLP packed MAC coverage is `98.14%`; host fallback passes current 8-case golden. | Historical DMA QMLP profile exists; large-batch hardware cycles are near kernel limit. | A dedicated MMIO/polling profile binary now builds. |
| Evidence still missing | Board CPU cycle share and hardware custom-instruction implementation speedup. | Full fresh board validation at the promoted timing point and full-chain hardware coverage. | Board run splitting `qctrl`, DMA setup, DMA polling, MMIO reads/writes. |
| Thesis framing | Minimal radar/QMLP ISA/core specialization. | Domain accelerator integration and timing closure. | Core-accelerator control coupling for small batches. |

Recommended current stance:

- Treat `rqdot4` and `rqscale8` as the first active RISC-V optimization candidates because their semantics are already frozen in software and the static operation coverage is strong.
- Treat `racc.*` as not yet passed through implementation gate. It should wait for MMIO/setup/polling instrumentation from the board.
- Treat the current Feature21/QMLP hardware as the existing MMIO + DMA accelerator baseline.
- Avoid claiming wall-clock speedup for either custom instructions or `racc.*` until board data exists.

## Next Work Assessment

Priority 1: close dynamic coverage gaps when board access returns.

- UART-TSI load/readback/selfcheck at 75 MHz.
- QMLP CPU profile to get dot/MAC, quant, and residual cycle share.
- QMLP MMIO/DMA profile to split setup and polling.
- Feature21/QMLP full hardware chain validation rather than mixed hardware/software chain evidence.

Priority 2: add offline simulation coverage if board remains unavailable.

- AXIS backpressure tests for QMLP and Feature21.
- Directed short-frame/partial-keep tests.
- AXI bridge tests for AW/W ordering and SLVERR paths.

Priority 3: only then choose implementation route.

- If CPU dot/MAC share is large enough, prototype `rqdot4`/`rqscale8` through RoCC first.
- If board MMIO/polling dominates named small batches, revisit `racc.*`.
- If Gemmini reports become available and fit/timing look strong, reframe `Xradar` as lower-cost coupling-point analysis rather than a faster-than-Gemmini claim.

