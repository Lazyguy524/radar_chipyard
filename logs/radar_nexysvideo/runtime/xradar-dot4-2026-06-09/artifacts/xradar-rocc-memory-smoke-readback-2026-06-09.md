# Xradar RoCC Memory Smoke Readback

Date: 2026-06-09

## Artifact

- ELF: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-xradar-rocc-memory-smoke-funct3fix-2026-06-09.riscv`
- Source: `tests/radar-xradar-rocc-memory-smoke.c`
- Bitstream already programmed: `NexysVideoHarness-xradar-rocc-pipelined-75mhz-timingclean-2026-06-09.bit`
- UART-TSI: `/dev/ttyUSB0`, `115200`

## Summary Readback

| Field | Value | Meaning |
| --- | --- | --- |
| `0x80010000` | `0x524f4343` | Low word of magic marker |
| `0x80010008` | `0x7777aaaa` | PASS stage |
| `0x80010010` | `0x00000000` | Fail code |
| `0x80010018` | `0x0000000f` | Basic pass mask, 4/4 |
| `0x80010020` | `0x000000ff` | QMLP pass mask, 8/8 |
| `0x80010028` | `0x00000004` | Basic cases completed |
| `0x80010030` | `0x00000008` | QMLP cases completed |
| `0x80010038` | `0x00000350` | `rqdot4_ops=848` |
| `0x80010040` | `0x00000040` | `scalar_tail_macs=64` |
| `0x80010048` | `0x00000060` | `rqscale8_ops=96` |
| `0x80010050` | `0x00000d80` | `total_macs=3456` |
| `0x80010058` | `0x00002656` | packed MAC coverage x100 = `9814` |

## Basic Dot4 Cases

| Case | LHS | RHS | RoCC | Expected |
| --- | --- | --- | --- | --- |
| 0 | `0xfc03fe01` | `0x08f906fb` | `0xffffffba` | `0xffffffba` |
| 1 | `0xff01807f` | `0x7f800101` | `0xffffff00` | `0xffffff00` |
| 2 | `0x00000000` | `0xf9079d63` | `0x00000000` | `0x00000000` |
| 3 | `0x4ec822f4` | `0x0607f8f7` | `0xffffffa8` | `0xffffffa8` |

## QMLP Semantic Cases

| Case | RoCC Logit0 | Scalar Logit0 | RoCC Logit1 | Scalar Logit1 | `rqdot4_ops` | Tail MACs |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | `0x00000357` | `0x00000357` | `0xffffd62e` | `0xffffd62e` | `0x350` | `0x40` |
| 1 | `0x0000035d` | `0x0000035d` | `0x000001fc` | `0x000001fc` | `0x350` | `0x40` |
| 2 | `0x000003d3` | `0x000003d3` | `0xffffde69` | `0xffffde69` | `0x350` | `0x40` |
| 3 | `0x00000123` | `0x00000123` | `0x00000097` | `0x00000097` | `0x350` | `0x40` |
| 4 | `0xfffff09c` | `0xfffff09c` | `0xffffe970` | `0xffffe970` | `0x350` | `0x40` |
| 5 | `0x00000389` | `0x00000389` | `0xffffeb63` | `0xffffeb63` | `0x350` | `0x40` |
| 6 | `0xfffffe16` | `0xfffffe16` | `0xffffda1e` | `0xffffda1e` | `0x350` | `0x40` |
| 7 | `0xfffffe4b` | `0xfffffe4b` | `0x00000da8` | `0x00000da8` | `0x350` | `0x40` |

## Verdict

PASS for the current board `rqdot4` scope. This validates repeated RoCC command sequencing and the 8-case QMLP semantic path without relying on printable HTIF output.
