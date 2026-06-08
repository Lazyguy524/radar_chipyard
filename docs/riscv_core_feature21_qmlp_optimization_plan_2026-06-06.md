# RISC-V Core Optimization Plan for Feature21 + QMLP

Date: 2026-06-06

## Goal

The current project already has meaningful accelerator-side innovation:

- Feature21 preprocessing design.
- QMLP model design.
- QMLP hardware implementation.
- Chipyard/NexysVideo SoC integration and board validation.

The remaining thesis risk is that the SoC/core portion can be read as "using an open-source Rocket core." The next research direction should therefore make the RISC-V core participate in the radar/QMLP workload in a domain-specific way, rather than only improving timing.

This plan recommends a staged path toward a thesis-grade contribution:

> A radar-oriented RISC-V core/ISA co-design study that quantifies where Feature21 + QMLP should couple to the processor: MMIO/CSR, RoCC, or Rocket execute-stage logic.

The primary contribution should be framed as algorithm-aware coupling-point exploration, not as a blanket promise of speedup. The main metrics should be instruction count, software-visible control overhead, code size, resource/timing cost, and bit-exact integration effort. Wall-clock latency remains important, but it should be reported as an outcome of the coupling choice rather than the only claim.

## Local Starting Point

Current relevant local facts:

- `RadarAXIMMIONexysVideoFreqConfig` uses:
  - `WithoutFPU`
  - `WithNSmallCores(1)`
  - AXI4-MMIO radar peripheral window.
  - UART-TSI for bring-up.
- The best 75 MHz candidate is timing-clean at WNS `+0.040 ns`.
- The final 75 MHz limiter is Rocket frontend/icache/fetch-queue/control into execute decode, not QMLP, ordinary Feature21 quant/writeback, or TSI.
- Existing software already has useful measurement hooks:
  - `tests/radar-qmlp-cpu-only.c`
  - `tests/radar-axi-dma-qmlp-validation.c`
  - `tests/radar-axi-dma-feature21-golden.c`
  - cycle counters via `radar_read_cycle64()`.
- Chipyard already has a RoCC path and a prefetcher example config:
  - `generators/rocket-chip/src/main/scala/tile/LazyRoCC.scala`
  - `generators/chipyard/src/main/scala/config/RocketConfigs.scala`
  - `PrefetchingRocketConfig`
- The repository also contains Gemmini-related configs, so any `Xradar` plan must explicitly answer why a tiny radar/QMLP-specific instruction subset is worth studying instead of simply using Gemmini.

## External Design References

These are the most relevant sources for the proposed research direction:

- Chipyard RoCC documentation: https://chipyard.readthedocs.io/en/main/Customization/RoCC-Accelerators.html
  - RoCC attaches to Rocket/BOOM tiles and receives custom instructions routed by opcode sets such as `custom0` and `custom1`.
  - It can access L1 cache, PTW, and TileLink ports depending on design needs.
- Chipyard accelerator overview: https://chipyard.readthedocs.io/en/1.0.0/Customization/Adding-An-Accelerator.html
  - Distinguishes MMIO-attached accelerators from tightly coupled RoCC custom-instruction accelerators.
- Rocket Chip generator report: https://www2.eecs.berkeley.edu/Pubs/TechRpts/2016/EECS-2016-17.html
  - Establishes Rocket Chip as a generator and RoCC as the intended custom-coprocessor interface.
- RISC-V Vector extension v1.0: https://docs.riscv.org/reference/isa/unpriv/v-st-ext.html
  - Useful as a design reference for data-parallel integer multiply-add semantics, but likely too heavy for the current Artix-7/SmallRocket target.
- RISC-V Bitmanip extension: https://docs.riscv.org/reference/isa/unpriv/b-st-ext.html
  - A model for small scalar extensions that reduce code size, cycles, and energy without a full vector unit.
