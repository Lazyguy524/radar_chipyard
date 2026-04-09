# 当前项目 CPU 是否需要提升：RISC-V CPU 路线调研与取舍报告

更新时间：2026-04-07  
适用对象：`Chipyard/Rocket + DDR + AXI DMA + AXIS Preproc/QMLP` 当前平台后续论文选题与工程路线判断

## 1. 调研背景

当前项目已经完成的板级基线包括：

- `Rocket` 单核 `RV64IMAC` SoC
- `DDR / MIG`
- `AXI DMA`
- `AXI4-Stream Preprocessor`
- 固定模型 `21 -> 64 -> 32 -> 2 INT8 QMLP`
- 单 ELF 综合回归
- `QMLP` 多样本对拍

现有实验已经给出两个很关键的事实：

1. 当前 `50 MHz` 是稳定可综合、可上板的频点。
2. 当前端到端时延的主要瓶颈不在 `QMLP` 算子本体，而在外围调度、DMA 启停、软件轮询和整体数据搬运路径。

已有本地结果：

- [243-qmlp-multisample-pass-summary-2026-04-06.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/243-qmlp-multisample-pass-summary-2026-04-06.md)
- `QMLP` 本体平均：`3554 cycles`
- `50 MHz` 下本体延迟约：`71.08 us`
- 当前端到端延迟约：`178.67 ms`

因此，这里需要回答的不是“CPU 能不能变强”，而是：

- 在当前 `Artix-7 + Rocket + DDR + DMA + AXIS accelerator` 框架下，**优先提升 CPU 是否划算**
- 如果要提升，**哪类 CPU 路线最符合论文质量与工程可落地性**

## 2. 调研范围与筛选规则

本次调研重点看 `2020~2026` 之间与下列方向直接相关的高影响工作：

- 更强的 RISC-V 微架构（如 OoO / 更高 IPC）
- RISC-V Vector / 子字节量化向量处理
- 自定义指令 / CFU / 功能单元扩展
- CPU + accelerator 协同，而不是单独堆 CPU

筛选原则：

- 优先公开论文页、arXiv、官方项目页
- 优先近五年高影响或高被引代表作
- 重点分析它们对**当前项目**是否真的合适

说明：

- 引用数会持续变化，文中使用“高影响 / 高被引代表作”的口径
- 个别工作虽然较新，但因方向高度相关，仍纳入对比

## 3. 代表论文与路线对比

### 3.1 代表工作列表

| 论文 | 年份 | 路线类型 | 关键优点 | 对本项目的直接启发 | 对本项目的实现难度 |
|---|---:|---|---|---|---|
| SonicBOOM: The 3rd Generation Berkeley Out-of-Order Machine | 2020 | 更强 OoO CPU | 以更高 IPC 提升通用执行性能，代表 RISC-V 开源高性能核路线 | 说明“换更强 CPU”理论上可行，但会显著抬高 SoC 复杂度、时序和资源压力 | 很高 |
| Ara: A 1 GHz+ Scalable and Energy-Efficient RISC-V Vector Processor | 2020 | RVV 向量核 | 基于 lane 的可扩展向量架构，面向数据并行计算 | 说明若走 RVV 路线，可把部分 MLP/GEMV 工作放到 vector side，但需要更大重构 | 很高 |
| Gemmini: An Agile Systolic Array Generator Enabling Systematic Evaluations of Deep-Learning Architectures | 2021 | CPU+专用 accelerator 协同 | 直接证明“Rocket/BOOM + 专用矩阵阵列”是成熟路线 | 对当前项目最重要：论文主线更适合 accelerator，而不是先强行升级 CPU | 中高 |
| CFU Playground: Full-Stack Open-Source Framework for tinyML Acceleration on FPGAs | 2022/2023 | 自定义指令/CFU | 软核 CPU + 小型定制功能单元可快速迭代，并在 FPGA 上闭环验证 | 适合做小规模 pre/post-processing、控制辅助或轻量算子扩展 | 中 |
| EXTREM-EDGE—Extensions To RISC-V for Energy-efficient ML inference at the EDGE of IoT | 2022 | 自定义指令 + AI 功能单元 | 用 ISA 扩展和 AI Functional Unit 一起提升边缘推理效率 | 适合借鉴“只增强 CPU 局部能力”，但不适合取代主 NN accelerator | 中高 |
| Quark: An Integer RISC-V Vector Processor for Sub-Byte Quantized DNN Inference | 2023 | 子字节整数向量核 | 针对低比特量化推理做定制向量指令，突出量化友好性 | 适合做后续低比特量化论文扩展，但对当前平台改动较大 | 很高 |
| Sparq: A Custom RISC-V Vector Processor for Efficient Sub-Byte Quantized Inference | 2023 | 自定义向量处理器 | 在 RVV 基础上加入新指令并移除无关单元，面向 QNN | 说明“做专用 vector-like 处理器”可行，但对当前 Rocket SoC 侵入大 | 很高 |
| SPEED: A Scalable RISC-V Vector Processor Enabling Efficient Multi-Precision DNN Inference | 2024 | 多精度向量 + tensor unit | 将 RVV、自定义指令、tensor unit、dataflow 结合起来 | 说明 CPU 路线一旦认真做，会迅速演变成“向量/张量处理器设计”，不再是简单提 CPU | 很高 |

