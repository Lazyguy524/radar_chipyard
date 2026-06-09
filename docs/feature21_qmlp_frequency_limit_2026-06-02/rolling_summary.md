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

## Checkpoint 2026-06-04 Fresh Continuation / QMLP Stage 0

- Restarted from this rolling summary and current files only; no old thread context was used.
- Current evidence files for this phase:
  - Rolling context: `docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md`
  - Latest post-buffer 60 MHz timing: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo60MHzConfig/obj/report/timing.txt`
  - Latest post-buffer bitstream log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/tsi-buffer-experiment-2026-06-03/bitstream-60mhz-tsi-buffer-vivado2022p2-2026-06-03.log`
  - QMLP source: `fpga/src/main/scala/nexysvideo/RadarQMLP.scala`
  - Feature21 source: `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
- Current timing state from the latest 60 MHz implementation:
  - Overall setup still fails: WNS `-1.578 ns`, TNS `-276.127 ns`, 293 failing endpoints.
  - `sys_clock` is clean; failures are intra-DUT `clk_out1_harnessSysPLLNode`.
  - Top three observed classes are QMLP, Feature21, and buffered UART-TSI, in that order.
- QMLP source/timing mapping rechecked:
  - `RadarQMLPAsyncRom` remains asynchronous distributed ROM with `assign data = Memory[addr]`.
  - `outIdx/inIdx` drive weight ROM addresses combinationally.
  - MAC states consume ROM data and update `accReg` in the same cycle.
  - The timing report shows `outIdx_reg[1]_replica -> l1WeightRom -> partial-sum/add tree -> accReg_reg[27]`, with 27 logic levels.
- Next experiment:
  - Add a conservative per-tile MAC prep stage in `RadarQMLP.scala`.
  - Register selected activation lanes and weight lanes before the MAC add.
  - Leave arithmetic semantics unchanged and accept extra cycles per tile.
- Backup directory:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/qmlp-staging-experiment-2026-06-04/`

## Checkpoint 2026-06-04 QMLP Async-ROM/MAC Staging Stage 1

- Modified `fpga/src/main/scala/nexysvideo/RadarQMLP.scala`.
- Added one MAC prep stage per layer:
  - `sL1Load -> sL1Prep -> sL1Mac`
  - `sL2Load -> sL2Prep -> sL2Mac`
  - `sL3Load -> sL3Prep -> sL3Mac`
- Added staging registers:
  - `biasStageReg`
  - `macDataRegs`
  - `macWeightRegs`
- Behavior intent:
  - Keep async ROMs unchanged for now.
  - Keep arithmetic and output values unchanged.
  - Register selected activation lanes and weight lanes before the MAC add.
  - Accept one extra cycle per MAC tile so the old `outIdx/inIdx -> async ROM -> multiply/sum -> accReg` path is cut.
- Validation:
  - `git diff --check -- fpga/src/main/scala/nexysvideo/RadarQMLP.scala docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md` passed.
  - `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo60MHzConfig verilog` passed.
  - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/qmlp-staging-experiment-2026-06-04/verilog-60mhz-qmlp-staging-2026-06-04.log`
  - Existing Makefile behavior still prints the ignored empty-`SIM_FILE_REQS` `cp: missing destination file operand` message.
- Generated SV evidence:
  - `RadarAXISQMLP.sv` contains real registers `macDataRegs_0..3`, `macWeightRegs_0..3`, and `biasStageReg`.
  - In prep states, async ROM data such as `_l1WeightRom_data` loads `macWeightRegs_*`.
  - In MAC states, `accReg` is updated from `macDataRegs_* * macWeightRegs_*` through `macPartialSum`, not directly from ROM outputs.
- Current interpretation:
  - The QMLP structural issue identified by the latest 60 MHz timing report has been addressed at RTL/generator level.
  - Actual slack impact still requires implementation timing.
  - Next stage is Feature21 quant/writeback split, because the second latest 60 MHz failing path was `featureQ8p8Reg_reg[0] -> featureByteRegs_11_reg[1]`.

## Checkpoint 2026-06-04 Feature21 Quant/Writeback Split Stage 1

- Feature21 timing source/destination rechecked from the latest 60 MHz report:
  - `radarDMA/feature21/featureQ8p8Reg_reg[0]` to `radarDMA/feature21/featureByteRegs_11_reg[1]`
  - Slack `-1.530 ns`
  - Data path delay `17.908 ns`
  - Logic levels `37`
- Source mapping:
  - `sFeatureSelect` already registers the selected feature control/data into `featureRawReg`, `featureDensityReg`, and `featureQ8p8Reg`.
  - `sFeatureQuant` still computed `selectedFeatureByte` and wrote `featureByteRegs(featureIdx)` in the same cycle.
  - That one-cycle path includes constant multiply, round-nearest-even, clamp, and the dynamic 32-entry feature-byte write mux.
- Modified `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`.
- Added `featureByteReg` and split the final feature byte path:
  - `sFeatureSelect -> sFeatureQuant -> sFeatureWrite`
  - `sFeatureQuant` now computes and registers `selectedFeatureByte`.
  - `sFeatureWrite` writes `featureByteRegs(featureIdx)` from the 8-bit `featureByteReg`.
- Behavior intent:
  - Keep feature values and quantization formula unchanged.
  - Add one cycle per emitted feature byte.
  - Cut the old `featureQ8p8Reg -> quantize/round/clamp -> featureByteRegs` timing path.
- Validation:
  - `git diff --check -- fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala fpga/src/main/scala/nexysvideo/RadarQMLP.scala docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md` passed.
  - `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo60MHzConfig verilog` passed.
  - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/feature21-quant-writeback-experiment-2026-06-04/verilog-60mhz-feature21-quant-writeback-2026-06-04.log`
  - Existing Makefile behavior still prints the ignored empty-`SIM_FILE_REQS` `cp: missing destination file operand` message.
- Generated SV evidence:
  - `RadarAXISFeature21Preprocessor.sv` contains real `featureByteReg`.
  - The quantization network from `featureQ8p8Reg` feeds `featureByteReg`.
  - The dynamic `featureByteRegs_*` write muxes now select `featureByteReg`, not the full quantization result.
- Current interpretation:
  - The Feature21 structural issue identified by the latest 60 MHz timing report has been addressed at RTL/generator level.
  - Actual slack impact still requires implementation timing.
  - The remaining watch item is the UART-TSI/`TSIToTileLink` A-channel request-generation path, especially an internal A-channel register stage if implementation timing still shows `tsi2tl` near the top.

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

## Checkpoint 2026-06-04 Post-QMLP/Feature21 60 MHz Bitstream

- Ran a targeted 60 MHz implementation after the QMLP MAC staging and Feature21 quant/writeback split.
- Command:
  - `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo60MHzConfig bitstream`
- Log:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/post-qmlp-feature21-bitstream-2026-06-04/bitstream-60mhz-post-qmlp-feature21-2026-06-04-181822.log`
- Result:
  - Top-level `make` returned `0`.
  - `write_bitstream completed successfully`.
  - Final timing gate passed; no `Failed to meet timing` exit was triggered.

### Final Artifacts

- Bitstream:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo60MHzConfig/obj/NexysVideoHarness.bit`
  - mtime `2026-06-04 18:35:17 +0800`
  - size `9730766`
  - SHA256 `2e837c3700adbd0385837dc2697d1d3abf5f2a5607d2aed8d7073c2c5c5b3a39`
