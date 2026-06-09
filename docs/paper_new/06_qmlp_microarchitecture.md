# QMLP 微架构

## 模型与数值格式

QMLP 是固定形状的三层 MLP：

```text
输入: int8[21]
L1: 21 -> 64, int8 weight, int32 accumulate, requant + ReLU -> int8[64]
L2: 64 -> 32, int8 weight, int32 accumulate, requant + ReLU -> int8[32]
L3: 32 -> 2, int8 weight, int32 accumulate -> int32 logits[2]
```

总 MAC 数：

```text
21*64 + 64*32 + 32*2 = 3456
```

## AXI4-Stream 接口

主模块在 [../../fpga/src/main/scala/nexysvideo/RadarQMLP.scala](../../fpga/src/main/scala/nexysvideo/RadarQMLP.scala)，类名 `RadarAXISQMLP`。

接口是 Chisel `Decoupled` 风格：

- `io.in`: 64-bit AXIS-like word，含 `data/keep/last`
- `io.out`: 64-bit AXIS-like word，输出两个 int32 logits
- `ctrlEnable`、`clearCounters`
- counters/status：`inBeats`、`outBeats`、`frameCount`、`lastKeep`、`runCycles`

## 状态机

`RadarAXISQMLP` 的状态枚举包含：

```text
sIdle, sRecv,
sL1Load, sL1Prep, sL1Mac, sL1QuantMul, sL1QuantRound, sL1Write,
sL2Load, sL2Prep, sL2Mac, sL2QuantMul, sL2QuantRound, sL2Write,
sL3Load, sL3Prep, sL3Mac, sL3Write, sL3Pack,
sEmit
```

设计含义：

- `sRecv` 收 4 个 64-bit beat，按 `keep` 合并到输入寄存器。
- L1/L2/L3 逐输出 neuron 计算。
- MAC 阶段使用 4-lane 分组，减少串行 MAC 周期。
- L1/L2 requant 被拆成 multiply、round、write 多个阶段。
- `sEmit` 持有输出直到 downstream `ready`。

## 当前周期证据

2026-06-08 direct QMLP validation：

- `1000` large-golden samples + `54` boundary cases PASS
- `hw_cycles_avg=2213` at 75 MHz

2026-04-16 older no-reset QMLP DMA profile at 50 MHz：

- QMLP internal `hw_avg=1301 cycles/sample`
- batch=511 时 DMA timed interval 仅比 QMLP kernel 多约 `5 cycles/sample`
- 该证据说明在该旧 profile/bitstream 下，大 batch DMA stream 已接近计算下限，数据搬运不明显让 QMLP 空拍

写论文时要区分：

- `hw_cycles`：QMLP RTL 内部计算周期。
- `dma_avg`：去除大量 debug 打印/重置后的 DMA timed interval。
- validation `e2e_cycles`：通常包含 reset、打印、校验，不适合作为最终性能代表。

## 瓶颈判断

CPU-only QMLP profile 显示 dot/MAC 是主要工作量：

- `infer_avg=168349`
- `dot_mac_upper=93.43%`
- `quant_relu=5.66%`
- `control_resid=0.90%`

RoCC dot4 profile 进一步证明替换 packed MAC 有明显收益，但 `rqscale8` 仍在软件中，因此后续还有优化空间。

## 边界

- QMLP 当前是固定模型，不是通用可编程神经网络加速器。
- 输出 logits 不是概率，也不是 softmax。
- 不同参数文件/模型版本要明确引用路径。
