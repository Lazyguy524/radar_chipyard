# 论文整体逻辑漏洞审查与补救方案

日期：2026-04-16  
对象：《基于 RISC-V 的雷达信号智能处理系统设计与研究》  
审查口径：按答辩委员从“系统闭环、端到端延迟、创新合理性、实验可信度”角度进行严格质疑。

---

## 1. 总结论

当前项目不会因为“21 维输入特征计算比 QMLP 慢 10 倍”而整体崩溃，但论文叙事必须立刻调整。

如果论文继续按下面这种逻辑写：

> 本文完成了雷达信号智能处理系统，QMLP 硬件延迟只有 26.02 us，因此系统具备低延迟边缘推理能力。

这个逻辑是危险的。

因为当前硬件真正加速的是：

```text
int8[21] feature vector -> QMLP -> int32 logits[2]
```

而不是完整的：

```text
raw radar / point cloud / x-y-doppler-rcs -> feature extraction -> quantization -> QMLP -> classification
```

如果 21 维特征构建耗时约为 QMLP kernel 的 10 倍，那么 QMLP kernel 只占完整计算链路约 `1 / 11 = 9.1%`。这意味着：

- 继续优化 QMLP kernel 对系统端到端延迟帮助有限。
- 论文不能只展示 QMLP kernel latency。
- 必须补充 feature extraction 的耗时、位置、实现方式和未来硬件化路线。

更准确的论文定位应改为：

> 本文当前完成的是“面向已量化 21 维雷达特征的 RISC-V SoC QMLP 推理加速原型”，并识别出特征构建是后续完整雷达智能处理系统的主要瓶颈，提出并部分实现面向 AXI-Stream 的板端特征构建/数据流融合方案。

---

## 2. 最大逻辑漏洞：特征构建瓶颈

### 2.1 当前硬件链路边界

当前 QMLP 硬件输入是：

```text
input_int8[21]
```

这 21 维数据已经是软件侧处理、冻结、量化后的特征。硬件 QMLP 不知道：

- 原始 radar frame 是什么格式
- x/y/doppler/rcs 如何得到
- k=7 邻域或聚类如何构建
- 21 维特征如何归一化、量化、裁剪

因此当前硬件结果只能证明：

> 从 21 维 INT8 特征到 2 维 logits 的板级推理正确且延迟稳定。

不能证明：

> 从雷达原始信号到目标类别的完整链路已经硬件低延迟化。

### 2.2 10 倍特征构建开销意味着什么

若：

```text
T_qmlp_hw = 26.02 us
T_feature ≈ 10 * T_qmlp_hw ≈ 260 us
```

则：

```text
T_feature + T_qmlp_hw ≈ 286 us
```

其中 QMLP 只占：

```text
26.02 / 286 ≈ 9.1%
```

这说明：

- QMLP 已经不是主要瓶颈。
- 继续把 QMLP 从 26 us 优化到 10 us，完整链路只从 286 us 降到 270 us，收益约 5.6%。
- 若 feature extraction 不迁移或不优化，论文中“低延迟智能处理系统”的说服力会明显下降。

这就是典型的 Amdahl 定律问题。

### 2.3 这会不会让论文崩溃

不会必然崩溃，但会改变论文贡献边界。

如果不补救，论文只能安全地写成：

> QMLP 推理核硬件加速系统。

如果要支撑题目中的“雷达信号智能处理系统”，至少需要补充：

- 21 维特征构建耗时
- 特征构建目前在哪个平台完成
- 特征构建是否可迁移到 RISC-V CPU
- 特征构建是否可硬件化
- QMLP 与 feature extraction 是否能流水并行

---

## 3. 硬件补救措施

### 3.1 最低成本补救：明确系统边界并补测 latency budget

这是必须做的，不做论文会被问穿。

需要建立一张完整 latency budget 表：

| 阶段 | 当前实现位置 | 是否已硬件化 | 延迟 |
|---|---|---|---:|
| radar 数据读取/输入 | PC/软件/DDR | 否/部分 | 待测 |
| x/y/doppler/rcs 到 21 维特征 | 软件侧 | 否 | 待测 |
| int8 量化与打包 | 软件侧/CPU | 否/部分 | 待测 |
| DMA 搬运到 QMLP | RISC-V SoC | 是 | 已测 e2e 包含 |
| QMLP kernel | RTL | 是 | `26.02 us` |
| logits 读回与 argmax | CPU | 否 | 待测 |

