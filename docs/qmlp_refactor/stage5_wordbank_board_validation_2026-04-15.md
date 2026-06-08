# QMLP word-bank/ROM 重构版板级验证

日期：2026-04-15  
阶段：Stage 5，板级功能验证  
对应 bitstream：`fpga/deliverables/radar_nexysvideo_bits/545-qmlp-wordbank-refactor-k7-2026-04-15.bit`

## 结论

当前结构化重构版已经完成板级功能闭环：

| 数据集 | 样本数 | 结果 |
|---|---:|---|
| `large_golden` | `1000` | 通过 |
| `boundary_cases` | `54` | 通过 |

最终程序输出：

```text
AXI DMA qmlp validation PASSED
```

## 性能

| 指标 | 数值 |
|---|---:|
| QMLP kernel cycles | `1301 cycles / sample` |
| QMLP kernel latency @ 50 MHz | `26.02 us / sample` |
| large_golden e2e avg | `1117247 cycles / sample` |
| boundary_cases e2e avg | `8941730 cycles / sample` |

说明：`kernel cycles` 更能代表 QMLP 加速器计算延迟；`e2e avg` 包含 DMA、软件调度和测试程序开销。

## 本轮意义

这轮验证证明以下结构化改动没有改变功能行为：

- 固定权重/bias 显式 ROM 访问
- activation cache 改为 64-bit word-bank
- logits 写回路径由动态 `logitsVec` 改为显式暂存寄存器
- 集中式 FSM 与 next-value 风格寄存器更新

因此，当前版本可以作为后续论文、PPT 和进一步优化的硬件代码基线。

## 详细记录

- 外层运行日志：`logs/radar_nexysvideo/runtime/552-qmlp-wordbank-refactor-board-validation-2026-04-15.log`
- 主串口日志：`logs/radar_nexysvideo/runtime/run-qmlp-validation-manual-2026-04-15-120545.log`
- 板测摘要：`logs/radar_nexysvideo/runtime/553-qmlp-wordbank-refactor-board-pass-summary-2026-04-15.md`
