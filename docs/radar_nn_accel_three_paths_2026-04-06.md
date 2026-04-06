# 基于当前 NexysVideo SoC 基线的 NN 加速器三套可行方案

## 1. 当前平台边界与设计前提

说明：

- 文中算子路线与硬件设计判断基于当前工程代码、板测结果和所列论文原文。
- 文中的引用量数字仅作为选题热度参考，来自 `Emergent Mind`、`ACM PDF front matter`、`Scopus` 等公开元数据页面，查询时间统一为 `2026-04-06`。

### 1.1 当前已经稳定的硬件基线

当前工程已经稳定跑通的板级基线为：

- 单核 `Rocket RV64IMAC` soft CPU
- `DDR(MIG)` 外部存储
- `AXI MMIO + AXI DMA + AXI4-Stream` 数据通路
- `MM2S -> AXIS Preprocessor -> S2MM` 硬件流处理链
- `cacheable + cache maintenance` 与 `uncached alias` 两条 DMA buffer 路径

当前通过验证的关键结论见：

- [152-final-loopback-pass-summary-2026-03-31.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/152-final-loopback-pass-summary-2026-03-31.md)
- [186-integrated-regression-with-uncached-pass-summary-2026-04-01.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/186-integrated-regression-with-uncached-pass-summary-2026-04-01.md)
- [213-preproc-pass-summary-2026-04-01.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/213-preproc-pass-summary-2026-04-01.md)

当前稳定实现频点仍以 `50 MHz` 为准。`60 MHz` 和 `75 MHz` 均已出现实现后时序失败，见：

- [217-75mhz-criticalpath-summary-2026-04-05.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/217-75mhz-criticalpath-summary-2026-04-05.md)
- [220-fpga-bitstream-60mhz-2026-04-05.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/220-fpga-bitstream-60mhz-2026-04-05.log)

因此，后续 NN 加速器设计不应默认依赖“继续提频”，而应优先依赖：

- 更清晰的 AXI/AXIS 数据分工
- 更高的片上数据复用
- 更少的 DDR 往返
- 更低的控制复杂度

### 1.2 当前平台最适合承载的加速器形态

结合现有工程，后续最合理的方向不是“一次性做完整网络 SoC”，而是做 **可被 CPU 调度、由 DMA 喂数、通过 AXI-Stream 工作的层级算子/子网络加速器**。推荐工作模式为：

`SD/CPU -> DDR -> MM2S -> NN accelerator -> S2MM -> DDR -> CPU`

其中 CPU 的角色是：

- 从 `SD` 或测试数组准备输入
- 管理权重与中间特征图在 DDR 中的位置
- 配置 accelerator CSR
- 启动 DMA
- 统计周期数/吞吐/结果校验

CPU 不应承担主计算，主计算应由硬件数据通路完成。

## 2. 三套可行方案

---

## 方案 A：面向雷达/BEV 主干的二维 PE 阵列卷积加速器

### 2.1 方案定义

该方案以 **规则二维 PE 阵列 + MAC 累加树 + 行缓冲/权重缓冲** 为核心，优先支持以下算子：

- `3x3 Conv`
- `1x1 Conv`
- `Depthwise/Pointwise`
- `ReLU`
- 可选 `MaxPool`

建议不要一上来就支持完整网络，而是先支持雷达或 BEV 主干中最常见的卷积块，例如：

- `Conv -> BN(折叠) -> ReLU`
- `1x1 -> 3x3 -> 1x1`
- 多层卷积串行执行

在当前工程中，最自然的接法是：

`MM2S -> line buffer / ifmap buffer -> PE array -> partial-sum / output buffer -> S2MM`

### 2.2 为什么最适合当前项目

这一方案与当前工程最匹配，原因有四点：

1. 当前工程已经验证了稳定的 `DDR -> MM2S -> AXIS -> S2MM -> DDR` 主链。
2. 现有 `RadarAXISPreprocessor` 已经证明中间插入一个流处理模块是可行的。
3. 二维卷积/1x1-GEMM 的数据访问模式规则，最容易先做出论文中能交代清楚的硬件结构。
4. 雷达前处理、BEV 编码、以及许多轻量 CNN 主干，本质上都能落到 `Conv/GEMM + Activation` 这一类算子。

### 2.3 预期论文创新点

如果选这一条路线，论文创新点不应仅仅停留在“我实现了一个 PE 阵列”，而应落到下面这些更具体的点：

