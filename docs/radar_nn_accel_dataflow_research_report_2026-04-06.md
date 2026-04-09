# NN 加速器架构与数据搬运协同优化调研报告

更新时间：2026-04-06  
适用对象：当前 `Chipyard/Rocket + DDR + AXI DMA + AXIS QMLP` 平台后续论文选题与实现路线

## 1. 当前项目基线

当前仓库已经完成的板级基线是：

- Rocket 单核 SoC
- DDR / MIG
- AXI DMA
- AXI4-Stream 预处理链
- 固定功能 `21 -> 64 -> 32 -> 2 INT8 QMLP`
- 单 ELF 综合回归
- QMLP 多样本板级对拍

当前最关键的实验结论来自：

- [243-qmlp-multisample-pass-summary-2026-04-06.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/243-qmlp-multisample-pass-summary-2026-04-06.md)

已知数据：

- `QMLP` 硬件本体平均计算周期：`3554 cycles`
- 在 `50 MHz` 下，硬件本体单次推理延迟约：`71.08 us`
- 当前 bare-metal + DMA + 轮询路径下端到端单次延迟约：`178.67 ms`

因此，当前论文后续工作不能只做“算子本体”，也不能只做“搬运链路”；更合适的方向是：

- 以 **可解释、可扩展的 NN accelerator 架构** 为主线
- 以 **数据搬运 / 数据流优化** 作为系统级协同优化贡献

## 2. 调研目标与筛选规则

本次调研聚焦两个方向：

1. **加速器架构方向**
   - PE 阵列
   - MAC 阵列
   - 稀疏支持
   - attention / MLP / GEMM 专用架构
2. **数据搬运与数据流方向**
   - tiling / mapping
   - 片上 buffer / FIFO / ping-pong
   - DRAM 访问削减
   - 调度、流式融合、IO-aware 设计

筛选规则：

- 时间：优先 `2020~2025`
- 来源：ISCA / HPCA / ASPLOS / MICRO / TCAD / arXiv 预印本 / 公开项目主页 / 官方机构论文页
- 选择标准：优先近五年高影响或高引用代表作

说明：

- 部分论文可直接从公开页面看到引用数字或被 survey 明确列为代表作
- 部分论文虽然页面未直接显示引用数，但属于该方向公认高影响工作，且被后续 survey、项目主页、课程材料频繁引用

## 3. 方向 A：NN 加速器架构代表工作

### 3.1 代表论文列表

| 论文 | 年份 | 方向关键词 | 代表创新点 | 对本项目可借鉴点 | 实现工作量判断 |
|---|---:|---|---|---|---|
| SIGMA: A Sparse and Irregular GEMM Accelerator with Flexible Interconnects for DNN Training | 2020 | 稀疏 GEMM、灵活互连 | 针对不规则/稀疏 GEMM 设计可重构互连与归约树，避免传统刚性 systolic 阵列利用率下降 | 后续如果做通用 FC/GEMM PE 阵列，可直接借鉴“阵列不是固定全广播，而是灵活分发 + 归约”的思路 | 高 |
| FTRANS: Energy-Efficient Acceleration of Transformers using FPGA | 2020 | FPGA、Transformer、权重压缩 | 用块循环矩阵压缩 + FPGA 架构协同，解决大模型无法直接上板问题 | 适合借鉴“冻结模型 + 参数压缩 + 板级加速闭环”这一路线 | 中 |
| SpAtten: Efficient Sparse Attention Architecture with Cascade Token and Head Pruning | 2020/2021 | sparse attention、token/head pruning | 将 token/head 动态裁剪、top-k 排序和 progressive quantization 统一到 attention accelerator 中 | 适合后续如果从 QMLP 扩展到轻量 attention block，可直接借鉴“先算法剪枝，再做硬件 top-k/support logic” | 高 |
| S2TA: Exploiting Structured Sparsity for Energy-Efficient Mobile CNN Acceleration | 2021 | structured sparsity、systolic array | 利用结构化稀疏替代非结构化稀疏，降低硬件复杂度并提高能效 | 对当前 FPGA 平台最有价值，适合作为“PE 阵列 + 可预测稀疏”路线的重要参考 | 高 |
| ELSA: Hardware-Software Co-design for Efficient, Lightweight Self-Attention Mechanism in Neural Networks | 2021 | 轻量 attention、软硬件协同 | 用近似关系筛除无效 attention 计算，并设计专门硬件支持 | 对论文写法很有价值，能证明“算法近似 + 架构支持”是高质量路线 | 中高 |
| Sanger: A Co-Design Framework for Enabling Sparse Attention using Reconfigurable Architecture | 2021 | sparse attention、reconfigurable | 将 sparse attention 的软件模式与重构式硬件架构联动，兼顾灵活性和稀疏效率 | 适合后续如果你不想一上来做大 PE 阵列，而想做“可配置数据通路” | 高 |
| AccelTran: A Sparsity-Aware Accelerator for Dynamic Inference with Transformers | 2023 | dynamic sparsity、tiling、transformer | 运行时剪枝 + 矩阵分块 + 多 dataflow 协同，提高 Transformer 推理吞吐与能效 | 适合你后续从固定 QMLP 走向更一般 MLP/attention accelerator 时参考 | 中高 |

