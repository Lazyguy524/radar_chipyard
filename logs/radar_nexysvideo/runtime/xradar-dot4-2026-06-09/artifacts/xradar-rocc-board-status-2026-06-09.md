# Xradar RoCC Board Status

Date: 2026-06-09

## Program

- Bitstream: `NexysVideoHarness-xradar-rocc-pipelined-75mhz-timingclean-2026-06-09.bit`
- Program log: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/program-xradar-rocc-pipelined-75mhz-2026-06-09.log`
- Result: `PROGRAM_DONE`
- Vivado note: `Device xc7a200t ... has no supported debug core(s)` is expected for this design and is not a programming failure.

## Timing

- WNS: `+0.004 ns`
- TNS: `0.000 ns`
- WHS: `+0.009 ns`
- Timing report says all user timing constraints are met.

## Board Attempts

- Original full smoke ELF failed the first basic case:
  - Log: `logs/radar_nexysvideo/runtime/xradar-rocc-smoke-75mhz-2026-06-09-2026-06-09-201352.log`
  - Observed: `got=-66847231`, expected `-70`
  - Diagnosis: the inline assembly used `.insn r CUSTOM_0, 0, 0`, which encoded RoCC `xd/xs1/xs2=0`. The observed value `0xfc03fe01` matches the packed `rs1` input, so this was a software instruction-encoding bug, not valid RoCC arithmetic evidence.
- Fixed full smoke ELF:
  - Artifact: `radar-xradar-rocc-smoke-funct3fix-2026-06-09.riscv`
  - Encoding: `funct3=7`, so `xd/xs1/xs2=1`
  - Board status: selfcheck passed, but the run timed out before visible HTIF output. This is not a full smoke PASS.
- Fixed single-instruction probe:
  - Artifact: `radar-xradar-rocc-single-probe-funct3fix-2026-06-09.riscv`
  - Encoding: `funct3=7`, so `xd/xs1/xs2=1`
  - Probe writeback read through UART-TSI:
    - `0x80003000 -> 0x11110000`
    - `0x80003008 -> 0xfc03fe01`
    - `0x80003010 -> 0x08f906fb`
    - `0x80003018 -> 0xffffffba`
    - `0x80003020 -> 0x2222aaaa`
  - Expected arithmetic: `0xfc03fe01` packs lanes `{1, -2, 3, -4}` and `0x08f906fb` packs lanes `{-5, 6, -7, 8}`. The signed int8 dot product is `1*(-5) + (-2)*6 + 3*(-7) + (-4)*8 = -70`.
  - Interpretation: one board-executed `rqdot4` returned `-70` for the first basic case and passed the probe status check.
- Fixed memory-smoke validation:
  - Artifact: `radar-xradar-rocc-memory-smoke-funct3fix-2026-06-09.riscv`
  - Encoding: `funct3=7`, so `xd/xs1/xs2=1`
  - Coverage: 4 basic `rqdot4` cases plus 8 QMLP semantic cases.
  - Summary readback:
    - Stage: `0x7777aaaa`
    - Fail code: `0x00000000`
    - Basic pass mask: `0x0000000f`
    - QMLP pass mask: `0x000000ff`
    - Basic cases completed: `4`
    - QMLP cases completed: `8`
    - `rqdot4_ops=848`
    - `scalar_tail_macs=64`
    - `rqscale8_ops=96`
    - `packed_mac_coverage_x100=9814`
  - Interpretation: the memory-based board smoke passed the full current `rqdot4` semantic workload without relying on HTIF/printf output.
- Repeat-after-reset memory-smoke validation:
  - Log: `logs/radar_nexysvideo/runtime/xradar-rocc-memory-smoke-repeat-after-reset-75mhz-2026-06-09-2026-06-09-205440.log`
  - Fresh reset was applied before the rerun.
  - Selfcheck passed over all ELF chunks.
  - Summary readback matched the previous PASS:
    - Stage: `0x7777aaaa`
    - Fail code: `0x00000000`
    - Basic pass mask: `0x0000000f`
    - QMLP pass mask: `0x000000ff`
    - Basic cases completed: `4`
    - QMLP cases completed: `8`
    - `rqdot4_ops=848`
    - `scalar_tail_macs=64`
    - `rqscale8_ops=96`
    - `packed_mac_coverage_x100=9814`
  - Interpretation: the memory-smoke PASS is repeatable across a fresh CPU reset.
- HTIF/printf probe:
  - Artifact: `radar-xradar-rocc-htif-probe-funct3fix-2026-06-09.riscv`
  - Log: `logs/radar_nexysvideo/runtime/xradar-rocc-htif-probe-funct3fix-75mhz-2026-06-09-2026-06-09-210454.log`
  - Result: PASS; printed `before rqdot4`, `after rqdot4 got=-70 expected=-70`, and `PASSED`.
  - Interpretation: HTIF/printf is not globally broken on the RoCC bitstream.
- Fixed printable full smoke:
  - Artifact: `radar-xradar-rocc-smoke-funct3fix-printfix-2026-06-09.riscv`
  - Source fix: replaced unsupported bare-metal `%-20s` with `%s`.
  - Log: `logs/radar_nexysvideo/runtime/xradar-rocc-smoke-funct3fix-printfix-after-reset-75mhz-2026-06-09-2026-06-09-210735.log`
  - Result: PASS; all 8 QMLP semantic cases printed and final line was `[XRADAR-ROCC] PASSED`.
  - Counts: `rqdot4=848`, `scalar_tail_macs=64`, `rqscale8=96`, packed MAC coverage x100 `9814`.
  - Interpretation: the earlier printable-smoke timeout was caused by software-side print/format handling, not by RoCC functional behavior.
- Scalar-vs-RoCC cycle profile:
  - Artifact: `radar-xradar-rocc-cycle-profile-2026-06-09.riscv`
  - Log: `logs/radar_nexysvideo/runtime/xradar-rocc-cycle-profile-75mhz-2026-06-09-2026-06-09-215919.log`
  - One board run after fresh reset covered both scalar QMLP and RoCC `rqdot4` QMLP.
  - Result: PASS; scalar QMLP `cycles_avg=168203`, RoCC `rqdot4` QMLP `cycles_avg=62532`.
  - Reported speedup: `speedup_x1000=2689`, about `2.689x` for this QMLP-kernel profile.
  - Counts: `rqdot4_avg=848`, `scalar_tail_macs_avg=64`, `rqscale8_avg=96`, packed MAC coverage x100 `9814`.
  - Interpretation: this is first board-measured speedup evidence for the implemented `rqdot4` RoCC path. It is not a full Feature21+QMLP end-to-end speedup claim.

## Current Boundary

The timing-clean RoCC bitstream is programmed and has repeatable board validation for the current `rqdot4` scope. A single-instruction probe passes, memory-smoke passes 4 basic dot-product cases plus all 8 QMLP semantic cases across a fresh reset rerun, HTIF probe passes, fixed printable smoke passes, and the combined scalar-vs-RoCC profile shows about `2.689x` QMLP-kernel speedup for the RoCC-dot4 path. `rqscale8`, `rqpack`, and `racc.*` remain unimplemented in RoCC RTL.
