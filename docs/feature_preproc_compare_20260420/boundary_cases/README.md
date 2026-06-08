# boundary_cases

这些边界样本是用于前处理模块和 QMLP 的人工合成点簇，不对应真实标签。

- `raw_or_fused_boundary_inputs.bin`: float32 点数组，列为 `[x, y, doppler, rcs]`。
- `raw_or_fused_boundary_offsets_u32.bin`: 每个 case 在点数组中的起止 offset。
- `features{14,18,21}_boundary_int8.bin`: 各输入维度前处理后的 int8 特征。
- `logits{14,18,21}_boundary_int32.bin`: 对应 QMLP 输出 `[pedestrian, vehicle]` logits。
