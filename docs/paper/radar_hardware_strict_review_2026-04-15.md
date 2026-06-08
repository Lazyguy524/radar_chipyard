# 硬件论文内容严厉评审意见与修改方案

日期：2026-04-15  
对象：《基于 RISC-V 的雷达信号智能处理系统设计与研究》硬件侧内容  
评审口径：按“非常严厉的硕士论文外审/答辩委员”标准审查合理性、逻辑性、已有工作、项目价值与修改路径。

---

## 1. 一句话总评

如果论文把当前工作写成：

> “我提出了一种全新的 RISC-V 神经网络加速器架构”

这个说法站不住，容易被评委打穿。

如果论文改写成：

> “面向停车场雷达特征分类任务，完成了一个基于 RISC-V SoC 的轻量 QMLP 智能处理原型系统，并围绕固定 INT8 模型硬件化、AXI-Stream 数据通路、4-lane PE 推理核、权重 ROM 化、板级验证和 PPA 评估形成完整实现闭环”

这个说法更合理，也更安全。

当前项目的核心价值不是“发明了通用 AI accelerator”，而是：

- 把雷达任务、轻量模型、RISC-V SoC、DMA 数据通路、RTL 加速器、板级验证贯通起来。
- 给出了一个可综合、可烧录、可对拍、可测时延和资源的端到端工程原型。
- 在同一块板、同一模型、同一数据上完成 CPU-only 与硬件 kernel 的公平对比。

这足够支撑硕士论文硬件部分，但需要非常谨慎地界定创新点。

---

## 2. 最严格的问题：别人有没有做过类似事情？

有，而且很多。

### 2.1 RISC-V + 神经网络加速器已经不是新方向

已有工作包括：

- `Gemmini`：Berkeley/Chipyard 生态中的 RISC-V 深度学习加速器生成器，强调 full-stack 集成和 systolic array 结构。
- `PULP-NN / GAP8`：面向超低功耗 RISC-V 平台的量化神经网络推理库和边缘 SoC。
- `NVDLA + RISC-V`：工业界开放 DNN accelerator，并已有与 RISC-V SoC 集成的研究。
- `GAP8/GAP9`：商业 RISC-V AIoT 芯片，面向传感器侧 AI/DSP/NN 工作负载。

因此，不能把“RISC-V 上部署神经网络加速器”本身当作强创新。

### 2.2 FPGA 上做 NN 硬件化也不是新方向

已有工作包括：

- `FINN`：面向 FPGA 的量化/二值神经网络推理框架。
- `hls4ml`：将机器学习模型转换到 FPGA/HLS，强调低延迟推理。
- `SECDA / SECDA-TFLite`：面向 edge FPGA DNN accelerator 的软硬件协同设计工具链。

因此，不能把“把 MLP 写成 RTL 并综合到 FPGA”本身写成强创新。

### 2.3 TinyML / 小模型保精度也不是新方向

已有工作包括：

- `MCUNet`
- `MCUNetV2`
- `MicroNets`
- TinyML 量化部署研究

这些工作已经说明“小模型 + 量化 + 边缘部署”是成熟路线。

因此，不能把“模型小、INT8、能跑在边缘”直接说成新思想。

### 2.4 雷达轻量网络也已有相关工作

例如 `TinyRadarNN` 已经探索了短距雷达场景下的嵌入式轻量神经网络。

因此，不能说“雷达任务第一次使用轻量神经网络边缘部署”。

---

## 3. 当前项目真正有价值的地方

虽然单个技术点并不新，但当前项目仍然有论文价值。价值主要在组合、落地和验证。

### 3.1 任务约束明确

当前任务不是泛泛做 AI accelerator，而是停车场雷达目标检测/分类。输入是固定的 21 维雷达特征，输出是 2 维 logits。

这让硬件设计可以很专用：

- 模型维度固定：`21 -> 64 -> 32 -> 2`
- 权重固定：k7 + rcs21 冻结参数
- 数据宽度固定：INT8 activation / INT8 weight / INT32 logits
- 输出类别固定：pedestrian / vehicle

评审会认可“面向具体应用约束的专用硬件实现”，但不会认可“泛泛说自己做了 AI 加速器”。