- Timing report:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo60MHzConfig/obj/report/timing.txt`
  - mtime `2026-06-04 18:35:53 +0800`
  - size `3397930`
  - SHA256 `3e5f6c41991cc8aa6a6288994fa0af1515e8686fc680ea06c39728fb71682f3c`

### Timing Result

- Final design timing summary:
  - WNS `+0.018 ns`
  - TNS `0.000 ns`
  - Setup failing endpoints `0`
  - WHS `+0.027 ns`
  - THS `0.000 ns`
  - Hold failing endpoints `0`
- Intra-DUT clock group:
  - `clk_out1_harnessSysPLLNode` WNS `+0.018 ns`
  - `clk_out1_harnessSysPLLNode` TNS `0.000 ns`
  - 0 setup/hold failing endpoints.
- Route/physopt progression:
  - Post-route before post-route physopt: WNS `-0.071 ns`, TNS `-0.136 ns`.
  - Post-route `phys_opt_design` improved the critical path by about `0.090 ns`.
  - Final post-physopt timing: WNS `+0.018 ns`, TNS `0.000 ns`.

### New Tight Paths After Closure

- Worst setup path is no longer QMLP async-ROM/MAC:
  - Source `radarDMA/feature21/densityQ8p8Reg_reg[2]`
  - Destination `radarDMA/feature21/densityFeatureReg_reg[4]`
  - Slack `+0.018 ns`
  - Data path delay `16.545 ns`
  - Logic levels `31`
  - Interpretation: Feature21 density final quantization/feature-byte generation is now the tightest accepted path.
- Other near-top Feature21 density paths:
  - `densityQ8p8Reg_reg[2] -> densityFeatureReg_reg[0]`, slack `+0.019 ns`
  - `densityQ8p8Reg_reg[2] -> densityFeatureReg_reg[1]`, slack `+0.023 ns`
  - `densityQ8p8Reg_reg[2] -> densityFeatureReg_reg[2]`, slack `+0.023 ns`
  - `densityQ8p8Reg_reg[2] -> densityFeatureReg_reg[3]`, slack `+0.024 ns`
- Buffered UART-TSI path remains close but no longer failing:
  - Source `chiptop0/system/fbus/tsi2tl/addr_reg[4]`
  - Destination `chiptop0/system/fbus/coupler_from_uart_tsi/buffer/nodeOut_a_q/ram_reg[50]`
  - Slack `+0.102 ns`
  - Data path delay `16.451 ns`
  - Logic levels `33`
- QMLP no longer appears among the worst max-delay paths in the final report excerpt, which supports the QMLP MAC staging change as effective for the previously observed `outIdx -> async ROM -> accReg` path.

### Updated Interpretation

- Practical 60 MHz closure is now achieved for the integrated Feature21 + QMLP NexysVideo config.
- The QMLP MAC staging and Feature21 quant/writeback split converted the previous `-1.578 ns` 60 MHz failure into a passing post-route bitstream with only `+0.018 ns` margin.
- Margin is very thin. This bitstream should be treated as a timing-accepted 60 MHz candidate, not a robustly overclosed design.
- The next engineering priority should be functional validation on board:
  - UART-TSI load/selfcheck smoke test.
  - Feature21/QMLP board regression or golden comparison.
  - Confirm added QMLP and Feature21 cycles did not break software-visible completion or expected outputs.
- If more timing margin is needed after functional validation:
  - split Feature21 density final quantization/feature-byte generation,
  - or add an internal registered A-channel request stage in `TSIToTileLink` because the buffered TSI path still has only about `0.10 ns` slack.

### Immediate Validation After Bitstream

- Static diff check passed:
  - `git diff --check -- fpga/src/main/scala/nexysvideo/RadarQMLP.scala fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md`
- RISC-V test ELF build targets were checked:
  - `radar-axi-dma-feature21.riscv`
  - `radar-axi-dma-feature21-golden.riscv`
  - `radar-axi-dma-qmlp.riscv`
  - `radar-axi-dma-qmlp-validation.riscv`
  - `radar-axi-dma-qmlp-chain-validation.riscv`
  - `radar-axi-dma-qmlp-e2e.riscv`
  - Result: all were present and `make` reported them up to date.
- Generated SV evidence rechecked:
  - `RadarAXISQMLP.sv` contains real `biasStageReg`, `macDataRegs_*`, and `macWeightRegs_*`.
  - QMLP MAC expressions now multiply `macDataRegs_* * macWeightRegs_*`, not ROM outputs directly.
  - `RadarAXISFeature21Preprocessor.sv` contains real `featureByteReg`.
  - Feature byte array update muxes now select `featureByteReg`.
- Source-level state-machine sanity:
  - QMLP `Load -> Prep -> Mac` sequence registers bias/data/weight before MAC and preserves accumulator semantics.
  - Feature21 `Select -> Quant -> Write` sequence adds one byte-register stage before indexed feature-byte writeback.
  - No obvious same-cycle read-after-write issue was found in the final Feature21 emit transition: the final feature byte is written before later output beats read that word.
- Board validation was not run in this checkpoint because no `/dev/ttyUSB*` or `/dev/ttyACM*` device was present.

## Checkpoint 2026-06-04 Feature21 Density/General Quant Split 60 MHz Closure

- Continued from the thin-margin `+0.018 ns` 60 MHz candidate and kept the earlier bitstream/timing result as history.
- First follow-up: split Feature21 density final quantization by adding `densityQuantProductReg` and changing the density tail to:
  - `sDensityShift -> sDensityQuantMul -> sDensityQuantRound`
- Density-only split result:
  - 60 MHz bitstream passed.
  - Archived bitstream: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/feature21-density-quant-split-2026-06-04/artifacts/NexysVideoHarness-density-quant-split-60mhz.bit`
  - Archived timing: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/feature21-density-quant-split-2026-06-04/artifacts/timing-density-quant-split-60mhz.txt`
  - Bit SHA256 `2f5b54cdfab75326c7a063e6d9d52845bfb99a670a60cf6202206c33771d6f07`
  - Timing SHA256 `e4d624a9dd6115316b589abd50984be1784f02e1d7d1bdf90562675e7915c386`
  - Final WNS `+0.007 ns`, TNS `0.000 ns`, setup failing endpoints `0`.
  - Hold was clean: WHS `+0.015 ns`, THS `0.000 ns`.
  - Intra-DUT `clk_out1_harnessSysPLLNode` WNS `+0.007 ns`.
  - Worst 60 MHz setup path moved to ordinary Feature21 quantization:
    - `radarDMA/feature21/featureQ8p8Reg_reg[2]` to `radarDMA/feature21/featureByteReg_reg[2]`
    - data path delay `16.514 ns`
    - logic levels `37`
- Second follow-up: split ordinary Feature21 quantization by adding `featureQuantProductReg` and changing the feature tail to:
  - `sFeatureSelect -> sFeatureQuantMul -> sFeatureQuantRound -> sFeatureWrite`
- Current source state in `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`:
  - density quant multiply is registered in `densityQuantProductReg`.
  - ordinary feature quant multiply is registered in `featureQuantProductReg`.
  - `sFeatureQuantRound` only rounds/clamps from `featureQuantProductReg` into `featureByteReg`.
  - `sFeatureWrite` writes `featureByteRegs(featureIdx)` from `featureByteReg`.
  - Feature 0/count uses the same selected Q8.8 feature path via `(actualPoints << 8)`, so it no longer bypasses directly into the byte write mux.
- General-quant-split result:
  - 60 MHz bitstream passed.
  - Current generated bitstream and timing are byte-identical to the archived general-quant-split copies.
  - Archived bitstream: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/feature21-general-quant-split-2026-06-04/NexysVideoHarness-general-quant-split-60mhz.bit`
  - Archived timing: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/feature21-general-quant-split-2026-06-04/timing-general-quant-split-60mhz.txt`
  - Bit SHA256 `e01ce71f4c130f213d1657c738e008e8f08f5ddf6bff37f25ac47acb18798644`
  - Timing SHA256 `5e0236c9a9f5537416d3bd937e2c0f1d9e53d670e265b6856067707b74a4d63a`
  - Generated bitstream mtime `2026-06-04 22:25:54 +0800`, size `9730766`.
  - Generated timing mtime `2026-06-04 22:26:31 +0800`, size `3386661`.
- Final timing summary for the general-quant-split build:
  - WNS `+0.162 ns`
  - TNS `0.000 ns`
  - Setup failing endpoints `0`
  - WHS `+0.025 ns`
  - THS `0.000 ns`
  - Hold failing endpoints `0`
  - Intra-DUT `clk_out1_harnessSysPLLNode` WNS `+0.162 ns`, TNS `0.000 ns`, 0 failing endpoints.
  - `sys_clock` WNS `+5.584 ns`.
- True 60 MHz worst setup path for the current general-quant-split build:
  - Source `chiptop0/system/fbus/tsi2tl/addr_reg[4]_replica`
  - Destination `chiptop0/system/fbus/coupler_from_uart_tsi/buffer/nodeOut_a_q/ram_reg[50]`
  - Slack `+0.162 ns`
  - Data path delay `16.411 ns`
  - Logic levels `32`
  - Path group `clk_out1_harnessSysPLLNode`
  - This is the buffered UART-TSI / front-bus A-channel path, not Feature21 or QMLP arithmetic.
- Generated SV evidence:
  - `RadarAXISFeature21Preprocessor.sv` contains both `featureQuantProductReg` and `densityQuantProductReg`.
  - `featureByteRegs_*` writebacks select `featureByteReg`.
- Resource note:
  - `feature21` uses 2 DSP blocks in the post-route utilization report, matching the expected Feature21 multiply resources.
  - The added general quant split did not introduce an obvious extra DSP block beyond the Feature21 pair already present.
- Current recommendation:
  - Treat `feature21-general-quant-split-2026-06-04` as the preferred 60 MHz timing-closed candidate.
  - It improves the accepted margin from the density-only `+0.007 ns` to `+0.162 ns`.
  - The next timing-margin target is no longer ordinary Feature21 quantization; it is the buffered `tsi2tl` / UART-TSI front-bus path, unless board validation exposes a functional issue first.
  - Board validation is still required for UART-TSI load/selfcheck and Feature21/QMLP golden/regression behavior.

## Checkpoint 2026-06-04 75 MHz TSI/QMLP Split Work

- Target shifted from the already timing-closed 60 MHz candidate to an aggressive 75 MHz push.
- Historical 75 MHz baseline remains:
  - WNS `-3.059 ns`
  - TNS `-599.344 ns`
  - worst path `fbus/tsi2tl/addr_reg[4]` into `fbus/buffer` TL-A queue RAM.
- First 75 MHz TSI change:
  - Modified `generators/testchipip/src/main/scala/tsi/TSIToTileLink.scala`.
  - Added registered TL-A request output (`aBitsReg`, `aValidReg`) and prepare states so `mem.a.bits` no longer comes directly from `edge.Get`/`edge.Put` combinational request generation.
  - 75 MHz verilog generation passed and generated `TSIToTileLink.sv` confirmed TL-A fields driven from `aBitsReg_*`.
- A first implementation attempt with only that TSI A-register stage was intentionally stopped during route:
  - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/feature21-75mhz-tsi-a-pipeline-2026-06-04/bitstream-75mhz-tsi-a-pipeline-2026-06-04.log`
  - It reached route startup, but the code had a functional bug for multi-beat TSI reads.
  - The stopped run did not produce a final post-route timing report.
  - Intermediate post-place/power-opt estimate still showed negative setup timing around WNS `-2.226 ns`.
  - Placement/physopt messages named `tsi2tl/aBitsReg_*`, `raw_size`, `byteAddr`, and `radarDMA/qmlp/quantProductReg_*` candidates, so the next cuts were aimed there.
- Functional bug fixed in TSI read flow:
  - The original A-register patch cleared `aValidReg` after a read request fired.
  - Multi-beat reads then returned from `s_read_body` to `s_read_req` without reloading `aBitsReg` or reasserting `aValidReg`, which could hang UART-TSI selfcheck/readback.
  - The read loop now returns to request preparation for each new beat.
- Deeper TSI read-request split:
  - Added `s_read_measure`, `s_read_size`, `s_read_prepare`, then `s_read_req`.
  - `s_read_measure` registers address/length sizing inputs.
  - `s_read_size` registers derived request size/address-low fields.
  - `s_read_prepare` loads the final TL-A `Get` request into `aBitsReg`.
  - Generated `TSIToTileLink.sv` confirms real `readAddrSizeReg`, `readLenSizeReg`, `readLgSizeReg`, `readBeatAddrReg`, `readByteAddrReg`, and `aBitsReg_*`.
- QMLP follow-up split:
  - Modified `fpga/src/main/scala/nexysvideo/RadarQMLP.scala`.
  - Changed the requant constant multiply helper from a linear shift-add fold to a fixed-width balanced sum helper.
  - Intent is to reduce the `accReg -> quantProductReg` logic depth without changing QMLP state sequencing or adding visible cycles.
  - First attempt failed elaboration because fixed-width slicing ran before padding; fixed by padding before slicing.
- Validation before rerun:
  - `git -C generators/testchipip diff --check -- src/main/scala/tsi/TSIToTileLink.scala` passed.
  - `git diff --check -- fpga/src/main/scala/nexysvideo/RadarQMLP.scala docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md` passed.
  - `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo75MHzConfig verilog` passed after both TSI and QMLP changes.
  - Latest verilog log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/feature21-75mhz-tsi-read-pipeline-2026-06-04/verilog-75mhz-tsi-read-pipeline-qmlp-balanced-v2-2026-06-04.log`
- Current active run:
  - Command: `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo75MHzConfig bitstream`
  - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/feature21-75mhz-tsi-read-pipeline-2026-06-04/bitstream-75mhz-tsi-read-pipeline-qmlp-balanced-2026-06-04.log`
  - At the time of this checkpoint, the run had passed PLL/IP setup and was entering Vivado implementation; no final WNS/TNS yet.

## Checkpoint 2026-06-04 75 MHz TSI/QMLP Split Closure

- The 75 MHz implementation completed after the deeper TSI read pipeline and QMLP balanced requant add tree.
- Command:
  - `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo75MHzConfig bitstream`
- Log:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/feature21-75mhz-tsi-read-pipeline-2026-06-04/bitstream-75mhz-tsi-read-pipeline-qmlp-balanced-2026-06-04.log`
- Result:
  - `write_bitstream completed successfully`.
  - Vivado exited normally at `2026-06-04 23:31:42 +0800`.
  - The final timing gate did not trigger a failure.

### Final 75 MHz Artifacts

- Bitstream:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/NexysVideoHarness.bit`
  - mtime `2026-06-04 23:30:58 +0800`
  - size `9730766`
  - SHA256 `4c17ff97e38d99de268e010458d3e6172f8f03e3f2b41fc205d7e219e2e024a9`
