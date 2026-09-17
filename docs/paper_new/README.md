# Chipyard 雷达 SoC 论文知识库

2026-09-17 阶段总结与下一方向：[先补特征必要性的证据](research_status_2026-09-17/README.md)。固定 21 维的软件对照已完成，当前协议的删维重训尚未做；历史 14/18/21 模型单列。新增只读检查确认当前代理/均值表示中两项输出重复，建议先重复项审计与有限删组重训。本次仅总结及训练输入核查，没有追加训练或硬件工作。


2026-09-17 当前软件收口：[软件收敛与真实少点覆盖](software_convergence_2026-09-17/README.md)。按用户要求暂停新增硬件，恢复 474,582 条训练少点，完成两表示×两覆盖×三 seed 的 12 条训练、13 条件/全部分组/精度与配对区间。真实覆盖改善单帧少点，但四候选均未通过全部新平衡门槛，保留 A 主基线、B 困难条件备选；原负结果不改。已交付全部模型与三种子主/备 C 包，1,655,508 次完整 C 对拍零差异。当前是开发域有界选型，独立泛化仍缺；旧位流和 RTL 保留。**本入口优先于下方历史阶段的下一步 SoC/板测安排。**


2026-09-17 最新推进：[三种代表方案的硬件衔接](representative_rtl_2026-09-17/README.md)。停止上一轮训练不等于停止项目；本轮不重训，完成 Python 预检和实际 Feature21＋QMLP 的隔离 RTL 对拍。A 普通训练、B 扰动训练、C 正确判断保护各以固定 seed 7 检查 80,450 条真实点簇＋542 个边界簇，特征和 logits 完全一致，并通过阻塞/取消恢复检查。确定新逐特征定标必须在旧 INT8 饱和前接入；原工程与位流保留。当前只通过独立模块功能验证，没有新完整 SoC/位流/板测，也没有改变前阶段的算法推广结论。下一步和质量确认缺口见[验证收口](representative_rtl_2026-09-17/02_最终验证如何收口.md)。

2026-09-16 最新接续：[条件保护训练、反思与 Git 备份](conditional_protection_2026-09-16/README.md)。完成两种方法×三个 seed；保护旧正确判断减少负翻转、缓解近距离/历史充分组回退，却损失部分形态变化收益，均未通过全部预设门槛，按六条预算停止。代表对照和后续缺口见[论文收敛](conditional_protection_2026-09-16/03_论文收敛与接续.md)。新增[设计账本](conditional_protection_2026-09-16/00_设计账本与主线.md)与原问题哈希，执行前/结果后独立 Git 备份分支；历史清单外五序列无当前目标轨迹点，独立确认仍待补。无新 RTL/位流/板测，旧成果不改。

2026-09-16 前阶段算法入口：[35 条训练后的机制拆分与收敛判断](mechanism_convergence_2026-09-16/README.md)。五 seed 四组统计、三 seed 扰动训练和三 seed 输出编码均完成；完整 80,450 条 validation 的 11 条件、97,734 条自然被过滤观测、位宽/交叉分组与 2,815,750 次完整 C 模型/观测对拍已核。简单定标＋条件覆盖训练是当前强基线，精确矩和开平方未建立全面优势；增强改善无历史少点，同时在部分近距离/历史充分组回退。原验证域仍属开发数据，未增加 test 使用、RTL、位流或板测。请先读[评审决定](mechanism_convergence_2026-09-16/03_评审与收敛决定.md)与[分组回退](mechanism_convergence_2026-09-16/05_分组收益与回退.md)。此前六条训练包及其停止门槛保留为历史，新增两份计划单独冻结。

2026-09-16 前一轮算法研究：[点数、形态、统计精度与共享计算：主线复核及受控实现](conditional_statistics_2026-09-16/README.md)。持续回答“哪些近似损害条件分类稳定性、怎样形成可验证的质量—成本取舍”，不是先指定 21 维或某个分类器。完成 357,780 条全量 train 的六条新轨迹、80,450 条 validation、3,448 条五条件配对诊断、两个固定 RF 与历史过滤审计；单遍 C 统计和完整整数分类候选均已实现并对拍。仅逐特征定标已将 F1 提高至 98.0547%/98.0806%；矩统计在部分减点条件有线索，未全面胜过简单基线，Q16 重训未过条件容差。历史单点/两点观测过滤比例 train 57.0163% / validation 54.8500%，需限制论文覆盖范围。没有新 RTL/位流/板测，最终质量—成本优势尚未证明。后续先读[评审门槛](conditional_statistics_2026-09-16/03_评审与下一步门槛.md)，再决定是否增加实验。

