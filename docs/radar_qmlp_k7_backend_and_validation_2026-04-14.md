# QMLP k7 硬件验证与后端检查说明

更新时间：2026-04-14

本文档用于把 `k=7 + rcs21` 版本 QMLP 的硬件状态、板级验证结果、权重物理形态和输出含义统一收口。  
它面向后续论文记录、师兄代码/后端检查，以及后续是否继续做 ASIC/数字后端规范化改造的讨论。

---

## 1. 当前版本结论

当前硬件已经切换到软件侧推荐的：

```text
k = 7
feature = rcs21
QMLP = 21 -> 64 -> 32 -> 2
INT8 activation / INT8 weight / INT32 logits
```

对应 release 目录：

```text
releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414
```

当前已经完成：

- `k7` 参数替换
- 重新生成 Verilog
- 重新生成 bitstream
- 板级功能验证
- `1000` 组大样本 golden 对拍
- `54` 组边界样本 golden 对拍

最终板测结论：

- `large_golden`: `1000 / 1000` 通过
- `boundary_cases`: `54 / 54` 通过
- 日志中出现：`AXI DMA qmlp validation PASSED`

---

## 2. 关键日志与报告入口

bitstream 与后端检查摘要：

- `/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/440-qmlp-k7-bitstream-and-backend-summary-2026-04-14.md`

板级验证摘要：

- `/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/443-qmlp-k7-validation-pass-summary-2026-04-14.md`

板级验证主日志：

- `/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/run-qmlp-validation-manual-2026-04-14-171045.log`

交付说明：

- `/home/soooarr/chipyard/docs/fixed_rcs_k7_hardware_handoff_2026-04-14.md`

---

## 3. 板级验证结果

本轮使用 `UART-TSI` 加载新的 validation ELF，并开启 `selfcheck`。

验证程序已经切到 `k7` 数据包：

- `large_golden/test_inputs_int8.h`
- `large_golden/test_logits_int32.h`
- `boundary_cases/boundary_inputs_int8.h`
- `boundary_cases/boundary_logits_int32.h`

板测结果：

```text
large_golden samples = 1000
large_golden hw_cycles_avg = 1301
large_golden e2e_cycles_avg = 1114779

boundary_cases samples = 54
boundary_cases hw_cycles_avg = 1301
boundary_cases e2e_cycles_avg = 8912855
```

按当前 `50 MHz` 主系统时钟换算：

```text
QMLP kernel latency = 1301 / 50 MHz ≈ 26.02 us
large_golden batch 平均每样本 e2e ≈ 22.30 ms
boundary_cases 单样本式 e2e ≈ 178.26 ms
```

说明：

- `large_golden` 采用 batch 路径，因此平均每样本 e2e 明显低于单样本式测试。
- `boundary_cases` 当前按单样本方式跑，主要用于鲁棒性和极端输入验证，不用于展示最高 e2e 性能。

---

## 4. 生成 RTL 质量

当前生成的 QMLP RTL：

```text
fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/gen-collateral/RadarAXISQMLP.sv
```

检查结果：

- 文件约 `1666` 行
- 无 `while`
- 无 `generate / genvar`
- 无 `$display / $finish / $readmem`
- 功能路径中没有动态软件式循环

唯一看到的 `for` 位于 FIRRTL/CIRCT 自动生成的随机初始化辅助块：

```systemverilog
initial begin
  `ifdef RANDOMIZE_REG_INIT
    for (...) begin
      _RANDOM[i] = `RANDOM;
    end
  ...
end
```

该 `for` 不属于 QMLP 推理计算 datapath，也不是运行时硬件循环控制器。  
从综合结果看，当前 RTL 已经通过 Vivado 综合、实现和 bitstream 生成。

---

## 5. QMLP 权重的物理形态

这一点对后续数字后端检查很重要。

当前 QMLP 权重不是运行时从 DDR 动态装载，也不是单独显式建模成 SRAM/BRAM 宏。  
当前实现方式是：

1. `RadarQMLP.scala` 在 elaboration 阶段读取 release 中的 Scala 参数文件。
2. 权重和 bias 通过 `VecInit(...)` 固化为 Chisel 常量表。
3. 生成 SystemVerilog 后，这些权重成为固定常量逻辑。
4. 运行时状态机按层、按行把当前输出神经元的一行权重装入 row register。
5. `4-lane PE` 使用 row register 与输入向量进行乘加。

