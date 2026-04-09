# QMLP PE Array v2.5 Bitstream Summary (2026-04-09)

## 1. 版本定位

- 分支：`radar-qmlp-pe-array-v2p5`
- 目标：修复 `v2.4` 在板上暴露出的不稳定行为，同时保持 `4-lane PE` 阵列，不走“降并行度”回退路线。

## 2. 本轮改动

本轮保持 `RadarAXISQMLP` 的 `4-lane PE/MAC` 结构不变，只调整 `L1/L2` 的 requant 实现方式：

- 保留：
  - `4-lane PE`
  - `Load -> Mac -> Quant -> Write` 分阶段状态机
  - `L3` 原有输出路径
- 修改：
  - 将 `L1/L2` 的小常数 requant 乘法从
    - `accReg * multiplier`
    改为
    - `constMultiplyShiftAdd(accReg, multiplier, 64)`
  - 其中常数为：
    - `l1Multiplier = 1516 (0x5ec)`
    - `l2Multiplier = 608 (0x260)`

这样做的目的不是改变算法，而是减少 DSP 参与和布局布线扰动，尽量降低对系统其他路径的影响。

## 3. 离线实现结果

构建日志：
- `verilog`：[337-fpga-verilog-qmlp-pe-array-v2p5-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/337-fpga-verilog-qmlp-pe-array-v2p5-2026-04-09.log)
- `bitstream`：[338-fpga-bitstream-qmlp-pe-array-v2p5-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/338-fpga-bitstream-qmlp-pe-array-v2p5-2026-04-09.log)

结果：
- `route_design completed successfully`
- `write_bitstream completed successfully`
- `The design met the timing requirement`
- `All user specified timing constraints are met`

时序：
- `WNS = 3.385 ns`
- `WHS = 0.248 ns`

## 4. 资源情况

顶层关键资源：
- `radarDMA / RadarAXIDMA`
  - `LUT = 5239`
  - `FF = 4710`
  - `DSP = 2`
- `qmlp / RadarAXISQMLP`
  - `LUT = 2858`
  - `FF = 1999`
  - `DSP = 0`

## 5. 与 v2.4 的对比

`v2.4`：
- `WNS = 0.337 ns`
- `WHS = 0.050 ns`
- `RadarAXISQMLP DSP = 4`

`v2.5`：
- `WNS = 3.385 ns`
- `WHS = 0.248 ns`
- `RadarAXISQMLP DSP = 0`

结论：
- `v2.5` 在不降低 `PE` 并行度的前提下，时序余量明显放大。
- `v2.5` 的 `QMLP` 本体不再占用 DSP，这说明常数乘改写确实改变了实现风格。

## 6. 当前判断

`v2.5` 是当前最值得上板验证的 PE 阵列版本，原因有三点：

- 保留了 `4-lane PE`，没有牺牲阵列结构
- 离线时序余量明显优于 `v2.4`
- 常数 requant 路径从 DSP 型实现改成移位加法后，更有希望减轻此前怀疑的布局扰动问题

## 7. 已留档内容

备份目录：
- [qmlp_pe_array_v2p5_2026-04-09](/home/soooarr/chipyard/logs/radar_nexysvideo/bit_backups/qmlp_pe_array_v2p5_2026-04-09)

已保存：
- `NexysVideoHarness.bit`
- `timing.txt`
- `utilization.txt`
- `338` bitstream 日志
- `RadarQMLP.scala.snapshot`

## 8. 下一步

建议上板后按以下顺序验证：

1. `init_write / init_read` 最小探针
2. `hello.riscv`
3. `hello.riscv + selfcheck`
4. `regression.riscv + selfcheck`
5. `QMLP` 单项和多样本

重点观察：
- `0x80000980..0x8000098c` 固定窗口是否恢复
- `hello + selfcheck` 是否稳定
- `QMLP RUN_CYCLES` 是否能重新拿到