2026-09-16 早先顺序修订（历史）：[先完成特征筛选与样本审计，RTL 后置](qmlp_int8_convergence_2026-09-16/04_先完成特征筛选与样本审计.md)。当时尚未运行 RF 或过滤统计；上方当前入口已补齐固定 RF、组置换和过滤审计，未进行后向删除。RF/删维属于原研究问题的支撑工具，不再作为独立优先目标。

2026-09-16 后续开发：[当前硬件镜像对应的冻结 INT8 训练与收敛](qmlp_int8_convergence_2026-09-16/README.md)。完整 train 357,780 条、两个 seed，标准化折叠入第一层、训练集校准并冻结尺度，分别在 QAT 第 28/39 epoch 达到预设训练损失平台期。开发 validation Macro-F1 为 97.4957%/97.5364%，旧整数模型同集为 96.6527%；完整验证集逐层 C/NumPy/QAT 一致。提供独立 C/Scala 参数候选，未接入旧 RTL/位流，也不是新增独立测试或上板成绩。

2026-09-16 有约束试验：[近似特征真实数据诊断与匹配训练](feature_approximation_pilot_2026-09-16/README.md)。432 条校验通过后，完成 80,450 条 validation 的 10 模式固定模型诊断；达到预设门槛后才进行 49,255 条 train 子集、3 表示×2 seed 的六次训练。均值＋协方差修正在固定旧模型下 +0.4505 个 F1 百分点，但匹配重训差值为 -0.0892/+0.0180 个百分点、区间跨零，因此按预算停止、暂停硬件扩展。新训练为 FP32 表示对照，非部署 QAT/板测；历史 test 未参与新候选选择或评价。

2026-09-16 研究方向细化：[雷达点簇近似特征的稳定性、精度与实现成本](feature_approximation_research_2026-09-16/README.md)。新增 9 篇文献与 Zotero 导入、公开 PDF、源码和合成 Python 预检，区分统计定义损失与有限位宽误差；候选创新尚未确立。旧工程审计中的“创新达标”不作为新颖性或毕业充分性的保证。该文献与合成预检阶段没有训练、服务器任务、RTL 修改或新增板测；后续真实数据试验见上方新包。

2026-09-15 训练资料已恢复：[数据、模型复现与逻辑闭环审计](training_server_recovery_2026-09-15/README.md)。335 个原文件 SHA256 一致，493,746 条样本划分已核对；三个 checkpoint→训练集校准→冻结导出一致。新增 55,516 条历史 test 的部署近似软件镜像评价 Macro-F1=0.963226，旧 1000 条板测 logits 回归全匹配；这不是新增全量板测。确认历史 test 参与选 K、QAT eval 尺度随 batch 变化、K7 无时间上限，需修正评价与论文边界。服务器随后网络不可达，按用户要求停止重试，明天开机后排查；本轮未训练、未用 GPU。

2026-09-15 读后核对：[Scheiner 2018 与 Feature21：逐项对应、数据关系和特征选择](scheiner_feature21_review_2026-09-15/README.md)。区分软件定义与硬件代理特征；RadarScenes 官方确认该文使用早期子集，但具体样本/划分重合未知。21 维尚非已证明最优，二分类 F1 不能单独证明无偏。Gemmini 公平板测套件缺口按用户要求记录暂缓。

2026-09-15 用户明确的指标标准：**最终性能与加速比以对应配置的上板实测为准；Python/RTL 结果仅作设计评估，不作为最终性能指标。** 已有板测按原位流及窗口独立有效；跨配置、跨仿真/板测数据不得拼接。