### 3.2 不是纸面设计，已经板级闭环

当前已经完成：

- 完整 bitstream 生成
- post-route timing 通过
- QMLP 资源统计
- 板级 `large_golden 1000/1000`
- 板级 `boundary_cases 54/54`
- `kernel latency = 1301 cycles = 26.02 us @ 50 MHz`

这比只做仿真或者只做软件模型强很多。

### 3.3 同平台 CPU-only 对比有说服力

当前最强的对比不是 PC 或 Jetson，而是：

- 同一块 RISC-V SoC
- 同一个 QMLP 模型
- 同一套量化参数
- 同一组数据
- 软件 pure forward vs RTL QMLP kernel

这能公平说明“硬件化带来的 kernel 计算收益”。

### 3.4 代码结构有工程演进

当前已经从早期“能跑但结构乱”的 QMLP RTL，推进到：

- 集中式 FSM
- next-value 风格
- 显式 ROM 权重访问
- 64-bit word-bank activation cache
- 去除动态 `logitsVec`
- 板级行为保持一致

这部分适合写成“实现优化与工程可靠性提升”，但不要包装成算法创新。

---

## 4. 当前论文逻辑中最容易被拷打的点

### 4.1 “为什么一定要 RISC-V？”

如果回答只是：

> 因为 RISC-V 开源、可扩展。

不够。

严格评委会追问：

- 为什么不用 ARM MCU？
- 为什么不用 Jetson Nano？
- 为什么不用现成 NPU？
- 为什么不用 PC 直接跑？
- RISC-V 在你的实验中体现了什么不可替代性？

建议回答口径：

> 本文并非证明 RISC-V 绝对性能优于 ARM/Jetson/PC，而是利用 RISC-V SoC 的开放可定制特性，完成 CPU、DMA、AXI-Stream 加速器和固定雷达模型的软硬件协同集成。RISC-V 在本文中的意义是“可定制 SoC 原型平台”，不是“通用计算性能领先平台”。

如果有时间，建议补一个外部平台对比：

- PC Python/C 推理
- Jetson Nano CPU/GPU 推理
- ARM MCU 或 Raspberry Pi 推理

但论文最核心对比仍应是同板 CPU-only vs hardware kernel。

### 4.2 “QMLP 硬件化是不是太简单？”

这是最危险的问题。

一个 21->64->32->2 MLP 本质就是几千次 MAC。如果只说“我把 MLP 写成硬件”，评委可能认为工作量低。

必须补足系统层工作量：

- 参数导出与硬件固化
- INT8/INT32 定点对齐
- bankers rounding / ReLU / clamp 与软件 golden 一致
- AXI DMA 数据搬运
- AXI-Stream 协议
- batch 输入边界
- MMIO 控制与计数器
- 板级 large/boundary golden 对拍
- timing/PPA

建议把 QMLP 放在 SoC 系统中讲，而不是孤立成“一个全连接模块”。

### 4.3 “4-lane PE 能不能算创新？”

单独不能。

4-lane PE 是常见并行化设计，不具备强原创性。

可以这样写：

> 针对该 QMLP 规模和 Nexys Video FPGA 资源约束，本文采用 4-lane 折叠 PE 结构，在资源占用和计算周期之间取得折中，并通过板级实验验证 kernel 周期从早期实现降低至 1301 cycles。

不能这样写：

> 本文提出了一种创新 PE 阵列架构。

更合适的定位是：

- 结构设计点
- 工程优化点
- 可复现实验结果
- 不是理论创新

### 4.4 “1000 组 golden 通过能不能证明功能彻底正确？”

不能证明数学意义上的彻底正确。

它只能证明：

- 对当前测试集和边界集，硬件输出与 golden 一致。
- 对当前冻结模型、当前量化规则、当前数据通路，板级行为是可信的。

如果要更强，可以补：

- 随机输入对拍
- 极值输入覆盖
- layer-wise L1/L2 定位
- SystemVerilog/Chisel 仿真对拍
- 软件参考模型与硬件 bit-accurate reference 一致性说明

论文里应写：