- Timing report:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/report/timing.txt`
  - mtime `2026-06-04 23:31:32 +0800`
  - size `3452071`
  - SHA256 `cb7cb8bd1bbe388ea270926b516232c8e5a03299299a705ffaa42e9ea4acade8`

### Final Timing Result

- Final design timing summary:
  - WNS `+0.021 ns`
  - TNS `0.000 ns`
  - Setup failing endpoints `0`
  - WHS `+0.017 ns`
  - THS `0.000 ns`
  - Hold failing endpoints `0`
- Intra-DUT `clk_out1_harnessSysPLLNode`:
  - WNS `+0.021 ns`
  - TNS `0.000 ns`
  - setup failing endpoints `0`
  - WHS `+0.024 ns`
  - THS `0.000 ns`
  - hold failing endpoints `0`
- Post-route progression:
  - Route-stage timing before post-route physopt was still failing at WNS `-0.919 ns`, TNS `-111.716 ns`, WHS `+0.017 ns`.
  - Post-route `phys_opt_design -directive Explore` recovered about `0.939 ns` WNS and `111.716 ns` TNS.
  - Post-route physopt final summary was WNS `+0.021 ns`, TNS `0.000 ns`, WHS `+0.017 ns`, THS `0.000 ns`.

### Tight Paths After 75 MHz Closure

- Worst setup path in the final report:
  - Slack `+0.021 ns`
  - Source `chiptop0/system/tile_prci_domain/element_reset_domain_rockettile/frontend/fq/valid_0_reg_replica`
  - Destination `chiptop0/system/tile_prci_domain/element_reset_domain_rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Requirement `13.333 ns`
  - Data path delay `12.484 ns`
  - Logic delay `2.068 ns`
  - Route delay `10.416 ns`
  - Logic levels `13`
  - Interpretation: the final worst setup path is Rocket front-end queue/control into core execute decode, not TSI or QMLP.
- Other near-top setup paths repeat the same source into nearby `ex_reg_rs_msb_0` destinations with the same `+0.021 ns` slack.
- During post-route physopt, the active path group rotated through:
  - Rocket divider DSP/multiply residue, including `_prod_T_40__*` and `remainder*` nets.
  - Rocket front-end queue/control decode nets.
  - Feature21 density quantization nets, including `densityFeatureReg*`, `densityRounded0`, and `densityQuantProductReg`.
- The earlier TSI and QMLP candidates no longer appear as the final top setup path class in the closed timing report.

### DRC / Robustness Notes

- Bitgen DRC completed with `0 Errors`, `28 Warnings`, and `4 Advisories`.
- Notable timing-relevant warnings:
  - DSP input/output pipeline warnings remain on Feature21 density DSPs (`densityAreaReg0`, `densityProdReg0`).
  - DSP output/multiplier pipeline warnings remain on Rocket divider DSPs (`core/div/_prod_T_40__*`).
  - These warnings line up with the paths Vivado had to optimize late in post-route physopt.
- There were also known project/IP critical warnings earlier in the log for already-present IP/fileset/XDC issues; they did not prevent bitstream generation or final timing closure.

### Current Interpretation

- The 75 MHz target is now timing-closed for this generated bitstream, but with a very thin `+0.021 ns` setup margin.
- The TSI TL-A request registerization plus deeper read-request preparation eliminated the old 75 MHz front-bus/TSI bottleneck as the top final path.
- The QMLP balanced requant add tree also removed the observed `qmlp/quantProductReg_*` path from the final top path class.
- The remaining margin risk has shifted to global SoC timing and Feature21 density DSP/quantization residue rather than one obvious accelerator path.
- Board validation is still required, especially UART-TSI load/readback/selfcheck, because the TSI FSM changed and the earlier A-register-only patch had a multi-beat read bug that was fixed before this final run.
- If more 75 MHz guardband is needed after functional validation, the likely next targets are:
  - Rocket divider/front-end timing only if changing the core configuration is acceptable.
  - Feature21 density DSP pipelining or another density-tail split.
  - A floorplanning/clocking pass, because the final Rocket path is route-dominated (`10.416 ns` route out of `12.484 ns` data delay).

## Checkpoint 2026-06-05 Fresh 75 MHz/QMLP/TSI Audit

- Restarted from `docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md` and current files only; no old thread context was used.
- Evidence rechecked:
  - 75 MHz timing: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/report/timing.txt`
  - 75 MHz bitstream: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/NexysVideoHarness.bit`
  - 75 MHz build log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-04/feature21-75mhz-tsi-read-pipeline-2026-06-04/bitstream-75mhz-tsi-read-pipeline-qmlp-balanced-2026-06-04.log`
  - QMLP source: `fpga/src/main/scala/nexysvideo/RadarQMLP.scala`
  - Feature21 source: `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
  - UART-TSI source: `generators/testchipip/src/main/scala/tsi/TSIToTileLink.scala` and `generators/testchipip/src/main/scala/tsi/PeripheryUARTTSI.scala`
- 75 MHz artifact hashes still match the prior checkpoint:
  - Bitstream SHA256 `4c17ff97e38d99de268e010458d3e6172f8f03e3f2b41fc205d7e219e2e024a9`
  - Timing SHA256 `cb7cb8bd1bbe388ea270926b516232c8e5a03299299a705ffaa42e9ea4acade8`
- 75 MHz final timing rechecked:
  - WNS `+0.021 ns`
  - TNS `0.000 ns`
  - Setup failing endpoints `0`
  - WHS `+0.017 ns`
  - THS `0.000 ns`
  - Hold failing endpoints `0`
- Final 75 MHz worst setup path remains a Rocket/SoC path, not QMLP, Feature21, or TSI:
  - Source `chiptop0/system/tile_prci_domain/element_reset_domain_rockettile/frontend/fq/valid_0_reg_replica`
  - Destination `chiptop0/system/tile_prci_domain/element_reset_domain_rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Slack `+0.021 ns`
  - Data path delay `12.484 ns`
  - Route delay `10.416 ns`
  - Logic levels `13`
- QMLP async-ROM/MAC staging source check:
  - Async distributed ROMs are still present, but the MAC path is now staged through `biasStageReg`, `macDataRegs`, and `macWeightRegs`.
  - Layer sequencing is `Load -> Prep -> Mac`, so the old `outIdx/inIdx -> async ROM -> lane multiply/sum -> accReg` path is cut by real registers.
  - The requant constant multiply now uses `balancedFixedWidthSum`, matching the 75 MHz checkpoint intent to reduce `accReg -> quantProductReg` depth.
  - No further QMLP RTL change was made in this audit.
- Feature21 quant/writeback split source check:
  - Density quantization is split through `densityQuantProductReg`.
  - Ordinary feature quantization is split through `featureQuantProductReg`, then `featureByteReg`, then `featureByteRegs(featureIdx)`.
  - This matches the timing-closed 60 MHz general-quant-split path and keeps the 75 MHz final top path away from ordinary Feature21 quant/writeback.
  - No further Feature21 RTL change was made in this audit.
- UART-TSI watch-list source check:
  - `PeripheryUARTTSI.scala` still couples UART-TSI into FBUS through `TLBuffer(BufferParams.pipe)`.
  - `TSIToTileLink.scala` now drives TL A-channel from `aBitsReg/aValidReg`, not directly from combinational `edge.Get/edge.Put` logic.
  - Read request generation is split through `s_read_measure`, `s_read_size`, and `s_read_prepare`; multi-beat reads return to `s_read_measure`, avoiding the earlier A-register-only bug where later read beats could fail to reassert `aValidReg`.
  - TSI is no longer the final 75 MHz top path, but it remains a functional validation watch item because the bring-up/readback FSM changed.
- Current conclusion:
  - The current source plus generated artifacts support 75 MHz timing closure, with very thin margin.
  - QMLP async-ROM/MAC staging and Feature21 quant/writeback splitting should be treated as implemented timing cuts, not pending hypotheses.
  - Next priority is board validation: UART-TSI load/readback/selfcheck and Feature21/QMLP golden/regression tests.
  - If more 75 MHz guardband is needed after functional validation, the next timing targets are Feature21 density DSP/tail pipelining or route/floorplanning/Rocket-core configuration work; TSI stays on the watch list but is no longer the leading timing limiter in the final report.

## Checkpoint 2026-06-05 75 MHz WNS Margin Experiments

- User requested more WNS margin because the closed 75 MHz bitstream is still too close to the edge.
- Baseline remains the 2026-06-04 75 MHz bitstream/timing:
  - WNS `+0.021 ns`
  - WHS `+0.017 ns`
  - Worst setup path is Rocket frontend queue/control into Rocket execute decode, not QMLP/Feature21/TSI.
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/`
- Physical implementation experiment 1:
  - Script: `run_post_place_route_variant.tcl`
  - Input checkpoint: generated 75 MHz `obj/post_place.dcp`
  - Route directive `AggressiveExplore`
  - Post-route physopt directive `AggressiveExplore`
  - Result: post-route WNS `-0.919 ns`, final WNS `+0.021 ns`, final WHS `+0.017 ns`
  - Interpretation: no improvement over baseline; the result is timing-clean but not a better candidate bitstream.
- Physical implementation experiment 2:
  - Script: `run_impl_directive_variant.tcl`
  - Input checkpoint: generated 75 MHz `obj/post_synth.dcp`
  - Opt `Explore`, place `ExtraTimingOpt`, post-place physopt `AggressiveExplore`, no power opt, route `MoreGlobalIterations`, post-route physopt `AggressiveExplore`
  - Result: post-route WNS `-0.689 ns`, final WNS `-0.420 ns`, final WHS `+0.010 ns`
  - Interpretation: failed timing; do not use the generated bitstream from this variant.
- Physical implementation experiment 3:
  - Script: `run_post_place_route_variant.tcl`
  - Input checkpoint: generated 75 MHz `obj/post_place.dcp`
  - Route directive `Explore`
  - Post-route physopt directive `AddRetime`
  - Result: post-route WNS `-0.919 ns`, final WNS `-0.177 ns`, final WHS `+0.017 ns`
  - Interpretation: failed timing; it improved the raw route result by `0.742 ns`, but still did not reach the existing baseline `+0.021 ns`.
- Current read:
  - The existing baseline placement/routing recipe is already close to the best observed result.
  - Continue with targeted post-place route/physopt variants first because they are lower-risk than RTL, then fall back to Feature21 density DSP/tail pipelining if no physical variant produces extra margin.
  - Keep `TSIToTileLink` A-channel register stage on the watch list; it is not currently the final top timing class.

## Checkpoint 2026-06-05 Feature21 Density DSP Pipeline Edit