### 3.2 高影响支撑说明

本方向中，以下论文可以直接从公开页面获得较明确的影响力证据：

- `SIGMA`
  - 公开页显示约 `449 citations`
  - 来源：Semantic Scholar 镜像页检索结果  
  - DOI：`10.1109/HPCA47549.2020.00015`
- `Sanger`
  - 公开页显示约 `198 citations`
  - 来源：Semantic Scholar 镜像页检索结果  
  - DOI：`10.1145/3466752.3480125`
- `AccelTran`
  - 公开页显示 `39 Scopus citations`
  - 来源：Princeton 页面  
  - DOI：`10.1109/TCAD.2023.3273992`

另外：

- `FTRANS / SpAtten / ELSA / S2TA` 均是该方向公开 survey、实验室主页、FPGA/Transformer 加速综述里反复出现的代表作
- `SpAtten`、`ELSA` 还被 2023~2025 的 Transformer accelerator survey 明确列入代表方案

### 3.3 对本项目的直接启发

结合当前仓库状态，架构方向最值得吸收的不是“做一个很大很泛的 accelerator”，而是三件事：

1. **从固定 QMLP 过渡到小型 PE/MAC 阵列**
   - 当前 `RadarQMLP.scala` 本质上还是固定功能硬件
   - 后续论文更有说服力的做法，是把 L1/L2/L3 的计算抽象成：
     - 一个可配置 `GEMV/GEMM` 内核
     - 配套小型 `PE array` 或 `MAC tile`
2. **优先支持可预测结构化稀疏，而不是一上来做完全不规则稀疏**
   - 这点更贴近 `S2TA`
   - 也更符合当前 FPGA 和论文工作量
3. **保留当前 AXI-Stream 接口，不重构整个 SoC**
   - 继续沿用：
     - `DDR -> MM2S -> Accelerator -> S2MM -> DDR`
   - 这样改动局部、风险小、对比实验也清楚

## 4. 方向 B：数据搬运 / 数据流优化代表工作

### 4.1 代表论文列表

