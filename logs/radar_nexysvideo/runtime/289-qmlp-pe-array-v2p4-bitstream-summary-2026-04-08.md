# QMLP PE-array v2.4 bitstream 摘要（2026-04-08）

## 版本说明

- 分支：`radar-qmlp-pe-array-v2p4`
- 目标：
  - 保持 `PE` 阵列，不再像 `v2.2/v2.3` 那样通过削弱并行度换稳定性
  - 针对 `accReg -> requant -> 写回` 这条关键路径做结构级拆分
- 相比 `v2.3` 的主要改动：
  - 将 `peLanes` 从 `2` 恢复为 `4`
  - 将 `L1/L2` 的量化路径从单拍逻辑拆成：
    - `QuantMul`
    - `QuantRound`
    - `Write`
  - 保留 `L3Pack` 单独打包输出的结构
  - 目标是用更短的组合路径恢复 4-lane 并行度，而不是继续收缩架构

## 离线结果

- `verilog` 通过：
  [287-fpga-verilog-qmlp-pe-array-v2p4-2026-04-08.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/287-fpga-verilog-qmlp-pe-array-v2p4-2026-04-08.log)
- `bitstream` 通过：
  [288-fpga-bitstream-qmlp-pe-array-v2p4-2026-04-08.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/288-fpga-bitstream-qmlp-pe-array-v2p4-2026-04-08.log)

## 时序结果

- `WNS = 0.337 ns`
- `WHS = 0.050 ns`
- `All user specified timing constraints are met`
- `The design met the timing requirement`
- `write_bitstream completed successfully`

## 资源结果

### 顶层

- `LUT = 27682`
- `FF = 17943`
- `RAMB36 = 2`
- `RAMB18 = 14`
- `DSP = 14`

### RadarAXIDMA

- `LUT = 4996`
- `FF = 4701`
- `RAMB36 = 2`
- `RAMB18 = 2`
- `DSP = 4`

### RadarAXISQMLP

- `LUT = 2613`
- `FF = 1990`
- `RAMB = 0`
- `DSP = 4`

## 与前几版对比

### 相比 v2.2

- `v2.2`：`2-lane`, `WNS = 0.266 ns`
- `v2.4`：`4-lane`, `WNS = 0.337 ns`

结论：
- 在恢复 `4-lane PE` 的同时，`v2.4` 的 setup 余量反而比 `v2.2` 更好
- 这说明“拆 requant 路径”比“单纯降并行度”更有效

### 相比 v2.3

- `v2.3`：`2-lane + reset/fanout 小修`, `WNS = 0.140 ns`
- `v2.4`：`4-lane + quant 结构拆分`, `WNS = 0.337 ns`

结论：
- `v2.4` 明显优于 `v2.3`
- 本轮收益主要来自结构级时序切分，而不是 reset/fanout 小刀法

## 当前判断

- `v2.4` 是目前离线结果最好的 `PE-array` 版本之一：
  - 保留 `4-lane PE`
  - 时序通过
  - 余量优于 `v2.2/v2.3`
- 当前值得优先作为下一轮上板候选
- 下一步重点不再是继续削弱阵列，而是：
  - 直接做板级 smoke
  - 观察 `init_read / ELF 装载 / QMLP RUN_CYCLES`
  - 判断 `v2.4` 是否真正把此前的读回不稳问题压下去

## 归档

- 本轮 bit 与报告已备份到：
  [qmlp_pe_array_v2p4_2026-04-08](/home/soooarr/chipyard/logs/radar_nexysvideo/bit_backups/qmlp_pe_array_v2p4_2026-04-08)