- Since three physical implementation variants failed to improve the baseline, moved to the next lower-risk RTL cleanup target: Feature21 density DSP/tail pipelining.
- Source edited:
  - `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
- RTL change:
  - Expanded the Feature21 FSM from `Enum(17)` to `Enum(21)`.
  - Split `sDensityArea` into:
    - `sDensityArea`: register `spanX/spanY` operands.
    - `sDensityAreaMul`: compute registered `spanX * spanY`.
    - `sDensityAreaCommit`: commit the registered area product into `densityAreaReg`.
  - Split density reciprocal multiplication into:
    - `sDensityMulPrep`: register point-count and reciprocal operands.
    - `sDensityMul`: compute the registered product.
    - `sDensityMulCommit`: commit into `densityProdReg`.
  - Added internal registers: `densitySpanXReg`, `densitySpanYReg`, `densityAreaProductReg`, `densityPointCountReg`, `densityRecipOperandReg`, and `densityProdProductReg`.
- Expected behavior impact:
  - AXIS input/output format and Feature21 feature bytes are intended to remain unchanged.
  - Feature21 per-frame internal latency increases by four cycles.
  - The edit targets Vivado DRC warnings on `radarDMA/feature21/densityAreaReg0` and `radarDMA/feature21/densityProdReg0` DSP input/output/multiplier pipelining.
- Verification status:
  - Path-limited `git diff --check -- fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md` passed.
  - Full-repo `git diff --check` still reports pre-existing trailing whitespace in unrelated `docs/radar_soc_progress_report_2026-04-05.md`; left untouched.
  - 75 MHz Verilog regeneration passed.
  - Verilog log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-feature21-density-pipeline-2026-06-05/verilog-75mhz-feature21-density-pipeline-2026-06-05.log`
  - 75 MHz implementation completed, but failed to improve timing.

### Density Pipeline Result And Revert

- Failed density-pipeline artifacts were archived before restoring the usable baseline:
  - Bitstream: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-feature21-density-pipeline-2026-06-05/failed-density-pipeline.NexysVideoHarness.bit`
    - SHA256 `e2fd5bd9268f361b50929299a6867579c57d9c62a5a74e3759d12a95dcf217d0`
  - Timing: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-feature21-density-pipeline-2026-06-05/failed-density-pipeline.timing.txt`
    - SHA256 `130dc3077c0c26dc067b98d1ab553bc706d838f1252be28c53e53b08579f9648`
  - DRC: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-feature21-density-pipeline-2026-06-05/failed-density-pipeline.drc.txt`
    - SHA256 `7dd8c55b05ed542f2faad70efcdd2e02f5d7973f0764c31bf4678d53d203b386`
- Failed density-pipeline final timing:
  - WNS `-0.169 ns`
  - TNS `-8.931 ns`
  - Setup failing endpoints `131`
  - WHS `+0.024 ns`
  - Worst setup path remained Rocket frontend/core decode:
    - Source `rockettile/frontend/icache/s2_dout_0_reg[11]`
    - Destination `rockettile/core/ex_reg_rs_msb_1_reg[12]/CE`
    - Data path delay `13.075 ns`, route delay `10.562 ns`, logic levels `13`
- The density edit did not solve the DSP DRC class either:
  - The DRC warnings moved from `densityAreaReg0` / `densityProdReg0` to `densityAreaProductReg0` / `densityProdProductReg0`.
  - The generated DSPs still had no internal A/B/M/P register absorption.
- Conclusion:
  - Do not use the density-pipeline bitstream.
  - The extra Feature21 density area/product staging was reverted from `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`.
  - The effective Feature21 quant/writeback split remains in place: `featureQuantProductReg`, `featureByteReg`, and the `sFeatureQuantMul` / `sFeatureQuantRound` states are still present.
- The generated 75 MHz `obj` bitstream and timing report were restored to the known-good 2026-06-04 baseline:
  - `obj/NexysVideoHarness.bit` SHA256 `4c17ff97e38d99de268e010458d3e6172f8f03e3f2b41fc205d7e219e2e024a9`
  - `obj/report/timing.txt` SHA256 `cb7cb8bd1bbe388ea270926b516232c8e5a03299299a705ffaa42e9ea4acade8`
  - Restored timing remains WNS `+0.021 ns`, TNS `0.000 ns`, WHS `+0.017 ns`.
- Next step:
  - Regenerated 75 MHz Verilog after the revert to confirm the source state is clean.
    - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-feature21-density-pipeline-2026-06-05/verilog-75mhz-after-density-revert-2026-06-05.log`
    - Result: passed.
    - Generated `RadarAXISFeature21Preprocessor.sv` no longer contains `densityAreaProductReg`, `densityProdProductReg`, `densitySpanXReg`, or `densityPointCountReg`.
    - Generated SV still contains `featureQuantProductReg`, confirming the useful general quant split remains.
    - The existing Makefile `SIM_FILE_REQS` empty-copy warning is still present and ignored by make, as in earlier successful runs.
  - Rebuild or otherwise refresh baseline implementation checkpoints before running any further post-place route/physopt variants, because the density experiment overwrote generated implementation checkpoints even though bit/timing were restored.

### After-Revert 75 MHz Baseline Refresh

- Ran a full 75 MHz bitstream build after reverting the failed density-pipeline edit.
- Command:
  - `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideo75MHzConfig bitstream`
- Log:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-feature21-density-pipeline-2026-06-05/bitstream-75mhz-after-density-revert-refresh-2026-06-05.log`
- Result:
  - `write_bitstream completed successfully`.
  - Vivado exited normally at `2026-06-05 20:15:42 +0800`.
  - Timing gate passed.
- Refreshed final timing:
  - WNS `+0.021 ns`
  - TNS `0.000 ns`
  - Setup failing endpoints `0`
  - WHS `+0.017 ns`
  - THS `0.000 ns`
  - Hold failing endpoints `0`
- Refreshed worst setup path is identical in class and slack to the 2026-06-04 baseline:
  - Source `rockettile/frontend/fq/valid_0_reg_replica`
  - Destination `rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Slack `+0.021 ns`
  - Data path delay `12.484 ns`, route delay `10.416 ns`, logic levels `13`
- Post-route progression again matches the known-good baseline shape:
  - Post-route before post-route physopt: WNS `-0.919 ns`, TNS `-111.716 ns`, WHS `+0.017 ns`.
  - Post-route `phys_opt_design -directive Explore`: final WNS `+0.021 ns`, TNS `0.000 ns`, WHS `+0.017 ns`.
- Refreshed artifact archive:
  - Directory: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-feature21-density-pipeline-2026-06-05/after-density-revert-refresh-artifacts/`
  - Bitstream SHA256 `d10295154b23971be1e21129729d0f7f569ed6648c47d3f710cb772583961c8e`
  - Timing SHA256 `266dd3ecbfa477de4b20262eeae7d40e772bbbdd325aabc8153050660846168c`
  - DRC SHA256 `a051e1466c187b6473cebfff417601864942a0c7c3a06d50da2b981182aeea0a`
  - Post-place checkpoint SHA256 `5c637f0a920f03c7d18e20eccb6243d4c0103cca940d4f12baedaf44c65a785e`
- Note:
  - The refreshed bitstream hash differs from the earlier 2026-06-04 bitstream hash, but final WNS/WHS and the top timing path reproduce the same timing-closed baseline.
  - The generated implementation checkpoints are now aligned with the reverted RTL again, so further post-place route/physopt variants can safely use the refreshed `obj/post_place.dcp`.

## Checkpoint 2026-06-05 Post-Revert 75 MHz Physical Variant

- Ran another post-place route/physopt variant from the refreshed, reverted 75 MHz `obj/post_place.dcp`.
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/explore_route_aggressivefanout_phys_after_revert/`
- Variant:
  - Route directive `Explore`
  - Post-route physopt directive `AggressiveFanoutOpt`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `-0.177 ns`
  - Final TNS `-2.069 ns`
  - Setup failing endpoints `33`
  - Final WHS `+0.017 ns`
  - Bitgen completed, but timing constraints were not met.
- Worst final setup path:
  - Source `rockettile/frontend/fq/valid_0_reg_replica`
  - Destination `rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Data path delay `12.681 ns`
  - Route delay `10.613 ns`
  - Logic levels `13`
- Interpretation:
  - Do not use this bitstream.
  - `AggressiveFanoutOpt` behaves similarly to the earlier `AddRetime` post-route variant: it improves the raw `-0.919 ns` route result but fails to recover to the existing `+0.021 ns` baseline.
  - The final limiter remains Rocket frontend/core routing, with Rocket divider residue also appearing among failing paths.
  - TSI, QMLP MAC, and ordinary Feature21 quant/writeback remain off the top final path list.

## Checkpoint 2026-06-05 Post-Revert 75 MHz MoreGlobal Variant

- Ran a post-place route/physopt variant from the refreshed, reverted 75 MHz `obj/post_place.dcp`.
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/moreglobal_route_explore_phys_after_revert/`
- Variant:
  - Route directive `MoreGlobalIterations`
  - Post-route physopt directive `Explore`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `+0.040 ns`
  - Final TNS `0.000 ns`
  - Setup failing endpoints `0`
  - Final WHS `+0.017 ns`
  - Bitgen completed successfully.
- This is the best 75 MHz candidate observed so far:
  - It improves over the current baseline WNS `+0.021 ns` by `0.019 ns`.
  - The margin is still very thin, but it is a measurable improvement.
- Worst final setup path:
  - Source `rockettile/frontend/icache/s2_dout_0_reg[15]`
  - Destination `rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Slack `+0.040 ns`
  - Data path delay `12.461 ns`
  - Route delay `10.257 ns`
  - Logic levels `13`
- Artifact hashes:
  - Bitstream SHA256 `530cceaee2e9d433b5829d32340012fd1ee107c9b16adc4115013f6e2f8cb665`
  - Timing summary SHA256 `d5a81563a12c8977e60584621f7ccd4cc946293de1f5e46e5ef4b0023aea9482`
  - Post-physopt checkpoint SHA256 `e39d9e4415ef06f3a706f9c39997c6ca56416d794a85d7aa278cfb1008f53c69`
- Interpretation:
  - Prefer this bitstream over the baseline if using a 75 MHz candidate now.
  - The improvement came from routing/physopt behavior only; no new RTL change was introduced.
  - The final top path is still Rocket frontend/core routing, not TSI, QMLP, or Feature21 quant/writeback.

### MoreGlobal + AggressiveExplore Check

- Ran adjacent variant from the same refreshed `obj/post_place.dcp`:
  - Route directive `MoreGlobalIterations`
  - Post-route physopt directive `AggressiveExplore`
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/moreglobal_route_aggressive_phys_after_revert/`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `+0.040 ns`
  - Final TNS `0.000 ns`
  - Final WHS `+0.017 ns`
  - Bitgen completed successfully.
- Artifact hashes:
  - Bitstream SHA256 `6eeb61241517b23c2ad43a20440f785d16f1760e0636f1522d241dceb7682f4f`
  - Timing summary SHA256 `7e377fd87d82875502e75680b4870de4a7161fac7e0ce7649ca862bb585ab7cd`
  - Post-physopt checkpoint SHA256 `df40a6c12d365344eff3c26142f83bb40b0b7a3c058eb30077d05e82199471eb`
