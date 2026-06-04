# Feature21 + QMLP Frequency Limit Investigation Rolling Summary

Date: 2026-06-02

## Current Scope

Investigate why the current 21-feature + QMLP NexysVideo/Chipyard project appears to be practically limited to the 50 MHz configuration, identify the timing bottlenecks, and assess whether they are fixable.

## Important Guardrails

- The worktree is dirty. Existing user/generated changes must not be reverted.
- Existing bitstreams and implementation logs are already archived; do not rerun bitstream unless the archived evidence is insufficient.
- Avoid pasting long Vivado logs into chat. Extract only WNS/TNS, critical path modules, and file paths.

## Existing Archived Results Found

- Deliverable bitstreams:
  - `fpga/deliverables/radar_nexysvideo_bits/2026-04-05_preproc_stable/NexysVideoHarness_preproc_stable_2026-04-01.bit`
  - `fpga/deliverables/radar_nexysvideo_bits/545-qmlp-wordbank-refactor-k7-2026-04-15.bit`
  - `fpga/deliverables/radar_nexysvideo_bits/611-feature21-preproc-chain-2026-04-20.bit`
  - `fpga/deliverables/radar_nexysvideo_bits/646-feature21-v1p3-preproc-qmlp-2026-04-22.bit`
  - `fpga/deliverables/radar_nexysvideo_bits/662-feature21-v1p4a-density-recip-exact-lut-2026-04-26.bit`
- Additional backups exist under `logs/radar_nexysvideo/bit_backups/`, including 50 MHz preproc and QMLP versions.
- Frequency/timing logs found:
  - `logs/radar_nexysvideo/runtime/214-cpu-freq-sweep-summary-2026-04-05.md`
  - `logs/radar_nexysvideo/runtime/215-cpu-freq-sweep-compatible-summary-2026-04-05.md`
  - `logs/radar_nexysvideo/runtime/216-fpga-bitstream-75mhz-2026-04-05.log`
  - `logs/radar_nexysvideo/runtime/217-75mhz-criticalpath-summary-2026-04-05.md`
  - `logs/radar_nexysvideo/runtime/219-fpga-bitstream-65mhz-2026-04-05.log`
  - `logs/radar_nexysvideo/runtime/220-fpga-bitstream-60mhz-2026-04-05.log`
- Feature21/QMLP result logs found:
  - `logs/radar_nexysvideo/runtime/617-feature21-preproc-chain-bitstream-summary-2026-04-20.md`
  - `logs/radar_nexysvideo/runtime/649-feature21-v1p3-bitstream-summary-2026-04-22.md`
  - `logs/radar_nexysvideo/runtime/662-feature21-v1p4a-density-bitstream-and-board-attempt-summary-2026-04-26.md`
  - `logs/radar_nexysvideo/runtime/662-feature21-v1p4a-density-board-validation-summary-2026-04-26.md`
  - `logs/radar_nexysvideo/runtime/661-feature21-v1p4a-density-synth-precheck-summary-2026-04-26.md`

## First Evidence Snapshot

- Historical 75 MHz summary reports setup failure:
  - Overall WNS: `-3.059 ns`
  - Overall TNS: `-599.344 ns`
  - Dominant failing domain: `clk_out1_harnessSysPLLNode`, the DUT clock domain.
  - Reported top bottleneck: front-bus / UART-TSI transport path, not the radar DMA/QMLP datapath.
- Historical 66.666667 MHz attempt failed before bitstream because harness clock reference rounding was incompatible: harness reference printed as 66 MHz while the config required exactly 66.666667 MHz.
- There is an out-of-context synth result for the Feature21 density preprocessor:
  - `logs/radar_nexysvideo/runtime/661-feature21-density-synth-out-2026-04-26/timing_summary.rpt`
  - It was synthesized standalone at 100 MHz and met timing in that OOC context.
  - Worst data path in that OOC report is inside feature-byte computation/selection logic, but still met 100 MHz when standalone.

## Frequency Evidence Snapshot 2

- Latest default 50 MHz integrated Feature21 v1.4a result:
  - Timing report: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/report/timing.txt`
  - Date in report: 2026-04-26
  - WNS: `+0.349 ns`
  - TNS: `0.000 ns`
  - No setup/hold failing endpoints.
  - Worst setup path is `chiptop0/system/fbus/tsi2tl/addr_reg[3]` to `chiptop0/system/fbus/buffer/nodeOut_a_q/...`, not Feature21 or QMLP.
- Historical 60 MHz result:
  - Timing report: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo60MHzConfig/obj/report/timing.txt`
  - `write_bitstream` completed successfully, but the flow failed at the post-bitstream timing check.
  - WNS: `-1.381 ns`
  - TNS: `-21.480 ns`
  - 27 setup failing endpoints, all in `clk_out1_harnessSysPLLNode -> sys_clock`.
  - Worst path is from `dutWrangler/nodeOut_reset_catcher/io_sync_reset_chain/output_chain/sync_0_reg` to the 100 MHz LED blink/status registers (`on_reg`, `counter_reg[*]`).
  - The 60 MHz failure is therefore a harness/reset/status CDC/timing-constraint problem, not a Feature21/QMLP datapath problem.
