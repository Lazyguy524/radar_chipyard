# feature_preproc_compare_20260420

本目录是给硬件端选择 14/18/21 维前处理 RTL 实现顺序的交付包。

目录内容：

- `feature_compare_summary.md`: 总结、指标对比、实现建议。
- `feature14/`, `feature18/`, `feature21/`: 对应模型参数、特征定义、golden 数据。
- `boundary_cases/`: 合成边界点簇及三种维度的前处理和 logits。
- `benchmark/preproc_benchmark_result.json`: C -O3 前处理耗时参考。

二进制格式约定：

- `inputs_raw_or_fused.bin`: float32，按 `[x, y, doppler, rcs]` 平铺。
- `inputs_raw_or_fused_offsets_u32.bin`: uint32，长度为 sample_count+1。
- `features_int8_*.bin`: int8，连续 `[sample][feature_dim]`。
- `logits_int32.bin`: int32，连续 `[sample][2]`，顺序为 `[pedestrian, vehicle]`。