- RISC-V scalar cryptography extension: https://docs.riscv.org/reference/isa/v20240411/unpriv/scalar-crypto.html
  - A good example of domain-specific scalar instructions designed around a 2-read/1-write register-file constraint.
- RISC-V Packed SIMD draft repository: https://github.com/riscv/riscv-p-spec
  - Relevant to 8-bit/16-bit lane packing, but still draft-level; use as inspiration, not as a dependency.
  - `rqdot4` should be described as semantics-inspired by P-extension-style packed dot-product operations, but as a workload-specific subset that does not claim P-extension ISA compliance.
- Stream Semantic Registers paper: https://arxiv.org/abs/1911.08356
  - Shows a lightweight ISA extension that turns memory streams into register accesses to reduce load/store overhead.
- RI5CY user manual: https://pulp-platform.org/docs/ri5cy_user_manual.pdf
  - Useful reference for practical embedded-RISC-V DSP extensions such as hardware loops and post-increment load/store.
- Branch Triggered Instruction Prefetcher: https://www.mdpi.com/2079-9292/13/21/4323
  - Useful for instruction-prefetch ideas, but likely a secondary path for this project.
- Fetch Directed Instruction Prefetching: https://cseweb.ucsd.edu/~calder/abstracts/MICRO-99-FDP.html
  - Classic instruction-prefetch reference; useful background if modifying Rocket frontend.

## Required Baseline Question: Why Not Gemmini?

This must be answered before claiming `Xradar` novelty.

Gemmini is already present in the Chipyard tree and is a RoCC systolic-array accelerator for matrix/tensor workloads. A reviewer can reasonably ask:

> If Gemmini already provides int8 matrix acceleration through RoCC, why build `rqdot4` or a custom QMLP instruction path?

The thesis answer should not be "because we want another accelerator." The defensible answer is:

> Gemmini is the dense-GEMM endpoint in the design space. `Xradar` studies the opposite endpoint: a minimal algorithm-aware RISC-V coupling layer for tiny-batch, low-dimensional, control-heavy radar Feature21/QMLP kernels on a resource- and timing-constrained Artix-7 SmallRocket SoC.

The plan should evaluate Gemmini as a baseline or rejected point in the design space, not ignore it.

Required Phase 0 evidence:

| Question | Evidence to collect |
| --- | --- |
| Resource fit | Compare current Feature21/QMLP SoC resource and timing against a lean Gemmini/Rocket config on the same NexysVideo/Artix-7 target if elaboration/implementation is practical. |
| FPGA budget | Report LeanGemmini LUT/FF/DSP/BRAM use against the Artix-7 budget and against the current SmallRocket + Feature21/QMLP utilization. |
| Timing fit | Check whether a Gemmini-bearing config can close at the relevant frequency and what paths dominate. |
| Workload shape | Show QMLP dimensions, batch size, memory movement, and control overhead; identify whether mapping to dense GEMM underutilizes the systolic array. |
| Systolic utilization | Compare QMLP layer dimensions against Gemmini systolic-array/tile dimensions and estimate PE utilization, padding, and setup/DMA overhead for `batch=1` and the smallest thesis-claimed batch. |
| Software overhead | Compare Gemmini programming/setup path against current MMIO QMLP and proposed minimal custom instructions for small batches. |
| Research fit | Explain whether Gemmini answers the thesis question, or whether it mainly demonstrates a large general-purpose ML accelerator. |

Expected but unproven hypotheses:

- Gemmini may be too large or timing-expensive for the current Artix-7 SmallRocket 75 MHz target.
- Gemmini is optimized for dense matrix operations and batched tensor workloads, while this project has small QMLP layers, Feature21 scalar quantization, variable point-cloud preprocessing, and board-level control overhead.
- For small batches, instruction count/code size/control-path simplification may matter more than peak GEMM throughput.

These are hypotheses until Phase 0 measures them. The plan should not claim Gemmini is unsuitable without local resource/timing/workload evidence.

## Candidate Directions

### A. Radar-QMLP Custom Instruction Extension