- Historical 75 MHz result:
  - Timing report: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/report/timing.txt`
  - WNS: `-3.059 ns`
  - TNS: `-599.344 ns`
  - 966 intra-DUT-domain setup failing endpoints in `clk_out1_harnessSysPLLNode`.
  - Worst path is `chiptop0/system/fbus/tsi2tl/addr_reg[4]` to `chiptop0/system/fbus/buffer/nodeOut_a_q/ram_ext/...`.
  - This is a real SoC front-bus / UART-TSI queue path timing problem.
- Historical 55 MHz result:
  - Fails at Vivado clock-wizard IP generation/check, not timing.
  - Requested clocks: 55 / 100 / 200 MHz.
  - Achieved 55 and 100 MHz, but CLKOUT3 achieved 183.333 MHz instead of 200 MHz, so the flow exited.
- Historical 65 MHz result:
  - Fails at Vivado clock-wizard IP generation/check, not timing.
  - CLKOUT1 jitter was `676.125 ps`, above the 300 ps threshold.
- Historical 51.282051 MHz and 66.666667 MHz results:
  - Fail during Chisel elaboration due to `AllClocksFromHarnessClockInstantiator` exact frequency equality checks.
  - The harness reference frequency is integer-truncated (`51` or `66`) while the requested clock names require fractional MHz.

## Current Hypothesis

The project is not limited to 50 MHz by Feature21 or QMLP arithmetic. The current 50 MHz margin is small because the full Chipyard SoC on Artix-7 is already dominated by UART-TSI/front-bus queue paths. The next frequency point failed for a harness CDC/status reset path, and the higher 75 MHz point failed in `fbus/tsi2tl` itself. Feature21/QMLP add resource and routing pressure, but the observed top failures are outside their datapaths.

## Next Evidence To Extract

- WNS/TNS and failure module names from 55/60/65 MHz logs.
- Current source layout for:
  - `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
  - `fpga/src/main/scala/nexysvideo/RadarQMLP.scala`
  - NexysVideo clock/config fragments.
- Whether current feature21 + QMLP integrated bitstreams were built at the default 50 MHz only.

## Checkpoint 2026-06-03

- Confirmed archived/generated implementation artifacts exist; no need to rerun bitstream yet.
- Current default 50 MHz bitstream:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/NexysVideoHarness.bit`
  - mtime `2026-04-26 01:16:22 +0800`, SHA256 `24ed400ed3d3f167472e388aa1765a60481a4b475184338008bf150e0d463ec5`
  - Timing summary: WNS `+0.349 ns`, TNS `0.000 ns`, 0 failing endpoints.
- Archived 60 MHz bitstream:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo60MHzConfig/obj/NexysVideoHarness.bit`
  - mtime `2026-04-05 17:22:25 +0800`, SHA256 `488542737a9c6317aa7d73ae6517e75a2b5c4edec334ca47634eaa6cab70c170`
  - Timing summary: WNS `-1.381 ns`, TNS `-21.480 ns`, 27 failing endpoints.
  - Critical failing group: inter-clock `clk_out1_harnessSysPLLNode -> sys_clock`, not the Feature21/QMLP datapath.
- Archived 75 MHz bitstream:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/NexysVideoHarness.bit`
  - mtime `2026-04-05 16:49:05 +0800`, SHA256 `5de55ad6286f2ed0ace680ad1ca2790621a5d5ec5bc19461b3fc381d05beb57a`
  - Timing summary: WNS `-3.059 ns`, TNS `-599.344 ns`, 967 failing endpoints.
  - Critical failing group: intra-DUT `clk_out1_harnessSysPLLNode`; top source/destination are `fbus/tsi2tl/addr_reg[4]` into `fbus/buffer/nodeOut_a_q` RAM write inputs.

## Checkpoint 2026-06-03 Continued Work

### Additional Evidence Extracted

- 55 MHz archived attempt:
  - Log: `logs/radar_nexysvideo/runtime/214-fpga-bitstream-55mhz-2026-04-05.log`
  - Failure stage: Vivado clock-wizard/IP clock check before implementation timing.
  - Requested clocks: 55 / 100 / 200 MHz.
  - Achieved: 55.0 MHz with 139.932 ps jitter, 100.0 MHz with 123.670 ps jitter, but CLKOUT3 achieved 183.333333 MHz and failed the 198.0-202.0 MHz tolerance.
- 65 MHz archived attempt:
  - Log: `logs/radar_nexysvideo/runtime/219-fpga-bitstream-65mhz-2026-04-05.log`
  - Failure stage: Vivado clock-wizard/IP clock check before implementation timing.
  - Requested clocks: 65 / 100 / 200 MHz.
  - Failed because CLKOUT1 jitter was 676.125 ps, above the 300 ps limit.
- Current source layout checked:
  - `fpga/src/main/scala/nexysvideo/Configs.scala`
  - `fpga/src/main/scala/nexysvideo/Harness.scala`
  - `fpga/src/main/scala/nexysvideo/HarnessBinders.scala`
  - `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
  - `fpga/src/main/scala/nexysvideo/RadarQMLP.scala`
- Key source finding:
  - `WithNexysVideoTweaks`, `WithTinyNexysVideoTweaks`, and `WithRadarNexysVideoTweaks` had `freqMHz`-style parameters or needed them, but their bus/harness frequency fragments were still hard-wired to 50 MHz.
  - `NexysVideoHarness` computed `dutFreqMHz` with integer division/`toInt`, which explains the old fractional-frequency elaboration failures for 51.282051 MHz and 66.666667 MHz.
  - The 100 MHz status LED blink logic was clocked by the board/system clock but reset from the DUT/ResetWrangler domain, matching the historical 60 MHz `clk_out1_harnessSysPLLNode -> sys_clock` failing endpoints.

### Source Changes Made