| 论文 | 年份 | 方向关键词 | 代表创新点 | 对本项目可借鉴点 | 实现工作量判断 |
|---|---:|---|---|---|---|
| CoSA: Scheduling by Constrained Optimization for Spatial Accelerators | 2021 | 调度、tiling、mapping | 将空间加速器调度问题统一为约束优化，联合考虑 loop tiling / permutation / spatial mapping | 非常适合你后续设计 PE 阵列后做 mapping 策略，不必靠手工拍脑袋 | 中 |
| Mind Mappings: Enabling Efficient Algorithm-Accelerator Mapping Space Search | 2021 | mapping search、优化 | 用可微近似搜索 mapping space，比传统启发式更快更稳 | 对论文的方法论很有帮助，适合做设计空间探索章节 | 中 |
| Gamma: Leveraging Gustavson's Algorithm to Accelerate Sparse Matrix Multiplication | 2021 | 数据复用、显式数据编排 | 围绕稀疏矩阵乘的数据重用与显式调度，重点解决“怎么少搬数据” | 对后续稀疏 PE 阵列尤其有参考价值 | 中高 |
| Sparseloop: An Analytical Approach To Sparse Tensor Accelerator Modeling | 2022 | 建模、dataflow、稀疏加速 | 统一建模 sparse tensor accelerator，快速分析不同 dataflow / data movement 成本 | 对论文实验设计很有帮助，可指导 buffer 和 dataflow 取舍 | 中 |
| FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness | 2022 | IO-aware、tiling、HBM/SRAM | 把 attention 视为 IO 问题而不是纯算力问题，通过分块显著减少外存访存 | 非常适合作为你论文中“为什么必须同步优化搬运”的论据 | 中 |
| FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning | 2023 | work partitioning、并行分工 | 在 FlashAttention 基础上进一步优化线程/块/片上通信分工 | 可直接转化为你后续“PE 阵列内部如何分工、如何减少共享缓冲冲突”的思路 | 中 |

### 4.2 高影响支撑说明

本方向中，以下论文可以直接从公开页面看到较明确的影响证据：

- `Gamma`
  - 公开页显示约 `79 citations`
  - 来源：Scinapse / NSF 页面
  - DOI：`10.1145/3445814.3446702`
- `FlashAttention / FlashAttention-2`
  - 虽当前检索页未直接给出统一引用数字，但已是 Transformer/LLM 系统方向最常用的 IO-aware 代表作
  - 公开 survey 与项目主页均将其列为关键基线
- `CoSA / Mind Mappings / Sparseloop`
  - 在 spatial accelerator 设计空间探索与映射优化领域属于高影响基础工作
  - 公开实验室主页、arXiv 页面和后续研究中被反复引用

### 4.3 对本项目的直接启发

当前仓库的真实实验已经证明：

- `QMLP` 本体：`71 us`
- 端到端：`178.67 ms`

所以，论文里如果完全不做数据搬运优化，会出现两个问题：

1. **系统性能论证不完整**
   - 因为最终 wall-clock 慢的主要不是 `QMLP` 本体
2. **PE 阵列优化收益会被外围调度开销淹没**
   - 即使算子本体更快，端到端也不一定显著改善

因此对当前项目来说，数据搬运方向最值得优先做的是：

1. **多样本 batching**
   - 不要每个样本都完整启停一次 DMA/轮询一次
2. **层间或样本间 ping-pong buffer**
   - 减少 DDR 往返
3. **权重常驻 / 片上缓存**
   - 避免每次都走完整外存读路径
4. **固定长度流式 packet 化**
   - 让 AXIS 传输和 PE 阵列配合更稳定
5. **将当前 bare-metal 轮询式调度收紧**
   - 当前端到端延迟高，很大一部分来自外围控制路径

## 5. 结合本项目后的三套可实现路线

### 方案 A：小型 GEMV/GEMM PE 阵列 + 多样本批处理

#### 核心思路

- 以当前固定 `QMLP` 为 baseline
- 将 `21 -> 64 -> 32 -> 2` 的逐层计算重构成一个可复用 `PE/MAC` 小阵列
- 软件侧改成多样本连续输入
- DMA 一次搬更多样本

#### 论文创新点

- 从固定功能 `QMLP` 升级为可配置小型 `PE array`
- 证明同一 SoC 中：
  - 固定功能 vs 小型阵列
  - 单样本搬运 vs 多样本 batching
  的差异

#### 工作量

- 中等偏高
- 最容易落地
- 最适合你当前已有的 `QMLP` 代码基础

#### 推荐度

- **最高**

### 方案 B：结构化稀疏 PE 阵列 + 压缩数据搬运