Core idea:

Add a small custom instruction set that targets the scalar kernels still visible in the software path:

- signed int8 dot product over packed lanes,
- Q8.8 fixed-point multiply/round/clamp,
- saturating pack,
- possibly Feature21 density/quant helper operations.

Example instruction family:

| Instruction | Function |
| --- | --- |
| `rqdot4 rd, rs1, rs2` | Signed 4-lane int8 dot product from two 32-bit operands into a 32-bit or 64-bit accumulator. |
| `rqmac4 rd, rs1, rs2` | Multiply-accumulate variant for QMLP fallback loops. |
| `rqscale8 rd, rs1, rs2` | Fixed-point scale with round-nearest-even and int8 clamp. |
| `rqpack rd, rs1, rs2` | Pack/clamp multiple quantized feature bytes. |

Why it fits this project:

- QMLP weights and activations are naturally low precision.
- Feature21 already uses quantization, rounding, clamp, and byte packing.
- Existing `radar-qmlp-cpu-only.c` provides a direct baseline.
- This is visibly more than "using Rocket"; it changes the core ISA/microarchitecture around the radar/QMLP workload.
- It is intentionally narrower than Gemmini: the goal is not peak dense GEMM, but to quantify the minimum useful core/ISA coupling for this radar pipeline.

Implementation options:

| Path | Difficulty | Research value | Timing risk |
| --- | --- | --- | --- |
| RoCC prototype | Medium | Medium | Low-medium |
| Rocket execute-stage custom unit | High | High | Medium-high |
| Full compiler backend support | High | Medium-high | Low hardware risk, high tooling time |

Recommended method:

1. Use Phase 0 to prove that the targeted kernels are large enough to justify custom instructions.
2. Prototype as RoCC using a fixed custom opcode map.
3. Validate instruction semantics with inline assembly macros.
4. Measure CPU-only QMLP and Feature21 scalar kernels.
5. If results are good, decide whether to migrate the smallest 1-cycle/2-cycle operations into Rocket execute-stage decode for stronger thesis novelty.

Expected result:

- Report speedup in two layers:
  - kernel-level dot/MAC inner loops may show a large local reduction, for example `3x-8x`, if `rqdot4` replaces several scalar instructions per packed operation,
  - whole CPU-only QMLP speedup must be bounded by the measured accelerated fraction using Amdahl analysis.
- Use `Speedup_total = 1 / ((1 - f) + f / s_k)`, where `f` is the measured CPU-only QMLP cycle share of the accelerated kernel and `s_k` is the measured kernel-local speedup after Phase 2/3 implementation.
- Treat `1 / (1 - f)` only as the unreachable limit where `s_k -> infinity`; do not use it as the realistic expected result.
- Example finite-kernel bounds:
  - `f=40%`, `s_k=4x` gives about `1.43x` whole-QMLP speedup,
  - `f=70%`, `s_k=4x` gives about `2.11x`,
  - `f=87.5%`, `s_k=4x` gives about `2.91x`,
  - even with `f=87.5%`, an `8x` whole-QMLP claim requires much more than a 4-lane dot-product replacement; it approaches the `8x` limit only as `s_k` becomes extremely large.
- If MMIO/polling dominates small accelerator batches, control instructions could reduce instruction count and code size even when wall-clock latency changes only modestly.
- End-to-end DMA accelerator runs may show limited wall-clock improvement for large streaming batches.
- Resource increase can be kept small if the first version uses LUT-based 4-lane int8 arithmetic or a tiny DSP-backed unit.

Risk:

- If the thesis already emphasizes the standalone QMLP accelerator, a RoCC dot-product block can look like "another accelerator" unless framed as an ISA/core extension and evaluated against CPU scalar code.
- If Phase 0 shows the dot-product kernel is a small fraction of CPU-only total cycles, `rqdot4` should not proceed as the first implementation target.
- If Gemmini fits the FPGA and dominates the same workload without excessive setup overhead, `Xradar` must pivot from "faster than Gemmini" to "lower-cost coupling-point analysis."

