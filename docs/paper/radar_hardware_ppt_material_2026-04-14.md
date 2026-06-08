# 硬件方向 PPT 汇报材料整理

日期：2026-04-14  
更新：2026-04-16，同步 `word-bank/ROM` 重构版硬件基线  
题目背景：《基于 RISC-V 的雷达信号智能处理系统设计与研究》  
当前硬件基线：`k=7 + rcs21 + 21->64->32->2 INT8 QMLP + 4-lane PE + explicit distributed ROM + activation word-bank`

本文档用于准备阶段性汇报 PPT。重点覆盖：

- NN-RTL 架构图与创新点
- SoC 架构图与数据流
- input/output 口径
- 测试结果
- PPA 指标
- 当前内容哪些能作为创新点候选，哪些更适合作为工程实现

配套 HTML 图页：

- [radar_hardware_ppt_diagrams_2026-04-14.html](/home/soooarr/chipyard/docs/paper/radar_hardware_ppt_diagrams_2026-04-14.html)

---

## 1. 汇报主线建议

建议 PPT 不要从“我写了一个模块”开始，而是从系统问题开始：

```text
停车场雷达目标检测
  -> 边缘侧需要低功耗、低延迟、可独立运行
  -> 软件 QMLP 模型压缩到 21->64->32->2 INT8
  -> 在 RISC-V SoC 上集成专用 QMLP RTL 加速器
  -> 通过 AXI DMA / AXI-Stream 完成数据搬运和板级推理
  -> 用 golden/boundary 数据完成正确性与时延验证
```

硬件部分可以浓缩成一句：

> 本项目实现了一个面向固定雷达目标检测 QMLP 模型的 RISC-V SoC 原型系统，将 `21->64->32->2` INT8 网络固化为可综合 RTL，并通过显式固定权重 distributed ROM、`32-bit` 权重 word-bank、`64-bit` activation word-bank、`4-lane PE` 乘加阵列和 AXI DMA 数据通路，实现了板上可验证的低延迟推理。

---

## 2. 当前硬件系统组成

当前 SoC 硬件侧主要包括：

| 部分 | 当前实现 | 汇报时建议说法 |
|---|---|---|
| CPU | 单核 Rocket RISC-V，当前配置去除 FPU | 作为控制核、测试程序运行核、DMA 配置与结果读取核 |
| 片外存储 | Nexys Video DDR，映射到 SoC 外部内存空间 | 存放输入样本、输出结果、bare-metal 测试数据 |
| 控制接口 | 自定义 AXI4 MMIO 端口，基地址 `0x60000000` | CPU 通过 MMIO 配置 Preproc/QMLP 控制寄存器 |
| 数据搬运 | AXI DMA，MM2S + S2MM | DDR 与 AXI-Stream 加速器之间的数据搬运 |
| 预处理模块 | `RadarAXISPreprocessor`，保留 bypass / add / shift / relu / swap 等模式 | 作为可扩展信号预处理数据路，当前可与 QMLP 共存 |
| QMLP 加速器 | `RadarAXISQMLP` | 固定 INT8 QMLP 的硬件推理模块 |
| 验证入口 | UART-TSI + bare-metal ELF | 当前用于加载测试程序和输出日志 |

关键源码：

- [RadarQMLP.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarQMLP.scala)
- [RadarAXIDMA.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala)
- [Configs.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/Configs.scala)

---

## 3. SoC 架构图内容

PPT 中建议展示如下结构：

```text
PC / Host
  | UART-TSI：下载 bare-metal ELF、接收日志
  v
RISC-V Rocket Core
  | MMIO 控制
  v
AXI4-Lite Control Bridge
  | 控制寄存器
  +--> Preproc Ctrl
  +--> QMLP Ctrl / Status / Counters

DDR Memory
  | input buffer
  v
AXI DMA MM2S
  | AXI-Stream
  v
RadarAXISPreprocessor
  | AXI-Stream
  v
RadarAXISQMLP
  | AXI-Stream logits[2]
  v
AXI DMA S2MM
  | output buffer
  v
DDR Memory
  | CPU 读取、对拍、打印
  v
UART Log
```

需要强调：

- CPU 不是直接逐周期参与 MAC 计算，而是负责配置、调度、对拍和日志。
- QMLP 位于 AXI-Stream 数据通路上，输入输出通过 DMA 搬运。
- 当前测试阶段 ELF 通过 UART-TSI 下载；如果做展示系统，可进一步做 Flash 自启动或交互式串口 Demo。

---

## 4. NN-RTL 架构图内容

当前 QMLP 结构：

```text
Input: int8[21]
  -> L1: 21 x 64, INT8 weight, INT32 acc, requant + ReLU + clamp
  -> L2: 64 x 32, INT8 weight, INT32 acc, requant + ReLU + clamp
  -> L3: 32 x 2,  INT8 weight, INT32 acc
  -> Output: int32 logits[2]
```

