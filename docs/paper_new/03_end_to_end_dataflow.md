# 端到端数据流

## 当前可解释数据流

```text
多帧融合 radar 点集
  -> [x, y, doppler, rcs] 点记录
  -> Feature21 固定点/近似预处理
  -> 21 维 int8 feature
  -> QMLP 输入帧，32 B 对齐
  -> L1: 21 -> 64, int8 weight, int32 accumulate, requant + ReLU
  -> L2: 64 -> 32, int8 weight, int32 accumulate, requant + ReLU
  -> L3: 32 -> 2, int8 weight, int32 accumulate
  -> 2 个 int32 logits，8 B 输出
  -> CPU 或软件比较 class/logits
```

## Feature21 到 QMLP 的数据形态

Feature21 的自然输出是 `21` 个 int8。QMLP 的 AXI4-Stream 接口按 `32 B` 接收输入，因此 21 个有效 feature byte 被放进 4 个 64-bit beat 中，剩余 byte 是对齐/填充空间。QMLP 内部只按 `RADAR_MLP_INPUT_DIM = 21` 使用有效输入维度。

## QMLP 内部数据变化

| 阶段 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| L1 | `int8[21]` | `int8[64]` | 每个输出 neuron 做 21 项 MAC，int32 bias 起始，requant 后 ReLU/clamp |
| L2 | `int8[64]` | `int8[32]` | 每个输出 neuron 做 64 项 MAC，requant 后 ReLU/clamp |
| L3 | `int8[32]` | `int32[2]` | 最后一层只输出 logits，不做 ReLU 或 softmax |

总 MAC 数：

```text
21*64 + 64*32 + 32*2 = 3456
```

## RoCC dot4 路径的数据变化

RoCC `rqdot4` 不处理完整样本帧，只处理 packed int8x4：

```text
rs1[31:0] = lane0..lane3 int8
rs2[31:0] = lane0..lane3 int8
result = sum(sign_i8(rs1_lane) * sign_i8(rs2_lane))
```

QMLP RoCC profile 中，软件仍负责循环、bias、tail MAC、requant 和 L1/L2/L3 调度，RoCC 只替代每组 4 lane MAC。

## 板级验证口径

- Feature21 compact board dump：`1000` samples，`cycles_avg=455`，用于验证 Feature21 输出和 exact-LUT mirror/分类一致性。
- QMLP direct validation：`1000` large-golden + `54` boundary cases，`hw_cycles_avg=2213`，用于验证当前 75 MHz QMLP 硬件路径。
- RoCC cycle profile：`1600` inferences，scalar `168203` cycles，RoCC `62532` cycles，用于验证 custom instruction kernel 收益。

## 不能混淆的路径

- Feature21 dump + software QMLP 不是完整硬件 Feature21->QMLP chain。
- QMLP direct validation 不包含 raw point Feature21 预处理。
- RoCC `rqdot4` profile 不经过 DMA，不代表 DMA stream accelerator 的端到端性能。
