# Feature21 处理模块周报 PPT 提纲

Date: 2026-05-06

用途：周报 / 阶段性汇报。内容基于现有 Feature21 论文整理文件和验证日志，不包含新的 RTL/Chisel 修改，不生成 bitstream，不加入 `mean_recip` / `range_piecewise`。

## 0. 一句话总结

本阶段完成了从融合点云到 21 维定点特征的硬件化验证闭环：输入为 k=7 多帧融合后的变长点集，每个点包含 `x, y, doppler, rcs` 四个字段；硬件 Feature21 模块将其转换为 21 维 int8 特征，并通过 Python mirror、RTL、板级 dump 和 QMLP prediction agreement 完成收敛验证。

## 1. 建议拆成 3 周讲

### Week 1：输入数据与 21 维特征定义收敛

汇报主题：

- 明确 Feature21 的输入不是单帧原始点，而是 k=7 多帧融合后的变长点集。
- 每个点包含四个字段：`x, y, doppler, rcs`。
- 硬件不做跨帧融合，只接收融合结果并提取 21 维特征。
- 梳理 21 维特征的物理含义和硬件化难度。

可做 PPT 页：

1. 背景页：为什么需要 Feature21
   - QMLP 输入不是原始点云，而是 21 维 int8 特征。
   - 软件原始 Feature21 包含除法、sqrt、atan2、eigen、density 等复杂算子。
   - 目标是在 FPGA 上实现硬件友好的近似版 Feature21。

2. 输入数据页：融合后的变长点集
   ```text
   k=7 多帧融合后的点集
       每个点: x, y, doppler, rcs
       点数 N 可变
           ↓
   Feature21 hardware preprocessor
           ↓
   21 维 int8 feature vector
   ```
   讲法：
   - 融合发生在 Feature21 之前。
   - 当前硬件模块不负责 tracking / frame fusion。
   - 硬件面对的问题是“变长点集统计特征提取”。

3. 21 维特征分类页

| 类别 | 特征 |
|---|---|
| 点数 / 坐标均值 | f0 `n_points`, f1 `mean_x`, f2 `mean_y` |
| 坐标离散程度 | f3 `std_x`, f4 `std_y`, f11 `eig_major`, f12 `eig_minor` |
| 包围盒 / range 几何 | f5 `span_x`, f6 `span_y`, f7 `range_min`, f8 `range_max`, f9 `centroid_range`, f10 `azimuth_span` |
| 密度 | f13 `density_2d` |
| Doppler | f14 `doppler_mean`, f15 `doppler_std`, f16 `doppler_min`, f17 `doppler_max` |
| RCS | f18 `rcs_mean`, f19 `rcs_std`, f20 `rcs_max` |

4. 硬件化难点页

| 难点 | 软件公式特点 | 硬件策略 |
|---|---|---|
| 变长点数 | 每个样本点数不同 | streaming accumulation + finalization |
| 均值 / 密度 | division | shift / reciprocal LUT / fixed-point approximation |
| range / centroid | sqrt | shift-add proxy |
| azimuth | atan2 | 当前使用 proxy，不做精确 atan2 |
| std / eigen | sqrt + division + covariance eigen | 当前使用统计/几何 proxy，作为 future work |

Week 1 结论：

> 完成了输入口径和 21 维特征定义收敛，明确硬件模块处理的是“融合后的变长点集 -> 21 维 int8 特征”，不是单帧点云融合。

### Week 2：硬件友好近似与验证链路建立

汇报主题：

- 建立 SW golden -> Python HW mirror -> RTL -> Board 四级验证链路。
- 用 Python mirror 先评估硬件近似，再做 RTL/板级验证。
- v1.3 暴露 f13 `density_2d` 是主要分类翻转来源。
- v1.4a 对 f13 使用 density exact-LUT 近似并完成板级对拍。

可做 PPT 页：

1. 四级验证链路页

```text
Software golden Feature21
    ↓
Python hardware mirror
    ↓
RTL / Chisel implementation
    ↓
Board 21-byte compact dump
    ↓
QMLP prediction agreement
```

讲法：
 - 软件 golden 是算法参考。
 - Python mirror 是硬件近似的 bit-level 参考。
 - RTL 正确性看是否匹配 Python mirror。
 - 软件 golden vs board 看近似误差。
 - QMLP agreement 看任务级影响。

2. v1.3 问题定位页

| 项目 | 结果 |
|---|---:|
| v1p3 Python mirror feature match | 62.45% |
| v1p3 QMLP prediction agreement | 79.90% |
| changed predictions | 201/1000 |
| f13 mismatch in changed predictions | 199/201 |

讲法：
 - v1.3 不是完全失败，硬件化路径跑通了。
 - 但任务级错误高度集中在 f13 density。
 - 因此下一步不是盲目重构全部 Feature21，而是针对密度项做局部修正。

