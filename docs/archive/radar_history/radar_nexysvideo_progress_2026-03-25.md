# Radar Nexys Video Progress Snapshot

Date: 2026-03-25

## Scope

This snapshot covers the ongoing bring-up work for a small Rocket based Chipyard configuration targeting Nexys Video, with focus on exporting an external AXI MMIO window for radar-related IP integration and validating the address map in simulation.

## Current Progress

The work has progressed beyond basic config drafting. The repository now contains:

- A Nexys Video FPGA config with an exported AXI MMIO master window:
  `RadarAXIMMIONexysVideoConfig`
- A matching simulation config for functional validation:
  `RadarAXIMMIOSimConfig`
- A shared AXI MMIO address map rooted at `0x6000_0000`
- A Nexys Video harness binder that exports the MMIO AXI port at top level as `axi4_mmio_0`
- A `GenericRadarShell` scaffold under `generators/chipyard/src/main/scala/radar`
- A standalone smoke test program for MMIO read/write validation
- An architecture SVG summarizing the intended Nexys Video mapping

## Relevant Files

- `fpga/src/main/scala/nexysvideo/Configs.scala`
- `fpga/src/main/scala/nexysvideo/HarnessBinders.scala`
- `generators/chipyard/src/main/scala/DigitalTop.scala`
- `generators/chipyard/src/main/scala/radar/GenericRadarShell.scala`
- `tests/radar-axi-mmio-smoke.c`
- `docs/radar_axi_nexysvideo_arch.svg`

## What Is Verified

The simulation-side smoke test is passing.

Command used:

```bash
PATH=/home/soooarr/chipyard/.conda-env/bin:/home/soooarr/chipyard/.conda-env/riscv-tools/bin:$PATH \
RISCV=/home/soooarr/chipyard/.conda-env/riscv-tools \
make -C sims/verilator CONFIG=RadarAXIMMIOSimConfig \
  BINARY=/home/soooarr/chipyard/tests/radar-axi-mmio-smoke.riscv \
  BREAK_SIM_PREREQ=1 run-binary-fast
```

Observed result:

- `PASS64` at `0x60000000`
- `PASS64` at `0x60001000`
- `PASS64` at `0x60002000`
- `PASS64` at `0x60003000`
- `PASS32` at `0x60000008`
- `PASS32` at `0x60001008`
- `PASS32` at `0x60002008`
- `PASS32` at `0x60003008`
- Final line: `Radar AXI MMIO smoke test PASSED`

Log file:

- `sims/verilator/output/chipyard.harness.TestHarness.RadarAXIMMIOSimConfig/radar-axi-mmio-smoke.log`

There are many DRAMSim alignment warnings during ELF loading, but they do not block execution and the smoke test completes successfully.

## What This Means

At this point we have evidence that:

- the custom MMIO window is present in simulation
- software can reach the reserved radar MMIO address range
- 64-bit and 32-bit accesses within that window behave as expected in the simulation harness

This is a solid checkpoint for the bus export and address map definition.

## What Is Not Finished Yet

The work is not yet at a "full radar platform integration" stage.

The following still remain open:

- No actual Nexys Video board run was performed in this pass
- The current validation is simulation only
- The exported AXI MMIO window is validated, but real downstream radar IP attachment is still a later step
- `GenericRadarShell` is a scaffold and not the same thing as a final radar datapath integration
- The repository state is not cleaned up for publication yet

## Push Readiness

The technical content is close to being publishable, but the repository state is not ready to push as-is.

Reasons:

- There is an unrelated large change in:
  `conda-reqs/conda-lock-reqs/conda-requirements-riscv-tools-linux-64.conda-lock.yml`
- There are Vivado temporary files and journals:
  `fpga/.Xil/`, `fpga/vivado.jou`, `fpga/vivado_*.backup.jou`
- There is a generated bitstream deliverable:
  `fpga/deliverables/v1_rocket_gemmini/NexysVideoHarness.bit`
- One submodule is dirty:
  `toolchains/riscv-tools/riscv-spike-devices`
- The repository is currently in detached `HEAD`
- A dry-run push to `origin` failed because GitHub credentials are not configured in this environment

Dry-run result:

```text
fatal: could not read Username for 'https://github.com': No such device or address
```

## Recommendation Before Push

Create a clean branch and stage only the files that belong to this work.

Likely keep:

- `fpga/src/main/scala/nexysvideo/Configs.scala`
- `fpga/src/main/scala/nexysvideo/HarnessBinders.scala`
- `generators/chipyard/src/main/scala/DigitalTop.scala`
- `generators/chipyard/src/main/scala/radar/GenericRadarShell.scala`
- `tests/radar-axi-mmio-smoke.c`
- `docs/radar_axi_nexysvideo_arch.svg`
- `docs/radar_nexysvideo_progress_2026-03-25.md`

Likely exclude:

- `conda-reqs/conda-lock-reqs/conda-requirements-riscv-tools-linux-64.conda-lock.yml`
- `fpga/.Xil/`
- `fpga/deliverables/`
- `fpga/vivado.jou`
- `fpga/vivado_*.backup.jou`
- submodule dirt unrelated to this feature

## Short Conclusion

Progress is at the "config plus simulation validation" stage, not yet the "board-validated final integration" stage.

Yes, the meaningful source changes can be pushed to GitHub after cleanup.

No, the current workspace should not be pushed directly without:

- isolating the feature files
- removing generated artifacts and unrelated changes
- creating a real branch
- configuring GitHub authentication or pushing to a writable fork
