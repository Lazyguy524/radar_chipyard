# QMLP 第一阶段结构重构结果记录

日期：2026-04-14  
目标文件：`fpga/src/main/scala/nexysvideo/RadarQMLP.scala`  
阶段目标：只做代码结构重构，不改变功能、协议、计数口径、权重来源和 golden 行为。

## 1. 本轮结论

本轮完成了 `RadarAXISQMLP` 的第一阶段单模块结构重构：

- 保持单一 `RadarAXISQMLP` 模块，没有新增子模块文件。
- 将原先分散的 `when(state === ...)` 状态块整理为一个集中式 `switch(state)` FSM。
- 将主要标量寄存器改为 `next-value` 风格，并在 FSM 后集中写回。
- 将输入 beat 解包抽成 `writeInputBeat` helper，减少接收路径重复代码。
- 保留当前固定权重 `VecInit` 常量表、rowReg、4-lane PE、AXI-Stream 协议和 MMIO 计数器口径。

当前评定：

```text
源码结构：第一阶段合格
Verilog 生成：通过
软件 ELF 构建：通过
板级 golden：本轮未重新跑，需要后续烧录后闭环
数字后端最终形态：仍建议第二阶段继续优化
```

## 2. 修改前后备份

修改前备份：

- `logs/radar_nexysvideo/code_backups/447-RadarQMLP-before-stage1-structure-refactor-2026-04-14.scala`
- `logs/radar_nexysvideo/runtime/448-pre-qmlp-stage1-refactor-status-2026-04-14.txt`
- `logs/radar_nexysvideo/runtime/449-pre-qmlp-stage1-refactor-RadarQMLP-diff-2026-04-14.patch`
- `logs/radar_nexysvideo/runtime/450-pre-qmlp-stage1-refactor-RadarQMLP-sha256-2026-04-14.txt`

修改后备份：

- `logs/radar_nexysvideo/code_backups/464-RadarQMLP-after-stage1-structure-refactor-2026-04-14.scala`
- `logs/radar_nexysvideo/runtime/465-qmlp-stage1-refactor-before-after-sha256-2026-04-14.txt`
- `logs/radar_nexysvideo/runtime/466-qmlp-stage1-refactor-final-tracked-diff-2026-04-14.patch`
- `logs/radar_nexysvideo/runtime/467-qmlp-stage1-refactor-post-status-2026-04-14.txt`

与本轮修改前备份的直接差异：

- `logs/radar_nexysvideo/runtime/460-qmlp-stage1-refactor-against-backup-2026-04-14.patch`

## 3. 具体结构变化

本轮实际改动集中在控制结构，不改变 QMLP 算法数据路径：

- `state` 不再在多个分散 `when` 块中直接跳转，而是通过 `nextState` 在集中 FSM 后统一写回。
- `recvBeatCount / outIdx / inIdx / accReg / quantProductReg / quantRoundedReg / outValidReg / counters / last logits` 使用 `WireDefault` 形式的 next-value。
- `inputVec / l1RowReg / l2RowReg / l3RowReg / l1OutVec / l2OutVec / logitsVec / outBitsReg` 仍采用集中状态内写端口，避免为大 Vec 建完整 nextVec 导致 RTL 进一步膨胀。
- `writeInputBeat` 统一处理 64-bit AXI-Stream beat 到 21 维 INT8 输入向量的解包。

这次没有改变：

- 模型结构：`21 -> 64 -> 32 -> 2`
- PE lane 数：`4`
- 输入 beat 宽度：`64-bit data + 8-bit keep + last`
- 输出格式：`Cat(logit1, logit0)`，`keep = 0xff`
- L1/L2 requant 口径
- `runCycles` 统计位置和优先级
- 权重 release 文件来源

## 4. 验证记录

Verilog 生成：

- 日志：`logs/radar_nexysvideo/runtime/456-qmlp-stage1-refactor-v2-verilog-2026-04-14.log`
- 结果：`make -C fpga SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideoConfig verilog` 退出码为 0。
- 备注：日志中仍出现历史已有的 `cp: missing destination ... Error 1 (ignored)`，make 最终成功。

源码质量扫描：