### B. Accelerator-Aware Custom Control Instructions

Core idea:

Replace MMIO-heavy start/status/wait sequences with custom instructions that expose radar accelerator control through the core ISA:

| Instruction | Function |
| --- | --- |
| `racc.cfg rs1, rs2` | Set accelerator mode, base pointer, batch size, or compact descriptor index. |
| `racc.start rs1` | Start Feature21/QMLP/fullchain operation. |
| `racc.wait rd` | Stall or sleep until accelerator done; return status/cycle count. |
| `racc.stat rd, rs1` | Read compact status/counter without MMIO load sequence. |

Why it fits:

- Current board tests use MMIO register writes, DMA setup, and polling loops.
- Small batches suffer from control overhead.
- A custom wait/start path is easy to explain as core-accelerator co-design.

Implementation options:

- RoCC command path with no memory access for the first prototype.
- A small bridge from RoCC command fields to the existing radar MMIO/control block.
- Optional custom CSRs for mode/status if cleaner than RoCC.

Expected result:

- Small-batch latency reduction must be reported for a named batch definition, starting with `batch=1` and the smallest batch size claimed in the thesis.
- If polling/setup dominates that named batch, control instructions may reduce latency, instruction count, code size, and MMIO transactions; the whole-flow wall-clock claim should still be bounded by the measured setup/polling fraction.
- Large streaming batch throughput: likely little change.
- Energy/instruction-count reduction: likely measurable even when wall-clock throughput is unchanged.

Risk:

- Innovation is weaker than arithmetic custom instructions if it only compresses MMIO access.
- Best used together with Candidate A.

### C. Radar Stream Registers / Address-Generation Extension

Core idea:

Adapt the Stream Semantic Registers idea to radar feature/QMLP loops:

- configure one or more implicit streams for feature bytes, weights, or point arrays,
- replace repeated loads/address updates with register reads that advance stream state,
- optionally add post-increment address-generation support for point-list traversal.

Why it fits:

- Feature21 processes variable point lists.
- QMLP consumes repeated activation/weight streams.
- The SSR paper shows this can be meaningful for single-issue cores by reducing load/store pressure.

Expected result:

- CPU-side Feature21/QMLP fallback benefit must be bounded by the measured memory/address-update fraction; report local load/address-loop reduction separately from whole-kernel speedup.
- Hardware accelerator E2E improvement is uncertain unless software preprocessing remains significant.

Risk:

- Much higher implementation complexity than RoCC custom instructions.
- Requires careful exception/CSR/debug story if implemented architecturally.
- Better as a second-stage research extension after Candidate A demonstrates value.

### D. Instruction Prefetch / Frontend Optimization

Core idea:

Add or adapt an instruction prefetch mechanism for Rocket's frontend, motivated by the current 75 MHz final timing path and possible bare-metal loop behavior.

Options:

- use existing Chipyard prefetcher infrastructure as a baseline,
- add a very small next-line or branch-target prefetcher,
- experiment with fetch queue/BTB sizing and frontend path retiming.

Why it fits:

- Current 75 MHz WNS path is Rocket frontend/core route dominated.
- Instruction prefetch is a RISC-V core microarchitecture topic, not just accelerator RTL.

Expected result:

- Runtime benefit is uncertain because current tests may not be instruction-cache miss dominated.
- Timing benefit is also uncertain; extra frontend logic may worsen the exact path currently limiting 75 MHz.

Risk:

- Weak coupling to Feature21/QMLP unless measurement shows instruction-fetch stalls in radar workloads.
- Treat this as a supporting experiment, not the main thesis contribution.

### E. Existing Standard Extension Evaluation

Core idea:

Evaluate whether standard or near-standard RISC-V ideas map to the workload:

