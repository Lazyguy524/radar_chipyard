# 21维特征说明

- feature_mode: `rcs21`
- 输入点格式: 融合后的点集，软件侧统一取 `[x, y, doppler, rcs]`。
- 多帧融合: 发生在特征计算之前，当前为同一 `sequence_id/sensor_id/track_id` 的最近 k=7 帧点集拼接。
- int8量化: `q = clamp(round(feature / 2.43614531e+00), -127, 127)`。

| idx | name | 物理含义 | 原始字段 | 来自k=7融合 | 复杂操作 | 软件公式 | 定点化建议 | 适合第一阶段硬件化 |
|---:|---|---|---|---|---|---|---|---|
| f[0] | `n_points` | 融合点簇内点数 | point count | 是 | normalization, dynamic_loop_variable_points | `N` | 整数计数；建议 uint16/uint32 累加后按输入 scale 量化 | 是 |
| f[1] | `mean_x` | 点簇 x 坐标均值 | x | 是 | division, normalization, dynamic_loop_variable_points | `sum(x_i) / N` | sum 使用 int32/fixed32，最后除以 N | 是 |
| f[2] | `mean_y` | 点簇 y 坐标均值 | y | 是 | division, normalization, dynamic_loop_variable_points | `sum(y_i) / N` | sum 使用 int32/fixed32，最后除以 N | 是 |
| f[3] | `std_x` | x 坐标标准差 | x | 是 | sqrt, division, normalization, dynamic_loop_variable_points | `sqrt(mean(x_i^2) - mean_x^2)` | 可用 variance 近似或查表/迭代 sqrt；第一阶段可先软件对拍 | 谨慎 |
| f[4] | `std_y` | y 坐标标准差 | y | 是 | sqrt, division, normalization, dynamic_loop_variable_points | `sqrt(mean(y_i^2) - mean_y^2)` | 同 std_x | 谨慎 |
| f[5] | `span_x` | x 方向包围盒宽度 | x | 是 | normalization, dynamic_loop_variable_points | `max(x_i) - min(x_i)` | min/max 比较器，减法 | 是 |
| f[6] | `span_y` | y 方向包围盒高度 | y | 是 | normalization, dynamic_loop_variable_points | `max(y_i) - min(y_i)` | min/max 比较器，减法 | 是 |
| f[7] | `range_min` | 点到传感器/车辆坐标原点距离最小值 | x/y | 是 | sqrt, normalization, dynamic_loop_variable_points | `min(sqrt(x_i^2 + y_i^2))` | 第一阶段建议用 range^2 或 CORDIC/sqrt；需与训练口径一致 | 谨慎 |
| f[8] | `range_max` | 点到坐标原点距离最大值 | x/y | 是 | sqrt, normalization, dynamic_loop_variable_points | `max(sqrt(x_i^2 + y_i^2))` | 同 range_min | 谨慎 |
| f[9] | `centroid_range` | 点簇中心点到坐标原点的距离 | x/y | 是 | sqrt, normalization, dynamic_loop_variable_points | `sqrt(mean_x^2 + mean_y^2)` | sqrt/CORDIC；可先用查表或分段近似 | 谨慎 |
| f[10] | `azimuth_span` | 点簇方位角跨度 | x/y | 是 | atan_angle, normalization, dynamic_loop_variable_points | `max(atan2(y_i,x_i)) - min(atan2(y_i,x_i))` | 涉及 atan2，第一阶段硬件化风险较高 | 谨慎 |
| f[11] | `eig_major` | xy 协方差矩阵较大特征值，描述主轴离散程度 | x/y | 是 | sqrt, division, normalization, dynamic_loop_variable_points | `eig_max(cov([[x],[y]]))` | 2x2 特征值闭式解，含除法和 sqrt | 谨慎 |
| f[12] | `eig_minor` | xy 协方差矩阵较小特征值，描述次轴离散程度 | x/y | 是 | sqrt, division, normalization, dynamic_loop_variable_points | `eig_min(cov([[x],[y]]))` | 同 eig_major | 谨慎 |
| f[13] | `density_2d` | 二维包围盒内点密度 | x/y/N | 是 | division, normalization, dynamic_loop_variable_points | `N / max(span_x * span_y, 1e-4)` | 乘法 + 除法；需上限保护，容易溢出 | 谨慎 |
| f[14] | `doppler_mean` | 径向速度/Doppler 均值 | doppler | 是 | division, normalization, dynamic_loop_variable_points | `sum(d_i) / N` | sum 后除以 N | 是 |
| f[15] | `doppler_std` | Doppler 标准差 | doppler | 是 | sqrt, division, normalization, dynamic_loop_variable_points | `sqrt(mean(d_i^2) - mean_d^2)` | 同 std_x | 谨慎 |
| f[16] | `doppler_min` | Doppler 最小值 | doppler | 是 | normalization, dynamic_loop_variable_points | `min(d_i)` | 比较器 | 是 |
| f[17] | `doppler_max` | Doppler 最大值 | doppler | 是 | normalization, dynamic_loop_variable_points | `max(d_i)` | 比较器 | 是 |
| f[18] | `rcs_mean` | RCS/反射强度均值 | rcs | 是 | division, normalization, dynamic_loop_variable_points | `sum(r_i) / N` | sum 后除以 N；需要输入端提供 rcs | 是 |
| f[19] | `rcs_std` | RCS/反射强度标准差 | rcs | 是 | sqrt, division, normalization, dynamic_loop_variable_points | `sqrt(mean(r_i^2) - mean_r^2)` | 同 std_x | 谨慎 |
| f[20] | `rcs_max` | RCS/反射强度最大值 | rcs | 是 | normalization, dynamic_loop_variable_points | `max(r_i)` | 比较器 | 是 |
