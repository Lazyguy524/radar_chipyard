# Radar QMLP 结构化重构结果：Word-Bank 激活缓存 + 显式 Logit0

日期：2026-04-15  
目标文件：`fpga/src/main/scala/nexysvideo/RadarQMLP.scala`  
本轮目标：继续优化 ROM 重构版，重点减少大宽度 packed byte 替换、去掉动态 logits Vec 写回，并梳理 ROM 读到 MAC 的路径。

## 1. 本轮结论

本轮最终采用 `64-bit word-bank` 方案，而不是 byte-level Vec 方案。

中间尝试过 `Vec[SInt(8.W)]` 字节级寄存器方案，源码更直观，但生成 RTL 反而变差：

| 方案 | RTL 行数 | if/else 类行数 | 结论 |
|---|---:|---:|---|
| ROM + full-packed baseline | 682 | 90 | 上一轮基线 |
| byte-level Vec 中间方案 | 2007 | 468 | 放弃，RTL 展开过大 |
| word-bank 最终方案 | 672 | 92 | 采用，结构更清晰，资源更低 |

最终方案把激活缓存改成 64-bit word bank：

- `inputWords`: 4 x 64-bit
- `l1OutWords`: 8 x 64-bit
- `l2OutWords`: 4 x 64-bit

这样仍然保留字节可寻址能力，但字节替换只发生在局部 64-bit word 内，不再对一个 168/512/256-bit 大 packed UInt 反复做 shift/mask/or。

## 2. 对 3 个关注点的处理

### 2.1 减少 packed bit 替换逻辑

已移除旧路径：

- `inputPacked`
- `l1OutPacked`
- `l2OutPacked`
- `replacePackedByte`
- `getPackedS8`

新增 word-bank helper：

- `replaceWordByte`: 只替换 64-bit word 内一个 byte
- `mergeAxisWord`: 根据 AXIS `keep` 合并一个 64-bit 输入 beat
- `writeWordBank`: 对少量 64-bit word 做集中写口选择
- `readS8WordBank`: 从 word-bank 中读取一个 INT8 activation
- `writeS8WordBank`: 将 L1/L2 量化输出写回 word-bank

### 2.2 输出 logits 写法更干净

已移除：

- `logitsVec`
- `nextLogitsVec(outIdx(0)) := accReg`

当前采用：

- `pendingLogit0Reg` 暂存第 0 维 logit
- 第二维 logit 计算完成时直接写入 `lastLogit1Reg`
- `lastLogit0Reg` 从 `pendingLogit0Reg` 更新

因此 L3 输出路径不再依赖动态 Vec 写回。

### 2.3 ROM 读路径和 MAC 衔接

当前路径保持异步 ROM 语义：

```text
outIdx + inIdx -> ROM address -> 32-bit weight word -> 4 lane weight -> MAC partial sum
```

每个 32-bit weight word 对应 4 个 INT8 权重，与 4-lane PE 一一对应：

```text
lane0 = word[7:0]
lane1 = word[15:8]
lane2 = word[23:16]
lane3 = word[31:24]
```

`Load` 状态只负责清 `inIdx` 并装载 bias；`MAC` 状态直接消费当前 `inIdx` 对应的 ROM weight word。这比早期 rowReg 整行装载更清楚，也减少了“权重表 -> rowReg -> PE”的中间层。

## 3. RTL 与 OOC 结果

关键扫描：

| 项目 | 结果 |
|---|---:|
| `RadarAXISQMLP.sv` 行数 | 672 |
| `always` block | 2 |
| `if/else if` 行数 | 92 |
| `while` | 0 |
| old packed 相关 RTL | 0 |
| byte Vec 相关 RTL | 0 |
| `logitsVec` 相关 RTL | 0 |
| ROM blackbox 文件 | 6 |
| ROM 实例 | 6 |

OOC synth：

| 项目 | 结果 |
|---|---:|
| Synthesis errors | 0 |
| Critical warnings | 0 |
| Slice LUTs | 3528 |
| Slice Registers | 1493 |
| BRAM Tile | 0 |
| DSP | 0 |
| 20 ns clock OOC WNS | 0.711 ns |

相对上一轮 ROM + full-packed baseline：

- LUT: `3870 -> 3528`，减少 342
- FF: `1410 -> 1493`，增加 83
- WNS: `0.709 ns -> 0.711 ns`，基本持平
- RTL 行数: `682 -> 672`

## 4. 验证与留档

- 修改前备份：`logs/radar_nexysvideo/code_backups/518-RadarQMLP-before-bytevec-logit-refactor-2026-04-15.scala`
- byte-level 中间方案 Verilog：`logs/radar_nexysvideo/runtime/522-qmlp-bytevec-logit-refactor-verilog-2026-04-15.log`
- byte-level 中间方案 RTL 扫描：`logs/radar_nexysvideo/runtime/523-qmlp-bytevec-logit-refactor-rtl-scan-2026-04-15.txt`
- word-bank Verilog：`logs/radar_nexysvideo/runtime/525-qmlp-wordbank-logit-refactor-verilog-2026-04-15.log`
- word-bank RTL 扫描：`logs/radar_nexysvideo/runtime/526-qmlp-wordbank-logit-refactor-rtl-scan-2026-04-15.txt`
- word-bank 源码扫描：`logs/radar_nexysvideo/runtime/527-qmlp-wordbank-logit-refactor-source-scan-2026-04-15.txt`
- word-bank Vivado 语法检查：`logs/radar_nexysvideo/runtime/528-qmlp-wordbank-logit-refactor-xvlog-2026-04-15.log`
- word-bank OOC synth：`logs/radar_nexysvideo/runtime/529-qmlp-wordbank-logit-refactor-ooc-synth-2026-04-15.log`
- word-bank OOC utilization：`logs/radar_nexysvideo/runtime/530-qmlp-wordbank-logit-refactor-ooc-util-2026-04-15.rpt`
- word-bank OOC timing：`logs/radar_nexysvideo/runtime/531-qmlp-wordbank-logit-refactor-ooc-timing-2026-04-15.rpt`
- ELF 构建检查：`logs/radar_nexysvideo/runtime/532-qmlp-wordbank-logit-refactor-elf-builds-2026-04-15.log`
- 修改后源码备份：`logs/radar_nexysvideo/code_backups/533-RadarQMLP-after-wordbank-logit-refactor-2026-04-15.scala`
- hash：`logs/radar_nexysvideo/runtime/534-qmlp-wordbank-logit-refactor-sha256-2026-04-15.txt`
- final diff：`logs/radar_nexysvideo/runtime/535-qmlp-wordbank-logit-refactor-final-diff-2026-04-15.patch`

## 5. 当前边界

这轮只完成 QMLP RTL 结构优化、Verilog 生成、Vivado 语法检查和 OOC synth。还没有重新跑完整 SoC bitstream，也没有重新做板级 boundary/large golden。因此该版本可以作为下一轮 bitstream 候选，但还不能视为板级功能闭环版本。