2026-09-15 追加：[Gemmini 与 QMLP：RTL 设计评估与板测准备](gemmini_qmlp_comparison_2026-09-15/README.md)。同一 RTL SoC、相同 K7 模型与首 32 帧，在 batch=1/8/32 均通过 logits 对拍。原生 Scale 版的 568 cycles/sample 等仅为评估参考，该版目标 FPGA 时序失败；无 Scale 版已有时序通过位流但未上板。**最终 Gemmini/QMLP 板测比较待测**，以[指标使用规则](gemmini_qmlp_comparison_2026-09-15/06_板测优先与指标使用规则.md)为准，原始结果审计不授予最终指标资格。

2026-09-15 初轮：[训练机资料获取对话、优先阅读论文与 Gemmini 独立复测](training_and_gemmini_retest_2026-09-15/README.md)。保存开机后可复制的训练来源核对请求；停车场案例暂缓；当前 HPM4 顶层 LUT 占标称容量约 26.68%，论文不再笼统声称板卡资源耗尽。新增 Scheiner 雷达特征设计与 Roofline 两条补充书目。4×4/K21 Gemmini RTL 对拍通过，33.333333 MHz 候选物理实现及已约束路径时序通过；该初轮尚未做完整 QMLP 比较，后续见上方追加包。旧位流和最新 HPM4 冻结包 201 项哈希一致。

2026-09-12 论文凝练与文献：[六章写作、27 条精选书目、Zotero 导入与独立评审包](thesis_writing_literature_2026-09-12/README.md)。恢复旧写作要求并收窄为雷达点簇分类，包含研究问题、贡献层次、章节材料与证据补齐顺序；书目区分正式论文、规范和短摘要。材料镜像写入 Obsidian 共享目录，实际同步与校验见新包清单。

2026-09-12 后续实施：[PMU 计划、Python 模拟与 HPM4 实施结果](pmu_execution_2026-09-12/README.md)。已完成计划及实现独立审计、Python 执行前模拟、HPM4 配置与采样软件；真实 Rocket 自检和 32 帧完整算法校准通过，新 50 MHz FPGA 镜像与已约束路径布线后审计通过。新包提供原始结果表、候选 bit/ELF、论文段落、模型图和上板步骤。1000 帧 RTL 为受控停止 NOT_PASS，板测尚未运行。

2026-09-12：新增 [PMU 加入难度与硕士论文快速阅读包](pmu_thesis_readiness_2026-09-12/README.md)，包括三路并行审计、六章证据映射、最小实验计划、12 篇核心研究和 17 条起始书目；另已从归档板测补出同一 1000 帧子集的真实标签指标（原始基线 accuracy 89.70%，硬件 91.10%，预测一致率 95.20%）。子集为单序列均衡选择，完整训练划分仍需溯源；新指标与复现见包内 05。以上为实施前评估；后续已执行 HPM4，进展见下方实施包。

Date: 2026-08-26

本目录是当前 `Chipyard + Nexys Video + Rocket + DDR + AXI DMA + Feature21 + QMLP` 项目的论文事实源。论文主线定位为“面向雷达边缘推理的轻量硬件加速、RISC-V SoC 集成、板级验证与事件驱动低功耗设计”。

2026-08-26 起，当前论文与答辩不再使用自定义算术指令或 custom ISA 作为贡献、实验或章节主线。相关历史 RTL、日志和旧文档仅作追溯档案；RISC-V 内容统一围绕 Rocket/Chipyard、标准 `WFI` 与 trap/CSR 机制、DMA IRQ/PLIC 和分域时钟门控展开。

## 阅读顺序