- Interpretation:
  - This ties the `MoreGlobalIterations + Explore` result but does not beat it.
  - The useful ingredient appears to be `route_design -directive MoreGlobalIterations`; changing post-route physopt from `Explore` to `AggressiveExplore` did not add margin.

### Unsupported Physopt Directive Check

- Tried `MoreGlobalIterations + ExploreWithRemap`.
- Runtime log:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/moreglobal_route_explorewithremap_phys_after_revert.log`
- Result:
  - Route completed with post-route WNS `-0.919 ns`.
  - `phys_opt_design -directive ExploreWithRemap` failed immediately afterward:
    - Vivado 2022.2 reported `Directive 'ExploreWithRemap' is not a recognized directive`.
  - No final physopt timing or usable bitstream from this variant.
- Interpretation:
  - Do not retry `ExploreWithRemap` in this toolchain.

### MoreGlobal + AlternateReplication Check

- Ran another adjacent variant from the same refreshed `obj/post_place.dcp`:
  - Route directive `MoreGlobalIterations`
  - Post-route physopt directive `AlternateReplication`
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/moreglobal_route_alternatereplication_phys_after_revert/`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `-0.061 ns`
  - Final TNS `-0.432 ns`
  - Setup failing endpoints `9`
  - Final WHS `+0.017 ns`
  - Bitgen completed, but timing constraints were not met.
- Worst final setup path:
  - Source `rockettile/frontend/fq/elts_0_data_reg[17]`
  - Destination `rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Data path delay `12.567 ns`
  - Route delay `10.623 ns`
  - Logic levels `12`
- Artifact hashes:
  - Bitstream SHA256 `4b95728561e5a38b88bfab7d318ce6257851f4e28171d559b6990ddb74dcba0c`
  - Timing summary SHA256 `5b92761da2c1e3b1d1d26f42242f2287baaedd2ba54f323b804bcf2fe42a2559`
- Interpretation:
  - Do not use this bitstream.
  - `AlternateReplication` is supported by this Vivado, but it regresses below the `+0.040 ns` MoreGlobal + Explore/AggressiveExplore candidates.

### NoTimingRelaxation Route Check

- Ran another post-place variant:
  - Route directive `NoTimingRelaxation`
  - Post-route physopt directive `Explore`
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/notimingrelax_route_explore_phys_after_revert/`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `-0.043 ns`
  - Final TNS `-0.258 ns`
  - Setup failing endpoints `6`
  - Final WHS `+0.002 ns`
  - Bitgen completed, but timing constraints were not met.
- Worst final setup path:
  - Source `rockettile/frontend/icache/s2_dout_0_reg[25]`
  - Destination `rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Data path delay `12.486 ns`
  - Route delay `10.219 ns`
  - Logic levels `13`
- Additional note:
  - Later failing paths included `feature21/densityQuantProductReg -> densityFeatureReg`, so this route/physopt trajectory also brings Feature21 density residue closer to failure.
- Artifact hashes:
  - Bitstream SHA256 `4ceb7f3d38d8d9d632a5bb5b41a2692c62ffe457194f7534290602f108b9f9b6`
  - Timing summary SHA256 `7b3018dea586684a9977317bb649b76f451ad18de0515ff3be8a06bcae732e93`
- Interpretation:
  - Do not use this bitstream.
  - Despite better post-route TNS than MoreGlobal in this run, `NoTimingRelaxation` did not convert into positive WNS and badly reduced hold margin.

### Current 75 MHz Candidate Promotion

- Promoted the best observed 75 MHz variant into the generated `obj` bit/timing paths:
  - Source candidate: `moreglobal_route_explore_phys_after_revert`
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/NexysVideoHarness.bit`
    - SHA256 `530cceaee2e9d433b5829d32340012fd1ee107c9b16adc4115013f6e2f8cb665`
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/report/timing.txt`
    - SHA256 `d5a81563a12c8977e60584621f7ccd4cc946293de1f5e46e5ef4b0023aea9482`
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/report/drc.txt`
    - SHA256 `649d09166ce437a7550c1c339ab7d4953317fcb15b994a168d36497ac50ccdae`
- Current promoted 75 MHz timing:
  - WNS `+0.040 ns`
  - TNS `0.000 ns`
  - Setup failing endpoints `0`
  - WHS `+0.017 ns`
  - THS `0.000 ns`
  - Hold failing endpoints `0`
- Source sanity after promotion:
  - The failed density area/product pipeline staging is absent from `RadarAXIDMA.scala` and regenerated `RadarAXISFeature21Preprocessor.sv`.
  - The useful Feature21 general quant split remains present through `featureQuantProductReg`.
  - Path-limited `git diff --check -- fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md` passed.

### HigherDelayCost Route Check

- The previously in-progress post-place route/physopt variant completed after the handoff.
- Variant:
  - Route directive `HigherDelayCost`
  - Post-route physopt directive `Explore`
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/higherdelaycost_route_explore_phys_after_revert/`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `-0.027 ns`
  - Final TNS `-0.194 ns`
  - Setup failing endpoints `13`
  - Final WHS `+0.017 ns`
  - Bitgen completed, but timing constraints were not met.
- Worst final setup path:
  - Source `rockettile/core/ibuf/nBufValid_reg`
  - Destination `rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Data path delay `12.532 ns`
  - Route delay `10.464 ns`
  - Logic levels `13`
- Near-top secondary path:
  - `radarDMA/feature21/densityQuantProductReg_reg[9]` to `radarDMA/feature21/densityFeatureReg_reg[2]`
  - Slack `-0.003 ns`
  - This confirms Feature21 density residue is still close to the edge in some route shapes, but it did not beat the Rocket/core path as the final limiter.
- Artifact hashes:
  - Bitstream SHA256 `1a80f2381f5babd9dbed51fb2d2e1e562684b4e77fee11d73d40107a19168a82`
  - Summary SHA256 `df7094c0141d9c22543c9c23f8d405aa168c5ba92e0694c9229b3c8a71177c38`
  - Post-physopt checkpoint SHA256 `016412c2e9ba0acec836bab89f717e32a9c07478b369756b57fc344bf85163ee`
- Interpretation:
  - Do not use this bitstream.
  - `HigherDelayCost` is a valid Vivado 2022.2 route directive, but this run failed timing and does not improve on the promoted `MoreGlobalIterations + Explore` candidate.
  - The generated 75 MHz `obj` bitstream/timing remain promoted to `MoreGlobalIterations + Explore` with WNS `+0.040 ns`, not this failed variant.

### MoreGlobal + AggressiveFanoutOpt Check

- Ran one more adjacent post-place route/physopt variant from the same refreshed `obj/post_place.dcp`.
- Variant:
  - Route directive `MoreGlobalIterations`
  - Post-route physopt directive `AggressiveFanoutOpt`
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/moreglobal_route_aggressivefanout_phys_after_revert/`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `-0.061 ns`
  - Final TNS `-0.432 ns`
  - Setup failing endpoints `9`
  - Final WHS `+0.017 ns`
  - Bitgen completed, but timing constraints were not met.
- Worst final setup path:
  - Source `rockettile/frontend/fq/elts_0_data_reg[17]`
  - Destination `rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Data path delay `12.567 ns`
  - Route delay `10.623 ns`
  - Logic levels `12`
- Artifact hashes:
  - Bitstream SHA256 `e99c24ffa9c87c3234205b9284d4fd5eaa273bbe95d0f7d6359264531e8a2001`
  - Summary SHA256 `fd64e1052d17fb9f9b1805c1a06c4e2bfb19799d786a8468555eb2c5278b314f`
  - Post-physopt checkpoint SHA256 `35b870b7b7d2b7059d73d06fee238a583eb0491a9fd8bb0cd02fee1e4297dcad`
- Interpretation:
  - Do not use this bitstream.
  - This matches the `MoreGlobalIterations + AlternateReplication` failure class and does not improve over the `MoreGlobalIterations + Explore` / `AggressiveExplore` tie at WNS `+0.040 ns`.
  - The generated 75 MHz `obj` bitstream/timing were not changed and still point to the `MoreGlobalIterations + Explore` candidate.

### AdvancedSkewModeling Route Check

- Ran a skew-targeted post-place route/physopt variant from the same refreshed `obj/post_place.dcp`.
- Variant:
  - Route directive `AdvancedSkewModeling`
  - Post-route physopt directive `Explore`
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/advancedskew_route_explore_phys_after_revert/`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `-0.099 ns`
  - Final TNS `-3.162 ns`
  - Setup failing endpoints `89`
  - Final WHS `+0.017 ns`
  - Bitgen completed, but timing constraints were not met.
- Worst final setup path:
  - Source `rockettile/frontend/icache/s2_dout_0_reg[17]`
  - Destination `rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Data path delay `12.541 ns`
  - Route delay `10.528 ns`
  - Logic levels `11`
  - Clock path skew `-0.346 ns`
- Artifact hashes:
  - Bitstream SHA256 `fcd12f75fc2dcef95622af269ab994df7181ff9ccaab5503b06cfb1568f6142d`
  - Summary SHA256 `51ba9e530af5373898cc5e6348ace23948f65a68ef601771117693718c9411a0`
  - Post-physopt checkpoint SHA256 `5e252a6bd60a7af2558434433dfacb844f4dad2565675041f2d9af1e196a6f83`
- Interpretation:
  - Do not use this bitstream.
  - `AdvancedSkewModeling` is valid in this Vivado 2022.2 environment, but it did not improve WNS and produced a worse final TNS than the current best candidate.
  - The final path remained Rocket frontend/core and the measured clock skew was worse than the promoted `MoreGlobalIterations + Explore` result, so this route directive is not helpful for the current placement.
  - The generated 75 MHz `obj` bitstream/timing remain the promoted `MoreGlobalIterations + Explore` candidate with WNS `+0.040 ns`.

### WLDrivenBlockPlacement Full-Impl Check

- Found one completed full implementation variant that had not yet been summarized in this rolling log.
- Variant:
  - `opt_design -directive Explore`
  - `place_design -directive WLDrivenBlockPlacement`
  - post-place `phys_opt_design -directive Explore`
  - `power_opt_design` enabled
  - `route_design -directive MoreGlobalIterations`
  - post-route `phys_opt_design -directive Explore`
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-05/75mhz-wns-margin-physopt-2026-06-05/impl_wldriven_mgi_explore_2026-06-05/`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `+0.000 ns`
  - Final WHS `+0.017 ns`
- Interpretation:
  - Do not promote this bitstream; it is timing-clean by the report but has effectively zero setup guardband.
  - It does not improve on the current promoted `MoreGlobalIterations + Explore` post-place candidate at WNS `+0.040 ns`.
  - Placement changes from `WLDrivenBlockPlacement` did not solve the current route-dominated Rocket frontend/core path.

## Checkpoint 2026-06-06 75 MHz Margin Status / QoR Audit

- Restarted from the rolling summary and current workspace only; no old thread context was used.
- Current promoted 75 MHz candidate remains:
  - Bitstream: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/NexysVideoHarness.bit`
  - Timing: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/report/timing.txt`
  - WNS `+0.040 ns`, TNS `0.000 ns`, setup failing endpoints `0`
  - WHS `+0.017 ns`, THS `0.000 ns`, hold failing endpoints `0`
- Current worst setup path remains route-dominated Rocket frontend/core timing:
  - Source `chiptop0/system/tile_prci_domain/element_reset_domain_rockettile/frontend/icache/s2_dout_0_reg[15]`
  - Destination `chiptop0/system/tile_prci_domain/element_reset_domain_rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Slack `+0.040 ns`
  - Data path delay `12.461 ns`
  - Route delay `10.257 ns`
  - Logic delay `2.204 ns`
  - Logic levels `13`
