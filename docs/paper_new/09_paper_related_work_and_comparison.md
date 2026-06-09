# 相关工作与对比口径

## 可对比方向

| 方向 | 可比较点 | 本项目位置 |
| --- | --- | --- |
| Gemmini / systolic array | 通用矩阵加速、scratchpad、DMA、RoCC 控制 | 本项目模型很小，`21 -> 64 -> 32 -> 2`，更适合轻量固定/半固定加速与 custom instruction 对比 |
| RISC-V custom instruction / RoCC | 指令级低开销协处理器 | 当前 `rqdot4` 已板测，适合写 core-accelerator coupling point |
| FPGA DPU / Vitis-AI | 通用 CNN/NN 部署工具链 | 本项目更偏雷达小模型和 SoC 内联数据通路，不依赖大 DPU |
| 雷达边缘推理 | 点云/特征提取/轻量分类 | Feature21 + QMLP 是本项目任务主线 |
| AXI DMA stream accelerator | DDR 到 stream 算子再回 DDR | 当前 Feature21/QMLP baseline |

## 论文材料入口

旧目录仍可参考：

- [../paper/radar_qmlp_edge_paper_survey_2026-04-09.md](../paper/radar_qmlp_edge_paper_survey_2026-04-09.md)
- [../paper/radar_hardware_thesis_framework_2026-04-13.md](../paper/radar_hardware_thesis_framework_2026-04-13.md)
- [../paper/radar_hardware_strict_review_2026-04-15.md](../paper/radar_hardware_strict_review_2026-04-15.md)
- [../paper/radar_thesis_logic_gap_audit_2026-04-16.md](../paper/radar_thesis_logic_gap_audit_2026-04-16.md)
- [../radar_cpu_upgrade_research_report_2026-04-07.md](../radar_cpu_upgrade_research_report_2026-04-07.md)

注意：这些文档是历史材料。写论文时必须用本目录和 2026-06-08/09 证据刷新性能、timing 和 RoCC 结论。

## 当前建议叙事

论文不建议写成“做了一个比所有通用 NPU 都快的加速器”。更稳的写法：

1. 面向 radar 小模型 workload，构建可板级运行的 RISC-V SoC + stream accelerator 原型。
2. 在固定 Feature21/QMLP pipeline 中完成数据搬运、定点计算、timing closure 和板级验证。
3. 进一步识别 CPU fallback 的 dot/MAC 瓶颈，并用 RoCC `rqdot4` 证明轻量 custom instruction 对该 workload 有收益。
4. 与 Gemmini/DPU 等通用方案对比时，强调本项目的低复杂度、低集成成本、固定小模型适配和端到端工程闭环。

## 需要补的外部文献

后续可以继续补这些方向的论文条目：

- Gemmini systolic array generator。
- RoCC/custom instruction accelerator examples。
- FPGA edge radar object classification。
- mmWave/radar point cloud feature extraction。
- INT8 quantized MLP accelerator。
- AXI stream based FPGA accelerator integration。

每条文献记录建议包含：问题、方法、硬件平台、模型/数据集、性能指标、与本项目可比和不可比之处。