1. [27_thesis_closeout_audit_2026-08-26.md](27_thesis_closeout_audit_2026-08-26.md)：先看毕业充分性、当前主线、缺口和证据边界。
2. [00_project_requirements_and_memory.md](00_project_requirements_and_memory.md)：持久写作规则和禁用的旧叙事。
3. [01_system_overview.md](01_system_overview.md)、[02_data_contract.md](02_data_contract.md)、[03_end_to_end_dataflow.md](03_end_to_end_dataflow.md)、[04_protocol_and_memory_path.md](04_protocol_and_memory_path.md)：系统、数据与协议。
4. [05_feature21_microarchitecture.md](05_feature21_microarchitecture.md)、[06_qmlp_microarchitecture.md](06_qmlp_microarchitecture.md)：算法硬件化与微架构。
5. [12_experiment_evidence_matrix.md](12_experiment_evidence_matrix.md)、[14_paper_experiment_tables.md](14_paper_experiment_tables.md)：当前可引用数字和实验口径。
6. [15_review_brief.md](15_review_brief.md)、[18_workload_innovation_assessment.md](18_workload_innovation_assessment.md)：评审摘要、工作量和创新判断。
7. [17_thesis_reference_library_plan.md](17_thesis_reference_library_plan.md)、[19_high_quality_reference_screening.md](19_high_quality_reference_screening.md)：引用池与正式书目缺口。
8. [20_thesis_intro_related_work_draft.md](20_thesis_intro_related_work_draft.md)、[22_thesis_formal_content_pack.md](22_thesis_formal_content_pack.md)、[26_thesis_academic_chapter_outline.md](26_thesis_academic_chapter_outline.md)：当前正文、摘要和章节蓝图。
9. [24_thesis_readiness_and_experiment_elf_manifest.md](24_thesis_readiness_and_experiment_elf_manifest.md)：材料 readiness 与可选板级功耗入口。

未列入上述顺序的编号文档和旧图仍保留为历史实验或规划档案，不作为当前论文事实入口；引用其中任何数字前必须回到 `12/14/27` 复核。

图纸入口见 [pic/README.md](pic/README.md)。Visio COM 对接规范见 [pic/visio_com_schema.md](pic/visio_com_schema.md)。

面向代码复盘、简历项目学习和面试讲解的当前 QMLP Scala 快照见 [learning/qmlp_scala_learning_pack_2026-07-31/README.md](learning/qmlp_scala_learning_pack_2026-07-31/README.md)。

2026-08-12 Feature21/QMLP 共享核心、双独立门控、Wide23/PortableV1 DMA 和证据边界见 [Feature21、QMLP 与 DMA 优化实现状态](../feature21_qmlp_dma_optimization_2026-08-12/README.md)。2026-08-20 的 r4/r5a/r5g 失败证据保留在 [历史运行证据](../feature21_qmlp_dma_optimization_2026-08-12/ASIC_REMOTE_EDA_RUN_2026-08-20.md)；2026-08-22 r5k_min 已完成 AO/ACC/FULL 三档 VCS、DC、PT 和 6 份 PTPX，当前结论见 [r5k_min 终态证据](../feature21_qmlp_dma_optimization_2026-08-12/ASIC_REMOTE_EDA_RUN_2026-08-22.md)。2026-08-25 又在同一冻结后端上完成三档连续 full-chain 活动窗口补测，见 [活动功耗证据](../feature21_qmlp_dma_optimization_2026-08-12/ASIC_ACTIVE_FULLCHAIN_POWER_2026-08-25.md)；2026-08-26 进一步完成 ACC/FULL 的真实 DMA IRQ -> PLIC -> WFI 窗口补测，见 [IRQ/WFI 功耗证据](../feature21_qmlp_dma_optimization_2026-08-12/ASIC_IRQ_WFI_FULLCHAIN_POWER_2026-08-26.md)。FullChain v3 accelerator-only ASIC 门控 A/B、Rocket 未新增门控的边界及双门控可复用方法见 [FullChain v3 accelerator 时钟门控参考](../feature21_qmlp_dma_optimization_2026-08-12/FULLCHAIN_V3_ACCELERATOR_CLOCK_GATING_REFERENCE.md)。

## 当前结论