- A compact QoR audit was run on the promoted `MoreGlobalIterations + Explore` post-physopt checkpoint:
  - Runtime workspace: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-06/75mhz-wns-margin-qor-2026-06-06/`
  - Log: `qor-suggestions-promoted-moreglobal-explore-2026-06-06.log`
  - Reports: `qor_suggestions_promoted_moreglobal_explore.rpt`, `qor_assessment_promoted_moreglobal_explore.rpt`, `design_analysis_timing_promoted_moreglobal_explore.rpt`, `top25_timing_promoted_moreglobal_explore.rpt`
- QoR findings:
  - Vivado reported WNS `+0.040 ns` and WHS `+0.017 ns` for the audited checkpoint.
  - `report_qor_suggestions` did not provide an ML strategy because this routed design was not produced by a recognized default/explore full implementation strategy.
  - Netlist suggestions still point toward retiming/rebalancing:
    - `RQS_NETLIST-19`: retime across high-fanout nets; the named high-fanout reset path has slack `+0.246 ns`, so it is not the immediate WNS limiter.
    - `RQS_NETLIST-10`: rebalance timing paths by forward/backward retiming; the listed paths are Rocket frontend/icache/fq/core paths and are route dominated.
- Current interpretation:
  - The project is still at WNS `+0.040 ns`, short of the requested `+0.100 ns` target by about `0.060 ns`.
  - QMLP, ordinary Feature21 quant/writeback, and TSI are no longer the leading 75 MHz timing classes.
  - The next low-risk experiment should align with the QoR retiming hint, e.g. a post-place route/physopt variant using `route_design -directive MoreGlobalIterations` plus post-route `phys_opt_design -directive AlternateFlowWithRetiming`.

### MoreGlobal + AlternateFlowWithRetiming Check

- Ran a post-place route/physopt variant from the refreshed 75 MHz `obj/post_place.dcp`.
- Variant:
  - `route_design -directive MoreGlobalIterations`
  - post-route `phys_opt_design -directive AlternateFlowWithRetiming`
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-06/75mhz-wns-margin-physopt-2026-06-06/moreglobal_route_alternateflowretiming_phys/`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `-0.061 ns`
  - Final TNS `-0.432 ns`
  - Setup failing endpoints `9`
  - Final WHS `+0.017 ns`
  - Bitgen completed, but timing constraints were not met.
- Worst final setup path:
  - Source `chiptop0/system/tile_prci_domain/element_reset_domain_rockettile/frontend/fq/elts_0_data_reg[17]`
  - Destination `chiptop0/system/tile_prci_domain/element_reset_domain_rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Slack `-0.061 ns`
  - Data path delay `12.567 ns`
  - Route delay `10.623 ns`
  - Logic levels `12`
- Secondary failing paths included Feature21 density tail residue:
  - `radarDMA/feature21/densityQuantProductReg_reg[9] -> radarDMA/feature21/densityFeatureReg_reg[1]`, slack `-0.052 ns`
  - `densityQuantProductReg_reg[9] -> densityFeatureReg_reg[2]`, slack `-0.010 ns`
  - `densityQuantProductReg_reg[9] -> densityFeatureReg_reg[4]`, slack `-0.003 ns`
- Artifact hashes:
  - Bitstream SHA256 `94169d372a2ee51092a8cb771069486e3bb76181b5226aba4b20ede2e87c8408`
  - Timing summary SHA256 `d10fb6929fb3ea15b55b22f397e07e1ba0107669b8c7cd772f1c866b066cd3e5`
  - Post-physopt checkpoint SHA256 `b77cc0417d1686758f99aebe3ca228fa46d7a1d2962701b9bf328f2f52f4bb38`
- Interpretation:
  - Do not use this bitstream.
  - The QoR retiming hint did not translate into a better post-route candidate from this placement.
  - The current generated 75 MHz `obj` bitstream/timing remain promoted to `MoreGlobalIterations + Explore` with WNS `+0.040 ns`.
  - The practical margin gap to the requested `+0.100 ns` target remains about `0.060 ns`.

### MoreGlobal + ExploreWithHoldFix Check

- Ran another post-place route/physopt variant from the same refreshed 75 MHz `obj/post_place.dcp`.
- Variant:
  - `route_design -directive MoreGlobalIterations`
  - post-route `phys_opt_design -directive ExploreWithHoldFix`
- Runtime workspace:
  - `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-06/75mhz-wns-margin-physopt-2026-06-06/moreglobal_route_explorewithholdfix_phys/`
- Result:
  - Post-route WNS `-0.919 ns`
  - Final WNS `+0.040 ns`
  - Final TNS `0.000 ns`
  - Setup failing endpoints `0`
  - Final WHS `+0.017 ns`
  - Bitgen completed successfully.
- Worst final setup path:
  - Source `chiptop0/system/tile_prci_domain/element_reset_domain_rockettile/frontend/icache/s2_dout_0_reg[15]`
  - Destination `chiptop0/system/tile_prci_domain/element_reset_domain_rockettile/core/ex_reg_rs_msb_0_reg[49]`
  - Slack `+0.040 ns`
  - Data path delay `12.461 ns`
  - Route delay `10.257 ns`
  - Logic levels `13`
- Artifact hashes:
  - Bitstream SHA256 `3c603cd074352a4804fe72a8cf0d79c511fe2975830daed271bdb7107811c67c`
  - Timing summary SHA256 `c2027badfab1e52bc95e9ec6b58043027e625a538c1afaa6405bcc8594b28d3e`
  - Post-physopt checkpoint SHA256 `85bf4e1259382c0f7b33031cb7778fb2f30ee92d1ae3e75bc7452ab6d45e2d63`
- Interpretation:
  - This ties the promoted `MoreGlobalIterations + Explore` result but does not improve it.
  - The hold-fix part did not add hold margin or setup margin; final WHS stayed `+0.017 ns`.
  - The current promoted 75 MHz generated `obj` bitstream/timing remain unchanged at WNS `+0.040 ns`.
  - At this point, repeated post-place route/physopt directive variants have not moved the design toward the requested `+0.100 ns` setup margin.

## Checkpoint 2026-06-06 Archive Reports And Core Optimization Planning

- User decided to stop further 75 MHz margin chasing for now and keep the current promoted WNS `+0.040 ns` candidate archived.
- Created an independent timing-closure report for later FullChain v2 design input:
  - `docs/feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md`
  - Purpose: compactly archive the 75 MHz closure timeline, effective RTL cuts, failed/accepted implementation variants, and transferable lessons for FullChain v2.
- Created a forward-looking RISC-V core optimization plan:
  - `docs/riscv_core_feature21_qmlp_optimization_plan_2026-06-06.md`
  - Purpose: outline thesis-grade core/ISA co-design directions so the SoC/core part is not merely "using an open-source Rocket core."
- Recommended research direction in the core plan:
  - Define a lightweight radar/QMLP custom extension, tentatively `Xradar`.
  - Prototype first through RoCC/custom opcodes for quick validation.
  - Focus initial instructions on packed int8 dot product, Q8.8 scale/round/clamp, feature-byte pack, and accelerator-aware start/wait/status control.
  - Use CPU-only QMLP and Feature21 software/golden paths as the first measurable baselines.
  - Consider migrating one or two proven arithmetic instructions into Rocket execute-stage only after RoCC results justify the timing and implementation risk.
- Supporting references captured in the core plan:
  - Chipyard RoCC docs.
  - Rocket Chip generator report.
  - RISC-V Vector, Bitmanip, Scalar Crypto, and P-extension references.
  - Stream Semantic Registers and RI5CY/PULP DSP-extension references.
  - Instruction prefetch references as secondary/background material.
- Local fit noted:
  - Current radar config already uses `WithoutFPU` and `WithNSmallCores(1)`, so a small workload-specific extension is more plausible than adding a full RVV/BOOM-style core.
  - The current 75 MHz final limiter is Rocket frontend/core routing, so frontend/prefetch work should be profile-driven rather than the first implementation target.
- Refined the RISC-V core optimization plan after thesis-defense risk review:
  - Added the required "Why not Gemmini?" baseline question and made Phase 0 collect resource, timing, workload-shape, software-overhead, and research-fit evidence before claiming `Xradar` novelty.
  - Reframed `Xradar` as an algorithm-aware ISA/core/accelerator coupling-point design-space study rather than a simple speedup claim.
  - Added hard Phase 0 go/no-go gates for dot-product dominance, accelerator control overhead, and Gemmini feasibility.
  - Froze an initial opcode partition proposal: `custom0` for `rq*` arithmetic/data instructions and `custom1` for `racc.*` accelerator-control instructions.
  - Added a Phase 1 bit-exact golden requirement: software fallback first, including `rqscale8` round-nearest-even and clamp validation against the existing Feature21/QMLP Q8.8 samples.
- Tightened the core optimization plan after Amdahl/gate consistency review:
  - Removed whole-workload optimistic speedup wording and split benefits into kernel-local improvement versus whole-QMLP Amdahl-bounded improvement.
  - Initially recorded the idealized `s_k -> infinity` bounds to expose the conflict between dot/MAC share and whole-workload claims; this was later corrected to the finite-kernel-speedup model below.
  - Added Phase 0 counter requirements for measured fraction shares and Amdahl sensitivity calculations.
  - Added explicit fallback actions when `rqdot4`, `racc.*`, or software-visible kernel gates fail.
  - Strengthened Gemmini evidence requirements with LeanGemmini resource/timing checks and QMLP-layer utilization against Gemmini array/tile dimensions.
  - Reserved opcode/funct space for later execute-stage migration and required accumulator width/overflow behavior in the golden ISA semantics.
- Corrected the Amdahl treatment again to avoid using the unreachable `s_k -> infinity` limit as a realistic bound:
  - Whole-workload estimates now use `Speedup_total = 1 / ((1 - f) + f / s_k)`, where Phase 0 measures accelerated fraction `f` and Phase 2/3 measures finite kernel-local speedup `s_k`.
  - Example finite-kernel bounds were added: `f=40%, s_k=4x -> ~1.43x`, `f=70%, s_k=4x -> ~2.11x`, and `f=87.5%, s_k=4x -> ~2.91x`.
  - The plan now treats `1 / (1 - f)` only as the idealized `s_k -> infinity` limit and requires comparing Amdahl prediction against actual whole-workload measurements.

## Checkpoint 2026-06-08 Feature21 Batch DMA Candidate

- User observed that the Feature21 golden dump flow was too slow because it configured/reran DMA per sample and printed too much per-sample output.
- Implemented a one-shot Feature21 batch mode:
  - `FEATURE21_DMA_BATCH_MODE=1` default in `tests/Makefile`.
  - `tests/radar-axi-dma-feature21-golden.c` now packs all 1000 Feature21 golden frames into one MM2S stream, expects all output frames in one S2MM buffer, checks preprocessor counters and padding, and prints a compact summary.
  - `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala` now carries input TLAST through the Feature21 preprocessor so only the final output frame asserts TLAST in a concatenated multi-frame stream; frame count increments on completed output frames.
- Offline gates:
  - Batch ELF rebuilt: `tests/radar-axi-dma-feature21-golden.riscv`.
  - Verilog generation PASS for `RadarAXIMMIONexysVideo75MHzConfig`.
  - 75 MHz bitstream generation PASS.
- Final timing:
  - WNS `+0.016 ns`
  - TNS `0.000 ns`
  - WHS `+0.010 ns`
  - `timing.txt` reports all user specified timing constraints are met.
- Artifacts:
  - `logs/radar_nexysvideo/runtime/feature21-batch-dma-2026-06-08/artifacts/NexysVideoHarness-feature21-batch-dma-75mhz-2026-06-08.bit`
  - `logs/radar_nexysvideo/runtime/feature21-batch-dma-2026-06-08/artifacts/radar-axi-dma-feature21-golden-batch-2026-06-08.riscv`
  - `logs/radar_nexysvideo/runtime/feature21-batch-dma-2026-06-08/artifacts/timing-feature21-batch-dma-75mhz-2026-06-08.txt`
- Board status:
  - New batch bitstream is not yet board-validated.
  - The reset-interrupted summary-only run before this bitstream was generated used the old bitstream and should remain invalid evidence.
- Next board step:
  - Program the new batch-DMA bitstream, press CPU_RESET, then run the archived batch ELF at UART-TSI baudrate `115200`.

## Checkpoint 2026-06-09 Xradar dot4 Fallback/Profile Prep

- Continued the RISC-V/Xradar work according to `docs/riscv_core_feature21_qmlp_optimization_plan_2026-06-06.md`.
- Existing Phase 1 fallback files were confirmed present:
  - `tests/radar_xradar_fallback.h`
  - `tests/radar-xradar-fallback-host.c`
  - `tests/radar-xradar-static-model-host.c`
- Host/static checks pass:
  - `make -C tests xradar-host-test xradar-static-model`
  - Log: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/xradar-host-and-static-2026-06-09.log`
  - Result: `rqdot4=848`, `scalar_tail_macs=64`, `rqscale8=96`, packed MAC coverage `98.14%`.
