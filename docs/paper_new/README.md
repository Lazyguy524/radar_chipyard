# Chipyard 雷达 SoC 论文知识库

Date: 2026-06-09

本目录是当前 `Chipyard + Nexys Video + Rocket + DDR + AXI DMA + Feature21 + QMLP + Xradar RoCC` 项目的论文事实源。它不是旧 `docs/paper/` 的替代移动，而是一个新的、以毕业论文和答辩图为目标的中文知识地图。

## 阅读顺序

1. [00_project_requirements_and_memory.md](00_project_requirements_and_memory.md)：写作偏好、Obsidian 习惯、后续窗口延续规则。
2. [01_system_overview.md](01_system_overview.md)：整体 SoC 与加速器边界。
3. [02_data_contract.md](02_data_contract.md)：数据输入、shape、类型、位宽和是否定型。
4. [03_end_to_end_dataflow.md](03_end_to_end_dataflow.md)：从点云/特征到 logits 的完整数据流。
5. [04_protocol_and_memory_path.md](04_protocol_and_memory_path.md)：TileLink、AXI、AXI4-Stream、DDR 与 uncached alias。
6. [05_feature21_microarchitecture.md](05_feature21_microarchitecture.md)：Feature21 内部计算、状态机、周期和误差边界。
7. [06_qmlp_microarchitecture.md](06_qmlp_microarchitecture.md)：INT8 QMLP 内部结构、MAC/requant/logits 和瓶颈。
8. [07_xradar_rocc_custom_isa.md](07_xradar_rocc_custom_isa.md)：`rqdot4`、RoCC 调度、当前板级结果。
9. [08_performance_timing_evidence.md](08_performance_timing_evidence.md)：性能、时序和可引用实验数字。
10. [09_paper_related_work_and_comparison.md](09_paper_related_work_and_comparison.md)：论文对比和相关工作。
11. [10_future_optimization_plan.md](10_future_optimization_plan.md)：后续优化路线和待验证问题。

图纸入口见 [pic/README.md](pic/README.md)。Visio COM 对接规范见 [pic/visio_com_schema.md](pic/visio_com_schema.md)。

## 当前结论

- 当前主线硬件平台是 Digilent Nexys Video 上的 Rocket-based Chipyard SoC，板上 DDR 通过 MIG 接入，雷达数据搬运依靠 Xilinx AXI DMA 风格的数据通路。
- 稳定的硬件加速基线是 `MMIO 控制 + AXI DMA 搬运 + AXI4-Stream 算子`。Feature21 和 QMLP 都在该流式路径中工作。
- QMLP 模型形状为 `21 -> 64 -> 32 -> 2`，输入是 `21` 个 int8 特征，测试/硬件帧按 `32 B` 对齐输入；输出是两个 int32 logits，共 `8 B`。
- Feature21 当前应表述为固定点/近似硬件实现，并与 Python exact-LUT mirror 和分类一致性对拍；不要写成严格 1:1 float clone。
- 75 MHz Feature21/QMLP 候选已 timing-clean。推广候选 WNS `+0.040 ns`，最终限制主要转移到 Rocket frontend/core routing，而不是普通 QMLP、Feature21 量化写回或 UART-TSI TL-A。
- Xradar RoCC 当前只实现并板测了 `rqdot4`。`rqscale8`、`rqpack`、`racc.*` 仍未在 RoCC RTL 中实现。
- 2026-06-09 RoCC `rqdot4` timing-clean bitstream 在板上 PASS；scalar-vs-RoCC QMLP profile 显示 `168203` vs `62532` cycles，约 `2.689x`。这是 QMLP kernel/profile 证据，不是完整 Feature21+QMLP 端到端 speedup。

## 关键证据索引

| 主题 | 证据 |
| --- | --- |
| 文档功能地图 | [../README.md](../README.md) |
| 75 MHz timing closure | [../feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md](../feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md) |
| 长期滚动记录 | [../feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md](../feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md) |
| RTL 逻辑综述 | [../radar_rtl_implementation_logic_review_2026-06-08.md](../radar_rtl_implementation_logic_review_2026-06-08.md) |
| QMLP 旧 profile | [../performance/radar_qmlp_dma_profile_2026-04-16.md](../performance/radar_qmlp_dma_profile_2026-04-16.md) |
| Xradar 静态/离线分析 | [../performance/xradar_offline_static_analysis_2026-06-07.md](../performance/xradar_offline_static_analysis_2026-06-07.md) |
| Xradar ISA 草案 | [../riscv_xradar_isa_spec_2026-06-07.md](../riscv_xradar_isa_spec_2026-06-07.md) |
| RoCC 板级状态 | [../../logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-board-status-2026-06-09.md](../../logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-board-status-2026-06-09.md) |
| RoCC cycle profile log | [../../logs/radar_nexysvideo/runtime/xradar-rocc-cycle-profile-75mhz-2026-06-09-2026-06-09-215919.log](../../logs/radar_nexysvideo/runtime/xradar-rocc-cycle-profile-75mhz-2026-06-09-2026-06-09-215919.log) |
| Feature21 validation report | [../../logs/radar_nexysvideo/runtime/feature21-v1p4a-compact-validation-1000-75mhz-2026-06-08.md](../../logs/radar_nexysvideo/runtime/feature21-v1p4a-compact-validation-1000-75mhz-2026-06-08.md) |
| QMLP test common | [../../tests/radar_qmlp_test_common.h](../../tests/radar_qmlp_test_common.h) |
| Xradar fallback common | [../../tests/radar_xradar_fallback.h](../../tests/radar_xradar_fallback.h) |
| DMA common | [../../tests/radar_axi_dma_common.h](../../tests/radar_axi_dma_common.h) |
| QMLP RTL | [../../fpga/src/main/scala/nexysvideo/RadarQMLP.scala](../../fpga/src/main/scala/nexysvideo/RadarQMLP.scala) |
| DMA/Feature21 RTL | [../../fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala](../../fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala) |
| RoCC RTL | [../../fpga/src/main/scala/nexysvideo/XradarRoCC.scala](../../fpga/src/main/scala/nexysvideo/XradarRoCC.scala) |

## Obsidian 镜像

Obsidian 主入口：

`/home/soooarr/obsidian/项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md`

Obsidian 中使用 `[[WikiLink]]` 做主题连接，repo 中使用相对 Markdown 链接做版本化证据索引。两边的原则是：读写体验放 Obsidian，事实证据以本目录和 repo/logs 为准。
