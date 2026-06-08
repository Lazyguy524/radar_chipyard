# 当前 QMLP/边缘部署可对比论文调研（2020-2026）

更新时间：2026-04-09

## 1. 当前项目可用于对比的基线

当前项目已经形成了一个可以拿来和文献对照的最小闭环：

- 模型：`k=3 + rcs21 + 21 -> 64 -> 32 -> 2 INT8 QMLP`
- 当前冻结模型精度：`accuracy = 0.9279`
- 参数量：
  - 权重：`21*64 + 64*32 + 32*2 = 3456`
  - 偏置：`64 + 32 + 2 = 98`
  - 总参数量：`3554`
- 参数存储量：
  - `int8` 权重约 `3456 B`
  - `int32` 偏置约 `392 B`
  - 合计约 `3848 B`
- 硬件平台：`Rocket RV64 + DDR + AXI DMA + AXIS QMLP accelerator`
- 板级结果：
  - `QMLP hardware kernel latency ≈ 26.02 us`
  - `system end-to-end latency ≈ 178.31 ms`
  - `CPU-only pure forward ≈ 3306.86 us`
  - `CPU-only / hardware-kernel` 同口径加速比约 `127.1x`

这里最重要的事实不是“当前系统端到端已经很快”，而是：

- 当前模型极小，参数量只有 `3554`
- 在该任务上仍保持了 `92.79%` 精度
- 已经完成板级硬件化闭环
- 已经完成 `CPU-only` 与 `accelerator-kernel` 的同口径对比

因此，论文中的对比不应该只找“完全同任务同平台”的工作，而应该拆成两条线：

1. 小参数量模型如何保持可用精度
2. 小模型如何在边缘设备/FPGA/RISC-V SoC 上完成高效部署

## 2. 先说结论：哪些论文最适合拿来说明你的优势

如果只挑最适合写进论文正文的几篇，我建议优先引用下面这 8 篇：

### 2.1 小模型/保精度方向

1. MCUNet, 2020
2. MicroNets, 2020
3. Quantization and Deployment of Deep Neural Networks on Microcontrollers, 2021
4. MCUNetV2, 2021
5. TinyRadarNN, 2021

### 2.2 边缘部署/加速器方向

1. Edge Machine Learning for AI-Enabled IoT Devices: A Review, 2020
2. A Survey on the Optimization of Neural Network Accelerators for Micro-AI On-Device Inference, 2021
3. Gemmini, 2021
4. Custom Hardware Inference Accelerator for TensorFlow Lite for Microcontrollers, 2022
5. SECDA / SECDA-TFLite, 2021-2022

这几篇里：

- `MCUNet / MicroNets / MCUNetV2` 用来证明“小模型设计与边缘约束协同优化”的合理性
- `TinyRadarNN` 用来补“雷达任务本身也存在超轻量边缘网络”的领域相关性
- `Gemmini / SECDA / TFLM hardware accelerator` 用来证明“做板级 accelerator + SoC 协同”是论文常见且合理的路线

## 3. 论文列表与可用价值

说明：

- 下表中的“引用量”采用 `OpenAlex` 检索结果，时间点为 `2026-04-09`
- 这些数字是近似值，适合用来判断“高影响/高引用”程度，不建议在论文正文中写死具体引用数
- 你的项目与其中大多数工作并非同任务同数据集，因此更适合作为“设计思路/对比维度”参考，而不是直接做榜单式逐项压线比较

### 3.1 小模型、量化与精度保持方向

| 论文 | 年份 | 近似引用量 | 作用 | 你可以怎么用 |
|---|---:|---:|---|---|
| MCUNet: Tiny Deep Learning on IoT Devices | 2020 | 255 | TinyML 代表工作，强调模型与系统协同设计 | 说明“小模型不是单纯缩网络，而是结合部署约束设计” |
| MicroNets: Neural Network Architectures for Deploying TinyML Applications on Commodity Microcontrollers | 2020 | 148 | 超轻量网络设计代表工作 | 说明“小参数量 + 可部署性”是成熟研究方向 |
| Quantization and Deployment of Deep Neural Networks on Microcontrollers | 2021 | 179 | 量化部署与 MCU 落地综述/实践总结 | 说明 `INT8` 部署路线合理，且资源受限平台上量化是标准路线 |
| MCUNetV2: Memory-Efficient Patch-based Inference for Tiny Deep Learning | 2021 | 50 | 进一步从内存角度优化 TinyDL | 说明边缘推理的瓶颈不只在 MAC，也在内存和数据流 |
| TinyRadarNN: Combining Spatial and Temporal CNNs for Embedded Gesture Recognition With Short Range Radars | 2021 | 85 | 雷达领域的轻量边缘网络 | 说明“雷达任务做超轻量模型”有明确文献基础 |
| Unlocking Edge Intelligence Through Tiny Machine Learning (TinyML) | 2022 | 83 | TinyML 较高影响综述 | 可放在相关工作和问题定义中，支撑整体研究背景 |

