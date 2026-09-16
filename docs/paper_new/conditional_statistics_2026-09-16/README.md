# 点数、形态、统计精度与共享计算：主线复核及受控实现

2026-09-16。已经按原研究问题完成一轮隔离实现和六组受控训练，补上 RF 参照与历史样本过滤审计。**输出定标是明确的强基线；矩统计有条件性线索，但尚未证明最终质量—成本优势。** 没有把“训练停止”当作“算法已证明收敛”，也没有先改 RTL。

持续研究的问题：**在点数和目标形态变化时，哪些近似会损害分类稳定性？能否针对这些误差，用更合适的统计表示、精度分配和共享计算结构，获得优于现有实现的质量—成本取舍？** 已写入[持久要求入口](../00_project_requirements_and_memory.md)，RF、删维、QAT 和 RTL 都服务于它。

## 快速阅读

1. [结果与归因](02_结果与归因.md)：先看完整数据、两张图、条件翻转、RF 和舍弃样本。
2. [评审与下一步门槛](03_评审与下一步门槛.md)：哪些成立、哪些不能宣称、下一轮只需要回答什么。
3. [算法与可运行实现](01_算法与实现.md)：公式、精度、共享状态、主机 C 使用方法。
4. [原主线复核](00_研究主线复核.md)、[执行前冻结计划](plan.json)：本轮约束和已有方法边界。

## 已得到的关键结果

| 表示 | 全量开发 validation F1，seed 7/17 | 判断 |
| --- | --- | --- |
| 原有 21 维冻结 INT8 | 97.4957% / 97.5364% | 复用强基线 |
| 旧代理仅逐特征定标 | 98.0547% / 98.0806% | 必须保留的简单对照 |
| 局部平移矩统计 Q24 | 97.9643% / 98.1438% | 减点条件有线索，未全面优于定标 |
| 局部平移矩统计 Q16 | 98.0792% / 98.2036% | 未通过预设条件容差；训练达到预算上限 |

完整 train 357,780 条，validation 80,450 条；3,448 个相同验证点簇做五种预定输入条件。新训练只有 6 条轨迹，CPU 2 线程，GPU 0。

- 固定 Q24 权重单独换 Q16，诊断条件预测均不变，全量只变化数条；不同重训分数不能直接当作位宽影响。
- 两个固定 RF 已运行，组置换显示速度/RCS 依赖较强；没有按低排名盲目删除特征。
- 原始目标类有轨迹观测中，历史 min_points=3 排除了 train **57.0163%**、validation **54.8500%** 的单点/两点观测。分母是观测数，不能写成点数或独立物体数。
- 单遍 C 共享前端 **51,720** 项等价对拍通过；完整 C 分类候选 **20,688** 项对拍通过，提供[可独立编译的六套源码与例子](candidate_c_bundle.zip)。

未证明 21 最优，未新增独立最终测试或原生单点/两点分类实验；本轮没有新 RTL、Rocket ELF、bitstream 或板测成本。历史工件保持原状，实际校验见[validation.json](validation.json)。

## 证据与同步

- [结果 CSV](results.csv)、[完整评价与区间](../../../logs/conditional_statistics_20260916/evaluation/summary.json)、[条件分组表](../../../logs/conditional_statistics_20260916/evaluation/conditional_groups.csv)
- [单遍共享成本图](../../../logs/conditional_statistics_20260916/shared/cost_graph.json)、[完整 C 推理检查](../../../logs/conditional_statistics_20260916/inference/summary.json)
- [RF 及组置换](../../../logs/conditional_statistics_20260916/rf/summary.json)、[过滤观测明细](../../../logs/conditional_statistics_20260916/data/filter_observations.csv)
- [最终证据清单](evidence_manifest.json)、[Obsidian 本地镜像清单](obsidian_sync_manifest.json)：云端同步状态不由本机文件写入证明。

此前 [完整 QAT](../qmlp_int8_convergence_2026-09-16/README.md)、[修正/重训负结果](../feature_approximation_pilot_2026-09-16/README.md)、[研究文献与合成预检](../feature_approximation_research_2026-09-16/README.md)继续作为历史证据保留。本页及持久要求是后续算法研究优先入口，旧“先做森林筛选”的临时顺序由本页复核取代。