#### 核心思路

- 借鉴 `S2TA / SIGMA`
- 让 `PE array` 支持结构化稀疏权重或激活
- 同时设计压缩格式与对应的数据装载/展开路径

#### 论文创新点

- “阵列结构 + 稀疏格式 + 搬运协议”一体化
- 创新性强于单纯小阵列

#### 工作量

- 高
- 对验证、对拍和 AXIS/DMA 对接要求更高

#### 推荐度

- **中高**
- 适合在方案 A 打稳后继续推进

### 方案 C：层间流式融合 + 片上 buffer / ping-pong 优化

#### 核心思路

- 不急着把 PE 阵列做很大
- 先围绕当前 MLP 三层做：
  - layer fusion
  - on-chip buffer
  - ping-pong
  - 减少 DDR round-trip

#### 论文创新点

- 系统导向更强
- 能直接解释“为什么当前 QMLP 本体很快但端到端仍慢”

#### 工作量

- 中等
- 架构创新性略弱于方案 A/B

#### 推荐度

- **中**
- 更适合作为方案 A 的配套优化，不建议单独作为主线

## 6. 推荐的论文主线

结合当前平台状态，我最推荐的不是“只做 accelerator”，也不是“只做搬运”，而是：

### 推荐主线

**以小型 PE/MAC 阵列 NN accelerator 为主线，以多样本 batching + buffer/dataflow 优化为配套贡献。**

### 为什么这样更适合论文

因为你现在已经有：

- SoC 平台
- DMA 主链
- QMLP baseline
- 单样本和多样本板测通过

这意味着论文可以非常自然地写成：

1. 基线系统搭建
2. 固定 QMLP accelerator 验证
3. 发现端到端瓶颈不在算子本体
4. 提出 PE 阵列 NN accelerator
5. 同步引入数据搬运优化
6. 做性能 / 资源 / 延迟对比

这种结构比“只做一个算子 IP”更完整，也更符合硕士论文工作量。

## 7. 对当前仓库的建议落点

如果后续真的进入实现，建议新开分支，不要直接在当前稳定板测分支上硬改。

推荐分支名：

- `feature/qmlp-pe-array-v1`
- `feature/qmlp-batching-dma`
- `feature/qmlp-sparse-pe-array`

建议实施顺序：

1. 先保留当前 `RadarQMLP.scala` 作为 baseline
2. 单独实现一个小型 `PE/MAC tile`
3. 再把 DMA 入口改成多样本 batching
4. 最后再考虑结构化稀疏

## 8. 参考文献与入口链接

### 架构方向

1. SIGMA  
   DOI: `10.1109/HPCA47549.2020.00015`
2. FTRANS  
   DOI: `10.1145/3370748.3406567`
3. SpAtten  
   arXiv: `https://arxiv.org/abs/2012.09852`
4. S2TA  
   arXiv: `https://arxiv.org/abs/2107.07983`
5. ELSA  
   DOI: `10.1109/ISCA52012.2021.00060`
6. Sanger  
   DOI: `10.1145/3466752.3480125`
7. AccelTran  
   DOI: `10.1109/TCAD.2023.3273992`

### 数据搬运 / 数据流方向

1. CoSA  
   arXiv: `https://arxiv.org/abs/2105.01898`
2. Mind Mappings  
   arXiv: `https://arxiv.org/abs/2103.01489`
3. Gamma  
   DOI: `10.1145/3445814.3446702`
4. Sparseloop  
   arXiv: `https://arxiv.org/abs/2205.05826`
5. FlashAttention  
   arXiv: `https://arxiv.org/abs/2205.14135`
6. FlashAttention-2  
   arXiv: `https://arxiv.org/abs/2307.08691`

### 辅助综述

- [A Survey on Sparsity Exploration in Transformer-Based Accelerators](https://www.mdpi.com/2079-9292/12/10/2299)
- [A Survey on Hardware Accelerators for Large Language Models](https://www.mdpi.com/2076-3417/15/2/586)
