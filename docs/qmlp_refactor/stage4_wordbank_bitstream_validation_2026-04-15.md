# QMLP word-bank/ROM 重构版 bitstream 验证

日期：2026-04-15  
阶段：Stage 4，完整 bitstream 验证  
对应代码：`fpga/src/main/scala/nexysvideo/RadarQMLP.scala`

## 结论

当前 QMLP 重构版已经通过完整 FPGA bitstream 生成，post-route timing 满足约束。

本轮验证说明：代码结构从原来的大块常量/packed 替换路径，推进为：

- 集中式 `switch(state)` FSM
- next-value 风格寄存器更新
- QMLP 权重和 bias 通过显式 ROM 访问
- activation cache 改为 64-bit word bank
- final logits 写法改为 `pendingLogit0Reg + lastLogit0Reg + lastLogit1Reg`

## Bitstream

推荐烧录文件：

```text
fpga/deliverables/radar_nexysvideo_bits/545-qmlp-wordbank-refactor-k7-2026-04-15.bit
```

原始输出文件：

```text
fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/NexysVideoHarness.bit
```

SHA256：

```text
15030d44f2526257d9bc95bde3f79b577971fcf6f2dd79787749fcf08d14cec9
```

## Timing

最终 post-route timing：

| 指标 | 数值 |
|---|---:|
| WNS | `0.531 ns` |
| TNS | `0.000 ns` |
| WHS | `0.051 ns` |
| THS | `0.000 ns` |
| Setup failing endpoints | `0` |
| Hold failing endpoints | `0` |

Vivado 报告结论：

```text
All user specified timing constraints are met.
```

主约束时钟 `clk_out1_harnessSysPLLNode` 的 WNS 为 `0.531 ns`。

## 资源

全设计资源：

| 资源 | 数量 |
|---|---:|
| Total LUTs | `28366` |
| Logic LUTs | `24346` |
| LUTRAMs | `3726` |
| SRLs | `294` |
| FFs | `17445` |
| RAMB36 | `2` |
| RAMB18 | `14` |
| DSP Blocks | `10` |

QMLP 层级资源：

| 资源 | 数量 |
|---|---:|
| Total LUTs | `3341` |
| Logic LUTs | `3341` |
| LUTRAMs | `0` |
| SRLs | `0` |
| FFs | `1491` |
| RAMB36 | `0` |
| RAMB18 | `0` |
| DSP Blocks | `0` |

说明：QMLP 权重 ROM 当前综合为分布式 ROM / LUT 结构，不占用 BRAM；QMLP 内部乘法仍保持 LUT 逻辑实现，未占用 DSP。

## 后续板级验证

本轮只是 bitstream/timing/PPA 验证。要证明功能闭环，还需要烧录归档 bit 后执行：

1. `hardware_validation_20260414/boundary_cases`
2. `hardware_validation_20260414/large_golden`

目标结果仍然是：

- boundary cases：`54/54`
- large golden：`1000/1000`

## 详细日志

完整日志与原始报告保存在：

- `logs/radar_nexysvideo/runtime/544-fpga-bitstream-qmlp-wordbank-refactor-2026-04-15.log`
- `logs/radar_nexysvideo/runtime/548-qmlp-wordbank-refactor-bitstream-summary-2026-04-15.md`
- `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/report/timing.txt`
- `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/report/utilization.txt`