- `fpga/src/main/scala/nexysvideo/Configs.scala`
  - Parameterized `WithNexysVideoTweaks`, `WithTinyNexysVideoTweaks`, and `WithRadarNexysVideoTweaks` with `freqMHz: Double`.
  - Routed `freqMHz` into `WithHarnessBinderClockFreqMHz` and the memory/front/system/periphery/control bus frequency fragments.
  - Added reusable `RadarAXIMMIONexysVideoFreqConfig(freqMHz: Double = 50.0)`.
  - Reintroduced concrete sweep configs:
    - `RadarAXIMMIONexysVideo51p282MHzConfig`
    - `RadarAXIMMIONexysVideo55MHzConfig`
    - `RadarAXIMMIONexysVideo60MHzConfig`
    - `RadarAXIMMIONexysVideo65MHzConfig`
    - `RadarAXIMMIONexysVideo66p667MHzConfig`
    - `RadarAXIMMIONexysVideo75MHzConfig`
- `fpga/src/main/scala/nexysvideo/Harness.scala`
  - Changed `dutFreqMHz` from integer MHz to `Double` MHz:
    - `dp(SystemBusKey).dtsFrequency.get.toDouble / 1.0e6`
  - Added a 100 MHz local reset synchronizer for status LEDs:
    - `ResetCatchAndSync(clk_100mhz, clk_100mhz_reset, "status_led_reset")`
  - The status LED `counter`/`on` registers now reset from the board-clock-domain synchronized reset, not from `dutClock.in.head._1.reset`.

### Validation Run

- Environment activation used for validation:
  - `source /home/soooarr/anaconda3/etc/profile.d/conda.sh && conda activate /home/soooarr/chipyard/.conda-env`
- Formatting/static patch check:
  - `git diff --check -- fpga/src/main/scala/nexysvideo/Harness.scala fpga/src/main/scala/nexysvideo/Configs.scala`
  - Result: passed.
- FIRRTL/elaboration checks:
  - 50 MHz: `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideoConfig firrtl`
    - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/firrtl-50mhz-2026-06-03.log`
    - Result: passed.
    - Printed frequencies: `NexysVideo FPGA Base Clock Freq: 50.0 MHz`, `Harness binder clock is 50.0`.
  - 60 MHz: `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo60MHzConfig firrtl`
    - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/firrtl-60mhz-2026-06-03.log`
    - Result: passed.
    - Printed frequencies: `NexysVideo FPGA Base Clock Freq: 60.0 MHz`, `Harness binder clock is 60.0`.
  - 51.282051 MHz: `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo51p282MHzConfig firrtl`
    - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/firrtl-51p282mhz-2026-06-03.log`
    - Result: passed.
    - Printed frequencies: `NexysVideo FPGA Base Clock Freq: 51.282051 MHz`, `Harness binder clock is 51.282051`.
    - Generated PLL Tcl requests `CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {51.282051}`.
  - 66.666667 MHz: `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo66p667MHzConfig firrtl`
    - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/firrtl-66p667mhz-2026-06-03.log`
    - Result: passed.
    - Printed frequencies: `NexysVideo FPGA Base Clock Freq: 66.666667 MHz`, `Harness binder clock is 66.666667`.
    - Generated PLL Tcl requests `CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {66.666667}`.
