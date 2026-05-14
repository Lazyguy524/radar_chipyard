# Feature21 Bitstream Index

Date: 2026-05-05

This document indexes existing bitstreams for follow-up board programming and experiment-data supplementation. It does not generate a new bitstream and does not modify RTL/Chisel.

## Recommended Bitstreams

| Priority | Version / purpose | Bitstream | SHA256 | Use for |
|---:|---|---|---|---|
| 1 | v1.4a density exact-LUT final thesis baseline | `fpga/deliverables/radar_nexysvideo_bits/662-feature21-v1p4a-density-recip-exact-lut-2026-04-26.bit` | `24ed400ed3d3f167472e388aa1765a60481a4b475184338008bf150e0d463ec5` | Final 1000-sample Feature21 board dump, RTL-vs-Python mirror, software-golden feature comparison, QMLP agreement |
| 2 | v1.3 fixed-point baseline | `fpga/deliverables/radar_nexysvideo_bits/646-feature21-v1p3-preproc-qmlp-2026-04-22.bit` | `260e5353ed241dccf5eac2d53416c9b31bf43ae826557597aa64f77ad3725a56` | Historical comparison, v1.3 board subset rerun, Feature21 -> QMLP smoke |
| 3 | Feature21 preproc-chain earlier integration | `fpga/deliverables/radar_nexysvideo_bits/611-feature21-preproc-chain-2026-04-20.bit` | `9289d784bde749ee6b8b8c787c0369c0c7aff8128613ba1a53fa9f7f4d446250` | Earlier chain sanity check only; not the final thesis baseline |
| 4 | QMLP word-bank/ROM baseline | `fpga/deliverables/radar_nexysvideo_bits/545-qmlp-wordbank-refactor-k7-2026-04-15.bit` | `15030d44f2526257d9bc95bde3f79b577971fcf6f2dd79787749fcf08d14cec9` | QMLP-only validation baseline; not a Feature21 final preprocessor bitstream |

## Final Thesis Baseline: v1.4a Density Exact-LUT

Use this bitstream for the final Feature21 board experiments:

```text
/home/soooarr/chipyard/fpga/deliverables/radar_nexysvideo_bits/662-feature21-v1p4a-density-recip-exact-lut-2026-04-26.bit
```

Known validated result from existing reports:

| Metric | Existing value |
|---|---:|
| RTL vs Python mirror full 21-byte match | 1000/1000 |
| f13 `density_2d` RTL vs Python mirror match | 1000/1000 |
| Software golden vs board feature match | 67.10% |
| Mean abs int8 error | 0.791 |
| Max abs int8 error | 122 |
| QMLP prediction agreement | 95.20% |
| Changed predictions | 48/1000 |
| Cycles avg/min/max | 397 / 387 / 589 |

Primary board ELF:

```text
/home/soooarr/chipyard/tests/radar-axi-dma-feature21-golden.riscv
```

Suggested run command after programming:

```bash
scripts/run_nexysvideo_uart_tsi.sh \
  --tty /dev/ttyUSB1 \
  --baudrate 115200 \
  --bin tests/radar-axi-dma-feature21-golden.riscv \
  --log-name feature21-v1p4a-density-final-dump
```

If the board enumerates as `/dev/ttyUSB0`, use that tty instead.

Post-run report command:

```bash
python3 tools/feature21_board_validation_report.py \
  --board-log logs/radar_nexysvideo/runtime/feature21-v1p4a-density-final-dump-*.log \
  --golden-dir docs/feature_preproc_compare_20260420/feature21/golden \
  --mirror-mode density_recip_exact_lut \
  --qmlp-params docs/feature_preproc_compare_20260420/feature21/qmlp_params_21.h \
  --out docs/paper/feature21-v1p4a-density-final-board-validation.md
```

If shell glob expansion selects more than one log, replace the `--board-log` argument with the exact generated log path.

Existing source reports:

| Topic | Source |
|---|---|
| Full implementation and timing | `logs/radar_nexysvideo/runtime/662-feature21-v1p4a-density-bitstream-and-board-attempt-summary-2026-04-26.md` |
| 1000-sample board validation | `logs/radar_nexysvideo/runtime/664-feature21-v1p4a-density-compact-validation-1000-2026-04-26.md` |
| Residual attribution | `logs/radar_nexysvideo/runtime/feature21-v1p4a-residual-error-attribution-1000.md` |
| Programming Tcl used previously | `logs/radar_nexysvideo/runtime/662-program-feature21-v1p4a-density-2026-04-26.tcl` |

## v1.3 Baseline Bitstream

Use this bitstream only when a direct historical baseline rerun is needed:

```text
/home/soooarr/chipyard/fpga/deliverables/radar_nexysvideo_bits/646-feature21-v1p3-preproc-qmlp-2026-04-22.bit
```

