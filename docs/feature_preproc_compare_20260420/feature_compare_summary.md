# 14/18/21维雷达特征模型对比与硬件前处理交付说明

## 结论先行

- 当前硬件已经板测通过的是 `k=7 + rcs21 + 21->64->32->2` QMLP，QMLP 本体不是瓶颈。
- 14维和18维均已补齐 INT8 参数导出、1000组 golden、边界样本和 C 端前处理 benchmark，但尚未板测。
- 如果硬件端优先降低风险，第一阶段建议做 `14维前处理 + 14维QMLP`，不要做“14维硬件 + 软件补7维 + 21维QMLP”。
- 如果14维精度不满足论文展示，推荐第二阶段转 `21维完整前处理`；18维目前软件精度不优于14维，不是强折中。

## 模型对比

| 维度 | 模型名 | 结构 | 使用RCS | 参数量 | MAC/sample | QAT acc | QAT macro-F1 | INT C acc | INT C macro-F1 | 导出状态 |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 14 | k7_compact14 | `14->64->32->2` | 否 | 3106 | 3008 | 0.913520 | 0.902306 | 0.928975 | 0.919102 | 已导出 |
| 18 | k7_baseline18 | `18->64->32->2` | 否 | 3362 | 3264 | 0.908657 | 0.896546 | 0.920852 | 0.909914 | 已导出 |
| 21 | k7_rcs21 | `21->64->32->2` | 是 | 3554 | 3456 | 0.964551 | 0.958411 | 0.972170 | 0.967020 | 已导出 |

说明：`float_fp32_metrics` 当前没有单独保留；现有 checkpoint 是 QAT student。14/18/21 的 INT C-trace 是本次交付重新按导出参数跑完整 test split 得到；只有21维已有硬件板级 QMLP 对拍记录。

## 路径索引

| 维度 | checkpoint | config | 本次release目录 |
|---:|---|---|---|
| 14 | `logs/input_dim_window_grid_2026-04-14/train/compact14_k7_nokd/student_qat.pt` | `configs/input_dim_window_grid_2026-04-14/compact14_k7_nokd.yaml` | `releases/feature_preproc_compare_20260420/feature14` |
| 18 | `logs/baseline18_recheck_2026-04-14/train/k7_baseline18_nokd/student_qat.pt` | `configs/baseline18_recheck_2026-04-14/k7_baseline18_nokd.yaml` | `releases/feature_preproc_compare_20260420/feature18` |
| 21 | `logs/multiframe_k_sweep_rcsfix_2026-04-14/train/k7_rcs21_nokd/student_qat.pt` | `configs/multiframe_k_sweep_rcsfix_2026-04-14/k7_rcs21_nokd.yaml` | `releases/feature_preproc_compare_20260420/feature21` |

## precision / recall / confusion matrix

| 维度 | 口径 | macro precision | macro recall | pedestrian P/R | vehicle P/R |
|---:|---|---:|---:|---:|---:|
| 14 | INT C-trace | 0.904849 | 0.940864 | 0.823346/0.970386 | 0.986352/0.911342 |
| 18 | INT C-trace | 0.895880 | 0.931609 | 0.810994/0.958323 | 0.980765/0.904895 |
| 21 | INT C-trace | 0.963821 | 0.970394 | 0.942284/0.965983 | 0.985358/0.974805 |

- 14维 INT C-trace confusion matrix `[[ped->ped, ped->veh], [veh->ped, veh->veh]]` = `[[16089, 491], [3452, 35484]]`
- 18维 INT C-trace confusion matrix `[[ped->ped, ped->veh], [veh->ped, veh->veh]]` = `[[15889, 691], [3703, 35233]]`
- 21维 INT C-trace confusion matrix `[[ped->ped, ped->veh], [veh->ped, veh->veh]]` = `[[16016, 564], [981, 37955]]`

## 14/18/21关系

