# QMLP PE Array v2.5 Board Pass Summary (2026-04-09)

## 1. 结论

`v2.5` 已经完成板级验证，通过了：

- `hello + selfcheck @115200`
- `integrated regression + selfcheck @115200`
- `QMLP` 多样本回归

对应日志：
- `hello+selfcheck`：
  [v2p5-hello-selfcheck-nomsip-2026-04-09-175245.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/v2p5-hello-selfcheck-nomsip-2026-04-09-175245.log)
- 综合回归：
  [v2p5-integrated-regression-115200-after-reset-2026-04-09-180015.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/v2p5-integrated-regression-115200-after-reset-2026-04-09-180015.log)

## 2. 关键修复效果

相对 `v2.4`，`v2.5` 已经把此前板上暴露出的固定坏窗问题压下去。

关键地址单点探针：
- `0x80000980` 写回正常
  - [340-v2p5-probe-980-write-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/340-v2p5-probe-980-write-2026-04-09.log)
  - [341-v2p5-probe-980-read-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/341-v2p5-probe-980-read-2026-04-09.log)
- `0x80000988` 写回正常
  - [342-v2p5-probe-988-write-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/342-v2p5-probe-988-write-2026-04-09.log)
  - [343-v2p5-probe-988-read-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/343-v2p5-probe-988-read-2026-04-09.log)

这说明 `v2.4` 上暴露的 `0x80000980..0x8000098c` 固定 16B 窗口异常，在 `v2.5` 上已经不再出现。

## 3. 回归结果

综合回归日志中确认：
- `Self check success`
- `AXI_DMA_REGRESSION_PASSED`
- `QMLP passed`

## 4. QMLP 多样本结果

`8` 组样本全部通过，所有 case 的硬件 logits 与 golden 一致。

多样本性能汇总：
- `cases = 8`
- `hw_cycles_avg = 1301`
- `hw_cycles_min = 1301`
- `hw_cycles_max = 1301`
- `e2e_cycles_avg = 8915389`
- `inf_per_sec = 38431`
- `input_MBps_x100 = 122982321`

## 5. 与旧版 baseline 的对比

旧固定 QMLP baseline：
- `hw_cycles_avg = 3554`

`v2.5`：
- `hw_cycles_avg = 1301`

因此当前 `v2.5` 相比旧 baseline 的硬件本体周期数下降明显，约为：

- `3554 / 1301 ≈ 2.73x`

## 6. 当前定位

`v2.5` 是目前最完整的一版：

- 保留了 `4-lane PE` 阵列
- 离线时序显著改善
- 板上固定坏窗问题已修复
- 老链路综合回归恢复通过
- `QMLP` 多样本也恢复通过

## 7. 建议

后续应以 `v2.5` 作为新的 PE 阵列基线，继续推进：

1. 将该版本同步到主文档与主记录页
2. 对 `v2.5` 与旧 baseline 做正式性能对比
3. 继续研究数据搬运与多样本调度优化