- Verilog/lowering check:
  - 60 MHz: `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo60MHzConfig verilog`
    - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/verilog-60mhz-2026-06-03.log`
    - Result: passed through firtool, uniquify, memory split, and macrocompiler.
    - Existing Makefile behavior still prints an ignored `cp: missing destination file operand` when `SIM_FILE_REQS` is empty; make continues and exits successfully.
  - Generated Verilog confirms the status LED reset change:
    - `statusLedReset_status_led_reset` is clocked by `_sys_clock_ibufg_O`.
    - Its reset input is `~_reset_ibuf_O`, i.e. board reset synchronized locally to the 100 MHz status LED clock.
    - The LED `counter` register resets from `_statusLedReset_status_led_reset_io_sync_reset`, not from `dutWrangler`/DUT-domain reset.

### Current Conclusion

- Two low-risk infrastructure causes were fixed:
  - Frequency sweep configs are now reproducible instead of silently stuck at 50 MHz.
  - Fractional MHz sweep points now elaborate because the harness reference frequency remains a `Double`.
  - The known 60 MHz status LED reset CDC/timing path is removed at RTL/Verilog level.
- This still does not prove a 60 MHz bitstream closes timing; no new bitstream was run by design.
- The old 75 MHz conclusion remains unchanged: after removing the harness/status path, the next likely integrated bottleneck is the full SoC `fbus/tsi2tl` path, not Feature21/QMLP arithmetic.

### Next Most Reasonable Action

- If implementation time is acceptable, run one targeted 60 MHz bitstream after this source fix to check whether timing now closes or whether the bottleneck moves to `fbus/tsi2tl`.
- If avoiding bitstream remains mandatory, inspect generated 60 MHz constraints/clock groups and compare the 60 MHz generated Verilog against the old timing source/destination names to make a no-build handoff package.
- Do not spend time optimizing QMLP/Feature21 datapaths until a post-fix integrated timing report shows them in the top failing setup paths.

## Checkpoint 2026-06-03 UART-TSI / TSIToTileLink Path

### What UART-TSI Does In This Design

- NexysVideo configs intentionally disable the normal SiFive UART and use the board USB-UART as the UART-TSI transport:
  - `fpga/src/main/scala/nexysvideo/Configs.scala`
  - `WithNexysVideoUARTTSI`
  - `testchipip.tsi.WithUARTTSIClient`
  - `chipyard.config.WithNoUART`
- The host-side utility is `generators/testchipip/uart_tsi/uart_tsi`.
  - Board scripts call it with `+tty`, `+baudrate`, optional `+selfcheck`, and an ELF/binary path.
  - `scripts/run_nexysvideo_uart_tsi.sh` defaults to `/dev/ttyUSB0`, `921600`, and `tests/radar-axi-dma-regression.riscv`.
  - Archived board logs show Feature21 tests running through `uart_tsi +tty=/dev/ttyUSB0 +baudrate=115200 +selfcheck ...`, then `Starting UART-based TSI` and `Done, shutting down, flushing UART`.
  - `testchip_uart_tsi.cc` uses the base `testchip_tsi_t` load/read/write path; `+selfcheck` reads loaded chunks back through the same TSI path.
- Functional role: UART-TSI is the board bring-up/test/debug memory-transaction path. It can load code/data and issue direct reads/writes over TileLink. It is not the QMLP accelerator datapath.

### Where It Is Instantiated And Connected

- `DigitalTop` mixes in `testchipip.tsi.CanHavePeripheryUARTTSI`.
- `UARTTSIClientParams` defaults `tlbus` to `FBUS`.
- `CanHavePeripheryUARTTSI` does:
  - `val tlbus = locateTLBusWrapper(params.tlbus)`
  - `val tsi2tl = tlbus { LazyModule(new TSIToTileLink) }`
  - `tlbus.coupleFrom("uart_tsi") { _ := tsi2tl.node }`
  - In the same bus clock domain it instantiates `UARTToSerial` and `SerialWidthAdapter(8, TSI.WIDTH)`.
- NexysVideo harness binder only wires the punched-through UART-TSI IO to the board UART overlay:
  - `nexysvideoth.io_uart_bb.bundle <> port.io.uart`
- Generated Verilog confirms the integrated path in `FrontBus.sv`:
  - `UARTToSerial` <-> `SerialWidthAdapter` <-> `TSIToTileLink tsi2tl`.
  - `tsi2tl.auto_out_a_*` feeds the fbus xbar input.
  - fbus xbar output feeds `TLBuffer ... buffer`.
  - The buffer contains `Queue2_TLBundleA... nodeOut_a_q`, whose inferred RAM is the timing endpoint seen in reports.

### Why This Path Has Timing Pressure

- `TSIToTileLink.scala` computes TL A-channel request fields combinationally from the TSI state/registers:
  - `nextAddr`, `addr_size`, `len_size`, `raw_size`, `rsize`, `pow2size`, `byteAddr`
  - `edge.Put(...)` / `edge.Get(...)`
  - `mem.a.bits := Mux(state === s_write_data, put_acquire, get_acquire)`
- Generated `TSIToTileLink.sv` expands this into a long combinational network:
  - 64/66-bit add/sub/compare for address and length sizing.
  - a large `PopCount(raw_size) === 1` tree for `pow2size`.
  - mask/address/size muxing into TL A-channel fields.
- The critical report path is from `tsi2tl/addr_reg[*]` through that request-building logic and fbus routing into the downstream `TLBuffer` A-channel queue RAM input (`fbus/buffer/nodeOut_a_q/ram_ext/...`).
- UART RX/TX itself is not the observed critical path; it is slow serial protocol logic feeding queues/width adapters. The failing path is the synchronous TileLink request-generation and front-bus buffering side.

### Frequency Interpretation

- 50 MHz integrated Feature21/QMLP bitstream meets timing but worst setup path is already `fbus/tsi2tl -> fbus/buffer/nodeOut_a_q`:
  - WNS `+0.349 ns`
  - path delay `19.226 ns`
  - 34 logic levels
- Historical 60 MHz bitstream failed overall because of the old DUT-reset-to-100MHz-status-LED path:
  - WNS `-1.381 ns`
  - inter-clock group `clk_out1_harnessSysPLLNode -> sys_clock`
  - source `dutWrangler/nodeOut_reset_catcher/.../sync_0_reg`
  - destinations `on_reg` / `counter_reg[*]`
  - This was not a UART-TSI failure, but the DUT main clock group was already very close to the edge: `clk_out1_harnessSysPLLNode` WNS `+0.011 ns`.
- Historical 75 MHz bitstream fails directly in the UART-TSI/front-bus path:
  - WNS `-3.059 ns`, TNS about `-599 ns`
  - source `chiptop0/system/fbus/tsi2tl/addr_reg[4]`
  - destination `chiptop0/system/fbus/buffer/nodeOut_a_q/ram_ext/...`
  - path delay `16.087 ns`
  - 31 logic levels
- Conclusion: UART-TSI affects the frequency-limit judgment because it is part of the full SoC in the same DUT/fbus clock domain. It can be the worst integrated timing path even though QMLP itself is not using it for compute.

### Optimization Directions To Investigate Next

- Do not start inside QMLP/Feature21 arithmetic for this issue.
- Most relevant places:
  - `generators/testchipip/src/main/scala/tsi/TSIToTileLink.scala`
    - consider registering/pipelining TL A-channel request fields before they enter the fbus/xbar/buffer.
    - consider simplifying size/mask calculation if the board use case can restrict TSI accesses to aligned full-beat transactions.
  - `generators/testchipip/src/main/scala/tsi/PeripheryUARTTSI.scala`
    - consider adding a `TLBuffer` or different coupling structure immediately at the `tsi2tl.node` boundary, if it cuts the long request generation to fbus buffer path.
    - consider moving UART-TSI to a lower-frequency bus only if the resulting crossings and address reachability remain correct.
  - NexysVideo/SoC config fragments:
    - consider making UART-TSI optional or replacing it with a less timing-critical bring-up path for high-frequency builds.
    - consider separate high-frequency performance configs that remove bring-up/debug transports not needed on the final bitstream.
- Harness-level work is still relevant for the 60 MHz status/reset issue, but the `tsi2tl` path itself is inside the SoC/front-bus logic, not the outer board harness wiring.

## Checkpoint 2026-06-03 TSI Continuation Stage 1

- Restarted this investigation from the rolling summary and current source only; no old thread context was assumed.
- Rechecked the main UART-TSI source entry points:
  - `fpga/src/main/scala/nexysvideo/Configs.scala`
  - `fpga/src/main/scala/nexysvideo/HarnessBinders.scala`
  - `generators/chipyard/src/main/scala/DigitalTop.scala`
  - `generators/testchipip/src/main/scala/tsi/Configs.scala`
  - `generators/testchipip/src/main/scala/tsi/PeripheryUARTTSI.scala`
  - `generators/testchipip/src/main/scala/tsi/TSIToTileLink.scala`
- The current-source reading still supports the prior conclusion: UART-TSI is a bring-up/debug TileLink master attached through FBUS, and the observed frequency pressure is in the SoC front-bus/TSI frontend path rather than in QMLP arithmetic.
- Next local check: inspect whether `TSIToTileLink` can legally add a register stage on TL A-channel request fields, and whether `PeripheryUARTTSI` can add buffering at the `tsi2tl.node`/FBUS coupling boundary without changing board-level UART wiring.

## Checkpoint 2026-06-03 TSI Continuation Stage 2

### Current File Evidence

- `DigitalTop` always has the optional UART-TSI mixin available through `testchipip.tsi.CanHavePeripheryUARTTSI`; the NexysVideo configs enable it with `testchipip.tsi.WithUARTTSIClient` and disable the normal SiFive UART with `WithNoUART`.
- `UARTTSIClientParams` still defaults to `tlbus = FBUS`, so this transport is a TileLink client on the front bus unless a config overrides it.
- `PeripheryUARTTSI.scala` currently connects the client directly:
  - `val tsi2tl = tlbus { LazyModule(new TSIToTileLink) }`
  - `tlbus.coupleFrom("uart_tsi") { _ := tsi2tl.node }`
  - `UARTToSerial` and `SerialWidthAdapter` live in the same `tlbus` clock-domain wrapper and feed `tsi2tl.module.io.tsi`.
- `TSIToTileLink.scala` still drives `mem.a` directly from combinational request generation:
  - address/length sizing: `nextAddr`, `addr_size`, `len_size`, `raw_size`, `rsize`
  - read sub-beat alignment: `pow2size`, `byteAddr`
  - TileLink request construction: `edge.Put`, `edge.Get`
  - final drive: `mem.a.valid := state.isOneOf(s_write_data, s_read_req)` and `mem.a.bits := Mux(...)`.
- Generated `TSIToTileLink.sv` confirms the critical logic is real hardware, not just source-level suspicion:
  - `raw_size` is a 66-bit compare/mux result.
  - `pow2size` expands into a large popcount tree over `raw_size[65:0]`.
  - `auto_out_a_bits_size/address/mask/data` are assigned directly from those combinational values.
- Generated `FrontBus.sv` confirms topology:
  - `TSIToTileLink tsi2tl` drives the fbus xbar input.
  - fbus xbar output drives a `TLBuffer ... buffer`.
  - the timing endpoint is that downstream buffer's A-channel queue RAM (`nodeOut_a_q/ram_ext/...`).

### Timing Evidence Rechecked

- 50 MHz integrated current report:
  - Intra-DUT `clk_out1_harnessSysPLLNode` WNS `+0.349 ns`.
  - Worst path: `chiptop0/system/fbus/tsi2tl/addr_reg[3]` to `chiptop0/system/fbus/buffer/nodeOut_a_q/...`.
  - Data path delay `19.226 ns`, 34 logic levels.
- Historical 60 MHz report:
  - Overall failure was still the old `clk_out1_harnessSysPLLNode -> sys_clock` status/reset path.
  - But the intra-DUT clock group had only `+0.011 ns` WNS.
  - Its worst path was already `fbus/tsi2tl/addr_reg[4]_replica` to `fbus/buffer/nodeOut_a_q/...`, with `16.325 ns` data delay and 29 logic levels.
- Historical 75 MHz report:
  - Intra-DUT `clk_out1_harnessSysPLLNode` WNS `-3.059 ns`, TNS about `-599 ns`.
  - Worst path was directly `fbus/tsi2tl/addr_reg[4]` to `fbus/buffer/nodeOut_a_q/...`, with `16.087 ns` data delay and 31 logic levels.

### Optimization Judgment

- The first optimization experiment should be at the `PeripheryUARTTSI.scala` coupling boundary, not in QMLP:
  - change the direct `tlbus.coupleFrom("uart_tsi") { _ := tsi2tl.node }` path into a buffered path such as `_ := TLBuffer(BufferParams.pipe) := tsi2tl.node` or `_ := TLBuffer() := tsi2tl.node`.
  - This matches existing local patterns in `GenericRadarShell.scala` and `PeripheryTLSerial.scala`, where front-bus clients are coupled through `TLBuffer()`.
  - Expected effect: cut the long `tsi2tl combinational request -> fbus xbar -> downstream fbus buffer queue RAM` path into two shorter registered paths.
- A stronger second experiment is inside `TSIToTileLink.scala`:
  - replace direct `mem.a.valid/bits` driving with an internal one-entry A-channel queue/register.
  - use the queue enqueue-side `ready` for the `s_read_req` and `s_write_data` state transitions, instead of raw `mem.a.ready`.
  - This is likely legal because TSI issues only one outstanding request and waits for D-channel response before issuing the next request, but it is more invasive than an external TLBuffer and needs FIRRTL/Verilog plus board/TSI selfcheck validation.
- Moving UART-TSI off FBUS is a larger system change:
  - it may require clock crossings and address reachability checks.
  - It should be considered only after the local buffer/pipeline experiments fail to recover enough slack.

## Checkpoint 2026-06-03 TSI Buffer Experiment Stage 0 Backup

- Created backup directory:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/tsi-buffer-experiment-2026-06-03/`
- Backed up files before changing RTL/generator code:
  - `PeripheryUARTTSI.scala.before`
  - `TSIToTileLink.scala.before`
  - `TestchipTSIConfigs.scala.before`
  - `rolling_summary.md.before`
