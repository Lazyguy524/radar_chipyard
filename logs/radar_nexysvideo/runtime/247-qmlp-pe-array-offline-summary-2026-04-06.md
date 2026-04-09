# QMLP 阵列化原型离线阶段摘要

更新时间：2026-04-06

当前状态：

- 已在独立分支 `radar-qmlp-pe-array-v1` 上开展实现
- `RadarAXISQMLP` 已从串行逐 MAC 重构为 4 路并行 `PE/MAC` 累加
- 软件测试入口保持不变
- `Nexys Video` 定向 `verilog` 生成通过
- bitstream 正在后台构建

本轮最关键的判断：

1. 方向选择上，已从“固定功能 QMLP”进入“可讲清楚的阵列化原型”阶段
2. 这轮改动没有扩散到 DMA/DDR/CPU 接口层，后续板测风险相对可控
3. 理论主体计算周期由 `3456` 次逐 MAC，收缩为约 `912` 个 4-lane MAC 累加周期

关键文件：

- 设计说明：
  [radar_qmlp_pe_array_prototype_2026-04-06.md](/home/soooarr/chipyard/docs/radar_qmlp_pe_array_prototype_2026-04-06.md)
- 硬件实现：
  [RadarQMLP.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarQMLP.scala)
- 软件构建日志：
  [244-build-qmlp-pe-array-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/244-build-qmlp-pe-array-2026-04-06.log)
- RTL 生成日志：
  [245-fpga-verilog-qmlp-pe-array-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/245-fpga-verilog-qmlp-pe-array-2026-04-06.log)
- bitstream 日志：
  [246-fpga-bitstream-qmlp-pe-array-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/246-fpga-bitstream-qmlp-pe-array-2026-04-06.log)
