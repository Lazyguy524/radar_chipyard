# 数据规格与类型约定

## 输入来源

Feature21 的输入是多帧融合后的 radar 点集。软件侧统一取每个点的 `[x, y, doppler, rcs]`。当前 21 维特征说明中写明：多帧融合发生在特征计算之前，当前为同一 `sequence_id/sensor_id/track_id` 的最近 `k=7` 帧点集拼接。

证据：[../feature_preproc_compare_20260420/feature21/feature_spec_21.md](../feature_preproc_compare_20260420/feature21/feature_spec_21.md)

## Feature21 输出

Feature21 输出 `21` 个 int8 特征。当前量化公式：

```text
q = clamp(round(feature / 2.43614531e+00), -127, 127)
```

21 维特征包含点数、均值、标准差、span、range、azimuth、特征值、density、doppler、rcs 等统计量。硬件实现不是所有 float 公式逐项严格复刻，而是使用固定点/近似路径，并与 exact-LUT mirror 做对拍。

## QMLP 输入输出

| 项目 | 当前约定 |
| --- | --- |
| 模型形状 | `21 -> 64 -> 32 -> 2` |
| 输入语义 | 21 维 int8 feature |
| 硬件/测试输入帧 | `32 B/sample`，即 4 个 64-bit AXI4-Stream beat |
| 输出语义 | 2 个 int32 logits |
| 硬件/测试输出帧 | `8 B/sample`，即 1 个 64-bit AXI4-Stream beat |
| 隐层激活 | int8，ReLU + clamp 到 `[0, 127]` |
| 权重 | int8 |
| 累加 | int32 |
| L1/L2 requant | `acc * multiplier >> 16`，round-nearest-even，再 ReLU/clamp |
| L3 输出 | 不做 softmax，直接输出 int32 logits |

测试口径证据：

- `RADAR_QMLP_TEST_INPUT_BYTES = 32`
- `RADAR_QMLP_TEST_OUTPUT_BYTES = 8`
- `RADAR_QMLP_MULTI_CASES = 8`
- `RADAR_QMLP_TOTAL_MACS = 3456`

证据：[../../tests/radar_qmlp_test_common.h](../../tests/radar_qmlp_test_common.h)、[../../tests/radar_xradar_fallback.h](../../tests/radar_xradar_fallback.h)

## 两套参数源的注意事项

当前 repo 中存在历史 release 参数和 feature21 对比目录参数：

- `tests/radar_qmlp_test_common.h` 和 Xradar fallback 当前包含 `releases/input_convergence_k3_rcs21_20260406/radar_mlp_binary_k3_rcs21_params.h`，测试常量中 L1/L2 multiplier 为 `1516` / `608`。
- `docs/feature_preproc_compare_20260420/feature21/qmlp_params_21.h` 是 feature21 对比材料中的 21 维参数，L1/L2 multiplier 为 `3439` / `504`。

论文写作时必须说明使用的是哪套验证口径。当前 2026-06-09 RoCC profile 使用的是 `tests/radar_xradar_fallback.h` 路径下的 QMLP 语义测试口径。

## 是否定型

当前论文可把以下约定视为“已定型的板级验证口径”：

- QMLP 输入维度 `21`，输出 logits `2`。
- QMLP 测试帧输入 `32 B`，输出 `8 B`。
- RoCC `rqdot4` 对 QMLP packed MAC 的覆盖：`848` 个 `rqdot4`，`64` 个 scalar tail MAC，packed MAC coverage `98.14%`。
- Feature21 v1.4a 作为当前固定点/approximate 硬件实现口径，对拍方式是 exact-LUT mirror 和分类一致性。

不应视为完全最终定型的部分：

- Feature21 full hardware chain 的最终 e2e 证据仍需独立验证。
- `rqscale8`、`rqpack`、`racc.*` 尚未进入 RoCC RTL。
- Feature21 batch DMA bitstream 有 timing-clean 候选，但新 bitstream 的 board validation 在现有记录中仍标为未运行。