### 3.2 关键节点摘录

为了便于后续截图，下面列出各论文中最值得截的“设计特征”：

1. `SonicBOOM`
   - 公开页强调其是开源高性能 OoO `RV64GC` 核，性能竞争力来自 `IPC` 和更完整的乱序微架构，而不是简单提高频率。
2. `Ara`
   - 公开摘要明确指出：向量处理器由多条相同 lane 构成，适合线性代数和矩阵类计算。
3. `Gemmini`
   - 官方页强调其直接集成到 `Rocket` / `BOOM` 生态，并通过矩阵阵列带来数量级级别加速。
4. `CFU Playground`
   - 公开摘要明确给出 `55x ~ 75x` 的 tinyML speedup，并强调软硬件快速闭环。
5. `EXTREM-EDGE`
   - 公开摘要明确是“自定义指令 + AI 功能单元”的软硬件协同。
6. `Quark / Sparq / SPEED`
   - 共同特点：一旦要让 CPU 侧真正承担 DNN 主算，架构就会向“向量核 / tensor unit / mixed dataflow”演进。

## 4. 把这些路线放回当前项目里看

### 4.1 路线一：继续提升当前 Rocket 主核

可选手段一般包括：

- 提频
- 增大 `I$/D$`
- 换更强 OoO 核
- 增加更多 CPU 核

但结合当前项目现状，这条路的问题非常明确：

1. **提频空间已经很窄**
   - 当前 `50 MHz` 稳定
   - `60 MHz`、`75 MHz` 已验证失败
   - 这说明继续靠频率吃性能，工程回报很差
2. **更大 cache 或更强核会继续加重时序和资源压力**
   - 当前板子是 `Nexys Video / Artix-7`
   - 主 SoC 时序余量本来就不宽松
3. **当前端到端瓶颈不在 CPU 核心算力**
   - 当前慢的是：
     - bring-up / bare-metal 调度
     - DMA 启停
     - 轮询等待
     - DDR 往返与数据搬运
   - 不是因为 Rocket 算不动 `QMLP`

结论：

- **不建议把“CPU 本体升级”作为论文主线**

### 4.2 路线二：把 CPU 扩展成 RVV / 向量处理器

从 `Ara / Quark / Sparq / SPEED` 可以看到，这条路线理论上很强，但对当前项目并不友好。

原因：

1. 这已经不是“小改 CPU”，而是**重做一类新处理器**
2. 工程内容会迅速转移到：
   - RVV 指令支持
   - vector register file
   - lane 微架构
   - 向量 load/store
   - compiler/toolchain 适配
3. 对当前论文主线会产生稀释
   - 你现在已经有：
     - `DDR + DMA + AXIS + QMLP`
     - 以及正在推进的 `PE/MAC` 阵列方向
   - 再切去做 RVV 处理器，等于论文中心换题

结论：

- **不建议当前项目把“换 RVV 处理器”作为近期主线**
- 更适合作为未来扩展方向或大论文后续章节

### 4.3 路线三：做轻量级 CPU 扩展（CFU / custom instruction）

这条路线来自 `CFU Playground` 和 `EXTREM-EDGE`，优点是：

- 对现有 Rocket SoC 侵入较小
- 工程周期比换核、上 RVV 更短
- 适合做：
  - 预处理
  - 后处理
  - 小型 reduction
  - 量化/反量化辅助

但局限也很明显：

- 它不适合承接真正主干 NN 计算
- 对论文的“主创新点”提升有限
- 很容易沦为“做了几个 custom instruction”的边缘工作

结论：

- **这条路线适合作为配套优化，不适合作为论文主轴**

### 4.4 路线四：保持 Rocket 作为控制核，把主要创新放在 accelerator + dataflow

这条路线与 `Gemmini` 最一致，也最贴合当前仓库的已完成工作。

现在你已经有：

- `Rocket` 控制核
- `DDR / MIG`
- `AXI DMA`
- `AXI4-Stream` 数据链
- 固定功能 `QMLP`
- 多样本对拍
- 正在推进 `PE/MAC` 阵列化版本

因此最合理的下一步不是“先去加强 CPU”，而是：

1. **保持 Rocket 作为控制与调度核**
2. **继续把 NN 主算放在 accelerator 上**
3. **同步优化数据搬运**
   - batching
   - ping-pong buffer
   - weight 常驻
   - 减少 DDR round-trip
   - 减少每样本 DMA 启停和轮询开销

