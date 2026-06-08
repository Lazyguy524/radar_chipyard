# 21维特征前处理接入状态记录

日期：2026-04-20

## 本轮目标

本轮没有直接实现完整 raw point cloud 到 21 维特征的硬件公式计算。原因是软件交付包中的 21 维前处理输入为 k=7 融合后的变长点集，并包含 `sqrt/atan2/div/eigen/std` 等复杂算子，直接一次性硬件化风险较高。

本轮先完成第一阶段硬件接入路径：

```text
DMA MM2S -> RadarAXISPreprocessor -> RadarAXISQMLP -> DMA S2MM
```

当前 `RadarAXISPreprocessor` 先使用 bypass 模式，因此这条路径验证的是“21维 INT8 特征流经过可替换前处理槽位后进入 QMLP”的串接能力。后续真实 `Feature21Preprocessor` 可以替换该槽位，而不破坏现有 QMLP 主线。

## 代码改动

- `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
  - 新增 `QMLP_CTRL[2]` 作为 `preproc -> QMLP` 串接模式选择位。
  - 保留 `QMLP_CTRL[0]` direct QMLP 行为。
  - 保留原有 preproc-only 行为。

- `tests/radar_axi_dma_common.h`
  - 新增 `QMLP_CTRL_CHAIN_PREPROC`。
  - 新增 `qmlp_enable_preproc_chain()`。

- `tests/radar-axi-dma-qmlp-validation.c`
  - 增加宏开关，支持 direct QMLP 与 preproc-chain QMLP 共用同一套 golden 校验逻辑。

- `tests/radar-axi-dma-qmlp-chain-validation.c`
  - 新增链路验证 ELF 源文件。

## 构建结果

- C 端验证 ELF 编译通过：
  - `tests/radar-axi-dma-qmlp-validation.riscv`
  - `tests/radar-axi-dma-qmlp-chain-validation.riscv`
- Bitstream 生成通过：
  - 日志：`logs/radar_nexysvideo/runtime/610-fpga-bitstream-feature21-preproc-chain-resume-2026-04-20.log`
  - 标志：`write_bitstream completed successfully`
  - 返回码：`rc=0`

## Bitstream 归档

- 正式交付 bit：
  - `fpga/deliverables/radar_nexysvideo_bits/611-feature21-preproc-chain-2026-04-20.bit`
- 备份 bit：
  - `logs/radar_nexysvideo/bit_backups/feature21_preproc_chain_2026-04-20/NexysVideoHarness.bit`
- SHA256：
  - `9289d784bde749ee6b8b8c787c0369c0c7aff8128613ba1a53fa9f7f4d446250`

## 时序与资源摘要

- Timing：
  - Overall WNS：`0.015 ns`
  - TNS：`0.000 ns`
  - 结论：满足当前时序约束，但余量很薄，后续加入真实 feature21 算子前需要重新评估时序。

- Top utilization：
  - LUT：`28338`
  - FF / Slice Registers：`17444`
  - RAMB36：`2`
  - RAMB18：`14`
  - DSP：`10`

- QMLP hierarchy：
  - LUT：`3284`
  - FF：`1491`
  - RAMB36/RAMB18：`0/0`
  - DSP：`0`

## 后续板测建议

烧录本轮 bit 后，建议按顺序测试：

1. `tests/radar-axi-dma-qmlp-validation.riscv`
   - 验证原 direct QMLP 路径没有被破坏。
2. `tests/radar-axi-dma-qmlp-chain-validation.riscv`
   - 验证新增 `DMA -> preproc(bypass) -> QMLP -> DMA` 串接路径。

如果两者都通过，说明未来 21 维前处理模块可以优先放在 `RadarAXISPreprocessor` 与 `RadarAXISQMLP` 之间的链路位置继续迭代。

## 风险记录

- 当前不等价于完整 21 维前处理硬件实现，只是为完整前处理提供可验证插入位置。
- 完整 Feature21 硬件化需要软件侧进一步冻结：
  - 输入定点格式；
  - 单样本最大点数或流式结束协议；
  - `sqrt/atan2/eigen/std/div` 的近似策略；
  - 固定点 golden 与误差容忍规则。


## 2026-04-22 板级验证补充

烧录 `611-feature21-preproc-chain-2026-04-20.bit` 后完成两组验证：

- direct QMLP：`large_golden 1000/1000`，`boundary_cases 54/54`，通过。
- preproc-chain QMLP：`large_golden 1000/1000`，`boundary_cases 54/54`，通过。
- 两条路径的 QMLP kernel 延迟均为 `1301 cycles/sample`。
- 对比摘要：`logs/radar_nexysvideo/runtime/624-feature21-preproc-chain-board-summary-2026-04-22.md`。

注意：当前 chain 中的 preproc 仍为 bypass 模式，因此本轮证明的是 21维 INT8 特征流可通过 `preproc -> QMLP` 串接路径并保持 golden 一致；它还不是完整的 raw/fused point 到 21维特征的硬件前处理实现。