对应源码位置：

```text
RadarQMLP.scala
  l1Biases / l2Biases / l3Biases
  l1Rows / l2Rows / l3Rows
  l1RowReg / l2RowReg / l3RowReg
```

### 5.1 它是 ROM 还是 LUT？

从功能上看，它相当于一个**固定只读权重表**。

但从当前 FPGA 物理实现看，更准确的说法是：

```text
权重 = 固化常量网络 / LUT fabric 中的常量与选择逻辑
行缓存 = FF 寄存器
```

当前 `RadarAXISQMLP` 层级资源中：

- `BRAM = 0`
- `DSP = 0`
- 主要资源是 `LUT + FF`

因此不建议把当前实现直接说成“权重存储在 BRAM ROM 中”。  
更准确的论文/汇报表述是：

> QMLP 权重在硬件生成阶段固化为常量表，由综合工具映射到 FPGA LUT 逻辑资源中；推理时按层按行加载到寄存器组参与 PE 乘加。该方式等价于固定只读权重存储，但当前不是显式 BRAM/ROM macro 实现。

### 5.2 对数字后端流程的影响

如果后端检查重点是：

- RTL 是否可综合
- 是否存在不可综合行为级语句
- 是否存在运行时动态循环
- 时序是否可收敛

当前实现是合格的。

如果后端检查重点是 ASIC/macro 级工程化，例如：

- 权重是否单独落成 ROM macro
- 是否便于 memory planning
- 是否便于 floorplan 中固定 memory block
- 是否支持后期替换权重

那么当前实现还不是最终最规范的 memory-macro 风格。  
后续如果要面向 ASIC 或更严格数字后端交付，可以考虑把 `l1Rows/l2Rows/l3Rows` 显式改造成：

- synchronous ROM
- distributed ROM
- SRAM/ROM macro wrapper
- 或者可由软件/启动流程写入的 weight SRAM

但在当前 FPGA 原型阶段，固化常量表方案是合理的，因为它：

- 结构简单
- 不需要权重加载协议
- 固定模型验证效率高
- 已经完成板级功能验证

---

## 6. 最后 2 维输出代表什么

当前 QMLP 的最终输出是：

```text
logits_int32[2]
```

这两个值不是概率，也不是 softmax 之后的浮点值，而是最后一层 `L3` 的 `INT32 accumulator logits`。

类别顺序来自 `k7` 交付包：

```text
logits[0] -> class 0 -> pedestrian
logits[1] -> class 1 -> vehicle
```

最终类别判断方式：

```text
pred = argmax(logits[0], logits[1])
```

也就是说：

- 如果 `logits[0] > logits[1]`，预测为 `pedestrian`
- 如果 `logits[1] > logits[0]`，预测为 `vehicle`

硬件侧当前只负责输出两个 `INT32 logits`。  
是否做 `argmax`、是否转换成概率，可以交给 CPU 或软件后处理完成。

论文中建议这样写：

> QMLP 加速器输出最终两类分类得分 `INT32 logits[2]`，分别对应 `pedestrian` 与 `vehicle` 两个类别。硬件模块不执行 softmax，仅输出定点累加结果；CPU 侧通过比较两个 logits 的大小得到最终分类结果。

---

## 7. 当前阶段建议结论

当前 `k7 + rcs21` 版本可以作为新的硬件基线，原因是：

- 软件侧推荐模型已替换进硬件
- 结构仍保持 `21 -> 64 -> 32 -> 2`
- `4-lane PE` 不需要改变
- bitstream 已生成并通过时序
- `1000` 组真实样本和 `54` 组边界样本均完成板级 golden 对拍
- 权重当前以固定常量表形式映射到 LUT/寄存器结构，适合 FPGA 原型验证

后续如果论文或师兄更关注“数字后端规范性”，建议单独增加一节说明：

- 当前是 FPGA 原型中的固定权重常量表实现
- 后续 ASIC/backend 化时可演进为显式 ROM/SRAM macro
- 当前结果主要证明算法功能、数据通路和系统集成可行
