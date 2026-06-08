# Radar QMLP Chisel 重构方案与代码质量门禁

日期：2026-04-14  
适用文件：`fpga/src/main/scala/nexysvideo/RadarQMLP.scala`  
当前目标：先确定重构方案，不直接改功能实现。

本文档固化后续 `RadarAXISQMLP` 的工程化重构要求。后续任何 QMLP Chisel 实现都应优先保证：

- 状态机集中、可读、可验证
- 寄存器赋值来源清晰
- 控制通路与数据通路分离
- 生成 SystemVerilog 可综合、结构明确、便于时序分析
- 不接受“靠堆分散 when、补丁式跳转、多个地方覆盖同一个寄存器”的实现

---

## 1. 修改前备份

本轮在写入该规范文档前已经保存当前工作区状态：

- 状态快照：
  - `/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/444-pre-qmlp-refactor-guideline-status-2026-04-14.txt`
- tracked diff 备份：
  - `/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/445-pre-qmlp-refactor-guideline-tracked-diff-2026-04-14.patch`
- 原 RTL 编码规范快照：
  - `/home/soooarr/chipyard/logs/radar_nexysvideo/code_backups/446-radar_nexysvideo_rtl_coding_guidelines-before-qmlp-refactor-2026-04-14.md`

后续真正改 `RadarQMLP.scala` 前，还必须重新做一次同类备份。

---

## 2. 重构总体方案

建议分两阶段推进，避免一次性大改导致功能和时序同时失控。

### 2.1 第一阶段：行为保持型重构

目标：

- 不改变模型结构
- 不改变权重来源
- 不改变 AXI-Stream input/output 协议
- 不改变 `runCycles` 统计口径
- 不改变当前 `1301 cycles` kernel 行为，除非明确记录原因
- 不改变权重存储形态；本阶段仍保持当前固定权重 `VecInit` 常量表 + rowReg 工作方式

主要动作：

1. 将分散的 `when(state === xxx)` 改成集中式 `switch(state) { is(...) { ... } }`。
2. 将主要寄存器改成 `next-value` 风格。
3. 将输入解包、PE MAC、requant/clamp、输出打包拆成 helper 或子模块。
4. 保留当前 `4-lane PE`、固定权重 LUT/mux、rowReg 工作方式。
5. 完成软件 golden 对拍、板级 boundary/large golden 验证后再进入下一阶段。

本阶段的详细约束记录在：

- [stage1_structure_refactor_constraints_2026-04-14.md](/home/soooarr/chipyard/docs/qmlp_refactor/stage1_structure_refactor_constraints_2026-04-14.md)

### 2.2 第二阶段：模块化增强

目标：

- 把 QMLP 从“大 Module”拆成更明确的子模块边界。
- 为后续时序优化、显式 ROM/SRAM 权重存储、更多 PE lane 或流水线扩展留接口。

可选动作：

1. 将固定权重访问封装为 `FixedWeightBank` 风格模块或 helper。
2. 将 `4-lane PE` 做成独立可测模块。
3. 将 requant pipeline 独立出来，便于插入额外寄存器。
4. 将 AXI-Stream sample unpack / output pack 与 QMLP core 分离。
5. 单独评估显式 ROM/BRAM/SRAM macro 权重存储，不能和第一阶段结构重构混在同一次提交中。

---

## 3. 模块划分建议

### 3.1 顶层包装：`RadarAXISQMLP`

职责：

- 保持现有 IO 不变
- 连接 AXI-Stream 输入输出
- 暴露计数器、状态、last logits、capabilities
- 实例化 core / unpacker / packer

不应承担：

- 大量层内 MAC 细节
- 大块权重选择逻辑
- 复杂 requant 细节

### 3.2 输入解包：`QMLPSampleUnpacker`

职责：

- 接收 `RadarAXISWord`，即 `64-bit data + 8-bit keep + last`
- 将每个样本解包为 `inputVec[21]`
- 维护 `recvBeatCount`
- 处理 batch 中样本边界与 `last`
- 输出 `sampleValid` / `sampleLast`

建议接口：

```text
in:  Decoupled[RadarAXISWord]
out: Valid[SampleBundle]
```

其中 `SampleBundle` 包含：

- `features: Vec(21, SInt(8.W))`
- `last: Bool`

### 3.3 固定权重表：`FixedQMLPWeights`

职责：

- 明确区分固定常量表和当前工作行寄存器
- 封装 `l1Rows / l2Rows / l3Rows`
- 提供按层、按 `outIdx` 选择一行权重的接口或 helper

说明：

- 当前仍可用 `VecInit` 常量表
- 但状态机里不应直接混入大块权重构造逻辑
- 后续若改显式 ROM/BRAM，只替换该层