论文中必须区分：

- `kernel latency`
- `feature latency`
- `DMA/software e2e latency`
- `full application latency`

### 3.2 中等成本补救：板端软件特征构建

如果时间不够做硬件特征提取器，至少要把 feature extraction 放到板端 RISC-V C 程序里测一次。

目的不是追求快，而是回答：

> 当前系统如果不靠 PC 预生成 21 维输入，RISC-V CPU 能否完成特征构建，并且开销是多少？

需要输出：

- `feature_cycles_avg`
- `quant_pack_cycles_avg`
- `qmlp_kernel_cycles_avg`
- `full_board_cycles_avg`

这样论文可以诚实写：

> 当前 NN 推理已硬件化，系统主要瓶颈转移到特征构建。本文进一步测量了板端特征构建开销，并给出后续硬件化设计。

### 3.3 较强补救：实现 `RadarFeature21Preprocessor`

如果 21 维特征构建规则主要由固定点运算、加减乘、归一化、裁剪、拼接组成，则可以在硬件中新增一个特征构建模块：

```text
AXI-Stream raw/point features
  -> RadarFeature21Preprocessor
  -> int8[21]
  -> RadarAXISQMLP
  -> logits[2]
```

推荐模块定位：

- 不要替换 QMLP
- 放在 QMLP 前面
- 与现有 `RadarAXISPreprocessor` 区分开
- 命名建议：`RadarAXISFeature21` 或 `RadarFeature21Preprocessor`

建议接口：

```text
input:  packed x/y/doppler/rcs or point-cluster descriptor
output: int8[21] packed as 32B sample
```

硬件实现可以分阶段：

1. affine/scale/clip/quantize
2. simple statistics
3. k=7 fixed neighborhood aggregation
4. top-k/sort/cluster 逻辑

### 3.4 最强补救：feature extraction 与 QMLP 流水融合

如果完整特征构建很难一次做完，可以先实现流水调度：

```text
Feature extractor handles sample N+1
QMLP handles sample N
DMA writes back sample N-1
```

这样即使 feature extraction 单样本比 QMLP 慢 10 倍，也能形成系统论述：

- 当前瓶颈是 feature extraction。
- QMLP 已经足够快，可以作为后级分类器。
- 系统吞吐由 feature stage 决定。
- 后续通过并行 feature lanes 或 batch 化特征构建提升吞吐。

---

## 4. 其他关键逻辑漏洞

### 4.1 输入来源漏洞

当前板测输入来自编译进 ELF 的 golden 数据或 DDR buffer，而不是实时雷达传感器。

如果论文说“实时雷达处理”，评委会问：

- 雷达数据从哪里进板子？
- 采样率是多少？
- 一帧多少点？
- 数据如何从传感器进入 DDR？
- UART 下载 ELF 是否属于实际系统？

补救：

- 明确当前是离线样本回放式板级验证。
- 若没有真实雷达输入，不能宣称完整实时系统。
- 可以写成“面向在线部署的 SoC 原型验证平台”。

### 4.2 Preproc 与 feature extraction 混淆

当前 `RadarAXISPreprocessor` 存在，但它不是完整的 21 维特征构建器。

不能写：

> 本文已经完成 radar raw feature preprocessing 到 QMLP 的全硬件链路。

应该写：

> 当前系统保留了 AXI-Stream preprocessor 插槽，已验证其与 QMLP 在 SoC 数据通路中的共存能力；完整 21 维特征构建仍需后续迁移至板端或硬件实现。

### 4.3 e2e 延迟口径漏洞

当前 e2e 测试包含大量测试程序和 DMA 调度开销，不能等价于最终产品在线延迟。

必须拆分：

- UART-TSI 下载：开发/测试阶段，不属于在线推理。
- DMA + CPU 配置：当前系统 e2e。
- QMLP kernel：加速器本体。
- feature extraction：完整智能处理的前级。

论文应避免只用一个“端到端延迟”覆盖所有情况。

### 4.4 CPU-only 对比漏洞

如果只拿板上 Rocket CPU-only 与硬件 QMLP kernel 比，结论是公平的。

但如果拿 Xeon C 实现、RTX 3090 PyTorch、Jetson、Rocket、FPGA 混在一张表里，说“谁更快”，会被打穿。

因为：