- RVV-style vector multiply-add: algorithmically relevant but probably too large for the current FPGA/SmallRocket target.
- P-style packed SIMD: very relevant for int8/Q8.8, but draft status and tooling uncertainty make it risky.
- Bitmanip: useful for packing/clamping/control code, but probably too small alone.
- Scalar crypto: not directly applicable, but a strong design pattern for compact domain-specific scalar instructions.

Recommended use:

- Do not implement full RVV or P for this project.
- Borrow semantics and evaluation style.
- Define a narrower `Xradar` custom extension around the measured kernels.

## Recommended Thesis-Grade Direction

The strongest path is:

> Xradar: a lightweight RISC-V custom extension and coupling-point design-space study for radar Feature21/QMLP workloads, evaluated against MMIO/CSR control, RoCC, execute-stage custom logic, and Gemmini-style dense-GEMM acceleration where practical.

This gives a coherent story:

1. Algorithm: Feature21 + QMLP are specialized for radar point-cloud/classification.
2. Accelerator: QMLP/Feature21 hardware handles high-throughput streaming.
3. Core extension: Xradar quantifies whether scalar/control overhead is best handled through MMIO/CSR, RoCC, or execute-stage custom logic.
4. SoC: Chipyard/NexysVideo integration validates the whole system on FPGA.

This is more defensible than "we used Rocket" because the core is no longer untouched infrastructure. It becomes part of the radar compute stack.

## Proposed Research Questions

1. Which parts of Feature21/QMLP remain software-visible after hardware acceleration?
2. Can a small custom ISA extension reduce those costs without implementing a full vector core?
3. What is the best coupling point for radar custom instructions: RoCC, Rocket execute stage, or MMIO/CSR?
4. Does Xradar improve only CPU fallback, or also end-to-end board-level accelerator workflows?
5. What is the resource/timing cost of the extension at 60 MHz and 75 MHz on Artix-7?
6. When compared with Gemmini, what is lost in peak dense-GEMM throughput and what is gained in area, timing closure, code size, and small-batch/control efficiency?

## Implementation Plan

### Phase 0: Baseline Gate and Design-Space Triage

Tasks:

- Build a baseline matrix:
  - scalar CPU QMLP,
  - scalar CPU Feature21 where available,
  - current MMIO/DMA QMLP,
  - current Feature21 + QMLP chain,
  - Gemmini feasibility/configuration evidence if practical,
  - 60 MHz and 75 MHz timing candidates.
- Add or enable counters:
  - total cycles,
  - per-kernel cycles for dot-product, activation/lookup, quantization, memory loads, control/setup, and polling,
  - percentage share of each measured sink in CPU-only and accelerator-assisted totals,
  - Phase 0 accelerated fraction `f` for each candidate kernel,
  - preliminary Amdahl sensitivity table across plausible finite `s_k` values such as `2x`, `4x`, `6x`, and `8x`,
  - instruction count if available,
  - MMIO writes/reads in software wrappers,
  - polling-loop iterations,
  - QMLP hardware cycles,
  - Feature21 hardware cycles,
  - I-cache miss/proxy counters if Rocket events are accessible.

Deliverable:

- `docs/performance/radar_core_extension_baseline_YYYY-MM-DD.md`

Exit criteria:

- Identify top two software-visible cycle sinks.
- Gate A: proceed with `rqdot4` only if instruction-level or function-level profiling shows packed dot-product/MAC work is at least `40%` of CPU-only QMLP total cycles, or if a lower threshold is justified by code-size/instruction-count goals. Record the exact measured fraction `f` as the first input to the thesis Amdahl analysis; final whole-QMLP claims must wait for measured kernel-local speedup `s_k` from Phase 2/3.
- Gate A fallback: if dot/MAC is below threshold, do not implement `rqdot4` first; pivot to the measured bottleneck or keep `rqdot4` only as a small semantic comparison against P-extension-style packed dot products.
- Gate B: proceed with `racc.*` control instructions only if MMIO/setup/polling overhead is at least `20%` of accelerator E2E cycles for a named small batch, initially `batch=1` and the smallest batch size that the thesis will claim, or if instruction-count/code-size reduction is the primary thesis metric.
- Gate B fallback: if control overhead is below threshold for the named small batch, keep MMIO/CSR as the baseline coupling point and focus the thesis on arithmetic, quantization, or design-space comparison.
- Gate C: if activation/lookup/control flow dominates instead of dot-product, pivot the first custom arithmetic instruction toward the measured bottleneck, such as quantize/round/clamp or table/index helpers.
- Gate C fallback: if no software-visible kernel is large enough, stop custom-instruction implementation and write the result as a negative design-space finding that the existing accelerator boundary is already appropriate.
- Gate D: document Gemmini as one of three outcomes:
  - infeasible on the target due to resource/timing,
  - feasible but mismatched for small-batch/control-heavy QMLP,
  - feasible and competitive, in which case `Xradar` must be reframed as a lower-cost coupling-point study rather than a faster accelerator.
- Decide whether arithmetic custom instructions, control instructions, stream/address-generation instructions, or no custom extension should be first.

### Phase 1: Xradar ISA Sketch

Tasks:

- Define instruction encodings using RISC-V custom opcode space.
- Start with 3-5 instructions, not a large extension.
- Define C inline macros and pure-software fallback.
- Define precise arithmetic:
  - signedness,
  - lane width,
  - accumulator width,
  - accumulator overflow behavior,
  - rounding mode,
  - saturation/clamp behavior.
- Freeze the opcode/funct partition before RTL work.

Proposed opcode partition:

| Opcode set | Purpose | Initial users |
| --- | --- | --- |
| `custom0` | `rq*` arithmetic/data instructions | `rqdot4`, `rqmac4`, `rqscale8`, `rqpack` |
| `custom1` | `racc.*` accelerator-control instructions | `racc.cfg`, `racc.start`, `racc.wait`, `racc.stat` |
| `custom2` | reserved for stream/address-generation experiments | future SSR/post-increment style work |
| `custom3` | reserved for debug/profiling or not used | future profiling hooks |

Draft `custom0` arithmetic function map:

| Instruction | Opcode | `funct7` | `funct3` | Notes |
| --- | --- | ---: | ---: | --- |
| `rqdot4` | `custom0` | `0x00` | `0x0` | Signed 4-lane int8 dot product. |
| `rqmac4` | `custom0` | `0x01` | `0x0` | MAC form if accumulator convention is practical. |
| `rqscale8` | `custom0` | `0x02` | `0x0` | Q8.8 multiply, round-nearest-even, clamp. |
| `rqpack` | `custom0` | `0x03` | `0x0` | Pack/clamp feature bytes. |
| reserved | `custom0` | `0x04`-`0x0f` | `0x0` | Reserved for execute-stage migration variants, future `rqmac4` convention changes, or measured bottleneck helpers. |

Draft `custom1` control function map:

| Instruction | Opcode | `funct7` | `funct3` | Notes |
| --- | --- | ---: | ---: | --- |
| `racc.cfg` | `custom1` | `0x00` | `0x0` | Configure mode/descriptor index. |
| `racc.start` | `custom1` | `0x01` | `0x0` | Start selected accelerator operation. |
| `racc.wait` | `custom1` | `0x02` | `0x0` | Wait/read done status. |
| `racc.stat` | `custom1` | `0x03` | `0x0` | Read compact status/counter. |
| reserved | `custom1` | `0x04`-`0x0f` | `0x0` | Reserved for descriptor, counter, or low-power wait variants. |

The exact bit encodings can change after checking assembler macro constraints, but arithmetic and control instructions should not share the same opcode set unless there is a clear reason.

Candidate minimal set:

| Instruction | First implementation |
| --- | --- |
| `rqdot4` | RoCC, 1 command returns dot result |
| `rqscale8` | RoCC or execute-stage helper |
| `rqpack` | RoCC or execute-stage helper |
| `racc.start` | RoCC bridge to current accelerator control |
| `racc.wait` | RoCC wait/status return |

