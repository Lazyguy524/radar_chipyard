# Radar QMLP 结构化重构结果：显式 ROM + Packed Datapath

日期：2026-04-15  
目标文件：`fpga/src/main/scala/nexysvideo/RadarQMLP.scala`  
阶段目标：在不改变外部接口、计数口径、权重来源和 golden 语义的前提下，降低 QMLP RTL 的“大块 if/else + 大常量 mux”复杂度。

## 1. 本轮改动结论

本轮不再继续保留 `VecInit(qmlp.lxWeight)` 形式的大权重常量表，也不再使用 `l1RowReg/l2RowReg/l3RowReg` 做整行权重装载。新的实现把固定权重和 bias 导出为 hex 初始化文件，并实例化 6 个显式异步 ROM：

- `RadarQMLPL1WeightRom`
- `RadarQMLPL2WeightRom`
- `RadarQMLPL3WeightRom`
- `RadarQMLPL1BiasRom`
- `RadarQMLPL2BiasRom`
- `RadarQMLPL3BiasRom`

权重 ROM 的每个 word 为 32 bit，正好打包 4 个 INT8 权重 lane，对应当前 4-lane PE。MAC 阶段按 `outIdx` 和 `inIdx/4` 读取当前 4 个权重，不再先把整行权重写入 rowReg。

另外，源码内部参数对象已从容易误导的 `RadarQMLPK3Rcs21Data` 收敛为 `RadarQMLPReleaseData`，避免当前 k7 release 仍显示 k3 命名的问题。该修改只影响 Scala 源码命名，不改变生成硬件接口。

## 2. 为什么选择 ROM，而不是 RAM

当前 QMLP 的权重来自冻结模型，运行时不需要更新，因此更适合用 ROM，而不是 RAM。

- ROM 优点：接口简单、面积小、语义明确，适合固定模型参数。
- RAM/BRAM 适用场景：后续如果要支持板上动态换模型、在线加载权重、多模型切换，才更适合引入 RAM/BRAM 和权重加载控制器。
- 当前 FPGA OOC 综合结果显示，这些 ROM 被 Vivado 识别为 LUT ROM，没有占用 BRAM。

从数字后端角度看，本轮把“权重存储”从 Chisel 大常量 mux 收敛成了明确的 ROM 读口。若后续进入 ASIC 或更严格后端流程，可以用同样接口替换为 ROM macro 或 memory compiler 生成的只读存储宏，而不需要重写 QMLP 控制状态机。

## 3. Datapath 收敛情况

本轮同时收敛了主要数据寄存器写法：

- `inputVec` 改为 `inputPacked`，通过 `nextInputPacked` 统一写回。
- `l1OutVec` 改为 `l1OutPacked`，通过 `nextL1OutPacked` 统一写回。
- `l2OutVec` 改为 `l2OutPacked`，通过 `nextL2OutPacked` 统一写回。
- `outBitsReg` 改为完整 `nextOutBits` 风格。
- `state/outIdx/inIdx/acc/quant/counter/logit` 均保持集中 next-value 写回。

因此这版不只是 `switch/is` 层面的整理，而是把权重访问、激活缓存、输出打包都进一步收敛到了更清楚的数据通路。

## 4. 生成 RTL 质量

关键扫描结果：

| 项目 | 结果 |
|---|---:|
| `RadarAXISQMLP.sv` 行数 | 682 |
| `always` block | 2 |
| `if/else if` 行数 | 90 |
| `while` | 0 |
| rowReg 相关 RTL | 0 |
| 顶层 `$readmemh` | 0 |
| ROM blackbox 文件 | 6 |
| ROM 实例 | 6 |

源码侧扫描结果：

| 项目 | 结果 |
|---|---:|
| `switch(state)` | 1 |
| `when(state === ...)` 分散写法 | 0 |
| `state := nextState` | 1 |
| `VecInit(qmlp.lxWeight)` | 0 |
| Chisel `Mem(...)` | 0 |
| `loadMemoryFromFileInline` | 0 |

## 5. Vivado OOC 综合结果

OOC 综合对象仅为 `RadarAXISQMLP` 和 6 个 ROM blackbox，不代表完整 SoC 实现结果，但可用于判断该 RTL 是否可被 Vivado 前端和综合流程接受。