其中：

- `logits[0]`：pedestrian 类得分
- `logits[1]`：vehicle 类得分
- 硬件不做 softmax
- CPU 或测试程序用 `argmax(logits)` 得到最终类别

RTL 内部结构建议画成：

```text
AXI-Stream input
  -> inputWords[4] 64-bit 输入 word-bank
  -> 集中式 FSM 控制层/输出行/输入列
  -> 显式固定权重 ROM
       - L1/L2/L3 weight ROM：32-bit word，每 word 打包 4 个 INT8 权重
       - L1/L2/L3 bias ROM：32-bit bias
  -> ROM address = outIdx * wordsPerRow + (inIdx >> 2)
  -> 4-lane PE/MAC
       - lane0..3 消费同一个 32-bit weight word
       - activation 从 inputWords/l1OutWords/l2OutWords 取出
  -> accReg
  -> requant / ReLU / clamp
  -> l1OutWords[8] / l2OutWords[4] 64-bit activation word-bank
  -> pendingLogit0 / lastLogit0 / lastLogit1
  -> AXI-Stream output
```

汇报时可以强调：

- 当前实现已经不是早期“Vec 常量表 + rowReg 行缓存”的结构。
- 权重以显式 ROM 形式组织，物理上仍由 Vivado 映射为 distributed ROM / LUT 资源。
- MAC 阶段通过 `outIdx` 和 `inIdx` 生成 ROM 地址，每周期取出 4 个 INT8 权重供 `4-lane PE` 使用。
- 激活缓存从大 packed UInt 改为按 64-bit word 组织，便于解释 AXI-Stream beat 与中间激活写回。

---

## 5. 权重存储与调用方式

这一点建议 PPT 单独放一页，因为老师或师兄很可能会问。

当前权重不是运行时从 DDR 读入，也不是 CPU 可改写 RAM。当前实现是：

```text
release 参数文件
  -> Chisel elaboration 读取
  -> 打包为 32-bit weight words
  -> 写出 generated-src/radar_qmlp_mem/*.hex
  -> RadarQMLPAsyncRom 内联生成 ROM RTL
  -> initial $readmemh 初始化 ROM 内容
  -> Vivado 按 rom_style="distributed" 综合为 distributed ROM / LUT
```

运行时：

```text
outIdx 选择当前输出神经元 / 权重行
inIdx 选择当前行内输入维度
weightWordIndex = inIdx >> 2
romAddr = outIdx * wordsPerRow + weightWordIndex
  -> ROM 输出 32-bit weight word
  -> 4-lane PE 同时消费其中 4 个 INT8 权重
  -> activation word-bank 输出对应 4 个 INT8 激活
  -> partial sum 累加到 accReg
```

准确表述：

> QMLP 权重在硬件生成阶段固化为显式只读 ROM 表，ROM 初始化内容来自 release 参数导出的 hex 文件。FPGA 实现中该 ROM 按 distributed ROM / LUT 形式综合，不占用 BRAM；运行时通过 `outIdx` 和 `inIdx` 生成地址，每周期读取一个 32-bit 权重 word 供 `4-lane PE` 消费。

PPT 中不要说：

```text
权重存在 BRAM ROM 中
权重可以运行时由 CPU 改写
每次推理都从 DDR 搬权重
```

除非后续真的改成 BRAM ROM、SRAM macro 或可配置权重 RAM。

---

## 6. 数据流与 input/output

### 6.1 当前测试输入从哪里来

当前板级测试输入来自软件侧交付的 golden 数据包：

```text
releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/
  hardware_validation_20260414/
    large_golden/
    boundary_cases/
```

测试程序将这些 `input_int8[21]` 编译进 bare-metal ELF 或通过头文件引用。运行时流程是：

```text
PC 下载 ELF
  -> RISC-V CPU 运行测试程序
  -> CPU 配置 DMA 和 QMLP
  -> DMA 从 DDR 读取 input_int8[21]
  -> AXI-Stream 送入 QMLP
  -> QMLP 输出 logits_int32[2]
  -> DMA 写回 DDR
  -> CPU 读取结果，与 golden logits 对拍
```

### 6.2 QMLP 输入

```text
input_int8[21]
```

含义：软件模型冻结后导出的 21 维雷达特征，当前对应 `k=7 + rcs21` 版本。

### 6.3 QMLP 输出

```text
logits_int32[2]
```

含义：

- `logits[0]`：pedestrian
- `logits[1]`：vehicle
- 输出为最终层 INT32 累加结果
- 不代表概率
- 不经过 softmax

---

## 7. QMLP 优化内容与创新点候选

### 7.1 已实现的优化内容