- Saved pre-experiment context:
  - `pre-git-status-short.txt`
  - `pre-target-tsi-diff.patch`
- Backup SHA256:
  - `PeripheryUARTTSI.scala.before`: `738f9ae3fe16a2e427e6666383ea231db33aed54612ebfde46f94aef1888deb1`
  - `TSIToTileLink.scala.before`: `ebf0628aa3fd0e6cd96ca9a7d08844a516174c1b5b0be805de7bf1a4fc15eb81`
  - `TestchipTSIConfigs.scala.before`: `f38f26ba6ed322b7d8e1fe141b4a76cb74ac55e717c118e6b54edb4c3a543360`
  - `rolling_summary.md.before`: `1177e1dd50d018f69a08c0dd51777bf4f1f80918f02e8062d5f63398563589ca`
- Scope decision for the first experiment:
  - Do not touch QMLP or Feature21 datapath code.
  - Try the low-intrusion UART-TSI/FBUS boundary buffer in `PeripheryUARTTSI.scala` first.

## Checkpoint 2026-06-03 TSI Buffer Experiment Stage 1 Code Change

- Modified only `generators/testchipip/src/main/scala/tsi/PeripheryUARTTSI.scala`.
- Added import:
  - `freechips.rocketchip.tilelink.TLBuffer`
