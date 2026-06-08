# Radar 项目当前总览与导读

更新时间：2026-04-14

本文档用于把当前项目的高价值进展、关键结论、建议阅读顺序和常见概念统一收口。  
如果只想快速了解“现在做到哪一步了”，优先看这一份。

---

## 1. 当前一句话结论

当前项目已经从“Rocket + DDR + DMA + AXIS 通路样机”推进到“固定 `INT8 QMLP` 模型板上推理样机”，并且已经在此基础上完成了 `4-lane PE` 阵列化版本、batch e2e 优化，以及当前软件侧推荐 `k=7 + rcs21` 模型的板级验证。

当前最新硬件基线是：

- `k=7 + rcs21 QMLP`
- 结构仍为 `21 -> 64 -> 32 -> 2`
- `INT8 weight / INT8 activation / INT32 logits`
- `4-lane PE` 结构保持不变

对应正式说明：

- [radar_qmlp_k7_backend_and_validation_2026-04-14.md](/home/soooarr/chipyard/docs/radar_qmlp_k7_backend_and_validation_2026-04-14.md)

当前最重要的版本是：

- `radar-qmlp-pe-array-v2p5`

它已经同时满足：

- 保留 `4-lane PE`
- 离线时序通过，且余量明显改善
- 板上 `hello + selfcheck` 通过
- 板上 `integrated regression + selfcheck` 通过
- `QMLP` 多样本回归通过

当前 `k7` 版本额外满足：

- `k7` 参数替换后 bitstream 通过
- `large_golden`: `1000 / 1000` 通过
- `boundary_cases`: `54 / 54` 通过
- `QMLP kernel latency` 仍为 `1301 cycles ≈ 26.02 us @ 50 MHz`

当前最新的 e2e 优化阶段版本是：

- `v2.8`

它已经额外满足：

- 修复 `batch` 样本边界错位
- `batch-only` e2e 板上通过
- 在不降低 `4-lane PE` 并行度的情况下，把平均每样本 e2e 压到约 `23.145 ms`

---

## 2. 当前系统到底实现了什么

### 2.1 SoC 主体

当前板上 SoC 主体包括：

- `Rocket RISC-V CPU`
- `TileLink / AXI` 互连
- `DDR + MIG`
- `AXI DMA`
- `AXI-Stream` 数据处理链

当前稳定主频基线仍然是：

- `50 MHz`

### 2.2 当前 NN 加速器

当前已经实现并板测跑通的 NN 模块是：

- `RadarAXISQMLP`

源码位置：

- [RadarQMLP.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarQMLP.scala)

它对应的是冻结模型：

- `21 -> 64 -> 32 -> 2 INT8 QMLP`

也就是说，当前确实已经完成了：

- **模型硬件化**

但这不是“通用可编程 NN accelerator”，而是：

- **一个面向冻结 QMLP 模型的专用硬件推理块**

### 2.3 AXIS Preprocessor 还在不在

还在。

当前不是把 `AXI-PreProc` 删掉了，而是：

- `RadarAXISPreprocessor` 仍然保留
- `RadarAXISQMLP` 在同一条 AXI-Stream 主数据路中新增接入

所以当前可以理解为：

- `Preproc` 和 `QMLP` 共存
- 在 DMA 中间这条 `AXIS` 路上按配置切换

---

## 3. 当前 QMLP 到底做到了什么程度

### 3.1 baseline 阶段

最早完成的是“固定模型硬件化 baseline”：

- 固定输入维度 `21`
- 固定网络结构 `21 -> 64 -> 32 -> 2`
- 固定量化规则 `INT8`
- 固定权重参数

这个版本已经完成了：

- 单样本板测通过
- 多样本板测通过

对应摘要：

- [243-qmlp-multisample-pass-summary-2026-04-06.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/243-qmlp-multisample-pass-summary-2026-04-06.md)

baseline 的硬件周期为：

- `hw_cycles_avg = 3554`

### 3.2 PE 阵列化阶段

在 baseline 之后，项目继续把 `QMLP` 往 PE/MAC 阵列方向推进，主要经历了：

- `v2`
- `v2.1`
- `v2.2`
- `v2.3`
- `v2.4`
- `v2.5`

其中真正收成当前可用版本的是：

- `v2.5`

对应摘要：

- 离线 bitstream 总结：
  [339-qmlp-pe-array-v2p5-bitstream-summary-2026-04-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/339-qmlp-pe-array-v2p5-bitstream-summary-2026-04-09.md)
- 板级通过总结：
  [344-v2p5-board-pass-summary-2026-04-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/344-v2p5-board-pass-summary-2026-04-09.md)

### 3.3 e2e 优化阶段