- 面向当前 `AXI DMA + DDR` 平台的分块调度策略
- 针对 `50 MHz` FPGA SoC 的片上缓冲尺寸与 DDR 访问次序优化
- 针对雷达/BEV 特征图尺寸的 tile 切分方式
- 卷积块与 AXI-Stream 数据通路的对接方式
- 以 `C` 侧驱动 + `Chisel` RTL + 板测周期统计形成完整实验链

### 2.4 推荐落地顺序

建议分三步：

1. `v1`
   只做 `3x3 Conv + ReLU`
2. `v2`
   扩展到 `1x1 + 3x3 + 1x1`
3. `v3`
   引入更像雷达/BEV 主干的 residual block 或 neck block

### 2.5 论文支撑

#### 论文 1

- `BEVDet: High-Performance Multi-Camera 3D Object Detection in Bird-Eye-View`
- 2021
- 论文页：https://arxiv.org/abs/2112.11790
- 引用量元数据：`562`，来源 `Emergent Mind`，查询时间 `2026-04-06`
- 可提炼的点：
  - `BEV` 主干计算可拆成图像编码、视角变换、BEV 编码、检测头
  - `BEV encoder` 本身非常适合落成规则卷积/GEMM 加速器
  - 文章强调了精度与速度的权衡，适合作为“边缘雷达/视觉感知”类论文背景

#### 论文 2

- `BEVFusion: Multi-Task Multi-Sensor Fusion with Unified Bird's-Eye View Representation`
- 2022
- 论文页：https://arxiv.org/abs/2205.13542
- 引用量元数据：`717`，来源 `Emergent Mind`，查询时间 `2026-04-06`
- 可提炼的点：
  - 提出了统一 `BEV` 表征
  - 文中明确指出 view transform 是效率瓶颈，并给出了 `40x` latency reduction 的工程方向
  - 适合支撑“为什么需要为 BEV 主干设计专用硬件”

#### 论文 3

- `BEVFormer: Learning Bird's-Eye-View Representation from Multi-Camera Images via Spatiotemporal Transformers`
- 2022
- 论文页：https://arxiv.org/abs/2203.17270
- 引用量元数据：`1032`，来源 `Emergent Mind`，查询时间 `2026-04-06`
- 可提炼的点：
  - 说明了后续系统可能从纯卷积主干演化到带时序/注意力的主干
  - 适合在论文中作为后续扩展目标
  - 也说明先做规则 BEV/CNN block 是合理的第一步

### 2.6 结论

这是三套方案里 **最稳、最容易做出完整板级结果** 的一条。  
如果你的目标是优先保证论文可完成度、工作量可展示、板级结果能跑通，方案 A 是第一推荐。

---

## 方案 B：结构化稀疏 PE 阵列加速器

### 3.1 方案定义

该方案不是做纯 dense PE 阵列，而是做 **支持结构化稀疏/层级稀疏的 PE 阵列**。核心点不只是 MAC，而是：

- 非零值与索引/元数据分离
- 稀疏块调度
- 跳零执行
- 稀疏模式下的片上 FIFO 与权重缓冲组织

对当前项目，建议优先选择 **结构化稀疏**，而不是完全非结构化稀疏。原因是：

- 更容易在 Chisel 里实现
- 更容易在 FPGA 上保证时序
- 更适合作为硕士论文中的“可解释硬件创新”

### 3.2 为什么适合当前项目

你现在的平台已经有：

- DDR
- DMA
- AXI-Stream
- 本地 CSR 配置

这意味着你已经具备做“数据流算子 + 元数据配置”的硬件基础。  
如果在 PE 阵列之上继续加入：

- `group-wise sparsity`
- `N:M sparsity`
- `hierarchical sparsity`

那么论文中的创新性会明显高于“纯卷积阵列”。

### 3.3 预期论文创新点

这一方案能做出的创新点包括：

- 面向 `NexysVideo + DDR + DMA` 的结构化稀疏执行流
- 稀疏权重/稀疏激活的 AXIS 数据封装
- 非零块选择与 PE 派发策略
- 稀疏元数据与数据本体分离缓存
- 稀疏模式下的吞吐/能耗/资源折中

### 3.4 推荐落地顺序

建议不要一步到位做全稀疏卷积，而是按以下顺序：

1. `v1`
   dense PE 阵列先跑通
