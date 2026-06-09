# Feature21 微架构

## 功能定位

Feature21 把多帧融合后的 radar 点集转换为 21 维 int8 特征。输入点包含 `[x, y, doppler, rcs]`，输出是 QMLP 可消费的 feature vector。

当前硬件应表述为固定点/近似实现：它追求与 Python exact-LUT mirror 和分类结果一致，而不是逐操作复刻浮点软件。

## 主要特征类别

| 类别 | 特征 |
| --- | --- |
| 点数/空间统计 | `n_points`、`mean_x`、`mean_y`、`span_x`、`span_y` |
| 空间离散和距离 | `std_x`、`std_y`、`range_min`、`range_max`、`centroid_range` |
| 角度/协方差 | `azimuth_span`、`eig_major`、`eig_minor` |
| 密度 | `density_2d` |
| Doppler/RCS | `doppler_mean/std/min/max`、`rcs_mean/std/max` |

完整表见 [../feature_preproc_compare_20260420/feature21/feature_spec_21.md](../feature_preproc_compare_20260420/feature21/feature_spec_21.md)。

## RTL 状态机概貌

主模块在 [../../fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala](../../fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala) 中，类名 `RadarAXISFeature21Preprocessor`。

状态机核心阶段：

| 阶段 | 作用 |
| --- | --- |
| `sIdle` / `sAccum` | 接收 AXIS 点数据，累计 count、sum、min/max、平方和等统计量 |
| mean/variance/range 阶段 | 由累积量计算均值、范围、近似方差/距离等 |
| density 阶段 | 计算 span area、reciprocal/LUT normalize、density quant |
| feature select/quant/write | 选择 21 个 feature，做定点量化、round、clamp，写入 byte regs |
| `sEmit` | 输出 4 个 64-bit beat，组成 32 B 对齐的 feature frame |

## Pipeline 与 timing

Feature21 在 75 MHz closure 中做过关键路径拆分：

- density area / normalize / multiply / shift / quant / round 被拆开。
- feature select、quant multiply、round、writeback 被拆开。
- output 使用 `outValidReg/outBitsReg` 支持 downstream backpressure。

当前普通 Feature21 quant/writeback 不再是 75 MHz leading path，但 density tail 在坏 route shape 中仍可能变成 near-top path。

## 性能证据

2026-06-08 Feature21 compact board dump：

- `samples=1000`
- `cycles_avg=455`
- `cycles_min=420`
- `cycles_max=662`

PC validation report：

- board Feature21 dump matches Python exact-LUT mirror `1000/1000`
- software QMLP prediction agreement `95.20%`
- changed predictions `48/1000`

证据：[../../logs/radar_nexysvideo/runtime/feature21-v1p4a-compact-validation-1000-75mhz-2026-06-08.md](../../logs/radar_nexysvideo/runtime/feature21-v1p4a-compact-validation-1000-75mhz-2026-06-08.md)

## 边界和待验证

- `expectedPoints=0/1`、小点数、early last、count clamp、density area zero 都应作为 directed tests 保留。
- Feature21 batch DMA bitstream 已 75 MHz timing-clean，但新 bitstream board validation 在当前文档地图里仍标为未运行。
- Full Feature21 raw-point -> QMLP hardware chain 需要单独证据，不能由 Feature21 dump + software QMLP 直接代替。