在 `v2.5` 把 kernel latency 压到 `1301 cycles` 之后，后续优化重点不再是继续削减 PE，而是开始转向 system e2e latency。

这条线目前收成的关键版本是：

- `v2.6`
- `v2.8`

其中：

- `v2.6` 用来建立新的 e2e 优化基线
- `v2.8` 解决了 batch 模式下第二个样本开始错位的问题，并完成了 `batch-only` 板级验证

对应摘要：

- e2e checkpoint：
  [356-qmlp-e2e-v2p6-checkpoint-2026-04-10.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/356-qmlp-e2e-v2p6-checkpoint-2026-04-10.md)
- batch 修复离线摘要：
  [412-qmlp-e2e-batchfix-v2p8-summary-2026-04-10.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/412-qmlp-e2e-batchfix-v2p8-summary-2026-04-10.md)
- batch 板级通过摘要：
  [421-v2p8-batch-pass-summary-2026-04-10.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/421-v2p8-batch-pass-summary-2026-04-10.md)

### 3.4 `v2.8` 到底改了什么

`v2.8` 不是重新换一套 DMA，也不是把 `PE` 阵列降级，而是专门修了 batch 样本边界的接收逻辑。

之前 `batch-only` 诊断已经出现了一个很典型的现象：

- `out[0]` 正确
- `out[1]` 开始错位
- `sample = 32`
- `output = 8`
- 但实际 `out = 5`

这说明问题不在：

- 权重量化
- `L1/L2/L3` 的乘加
- `4-lane PE` 本身

而在：

- **第二个样本开始时，输入 beat 被错位装载**

根因最终定位到 [RadarQMLP.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarQMLP.scala) 的 `recvBeatCount`。

旧逻辑的问题是：

- 上一个样本结束后，状态机会回到 `sIdle`
- `sIdle` 中虽然会写 `recvBeatCount := 0`
- 但下一样本首拍如果就在这个周期到来，地址计算仍可能用到上一样本残留的 `recvBeatCount`
- 这样 `baseByte` 就不是从 `0` 开始，而是可能沿用上一样本的末尾偏移

因此 `v2.8` 的修法是：

- 引入显式 `recvBeatBase`
- 在 `state === sIdle` 时强制把它视为 `0`
- `io.in.fire` 时统一使用 `recvBeatBase` 来参与：
  - `baseByte`
  - `recvBeatCount` 递增
  - 样本结束判断

一句话说：

- **`v2.8` 修的是 batch 样本首拍对齐，不是模型数学本体**

### 3.5 `v2.8` 为什么能把 e2e 压下来

`v2.5` 已经把 kernel 压到：

- `1301 cycles`

但旧流程还是按：

- 单样本
- 每次完整 DMA 往返
- 每次单独配置和等待

去跑，所以端到端仍然约：

- `178.31 ms`

`v2.8` 的意义不在于再把 kernel 从 `1301` 压得更低，而在于：

1. 保持 `4-lane PE` 不变  
2. 把 batch 数据流真正跑通  
3. 让 `8` 组样本在一次 batch 事务里连续经过：
   - `DDR -> MM2S -> RadarAXISQMLP -> S2MM -> DDR`

也就是说，当前下降的不是：

- 单次乘加周期

而是：

- **平均到每个样本上的 DMA/调度/等待开销**

所以现在最准确的理解是：

- `v2.5` 解决的是 **kernel latency**
- `v2.8` 开始解决的是 **batch e2e latency**

---

## 4. 现在的 QMLP + 4-lane PE 是什么意思

### 4.1 当前 QMLP 是不是只是模型硬件化

是，但不只是“把模型抄成 RTL”。

更准确地说，当前已经做了两层工作：

1. 固定 `QMLP` 模型硬件化  
2. 在此基础上把内部乘加从较串行的实现，推进成带 `4-lane PE` 的并行版本

### 4.2 当前的 `4-lane PE` 是什么

当前 `RadarAXISQMLP` 内部的 `PE` 含义是：

- 每个 `MAC` 轮次不是只做 1 个乘加
- 而是并行做 `4` 路乘加

所以它提升的是：

- **层内乘加并行度**

也就是每次状态机停留在 `MAC` 状态时，能消化更多输入维度。

### 4.3 它是不是已经是通用阵列加速器

还不是。

当前更准确的定位是：

- **固定 QMLP 的 4-lane PE 阵列化专用加速器**

还没有做到：

- 通用层配置
- 通用权重热切换
- 通用 GEMM/Conv 阵列指令化调度

所以论文表述上更适合说：

- 先完成固定模型 baseline
- 再在固定模型上完成 `PE` 阵列化优化

---

## 5. 文档里的 L1/L2 是什么意思

是的，这里的 `L1 / L2 / L3` 指的就是这个 MLP 模型的三层全连接：

