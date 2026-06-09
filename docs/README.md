# Radar Docs Functional Map

Date: 2026-06-08

Purpose: give the current messy `docs/` tree a functional navigation layer without moving files or breaking old references. Use this file as the first stop before writing weekly reports, thesis notes, or the next implementation handoff.

## Quick Answer

The current `docs/` content should be read in three layers:

1. Official Chipyard docs: background reference, mostly `.rst`, not project progress.
2. Active radar project docs: current evidence, timing, RTL, RISC-V/Xradar, validation, and weekly-report material.
3. Archive/backups/generated evidence: useful for traceability, not the first place to read.

For weekly reports, start from:

- [2026-06-08 75 MHz board evidence](#2026-06-08-75-mhz-board-evidence)
- [2026-06-08 Feature21 batch DMA candidate](#2026-06-08-feature21-batch-dma-candidate)
- [weekly_report_2026-06-07_phase0_xradar_obsidian.md](/home/soooarr/chipyard/docs/weekly_report_2026-06-07_phase0_xradar_obsidian.md)
- [radar_rtl_implementation_logic_review_2026-06-08.md](/home/soooarr/chipyard/docs/radar_rtl_implementation_logic_review_2026-06-08.md)
- [performance/radar_core_extension_baseline_2026-06-06.md](/home/soooarr/chipyard/docs/performance/radar_core_extension_baseline_2026-06-06.md)
- [performance/xradar_offline_static_analysis_2026-06-07.md](/home/soooarr/chipyard/docs/performance/xradar_offline_static_analysis_2026-06-07.md)
- [feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md](/home/soooarr/chipyard/docs/feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md)

## 2026-06-08 75 MHz Board Evidence

Use this section for the latest board-run material behind weekly reports and Phase 0 RISC-V/Xradar decisions.

Board setup:

- Bitstream/config line: current 75 MHz Feature21/QMLP NexysVideo flow.
- Runtime UART-TSI: `/dev/ttyUSB0`, stable link `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A6003YUV-if00-port0`.
- Baudrate: `115200`; earlier `921600` attempts opened the TTY but hung during selfcheck.
- Manual step: press board `CPU_RESET` before each fresh ELF run.

Main logs and reports:

| Evidence | Status | Source |
| --- | --- | --- |
| CPU-only QMLP profile | PASS after fixed share printing; `infer_avg=168349`, `dot_mac_upper=93.43%`, `quant_relu=5.66%`, `control_resid=0.90%`. | [phase0-radar-qmlp-cpu-profile-75mhz-2026-06-08-115200-reset10-fixed-share-2026-06-08-204324.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/phase0-radar-qmlp-cpu-profile-75mhz-2026-06-08-115200-reset10-fixed-share-2026-06-08-204324.log) |
| QMLP MMIO/DMA polling profile | PASS; batch=1 shows `qctrl_avg=44`, `dma_setup_avg=347`, `dma_poll_avg=2351`, `hw_avg=2213`, `ctrl_poll_avg=2743`. | [phase0-radar-axi-dma-qmlp-mmio-profile-75mhz-2026-06-08-115200-reset3-2026-06-08-194930.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/phase0-radar-axi-dma-qmlp-mmio-profile-75mhz-2026-06-08-115200-reset3-2026-06-08-194930.log) |
| Direct QMLP validation | PASS; 1000 large-golden samples and 54 boundary cases, `hw_cycles_avg=2213`. | [qmlp-validation-75mhz-2026-06-08-115200-reset4-2026-06-08-195019.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/qmlp-validation-75mhz-2026-06-08-115200-reset4-2026-06-08-195019.log) |
| Feature21 v1.4a compact board dump | COMPLETE; `samples=1000`, `cycles_avg=455`, `cycles_min=420`, `cycles_max=662`. | [feature21-v1p4a-compact-dump-75mhz-2026-06-08-115200-reset9-rebuilt-2026-06-08-200258.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/feature21-v1p4a-compact-dump-75mhz-2026-06-08-115200-reset9-rebuilt-2026-06-08-200258.log) |
| Feature21 v1.4a PC validation report | RTL dump matches Python exact-LUT mirror `1000/1000`; QMLP prediction agreement `95.20%`, changed `48/1000`. | [feature21-v1p4a-compact-validation-1000-75mhz-2026-06-08.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/feature21-v1p4a-compact-validation-1000-75mhz-2026-06-08.md) |

Current gate notes:

- `racc.*`: now has board MMIO/setup/polling evidence; evaluate with the named batch numbers rather than old unsplit `dma_avg`.
- `rqdot4`: Phase 0 now supports entering a prototype path. Static packed-MAC coverage is `98.14%`, and board CPU-only profiling shows `dot_mac_upper=93.43%`; keep the wording as an upper bound because this bucket includes activation/weight loads and loop control.
- Feature21 should be reported as a fixed-point/approximate hardware implementation checked against the documented exact-LUT mirror and classification consistency, not as a 1:1 float software clone.

## 2026-06-08 Feature21 Batch DMA Candidate

This is the next board-validation candidate generated after the slow per-sample Feature21 dump run. It changes the test flow to send all 1000 Feature21 golden frames through one DMA transaction and print one summary instead of doing per-sample DMA setup and verbose output.

Status:

- Offline build: PASS. Verilog generation and `tests/radar-axi-dma-feature21-golden.riscv` both rebuilt with `FEATURE21_DMA_BATCH_MODE=1`.
- Bitstream: PASS at 75 MHz. Final timing summary reports `WNS=+0.016 ns`, `TNS=0.000 ns`, `WHS=+0.010 ns`, and "All user specified timing constraints are met."
- Board validation: NOT YET RUN for this new bitstream. The previous reset-interrupted run used the old bitstream and should not be counted as batch-mode evidence.

Artifacts:

| Artifact | Path |
| --- | --- |
| Bitstream to program | [NexysVideoHarness-feature21-batch-dma-75mhz-2026-06-08.bit](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/feature21-batch-dma-2026-06-08/artifacts/NexysVideoHarness-feature21-batch-dma-75mhz-2026-06-08.bit) |
| Batch test ELF | [radar-axi-dma-feature21-golden-batch-2026-06-08.riscv](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/feature21-batch-dma-2026-06-08/artifacts/radar-axi-dma-feature21-golden-batch-2026-06-08.riscv) |
| Timing report | [timing-feature21-batch-dma-75mhz-2026-06-08.txt](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/feature21-batch-dma-2026-06-08/artifacts/timing-feature21-batch-dma-75mhz-2026-06-08.txt) |
| Utilization report | [utilization-feature21-batch-dma-75mhz-2026-06-08.txt](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/feature21-batch-dma-2026-06-08/artifacts/utilization-feature21-batch-dma-75mhz-2026-06-08.txt) |
| Build log | [bitstream-75mhz-feature21-batch-dma-2026-06-08.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/feature21-batch-dma-2026-06-08/bitstream-75mhz-feature21-batch-dma-2026-06-08.log) |

Next board command shape:

```bash
scripts/run_nexysvideo_uart_tsi.sh --tty /dev/ttyUSB0 --baudrate 115200 --bin logs/radar_nexysvideo/runtime/feature21-batch-dma-2026-06-08/artifacts/radar-axi-dma-feature21-golden-batch-2026-06-08.riscv --log-name feature21-batch-dma-75mhz-2026-06-08
```

## Functional Divisions

### 1. Official Chipyard Reference

Use these when you need Chipyard/Rocket/RoCC/TileLink background, not current project progress.

| Directory | Use |
| --- | --- |
| `docs/Chipyard-Basics/` | Chipyard setup and high-level concepts. |
| `docs/Customization/` | MMIO, RoCC, custom cores, DMA, boot process. |
| `docs/Generators/` | Rocket, Gemmini, BOOM, TestChipIP, prefetcher references. |
| `docs/TileLink-Diplomacy-Reference/` | TileLink/Diplomacy reference material. |
| `docs/Prototyping/` | FPGA board bring-up reference, including NexysVideo background. |
| `docs/Simulation/`, `docs/Software/`, `docs/Tools/`, `docs/VLSI/` | General reference; not weekly-report evidence unless explicitly used. |

Weekly-report value: low, unless a report needs background like RoCC vs MMIO.

### 2. Current RISC-V / Xradar Direction

Use these for the "RISC-V optimization" section of reports.

| File | Role |
| --- | --- |
| [riscv_core_feature21_qmlp_optimization_plan_2026-06-06.md](/home/soooarr/chipyard/docs/riscv_core_feature21_qmlp_optimization_plan_2026-06-06.md) | Main plan. Explains why the project needs a RISC-V/core contribution and compares custom instructions, `racc.*`, stream registers, frontend work, Vector/Gemmini-style alternatives. |
| [riscv_xradar_isa_spec_2026-06-07.md](/home/soooarr/chipyard/docs/riscv_xradar_isa_spec_2026-06-07.md) | Draft ISA semantics for `rqdot4`, `rqscale8`, `rqpack`, and reserved `racc.*`. |
| [performance/radar_core_extension_baseline_2026-06-06.md](/home/soooarr/chipyard/docs/performance/radar_core_extension_baseline_2026-06-06.md) | Phase 0 baseline gate: evidence, missing measurements, Gemmini and `racc.*` gate status. |
| [performance/xradar_offline_static_analysis_2026-06-07.md](/home/soooarr/chipyard/docs/performance/xradar_offline_static_analysis_2026-06-07.md) | Offline host tests, static MAC coverage, Amdahl table, and queued board commands. |
| [radar_rtl_implementation_logic_review_2026-06-08.md](/home/soooarr/chipyard/docs/radar_rtl_implementation_logic_review_2026-06-08.md) | Explains current RTL logic and separates custom instruction direction from existing MMIO + DMA accelerator baseline. |

Weekly-report value: high.

One-line stance:

> Current RISC-V work keeps `rqdot4/rqscale8` as active custom-instruction candidates, treats `racc.*` as a reserved control path pending MMIO/polling evidence, and keeps current Feature21/QMLP as the MMIO + DMA accelerator baseline.

2026-06-09 dot4 fallback/profile artifacts:

| Evidence | Status | Source |
| --- | --- | --- |
| Xradar host fallback and static model | PASS; `rqdot4=848`, `scalar_tail_macs=64`, `rqscale8=96`, packed MAC coverage `98.14%`. | [xradar-host-and-static-2026-06-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/xradar-host-and-static-2026-06-09.log) |
| CPU profile scalar ELF | Built for board comparison against the fallback path. | [radar-qmlp-cpu-profile-scalar-2026-06-09.riscv](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-qmlp-cpu-profile-scalar-2026-06-09.riscv) |
| CPU profile Xradar fallback ELF | Built with `RADAR_QMLP_CPU_PROFILE_USE_XRADAR_FALLBACK=1`; reports `xradar_ops` on board. | [radar-qmlp-cpu-profile-xradar-fallback-2026-06-09.riscv](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-qmlp-cpu-profile-xradar-fallback-2026-06-09.riscv) |

Current dot4 boundary: the software fallback and profile path is the golden/measurement reference; the first RoCC RTL prototype now exists, and the pipelined version has a 75 MHz timing-clean bitstream. The bitstream has been programmed, single-instruction `rqdot4` passes on board, and the memory-based board smoke validates 4 basic `rqdot4` cases plus all 8 QMLP semantic cases.

2026-06-09 RoCC prototype artifacts:

| Item | Status | Path |
| --- | --- | --- |
| Xradar RoCC source | Implements `custom0/funct=0` `rqdot4` only; no `rqscale8`, `rqpack`, or `racc.*` RTL yet. | [XradarRoCC.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/XradarRoCC.scala) |
| Dedicated NexysVideo config | Keeps the RoCC design separate from the known MMIO/DMA 75 MHz config. | `RadarAXIMMIOXradarRoCCNexysVideo75MHzConfig` in [Configs.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/Configs.scala) |
| RoCC smoke ELF | Builds and compares RoCC `rqdot4` against the software fallback over basic cases plus 8 QMLP semantic cases. Only run on a RoCC bitstream. | [radar-xradar-rocc-smoke.c](/home/soooarr/chipyard/tests/radar-xradar-rocc-smoke.c), [radar-xradar-rocc-smoke.riscv](/home/soooarr/chipyard/tests/radar-xradar-rocc-smoke.riscv) |
| Verilog generation | PASS for `RadarAXIMMIOXradarRoCCNexysVideo75MHzConfig`; generated `RocketTile.sv` contains the four signed int8 multiply lanes and sign-extended response path. | [xradar-rocc-verilog-75mhz-2026-06-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/xradar-rocc-verilog-75mhz-2026-06-09.log) |
| 75 MHz combinational attempt | Bitstream was written, but the final timing gate failed: WNS `-0.330 ns`, TNS `-29.441 ns`, WHS `+0.016 ns`. Keep this as evidence that the one-cycle RoCC DSP/response path was too tight. | [timing-xradar-rocc-75mhz-timingfail-2026-06-09.txt](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/timing-xradar-rocc-75mhz-timingfail-2026-06-09.txt), [drc-xradar-rocc-75mhz-timingfail-2026-06-09.txt](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/drc-xradar-rocc-75mhz-timingfail-2026-06-09.txt) |
| 75 MHz pipelined implementation | PASS; final timing WNS `+0.004 ns`, TNS `0.000 ns`, WHS `+0.009 ns`. Programmed successfully on the NexysVideo board at 20:04. | [NexysVideoHarness-xradar-rocc-pipelined-75mhz-timingclean-2026-06-09.bit](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/NexysVideoHarness-xradar-rocc-pipelined-75mhz-timingclean-2026-06-09.bit), [program-xradar-rocc-pipelined-75mhz-2026-06-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/program-xradar-rocc-pipelined-75mhz-2026-06-09.log) |
| Original RoCC smoke board attempt | FAIL, but due to software instruction encoding: `.insn r CUSTOM_0, 0, 0` encoded `xd/xs1/xs2=0`, so the observed result stayed at the packed `rs1` value `0xfc03fe01` instead of the RoCC response. | [xradar-rocc-smoke-75mhz-2026-06-09-2026-06-09-201352.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-rocc-smoke-75mhz-2026-06-09-2026-06-09-201352.log) |
| Fixed single-instruction board probe | PASS for one `rqdot4` instruction with `funct3=7`; readback showed `lhs=0xfc03fe01`, `rhs=0x08f906fb`, result `0xffffffba` (`-70`). This is the expected dot product for lanes `{1,-2,3,-4}` and `{-5,6,-7,8}`. | [xradar-rocc-board-status-2026-06-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-board-status-2026-06-09.md) |
| Fixed memory-smoke board validation | PASS; no `printf`/HTIF output dependency. Readback showed stage `0x7777aaaa`, fail code `0`, basic mask `0x0f`, QMLP mask `0xff`, `rqdot4_ops=848`, scalar tail MACs `64`, `rqscale8=96`, packed MAC coverage `98.14%`. | [xradar-rocc-memory-smoke-readback-2026-06-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-memory-smoke-readback-2026-06-09.md) |
| Fixed printable RoCC smoke | PASS after replacing unsupported bare-metal `%-20s` with `%s`; prints all 8 QMLP semantic cases and final `PASSED`. | [xradar-rocc-smoke-funct3fix-printfix-after-reset-75mhz-2026-06-09-2026-06-09-210735.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/xradar-rocc-smoke-funct3fix-printfix-after-reset-75mhz-2026-06-09-2026-06-09-210735.log) |

Current RoCC boundary: `rqdot4` has board functional evidence on the timing-clean bitstream. Memory-smoke and printable smoke both validate 4 basic dot4 cases and 8 QMLP semantic cases. `rqscale8`, `rqpack`, and `racc.*` remain unimplemented in RoCC RTL.

RoCC debug carryover rules:

- Inline asm must encode `funct3=7` for `.insn r CUSTOM_0, 7, 0, rd, rs1, rs2`. In the RoCC custom instruction encoding, these bits request `xd/xs1/xs2`; using `funct3=0` can leave the destination unwritten. The board symptom was `got=0xfc03fe01`, exactly the packed `rs1` operand, not a dot-product result.
- Bare-metal HTIF `printf` support in this repo is limited. Avoid width/left-align formats such as `%-20s` or `%-16s`; use `%s` or fixed labels. The fixed printable smoke only passed after replacing `%-20s` with `%s`.
- Separate functional arithmetic from output-path debugging. Use the single probe or memory-smoke to verify RoCC dataflow; use the HTIF probe to verify printing/exit. A timeout is expected for memory-smoke because it intentionally spins for UART-TSI readback.
- After loading a new ELF over UART-TSI, press `CPU_RESET` first and use `/dev/ttyUSB0` at `115200`.

### 3. Timing / Frequency Closure

Use these for timing, implementation, and FPGA frequency-limit reports.

| File or directory | Role |
| --- | --- |
| [feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md](/home/soooarr/chipyard/docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md) | Long continuity log. Use when resuming timing work, but do not read top-to-bottom unless needed. |
| [feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md](/home/soooarr/chipyard/docs/feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md) | Clean summary of 75 MHz closure and reusable lessons. Best weekly/thesis source. |
| `logs/radar_nexysvideo/runtime/feature21-frequency-limit-*` | Raw build/run evidence outside `docs/`. Use only when exact logs or reports are needed. |

Weekly-report value: high for closure report, medium for rolling summary, low for raw logs unless citing exact WNS/TNS.

Current timing summary:

- Promoted 75 MHz candidate: WNS `+0.040 ns`, TNS `0.000 ns`, WHS `+0.017 ns`.
- Final limiter: Rocket frontend/icache/fetch-queue/control into execute decode.
- QMLP, ordinary Feature21 quant/writeback, and UART-TSI TL-A are no longer leading 75 MHz paths.

### 4. RTL / Hardware Implementation

Use these to explain what hardware exists and how it works.

| File or directory | Role |
| --- | --- |
| [radar_rtl_implementation_logic_review_2026-06-08.md](/home/soooarr/chipyard/docs/radar_rtl_implementation_logic_review_2026-06-08.md) | Current best entry for QMLP/Feature21/DMA/MMIO/UART-TSI logic and untested cases. |
| [radar_nexysvideo_qmlp_accelerator_2026-04-06.md](/home/soooarr/chipyard/docs/radar_nexysvideo_qmlp_accelerator_2026-04-06.md) | Earlier QMLP accelerator overview. |
| [radar_nexysvideo_rtl_coding_guidelines_2026-04-02.md](/home/soooarr/chipyard/docs/radar_nexysvideo_rtl_coding_guidelines_2026-04-02.md) | RTL coding and integration style. |
| [radar_qmlp_k7_backend_and_validation_2026-04-14.md](/home/soooarr/chipyard/docs/radar_qmlp_k7_backend_and_validation_2026-04-14.md) | K7/QMLP hardware backend and board validation material. |
| `docs/qmlp_refactor/` | QMLP staged refactor history and validation checkpoints. |
| `docs/feature21_hardware/` | Feature21 hardware status and planning notes. |
| `docs/Xilinx_IP_config/` | Xilinx IP/DMA configuration notes. |

Weekly-report value: medium to high, depending on whether the week includes RTL work.

### 5. Validation / Performance / Measurement

Use these for quantitative evidence and board/profile status.

| File or directory | Role |
| --- | --- |
| `docs/performance/` | Current performance and profiling docs. |
| [performance/radar_qmlp_dma_profile_2026-04-16.md](/home/soooarr/chipyard/docs/performance/radar_qmlp_dma_profile_2026-04-16.md) | Older QMLP DMA profile. |
| [performance/radar_core_extension_baseline_2026-06-06.md](/home/soooarr/chipyard/docs/performance/radar_core_extension_baseline_2026-06-06.md) | Current Phase 0 gate and missing board profiles. |
| [performance/xradar_offline_static_analysis_2026-06-07.md](/home/soooarr/chipyard/docs/performance/xradar_offline_static_analysis_2026-06-07.md) | Host/offline results and board commands. |
| `docs/feature_preproc_compare_20260420/` | Feature14/18/21 comparison data, boundary cases, benchmark outputs. |

Weekly-report value: high when writing "evidence/results"; this is where numbers should come from.

### 6. Thesis / Paper / PPT Material

Use these for writing thesis sections, report framing, and slides.

| File or directory | Role |
| --- | --- |
| [paper/README.md](/home/soooarr/chipyard/docs/paper/README.md) | Existing paper-material index. |
| [paper/radar_thesis_logic_gap_audit_2026-04-16.md](/home/soooarr/chipyard/docs/paper/radar_thesis_logic_gap_audit_2026-04-16.md) | Thesis gap/risk analysis. |
| [paper/radar_hardware_thesis_framework_2026-04-13.md](/home/soooarr/chipyard/docs/paper/radar_hardware_thesis_framework_2026-04-13.md) | Thesis framework. |
| [paper/feature21-thesis-methodology.md](/home/soooarr/chipyard/docs/paper/feature21-thesis-methodology.md) | Feature21 methodology material. |
| [paper/feature21-thesis-experiment-summary.md](/home/soooarr/chipyard/docs/paper/feature21-thesis-experiment-summary.md) | Experiment summary material. |
| [paper/feature21-weekly-report-ppt-outline.md](/home/soooarr/chipyard/docs/paper/feature21-weekly-report-ppt-outline.md) | PPT/weekly outline source. |

Weekly-report value: medium. Use these to polish language, not to replace fresh evidence files.

### 7. Project Status / Handoff

Use these when you need the state of the whole project.

| File | Role |
| --- | --- |
| [weekly_report_2026-06-04.md](/home/soooarr/chipyard/docs/weekly_report_2026-06-04.md) | Earlier weekly report. |
| [weekly_report_2026-06-07_phase0_xradar_obsidian.md](/home/soooarr/chipyard/docs/weekly_report_2026-06-07_phase0_xradar_obsidian.md) | Latest weekly-style summary after Phase 0/Xradar/Obsidian work. |
| [radar_project_status_index_2026-04-09.md](/home/soooarr/chipyard/docs/radar_project_status_index_2026-04-09.md) | Older project status index. Useful but stale relative to June Xradar/timing work. |
| [radar_soc_progress_report_2026-04-05.md](/home/soooarr/chipyard/docs/radar_soc_progress_report_2026-04-05.md) | Older SoC progress report. |

Weekly-report value: high for the latest weekly report; medium/low for older status docs.

### 8. Archive, Backups, And Patch Evidence

Use these only when reconstructing history or protecting work.

| Directory | Use |
| --- | --- |
| `docs/archive/` | Old but useful bring-up/research notes moved out of the main path. |
| `docs/backups/` | Patch backups before edits. Do not use as primary reading material. |
| `docs/submodule_patches/` | Submodule patch evidence. |

Weekly-report value: low, except when a backup or patch itself is part of the week's process.

## Weekly Report Conversion Guide

Use this section as the practical bridge from docs to weekly report.

| Weekly report section | Best source |
| --- | --- |
| This week's completed work | Latest `weekly_report_*.md`, `xradar_offline_static_analysis`, `radar_rtl_implementation_logic_review`. |
| Timing progress | 75 MHz closure report; rolling summary only for exact checkpoint details. |
| RISC-V optimization progress | RISC-V optimization plan, Xradar ISA spec, Phase 0 baseline, offline static analysis. |
| RTL understanding / implementation logic | RTL implementation logic review. |
| Validation status | Performance docs, feature preproc compare docs, board logs if available. |
| Risks / not yet tested | RTL implementation logic review checklist; Phase 0 baseline gate. |
| Next steps | Phase 0 baseline next commands, offline static analysis next tasks, RTL review coverage table. |

Suggested weekly report structure:

```text
1. Work completed
2. Key evidence / numbers
3. Current status
4. Risks and missing tests
5. Next work plan
```

Current Obsidian support:

- Obsidian already has synced research notes and a weekly report note under `~/obsidian/Codex/Chipyard/`.
- It supports weekly-report conversion in the practical sense: the latest notes are already organized enough to lift into a weekly report.
- A dedicated weekly source-map/template note should be added so future weekly reports do not require searching the whole repo again.

## Recommended Future Physical Layout

Do not move files immediately. If the navigation layer proves useful, the low-risk next step is to gradually move or mirror active project docs into this shape:

```text
docs/radar/
  00_index/
  01_status_weekly/
  02_timing_frequency/
  03_rtl_hardware/
  04_validation_performance/
  05_riscv_xradar/
  06_thesis_paper/
  archive/
```

For now, keep this functional map as the stable entrypoint and avoid breaking old links.