- 主频不同
- 平台不同
- 是否包含量化不同
- 是否包含数据搬运不同
- batch size 不同
- 功耗不同

建议拆成两类表：

1. 同平台公平对比：
   - Rocket CPU-only
   - Rocket + QMLP accelerator

2. 外部参考对比：
   - Xeon C
   - RTX 3090 PyTorch
   - Jetson

外部参考只能说明部署路线差异，不能作为绝对胜负。

### 4.5 精度数据版本混乱漏洞

已有文档里同时出现过：

- k3 版本 accuracy `0.9279`
- k7 QAT test accuracy `0.964551`
- k7 INT C-trace accuracy `0.972170`

论文必须统一当前最终模型为：

```text
k=7 + rcs21
21 -> 64 -> 32 -> 2
```

并区分：

- QAT test accuracy
- exported INT C-trace accuracy
- hardware golden 对拍正确率

不能写成：

> 量化后精度提升到 97.2%

更安全写法：

> 在导出的固定点 C-trace 口径下，测试集 accuracy 为 0.972170；硬件验证以该固定点导出结果作为 golden。

### 4.6 验证覆盖漏洞

当前硬件板测：

- `large_golden`: 1000 samples
- `boundary_cases`: 54 samples

软件 C-trace 全 test 是：

- 55516 samples

评委会问：

- 1000 样本如何选取？
- 是否覆盖全部类别？
- 是否覆盖错误样本？
- 为什么不全量板测？

补救：

- 说明 1000 是板级回归子集。
- 补一个全量或更大批量回归更好。
- 至少给 sample selection policy。
- 如果不能全量板测，写明硬件与 bit-accurate C reference 对拍路径。

### 4.7 功耗与能效漏洞

题目和动机强调低功耗边缘部署，但当前硬件结果主要是 latency/resource/timing。

缺口：

- 没有板级功耗
- 没有 Vivado power
- 没有 energy/inference
- 没有与 CPU-only 的能耗对比

补救：

- 最低限度跑 Vivado power report。
- 更好是测板级电源功耗。
- 至少给 energy estimate：

```text
Energy = Power * Latency
```

否则“低功耗”只能作为背景，不能作为实验结论。

### 4.8 权重固定性漏洞

当前权重固化进 ROM/LUT，换模型需要重新生成 bitstream。

这不是错误，但必须说清楚。

优势：

- 资源小
- 时序简单
- 适合固定任务

缺点：

- 不能运行时更新模型
- 不支持多模型
- 不适合泛化神经网络平台

论文应写成“任务专用固定权重加速器”，不要写成“可编程神经网络处理器”。

### 4.9 50 MHz 主频漏洞

当前稳定主频是 50 MHz，之前 60/75 MHz 有时序违例。

如果论文强调高性能，会被问：

- 为什么只有 50 MHz？
- 是否能满足真实雷达帧率？
- 若换芯片/工艺是否成立？

补救：

- 不以高主频为卖点。
- 强调确定性低延迟和低资源。
- 给真实帧率需求反推是否够用。

### 4.10 论文题目范围偏大

题目是“雷达信号智能处理系统”，但当前硬件最强证据集中在“21 维特征后的 QMLP 推理”。

补救方式有两种：

1. 缩小论文实际贡献表述：
   - “雷达特征智能分类 SoC”
   - “面向雷达特征的轻量神经网络硬件加速”

2. 补全特征构建章节：
   - 软件特征构建
   - latency budget
   - 硬件化方案
   - 可选原型

---

## 5. 建议立即补的实验

### 5.1 必补：feature extraction latency

需要测：

```text
T_feature_cpu
T_quant_pack_cpu
T_qmlp_cpu
T_qmlp_hw
T_dma_qmlp_e2e
```

建议输出表：

| 阶段 | 平台 | cycles/us | 占比 |
|---|---|---:|---:|
| feature extraction | Rocket CPU | 待测 | 待测 |
| quant/pack | Rocket CPU | 待测 | 待测 |
| QMLP hardware kernel | RTL | 26.02 us | 待算 |
| DMA/QMLP e2e | SoC | 22.345 ms | 待算 |

### 5.2 必补：全链路数据流图

图中必须明确：

```text
raw radar / point data
  -> feature extraction
  -> int8[21]
  -> QMLP accelerator
  -> logits
  -> argmax
```

用颜色区分：

- 已硬件化
- 当前软件侧
- 当前测试环境
- 后续计划