- 14维是21维的子集：`[n_points, mean_x, mean_y, std_x, std_y, span_x, span_y, centroid_range, azimuth_span, eig_major, eig_minor, density_2d, doppler_mean, doppler_std]`。
- 18维是21维的子集：14维之外还包含 `range_min, range_max, doppler_min, doppler_max`，顺序上是 baseline18 的完整前18项。
- 21维相比14维多7项：`range_min, range_max, doppler_min, doppler_max, rcs_mean, rcs_std, rcs_max`。
- 这7项中 `range_min/range_max/rcs_std` 涉及 sqrt 或 std；`rcs_mean/rcs_std` 涉及除法；`doppler_min/max` 和 `rcs_max` 主要是比较器。
- 但要特别注意：复杂操作并不只在新增7维中。14维本身已经包含 `std_x/std_y/doppler_std/centroid_range/azimuth_span/eig/density`，因此14维不是“纯简单特征”。

## 多帧融合和输入格式

- 多帧融合发生在特征计算之前。
- 当前 QMLP 输入是 k=7 融合后的 int8 特征，不是单帧特征。
- 一个 sample 表示一个目标候选/track 在当前帧的融合点簇；不是整帧所有目标。
- 当前融合逻辑使用同一 `sequence_id/sensor_id/track_id` 的当前帧和历史最多6帧点集拼接。
- 点数不固定；本包 k=7 test golden 使用 offset 描述变长点集，训练打包摘要中 fused_points_mean=37.02，max=465。
- 当前不做 pad/truncate 后再算特征；特征直接从变长融合点集统计得到。pad/truncate 主要给 teacher/点云分支保留，不是 student rcs21 的必要输入。
- 当前软件融合依赖 RadarScenes 的 `track_id`，不是 DBSCAN 的单帧 `cluster_id`。如果硬件自己做 k=7 融合，需要前级提供稳定 object/track id，或另做目标关联。
- 如果硬件只接收“融合后的中间量”，建议接口就是本包 golden 的格式：`float/fixed point [x,y,doppler,rcs]` 变长点数组 + `offsets`。
- 如果硬件自己完成 k=7 融合，最小缓存字段为 `{valid, sequence/sensor/object_id, frame_order, point_count, points[x,y,doppler,rcs]}`；缓存深度至少覆盖每个活动目标最近7帧，单目标点数需按系统最大点数设上限。

## C前处理耗时参考

- 测试实现: x86_64 C -O3 benchmark, data preloaded from binary files; timing excludes file I/O and model loading
- CPU: Intel(R) Xeon(R) Gold 6258R CPU @ 2.70GHz
- 样本数: 1000，repeat: 200，不含文件I/O。
- 14维前处理+量化: 1.056 us/sample
- 18维前处理+量化: 0.899 us/sample
- 21维前处理+量化: 0.887 us/sample
- 21维完整特征计算不含量化: 0.837 us/sample
- 注意：这个 C benchmark 为了统一对齐，内部先计算完整21维再选择14/18子集，所以 14/18/21 的耗时差异不能直接视为最优 RTL 差异；硬件若只实现子集，14维理论资源会低于21维。
- 多帧融合/目标关联维护没有计入该 C 耗时；本包计时口径是“已获得融合点集后，生成 int8 feature vector”。

## 推荐实现顺序

| 方案 | 内容 | 难度 | sqrt/division | golden对拍 | 精度风险 | 建议 |
|---|---|---|---|---|---|---|
| A | 14维前处理 + 14维QMLP | 中 | 有，14维也含 std/eig/angle/density | 容易，本包已给golden | 明显低于21维 | 适合第一阶段风险收敛 |
| B | 14维硬件 + 软件补7维 + 21维QMLP | 高 | 仍需要软件复杂特征 | 边界模糊 | 端到端收益小 | 不推荐，接口和论文叙事都不干净 |
| C | 18维前处理 + 18维QMLP | 中高 | 比14多range min/max | 容易 | 当前效果不优于14 | 仅作为对照，不优先 |
| D | 21维前处理 + 21维QMLP | 高 | 完整包含RCS统计和range | 容易但RTL复杂 | 精度最好 | 第二阶段/最终论文完整方案 |

明确建议：第一阶段硬件先做 A；如果时间允许，再直接做 D。不要把 B 当主线。若选择 A，必须使用本包 `feature14/qmlp_params_14.*`，不能继续喂当前21维 QMLP。若14维指标无法接受，18维不是当前最强折中，优先评估21维完整前处理。
