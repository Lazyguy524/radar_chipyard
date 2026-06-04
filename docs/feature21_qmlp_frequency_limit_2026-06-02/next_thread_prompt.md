# Next Thread Prompt: Feature21/QMLP 60 MHz Closure and UART-TSI Timing

工作区：`/home/soooarr/chipyard`

请不要恢复旧长对话，也不要依赖旧 thread 的隐式上下文。请先读取：

- `docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md`

当前状态要点：

- 已修复/验证基础频率 sweep 问题：
  - NexysVideo frequency configs 已参数化到 50/51.282051/55/60/65/66.666667/75 MHz。
  - harness `dutFreqMHz` 已用 `Double`，避免 fractional MHz elaboration 失败。
  - 100 MHz status LED reset 已改为本地同步 reset，旧 60 MHz `clk_out1_harnessSysPLLNode -> sys_clock` 失败路径不再是 top failure。
- UART-TSI/TSIToTileLink 排查结论：
  - UART-TSI 是 board bring-up/debug/ELF load 的 TileLink master，不是 QMLP compute datapath。
  - NexysVideo config 启用 `testchipip.tsi.WithUARTTSIClient` 并 `WithNoUART`，默认挂到 `FBUS`。
  - 当前已在 `generators/testchipip/src/main/scala/tsi/PeripheryUARTTSI.scala` 的 `tlbus.coupleFrom("uart_tsi")` 边界加入 `TLBuffer(BufferParams.pipe)`。
- 最新 60 MHz bitstream/timing：
  - Log: `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/tsi-buffer-experiment-2026-06-03/bitstream-60mhz-tsi-buffer-vivado2022p2-2026-06-03.log`
  - Timing: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo60MHzConfig/obj/report/timing.txt`
  - Bitstream 已写出：`fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo60MHzConfig/obj/NexysVideoHarness.bit`
  - Final WNS `-1.578 ns`, TNS `-276.127 ns`, 293 failing endpoints。
  - `sys_clock` clean；失败集中在 intra-DUT `clk_out1_harnessSysPLLNode`。

最新 top path 归属：

- Worst QMLP:
  - `radarDMA/qmlp/outIdx_reg[1]_replica -> radarDMA/qmlp/accReg_reg[27]`
  - Slack `-1.578 ns`
  - 当前判断：`outIdx -> async weight ROM address/data -> lane multiply/sum -> accReg`
  - 相关源码：`fpga/src/main/scala/nexysvideo/RadarQMLP.scala`
- Feature21:
  - `radarDMA/feature21/featureQ8p8Reg_reg[0] -> radarDMA/feature21/featureByteRegs_11_reg[1]`
  - Slack `-1.530 ns`
  - 当前判断：`featureQ8p8Reg -> quantQ8p8 -> selectedFeatureByte -> featureByteRegs(featureIdx)`
  - 相关源码：`fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
- Buffered UART-TSI:
  - `chiptop0/system/fbus/tsi2tl/addr_reg[5] -> chiptop0/system/fbus/coupler_from_uart_tsi/buffer/nodeOut_a_q/ram_reg[51]`
  - Slack `-1.508 ns`
  - 当前判断：边界 buffer 有效但不够；`TSIToTileLink` 内部仍然直接组合生成 TL A-channel。
  - 相关源码：`generators/testchipip/src/main/scala/tsi/TSIToTileLink.scala`

请继续做：

1. 先用简短中文复述当前状态和证据文件，不展开大日志。
2. 优先研究 60 MHz closure：
   - QMLP async-ROM/MAC staging 方案：给出最小 RTL 改动方案，必要时实现并跑 `firrtl`/`verilog`。
   - Feature21 quant/writeback split 方案：给出最小 RTL 改动方案，必要时实现并跑 `firrtl`/`verilog`。
   - 保持 TSI path 在 watch list；若继续 TSI，实验方向是 `TSIToTileLink` 内部 one-entry registered A-channel request stage。
3. 功能验证入口：
   - `tests/radar-axi-dma-feature21.c`
   - `tests/radar-axi-dma-feature21-golden.c`
   - `tests/radar-axi-dma-qmlp.c`
   - `tests/radar-axi-dma-qmlp-validation.c`
   - `tests/radar-axi-dma-qmlp-chain-validation.c`
   - `tests/radar-axi-dma-regression.c`
4. 全程避免 compact：
   - 不展开完整 timing/report/log。
   - 查文件优先用 `rg`/`sed`/`tail`。
   - 每完成一个阶段，更新 `rolling_summary.md`。
   - 如果要开始新一轮 bitstream 或上下文明显变长，提醒开下一阶段 thread。
