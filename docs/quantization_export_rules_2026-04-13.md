# 冻结模型量化与导出规则确认说明

## 1. 模型范围

当前冻结模型为：

- 多帧设置：`k=3`
- 输入模式：`rcs21`
- 网络结构：`21 -> 64 -> 32 -> 2`
- 模型类型：`INT8 QMLP`

对应冻结版本目录：

- [input_convergence_k3_rcs21_20260406](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406)

## 2. 位宽定义

- 输入特征：`int8`
- 权重：`int8`
- 中间累加：`int32`
- bias：`int32`
- 最终 logits：`int32`

说明：

- `L1` 和 `L2` 在 GEMV 后先得到 `int32 acc`
- 然后通过 requant 回到 `int8`
- `L3` 只输出 `int32 logits`，不再 requant 回 `int8`

## 3. 输入、权重、输出的量化语义

### 输入

模型输入在软件端先按第一层 `input_scale` 量化：

```text
x_q = clamp(round(x_float / input_scale), -127, 127)
```

### 权重

每层权重都按本层 `weight_scale` 单独量化：

```text
w_q = clamp(round(w_float / weight_scale), -127, 127)
```

### 中间层输出

`L1`、`L2` 的 `int32 acc` 经过 requant 和 ReLU 后，得到下一层输入 `int8`。

### 最终输出

`L3` 输出保留为 `int32 logits`：

```text
logits_int32 = acc3
```

如果需要在软件端查看浮点语义，可再乘以 `L3.output_scale`：

```text
logits_float = logits_int32 * l3_output_scale
```

## 4. requant 规则

当前冻结模型的 requant 规则固定为：

- requant 模式：`float_mul_scale_then_round`
- rounding 规则：`round_to_nearest_ties_to_even`
- saturation / clamp 范围：`[-127, 127]`

也就是：

```text
scaled = acc_int32 * (input_scale * weight_scale / output_scale)
requant = clamp(round(scaled), -127, 127)
```

## 5. ReLU 位置

ReLU 固定发生在 requant 之前：

```text
acc_int32
 -> scaled_float
 -> relu(scaled_float)
 -> round
 -> clamp
 -> int8 output
```

这一规则只用于 `L1` 和 `L2`。

`L3` 不做 ReLU。

## 6. 三层固定计算顺序

### L1

```text
y1_acc = x_q @ W1_q^T + b1_int32
y1_scaled = y1_acc * (l1_input_scale * l1_weight_scale / l1_output_scale)
y1_relu = relu(y1_scaled)
y1_q = clamp(round(y1_relu), -127, 127)
```

### L2

```text
y2_acc = y1_q @ W2_q^T + b2_int32
y2_scaled = y2_acc * (l2_input_scale * l2_weight_scale / l2_output_scale)
y2_relu = relu(y2_scaled)
y2_q = clamp(round(y2_relu), -127, 127)
```

### L3

```text
logits_int32 = y2_q @ W3_q^T + b3_int32
```

## 7. 为什么 golden logits 是 int32

因为硬件侧当前实现的是 kernel 级定点推理。

对最终分类而言，最稳定、最不丢信息的对拍口径就是：

- 输入：`int8[21]`
- 输出：`int32[2] logits`

这样有几个好处：

- 避免末层再做一次额外 requant 带来的误差
- 硬件与软件能直接逐项比对
- CPU 侧只需做 `argmax(logits)` 即可得到分类结果

因此：

> `golden logits` 采用 `int32` 不是临时选择，而是当前软硬件对拍最合适的固定口径。

## 8. 导出文件应如何理解

硬件侧应重点参考：

- [radar_mlp_binary_k3_rcs21_params.h](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/radar_mlp_binary_k3_rcs21_params.h)
- [radar_mlp_binary_k3_rcs21_params.json](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/radar_mlp_binary_k3_rcs21_params.json)

其中：

- 权重布局：`row_major[out][in]`
- bias 布局：`separate_int32[out]`
- `L1/L2/L3` 的 `input_scale / weight_scale / output_scale` 已固定
- `clamp_range = [-127, 127]`

## 9. 当前对拍建议

建议按以下顺序做：

1. 先使用单样本 golden：
   - [golden_input.h](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_input.h)
   - [golden_logits.h](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_logits.h)
2. 再使用大样本验证包：
   - [hardware_validation_20260413](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_validation_20260413)
3. 如果层级结果不一致，再对照：
   - `L1 output_int8`
   - `L2 output_int8`
   - 每层 `acc_int32`

这样能最快定位：

- 输入量化问题
- GEMV 顺序问题
- requant / rounding / clamp 问题
- ReLU 位置问题
