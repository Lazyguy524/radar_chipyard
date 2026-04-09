## QMLP PE-array v2.1 bitstream 摘要

- 时间：2026-04-07
- 分支：`radar-qmlp-pe-array-v2p1`
- RTL：`fpga/src/main/scala/nexysvideo/RadarQMLP.scala`
- Verilog 日志：
  `logs/radar_nexysvideo/runtime/259-fpga-verilog-qmlp-pe-array-v2p1-2026-04-07.log`
- Bitstream 日志：
  `logs/radar_nexysvideo/runtime/260-fpga-bitstream-qmlp-pe-array-v2p1-2026-04-07.log`

### 结论

- `v2.1` bitstream 已成功生成。
- Vivado 时序约束满足，可以继续上板验证。
- 本轮改动目标是继续切分 `QMLP` 写回侧时序路径：
  - `L1Mac -> L1Quant -> L1Write`
  - `L2Mac -> L2Quant -> L2Write`
  - `L3Write -> L3Pack`

### 时序

- `WNS = 0.265 ns`
- `WHS = 0.050 ns`
- `All user specified timing constraints are met`

对比上一版 `v2`：

- `v2`：`WNS = 0.146 ns`
- `v2.1`：`WNS = 0.265 ns`

说明本轮切分后，setup 余量有改善，但整体仍然属于贴边收敛。

### 资源

- 顶层 `NexysVideoHarness`
  - `LUT = 28093`
  - `FF = 17867`
  - `RAMB36 = 2`
  - `RAMB18 = 14`
  - `DSP = 10`

- `radarDMA / RadarAXIDMA`
  - `LUT = 5217`
  - `FF = 4625`
  - `RAMB36 = 2`
  - `RAMB18 = 2`

- `qmlp / RadarAXISQMLP`
  - `LUT = 2289`
  - `FF = 1916`
  - `RAMB = 0`
  - `DSP = 0`

### 当前判断

- `v2.1` 比 `v2` 更适合作为新的板测候选版本。
- 但它仍然不是“大余量”设计，板测时仍需重点观察：
  - `init_read` 是否恢复稳定
  - `QMLP` 多样本是否真正跑进主体
  - `RUN_CYCLES` 是否能拿到有效值