- `L1`: 第一层，`21 -> 64`
- `L2`: 第二层，`64 -> 32`
- `L3`: 第三层，`32 -> 2`

所以：

- 文档里说的 `L1/L2`，就是 **MLP 模型的第一、第二层**
- 不是 cache hierarchy 的 `L1/L2 cache`

当前 `v2.5` 中被重点优化的是：

- `L1`
- `L2`

的 requant 实现路径。

---

## 6. v2.5 做了什么，以至于 WNS 提高这么多

这是当前最关键的技术点之一。

`v2.4` 的主要特征是：

- 保留 `4-lane PE`
- 把 `requant` 路径拆成多状态
- 但 `L1/L2` 的 requant 仍然用了类似：
  - `accReg * multiplier`

这种常数乘实现

在 `v2.4` 上，`QMLP` 本体资源中：

- `DSP = 4`

对应离线余量：

- `WNS = 0.337 ns`

而 `v2.5` 做的核心改动是：

- **保持 `4-lane PE` 不变**
- **不降并行度**
- **只把 `L1/L2` 的小常数 requant 乘法改成移位加法常数乘**

也就是把：

- `accReg * 1516`
- `accReg * 608`

改写成：

- `constMultiplyShiftAdd(accReg, constant, 64)`

这种 shift-add 结构

这样带来的直接结果是：

- `RadarAXISQMLP DSP: 4 -> 0`
- `WNS: 0.337 ns -> 3.385 ns`
- `WHS: 0.050 ns -> 0.248 ns`

当前最合理的解释是：

1. `v2.5` 没有削弱阵列  
2. 它减少了 requant 常数乘对 DSP/布局布线的扰动  
3. 从而让整个 `QMLP` 模块以及周边路径都变得更稳定  

一句话说：

- **`v2.5` 的关键不是“降复杂度”，而是“换实现风格”**

---

## 7. 当前是不是可以尝试再提主频

可以尝试，但要注意边界。

### 7.1 为什么说可以尝试

当前 `v2.5` 的离线余量已经明显改善：

- `WNS = 3.385 ns`

这说明相对之前的 PE 版本，`50 MHz` 下已经不再是边缘收敛状态。

### 7.2 为什么不能直接说“CPU 主频一定能提很多”

因为这里提的其实不是“只提 Rocket core 主频”，而是：

- **整个 SoC 主时钟**

也就是说，真正要一起承担更高频率的是：

- CPU
- 互连
- DMA
- MIG 边界
- `uart_tsi` 装载链
- QMLP / Preproc

以前做频率上探时，问题就不全在 CPU：

- 有些失败点在 `fbus / tsi2tl`
- 有些是 PLL / jitter 问题
- 有些是实现后时序问题

所以当前更准确的说法是：

- **`v2.5` 值得重新尝试频点上探**
- 但这叫“整机 SoC 主频上探”
- 不能简单理解成“Rocket 核本体一定能单独提到多少”

### 7.3 当前建议

如果后面要重新试，建议顺序是：

1. `55 MHz`
2. `60 MHz`

不建议一上来再冲 `75 MHz`。

---

## 8. 当前软件、kernel 与 e2e 的关键数据

为了避免后续只拿硬件 `26.02 us` 单独表述，本轮还补了一组 `Rocket CPU-only pure forward` 数据。

对应摘要：

- [350-qmlp-cpu-only-pure-forward-summary-2026-04-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/350-qmlp-cpu-only-pure-forward-summary-2026-04-09.md)

当前同口径数据为：

- `CPU-only pure forward ≈ 3306.86 us`
- `QMLP hardware kernel ≈ 26.02 us`

对应加速比约为：

- `3306.86 / 26.02 ≈ 127.1x`

这里要注意口径：

- 左边是 `Rocket CPU-only pure forward`
- 右边是 `QMLP hardware kernel`
- 两者都**不包含**串口下载、自检和 system end-to-end 流程

所以这组数据适合用于说明：

- **硬件算子本体相对于 Rocket 软件前向推理的加速效果**

但不能直接拿它去说明：

- **system end-to-end 加速比**

因为 system e2e latency 直到 `v2.5` 还没有完成系统级优化。

### 8.1 当前 e2e 优化结果

`v2.8` 当前已经完成的，不再只是 kernel 优化，而是 batch 路径上的 e2e 优化。

关键数据来自：

- [421-v2p8-batch-pass-summary-2026-04-10.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/421-v2p8-batch-pass-summary-2026-04-10.md)

当前 batch-only 板级结果为：

- `in = 32`
- `out = 8`
- `frames = 1`
- `hw_cycles_avg = 1301`
- `e2e_cycles_avg = 1157261`

按 `50 MHz` 换算：

