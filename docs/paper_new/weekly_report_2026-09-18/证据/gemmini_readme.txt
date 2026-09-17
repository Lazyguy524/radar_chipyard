# Gemmini 与 QMLP：RTL 设计评估与板测准备（2026-09-15）

**最终性能指标以对应位流的上板实测为准。本包现有周期、比值和曲线仅用于 RTL 设计评估，不作为论文最终性能指标或最终比较基准。当前 Gemmini/QMLP 同条件板测比较尚未完成，最终加速比待测。**

这是用户明确的指标使用标准，详见[板测优先与指标使用规则](06_板测优先与指标使用规则.md)。RTL 对拍用于验证功能、观察批量及后处理开销；物理实现用于说明资源与时序条件；最终性能表必须绑定实际烧录的位流、运行 ELF、工作负载、时钟和板端日志。

| 本轮设计点 | 已有 RTL 评估 | FPGA 实现 | 本轮最终板测性能 |
| --- | --- | --- | --- |
| QMLP8 + PortableV1 DMA | 首 32 帧对拍通过 | 仿真路径与既有 Xilinx DMA 位流不同 | 待测，不能借用旧位流数据 |
| Gemmini16，有原生 Scale | batch32 为 568 cycles/sample | route 时序失败，无最终位流 | 待测，需先解决实现条件 |
| Gemmini16，无原生 Scale、CPU 后处理 | batch32 为 4628.84375 cycles/sample | 33.33 MHz 已约束时序通过 | 待测，尚未上板 |

`568` 不属于无 Scale 的通过版；`4628.84375` 也仅是 RTL 结果。既有 QMLP 板测仍按各自冻结位流和测试口径有效，但不能与这轮 Gemmini 仿真组成最终加速比。

## RTL 设计评估表（非最终性能指标）

双方执行冻结 K7 `21→64→32→2` 模型，采用 large golden 首 32 帧，每个批量点的两个 INT32 logits 均逐位通过。Gemmini 保留硬件偏置、原生重量化和 ReLU，batch=8/32 是真正的矩阵批量计算。单位为 **CPU cycles/sample**，计入输入整理至 CPU 读回最终 logits。

| batch | QMLP8 + PortableV1 DMA，RTL | Gemmini 16×16 原生 scale，RTL | 仿真周期比，仅供评估 |
| --- | ---: | ---: | --- |
| 1 | 1699.09375 | 6491.5 | QMLP8，3.82× |
| 8 | 1004.375 | 1074.59375 | QMLP8，1.07×；接近 |
| 32 | 924.03125 | 568.0 | Gemmini，1.63× |

表由[汇总脚本](../../../scripts/gemmini_qmlp_compare_20260915/finalize_comparison.py)读取经验证的结果生成：[CSV](comparison_main.csv)、[来源 SHA 与完整精度 JSON](comparison_main.json)。历史文件名 `comparison_main` 只标识本包仿真汇总，不代表论文最终主表。batch=32 的**整批**完成周期为 QMLP8 `29569`、Gemmini `18176`；批量表项是摊销开销，不是单个请求的响应时间，没有包含组批等待。

首 32 帧形成 32/4/1 个正式批次，当前没有独立重复或置信区间，不能据此给出精确批量交叉阈值。batch=8 的约 7% 差距尤其不宜包装成稳健架构优势。

![RTL 设计评估：非最终板测性能](figures/comparison_rtl_evaluation.png)

评估图导出：[SVG](figures/comparison_rtl_evaluation.svg)、[PDF](figures/comparison_rtl_evaluation.pdf)。图中没有统计误差条，因为本轮没有足够的独立重复。旧 `comparison_main.*` 图保留为历史附件，适用相同的“仅供 RTL 评估”限制。

## 论文中怎样使用

- **放入设计评估或补充实验。** 仿真观察到小批量与大批量的周期变化，仅用于选择后续板测配置、解释可能的瓶颈；`3.82×/1.63×` 不进入最终实测性能表、摘要或结论中的实际加速收益声明。
- **以板测确定最终比较配置。** 原生 Scale 与 CPU 后处理版都是候选评估点，不能预先指定未通过时序的原生版为最终基准。原生 float32 scale 对本模型具有与整数参考相同的量化语义，但不能称为纯整数硬件实现。
- **资源约束需要量化。** 已有能装入该板卡的 16×16 配置，不能笼统写“板卡放不下 Gemmini”或“本项目耗尽板卡资源”。应写模型、批量、缓冲容量和频率条件下的性能/资源取舍。

仅适用于“RTL 设计评估”小节的段落及完整口径见[实验口径与论文用法](02_实验口径与论文用法.md)。本轮只评估 **QMLP 分类阶段**，不包含 Feature21，不是 Feature21+QMLP full-chain。