### 3.2 边缘板级部署、软硬件协同与加速器方向

| 论文 | 年份 | 近似引用量 | 作用 | 你可以怎么用 |
|---|---:|---:|---|---|
| Edge Machine Learning for AI-Enabled IoT Devices: A Review | 2020 | 461 | 边缘 ML 总体背景综述 | 说明边缘设备上的模型压缩、量化、加速器协同是主流方向 |
| A Survey on the Optimization of Neural Network Accelerators for Micro-AI On-Device Inference | 2021 | 62 | 面向 Micro-AI 的加速器优化综述 | 说明你后续做 `PE/dataflow/e2e` 优化是合理论文路线 |
| Gemmini: Enabling Systematic Deep-Learning Architecture Evaluation via Full-Stack Integration | 2021 | 16 | Chipyard/RISC-V 体系内最相关的 full-stack accelerator 工作 | 用来支撑“在 RISC-V SoC 上做 accelerator 集成”这条线 |
| Custom Hardware Inference Accelerator for TensorFlow Lite for Microcontrollers | 2022 | 36 | TinyML 硬件加速器代表性落地工作 | 用来说明“小模型 + MCU/边缘硬件加速”是可发表的方向 |
| SECDA: Efficient Hardware/Software Co-Design of FPGA-based DNN Accelerators for Edge Inference | 2021 | 18 | FPGA 边缘推理软硬协同 | 说明 FPGA 上做 edge inference 的方法论与工具链价值 |
| SECDA-TFLite: A toolkit for efficient development of FPGA-based DNN accelerators for edge inference | 2022 | 11 | 从工具链角度推动 FPGA edge inference | 说明“可重复、可工程化”的板级部署流程很重要 |

## 4. 这些论文和你当前工作的关系

### 4.1 哪些可以直接比

严格来说，当前最适合直接和你做“同口径数值对比”的，其实不是上面这些论文，而是你自己已经做出来的两个基线：

1. `Rocket CPU-only pure forward ≈ 3306.86 us`
2. `QMLP hardware kernel ≈ 26.02 us`

这是你目前最强、也最公平的一组实验，因为：

- 同一个模型
- 同一组权重
- 同一个 SoC
- 同一块板子
- 只改变是否使用 accelerator

这一组数据比“强行拿你的 26us 去和 PC、Jetson、ARM MCU 的某个不完全同模型结果硬比”更有说服力。

### 4.2 哪些更适合做“论文论证”

上面列出的论文更适合帮助你完成这三类论证：

1. 为什么模型可以这么小

- `MCUNet / MicroNets / MCUNetV2` 说明边缘任务中，小模型与系统约束协同优化是成熟方向
- 你这里可以进一步强调：
  - 任务不是通用视觉分类，而是雷达特征分类
  - 因此 `21 -> 64 -> 32 -> 2` 这种极小 QMLP 是合理设计点

2. 为什么还能保持可用精度

- `TinyRadarNN` 说明雷达任务本身就存在轻量网络落地需求
- 你这里不能说“我的精度一定全面优于这些工作”，但可以说：
  - 在当前数据表示和任务设定下
  - 你的冻结 `INT8 QMLP` 以 `3554` 参数实现了 `92.79%` 精度
  - 这说明任务本身具备“超轻量模型仍保持可用精度”的空间

3. 为什么值得做板级 accelerator

- `Gemmini / SECDA / TFLM custom accelerator` 支撑的是：
  - accelerator 不只是算快一个算子
  - 而是要做 SoC 集成、数据流、部署闭环、性能计量
- 你现在已经完成了：
  - `DDR + DMA + AXIS + QMLP`
  - 板级多样本验证
  - `CPU-only` 对比
  - `4-lane PE` 优化

这已经足以把论文从“纯工程试验”提升到“有系统性论证的 accelerator work”

## 5. 当前项目能讲出的优势

### 5.1 能明确讲的优势

1. 模型极小

- 只有 `3554` 参数
- 参数总存储仅约 `3.8 KB`
- 这比大多数 CNN/Transformer 边缘模型都小得多

2. 精度仍然可用

- 当前冻结模型精度 `0.9279`
- 对雷达特征分类任务来说，这已经说明“超小模型并未丧失任务有效性”

3. 已经完成硬件闭环

- 不是只在软件里模拟
- 而是已经在 `Rocket + DDR + DMA + FPGA accelerator` 上完成闭环

