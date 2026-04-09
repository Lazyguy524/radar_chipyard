# QMLP PE-array v2.2 bitstream 摘要（2026-04-08）

## 版本说明

- 分支：`radar-qmlp-pe-array-v2p2`
- 主要改动：
  - 保留 `v2.1` 的分阶段 `Load / MAC / Quant / Write / Pack` 结构
  - 将 `PE` 并行度从 `4-lane` 降为 `2-lane`
  - 目标是优先恢复板级读回稳定性，而不是继续追求激进吞吐

## 离线结果

- `verilog` 通过：
  [281-fpga-verilog-qmlp-pe-array-v2p2-2026-04-07.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/281-fpga-verilog-qmlp-pe-array-v2p2-2026-04-07.log)
- `bitstream` 通过：
  [282-fpga-bitstream-qmlp-pe-array-v2p2-2026-04-07.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/282-fpga-bitstream-qmlp-pe-array-v2p2-2026-04-07.log)

## 时序结果

- `WNS = 0.266 ns`
- `WHS = 0.050 ns`
- `All user specified timing constraints are met`
- `write_bitstream completed successfully`

## 资源结果

### 顶层

- `LUT = 27555`
- `FF = 17868`
- `RAMB36 = 2`
- `RAMB18 = 14`
- `DSP = 10`

### RadarAXIDMA

- `LUT = 4922`
- `FF = 4626`
- `RAMB36 = 2`
- `RAMB18 = 2`

### RadarAXISQMLP

- `LUT = 2435`
- `FF = 1915`
- `RAMB = 0`
- `DSP = 0`

## 与上一版 v2.1 对比

- `v2.1`：`WNS = 0.265 ns`
- `v2.2`：`WNS = 0.266 ns`

时序余量几乎持平，没有恶化。

- 顶层 `LUT`：
  - `v2.1 = 28093`
  - `v2.2 = 27555`

整体资源略有下降。

## 当前判断

- `v2.2` 从离线实现角度是可继续上板验证的。
- 由于 `v2.1` 的板测问题更像“读事务返回链路不稳”，`v2.2` 的价值在于：
  - 保守收缩 `PE` 并行度
  - 尝试降低全局布线/扇出压力
  - 观察板上 `init_read` 与 `ELF` 装载是否恢复