3. v1.4a density exact-LUT 方法页

```text
area_q16p16 = span_x * span_y
mant8 normalized to 128..255
lut_index = mant8 - 128
recip_lut[index] = round_nearest_even(2^23 / mant8)
density_q8p8 reconstructed by exponent-dependent shifting
f13 = clamp_u7(bank_round_shift(density_q8p8 * 105, 16))
```

讲法：
 - 原始 density 是除法，硬件代价高。
 - v1.4a 把 reciprocal 变成小 LUT + shift + fixed-point multiply。
 - 只改 density，不混入 mean/range 的新变化，保证版本边界清晰。

4. RTL vs mirror 验证页

| Check | Result |
|---|---:|
| Board samples | 1000 |
| Full 21-byte RTL vs Python mirror | 1000/1000 |
| f13 RTL vs Python mirror | 1000/1000 |
| Mean abs error vs mirror | 0.000 |
| Max abs error vs mirror | 0 |

讲法：
 - 这证明 RTL 正确实现了选定的硬件近似。
 - 后续 software golden 差异不是 RTL bit mismatch，而是 approximation gap。

Week 2 结论：

> 完成了 density exact-LUT 的硬件化和板级 bit-level 对拍，v1.4a RTL 与 Python mirror 在 1000 个样本上 full-vector 完全一致。

### Week 3：板级实验结果、QMLP 任务级指标与风险收敛

汇报主题：

- 汇总 v1.4a 最终板级结果。
- 解释为什么 feature match 67.10% 但 QMLP agreement 95.20% 是合理的。
- 补充 class balance / confusion matrix。
- 给出剩余风险：f11 `eig_major` 统计几何 proxy。

可做 PPT 页：

1. 最终实验结果页

| Metric | Value |
|---|---:|
| RTL vs Python mirror full 21-byte | 1000/1000 |
| f13 density RTL vs Python mirror | 1000/1000 |
| Software golden vs board feature match | 67.10% |
| Mean abs int8 error | 0.791 |
| Max abs int8 error | 122 |
| QMLP prediction agreement | 95.20% |
| Changed predictions | 48/1000 |
| Cycles avg/min/max | 397 / 387 / 589 |

讲法：
 - v1.4a 是当前论文硬件基线。
 - 不声称硬件 Feature21 完全等价软件 Feature21。
 - 声称“硬件近似与 Python mirror bit 一致，并保持较高任务级预测一致性”。

2. Feature match vs QMLP agreement 解释页

| 指标 | 含义 |
|---|---|
| 67.10% feature match | 21 个 int8 byte 逐字节比较 |
| 95.20% QMLP agreement | 1000 个样本中最终分类是否一致 |

讲法：
 - byte-level mismatch 很严格，很多差异是小幅 int8 误差。
 - QMLP 对小误差有一定容忍，关键看是否跨越分类边界。
 - 因此 67.10% feature match 与 95.20% prediction agreement 可以同时成立。

3. 分类结果页

1000-sample subset class balance:

| Class | Count |
|---|---:|
| pedestrian | 500 |
| vehicle | 500 |

Confusion matrix:

| Input features | Confusion matrix | Accuracy |
|---|---|---:|
| Software-golden Feature21 -> software QMLP | `[[397, 103], [0, 500]]` | 89.70% |
| Board Feature21 -> software QMLP | `[[411, 89], [0, 500]]` | 91.10% |

讲法：
 - 子集是均衡的 500/500。
 - board-feature accuracy 在这个固定子集上略高，但不能泛化成模型提升。
 - 论文里更应该强调 agreement，而不是过度强调 accuracy 增加。

4. 剩余误差归因页

| Feature | Evidence | Interpretation |
|---|---:|---|
| f13 `density_2d` | 0/48 changed prediction mismatches | 已不是剩余翻转来源 |
| f11 `eig_major` | 33/48 changed predictions mismatch | 主要剩余风险 |
| f1 `mean_x` | 47/48 mismatch | 次要残差 |
| f9 `centroid_range` | 43/48 mismatch | 几何 proxy 残差 |
| f10 `azimuth_span` | 44/48 mismatch | 几何 proxy 残差 |

5. f11 limitation 页

| 项目 | 内容 |
|---|---|
| 软件公式 | `eig_max(cov([[x], [y]]))` |
| 当前硬件 proxy | `max(span_x >> 2, span_y >> 2)` |
| max-error samples | 332 / 333 / 336 / 591 / 592 |
| golden f11 | 127 |
| board f11 | 5 |
| 结论 | eig/statistical geometry proxy limitation |