| 版本/阶段 | 主要内容 | 结果 |
|---|---|---|
| baseline | 固定 QMLP 模型硬件化 | 多样本 QMLP 通过，`hw_cycles_avg = 3554` |
| v2.5 | 保持 4-lane PE，优化 requant 常数乘实现，降低 DSP/布局扰动 | `hw_cycles_avg = 1301`，QMLP `DSP = 0`，WNS 明显改善 |
| v2.8 | 修复 batch 样本接收边界，优化 e2e 数据流 | batch-only e2e 通过，平均每样本 e2e 约 `23.145 ms` |
| k7 | 替换最终推荐 `k=7 + rcs21` 权重/scale/golden | `1000/1000` large golden 与 `54/54` boundary 通过 |
| word-bank/ROM 重构版 | 显式 distributed ROM、32-bit weight word、64-bit activation word-bank、集中式 FSM / next-value 风格 | bitstream 通过，板级 `1000/1000` + `54/54` 通过，kernel 保持 `1301 cycles` |

### 7.2 创新点候选

候选 1：面向雷达目标检测 QMLP 的 RISC-V SoC 内嵌式专用加速器

- 不是单独 FPGA IP 测试，而是接入 RISC-V SoC。
- CPU 负责控制与调度，QMLP 负责核心推理。
- 适合论文中支撑“低功耗边缘部署”和“软硬件协同处理”主线。

候选 2：固定权重 INT8 QMLP 的显式 ROM 与 word-bank 数据流

- 权重固化为显式只读 ROM，初始化来自 release 导出的 hex 文件，无运行时权重搬运。
- 每个 32-bit weight word 打包 4 个 INT8 权重，与 `4-lane PE` 的消费宽度一致。
- 激活缓存按 64-bit word-bank 组织，和 AXI-Stream 64-bit beat 对齐。
- 对小型固定 QMLP 很适合，资源低、控制清晰、延迟稳定。
- 注意：这更偏“针对本模型的架构选择”，不要过度说成通用 NN 加速器创新。

候选 3：4-lane PE/MAC 阵列化推理结构

- 每周期处理 4 个输入维度的乘加。
- 从 baseline `3554 cycles` 降到 `1301 cycles`。
- 保持 `DSP = 0` 的实现风格，适合资源受限 FPGA 原型。

候选 4：面向 batch 推理的 e2e 数据流修复与优化

- v2.8 修复 batch 样本边界错位问题。
- 从单样本式 e2e 约 `178 ms` 量级，下降到 batch 平均每样本约 `22~23 ms`。
- 这个创新更适合作为“系统级优化”而不是“神经网络算法创新”。

---

## 8. 不建议包装成创新点的内容

这些可以作为工程实现或系统支撑，不建议单独包装成创新点：

| 内容 | 建议定位 |
|---|---|
| 使用 Chipyard/Rocket 搭 SoC | 工程平台搭建，不宜单独说成创新 |
| UART-TSI 下载 ELF | 验证与调试手段 |
| AXI DMA 基础搬运 | 标准数据搬运机制 |
| Vivado bitstream 生成通过 | 工程闭环结果 |
| golden 对拍流程 | 验证方法，属于支撑证据 |
| 权重用 distributed ROM 固化 | 可作为针对小模型的实现策略，但不要说成普适存储创新 |

更稳妥的写法是：

> 本文在 RISC-V SoC 原型系统中完成了固定 QMLP 模型的专用硬件化、显式 ROM 权重访问、word-bank 激活缓存、PE 并行计算结构与 DMA 数据流集成，并通过板级 golden 对拍验证其正确性和时延优势。

---

## 9. 测试结果

### 9.1 正确性

当前最终 `k=7 + rcs21` 版本板测结果：

| 测试集 | 样本数 | 结果 | 说明 |
|---|---:|---|---|
| `large_golden` | 1000 | `1000/1000` 通过 | 真实样本大规模 golden 对拍 |
| `boundary_cases` | 54 | `54/54` 通过 | 全 0、极值、交替、单维激活等边界输入 |

结论：

> 当前 `k=7 + rcs21` QMLP bitstream 已经完成板级功能验证；新权重、scale、requant multiplier 已正确固化进硬件。

### 9.2 延迟

当前主频按 `50 MHz` 换算：

| 指标 | cycles | 时间 |
|---|---:|---:|
| QMLP kernel latency | 1301 | 约 `26.02 us` |
| large_golden batch 平均每样本 e2e | 1117247 | 约 `22.345 ms` |
| boundary 单样本式 e2e | 8941730 | 约 `178.835 ms` |

说明：