> 通过 1000 组大样本和 54 组边界样本验证了实现正确性。

不要写：

> 完全证明硬件在所有输入下正确。

### 4.5 “kernel latency 很快，为什么 e2e 还很慢？”

必须主动解释。

当前：

- QMLP kernel：`26.02 us`
- large_golden e2e：约 `22 ms / sample`
- boundary e2e：约 `178 ms / sample`

如果不解释，评委会认为系统加速没有意义。

建议明确区分三种时间：

| 时间 | 含义 | 适合说明什么 |
|---|---|---|
| kernel latency | QMLP RTL 内部计算时间 | 加速器本体性能 |
| DMA batch e2e | DMA + QMLP + CPU 调度 | 系统数据流效率 |
| UART/ELF 测试流程 | 下载 ELF、打印日志等 | 仅测试流程，不代表部署系统 |

论文里要强调：

- 26 us 是加速器核心推理延迟。
- 当前 e2e 包含测试程序、DMA 调度、bare-metal 控制和日志环境开销。
- 如果实际部署从 Flash 启动并流式输入，UART 下载 ELF 不属于在线推理路径。

### 4.6 “preproc 和 QMLP 的关系没讲清楚”

必须讲清楚。

当前 QMLP 输入已经是 21 维 INT8 特征。真正从 radar raw/x-y-doppler/rcs 到 21 维特征的转换，目前主要在软件侧/PC侧数据包中完成。

因此不能让读者误以为当前硬件已经完成完整雷达 raw data 到分类的全流程。

建议写法：

> 当前硬件 QMLP 模块处理的是软件侧冻结并量化后的 21 维雷达特征；特征构建和模型训练不属于该 RTL 模块。本系统保留了 AXI-Stream preprocessor 插槽，后续可将更多前处理步骤迁移至板端。

---

## 5. 当前创新点应如何重写

### 5.1 不建议写成创新点的内容

以下内容建议写成“主要工作”或“工程实现”，不要写成创新点：

- 搭建 RISC-V SoC
- 使用 AXI DMA
- 使用 AXI-Stream
- 使用 INT8 量化
- 把 MLP 写成 RTL
- 使用 4-lane PE
- 权重存在 ROM/LUT
- 通过 UART-TSI 下载 ELF

这些都已有大量先例。

### 5.2 可以作为创新点候选的内容

更安全的创新点候选如下。

#### 创新点 1：面向停车场雷达特征分类的轻量 RISC-V SoC 智能处理原型

推荐表述：

> 面向停车场雷达边缘检测任务，构建了基于 RISC-V 的轻量智能处理 SoC 原型，实现了从 DDR/DMA 数据搬运、AXI-Stream 模型推理到 CPU 侧结果验证的板级闭环。

注意：这是系统实现创新，不是架构理论创新。

#### 创新点 2：面向固定 INT8 QMLP 的任务专用 RTL 加速器

推荐表述：

> 针对 `21->64->32->2` INT8 QMLP 模型，设计了固定权重 ROM、折叠式 4-lane PE、定点 requant/ReLU/clamp 和 AXI-Stream 输入输出的数据通路，实现了 bit-accurate 的模型硬件化。

注意：强调任务专用和 bit-accurate，不要强调“通用”。

#### 创新点 3：面向板级部署的结构化数据流与验证方法

推荐表述：

> 建立了从软件 golden、边界样本、板级 DMA 执行、计数器统计到 timing/PPA 报告的验证链路，区分 kernel latency 与 system e2e latency，为小模型硬件部署提供了可复现评估方法。

这个点适合硕士论文，尤其能体现工程严谨性。

#### 创新点 4：QMLP RTL 工程化重构与时序友好实现

推荐表述：

> 对 QMLP RTL 进行集中式 FSM、显式 ROM、word-bank activation cache 和 next-value 风格重构，在保持 golden 行为不变的同时完成完整 bitstream 和板级验证。

注意：这更像“工程质量提升”，如果论文创新点数量已经够，可以放在实现章节，不一定放到摘要创新点。

---

## 6. 当前项目价值评分

按严厉标准打分：