讲法：
 - 这不是 density exact-LUT 的问题。
 - 这也不是 RTL vs mirror 对拍失败。
 - 它反映了当前 span-based proxy 与软件 covariance eigenvalue 的本质差异。
 - 作为 future work，不在当前版本继续改 RTL。

6. 性能与 CPU baseline 页

| 项目 | 状态 |
|---|---:|
| Hardware Feature21 cycles avg/min/max | 397 / 387 / 589 |
| Total points | 26642 |
| Avg points/sample | 26.642 |
| Approx cycles/point | 14.90 |
| CPU-only Feature21 baseline | TODO: no reliable existing data |

讲法：
 - 当前可以报告硬件 Feature21 latency。
 - 不能 claim CPU vs hardware Feature21 speedup，因为没有可靠 CPU-only Feature21 preprocessing baseline。
 - 已有 CPU-only QMLP 数据是 QMLP forward，不是 Feature21 preprocessing，不能混用。

Week 3 结论：

> v1.4a 已形成可用于论文/周报的闭环结果：1000/1000 RTL-mirror match，95.20% QMLP agreement；剩余风险集中在 f11 eig/statistical geometry proxy，作为 future work 收敛。

## 2. 如果只讲 2 周，可以这样压缩

### Week A：Feature21 定义与硬件化路径

合并 Week 1 + Week 2 前半：

- 输入数据：k=7 融合后的变长点集，每点 `[x, y, doppler, rcs]`。
- 输出：21 维 int8 特征。
- 复杂特征：division / sqrt / atan2 / eigen / density。
- 建立 SW golden -> Python mirror -> RTL -> Board 验证链路。
- v1.3 定位到 f13 density 是关键分类翻转来源。

### Week B：v1.4a 密度优化与板级结果

合并 Week 2 后半 + Week 3：

- 实现 density exact-LUT 硬件近似。
- 1000/1000 RTL vs Python mirror full-vector match。
- Software golden vs board feature match 67.10%。
- QMLP prediction agreement 95.20%。
- class balance / confusion matrix。
- f11 eig_major 作为 future work。

## 3. 周报中建议使用的图

### 图 1：数据路径图

```text
k=7 fused point set
  each point: x, y, doppler, rcs
        ↓
AXI DMA MM2S
        ↓
Feature21 fixed-point preprocessor
        ↓
21 x int8 feature vector
        ↓
QMLP inference
        ↓
prediction / validation
```

### 图 2：验证链路图

```text
Software golden
      │ feature / logits / labels
      ▼
Python HW mirror
      │ bit-consistent approximation model
      ▼
RTL / Chisel
      │ board compact dump
      ▼
Board validation
      │
      ├─ RTL vs mirror: implementation correctness
      ├─ Board vs software: approximation error
      └─ QMLP agreement: task-level impact
```

### 图 3：误差收敛图

```text
v1p3:
  QMLP agreement = 79.90%
  changed = 201/1000
  f13 in changed = 199/201

v1.4a:
  QMLP agreement = 95.20%
  changed = 48/1000
  f13 in changed = 0/48
```

## 4. PPT 可直接使用的结论页

标题：Feature21 处理模块阶段性结论

- 输入口径已收敛：硬件输入为 k=7 融合后的变长点集，每点包含 `x, y, doppler, rcs`。
- 完成 21 维 int8 特征硬件近似实现和板级验证。
- 建立四级验证链路：SW golden -> Python HW mirror -> RTL -> Board。
- v1.4a density exact-LUT 在 1000 样本上达到 RTL vs Python mirror full-vector `1000/1000`。
- 板级 Feature21 与软件 golden 的 byte-level match 为 `67.10%`，mean abs int8 error 为 `0.791`。
- 任务级 QMLP prediction agreement 达到 `95.20%`，changed predictions 为 `48/1000`。
- f13 density 已不再是剩余翻转来源；剩余风险集中在 f11 `eig_major` 等 statistical geometry proxy。
- 当前阶段应冻结 v1.4a 作为论文/周报基线，后续 std/eig proxy、hardware-aware training、CPU-only Feature21 baseline 作为 future work。

## 5. 口径提醒

周报里建议避免：

- 不要说硬件 Feature21 完全等价软件 Feature21。
- 不要说硬件做了 k=7 融合；融合在 Feature21 之前。
- 不要说 v1.4a 包含 `mean_recip` 或 `range_piecewise`。
- 不要 claim CPU vs hardware Feature21 speedup；目前没有可靠 CPU-only Feature21 preprocessing baseline。
- 不要把 91.10% board-feature subset accuracy 说成通用精度提升。

建议说：

- 硬件 Feature21 是软件 Feature21 的 hardware-friendly fixed-point approximation。
- RTL 与 Python mirror 在当前 1000 样本上 bit-level 一致。
- 任务级评估使用 QMLP prediction agreement。
- 当前结果足以作为论文/周报硬件基线。