### 5.3 必补：全量或更大样本硬件验证

如果时间允许，做：

- 全 55516 test samples 板级回归

如果太慢，做：

- 类别均衡抽样
- 错误样本抽样
- 极值样本抽样
- 随机 5000 或 10000 样本

### 5.4 强烈建议：Vivado power report

至少给：

- full SoC power
- QMLP activity estimate
- resource-based static/dynamic estimate

如果没有真实功耗，论文不能强说“低功耗结果优秀”。

### 5.5 建议补：Flash/online deployment 说明

当前 UART-TSI 是开发方式，不是部署方式。

建议论文里画：

```text
开发验证：PC -> UART-TSI -> ELF -> DDR -> test
实际部署：Flash boot -> sensor/DMA -> accelerator -> result
```

---

## 6. 硬件实现层面的后续路线

### 6.1 路线 A：只做论文安全补救

不新增硬件模块，只补：

- latency budget
- feature extraction software measurement
- 论文边界说明
- future work

优点：

- 风险低
- 不影响当前已通过的 QMLP baseline

缺点：

- 论文创新强度有限
- “雷达信号智能处理系统”题目支撑偏弱

### 6.2 路线 B：实现轻量 feature quant/pack 硬件

如果 21 维特征已经由上游软件得到 float/int，但量化/裁剪/打包慢，可以先硬件化：

```text
feature int/float-like fixed input -> scale -> clamp -> int8[21] -> pack 32B
```

优点：

- 实现难度中等
- 能证明前处理开始迁移到硬件
- 和当前 QMLP 很容易串起来

缺点：

- 如果真正慢的是 kNN/聚类/特征统计，这只能解决一小部分。

### 6.3 路线 C：实现完整 `RadarFeature21Preprocessor`

把 x/y/doppler/rcs 到 21 维特征构建搬到 AXI-Stream 硬件中。

优点：

- 论文系统性明显增强
- 可以真正回应“feature extraction 比 QMLP 慢”的质疑

缺点：

- 需要软件侧给出精确定义和 bit-accurate golden
- 若涉及排序、kNN、聚类、除法、sqrt，硬件复杂度会显著上升
- 需要重新做验证和 bitstream

### 6.4 路线 D：流水并行而非完全硬件化

如果完整 feature extraction 太复杂，可以先做流水调度：

```text
CPU computes feature(N+1)
DMA/QMLP processes feature(N)
CPU reads result(N-1)
```

优点：

- 工程风险低
- 能减少 CPU/QMLP 空闲
- 适合论文讲 system scheduling

缺点：

- 总吞吐仍受 feature extraction 限制
- 不能说完成了特征硬件加速

---

## 7. 论文主线重写建议

### 7.1 原主线风险

风险主线：

```text
雷达信号处理
  -> QMLP 很小
  -> 我做了硬件加速
  -> 所以系统低延迟
```

问题：

- 忽略特征构建
- 忽略 DMA/e2e
- 忽略输入来源
- 容易被 Amdahl 定律打穿

### 7.2 推荐新主线

推荐主线：

```text
停车场雷达边缘部署要求低功耗和确定性响应
  -> 软件侧将任务压缩为 21 维特征 + INT8 QMLP
  -> 硬件侧先完成 QMLP 推理核和 RISC-V SoC 数据通路闭环
  -> 板级验证证明 QMLP kernel 正确且稳定
  -> 系统 profiling 发现 feature extraction / DMA 调度成为新瓶颈
  -> 论文给出 latency budget 和前处理硬件化/流水化方案
```

这样写的好处：

- 不假装所有东西都已经完美。
- 把瓶颈迁移作为系统研究发现。
- 给后续特征硬件化留下合理章节。
- 论文显得更诚实，也更像系统论文。

---

## 8. 答辩高危问题清单

必须准备回答：

1. 你的硬件输入为什么已经是 21 维特征，而不是 radar raw data？
2. 21 维特征是谁算的？在哪里算的？耗时多少？
3. 如果 feature extraction 比 QMLP 慢 10 倍，QMLP 加速还有意义吗？
4. 你的 `26.02 us` 是完整系统延迟还是 kernel 延迟？
5. 当前 e2e 为什么是 ms 级？
6. 你的 Preproc 是否真的生成了 21 维输入？
7. 当前系统是否支持实时雷达传感器输入？
8. UART-TSI 下载 ELF 是否属于实际部署路径？
9. 权重固定在 bitstream 里，模型变了怎么办？
10. 为什么不用 Gemmini / FINN / hls4ml？
11. 为什么不用 PC / Jetson / ARM MCU？
12. 1000 组样本通过是否足够？
13. 有没有功耗数据？
14. 50 MHz 是否满足真实应用？
15. 如果目标是低功耗，energy/inference 是多少？