| 维度 | 分数 | 评价 |
|---|---:|---|
| 工程完整性 | 4.2 / 5 | 已有 SoC、DMA、RTL、bitstream、板级验证，工作量扎实 |
| 学术原创性 | 2.5 / 5 | 单个技术点多为已有路线，不能夸大 |
| 系统研究价值 | 3.6 / 5 | 如果聚焦“雷达任务 + RISC-V SoC + QMLP 硬件闭环”，价值明显 |
| 实验说服力 | 3.4 / 5 | golden/边界/CPU-only/kernel 数据不错，但还缺功耗、外部平台、更多任务指标 |
| 论文可写性 | 3.8 / 5 | 足够写硕士论文，但必须重构叙事，不要写成泛泛 AI accelerator |

综合判断：

> 当前项目具备硕士论文硬件部分的工作量和完整性，但创新点必须降调，重点从“提出新架构”改为“面向具体雷达任务的 RISC-V SoC 软硬件协同实现与验证”。

---

## 7. 修改方案

### 7.1 论文题目保持不变，但摘要要降调

题目《基于 RISC-V 的雷达信号智能处理系统设计与研究》是合适的。

摘要中不要写：

- “提出一种全新的神经网络加速器”
- “首次实现”
- “显著优于现有边缘平台”

建议写：

- “设计并实现”
- “面向固定雷达特征模型”
- “构建 RISC-V SoC 原型”
- “完成板级验证”
- “在同平台 CPU-only 对比中降低 kernel 推理延迟”

### 7.2 章节主线建议

建议硬件相关章节这样组织：

1. 系统需求与总体架构
   - 停车场雷达边缘部署需求
   - RISC-V SoC 选择理由
   - 系统数据流

2. 雷达 QMLP 模型硬件映射
   - 21 维输入
   - INT8/INT32 定点格式
   - 权重/bias 固化
   - logits 输出含义

3. QMLP 加速器 RTL 设计
   - FSM
   - ROM 权重表
   - 4-lane PE
   - requant/ReLU/clamp
   - word-bank activation cache
   - AXI-Stream I/O

4. RISC-V SoC 集成与数据搬运
   - Rocket CPU
   - DDR/MIG
   - AXI DMA
   - MMIO control/status
   - preproc 与 QMLP 的串行数据通路关系

5. 实验与评估
   - bitstream/timing/PPA
   - golden/boundary 正确性
   - CPU-only vs hardware kernel
   - batch e2e
   - 资源与功耗

6. 局限性与后续优化
   - e2e 仍受 DMA/软件调度影响
   - 特征构建尚未完全板端化
   - 权重固定，暂不支持运行时换模型
   - 未来可做 BRAM/可配置权重/流水线/Flash 自启动

### 7.3 必须补强的实验

优先级从高到低：

1. 功耗或能耗
   - 至少给板级功耗估计或 Vivado power report
   - 最好给 energy/inference

2. 对比表
   - Rocket CPU-only
   - QMLP hardware kernel
   - QMLP batch e2e
   - PC 或 Jetson 可作为外部参考，但不要作为绝对公平比较

3. 模型精度材料
   - accuracy
   - confusion matrix
   - precision/recall/F1
   - 数据集划分
   - 量化前后精度对比

4. 消融实验
   - baseline QMLP vs 4-lane PE
   - packed/旧结构 vs ROM/word-bank 新结构
   - single sample vs batch

5. 系统图
   - SoC block diagram
   - QMLP datapath
   - timing/clock tree
   - memory map
   - test flow

### 7.4 必须删除或弱化的表述

删除：

- “彻底证明 QMLP 功能正确”
- “通用神经网络加速器”
- “首次”
- “工业级”
- “全面优于 PC/Jetson”

改成：

- “在当前 golden/boundary 数据集上完成板级对拍”
- “面向固定 QMLP 模型的任务专用加速器”
- “构建并验证”
- “原型系统”
- “同平台 CPU-only 对比下 kernel 延迟显著降低”

---

## 8. Review 方案

### 8.1 第一轮：事实审查

目标：所有论文里的数字都必须能追溯到日志或代码。

检查项：

