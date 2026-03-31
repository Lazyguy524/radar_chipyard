# Radar Nexys Video Bring-up Notes

Date: 2026-03-26

## Current Status (2026-03-28)

| Area | Status | Notes |
| --- | --- | --- |
| UART-TSI basic access | PASS | `0x1000` is reachable from `uart_tsi` |
| DDR basic access | PASS | direct `init_write` / `init_read` to `0x80000000` works |
| CPU bring-up | PASS | `hello.riscv` prints `Hello world from core 0, a rocket` |
| DMA CSR smoke | PASS | `radar-axi-mmio-smoke.riscv` completes and prints `PASSED` |
| DMA loopback | FAIL | failure is after `MM2S_LENGTH` write when the MM2S channel should start |
| Current debug bitstream | READY | a newer bitstream now exposes software-readable DMA debug CSR counters |

### Architecture Snapshot

`CPU -> AXI4 MMIO port @ 0x60000000 -> RadarAXIDMA ctrl bridge -> Xilinx AXI DMA CSR`

`CPU/uart_tsi -> DDR @ 0x80000000`

`AXI DMA MM2S/S2MM masters -> MIG -> DDR`

`MM2S stream -> direct loopback -> S2MM stream`

### Current Failure Signature

- Before MM2S starts, DMA registers read back correctly
- S2MM programming sequence looks sane
- MM2S programming also looks sane until `MM2S_LENGTH` is written
- Immediately after `MM2S_LENGTH`, transient MM2S register reads can show `0xa5a5....` values matching TX buffer payload words
- After that transient window, MM2S control registers settle back to sane values, but the channel stays stuck and times out
- RX buffer stays all zero, so loopback never actually completes

### Current Working Theory

- The control-port path is no longer the main blocker; it is usable enough to pass the DMA CSR smoke test
- The remaining blocker is in the MM2S start/run path after the transfer is armed
- Most likely fault domain is now one of:
  - MM2S AXI master read path into MIG
  - stream loopback / S2MM handoff while MM2S is active
  - transient response corruption around MM2S start

### Current Next Step

The latest local source tree adds software-readable debug CSR counters for:

- MM2S `AR` / `R` / `last`
- streamed beats on the internal loopback
- S2MM `AW` / `W` / `B`

That newer debug bitstream has already been rebuilt and tested on board once.
Current result:

- `hello.riscv` still runs
- but direct `uart_tsi +init_read` behavior becomes unreliable on this debug image
- the intended debug CSR window at `0x60000200` did not return sane data in the initial board test

So the debug image is currently an experiment, not yet the new stable baseline.

## Why Raw Serial Output Looks Wrong

The current `RadarAXIMMIONexysVideoConfig` does not expose a normal software
console UART. It uses the board UART as `UART-TSI` transport.

That means:

- `hello.riscv` output should appear in the `uart_tsi` host process
- `screen`, `minicom`, or `picocom` are not the right first-line validation tool
- after any power cycle, DDR contents are lost and the ELF must be loaded again

Also note that `uart_tsi` printing `Connection succeeded` is not a real protocol
handshake. In the current host utility it only means the TTY opened and no stray
byte was observed during a short read.

## Current Software Default

The general `tests/Makefile` defaults remain unchanged for the wider Chipyard
test suite:

- `ARCH=rv64imafdc`
- `ABI=lp64d`

For the current Nexys Video no-FPU bring-up flow, the three binaries below are
now built through a separate freestanding path:

- `hello.riscv`
- `radar-axi-mmio-smoke.riscv`
- `radar-axi-dma-loopback.riscv`

That path uses:

- `BRINGUP_ARCH=rv64imac_zicsr_zifencei`
- `BRINGUP_ABI=lp64`
- a small local HTIF runtime instead of the installed hard-float newlib/libgloss

This avoids the previous failure mode where the bundled toolchain produced or
linked double-float startup/runtime code for a `WithoutFPU` target.

To rebuild the relevant binaries:

```bash
cd /home/soooarr/chipyard/tests
PATH=/home/soooarr/chipyard/.conda-env/riscv-tools/bin:$PATH \
make bringup-binaries
```

## Recommended Bring-up Order

Assume the UART device is `/dev/ttyUSB0`. Replace it with the actual device on
your host.

### 1. Check basic TSI register access without starting the hart

```bash
/home/soooarr/chipyard/.conda-env/riscv-tools/bin/uart_tsi \
  +tty=/dev/ttyUSB0 \
  +no_hart0_msip \
  +init_read=0x1000 \
  none
```

Expected meaning:

- if this works, the UART-TSI path can at least access `boot-address-reg`
- if this hangs, stop and debug serial path, baud rate, or basic FPGA bring-up

### 2. Check DDR reachability

```bash
/home/soooarr/chipyard/.conda-env/riscv-tools/bin/uart_tsi \
  +tty=/dev/ttyUSB0 \
  +no_hart0_msip \
  +init_read=0x80000000 \
  none
```

Expected meaning:

- if `0x1000` works but `0x80000000` hangs, focus on DDR/MIG calibration or DDR path

### 3. Run the smallest real program

```bash
/home/soooarr/chipyard/.conda-env/riscv-tools/bin/uart_tsi \
  +tty=/dev/ttyUSB0 \
  +selfcheck \
  /home/soooarr/chipyard/tests/hello.riscv
```

Expected meaning:

- `Self check success` means the ELF was written to memory and read back correctly
- `Hello world ...` should appear in this same terminal if the CPU is actually running

### 4. Run the MMIO smoke test

```bash
/home/soooarr/chipyard/.conda-env/riscv-tools/bin/uart_tsi \
  +tty=/dev/ttyUSB0 \
  +selfcheck \
  /home/soooarr/chipyard/tests/radar-axi-mmio-smoke.riscv
```

This test is now a DMA CSR smoke test, not a generic scratch-register test.
It should:

- access only 32-bit DMA control registers under `0x60000000`
- read `MM2S_DMASR` / `S2MM_DMASR` repeatedly without hanging
- issue channel reset through `DMACR_RESET`
- observe the reset bit self-clear

Only move on to the loopback test after this test produces the expected CSR
output and exits with `PASSED`.

### 5. Run the DMA loopback test

```bash
/home/soooarr/chipyard/.conda-env/riscv-tools/bin/uart_tsi \
  +tty=/dev/ttyUSB0 \
  +selfcheck \
  /home/soooarr/chipyard/tests/radar-axi-dma-loopback.riscv
```

## LED Interpretation

For the current harness:

- LD0 and LD1 alternating means the harness clock logic is alive
- LD2 reflects `resetPin`
- LD3 reflects `dropped`
- LD4 reflects DDR `init_calib_complete`
- LD5 reflects DMA `ctrlResetN`
- LD6 reflects DMA control request activity
- LD7 reflects DMA control accept or response activity

Practical meaning:

- `LD0/LD1` blinking with `LD4` on means harness clocking is alive and DDR calibration completed
- `LD6`/`LD7` toggling during a `uart_tsi +init_read` or software MMIO access means the DMA CSR path is being exercised
- `LD3` turning on means the UART-TSI frontend reported dropped serial traffic and that result is not a valid MMIO datapoint