- `tests/radar-qmlp-cpu-profile.c` now has a build-time Xradar fallback path:
  - `RADAR_QMLP_CPU_PROFILE_USE_XRADAR_FALLBACK=0`: scalar baseline profile.
  - `RADAR_QMLP_CPU_PROFILE_USE_XRADAR_FALLBACK=1`: uses `xradar_dot_i8_packed_tail()` and `xradar_rqscale8_relu_sw()` while preserving the same QMLP logits contract.
  - The fallback profile prints `xradar_ops` averages, so future board runs can compare scalar and dot4-shaped software paths before RoCC RTL.
- Board-ready profile artifacts:
  - `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-qmlp-cpu-profile-scalar-2026-06-09.riscv`
  - `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-qmlp-cpu-profile-xradar-fallback-2026-06-09.riscv`
- Current boundary:
  - This step does not implement `rqdot4` in hardware yet.
  - It establishes the software golden/profile path required before a RoCC or execute-stage implementation.

## Checkpoint 2026-06-09 Xradar RoCC `rqdot4` Prototype

- Continued the offline RISC-V/Xradar path beyond the software fallback.
- Added a minimal RoCC RTL prototype:
  - Source: `fpga/src/main/scala/nexysvideo/XradarRoCC.scala`
  - Config fragment: `WithXradarRoCC`
  - Dedicated NexysVideo config: `RadarAXIMMIOXradarRoCCNexysVideo75MHzConfig`
- Current implemented hardware semantics:
  - `custom0`, `funct7=0`, `funct3=0`
  - `rqdot4 rd, rs1, rs2`
  - Treats the low 32 bits of both source registers as four signed int8 lanes.
  - Returns the signed 4-lane dot-product result, sign-extended to `xLen`.
- Added a board smoke ELF for the future RoCC bitstream:
  - Source: `tests/radar-xradar-rocc-smoke.c`
  - Build artifact: `tests/radar-xradar-rocc-smoke.riscv`
  - Size: text `8366`, data `16`, bss `0`.
  - The smoke test compares hardware `rqdot4` against `xradar_rqdot4_sw()` and then runs 8 QMLP semantic cases through a RoCC-dot4 path.
- Offline verification:
  - `make -C tests radar-xradar-rocc-smoke.riscv` PASS after loading `env.sh`.
  - `git diff --check` PASS for the RoCC source/config/test changes.
  - `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIOXradarRoCCNexysVideo75MHzConfig verilog` PASS.
  - Log: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/xradar-rocc-verilog-75mhz-2026-06-09.log`
  - Generated RTL evidence: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIOXradarRoCCNexysVideo75MHzConfig/gen-collateral/RocketTile.sv` contains four signed int8 multiply lanes and the RoCC response data mux.
- Current boundary:
  - This is not yet a timing-clean bitstream.
  - This is not yet board-validated.
  - `rqscale8`, `rqpack`, and `racc.*` remain unimplemented in RoCC RTL.
- Next offline gate:
  - Build a 75 MHz bitstream for `RadarAXIMMIOXradarRoCCNexysVideo75MHzConfig`.
  - Inspect final timing, especially whether the added RoCC path perturbs the already tight Rocket frontend/core timing.
- Next board gate:
  - Program the new RoCC bitstream.
  - Press CPU_RESET.
  - Run `tests/radar-xradar-rocc-smoke.riscv` over UART-TSI at `115200`.

## Checkpoint 2026-06-09 Xradar RoCC 75 MHz Implementation Gate

- Ran the first 75 MHz implementation attempt for `RadarAXIMMIOXradarRoCCNexysVideo75MHzConfig`.
- Outcome:
  - Vivado wrote a bitstream, but the make timing gate failed.
  - Final timing: WNS `-0.330 ns`, TNS `-29.441 ns`, WHS `+0.016 ns`, THS `0.000 ns`.
  - Treat this bitstream as timing-fail evidence, not as a formal board baseline.
- Worst final setup path:
  - Source: RoCC command queue RAM under `cmdRouter/cmd_q`.
  - Middle: `xradar_p0` DSP path.
  - Destination: RoCC response arbiter queue RAM under `respArb_io_in_0_q`.
  - This confirms the current combinational `rqdot4` response path is the immediate timing issue introduced by the prototype.
- DRC evidence:
  - `xradar_p0..p3` DSP inputs are not pipelined.
  - `xradar_p0..p3` DSP multiplier/output stages are not pipelined.
  - This matches the timing report and points to a registered/pipelined RoCC datapath as the next design step.
- Archived artifacts:
  - Bitstream: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/NexysVideoHarness-xradar-rocc-75mhz-timingfail-2026-06-09.bit`
  - Timing: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/timing-xradar-rocc-75mhz-timingfail-2026-06-09.txt`
  - DRC: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/drc-xradar-rocc-75mhz-timingfail-2026-06-09.txt`
  - Utilization: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/utilization-xradar-rocc-75mhz-timingfail-2026-06-09.txt`
  - Checksums: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/SHA256SUMS.txt`
- Next offline gate:
  - Convert `XradarRoCC` from a combinational response into a multi-cycle ready/valid design.
  - Register command operands, register DSP products, register the sum/response, and keep `io.busy` asserted while an in-flight command waits to respond.
  - Re-run Verilog and 75 MHz bitstream timing before asking for board validation.

## Checkpoint 2026-06-09 Xradar RoCC Pipelined 75 MHz Timing-Clean Candidate

- Implemented the next offline gate after the failed one-cycle RoCC attempt.
- RTL change:
  - `XradarRoCC` now uses a multi-cycle ready/valid microarchitecture.
  - Command operands and destination register are captured first.
  - Four int8 products are registered.
  - The dot-product sum is registered.
  - The response is emitted from a dedicated response state, with `io.busy` asserted while a command is in flight.
- Verification:
  - `git diff --check` PASS for the RoCC/docs changes.
  - `make -C tests radar-xradar-rocc-smoke.riscv` PASS after loading `env.sh`.
  - `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIOXradarRoCCNexysVideo75MHzConfig verilog` PASS.
  - `make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIOXradarRoCCNexysVideo75MHzConfig bitstream` PASS.
- Final timing:
  - WNS `+0.004 ns`
  - TNS `0.000 ns`
  - WHS `+0.009 ns`
  - THS `0.000 ns`
  - All user timing constraints are met.
- Interpretation:
  - The combinational RoCC DSP/response path was a real issue and has been addressed by pipelining.
  - During the successful run, the hard optimization work shifted to existing Rocket frontend/core-div paths rather than the Xradar dot4 path.
  - The resulting slack is very small, so this is a board-test candidate rather than a large-margin timing baseline.
- Archived artifacts:
  - Bitstream: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/NexysVideoHarness-xradar-rocc-pipelined-75mhz-timingclean-2026-06-09.bit`
  - Timing: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/timing-xradar-rocc-pipelined-75mhz-timingclean-2026-06-09.txt`
  - DRC: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/drc-xradar-rocc-pipelined-75mhz-timingclean-2026-06-09.txt`
  - Utilization: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/utilization-xradar-rocc-pipelined-75mhz-timingclean-2026-06-09.txt`
  - Checksums: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/SHA256SUMS.txt`
- Next board gate:
  - Program the pipelined timing-clean bitstream.
  - Press CPU_RESET.
  - Run `tests/radar-xradar-rocc-smoke.riscv` over UART-TSI at `115200`.
  - Treat a PASS as functional validation for `rqdot4` only; `rqscale8`, `rqpack`, and `racc.*` remain unimplemented in RoCC RTL.

## Checkpoint 2026-06-09 Xradar RoCC Board Bring-Up Partial Pass

- Programmed the timing-clean pipelined RoCC bitstream:
  - Bitstream: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/NexysVideoHarness-xradar-rocc-pipelined-75mhz-timingclean-2026-06-09.bit`
  - Program log: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/program-xradar-rocc-pipelined-75mhz-2026-06-09.log`
  - Result: `PROGRAM_DONE`
  - The Vivado `no supported debug core(s)` message is expected because this design has no ILA/VIO debug cores.
- Confirmed artifact checksums from repo root:
  - `sha256sum -c logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/SHA256SUMS.txt`
  - Result: all listed original timing/bitstream artifacts passed.