| 项目 | 结果 |
|---|---:|
| Synthesis errors | 0 |
| Critical warnings | 0 |
| Slice LUTs | 3870 |
| Slice Registers | 1410 |
| BRAM Tile | 0 |
| DSP | 0 |
| 20 ns clock OOC WNS | 0.709 ns |

Vivado ROM 识别摘要：

- `RadarQMLPL1WeightRom`: `512x32`, LUT ROM
- `RadarQMLPL2WeightRom`: `512x32`, LUT ROM
- `RadarQMLPL3WeightRom`: `16x32`, LUT ROM
- `RadarQMLPL1BiasRom`: `64x5`, LUT ROM
- `RadarQMLPL2BiasRom`: `32x8`, LUT ROM
- `RadarQMLPL3BiasRom`: `2x4`, LUT ROM

## 6. 已生成的日志与备份

- Verilog 生成日志：`logs/radar_nexysvideo/runtime/493-qmlp-inline-rom-refactor-verilog-2026-04-15.log`
- RTL 扫描：`logs/radar_nexysvideo/runtime/494-qmlp-inline-rom-rtl-quality-scan-2026-04-15.txt`
- 源码扫描：`logs/radar_nexysvideo/runtime/495-qmlp-inline-rom-source-quality-scan-2026-04-15.txt`
- ELF 构建检查：`logs/radar_nexysvideo/runtime/496-qmlp-inline-rom-qmlp-elf-builds-2026-04-15.log`
- Vivado 语法检查：`logs/radar_nexysvideo/runtime/497-qmlp-inline-rom-xvlog-2026-04-15.log`
- OOC synth 脚本：`logs/radar_nexysvideo/runtime/498-qmlp-inline-rom-ooc-synth-2026-04-15.tcl`
- OOC utilization：`logs/radar_nexysvideo/runtime/499-qmlp-inline-rom-ooc-util-2026-04-15.rpt`
- OOC timing：`logs/radar_nexysvideo/runtime/500-qmlp-inline-rom-ooc-timing-2026-04-15.rpt`
- OOC synth 日志：`logs/radar_nexysvideo/runtime/501-qmlp-inline-rom-ooc-synth-2026-04-15.log`
- 修改后源码备份：`logs/radar_nexysvideo/code_backups/502-RadarQMLP-after-inline-rom-refactor-2026-04-15.scala`
- 修改前后 hash：`logs/radar_nexysvideo/runtime/503-qmlp-inline-rom-before-after-sha256-2026-04-15.txt`
- 最终 diff：`logs/radar_nexysvideo/runtime/504-qmlp-inline-rom-final-diff-2026-04-15.patch`
- 命名前源码备份：`logs/radar_nexysvideo/code_backups/508-RadarQMLP-before-release-data-rename-2026-04-15.scala`
- 命名收敛后 Verilog 生成：`logs/radar_nexysvideo/runtime/509-qmlp-inline-rom-release-rename-verilog-2026-04-15.log`
- 命名收敛后 RTL 扫描：`logs/radar_nexysvideo/runtime/510-qmlp-inline-rom-release-rename-rtl-scan-2026-04-15.txt`
- 命名收敛后源码扫描：`logs/radar_nexysvideo/runtime/511-qmlp-inline-rom-release-rename-source-scan-2026-04-15.txt`
- 命名收敛后 Vivado 语法检查：`logs/radar_nexysvideo/runtime/512-qmlp-inline-rom-release-rename-xvlog-2026-04-15.log`
- 命名收敛后 OOC synth：`logs/radar_nexysvideo/runtime/513-qmlp-inline-rom-release-rename-ooc-synth-2026-04-15.log`

## 7. 后续门禁

这轮已经通过 Verilog 生成、Vivado `xvlog` 和 OOC synth，但还没有重新跑完整 SoC bitstream 与板级 golden 回归。因此目前可判断为“结构化 RTL 重构通过前端与独立综合检查”，但还不能替代最终板级功能验收。

后续建议顺序：

1. 重新跑完整 bitstream，确认完整 SoC 时序。
2. 烧录后跑 `boundary_cases`。
3. 再跑 `large_golden 1000/1000`。
4. 如果功能完全一致，再把该版作为新的 QMLP RTL 基线。