Deliverable:

- `docs/riscv_xradar_isa_spec_YYYY-MM-DD.md`

Exit criteria:

- Instruction semantics can reproduce QMLP/Feature21 scalar outputs bit-exactly.
- The pure-software fallback is the golden reference for every `Xradar` instruction.
- The golden semantics must define accumulator width and overflow behavior for every packed int8 dot/MAC instruction, not only final rounding and clamp.
- `rqscale8` must match existing Feature21 Q8.8 quantization exactly, including round-nearest-even and clamp behavior.
- Before any RoCC RTL is written, run the pure-software fallback over the existing golden subset, preferably the 1000-sample Feature21/QMLP validation data, to prove that ISA-level semantics match the current software/hardware contract.
- The ISA spec must include an explicit note that `rqdot4` is a semantics-inspired, workload-specific packed-dot-product subset related to P-extension-style packed SIMD/dot-product operations, while intentionally avoiding full P-extension tooling and not claiming P-extension ISA compliance.

### Phase 2: RoCC Prototype

Tasks:

- Add `WithXradarRoCC` config fragment.
- Instantiate one or two small `LazyRoCC` units using the frozen opcode partition:
  - arithmetic path on `OpcodeSet.custom0`,
  - optional control path on `OpcodeSet.custom1`.
- Implement arithmetic commands first with no memory access.
- Add software macros and tests.

Why RoCC first:

- It is the quickest path in Chipyard.
- It avoids immediately perturbing Rocket's already-tight frontend/execute timing path.
- It creates custom-instruction evidence early.

Deliverables:

- `generators` or `fpga/src/main/scala` Xradar RoCC source.
- `tests/radar-xradar-isa.c`
- FIRRTL/verilog check.
- RTL sim or board smoke test.

Exit criteria:

- RoCC custom instructions execute correctly.
- CPU-only QMLP/Feature21 kernels can call the new instructions.

### Phase 3: Workload Integration

Tasks:

- Modify CPU-only QMLP to use `rqdot4` and `rqscale8`.
- Modify Feature21 software/golden path where quantization/packing is scalar.
- Add control-instruction path for accelerator start/wait if Phase 0 shows MMIO/poll overhead matters.

Measurements:

- kernel-local speedup `s_k` for each replaced dot/MAC, quantization, or packing loop,
- cycles per QMLP inference,
- cycles per Feature21 sample,
- board E2E cycles for small/medium/large batches,
- instruction count reduction if available,
- code size change,
- MMIO read/write count reduction,
- estimated or measured energy proxy such as cycles times toggling/resource class if real power measurement is unavailable,
- timing/resource impact.
- whole-workload Amdahl prediction using Phase 0 `f` and measured Phase 2/3 `s_k`, compared against actual measured whole-workload speedup.

Expected outcome:

- Strongest likely win: CPU-only QMLP and scalar Feature21 helper paths.
- Moderate win: small-batch accelerator workflows.
- Limited win: large streaming accelerator throughput.
- The main thesis result should be the quantified tradeoff among coupling points, not a hard promise that every path is faster.

### Phase 4: Optional Execute-Stage Custom Unit

Only do this if RoCC results justify it.

Tasks:

- Add a small Rocket decode path for one or two arithmetic instructions.
- Keep it compatible with the 2-read/1-write register constraint.
- Prefer one-cycle or short multi-cycle operations.
- Avoid touching frontend unless profiling proves frontend changes matter.

Candidate migration:

- `rqdot4` as a short-latency custom execution unit.
- `rqscale8` if fixed-point rounding/clamp can meet timing.

Why this matters:

- A RoCC prototype can be criticized as an accelerator.
- A Rocket execute-stage extension is a stronger "core optimization" contribution.

Risk:

- Current 75 MHz margin is only `+0.040 ns`.
- Any execute-stage change must be checked at 60 MHz first, then 75 MHz.