Known existing results:

| Metric | Existing value |
|---|---:|
| Historical board subset samples | 16 |
| Software-golden feature match | 73.50% |
| Exact vectors | 0/16 |
| Mean abs int8 error | 1.181 |
| Max abs int8 error | 73 |
| Cycles avg/min/max | 404 / 356 / 690 |
| Feature21 -> QMLP smoke | PASS |

Useful ELFs:

```text
/home/soooarr/chipyard/tests/radar-axi-dma-feature21.riscv
/home/soooarr/chipyard/tests/radar-axi-dma-feature21-golden.riscv
```

Suggested smoke command:

```bash
scripts/run_nexysvideo_uart_tsi.sh \
  --tty /dev/ttyUSB0 \
  --baudrate 115200 \
  --bin tests/radar-axi-dma-feature21.riscv \
  --log-name feature21-v1p3-smoke-rerun
```

Suggested golden-subset / dump command:

```bash
scripts/run_nexysvideo_uart_tsi.sh \
  --tty /dev/ttyUSB0 \
  --baudrate 115200 \
  --bin tests/radar-axi-dma-feature21-golden.riscv \
  --log-name feature21-v1p3-golden-rerun
```

Existing source reports:

| Topic | Source |
|---|---|
| Bitstream summary | `logs/radar_nexysvideo/runtime/649-feature21-v1p3-bitstream-summary-2026-04-22.md` |
| Board smoke pass | `logs/radar_nexysvideo/runtime/651-feature21-v1p3-board-pass-summary-2026-04-23.md` |
| 16-sample golden subset | `logs/radar_nexysvideo/runtime/654-feature21-golden-subset-summary-2026-04-25.md` |

## Earlier / Auxiliary Bitstreams

### Feature21 Preproc-Chain, 2026-04-20

```text
/home/soooarr/chipyard/fpga/deliverables/radar_nexysvideo_bits/611-feature21-preproc-chain-2026-04-20.bit
```

Use only for earlier integration sanity checks. The existing note recommends:

```text
tests/radar-axi-dma-qmlp-validation.riscv
tests/radar-axi-dma-qmlp-chain-validation.riscv
```

Source:

```text
logs/radar_nexysvideo/runtime/617-feature21-preproc-chain-bitstream-summary-2026-04-20.md
```

### QMLP Word-Bank/ROM, 2026-04-15

```text
/home/soooarr/chipyard/fpga/deliverables/radar_nexysvideo_bits/545-qmlp-wordbank-refactor-k7-2026-04-15.bit
```

Use only for QMLP-only hardware validation. Existing report shows:

| Metric | Value |
|---|---:|
| large_golden | 1000/1000 |
| boundary_cases | 54/54 |
| QMLP kernel cycles | 1301 cycles/sample |

Source:

```text
logs/radar_nexysvideo/runtime/548-qmlp-wordbank-refactor-bitstream-summary-2026-04-15.md
logs/radar_nexysvideo/runtime/553-qmlp-wordbank-refactor-board-pass-summary-2026-04-15.md
```

## Programming Template

There is an existing Tcl for the v1.4a bitstream:

```text
logs/radar_nexysvideo/runtime/662-program-feature21-v1p4a-density-2026-04-26.tcl
```

Run it with Vivado batch mode if the JTAG device is connected:

```bash
vivado -mode batch -source logs/radar_nexysvideo/runtime/662-program-feature21-v1p4a-density-2026-04-26.tcl
```

For another bitstream, copy the Tcl and change only the `PROGRAM.FILE` path. Do not rebuild unless intentionally starting a new hardware version.

Generic Tcl template:

```tcl
open_hw_manager
connect_hw_server
open_hw_target

set devices [get_hw_devices xc7a200t*]
if {[llength $devices] == 0} {
  puts "ERROR: no xc7a200t hardware device found"
  exit 2
}

set dev [lindex $devices 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE {/absolute/path/to/NexysVideoHarness.bit} $dev
program_hw_devices $dev
refresh_hw_device $dev

puts "PROGRAM_DONE"
exit
```

## Data-To-Fill Checklist

After a rerun, append new data to the relevant thesis docs:

| Data item | Target document |
|---|---|
| Board log path and exact bit SHA | `docs/paper/feature21-thesis-experiment-summary.md` |
| Feature match / MAE / max error | `docs/paper/feature21-thesis-experiment-summary.md` |
| QMLP agreement / accuracy / changed predictions | `docs/paper/feature21-thesis-experiment-summary.md` |
| Class balance and confusion matrix | `docs/paper/feature21-risk-and-future-work.md` |
| Residual feature attribution, especially f11 | `docs/paper/feature21-risk-and-future-work.md` |