## FPGA 是另一组独立证据

CPU 后处理版 16×16 已在 `33.333333 MHz` 完成物理实现：LUT `90122`（标称容量约 66.96%）、寄存器 `63845`、DSP `166`、BRAM36 等效 `50.5`；已约束路径 WNS `+0.894 ns`、WHS `+0.001 ns`，DRC error/critical warning 均为 0。见[独立冻结清单](../../../fpga/deliverables/gemmini_qmlp_compare_20260915/variants/dim16_33mhz/manifest.json)，尚未上板。

带原生 scale 的 RTL 评估配置完成 route 后时序失败（WNS −21.792 ns），后优化经评审受控停止；已归档完整日志和较早的 post-place checkpoint，没有最终 post-route DCP 或位流，见[物理实现结果](04_FPGA资源与频率边界.md)。不能用 CPU 后处理版位流或资源，冒充原生版物理证据。33.333333 MHz 是验证点；没有同配置频率扫描，不能称 Fmax。仿真周期不能直接除以任意 FPGA 频率后称为板测延迟。

## 软件后处理消融

以下各项同样通过首 32 帧完整分类 RTL 对拍，单位 CPU cycles/sample，仅供仿真评估。4×4 为 16/8 KiB scratchpad/accumulator，16×16 为 64/16 KiB；容量同时变化，属于设计点比较。

| Gemmini 配置 | batch=1 | batch=8 | batch=32 |
| --- | ---: | ---: | ---: |
| 4×4 + 优化 CPU 后处理 | 10353.21875 | 4990.03125 | 4754.15625 |
| 16×16 + 优化 CPU 后处理 | 9546.09375 | 4822.25 | 4628.84375 |
| 16×16 + 原生 scale/ReLU/bias | 6491.5 | 1074.59375 | 568.0 |

CPU 后处理原始结果为本目录 `gemmini_dim4_b*_summary.json`、`gemmini_dim16_b*_summary.json`。原生版同时改变偏置/重量化位置、中间结果宽度和 CPU 参与方式，不能把差值全部归因于 scale 单元。

## 快速核验入口

- [最初计划快照](01_执行前计划快照.md)、[Luna 计划审计](plan_review_luna.md)、[问题解决](review_resolution.md)、[原生追加计划](03_原生重量化基线追加计划.md)、[原生主审](native_plan_review_root.md)。
- [模型 ROM/软件一致性](model_identity.json)、[布局容量预检](python_preflight.json)、[CPU 后处理范围穷举](postprocess_bounds_preflight.json)、[原生 float32 重量化范围穷举](native_scale_preflight.json)。Python 不预测硬件资源、时序或性能。
- [1000 帧 Python 模型算术预检](model_math_preflight.json)与[执行记录](../../../logs/gemmini_qmlp_compare_20260915/attempts/qmlp_preflight_001/command.json)：1000/1000 logits 匹配；这是执行前算术验证，不将其写成 1000 帧 Gemmini RTL 实验。
- RTL 评估来源：[QMLP8](qmlp_packed_native_dim16_summary.json)、[Gemmini batch1](gemmini_native_dim16_b1_summary.json)、[batch8](gemmini_native_dim16_b8_summary.json)、[batch32](gemmini_native_dim16_b32_summary.json)。每个 JSON 指向唯一运行目录，含 source/ELF/simulator SHA；同名 CSV 保存逐批计时。
- [四个主程序重建验证](software_reproducibility.json)：入口与全部 PT_LOAD 指令/数据/地址相同。非装载字符串表中的编译器随机临时对象名不同，保留原 ELF SHA 作为测量身份；另冻结 44 个编译依赖。
- [Luna 原始结果独立审计](final_comparison_review_luna.md)：PASS_WITH_LIMITATIONS 仅确认所审 RTL 证据及限制，不授予最终板测指标资格。历史计划/审计中的“主比较”“最终主表”按[当前指标规则](06_板测优先与指标使用规则.md)收窄为仿真评估表。
- [物理负结果收口评审](closeout_review_luna.md)、[冻结证据索引](evidence_index.json)、[文件身份与链接校验](documentation_validation.json)。前一份独立审计中的“FPGA 尚在运行”是审计时状态，最终以本页、物理实现页和收口评审为准。
- [复现与板测交接](05_复现与板测交接.md)、[保护清单复核](protected_artifacts_check.json)、[Obsidian 镜像状态](obsidian_sync_manifest.json)。旧位流、HPM4 与首轮 Gemmini 产物分别受原 201 项和新增 68 项哈希清单保护。

历史初轮 4×4/K21 复测保留在[旧包](../training_and_gemmini_retest_2026-09-15/README.md)。用户授权 Gemmini 作为外部比较基线，其 RoCC 不作为本项目自定义 ISA 贡献。