---

## 9. 最终判断

当前论文内容不是不能写，而是必须从“炫耀 QMLP 26 us”转成“系统瓶颈分析 + 任务专用硬件闭环”。

最真实的评价是：

> QMLP 硬件化已经做得足够扎实，但它只是完整雷达智能处理链路中的后级分类器。当前项目真正欠缺的是前级 21 维特征构建的板端实现和全链路 latency budget。如果不补这部分，论文仍可成立，但题目和结论都必须收窄；如果能补上 feature extraction 的测量和硬件/流水化方案，论文完整性会明显提升。

建议优先级：

1. 立刻补 feature extraction 耗时表。
2. 立刻画全链路边界图。
3. 论文中明确 QMLP kernel 与 full pipeline 的区别。
4. 若时间允许，实现或至少设计 `RadarFeature21Preprocessor`。
5. 补功耗或 Vivado power。
6. 更新所有 k3/k7、accuracy、latency 口径，避免混用。

---

## 10. 板端前处理与帧融合位置补充判断

### 10.1 如果把前级数据处理也放到板子上，速度是否一定会更好

不一定。

当前 QMLP kernel 很小，硬件侧计算量约为：

```text
21x64 + 64x32 + 32x2 = 3456 MAC
```

因此 `26.02 us/sample` 说明的是后级分类器推理核很快，但不代表完整链路已经很快。如果前级 `x/y/doppler/rcs -> 多帧融合 -> 聚类/统计 -> 21 维特征 -> INT8 量化` 的耗时约为 QMLP 的 10 倍，那么系统瓶颈会自然转移到前级特征构建。

需要区分三种情况：

| 放置方式 | 速度判断 | 论文含义 |
|---|---|---|
| PC 端做前处理，板端只做 QMLP | 当前验证方式，QMLP 快，但不是完整端到端 | 适合证明 QMLP 硬件核正确性 |
| Rocket CPU 做前处理 | 不一定快，50 MHz 软处理可能成为瓶颈 | 可证明板端自洽，但不宜夸大性能 |
| FPGA 逻辑做前处理 | 对固定点统计、归一化、量化、简单归约可能有效 | 可作为后续增强点或论文展望 |

因此，如果只是把前处理 C 代码搬到 RISC-V CPU 上，速度大概率不会“突然变好”；它更像是部署完整性提升，而不是性能提升。真正可能提升速度的是把前处理中规则、定点、流式、可并行的部分硬件化，例如求和、最大/最小、均值、计数、简单归一化、定点量化和打包。

### 10.2 当前帧融合发生在 21 维之前还是之后

根据当前工程交付文档和硬件接口，帧融合发生在 21 维特征生成之前，或者说发生在生成 21 维特征的过程中。

当前 QMLP 的硬件输入是：

```text
int8[21]
```

这 21 维输入已经是软件侧完成多帧融合、统计特征提取、量化之后的结果。QMLP 之后只输出 2 维 logits，用于分类判决，不再进行帧融合。

当前真实链路应表述为：

```text
多帧 radar/point data
  -> 帧融合/点簇处理/统计特征提取
  -> 21 维特征
  -> INT8 量化
  -> AXI DMA 输入 QMLP
  -> 2 维 INT32 logits
  -> argmax / 分类结果
```

### 10.3 对论文主线的影响

这不会导致论文“崩溃”，但会否定一种过度表述：

```text
错误表述：我完成了完整雷达智能处理链路的低延迟硬件加速。
```

更稳妥的表述是：

```text
本文完成了 21 维雷达融合特征对应的轻量化 QMLP 分类器硬件化，
并在 RISC-V SoC 上完成 AXI DMA 数据通路、板级验证和性能 profiling。
实验进一步表明，后续完整端到端优化的主要瓶颈应转向前级特征构建。
```

如果后续能补充 `x/y/doppler/rcs -> int8[21]` 的板端 CPU 耗时，或者实现部分 FPGA 前处理，那么论文完整性会明显增强。