- Changed the UART-TSI client coupling from direct FBUS attachment:
  - `tlbus.coupleFrom("uart_tsi") { _ := tsi2tl.node }`
- To a one-entry piped TLBuffer boundary:
  - `tlbus.coupleFrom("uart_tsi") { _ := TLBuffer(BufferParams.pipe) := tsi2tl.node }`
- Rationale:
  - This should register the TileLink A/D boundary between `TSIToTileLink` and the fbus xbar/downstream fbus buffer.
  - It is lower-risk than changing the `TSIToTileLink` request state machine.
  - It follows existing local patterns where front-bus clients are attached through `TLBuffer`.
- Saved experiment diff:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/tsi-buffer-experiment-2026-06-03/post-periphery-uarttsi-buffer.diff`
- Note:
  - `generators/testchipip` is tracked as its own Git repository/submodule; root `git diff` does not show this file, but `git -C generators/testchipip diff` does.

## Checkpoint 2026-06-03 TSI Buffer Experiment Stage 2 Validation

- Formatting/static diff check:
  - `git diff --check -- generators/testchipip/src/main/scala/tsi/PeripheryUARTTSI.scala docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md`
  - Result: passed.
- 60 MHz FIRRTL/elaboration:
  - Command: `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo60MHzConfig firrtl`
  - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/tsi-buffer-experiment-2026-06-03/firrtl-60mhz-tsi-buffer-2026-06-03.log`
  - Result: passed.
  - Printed frequencies: `NexysVideo FPGA Base Clock Freq: 60.0 MHz`, `Harness binder clock is 60.0`.
- 60 MHz Verilog/lowering:
  - Command: `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo60MHzConfig verilog`
  - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/tsi-buffer-experiment-2026-06-03/verilog-60mhz-tsi-buffer-2026-06-03.log`
  - Result: passed through firtool, uniquify, memory split, and macrocompiler.
  - Existing Makefile behavior still prints an ignored `cp: missing destination file operand` when `SIM_FILE_REQS` is empty.
- Generated SV evidence:
  - `FrontBus.sv` now has `TLInterconnectCoupler_fbus_from_uart_tsi`.
  - `TSIToTileLink tsi2tl` now drives `coupler_from_uart_tsi` buffer-side signals, not the fbus xbar input directly.
  - The coupler output drives the fbus xbar input.
  - Generated files include `TLBuffer_a37d64s1k2z4u.sv` and `Queue1_TLBundleA_a37d64s1k2z4u.sv`.
  - `Queue1_TLBundleA_a37d64s1k2z4u.sv` contains a registered `ram` and `full` bit, confirming a real one-entry A-channel register stage.
- Current interpretation:
  - The low-intrusion FBUS boundary buffer is syntactically and structurally valid.
  - It should cut the old `tsi2tl request logic -> fbus xbar -> downstream fbus buffer queue RAM` timing path.
  - Actual WNS/TNS impact still requires implementation timing.

### Next Action

- Run one targeted 60 MHz bitstream with this TSI buffer experiment to see whether:
  - the old status/reset failure remains removed,
  - the `tsi2tl -> fbus/buffer` path improves,
  - or a new non-QMLP path becomes the top limiter.

## Checkpoint 2026-06-03 TSI Buffer Experiment Stage 3 Final 60 MHz Timing

- User-observed top-level `make` return code was `2`, matching the expected timing-check failure.
- The captured log shows the inner Vivado Tcl timing gate failed with `exit 1`, then the fpga make target reported `Error 1`:
  - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/tsi-buffer-experiment-2026-06-03/bitstream-60mhz-tsi-buffer-vivado2022p2-2026-06-03.log`
  - Timing gate line: `Failed to meet timing by -1.578`