4. 已经拿到同口径加速比

- `CPU-only pure forward ≈ 3306.86 us`
- `QMLP hardware kernel ≈ 26.02 us`
- 加速比约 `127.1x`

5. 已经从“固定模型硬件化”推进到“PE 阵列化优化”

- `v2.5` 保持 `4-lane PE`
- 硬件本体周期从 `3554` 降到 `1301`
- 相对旧版 kernel 约 `2.73x`

### 5.2 暂时不能夸大的地方

1. 不能直接说端到端延迟已经非常强

- 当前 `system end-to-end latency ≈ 178.31 ms`
- 这说明外围搬运和调度还是主要瓶颈

2. 不能直接说“全面优于 PC/Jetson”

- 你的优势不在绝对算力，而在：
  - 模型极小
  - 板级可部署
  - SoC 可定制
  - accelerator 可继续演进

3. 不能把 TinyML 视觉论文的精度直接和你的雷达任务精度横着比

- 数据集不同
- 任务不同
- 指标定义不同

更合理的写法是：

- 它们证明了“小模型 + 保精度 + 边缘部署”是合理路线
- 你则在“雷达特征分类 + RISC-V SoC + FPGA accelerator”这个具体问题上给出了一条落地实现

## 6. 论文中建议采用的对比口径

我建议你后面论文正文的对比结构用下面这 3 层：

### 6.1 第一层：模型紧凑性

- 参数量：`3554`
- 存储量：约 `3.8 KB`
- 量化格式：`INT8 weights + INT32 bias/accum`
- 精度：`92.79%`

这一层对应 `MCUNet / MicroNets / MCUNetV2 / TinyRadarNN`

### 6.2 第二层：本平台内的公平对比

- `Rocket CPU-only pure forward`
- `Fixed-QMLP hardware kernel`
- `4-lane PE QMLP v2.5 hardware kernel`

这一层是你论文最硬的实验结果。

### 6.3 第三层：系统与架构意义

- `RISC-V SoC + DDR + DMA + AXIS accelerator`
- 多样本板测通过
- 从固定硬件化到 `PE/dataflow` 优化

这一层对应 `Gemmini / SECDA / TFLM hardware accelerator`

## 7. 最后给你的写法建议

如果你后面要在论文里写一句最像“结论”的话，我建议用这种口径：

> 本文面向边缘端雷达特征分类任务，选取冻结的 `21 -> 64 -> 32 -> 2` INT8 QMLP 作为超轻量基线模型。在仅 `3554` 参数、约 `3.8 KB` 参数存储的条件下，模型保持 `92.79%` 分类精度，并在基于 Rocket 的 RISC-V FPGA SoC 上完成板级闭环部署。通过引入 `4-lane PE` 阵列化 QMLP accelerator，单样本 kernel 延迟由 `CPU-only` 的 `3306.86 us` 降至 `26.02 us`，获得约 `127.1x` 的同口径加速比。

这个表述的优点是：

- 不夸大端到端系统已经完全优化好
- 但把“小模型、可用精度、板级部署、kernel 级显著加速”都说清楚了

## 8. 参考链接

### 8.1 TinyML / 小模型方向

- MCUNet, 2020  
  https://arxiv.org/abs/2007.10319
- MCUNetV2, 2021  
  https://arxiv.org/abs/2110.15352
- MicroNets, 2020  
  https://arxiv.org/abs/2010.11267
- Quantization and Deployment of Deep Neural Networks on Microcontrollers, 2021  
  https://doi.org/10.3390/s21092984
- TinyRadarNN, 2021  
  https://doi.org/10.1109/JIOT.2021.3067382
- Unlocking Edge Intelligence Through Tiny Machine Learning (TinyML), 2022  
  https://doi.org/10.1109/ACCESS.2022.3207200

### 8.2 边缘部署 / 加速器方向

- Edge Machine Learning for AI-Enabled IoT Devices: A Review, 2020  
  https://doi.org/10.3390/s20092533
- A Survey on the Optimization of Neural Network Accelerators for Micro-AI On-Device Inference, 2021  
  https://doi.org/10.1109/JETCAS.2021.3129415
- Gemmini, 2021  
  https://doi.org/10.1109/DAC18074.2021.9586216
- Custom Hardware Inference Accelerator for TensorFlow Lite for Microcontrollers, 2022  
  https://doi.org/10.1109/ACCESS.2022.3189776
- SECDA, 2021  
  https://doi.org/10.1109/SBAC-PAD53543.2021.00015
- SECDA-TFLite, 2022  
  https://doi.org/10.1016/j.jpdc.2022.11.005