### 3.4 行寄存器：`WeightRowRegs`

职责：

- 保存当前神经元的一行权重
- L1: 21 个 INT8
- L2: 64 个 INT8
- L3: 32 个 INT8

建议：

- 行装载只在 `Load` 状态发生
- MAC 阶段只消费 rowReg
- 不在 MAC 逻辑中直接访问大权重表

### 3.5 PE/MAC：`PEMac4`

职责：

- 输入：
  - 当前激活向量
  - 当前权重行
  - `inIdx`
  - `inputDim`
- 输出：
  - 4 lane partial sum
  - `tileDone`

每周期计算：

```text
lane0: input[inIdx + 0] * weight[inIdx + 0]
lane1: input[inIdx + 1] * weight[inIdx + 1]
lane2: input[inIdx + 2] * weight[inIdx + 2]
lane3: input[inIdx + 3] * weight[inIdx + 3]
```

要求：

- lane 数定义为常量 `PeLanes = 4`
- 不硬编码散落的 `4`
- index width 统一定义

### 3.6 Requant/Clamp：`RequantClamp`

职责：

- `INT32 acc -> multiplier -> bankers rounding -> ReLU -> clamp[0,127]`
- 保持当前 `L1/L2` 对齐口径
- 允许保留当前两级 pipeline：
  - `QuantMul`
  - `QuantRound`

要求：

- 不把 requant 乘法、round、clamp 全写在状态机里
- 量化规则必须和软件 handoff 文档一致

### 3.7 输出打包：`QMLPOutputPacker`

职责：

- 将 `lastLogit0 / lastLogit1` 打包成 64-bit AXI-Stream word
- 输出：

```text
data = Cat(logit1, logit0)
keep = 0xff
last = sampleLast
```

---

## 4. 状态机重写方案

### 4.1 推荐状态

保留当前语义，但集中管理：

```text
Idle
Recv
L1Load
L1Mac
L1QuantMul
L1QuantRound
L1Write
L2Load
L2Mac
L2QuantMul
L2QuantRound
L2Write
L3Load
L3Mac
L3Write
L3Pack
Emit
```

### 4.2 集中式 FSM 模板

后续实现应采用如下结构：

```scala
val nextState = WireDefault(state)
val nextOutIdx = WireDefault(outIdx)
val nextInIdx = WireDefault(inIdx)
val nextAcc = WireDefault(accReg)

// 其他 next-value 默认值

switch (state) {
  is (sIdle) {
    // 只处理 Idle 行为
  }

  is (sRecv) {
    // 只处理输入接收
  }

  is (sL1Load) {
    // 装载 L1 当前行
  }

  is (sL1Mac) {
    // L1 MAC 与 inIdx 推进
  }

  // ...
}

state := nextState
outIdx := nextOutIdx
inIdx := nextInIdx
accReg := nextAcc
```

禁止：

```scala
when (state === sA) { state := sB }
when (state === sC) { state := sD }
when (io.out.fire) { state := sIdle }
```

这种多处覆盖 `state` 的写法。

### 4.3 状态职责

| 状态 | 单一职责 |
|---|---|
| `Idle` | 等待 enable 与输入首拍，清理样本接收局部状态 |
| `Recv` | 接收 64-bit AXIS beat，写入 inputVec |
| `LxLoad` | 根据 `outIdx` 装载当前层一行权重与 bias |
| `LxMac` | 使用 `PEMac4` 计算 partial sum，推进 `inIdx` |
| `LxQuantMul` | 执行 requant multiplier 乘法或 shift-add |
| `LxQuantRound` | bankers rounding |
| `LxWrite` | 写入 `l1OutVec/l2OutVec` 并推进 `outIdx` |
| `L3Write` | 保存 final logits |
| `L3Pack` | 打包输出 word |
| `Emit` | 等待 `io.out.fire` |

---

## 5. 需要改成 next-value 风格的寄存器

以下寄存器后续必须优先改成 next-value 风格：