- 当前主线硬件平台是 Digilent Nexys Video 上的 Rocket-based Chipyard SoC，板上 DDR 通过 MIG 接入，雷达数据搬运依靠 Xilinx AXI DMA 风格的数据通路。
- 稳定的硬件加速基线是 `MMIO 控制 + AXI DMA 搬运 + AXI4-Stream 算子`。Feature21 和 QMLP 都在该流式路径中工作。
- QMLP 模型形状为 `21 -> 64 -> 32 -> 2`，输入是 `21` 个 int8 特征，测试/硬件帧按 `32 B` 对齐输入；输出是两个 int32 logits，共 `8 B`。
- Feature21 当前应表述为固定点/近似硬件实现，并与 Python exact-LUT mirror 和分类一致性对拍；不要写成严格 1:1 float clone。
- 75 MHz Feature21/QMLP 候选已 timing-clean。推广候选 WNS `+0.040 ns`，最终限制主要转移到 Rocket frontend/core routing，而不是普通 QMLP、Feature21 量化写回或 UART-TSI TL-A。
- 2026-06-22 Stage C strict board-reference oracle 已上板 PASS：`1000` 帧 PC replay，`14` 个 chunk，板端逐帧 expected logits 对拍，`pass=1000`、`mismatch=0`、`chain_cycles=190639602`。同日晚间在重烧 75 MHz full-chain bitstream 后复测同一 strict oracle 也 PASS，`chain_cycles=190681736`。这是当前最严格的 PC replay / frame-based edge inference 证据，不是 live radar sensor acquisition。
- 2026-06-23 已补 Rocket CPU software full-chain baseline：software Feature21 `density_recip_exact_lut` mirror + software QMLP 为 `168492 cycles/sample`，board-reference `logit_mismatches=0`、`pred_mismatches=0`。与 active hardware-chain `2224 cycles/sample` 对比约 `75.76x` cycle ratio。
- 后续优先级为：正式参考文献与 GB/T 7714 落地、章节/图表同步、算法指标口径补齐；板级外部功耗和多 seed strict oracle 属于可选补强，后端 P&R 不作为毕业前置项。
- 2026-06-24 已补正式论文内容落地包和图表生成包。图纸建议以 repo 中的 Mermaid/Visio JSON 为事实源；浏览器 ChatGPT 可用于视觉美化，但不应替代 repo 证据源。
- 2026-06-24 已补功耗测量入口 ELF：`tests/radar-power-state-hold.riscv` 和 `tests/radar-axi-dma-feature21-qmlp-fullchain-powerloop.riscv` 已 build-ready。功耗真实数值仍需本地接仪器上板测量。
- 2026-08-26 已更新毕业论文学术章节大纲：第 2 章写软件算法与数据处理，第 3 章写算法硬件化，第 4 章写 RISC-V SoC 集成与事件驱动低功耗，第 5 章写 FPGA/ASIC 系统测试与性能功耗评估。
- 2026-06-24 在 manual reset 后复跑 active hardware-chain benchmark，结果 PASS：`1000` samples、`14` chunks、`chain_cycles_sum=2224233`、`chain_cycles_per_sample_avg=2224`、`dma_reset_sum=0`。这是 active-throughput sanity retest，不替代 strict oracle correctness evidence。
- 2026-08-14 已完成 Wide23 `Q4_AO/Q8_AO/Q8_ACC/Q8_FULL` 四档 50 MHz FPGA bitstream 和 post-route 归档。四档 setup/hold 均 timing-clean，项目门数为 `0/0/2/4`，DRC Error/Critical Warning 和 LUT clock driver 均为 0；Q8_FULL 使用两个并行 root BUFG 各驱动两个 BUFGCE，没有 dedicated-clock waiver。
- 2026-08-19 四档选定 smoke 项 `16/16 PASS`：`221136 B / 1000 samples` one-shot strict replay 均 mismatch=`0`，Q4/Q8 的 8-case directed QMLP 为 `927/471 cycles`（`1.968x`），Q8_FULL 还完成 `262144 B` DMA IRQ/WFI、100 次 full-chain 双 IRQ 和 PM selftest。该状态严格为 `SELECTED_SMOKE_ITEMS_PASS_NOT_FULL_MATRIX`；Q8_FULL 缺 programming/readback log，仅按 operator-confirmed image 接受，且没有外部功耗、Rocket gate readback 或十次 strict replay。详见 [FPGA 板测收口证据](../feature21_qmlp_dma_optimization_2026-08-12/FPGA_BOARD_SMOKE_2026-08-19.md)。
- 2026-08-19 已冻结 PortableV1+QMLP4 ASIC AO/ACC/FULL 的 design-only RTL lint 包，顶层 `RadarASIC50Top`，相对 filelist 源数 `273/274/275`，项目门 `0/2/4`。本地 Verilator 5.022 portable-mode 三档均为 0 error，raw warning `1825/1826/1827`；包 tar SHA256 为 `1e9d9cc26232e3d86af283bf1ce1cfd3742a4a977de8baca71ecffec54ad8dc5`。该条严格是 `REMOTE_LINT_NOT_RUN`，不代表商业 lint、CDC/RDC、DC/PT 或 ASIC signoff。
- 2026-08-20 r4 远端 functional 将首个 `0x1081000000` store fault 定位为缺少非缓存 DDR alias 回映射。修复后 AO VCS compile、100 次 DMA IRQ/WFI functional 和两份 raw SAIF 已远端 PASS；最终 r5g DC 完成 mapping、三次 bounded hold 和 final DRC，但剩一条 QMLP 普通 same-clock min/hold path，整体 `FAILED_FROZEN`。FULL/ACC、mapped SAIF、PT/PTPX 未运行，因此仍不能升级为多档 ASIC 功能、时序或功耗证据。
- 2026-08-22 r5k_min 已完成 AO/ACC/FULL 三档各 8 个原子阶段，合计 `24/24` 个 attempt-1 PASS marker。三档 100 次 DMA IRQ/WFI functional strict-v2 signature 相同，DC/PT setup worst slack 均为 `+7.80 ns`，项目 ICG=`0/2/4`，六份 mapped-SAIF coverage=`97.21%..97.23%`；hold 仅报告。idle dynamic 为 AO=`0.013001425 W`、ACC=`0.012601169 W`、FULL=`0.0131298 W`，观测顺序 `ACC < AO < FULL`，未满足预期 `AO > ACC > FULL`。因此三档证据完整，但 S3 功耗判据未通过；本轮无重跑，且仍严格为 pre-layout generic-memory、`SIGNOFF=NO`。
- 2026-08-25 连续 full-chain 活动补测完成：AO/ACC/FULL 各热身 `1000` 个样例并测量 `5 x 1000` 个样例，三档共 `15000` 次输出对全部 oracle bit-exact，signature 同为 `0xa13262ff7c80799b`。active dynamic 为 `0.01318798/0.0130146/0.0135434 W`；ACC 相对 AO 下降 `1.3147%`，其 QMLP/Feature21 局部 dynamic 分别下降约 `42.25%/48.62%`，但 FULL 相对 ACC 上升 `4.0631%`。本 software-orchestrated active polling 窗口不给 Rocket WFI 门足够休眠机会，不能用来否定 interrupt-driven/稀疏负载的门控收益；仍为 pre-layout generic-memory、hold report-only、`SIGNOFF=NO`。
- 2026-08-26 Rocket-gate-enabled IRQ/WFI full-chain 补测完成：ACC/FULL 使用同一 ELF，各完成 `5 x 1000` exact samples，signature 一致，MM2S/S2MM IRQ=`5/5`、WFI entries=`10`。软件通过标准 RISC-V `WFI` 等待中断，并清除 Rocket custom `mcache_ctl@0x7c1` 的 disable mask `0x6`；FULL 两个 Rocket gate duty 为 `0.14726505%/0.14525012%`。dynamic=`0.01319629/0.00804812 W`，FULL 下降 `39.012253%`，coverage 均为 `97.23%`。原 run 因 PM comparison 分母错误保持 `FAILED_FROZEN / matrix`，独立 checksum-covered matrix-only 修正审计 PASS且未重跑 EDA；旧 r3 的 `FULL +4.0052%/gate duty 100%` 保留为 disable bits 未清除的负对照。hold report-only、pre-layout generic-memory、`SIGNOFF=NO`。