- 日志：`logs/radar_nexysvideo/runtime/461-qmlp-stage1-refactor-source-quality-scan-2026-04-14.txt`
- `switch(state)` 数量：`1`
- `when(state === ...)` 数量：`0`
- `state := nextState` 数量：`1`
- `next-value` 标量 wire 数量：`16`

生成 RTL 扫描：

- 日志：`logs/radar_nexysvideo/runtime/459-qmlp-stage1-refactor-v2-rtl-quality-scan-2026-04-14.txt`
- `RadarAXISQMLP.sv` 行数：`2298`
- `while`：`0`
- `$display/$finish/$readmem`：`0`
- `module` 数量：`1`
- `always` block：`2`
- `for`：`4`，主要来自工具生成结构或初始化相关展开，不是运行时动态循环语义。

软件 ELF 构建：

- 日志：`logs/radar_nexysvideo/runtime/463-qmlp-stage1-refactor-qmlp-elf-builds-2026-04-14.log`
- 结果：`radar-axi-dma-qmlp.riscv`、`radar-axi-dma-qmlp-e2e.riscv`、`radar-axi-dma-qmlp-validation.riscv`、`radar-qmlp-cpu-only.riscv` 均可构建，当前为 up-to-date。

## 5. 关于 ROM/RAM 的判断

大量常用数据可以使用 ROM 或 RAM，尤其是面向更标准的数字后端流程时，显式存储结构更容易说明：

- 权重在哪里存储
- 读地址如何产生
- 端口数如何满足 PE 并行读取
- 后续 ASIC memory macro 或 FPGA BRAM 如何替换

但本轮没有把权重改成显式 ROM/RAM，原因是本轮约束是行为保持型结构重构。当前权重仍然是：

```text
release Scala 参数文件 -> Chisel elaboration 读取 -> VecInit 固定常量表 -> 综合为 LUT/mux 常量网络 -> Load 状态装入 rowReg -> MAC 阶段由 PE 消费 rowReg
```

如果改成 `SyncReadMem` 或 BRAM ROM，会引入同步读延迟和端口约束。当前 4-lane PE 每周期要消费 4 个权重，显式 ROM 需要 multi-bank 或宽 word 读出，否则会改变 kernel cycle 和 FSM 行为。

因此建议：

```text
Stage 1: 保持 VecInit 固定权重表，先把控制结构整理清楚。
Stage 2: 单独设计 FixedWeightBank，可选择组合 ROM、多 bank SyncReadMem、BRAM ROM 或 ASIC ROM/SRAM wrapper。
```

## 6. 仍需注意的问题

源码层面已经比修改前更适合维护和验证，但生成的 SystemVerilog 仍然不是最终最理想的后端形态：

- FIRRTL/CIRCT 会把 Chisel 的集中 FSM 和寄存器 enable 降低成较多 `if/else` 条件。
- 当前生成 SV 有 `495` 行 if-like 结构，说明它仍偏向自动生成 RTL，而不是手写风格 RTL。
- 这不代表不可综合，也不代表功能错误；但如果师兄关注“后端交付可读性”，第二阶段应继续推进显式模块边界和权重 bank。

本轮暂不做以下事情：

- 不跑 bitstream
- 不改变频率或时序约束
- 不改变权重存储物理形态
- 不改变 `runCycles = 1301 cycles` 预期
- 不重新跑板级 `boundary_cases / large_golden`

## 7. 下一步建议

如果继续追求更标准的硬件交付形态，建议下一阶段按如下顺序推进：

1. 保留当前版本作为行为基线。
2. 先跑一次板级 k7 boundary/large golden，确认本轮结构重构无行为偏差。
3. 设计 `FixedWeightBank`，但先保持单文件实现，显式描述权重表、行选择和 rowReg 装载。
4. 再评估是否用 multi-bank ROM/BRAM 替代 LUT 常量表。
5. 若引入同步 ROM，必须重新定义 `Load` 状态读延迟，并重新记录 kernel cycles、WNS、资源和 golden。

短结论：

> 本轮重构完成了第一阶段“源码工程化整理”，适合作为继续优化的干净起点；但如果目标是更接近数字后端可交付 RTL，还需要第二阶段专门做权重存储 bank 化和模块边界整理。