| 寄存器 | 说明 | next-value 名称建议 |
|---|---|---|
| `state` | FSM 当前状态 | `nextState` |
| `outIdx` | 当前输出神经元/行编号 | `nextOutIdx` |
| `inIdx` | 当前行内输入维度编号 | `nextInIdx` |
| `accReg` | INT32 累加器 | `nextAcc` |
| `quantProductReg` | requant 中间乘积 | `nextQuantProduct` |
| `quantRoundedReg` | requant rounding 结果 | `nextQuantRounded` |
| `outValidReg` | 输出 valid | `nextOutValid` |
| `outBitsReg` | 输出 AXIS word | `nextOutBits` |
| `recvBeatCount` | 当前样本接收 beat 计数 | `nextRecvBeatCount` |
| `sampleLastReg` | 当前样本是否 frame last | `nextSampleLast` |
| `inputVec` | 当前样本 21 维输入 | `nextInputVec` 或由 unpacker 独立管理 |
| `l1OutVec` | L1 激活缓存 | `nextL1OutVec` 或集中写端口 |
| `l2OutVec` | L2 激活缓存 | `nextL2OutVec` 或集中写端口 |
| `logitsVec` | L3 logits 缓存 | `nextLogitsVec` 或集中写端口 |
| `lastLogit0Reg` | 调试/状态寄存器 | `nextLastLogit0` |
| `lastLogit1Reg` | 调试/状态寄存器 | `nextLastLogit1` |
| `inBeatsReg` | 输入 beat 计数器 | `nextInBeats` |
| `outBeatsReg` | 输出 beat 计数器 | `nextOutBeats` |
| `framesReg` | frame 计数器 | `nextFrames` |
| `lastKeepReg` | 最近一次 keep | `nextLastKeep` |
| `runCyclesReg` | kernel cycle 计数 | `nextRunCycles` |

说明：

- 对 `Vec` 类寄存器，允许采用集中写端口风格，而不是每个元素都建完整 `nextVec`。
- 但每个 `Vec` 的写入位置必须集中、可追踪。
- `clearCounters` 的优先级应在计数器 next-value 逻辑中统一处理，不要散落覆盖。

---

## 6. 常量、权重和 rowReg 规范

必须明确区分：

| 类型 | 当前物理/逻辑含义 | 允许出现位置 |
|---|---|---|
| 固定常量表 | elaboration 后固定，综合为 LUT/mux | 权重 helper / weight bank |
| 当前工作行寄存器 | 本轮输出神经元的权重行 | row loader / core datapath |
| PE 消费路径 | `inputVec/l1OutVec/l2OutVec` 与 rowReg | PE/MAC 模块 |

禁止：

- 在状态机里到处直接访问 `l1Rows(outIdx)(i)`。
- 在 MAC 计算路径里直接读取大权重表。
- 把权重常量构造和状态跳转混写。

推荐：

```text
LxLoad:
  selectedRow = weightBank.readRow(layer, outIdx)
  rowReg := selectedRow

LxMac:
  pe.io.activations := currentActivationVec
  pe.io.weights := rowReg
  pe.io.baseIdx := inIdx
  nextAcc := accReg + pe.io.partialSum
```

---

## 7. 验证门禁

后续重构后的实现必须至少通过：

1. Chisel elaboration / Verilog 生成通过。
2. 生成 RTL 质量扫描：
   - 无功能路径 `while`
   - 无 `$readmem / $display / $finish`
   - 无运行时动态循环语义
   - `for` 只能出现在工具随机初始化或固定生成语义中
3. 软件 golden 对拍：
   - 单样本 hardware golden
   - boundary cases
   - large golden
4. 板级验证：
   - `boundary_cases 54/54`
   - `large_golden 1000/1000`
5. 性能回归：
   - kernel cycles 不应无说明地劣化
   - 当前参考值为 `1301 cycles`
6. 时序回归：
   - `50 MHz DUT` 主域 WNS 必须保持正余量
7. 资源回归：
   - 重点记录 `RadarAXISQMLP` LUT / FF / DSP / BRAM

---

## 8. 不合格实现判定

以下情况直接判定为不合格，不应提交：

- 多个独立 `when` 块反复给同一个寄存器赋值。
- `state` 在状态机外被多个补丁式条件覆盖。
- 为修一个 bug 添加额外跳转，但不重新整理状态职责。
- 控制通路和 MAC 数据通路混在一个大段逻辑里。
- 权重访问、rowReg 装载、MAC 计算三者混杂。
- 生成的 SV 主要表现为大量难以追踪的 `if / else if` 优先级链。
- 为了“先跑起来”牺牲可读性、可维护性和验证边界。

---

## 9. 推荐执行顺序

后续如果确认开始重构，建议按以下步骤执行：

1. 再次备份当前工作区状态与 `RadarQMLP.scala`。
2. 先只重构 FSM 为集中式 `switch(state)`，不拆模块。
3. 跑 Scala/Verilog 生成和小规模 golden。
4. 再拆 `PEMac4` 与 requant helper。
5. 再拆 sample unpacker / output packer。
6. 每拆一层都跑一次功能回归。
7. 最后跑 bitstream、板级 boundary、large golden。

---

## 10. 给后续实现者的短结论

> QMLP 后续实现必须按集中式 FSM、next-value 寄存器更新、控制/数据通路分离、固定权重表/rowReg/PE 消费路径分层的工程风格重构。任何靠分散 when、状态补丁、多处覆盖寄存器临时跑通的写法均视为不合格。
