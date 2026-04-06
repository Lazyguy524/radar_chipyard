# QMLP Accelerator First-Cut Status

- Model target: frozen `k=3 + rcs21 + 21->64->32->2 INT8 QMLP`
- Release inputs used:
  - `docs/hardware_handoff_model_spec.md`
  - `releases/input_convergence_k3_rcs21_20260406/`
  - `releases/input_convergence_k3_rcs21_20260406/hardware_golden/`

## Implemented

- Added `RadarAXISQMLP` stream accelerator in
  `fpga/src/main/scala/nexysvideo/RadarQMLP.scala`
- Integrated QMLP routing and CSR page into
  `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
- Added software-side CSR helpers in
  `tests/radar_axi_dma_common.h`
- Added bare-metal bring-up test in
  `tests/radar-axi-dma-qmlp.c`
- Added build rule in
  `tests/Makefile`

## Function Shape

- Input packet: 32 bytes on AXI-Stream
- Valid feature bytes: first 21 bytes
- Output packet: 8 bytes carrying `logit0:int32` and `logit1:int32`
- Internal compute:
  - L1: `21 -> 64`, int32 accumulate, requant, ReLU, int8 output
  - L2: `64 -> 32`, int32 accumulate, requant, ReLU, int8 output
  - L3: `32 -> 2`, int32 logits output

## Validation Status

- Bare-metal test build passed:
  - `222-build-qmlp-test-2026-04-06.log`
- FPGA `verilog` generation passed after fixing width-boundary literals:
  - `223-fpga-verilog-qmlp-2026-04-06.log` captured first width error
  - `224-fpga-verilog-qmlp-rerun-2026-04-06.log` passed after fix

## Key Fix

- Fixed boundary-width literal bugs in `RadarQMLP.scala`
  - `64.U(6.W)` -> `64.U(7.W)`
  - `32.U(5.W)` -> `32.U(6.W)`

## Next Step

- Start `bitstream` build for the QMLP-integrated design
- Then run on board:
  - `radar-axi-dma-regression.riscv`
  - `radar-axi-dma-qmlp.riscv`