### Phase 5: Thesis Evaluation

Compare four systems:

| System | Purpose |
| --- | --- |
| Baseline Rocket + MMIO accelerator | Current open-core baseline. |
| Rocket + Gemmini baseline or feasibility report | Dense-GEMM reference point already present in Chipyard. |
| Rocket + Xradar RoCC arithmetic | Fast custom-instruction prototype. |
| Rocket + Xradar control instructions | Accelerator-aware control path. |
| Rocket + execute-stage Xradar subset | Strongest core-level novelty, if feasible. |

Metrics:

- functional correctness against golden references,
- CPU-only cycles,
- accelerator E2E cycles,
- instruction count/code size,
- MMIO transaction count,
- small-batch vs large-batch behavior,
- LUT/FF/BRAM/DSP resource delta,
- 60 MHz and 75 MHz WNS/WHS,
- board validation pass/fail,
- implementation complexity.

## Decision Matrix

| Direction | Novelty | Fit to Feature21/QMLP | Implementation difficulty | Timing risk | Recommended priority |
| --- | ---: | ---: | ---: | ---: | --- |
| Xradar arithmetic custom instructions | High | High | Medium | Medium | P0 |
| Xradar accelerator control instructions | Medium | High | Medium | Low-medium | P0/P1 |
| RoCC prototype | Medium | High | Medium | Low-medium | P0 |
| Execute-stage custom unit | High | High | High | Medium-high | P1 after RoCC |
| Gemmini baseline | Medium as comparison, low as new contribution | Medium if QMLP is GEMM-shaped, lower for Feature21/control | Medium-high | High on Artix-7 | Required baseline/foil |
| Stream/address-generation extension | High | Medium-high | High | Medium | P2 |
| Instruction prefetch/frontend changes | Medium | Low-medium until profiled | Medium-high | High | P2 |
| Full RVV/P extension | Medium-high | High | Very high | Very high | Not recommended |

## Recommended Near-Term Work

1. Keep the current 75 MHz timing candidate archived; do not chase `+0.100 ns` by more directive-only runs for now.
2. Treat Phase 0 as a go/no-go gate, not a routine profiling step.
3. Include Gemmini in the baseline discussion before claiming `Xradar` novelty, including QMLP-layer utilization against Gemmini array/tile dimensions and LeanGemmini resource/timing evidence if practical.
4. Define `Xradar` only after the measured bottleneck justifies the first instruction pair.
5. Report expected benefit in layers: Phase 0 measures accelerated fraction `f`, Phase 2/3 measures kernel-local speedup `s_k`, and whole-workload claims use the finite-speedup Amdahl equation.
6. Freeze custom0/custom1 opcode partition before RTL work.
7. Use pure-software fallback as golden and prove bit-exact Feature21/QMLP semantics on existing validation data.
8. Define accumulator width and overflow behavior in the golden semantics before RTL.
9. Prototype through RoCC first only if Phase 0 gates pass.
10. Only then decide whether to modify Rocket execute stage.

## Thesis Framing

Possible thesis contribution statement:

> This work proposes a radar-oriented RISC-V core/ISA and accelerator co-design methodology for Feature21 + QMLP inference. Beyond integrating an open-source Rocket core, the design evaluates where the radar workload should couple to the processor: MMIO/CSR, RoCC, execute-stage custom logic, or an existing dense-GEMM accelerator such as Gemmini. The proposed Xradar extension is a minimal workload-specific custom-instruction set for quantized radar feature and QMLP kernels. The evaluation emphasizes instruction count, code size, control overhead, resource/timing cost, bit-exactness, and board-level latency.

This framing gives you three connected innovation layers:

1. Feature21/QMLP algorithm and quantization.
2. Dedicated hardware accelerator.
3. RISC-V core/ISA coupling-point analysis and adaptation to the same workload.

That third layer is the one most likely to lift the thesis above a "used open-source SoC" critique.