2. `v2`
   支持 `weight-only structured sparsity`
3. `v3`
   扩展到 `weight + activation` 双侧稀疏

### 3.5 论文支撑

#### 论文 1

- `ESCALATE: Boosting the Efficiency of Sparse CNN Accelerator with Kernel Decomposition`
- MICRO 2021
- 论文页：https://par.nsf.gov/biblio/10300691-escalate-boosting-efficiency-sparse-cnn-accelerator-kernel-decomposition
- DOI：`10.1145/3466752.3480043`
- 可提炼的点：
  - 不是简单依赖传统 pruning，而是把 kernel decomposition 与硬件设计一起考虑
  - 提出了 `Basis-First` 数据流
  - 适合支撑“稀疏 CNN 加速器不应只停留在跳零，而要连数据流一起设计”

#### 论文 2

- `Sense: Model-Hardware Codesign for Accelerating Sparse CNNs on Systolic Arrays`
- IEEE TVLSI 2023
- 论文页：https://ieeexplore.ieee.org/document/10043636/
- 可提炼的点：
  - 直接把稀疏 CNN 与 systolic array 结合
  - 非常适合给你做“PE 阵列 + 稀疏化”的论文路线背书
  - 说明稀疏并不一定排斥阵列结构，关键在于模型-硬件协同

#### 论文 3

- `HighLight: Efficient and Flexible DNN Acceleration with Hierarchical Structured Sparsity`
- MICRO 2023
- 论文页：https://arxiv.org/abs/2305.12718
- 项目页：https://emze.csail.mit.edu/highlight
- 可提炼的点：
  - 重点不只是“稀疏”，而是“如何同时兼顾效率与灵活性”
  - 文章提出的 `hierarchical structured sparsity` 很适合转化成论文中的创新口径
  - 对你非常有价值的一点是：它强调“dense 到 sparse 的连续过渡”，这比做死一种稀疏模式更适合硕士论文

### 3.6 结论

这是三套方案里 **论文创新性最高、同时仍然能落在你现有 AXI/DMA/DDR 平台上的一条**。  
如果你希望论文比“普通 PE 阵列”更有新意，又不想直接跳到 Transformer 这种高风险方向，方案 B 是最适合的主线。

---

## 方案 C：面向 BEV/Transformer 子模块的注意力加速器

### 4.1 方案定义

该方案不是做整个 Transformer，而是做 **一个可被 CPU 调度的 attention 子加速器**，例如：

- `QK^T` block
- attention score top-k / mask block
- `softmax` 前后的稀疏化或裁剪 block
- `V` 加权累加 block

如果直接在当前平台上做，建议目标是：

- local attention
- static structured sparse attention
- token/head pruning

而不是完整做大模型推理。

### 4.2 为什么适合当前项目

这一方案与雷达方向并不冲突。原因是：

- 近两年很多 `BEV` 感知模型已经明显引入 transformer/attention
- 雷达/多传感器融合里也越来越多地使用 cross-attention
- 你现在的 `AXIS Preprocessor` 已经证明“流式中间算子”是可行的

因此，把下一步升级为“attention block accelerator”，在论文上是说得通的。

### 4.3 预期论文创新点

这一方案的创新点可放在：

- 针对 edge SoC 的 attention block 切分
- 静态稀疏 mask 或局部窗口 mask
- token/head 剪枝与硬件 top-k 支持
- 针对 DDR/AXI 的 tile 化 attention 调度

### 4.4 风险

这是三条路线里风险最高的一条：

- softmax 与归一化处理复杂
- 矩阵维度变化较大
- 片上 buffer 压力更大
- 时序和控制复杂度都高于卷积阵列

因此更适合作为 **第二阶段或后续扩展方向**，不建议作为第一颗硬件化 NN 模块。

### 4.5 论文支撑

#### 论文 1

- `Sanger: A Co-Design Framework for Enabling Sparse Attention using Reconfigurable Architecture`
- MICRO 2021
- 论文页：https://liqianglu-zju.github.io/files/conference/2021/MICRO_2021_Sanger.pdf
- DOI：`10.1145/3466752.3480125`
- 引用量元数据：`156`，来源 `ACM PDF front matter`，查询时间 `2026-04-06`
- 可提炼的点：
  - 直接面向 sparse attention 的软硬件协同设计
  - 适合支撑“为什么 attention 不该简单丢到普通 GEMM 上跑”
  - 与 FPGA/reconfigurable 语境也较接近

