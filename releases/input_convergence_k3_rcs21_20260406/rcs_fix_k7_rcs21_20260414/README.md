# Fixed-RCS K7 QMLP 硬件交付包（2026-04-14）

## 1. 模型版本

本目录是当前论文软件侧最佳模型对应的硬件交付版本。

固定模型：

```text
k=7 + rcs21
QMLP: 21 -> 64 -> 32 -> 2
INT8 activation / INT8 weight / INT32 accumulator logits
no-KD
```

类别顺序：

```text
0 = pedestrian
1 = vehicle
```

对应软件训练结果：

- 配置：`configs/multiframe_k_sweep_rcsfix_2026-04-14/k7_rcs21_nokd.yaml`
- 权重：`logs/multiframe_k_sweep_rcsfix_2026-04-14/train/k7_rcs21_nokd/student_qat.pt`
- 训练侧 test accuracy：`0.964551`
- 训练侧 test macro-F1：`0.958411`
- 导出后固定 INT C-trace test accuracy：`0.972170`
- 导出后固定 INT C-trace test macro-F1：`0.967020`

说明：训练侧指标来自 PyTorch/QAT 评估；硬件应以本 release 中的固定 INT C-trace/golden 为对拍基准。

## 2. 量化与 requant 固定口径

导出时使用 deterministic percentile calibration：

```text
calibration method = percentile
percentile = 99.99
calibration split = train
calibration sample_count = 357780
```

硬件 requant 参数：

```text
RADAR_QMLP_REQUANT_SHIFT = 16
RADAR_QMLP_L1_MULTIPLIER = 3439
RADAR_QMLP_L2_MULTIPLIER = 504
rounding = round-to-nearest ties-to-even
L1/L2 activation = integer requant -> ReLU -> clamp [0, 127]
L3 output = int32 accumulator logits, no requant
```

权重布局：

```text
row-major[out][in]
L1 weight shape = [64][21]
L2 weight shape = [32][64]
L3 weight shape = [2][32]
bias layout = int32[out]
```

## 3. 交付文件

参数文件：

- `radar_mlp_binary_k7_rcs21_rcsfix_params.h`
- `radar_mlp_binary_k7_rcs21_rcsfix_params.json`
- `Radar_mlp_binary_k7_rcs21_rcsfixParams.scala`

最小 C 参考：

- `baremetal_demo/radar_mlp_params.h`
- `baremetal_demo/radar_mlp.h`
- `baremetal_demo/radar_mlp.c`
- `baremetal_demo/main.c`

硬件 golden 包：

- `hardware_validation_20260414/manifest.json`
- `hardware_validation_20260414/large_golden/`
- `hardware_validation_20260414/boundary_cases/`

校验摘要：

- `release_manifest.json`
- `exported_c_trace_test_metrics.json`

## 4. Golden 数据说明

大样本 golden：

```text
sample_count = 1000
split = test
input layout = contiguous int8[1000][21]
logits layout = contiguous int32[1000][2]
L1 layout = contiguous int8[1000][64]
L2 layout = contiguous int8[1000][32]
```

关键文件：

- `large_golden/test_inputs_int8.bin`
- `large_golden/test_logits_int32.bin`
- `large_golden/test_l1_int8.bin`
- `large_golden/test_l2_int8.bin`
- `large_golden/test_overview.csv`
- `large_golden/test_detailed.jsonl`

边界输入：

```text
case_count = 54
包含 all_zero、all_pos127、all_neg127_quant_min、all_neg128_raw_int8、正负交替、单维非零、真实分布极端样本等。
```

关键文件：

- `boundary_cases/boundary_inputs_int8.bin`
- `boundary_cases/boundary_logits_int32.bin`
- `boundary_cases/boundary_l1_int8.bin`
- `boundary_cases/boundary_l2_int8.bin`
- `boundary_cases/boundary_cases.csv`
- `boundary_cases/boundary_cases.jsonl`

## 5. 硬件侧建议测试顺序

1. 先读取 `radar_mlp_binary_k7_rcs21_rcsfix_params.json`，确认 shape、scale、multiplier。
2. 用 `boundary_cases` 跑单样本对拍，先确认极端输入不会溢出或状态机卡死。
3. 用 `large_golden/test_inputs_int8.bin` 跑 1000 样本回归。
4. 对比顺序建议：先比 final logits int32[2]；若 logits 不一致，再比 L1 int8[64] 和 L2 int8[32]。
5. argmax 可以留给 CPU，硬件只需要保证 logits 与 golden 一致。

## 6. 与 K3 版本的关系

`releases/rcs_fix_k3_rcs21_20260414` 是历史 bring-up 对照版本，软件侧最佳结论已更新为 `k=7 + rcs21`。

由于 `k=3` 和 `k=7` 的部署特征维度相同，硬件 QMLP 结构仍为 `21 -> 64 -> 32 -> 2`，不需要改变矩阵维度和 PE 阵列形状；需要替换的是权重、scale、requant multiplier、golden 输入与 golden 输出。
