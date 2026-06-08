# QMLP 第一阶段结构重构约束

日期：2026-04-14  
目标文件：`fpga/src/main/scala/nexysvideo/RadarQMLP.scala`

## 1. 本轮允许做的事情

本轮只允许做第一阶段结构重构：

- 保持单模块实现，不优先引入新的子模块文件。
- 允许少量 helper function，用于输入解包、PE partial sum、寄存器 next-value 默认值等。
- 将分散式 `when(state === xxx)` 改为集中式 `switch(state)`。
- 将主要寄存器改为 next-value 风格，尽量保证单一写回点。
- 保持 `4-lane PE`、固定权重常量表、rowReg、requant 两级状态等原有行为。

## 2. 本轮禁止改变的事情

本轮不得改变：

- 模型结构：`21 -> 64 -> 32 -> 2`
- 权重来源：仍从当前 k7 release Scala 参数文件读取
- AXI-Stream 输入/输出协议
- MMIO 可见寄存器语义
- `runCycles` 统计口径
- `1301 cycles` kernel 行为预期
- golden 对拍口径
- Preproc/QMLP 串行数据通路
- 输出打包顺序：`Cat(logit1, logit0)`

## 3. ROM/RAM 使用判断

大量常用数据当然可以使用 ROM 或 RAM 存储，尤其是面向更规范的数字后端流程时，显式存储结构更容易做 memory planning、floorplan 和 macro integration。

但本轮不改变权重存储形态，原因是：

- 当前目标是行为保持型重构，不应同时改变架构和存储实现。
- 当前权重已经通过 `VecInit` 固化为常量表，并通过板级 golden 验证。
- 改成显式 ROM/BRAM/SyncReadMem 会引入读延迟、端口数、初始化方式和时序路径变化，可能改变 kernel cycle 或控制状态。
- 当前 `4-lane PE` 每周期需要并行消费 4 个权重，显式存储体需要考虑多端口或 banking，否则会影响吞吐。

因此：

```text
Stage 1: 保持当前固定权重 LUT/mux 常量表 + rowReg，专注代码结构。
Stage 2: 单独评估显式 ROM/BRAM/SRAM macro 权重存储。
```

## 4. 后续 ROM/RAM 方案候选

后续如要改权重存储，建议单独开分支和实验记录，候选包括：

| 方案 | 适用场景 | 风险 |
|---|---|---|
| LUT 常量表 | 小模型、固定权重、FPGA 快速原型 | 不适合大模型或 ASIC memory macro 交接 |
| 显式组合 ROM | 固定权重、希望 RTL 语义更像 ROM | 大表仍可能综合成 LUT/mux |
| SyncReadMem / BRAM ROM | FPGA 上较大权重表 | 同步读有 1-cycle latency，需要重排 FSM |
| 多 bank ROM | 保持 4-lane 并行读取 | 需要 banking 设计和地址规划 |
| SRAM/ROM macro wrapper | ASIC/数字后端更标准 | 需要 macro、初始化和时序约束配合 |

## 5. 本轮验证要求

本轮重构后至少需要：

- Chisel/Verilog 生成通过
- 生成 RTL 质量扫描
- 对比修改前后 `RadarQMLP.scala` 差异
- 尽可能跑软件侧 validation 构建
- 若后续生成 bitstream，则必须重新记录 timing/resource
- 板级测试仍以 `boundary_cases 54/54` 和 `large_golden 1000/1000` 为最终闭环