这条路对论文的好处是：

- 主线更清晰
- 工作量更容易集中体现
- 与当前已完成成果连续性最好

## 5. 对论文质量和工作量的影响判断

### 5.1 不同 CPU 路线的论文收益

| 路线 | 对当前工程的扰动 | 论文创新性提升 | 工作量 | 与当前项目连贯性 | 综合建议 |
|---|---:|---:|---:|---:|---|
| 仅提频 / 改 cache | 低到中 | 低 | 低到中 | 中 | 不建议作为主线 |
| 换更强 OoO 核 | 很高 | 中 | 很高 | 低 | 不建议 |
| 上 RVV / 向量核 | 很高 | 高 | 很高 | 低到中 | 暂不建议 |
| 加 CFU / 自定义指令 | 中 | 中 | 中 | 高 | 可做配套 |
| Rocket + PE/MAC accelerator + 数据搬运优化 | 中到高 | 高 | 高 | 最高 | **最推荐** |

### 5.2 对当前论文最有价值的 CPU 相关贡献是什么

如果你仍希望“CPU 也有一些可写内容”，最合适的方式不是大改 CPU，而是把 CPU 写成：

- 控制核
- 数据搬运调度器
- accelerator 配置与同步管理者
- 可选地增加少量辅助扩展

也就是说，CPU 在论文里更适合承担：

- 系统控制
- 数据流编排
- 与 accelerator 的协同接口

而不是承担：

- 主计算性能提升的核心贡献

## 6. 建议的项目路线

### 6.1 近期建议

保持当前：

- `Rocket @ 50 MHz`
- 不优先改 CPU 主频
- 不优先换更复杂内核

优先推进：

1. `PE/MAC` 阵列版 `QMLP`
2. 多样本 batching
3. 权重常驻 / 片上缓存
4. DMA / AXIS / buffer 组织优化

### 6.2 中期建议

如果论文需要补一个“CPU 也做了增强”的章节，可以选轻量路线：

- 少量 custom instruction / CFU
- 为 pre/post-processing 服务
- 不改主 SoC 骨架

### 6.3 不推荐当前阶段优先做的事情

- 为了“看起来更强”而换 `BOOM`
- 在当前 `Artix-7` 平台上硬上 RVV 处理器替换 Rocket
- 为 CPU 提升投入大量工作，而不处理数据搬运路径

## 7. 最终结论

结合近五年高影响 RISC-V CPU / vector / ISA extension 相关工作与当前项目基线，可以得出比较明确的结论：

1. **当前项目不需要把 CPU 提升作为第一优先级**
2. **仅靠提升 CPU，对当前端到端性能帮助有限**
3. **最合适的论文主线仍然是 accelerator + dataflow**
4. **CPU 更适合作为控制与协同核心，而不是论文主算主角**

因此，对当前项目最合理、最符合论文质量和工作量平衡的路线是：

- 保持 `Rocket 50 MHz` 作为控制核
- 继续把 `QMLP` 向 `PE/MAC` 阵列演进
- 同步做数据搬运优化
- 只在必要时增加少量 CPU 辅助扩展

这条路线既能继承当前仓库已经跑通的硬件基础，也最容易形成一条完整、能自圆其说的论文叙事链。

## 8. 参考文献与公开页面

1. SonicBOOM: The 3rd Generation Berkeley Out-of-Order Machine  
   - PDF: https://people.eecs.berkeley.edu/~krste/papers/SonicBOOM-CARRV2020.pdf  
   - 项目页: https://github.com/riscv-boom/riscv-boom

2. Ara: A 1 GHz+ Scalable and Energy-Efficient RISC-V Vector Processor with Multi-Precision Floating Point Support in 22 nm FD-SOI  
   - arXiv: https://arxiv.org/abs/1906.00478

3. Gemmini: An Agile Systolic Array Generator Enabling Systematic Evaluations of Deep-Learning Architectures  
   - 项目/论文页: https://alonamid.github.io/publication/gemmini/

4. CFU Playground: Full-Stack Open-Source Framework for Tiny Machine Learning (tinyML) Acceleration on FPGAs  
   - arXiv: https://arxiv.org/abs/2201.01863

5. EXTREM-EDGE—EXtensions To RISC-V for Energy-efficient ML inference at the EDGE of IoT  
   - ScienceDirect: https://www.sciencedirect.com/science/article/pii/S2210537922000749

6. Quark: An Integer RISC-V Vector Processor for Sub-Byte Quantized DNN Inference  
   - arXiv: https://arxiv.org/abs/2302.05996

7. Sparq: A Custom RISC-V Vector Processor for Efficient Sub-Byte Quantized Inference  
   - arXiv: https://arxiv.org/abs/2306.09905

8. SPEED: A Scalable RISC-V Vector Processor Enabling Efficient Multi-Precision DNN Inference  
   - arXiv: https://arxiv.org/abs/2409.14017