- Bitstream was written before the timing gate failed:
  - Bitstream: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo60MHzConfig/obj/NexysVideoHarness.bit`
  - mtime: `2026-06-03 22:47:57 +0800`
  - size: `9730766`
  - SHA256: `12aa0bfaca61698a18f8de7c209250d5e274d8d555e31c64acae1e00fdd6f15b`
  - Log evidence: `write_bitstream completed successfully` and `Bitgen Completed Successfully`.
- Final timing report:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo60MHzConfig/obj/report/timing.txt`
  - mtime: `2026-06-03 22:48:35 +0800`
  - size: `3466088`
  - SHA256: `ab5572cb533b6cf35aac89c973b3f0d00c7a7824543272cc1a712823f9ba2ca9`
- Final design timing:
  - WNS: `-1.578 ns`
  - TNS: `-276.127 ns`
  - Failing endpoints: `293`
  - Hold is clean: WHS `+0.029 ns`, THS `0.000 ns`
  - Failing group: intra-DUT `clk_out1_harnessSysPLLNode`, not `sys_clock` and not the old inter-clock status LED path.
- Intra-clock summary:
  - `sys_clock`: WNS `+5.957 ns`, 0 failing endpoints.
  - `clk_out1_harnessSysPLLNode`: WNS `-1.578 ns`, TNS `-276.127 ns`, 293 failing endpoints.
- Top reported setup paths now mix QMLP/Feature21 and UART-TSI:
  - Worst path:
    - `radarDMA/qmlp/outIdx_reg[1]_replica` to `radarDMA/qmlp/accReg_reg[27]`
    - Slack `-1.578 ns`
    - Data path delay `18.597 ns`
    - Logic levels `27`
    - Module attribution: integrated QMLP accumulator/index path under `radarDMA/qmlp`.
  - Second path:
    - `radarDMA/feature21/featureQ8p8Reg_reg[0]` to `radarDMA/feature21/featureByteRegs_11_reg[1]`
    - Slack `-1.530 ns`
    - Data path delay `17.908 ns`
    - Logic levels `37`
    - Module attribution: Feature21 byte extraction/quantization path under `radarDMA/feature21`.
  - First UART-TSI path after adding the boundary buffer:
    - `chiptop0/system/fbus/tsi2tl/addr_reg[5]` to `chiptop0/system/fbus/coupler_from_uart_tsi/buffer/nodeOut_a_q/ram_reg[51]`
    - Slack `-1.508 ns`
    - Data path delay `18.055 ns`
    - Logic levels `33`
    - Module attribution: `TSIToTileLink` address/request generation into the newly inserted `coupler_from_uart_tsi` TLBuffer.
- Interpretation:
  - The old 60 MHz `clk_out1_harnessSysPLLNode -> sys_clock` status/reset failure is no longer the top failure; `sys_clock` is clean.
  - The UART-TSI boundary buffer structurally changed the endpoint from the global fbus downstream buffer to `coupler_from_uart_tsi/buffer`, which confirms the experiment affected the intended path.
  - The buffer did not make 60 MHz close. It also did not remove the TSI frontend as a timing concern; TSI remains within about 70 ps of the worst path.
  - After this experiment, the frequency limit is no longer explainable by UART-TSI alone. The integrated QMLP and Feature21 datapaths are now co-leading the 60 MHz failure, with the buffered TSI path still close behind.
  - This does not invalidate the earlier 75 MHz conclusion: the unbuffered historical 75 MHz result was dominated by `fbus/tsi2tl`. It means that once the obvious harness reset issue and one TSI boundary issue are addressed, 60 MHz exposes several near-equal integrated paths.

### Updated Next Action

- For the specific UART-TSI question:
  - Keep the `PeripheryUARTTSI.scala` boundary-buffer experiment as evidence, but do not assume it is enough.
  - If still optimizing TSI, the next relevant experiment is an internal registered A-channel request stage in `TSIToTileLink.scala`, because `addr_reg -> coupler_from_uart_tsi/buffer/nodeOut_a_q` still has 33 logic levels and negative slack.
- For the practical 60 MHz closure question:
  - The next highest-yield investigation is now broader than TSI: inspect/pipeline `radarDMA/qmlp` accumulator/index paths and `radarDMA/feature21` feature byte/quantization paths, while also keeping the TSI request-generation path on the watch list.
  - Do not claim QMLP is innocent for this latest 60 MHz build; that was true for the earlier 50 MHz/75 MHz evidence focus, but the post-buffer 60 MHz report now shows QMLP and Feature21 among the top failing paths.

## Checkpoint 2026-06-03 Post-Buffer Source Mapping Stage 4

### QMLP Worst Path Mapping

- Latest timing source/destination:
  - `radarDMA/qmlp/outIdx_reg[1]_replica` to `radarDMA/qmlp/accReg_reg[27]`
  - Slack `-1.578 ns`, data path `18.597 ns`, 27 logic levels.