- `kernel latency ≈ 26.02 us`
- `reset_batch_per_sample e2e latency ≈ 23.145 ms`

和旧单样本 e2e 相比：

- 旧单样本 e2e：约 `8.915M cycles`，约 `178.31 ms`
- `v2.8 reset_batch_per_sample`：`1.157M cycles`，约 `23.145 ms`

这说明：

- `v2.5` 解决的是 **kernel latency**
- `v2.8` 已经开始实质性压低 **system e2e latency**
- 当前 batch e2e 平均每样本端到端延迟，相比旧单样本流程约下降 `7.7x`

---

## 9. 当前最值得看的文档

如果你现在只想抓主线，优先看下面这几份就够：

1. 当前总览  
   - [radar_project_status_index_2026-04-09.md](/home/soooarr/chipyard/docs/radar_project_status_index_2026-04-09.md)

2. 阶段 SoC 总结  
   - [radar_soc_progress_report_2026-04-05.md](/home/soooarr/chipyard/docs/radar_soc_progress_report_2026-04-05.md)

3. QMLP 加速器设计说明  
   - [radar_nexysvideo_qmlp_accelerator_2026-04-06.md](/home/soooarr/chipyard/docs/radar_nexysvideo_qmlp_accelerator_2026-04-06.md)

4. PE 阵列原型路线  
   - [radar_qmlp_pe_array_prototype_2026-04-06.md](/home/soooarr/chipyard/docs/radar_qmlp_pe_array_prototype_2026-04-06.md)

5. `v2.5` 离线结果  
   - [339-qmlp-pe-array-v2p5-bitstream-summary-2026-04-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/339-qmlp-pe-array-v2p5-bitstream-summary-2026-04-09.md)

6. `v2.5` 板级结果  
   - [344-v2p5-board-pass-summary-2026-04-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/344-v2p5-board-pass-summary-2026-04-09.md)

7. `v2.8` batch e2e 板级结果
   - [421-v2p8-batch-pass-summary-2026-04-10.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/421-v2p8-batch-pass-summary-2026-04-10.md)

---

## 10. 为什么最近新生成的 log 前面没有序号

这是因为最近一部分日志不是手工按全局流水号命名的，而是由新写的脚本自动生成的。

例如这些脚本：

- [run_nexysvideo_uart_tsi.sh](/home/soooarr/chipyard/scripts/run_nexysvideo_uart_tsi.sh)
- [probe_nexysvideo_ddr_window.sh](/home/soooarr/chipyard/scripts/probe_nexysvideo_ddr_window.sh)

它们默认采用的是：

- `语义前缀 + 时间戳`

比如：

- `v2p5-hello-selfcheck-nomsip-2026-04-09-175245.log`

这种命名方式的优点是：

- 一眼能看出是什么测试
- 不需要每次人工维护全局编号

缺点就是你现在感受到的：

- 文件不再按全局数字自然排序
- 找起来没有 `339/344` 这种编号直观

所以现在仓库里其实存在两种风格：

1. 手工整理摘要类  
   - 常用 `NNN-...` 编号
2. 脚本直接产物  
   - 常用 `prefix-timestamp.log`

### 9.1 当前建议

现阶段先不批量改名，因为：

- 这些文件已经被文档和提交引用
- 贸然重命名会把链接打乱

更稳妥的做法是：

- 后续继续保留脚本自动文件名
- 但把“关键轮次”再补一份编号摘要

例如这次：

- 关键结论还是落在：
  - [339-qmlp-pe-array-v2p5-bitstream-summary-2026-04-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/339-qmlp-pe-array-v2p5-bitstream-summary-2026-04-09.md)
  - [344-v2p5-board-pass-summary-2026-04-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/344-v2p5-board-pass-summary-2026-04-09.md)

也就是说：

- 详细原始日志可以无编号
- 但关键阶段摘要尽量继续保留编号

---

## 11. 当前最重要的项目定位

截至现在，项目最准确的定位是：

- 已完成 `Rocket + DDR + DMA + AXIS` 的稳定 SoC 基线
- 已完成固定 `INT8 QMLP` 的板级硬件化
- 已完成 `4-lane PE` 阵列化版本 `v2.5`
- `v2.5` 已在板上恢复通过
- `v2.8` 已完成 batch e2e 修复与板级通过
- 当前可以把 `v2.5` 作为新的 PE 阵列基线，把 `v2.8` 作为新的 e2e 优化基线继续写论文和做后续优化

如果只记一句话，可以记成：

- **当前已经不是“固定模型硬件化试验”，而是已经收敛到一个可板测、可对比、可继续扩展的 `4-lane PE QMLP` 基线，并且开始拿到真实的 batch e2e 优化结果。**