## 关键证据索引

| 主题 | 证据 |
| --- | --- |
| 文档功能地图 | [../README.md](../README.md) |
| 75 MHz timing closure | [../feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md](../feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md) |
| 长期滚动记录 | [../feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md](../feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md) |
| RTL 逻辑综述 | [../radar_rtl_implementation_logic_review_2026-06-08.md](../radar_rtl_implementation_logic_review_2026-06-08.md) |
| QMLP 旧 profile | [../performance/radar_qmlp_dma_profile_2026-04-16.md](../performance/radar_qmlp_dma_profile_2026-04-16.md) |
| 双 context QMLP 50 MHz K7 profile | [../../logs/radar_nexysvideo/runtime/qmlp-pipeline-profile-k7-unified-50mhz-2026-08-03-211126.log](../../logs/radar_nexysvideo/runtime/qmlp-pipeline-profile-k7-unified-50mhz-2026-08-03-211126.log) |
| Stage A full-chain demo PASS | [../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-16/fullchain-demo-stage-a-board-result-2026-06-16.md](../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-16/fullchain-demo-stage-a-board-result-2026-06-16.md) |
| Stage B UART-TSI payload smoke PASS | [../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-16/pc-replay-smoke/stageb-write-readbin-smoke-result-2026-06-16.md](../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-16/pc-replay-smoke/stageb-write-readbin-smoke-result-2026-06-16.md) |
| Stage B external-input full-chain smoke PASS | [../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-16/pc-replay-smoke/stageb-external-fullchain-smoke-result-2026-06-16.md](../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-16/pc-replay-smoke/stageb-external-fullchain-smoke-result-2026-06-16.md) |
| Stage C 1000-frame PC replay PASS | [../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-19/pc-replay-run-readback-s0-n1000-chunked/run_summary.md](../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-19/pc-replay-run-readback-s0-n1000-chunked/run_summary.md) |
| Stage C 1000-frame PC replay repeat PASS | [../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-19/pc-replay-run-readback-s0-n1000-chunked-repeat1/run_summary.md](../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-19/pc-replay-run-readback-s0-n1000-chunked-repeat1/run_summary.md) |
| Stage C 1000-frame PC replay x3 PASS | [../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-19/pc-replay-run-readback-s0-n1000-chunked-repeat2/run_summary.md](../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-19/pc-replay-run-readback-s0-n1000-chunked-repeat2/run_summary.md) |
| Stage C strict board-reference oracle PASS | [../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-19/pc-replay-strict-oracle-board-s0-n1000-chunked/run_summary.md](../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-19/pc-replay-strict-oracle-board-s0-n1000-chunked/run_summary.md) |
| Stage C strict oracle after-reprogram PASS | [../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-22/pc-replay-strict-oracle-after-reprogram-s0-n1000-chunked/run_summary.md](../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-22/pc-replay-strict-oracle-after-reprogram-s0-n1000-chunked/run_summary.md) |
| 实验证据矩阵 | [12_experiment_evidence_matrix.md](12_experiment_evidence_matrix.md) |
| ASIC RTL lint 交付包 | [../feature21_qmlp_dma_optimization_2026-08-12/README.md](../feature21_qmlp_dma_optimization_2026-08-12/README.md) |
| ASIC r5k_min 远端 EDA 终态证据 | [../feature21_qmlp_dma_optimization_2026-08-12/ASIC_REMOTE_EDA_RUN_2026-08-22.md](../feature21_qmlp_dma_optimization_2026-08-12/ASIC_REMOTE_EDA_RUN_2026-08-22.md) |
| ASIC IRQ/WFI full-chain 功耗证据 | [../feature21_qmlp_dma_optimization_2026-08-12/ASIC_IRQ_WFI_FULLCHAIN_POWER_2026-08-26.md](../feature21_qmlp_dma_optimization_2026-08-12/ASIC_IRQ_WFI_FULLCHAIN_POWER_2026-08-26.md) |
| 论文收口审计 | [27_thesis_closeout_audit_2026-08-26.md](27_thesis_closeout_audit_2026-08-26.md) |
| ASIC r4/r5a/r5g 历史运行证据 | [../feature21_qmlp_dma_optimization_2026-08-12/ASIC_REMOTE_EDA_RUN_2026-08-20.md](../feature21_qmlp_dma_optimization_2026-08-12/ASIC_REMOTE_EDA_RUN_2026-08-20.md) |
| Full-chain profiling v2 plan | [13_fullchain_profiling_v2_plan.md](13_fullchain_profiling_v2_plan.md) |
| 论文实验表格草案 | [14_paper_experiment_tables.md](14_paper_experiment_tables.md) |
| 评审用一页摘要 | [15_review_brief.md](15_review_brief.md) |
| 相关工作扩展文献库 | [16_related_work_extended_bibliography.md](16_related_work_extended_bibliography.md) |
| 毕业论文参考文献库规划 | [17_thesis_reference_library_plan.md](17_thesis_reference_library_plan.md) |
| 工作量与创新点评估 | [18_workload_innovation_assessment.md](18_workload_innovation_assessment.md) |
| 高质量参考文献筛选 | [19_high_quality_reference_screening.md](19_high_quality_reference_screening.md) |
| 论文绪论与相关工作正文草稿 | [20_thesis_intro_related_work_draft.md](20_thesis_intro_related_work_draft.md) |
| 后续工作整理与执行顺序 | [21_followup_work_plan.md](21_followup_work_plan.md) |
| 正式论文内容落地包 | [22_thesis_formal_content_pack.md](22_thesis_formal_content_pack.md) |
| 论文图表生成包 | [23_thesis_figure_generation_pack.md](23_thesis_figure_generation_pack.md) |
| 论文材料 readiness 与补实验 ELF 清单 | [24_thesis_readiness_and_experiment_elf_manifest.md](24_thesis_readiness_and_experiment_elf_manifest.md) |
| 本地 Visio VSDX 生成交接与论文收口清单 | [25_local_visio_vsdx_handoff_and_thesis_todo.md](25_local_visio_vsdx_handoff_and_thesis_todo.md) |
| 毕业论文学术章节大纲与字数规划 | [26_thesis_academic_chapter_outline.md](26_thesis_academic_chapter_outline.md) |
| 2026-06-24 active benchmark reset retest | [../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-24/fullchain-benchmark-academic-outline-reset-result-2026-06-24.md](../../logs/radar_nexysvideo/runtime/feature21-full-test-2026-06-24/fullchain-benchmark-academic-outline-reset-result-2026-06-24.md) |
| Feature21 validation report | [../../logs/radar_nexysvideo/runtime/feature21-v1p4a-compact-validation-1000-75mhz-2026-06-08.md](../../logs/radar_nexysvideo/runtime/feature21-v1p4a-compact-validation-1000-75mhz-2026-06-08.md) |
| QMLP test common | [../../tests/radar_qmlp_test_common.h](../../tests/radar_qmlp_test_common.h) |
| DMA common | [../../tests/radar_axi_dma_common.h](../../tests/radar_axi_dma_common.h) |
| QMLP 共享核心 RTL | [../../generators/chipyard/src/main/scala/radar/RadarQMLP.scala](../../generators/chipyard/src/main/scala/radar/RadarQMLP.scala) |
| Feature21 共享核心 RTL | [../../generators/chipyard/src/main/scala/radar/RadarFeature21.scala](../../generators/chipyard/src/main/scala/radar/RadarFeature21.scala) |
| DMA/FPGA 路由 RTL | [../../fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala](../../fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala) |
| Wide23 四档 FPGA bitstream/post-route | [../../fpga/deliverables/radar_wfi_matrix_20260812/variants/](../../fpga/deliverables/radar_wfi_matrix_20260812/variants/) |
| Wide23 四档 release 板测包 | [../../fpga/deliverables/radar_wfi_matrix_20260812/board_test_20260814_release/](../../fpga/deliverables/radar_wfi_matrix_20260812/board_test_20260814_release/)；[tar.gz](../../fpga/deliverables/radar_wfi_matrix_20260812/board_test_20260814_release.tar.gz) |
| Wide23 四档板测收口证据 | [../feature21_qmlp_dma_optimization_2026-08-12/FPGA_BOARD_SMOKE_2026-08-19.md](../feature21_qmlp_dma_optimization_2026-08-12/FPGA_BOARD_SMOKE_2026-08-19.md) |

## Obsidian 镜像

Obsidian 主入口：

`/home/soooarr/obsidian/项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md`

Obsidian 中使用 `[[WikiLink]]` 做主题连接，repo 中使用相对 Markdown 链接做版本化证据索引。两边的原则是：读写体验放 Obsidian，事实证据以本目录和 repo/logs 为准。
