# Fixed-RCS K7 QMLP 硬件交付说明（2026-04-14）

## 1. 交付结论

当前论文软件侧推荐模型已经从 `k=3 + rcs21` 更新为 `k=7 + rcs21`。对应硬件交付包已补齐：

```text
releases/rcs_fix_k7_rcs21_20260414
```

该版本仍保持硬件 QMLP 结构不变：

```text
input_dim = 21
hidden = 64 -> 32
num_classes = 2
model = 21 -> 64 -> 32 -> 2
precision = INT8 weight / INT8 activation / INT32 accumulator logits
```

因此硬件侧不需要改变 PE 阵列维度和矩阵层次；需要替换的是参数、scale、requant multiplier 和 golden 数据。

## 2. 软件与导出口径

训练侧结果：

| item | value |
|---|---:|
| QAT test accuracy | 0.964551 |
| QAT test macro-F1 | 0.958411 |
| QAT confusion matrix | `[[16109, 471], [1497, 37439]]` |

导出后固定 INT C-trace 全 test 结果：

| item | value |
|---|---:|
| sample count | 55516 |
| INT C-trace accuracy | 0.972170 |
| INT C-trace macro-F1 | 0.967020 |
| INT C-trace confusion matrix | `[[16016, 564], [981, 37955]]` |

注意：QAT 指标与 exported INT C-trace 指标属于不同推理口径，不能写成“量化后精度提升”。硬件对拍以 exported INT C-trace 和 golden 为准。

## 3. 量化参数

参数文件：

- `releases/rcs_fix_k7_rcs21_20260414/radar_mlp_binary_k7_rcs21_rcsfix_params.h`
- `releases/rcs_fix_k7_rcs21_20260414/radar_mlp_binary_k7_rcs21_rcsfix_params.json`
- `releases/rcs_fix_k7_rcs21_20260414/Radar_mlp_binary_k7_rcs21_rcsfixParams.scala`

固定 requant 口径：

```text
calibration = percentile 99.99
train calibration samples = 357780
requant shift = 16
L1 multiplier = 3439
L2 multiplier = 504
rounding = round-to-nearest ties-to-even
activation order = integer requant -> ReLU -> clamp [0, 127]
L3 = int32 accumulator logits, no requant
```

权重布局：

```text
row-major[out][in]
L1 weight = [64][21]
L2 weight = [32][64]
L3 weight = [2][32]
bias = int32[out]
```

## 4. Golden 对拍包

目录：

```text
releases/rcs_fix_k7_rcs21_20260414/hardware_validation_20260414
```

大样本 golden：

| file | layout |
|---|---|
| `large_golden/test_inputs_int8.bin` | contiguous int8[1000][21] |
| `large_golden/test_logits_int32.bin` | contiguous int32[1000][2] |
| `large_golden/test_l1_int8.bin` | contiguous int8[1000][64] |
| `large_golden/test_l2_int8.bin` | contiguous int8[1000][32] |
| `large_golden/test_overview.csv` | sample id / label / pred overview |
| `large_golden/test_detailed.jsonl` | input / logits / L1 / L2 detailed trace |

边界测试：

| file | layout |
|---|---|
| `boundary_cases/boundary_inputs_int8.bin` | contiguous int8[54][21] |
| `boundary_cases/boundary_logits_int32.bin` | contiguous int32[54][2] |
| `boundary_cases/boundary_l1_int8.bin` | contiguous int8[54][64] |
| `boundary_cases/boundary_l2_int8.bin` | contiguous int8[54][32] |
| `boundary_cases/boundary_cases.csv` | case overview |
| `boundary_cases/boundary_cases.jsonl` | detailed trace |

## 5. 建议交付给硬件侧的最小文件集合

优先发送整个目录：

```text
releases/rcs_fix_k7_rcs21_20260414
```

如果只发最小集合，应包含：

1. `radar_mlp_binary_k7_rcs21_rcsfix_params.h`
2. `radar_mlp_binary_k7_rcs21_rcsfix_params.json`
3. `Radar_mlp_binary_k7_rcs21_rcsfixParams.scala`
4. `hardware_validation_20260414/manifest.json`
5. `hardware_validation_20260414/large_golden/test_inputs_int8.bin`
6. `hardware_validation_20260414/large_golden/test_logits_int32.bin`
7. `hardware_validation_20260414/large_golden/test_l1_int8.bin`
8. `hardware_validation_20260414/large_golden/test_l2_int8.bin`
9. `hardware_validation_20260414/boundary_cases/boundary_inputs_int8.bin`
10. `hardware_validation_20260414/boundary_cases/boundary_logits_int32.bin`
11. `hardware_validation_20260414/boundary_cases/boundary_l1_int8.bin`
12. `hardware_validation_20260414/boundary_cases/boundary_l2_int8.bin`

## 6. 建议发给硬件侧的话

这版是当前论文软件侧最佳模型的硬件交付包，目录为 `releases/rcs_fix_k7_rcs21_20260414`。模型仍是 `21->64->32->2` INT8 QMLP，硬件结构不需要改矩阵维度；相比之前 k3 版本，需要替换新的权重、scale、requant multiplier 和 golden。请优先使用 `hardware_validation_20260414/boundary_cases` 做边界对拍，再用 `large_golden` 的 1000 组 test 样本做回归。对拍口径以 `radar_mlp_binary_k7_rcs21_rcsfix_params.json` 中的 fixed-point requant 参数为准，最终比较 int32 logits，若不一致再比较 L1/L2 int8 中间结果。