- First full-smoke board attempt exposed a software encoding issue:
  - Original inline asm used `.insn r CUSTOM_0, 0, 0`, which encoded RoCC `xd/xs1/xs2=0`.
  - Board log showed first basic case `got=-66847231`, expected `-70`.
  - `-66847231` is `0xfc03fe01`, matching the packed `rs1` operand; this is consistent with no RoCC writeback rather than a valid arithmetic result.
  - Log: `logs/radar_nexysvideo/runtime/xradar-rocc-smoke-75mhz-2026-06-09-2026-06-09-201352.log`
- Fixed the smoke test instruction encoding:
  - Source: `tests/radar-xradar-rocc-smoke.c`
  - Change: encode `funct3=7`, so `xd/xs1/xs2=1`.
  - Rebuilt ELF: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-xradar-rocc-smoke-funct3fix-2026-06-09.riscv`
  - Fixed full smoke status: selfcheck passed, but the run timed out before visible HTIF output; not a full PASS.
- Added and ran a smaller single-instruction memory probe:
  - Source: `tests/radar-xradar-rocc-single-probe.c`
  - ELF: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-xradar-rocc-single-probe-funct3fix-2026-06-09.riscv`
  - Probe writes status words around one `rqdot4` instruction and then leaves the values readable through UART-TSI.
  - Board readback:
    - `0x80003000 -> 0x11110000`
    - `0x80003008 -> 0xfc03fe01`
    - `0x80003010 -> 0x08f906fb`
    - `0x80003018 -> 0xffffffba`
    - `0x80003020 -> 0x2222aaaa`
  - Expected arithmetic: `0xfc03fe01` packs `{1, -2, 3, -4}`, `0x08f906fb` packs `{-5, 6, -7, 8}`, and the signed int8 dot product is `1*(-5) + (-2)*6 + 3*(-7) + (-4)*8 = -70`.
  - Interpretation: the single board-executed `rqdot4` returned `-70` and passed the probe status check.
- Durable status note:
  - `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-board-status-2026-06-09.md`
- Current boundary:
  - The board now has partial functional validation for `rqdot4` arithmetic on the timing-clean bitstream.
  - Do not report the full QMLP semantic smoke as PASS yet.
  - Next debug should isolate whether the fixed full-smoke timeout is due to HTIF/printf interaction, repeated RoCC command sequencing, or another software-side issue.

## Checkpoint 2026-06-09 Xradar RoCC Memory-Smoke Board PASS

- After a fresh CPU reset, added and ran a memory-based smoke test to avoid the printable HTIF path:
  - Source: `tests/radar-xradar-rocc-memory-smoke.c`
  - ELF: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-xradar-rocc-memory-smoke-funct3fix-2026-06-09.riscv`
  - The program writes probe/status words to `0x80010000` and then stays in a loop, allowing UART-TSI readback.
  - The program uses `funct3=7`, so RoCC `xd/xs1/xs2=1`.
- Load/selfcheck:
  - Command shape: `scripts/run_nexysvideo_uart_tsi.sh --tty /dev/ttyUSB0 --baudrate 115200 --bin ...memory-smoke...`
  - Log: `logs/radar_nexysvideo/runtime/xradar-rocc-memory-smoke-funct3fix-75mhz-2026-06-09-2026-06-09-204609.log`
  - Selfcheck passed over all ELF chunks.
  - The run ended by timeout because the memory-smoke intentionally does not call `exit`.
- Board readback summary:
  - Stage: `0x7777aaaa`
  - Fail code: `0`
  - Basic pass mask: `0x0f` -> 4/4 basic `rqdot4` cases passed.
  - QMLP pass mask: `0xff` -> 8/8 QMLP semantic cases passed.
  - Cases completed: basic `4`, QMLP `8`.
  - Counts: `rqdot4_ops=848`, `scalar_tail_macs=64`, `rqscale8_ops=96`, `total_macs=3456`, packed MAC coverage x100 `9814`.
  - Case-detail table: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-memory-smoke-readback-2026-06-09.md`
- Interpretation:
  - This validates repeated RoCC command sequencing and the QMLP semantic path for the current `rqdot4` scope on the timing-clean 75 MHz bitstream.
  - The earlier printable full smoke timeout should now be treated as an HTIF/printf/debug-output issue, not as the primary functional verdict.
  - `rqscale8`, `rqpack`, and `racc.*` remain unimplemented in RoCC RTL.

## Checkpoint 2026-06-09 Xradar RoCC Memory-Smoke Repeat After Reset

- After another fresh CPU reset, reran the same memory-smoke ELF:
  - ELF: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-xradar-rocc-memory-smoke-funct3fix-2026-06-09.riscv`
  - Load log: `logs/radar_nexysvideo/runtime/xradar-rocc-memory-smoke-repeat-after-reset-75mhz-2026-06-09-2026-06-09-205440.log`
  - Selfcheck: PASS over all chunks.
  - Runtime ended by timeout as expected because memory-smoke intentionally does not call `exit`.
- Repeat readback summary:
  - Stage: `0x7777aaaa`
  - Fail code: `0`
  - Basic pass mask: `0x0f`
  - QMLP pass mask: `0xff`
  - Cases completed: basic `4`, QMLP `8`
  - Counts stayed consistent: `rqdot4_ops=848`, `scalar_tail_macs=64`, `rqscale8_ops=96`, packed MAC coverage x100 `9814`.
- Interpretation:
  - The memory-smoke board PASS is repeatable across a fresh reset.
  - Next useful validation layer is not another identical functional smoke, but either a multi-iteration stress test or a cycle/profile probe comparing scalar vs RoCC `rqdot4` paths.

## Checkpoint 2026-06-09 Xradar RoCC Printable Smoke Timeout Resolved

- Investigated the earlier fixed-smoke timeout rather than leaving it as an open issue.
- Added a minimal HTIF/printf probe:
  - Source: `tests/radar-xradar-rocc-htif-probe.c`
  - ELF: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-xradar-rocc-htif-probe-funct3fix-2026-06-09.riscv`
  - Log: `logs/radar_nexysvideo/runtime/xradar-rocc-htif-probe-funct3fix-75mhz-2026-06-09-2026-06-09-210454.log`
  - Result: PASS. It printed before/after one `rqdot4`, returned `got=-70 expected=-70`, printed `PASSED`, and exited.
  - Interpretation: HTIF/printf is not generally broken on this RoCC bitstream.
- Fixed the printable full smoke software:
  - Source: `tests/radar-xradar-rocc-smoke.c`
  - Prior fixes: `funct3=7`, so RoCC `xd/xs1/xs2=1`.
  - New fix: replace unsupported bare-metal `%-20s` with `%s`.
  - ELF: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-xradar-rocc-smoke-funct3fix-printfix-2026-06-09.riscv`
- Board result after fresh CPU reset:
  - Log: `logs/radar_nexysvideo/runtime/xradar-rocc-smoke-funct3fix-printfix-after-reset-75mhz-2026-06-09-2026-06-09-210735.log`
  - Selfcheck: PASS.
  - Printed all 8 QMLP semantic cases.
  - Counts: `rqdot4=848`, `scalar_tail_macs=64`, `rqscale8=96`, `total_macs=3456`, packed MAC coverage x100 `9814`.
  - Final line: `[XRADAR-ROCC] PASSED`.
- Updated interpretation:
  - Printable smoke timeout is resolved.
  - The root cause was software-side test formatting/encoding, not RoCC arithmetic or repeated-command behavior.
  - Current board status for the implemented `rqdot4` scope is PASS.
  - Still-open architecture scope: `rqscale8`, `rqpack`, and `racc.*` are not implemented in RoCC RTL.

## Checkpoint 2026-06-09 Xradar RoCC Debug Lessons Synced

- Synced the board-debug root causes into repo docs, Codex memory, and the local Obsidian notes so future continuation windows do not reopen the same failure modes.
- Durable source of truth:
  - Board status: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-board-status-2026-06-09.md`
  - Docs map: `docs/README.md`
  - Obsidian work log: `/home/soooarr/obsidian/Codex/Chipyard/Research Notes/Xradar Work Log.md`
- Debug carryover:
  - Use `.insn r CUSTOM_0, 7, 0, rd, rs1, rs2` for RoCC `rqdot4`. `funct3=7` requests `xd/xs1/xs2`; `funct3=0` caused the packed-`rs1` symptom `0xfc03fe01`.
  - Avoid unsupported bare-metal printf width/left-align formats such as `%-20s`; this was the reason the printable smoke appeared to timeout after the arithmetic path already passed.
  - Treat memory-smoke timeout as expected only because that program intentionally spins for UART-TSI readback. Judge it by DDR status words: stage `0x7777aaaa`, fail `0`, basic mask `0x0f`, QMLP mask `0xff`.
  - For future board tests, use `/dev/ttyUSB0` at `115200` and press `CPU_RESET` before each fresh ELF load.

## Checkpoint 2026-06-09 Xradar RoCC Scalar-vs-Dot4 Cycle Profile

- User had already pressed CPU_RESET, so the next scalar-vs-RoCC comparison was run as a single board test rather than two separate ELF loads.
- Added a combined profile ELF:
  - Source: `tests/radar-xradar-rocc-cycle-profile.c`
  - Build target: `tests/radar-xradar-rocc-cycle-profile.riscv`
  - Archived ELF: `logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/radar-xradar-rocc-cycle-profile-2026-06-09.riscv`
  - SHA256: `1c80410352d9cc3673f4bddfd4c1f1c1288cf1e39c88360165aeab40116e8e2d`
- Board command:
  - `timeout 240s scripts/run_nexysvideo_uart_tsi.sh --tty /dev/ttyUSB0 --baudrate 115200 --bin tests/radar-xradar-rocc-cycle-profile.riscv --log-name xradar-rocc-cycle-profile-75mhz-2026-06-09`
- Log:
  - `logs/radar_nexysvideo/runtime/xradar-rocc-cycle-profile-75mhz-2026-06-09-2026-06-09-215919.log`
  - SHA256: `991993c1672ccc9aabe46206b985dbc3a34ef3d016e531e9cf2e45898c67462e`
- Selfcheck:
  - PASS over all chunks.
- Result:
  - Scalar QMLP: `count=1600`, `cycles_avg=168203`, `instret_avg=26686`.
  - RoCC `rqdot4` QMLP: `count=1600`, `cycles_avg=62532`, `instret_avg=35016`.
  - RoCC ops per inference: `rqdot4_avg=848`, `scalar_tail_macs_avg=64`, `rqscale8_avg=96`, packed MAC coverage x100 `9814`.
  - Reported speedup: `speedup_x1000=2689`, i.e. about `2.689x` for this scalar-vs-RoCC QMLP kernel comparison.
  - Final line: `[XRADAR-PROFILE] PASSED`.
- Interpretation:
  - This is the first board-measured speedup evidence for the implemented `rqdot4` RoCC path.
  - The result is kernel/QMLP-profile evidence, not a full Feature21+QMLP end-to-end system speedup.
  - `rqscale8` is still software in this comparison; `rqscale8`, `rqpack`, and `racc.*` remain unimplemented in RoCC RTL.