#### 论文 2

- `AccelTran: A Sparsity-Aware Accelerator for Dynamic Inference with Transformers`
- TCAD 2023
- 论文页：https://arxiv.org/abs/2302.14705
- Princeton 条目：https://collaborate.princeton.edu/en/publications/acceltran-a-sparsity-aware-accelerator-for-dynamic-inference-with
- 引用量元数据：`39`，来源 `Scopus` 元数据页，查询时间 `2026-04-06`
- 可提炼的点：
  - 提出 `DynaTran`，强调动态剪枝与 tile/dataflow
  - 很适合给你的论文提供“如何从 attention 算法约束映射到硬件调度”的参考
  - 适合转化为“边缘 SoC 上的轻量 attention block”

#### 论文 3

- `Efficient Transformer Inference with Statically Structured Sparse Attention`
- DAC 2023
- 论文页：https://research.nvidia.com/publication/2023-07_efficient-transformer-inference-statically-structured-sparse-attention
- 可提炼的点：
  - 重点是 `static structured sparse attention`
  - 文中给出 `56.6%` energy reduction、`58.9%` performance improvement、`<1%` accuracy loss、`2.6%` area overhead
  - 这条路线特别适合你这种 FPGA/SoC 平台，因为它更接近“结构化 mask + 可流式实现”

### 4.6 结论

这是三套方案里 **趋势感最强** 的方向，但不建议作为当前第一优先级。  
更合适的方式是：先做方案 A 或 B 的卷积/稀疏 PE 阵列，后续再把方案 C 作为论文扩展章节或下一阶段工作。

## 5. 三套方案横向对比

| 维度 | 方案 A：二维卷积/PE 阵列 | 方案 B：结构化稀疏 PE 阵列 | 方案 C：attention 子加速器 |
| --- | --- | --- | --- |
| 与当前 SoC 兼容性 | 高 | 高 | 中 |
| 首次板级成功概率 | 高 | 中高 | 中低 |
| 论文创新性 | 中 | 高 | 高 |
| 工程工作量 | 中 | 高 | 高 |
| 时序/控制风险 | 低 | 中 | 高 |
| 是否适合作为硕士主线 | 适合 | 最适合 | 不建议直接作为第一主线 |

## 6. 推荐路线

### 6.1 最推荐路线

综合当前工程完成度、板级基线、时序上限、以及论文工作量要求，推荐优先级为：

1. **方案 B：结构化稀疏 PE 阵列**
2. **方案 A：二维卷积/PE 阵列**
3. **方案 C：attention 子加速器**

### 6.2 推荐原因

原因如下：

- 如果只做方案 A，板级成功概率最高，但论文创新性容易落到“常规卷积加速器”
- 方案 B 在保持工程可落地的同时，能明显提高论文新意
- 方案 C 很新，但以你当前平台和时序上限，直接切进去风险偏大

### 6.3 最建议的实际实施顺序

建议的真正实施顺序不是直接三选一，而是：

1. 先以 **方案 A 的 dense PE 阵列** 做出第一版可运行核心
2. 在该核心上继续演化为 **方案 B 的结构化稀疏版本**
3. 如果还有时间和篇幅，再引入 **方案 C 的 attention/block 扩展**

这样做的好处是：

- 工程上不会一下子失控
- 论文中可以形成清楚的阶段演化
- 每一阶段都能产出可截图、可板测、可汇报的结果

## 7. 对当前工程的直接建议

如果从下周就开始做，最具体的建议是：

1. 不要直接做整网。
2. 先定义一个 `AXI-Stream NN block` 壳层：
   - CSR
   - input/output tensor descriptor
   - weight base address
   - tile size
   - mode
3. 第一颗算子只做：
   - `Conv3x3`
   - `ReLU`
4. 第二颗版本加入：
   - `1x1`
   - `output-stationary PE array`
   - weight buffer / psum buffer
5. 第三颗版本再做：
   - structured sparsity metadata
   - skip-aware dispatch

如果只允许选一条最适合硕士论文的主线，本文件建议最终选：

**“以规则二维 PE 阵列为基线，进一步扩展为支持结构化稀疏的 AXI-Stream NN 加速器”**

这条路线与当前工程衔接最好，板级落地概率最高，同时也最容易做出有创新点和工作量的论文结果。
