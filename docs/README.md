# Radar Docs Functional Map

Date: 2026-06-08

Purpose: give the current messy `docs/` tree a functional navigation layer without moving files or breaking old references. Use this file as the first stop before writing weekly reports, thesis notes, or the next implementation handoff.

## Quick Answer

The current `docs/` content should be read in three layers:

1. Official Chipyard docs: background reference, mostly `.rst`, not project progress.
2. Active radar project docs: current evidence, timing, RTL, RISC-V/Xradar, validation, and weekly-report material.
3. Archive/backups/generated evidence: useful for traceability, not the first place to read.

For weekly reports, start from:

- [weekly_report_2026-06-07_phase0_xradar_obsidian.md](/home/soooarr/chipyard/docs/weekly_report_2026-06-07_phase0_xradar_obsidian.md)
- [radar_rtl_implementation_logic_review_2026-06-08.md](/home/soooarr/chipyard/docs/radar_rtl_implementation_logic_review_2026-06-08.md)
- [performance/radar_core_extension_baseline_2026-06-06.md](/home/soooarr/chipyard/docs/performance/radar_core_extension_baseline_2026-06-06.md)
- [performance/xradar_offline_static_analysis_2026-06-07.md](/home/soooarr/chipyard/docs/performance/xradar_offline_static_analysis_2026-06-07.md)
- [feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md](/home/soooarr/chipyard/docs/feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md)

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

