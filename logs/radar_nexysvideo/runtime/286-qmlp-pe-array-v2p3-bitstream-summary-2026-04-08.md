# QMLP PE-array v2.3 bitstream 摘要（2026-04-08）

## 版本说明

- 分支：`radar-qmlp-pe-array-v2p3`
- 相比 `v2.2` 的主要改动：
  - 删除未参与功能的数据接收侧寄存器：`recvByteCount`、`sawLast`
  - 将 `quantReg` 改为无复位寄存器
  - 将 `outBitsReg` 改为无复位寄存器
- 目标：
  - 继续降低 `QMLP` 内部 reset/fanout 压力
  - 尝试提升板级稳定性，而不是改变算法行为

## 离线结果

- `verilog` 通过：
  [284-fpga-verilog-qmlp-pe-array-v2p3-2026-04-08.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/284-fpga-verilog-qmlp-pe-array-v2p3-2026-04-08.log)
- `bitstream` 通过：
  [285-fpga-bitstream-qmlp-pe-array-v2p3-2026-04-08.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/285-fpga-bitstream-qmlp-pe-array-v2p3-2026-04-08.log)

## 时序结果

- `WNS = 0.140 ns`
- `WHS = 0.051 ns`
- `All user specified timing constraints are met`
- `write_bitstream completed successfully`

## 资源结果

### 顶层

- `LUT = 27555`（与 v2.2 顶层基本同量级）
- `FF = 17868`（顶层总量级基本同量级）
- `RAMB36 = 2`
- `RAMB18 = 14`
- `DSP = 10`

### RadarAXIDMA

- `LUT = 4884`
- `FF = 4630`

### RadarAXISQMLP

- `LUT = 2344`
- `FF = 1918`
- `RAMB = 0`
- `DSP = 0`

## 与 v2.2 对比

- `v2.2`：`WNS = 0.266 ns`
- `v2.3`：`WNS = 0.140 ns`

结论：
- `v2.3` 在资源上略有下降
- 但 setup 余量反而变差
- 因此这次“小刀法 reset/fanout 收缩”没有带来明显的离线时序收益

## 当前判断

- `v2.3` 仍然是可综合、可烧录版本
- 但从离线结果看，它**不比 v2.2 更值得优先上板**
- 如果后续继续上板验证，优先级建议仍是：
  1. `v2.2`
  2. 再考虑更强一点的结构级优化版本