- kernel latency 是 QMLP 模块内部从接收完成后执行推理到输出 logits 的硬件计算周期。
- e2e latency 包含 CPU 程序调度、DMA 配置、DDR 搬运、AXI-Stream 推理、结果回读等系统开销。
- boundary 当前按单样本式路径跑，主要用于鲁棒性，不代表最高吞吐路径。

### 9.3 性能对比

| 版本 | kernel cycles | 相对说明 |
|---|---:|---|
| 固定 QMLP baseline | 3554 | 串行/较低并行度基线 |
| 4-lane PE v2.5 / k7 | 1301 | 周期数下降约 `63.4%` |

计算：

```text
1 - 1301 / 3554 ≈ 63.4%
3554 / 1301 ≈ 2.73x
```

---

## 10. PPA 指标

### 10.1 平台与工具

| 项目 | 内容 |
|---|---|
| FPGA | Nexys Video / Artix-7 |
| Device | `xc7a200tsbg484-1` |
| Tool | Vivado 2022.2 |
| Design | `NexysVideoHarness` |
| 主系统时钟 | `50 MHz` |

### 10.2 时序

| Clock group | Period | Frequency | WNS | WHS | 说明 |
|---|---:|---:|---:|---:|---|
| `clk_out1_harnessSysPLLNode` | 20.000 ns | 50 MHz | 0.531 ns | 0.051 ns | DUT 主域，Rocket / 总线 / DMA / QMLP 主路径 |

结论：

> 当前 `k7` bitstream 在 50 MHz DUT 主域下时序为正余量，可作为板级验证与论文记录的有效硬件基线。

### 10.3 资源

以 Vivado `utilization.txt` 为准：

| 层级 | Total LUTs | Logic LUTs | LUTRAMs | SRLs | FFs | RAMB36 | RAMB18 | DSP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `NexysVideoHarness` | 28366 | 24346 | 3726 | 294 | 17445 | 2 | 14 | 10 |
| `RadarAXISQMLP` | 3341 | 3341 | 0 | 0 | 1491 | 0 | 0 | 0 |

QMLP 资源结论：

- 权重没有用 BRAM。
- 计算没有用 DSP。
- 权重 ROM 在 FPGA 上综合为 distributed ROM / LUT 结构。
- 主要资源为 LUT + FF。
- 这与“显式固定 ROM + word-bank activation cache + 4-lane PE”的实现方式一致。

### 10.4 Power

当前仓库内未看到独立的 Vivado power report 或板级功耗实测记录。PPT 中建议暂时写：

```text
Power: 待补充 Vivado report_power 或板级功耗测试
```

不要在正式汇报里编造功耗数据。

---

## 11. PPT 页面建议

建议 10 页左右：

1. 研究背景与系统目标
2. 整体 RISC-V SoC 架构
3. AXI DMA + AXI-Stream 数据流
4. QMLP 模型结构与 input/output
5. NN-RTL 架构：集中式 FSM + ROM 权重 + word-bank activation + 4-lane PE
6. 权重存储方式：显式 distributed ROM，不是 BRAM、不是运行时 RAM
7. 创新点候选
8. 正确性测试：large golden + boundary
9. PPA：资源、时序、延迟
10. 当前不足与后续工作

---

## 12. 后续建议补充

为了让 PPT 和论文更稳，建议后续补充：

| 材料 | 用途 |
|---|---|
| QMLP 状态机图 | 解释 `sRecv -> sL1Load -> sL1Mac -> ... -> sEmit` |
| 一张 4-lane PE 细节图 | 说明 `inIdx + lane` 并行乘加 |
| 一张权重 ROM 与 word-bank 图 | 回答“权重存在哪里、如何被 4-lane PE 消费” |
| Vivado power report | 补齐 PPA 中的 Power |
| Flash/交互式 demo 流程 | 答辩展示更自然 |
| PC CPU-only / Jetson / RISC-V CPU-only 对比表 | 支撑“为什么要硬件加速/边缘部署” |
| 资源占用百分比 | 比单纯 LUT/FF 数字更适合 PPT |

---

## 13. 推荐汇报表述

可以在 PPT 结尾这样总结：

> 当前硬件系统已经完成从软件 QMLP 模型到 RISC-V SoC 内嵌式 RTL 加速器的实现闭环。模型采用 `21->64->32->2` INT8 结构，权重在 bitstream 生成阶段固化为显式 distributed ROM，运行时通过 `outIdx/inIdx` 地址访问、`32-bit` 权重 word 和 `4-lane PE` 完成定点推理；中间激活采用 `64-bit` word-bank 缓存。板级验证中，`1000` 组 large golden 与 `54` 组 boundary cases 全部通过，QMLP kernel latency 为 `1301 cycles`，约 `26.02 us @ 50 MHz`。该结果可支撑论文中“面向低功耗边缘雷达检测的 RISC-V SoC + 专用神经网络加速器设计”的硬件主线。