- Source evidence:
  - `RadarQMLPAsyncRom` is an asynchronous distributed ROM:
    - `(* rom_style = "distributed" *) reg ... Memory`
    - `assign data = Memory[addr]`
  - QMLP weight/bias ROM addresses depend directly on `outIdx`:
    - `l1WeightAddr = outIdx * l1WeightWordsPerRow + weightWordIndex`
    - `l2WeightAddr = outIdx(4, 0) * l2WeightWordsPerRow + weightWordIndex`
    - `l3WeightAddr = outIdx(0) * l3WeightWordsPerRow + weightWordIndex`
  - MAC states update `accReg` in the same cycle:
    - `sL1Mac`: `nextAcc := accReg + l1PartialSum`
    - `sL2Mac`: `nextAcc := accReg + l2PartialSum`
    - `sL3Mac`: `nextAcc := accReg + l3PartialSum`
  - Generated SV confirms the single-cycle path:
    - `RadarQMLPL1WeightRom.sv` uses `assign data = Memory[addr]`.
    - `RadarAXISQMLP.sv` wires `outIdx` into ROM address expressions and then updates `accReg` from partial sums.
- Interpretation:
  - The worst QMLP path is likely `outIdx -> async weight ROM address/data -> lane multiply/sum -> accReg`.
  - This is a structural timing issue in the integrated QMLP pipeline, not merely router noise.
- Candidate optimization:
  - Add a MAC-prep/read stage per layer that registers the selected weight word, bias word, and possibly the selected activation bytes before the MAC state.
  - Keep arithmetic results unchanged; accept extra cycles per tile/output.
  - A more aggressive alternative is replacing the async distributed ROMs with synchronous ROMs, but that requires state-machine changes anyway.

### Feature21 Path Mapping

- Latest timing source/destination:
  - `radarDMA/feature21/featureQ8p8Reg_reg[0]` to `radarDMA/feature21/featureByteRegs_11_reg[1]`
  - Slack `-1.530 ns`, data path `17.908 ns`, 37 logic levels.
- Source evidence:
  - `sFeatureSelect` already registers feature selection into `featureQ8p8Reg`, `featureRawReg`, and `featureDensityReg`.
  - `sFeatureQuant` still does quantization and byte-array write in one cycle:
    - `selectedFeatureByte = Mux(featureDensityReg, densityFeatureReg, Mux(featureRawReg, quantRaw(actualPoints), quantQ8p8(featureQ8p8Reg)))`
    - `featureByteRegs(featureIdx) := selectedFeatureByte`
  - `quantQ8p8` contains constant multiply, banker's rounding, clamp, and then the indexed write fanout.
  - Generated `RadarAXISFeature21Preprocessor.sv` expands this into per-byte update muxes for `featureByteRegs_0..31`, confirming the long writeback network.
- Interpretation:
  - The Feature21 path is the quantize/round/clamp/writeback stage, not the earlier accumulation or density-area stage.
  - The existing select/quant split helped, but one more split is needed at 60 MHz.
- Candidate optimization:
  - Split `sFeatureQuant` into at least two stages:
    - quant-multiply/product register,
    - round/clamp/pending-byte register,
    - store `featureByteRegs(featureIdx)` and advance `featureIdx`.
  - This should preserve output bytes while adding cycles to feature generation.

### Buffered UART-TSI Path Mapping

- Latest timing source/destination:
  - `chiptop0/system/fbus/tsi2tl/addr_reg[5]` to `chiptop0/system/fbus/coupler_from_uart_tsi/buffer/nodeOut_a_q/ram_reg[51]`
  - Slack `-1.508 ns`, data path `18.055 ns`, 33 logic levels.
- Source evidence:
  - `PeripheryUARTTSI.scala` now inserts `TLBuffer(BufferParams.pipe)` at the `uart_tsi` FBUS coupling boundary.
  - `TSIToTileLink.scala` still generates TL A-channel request fields directly from `addr`, `len`, `raw_size`, `pow2size`, `edge.Get`, and `edge.Put`.
  - Generated `TSIToTileLink.sv` still contains a large `raw_size` compare/mux and `pow2size` popcount tree before A-channel fields.
- Interpretation:
  - The boundary buffer changed the endpoint and confirms the experiment acted on the intended path.
  - It did not remove the internal request-generation pressure inside `TSIToTileLink`.
- Candidate optimization:
  - Add an internal one-entry registered A-channel request stage in `TSIToTileLink`.
  - State transitions for `s_read_req` and `s_write_data` should wait for enqueue acceptance, then the queue/register should drive `mem.a`.
  - This needs UART-TSI selfcheck/ELF-load validation because it touches the bring-up transport.

### Validation Entrypoints Found

- Existing test binaries/sources can protect functional changes:
  - `tests/radar-axi-dma-feature21.c`
  - `tests/radar-axi-dma-feature21-golden.c`
  - `tests/radar-axi-dma-qmlp.c`
  - `tests/radar-axi-dma-qmlp-validation.c`
  - `tests/radar-axi-dma-qmlp-chain-validation.c`
  - `tests/radar-axi-dma-regression.c`
- Board scripts use UART-TSI, so any `TSIToTileLink` change must still pass `uart_tsi +selfcheck` and at least one ELF-load/run path.

### Stage 4 Triage

- If the immediate goal is to explain UART-TSI's role and remove it as a confounder:
  - Next code experiment should be internal A-channel pipelining in `TSIToTileLink.scala`.
- If the immediate goal is practical 60 MHz closure:
  - UART-TSI alone is no longer enough.
  - First address QMLP async-ROM/MAC staging because it is the current worst path.
  - Then split Feature21 quant/writeback.
  - Keep the buffered TSI path on the list because it is still only about `0.070 ns` behind the worst path.
