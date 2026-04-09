# QMLP 阵列化原型阶段说明

更新时间：2026-04-06

## 1. 目标

在当前已经板测通过的固定 `21 -> 64 -> 32 -> 2 INT8 QMLP` 基线之上，进一步验证“论文主线转向 PE/MAC 阵列”是否可行。  
本轮不改动 SoC 外围接口，不改动软件测试入口，只对 `RadarAXISQMLP` 内核做阵列化重构。

本轮实现分支：

- `radar-qmlp-pe-array-v1`

## 2. 选择这条路线的原因

当前基线已经证明：

- `DDR -> MM2S -> RadarAXISQMLP -> S2MM -> DDR` 链路可用
- 固定 QMLP 多样本对拍通过
- 当前硬件本体平均计算周期约为 `3554 cycles`

但当前 `QMLP` 内核本质上仍是“串行逐 MAC”实现，虽然能跑通，但不适合作为后续论文的主要创新点。  
结合调研报告 [radar_nn_accel_dataflow_research_report_2026-04-06.md](/home/soooarr/chipyard/docs/radar_nn_accel_dataflow_research_report_2026-04-06.md)，最适合本项目继续推进的路线是：

- 先做一个小型、规则、易验证的 `PE/MAC` 阵列原型
- 后续再扩展到 batching、buffer、dataflow 优化

## 3. 本轮硬件改动

核心文件：

- [RadarQMLP.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarQMLP.scala)

### 3.1 原始版本

原始版本采用逐输出、逐输入的串行累加方式：

- `L1`: `64 x 21` 次 MAC 串行执行
- `L2`: `32 x 64` 次 MAC 串行执行
- `L3`: `2 x 32` 次 MAC 串行执行

这一实现方式的优点是：

- 结构简单
- 对拍容易
- 首版 bring-up 风险低

缺点是：

- 不能体现阵列化硬件设计工作量
- 算子本体的周期较长
- 不利于后续论文扩展到更一般的 FC/GEMV/GEMM 内核

### 3.2 新增阵列化结构

本轮将内核重构为 **4 路并行 PE/MAC 累加**：

- `peLanes = 4`
- 每个周期并行处理 4 组 `data * weight`
- 再将 4 路乘积做加法归约，累加到当前输出神经元的 `accReg`

本轮仍保持：

- layer 顺序不变
- `INT8 -> INT32 accumulate -> requant -> ReLU -> INT8`
- AXI-Stream 接口不变
- 输出 packet 格式不变
- CSR / 软件测试接口不变

因此，这是一版**内核级阵列化**，而不是一次 SoC 级大改。

## 4. 预期周期变化

按当前固定层尺寸估算：

- `L1`: `64 * ceil(21 / 4) = 384 cycles`
- `L2`: `32 * ceil(64 / 4) = 512 cycles`
- `L3`: `2 * ceil(32 / 4) = 16 cycles`

仅计算层主体的理论 MAC 周期约为：

- `384 + 512 + 16 = 912 cycles`

相比原串行实现的 `3456` 次逐 MAC 累计，理论上约有 `3.8x` 左右的主体计算周期下降空间。  
最终硬件 `runCycles` 还需要等板级实测确认。

## 5. 与论文工作的关系

这版原型的价值不在于“直接替代最终 accelerator”，而在于提供一个过渡基线：

1. 从“固定功能硬编码 QMLP”过渡到“可解释的 PE/MAC 阵列结构”
2. 保留现有 `DMA + AXIS + DDR` 数据通路，降低验证风险
3. 为后续三类论文内容做铺垫：

- `PE 阵列规模扩展`
- `多样本 batching / dataflow 优化`
- `结构化稀疏或权重缓存优化`

## 6. 当前验证状态

截至本说明更新时：

- 软件侧构建入口保持可用
- `Nexys Video` 定向 `verilog` 生成已通过
- bitstream 正在后台构建

对应日志：

- 软件构建：
  [244-build-qmlp-pe-array-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/244-build-qmlp-pe-array-2026-04-06.log)
- RTL 生成：
  [245-fpga-verilog-qmlp-pe-array-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/245-fpga-verilog-qmlp-pe-array-2026-04-06.log)
- bitstream：
  [246-fpga-bitstream-qmlp-pe-array-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/246-fpga-bitstream-qmlp-pe-array-2026-04-06.log)

## 7. 下一步

如果 bitstream 收敛并通过板测，后续建议按这个顺序继续推进：

1. 测量新版本 `QMLP_RUN_CYCLES`
2. 与原 `3554 cycles` 做对比
3. 保持功能不变，加入多样本连续流
4. 再评估：
   - 样本 batching
   - 片上 buffer / ping-pong
   - 权重常驻或分层缓存

这一顺序更适合论文写作，因为每一步都能形成清晰的前后对比实验。