- QMLP 模型维度是否写对
- k7/rcs21 版本是否统一
- logits 类别含义是否统一
- 1301 cycles 是否来自板测
- WNS/PPA 是否来自最终 post-route 报告
- `large_golden 1000/1000` 和 `boundary 54/54` 是否有日志
- e2e 与 kernel 是否没有混写

不通过条件：

- 把 k3 和 k7 数据混用
- 把 bitstream OOC 结果当完整 SoC 结果
- 把 UART 下载时间算入在线推理又不解释

### 8.2 第二轮：创新点审查

目标：每个创新点都要回答“已有工作做过什么，你这里不同在哪里”。

每个创新点必须包含：

- 已有工作
- 本文问题设定
- 本文具体做法
- 实验支撑
- 局限性

不通过条件：

- 只有“我做了某模块”
- 没有对比
- 没有实验
- 夸大为通用架构创新

### 8.3 第三轮：答辩拷打预演

必须能回答以下问题：

1. 为什么不用 Gemmini？
2. 为什么不用 hls4ml/FINN？
3. 为什么不用 Jetson？
4. 你的 QMLP 和普通 MLP accelerator 有什么区别？
5. 4-lane PE 的选择依据是什么？
6. 权重为什么固定在 ROM/LUT？能不能换模型？
7. 当前硬件是否处理 raw radar data？
8. 1000 组 golden 通过能证明什么，不能证明什么？
9. 为什么 kernel 26 us，但 e2e 是 ms 级？
10. 如果数据特征提取放到板上，系统还成立吗？

### 8.4 第四轮：图表审查

建议论文至少具备：

- 总体 SoC 架构图
- QMLP RTL 数据通路图
- 权重 ROM 与 PE 消费路径图
- AXI DMA 数据流图
- 运行流程图
- 资源表
- timing 表
- latency 表
- accuracy/precision/recall/F1 表

---

## 9. 结论

严格地说，当前项目不是“新型通用 AI accelerator”的论文。

但它可以成为一篇相当扎实的“面向雷达边缘智能处理的 RISC-V SoC 原型系统设计与验证”硕士论文。

最合理的论文定位是：

> 本文针对停车场雷达特征分类任务，在 RISC-V SoC 上实现并验证了一个轻量 INT8 QMLP 硬件加速系统。该系统通过 AXI DMA 与 AXI-Stream 完成数据搬运，通过固定权重 ROM、4-lane PE 和定点量化路径实现模型推理，并在 Nexys Video FPGA 平台上完成 timing、PPA、large golden 与 boundary cases 板级验证。

最终建议：

- 不要把创新点写大。
- 把工程闭环写扎实。
- 把已有工作讲清楚。
- 把对比口径讲严谨。
- 把局限性主动写出来。

这样论文更像可靠研究，而不是“工程堆模块”。

---

## 10. 参考来源

- MCUNet: Tiny Deep Learning on IoT Devices  
  https://arxiv.org/abs/2007.10319
- MCUNetV2: Memory-Efficient Patch-based Inference for Tiny Deep Learning  
  https://arxiv.org/abs/2110.15352
- TinyRadarNN: Combining Spatial and Temporal CNNs for Embedded Gesture Recognition With Short Range Radars  
  https://arxiv.org/abs/2006.16281
- SECDA: Efficient Hardware/Software Co-Design of FPGA-based DNN Accelerators for Edge Inference  
  https://arxiv.org/abs/2110.00478
- Fast convolutional neural networks on FPGAs with hls4ml  
  https://arxiv.org/abs/2101.05108
- PULP-NN: Accelerating Quantized Neural Networks on Parallel Ultra-Low-Power RISC-V Processors  
  https://arxiv.org/abs/1908.11263
- FINN framework  
  https://xilinx.github.io/finn/
- Gemmini: Agile Systolic Array Generator / Full-stack RISC-V accelerator work  
  https://people.eecs.berkeley.edu/~alonamid/papers/gemmini-arxiv-1911.09925.pdf
- NVIDIA Deep Learning Accelerator  
  https://nvdla.org/
- Google Coral Edge TPU inference overview  
  https://www.coral.withgoogle.com/docs/edgetpu/inference/
