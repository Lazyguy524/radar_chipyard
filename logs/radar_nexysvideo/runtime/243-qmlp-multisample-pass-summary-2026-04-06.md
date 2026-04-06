# QMLP 多样本板测摘要

更新时间：2026-04-06

## 1. 测试入口

- 日志：
  - [242-run-integrated-regression-qmlp-multisample-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/242-run-integrated-regression-qmlp-multisample-2026-04-06.log)
- 入口程序：
  - [radar-axi-dma-regression.c](/home/soooarr/chipyard/tests/radar-axi-dma-regression.c)

## 2. 测试范围

本轮在原有单 ELF 综合回归中，新增了 `QMLP` 多样本回归，共 `8` 组输入：

- `golden_base`
- `zero`
- `alternating_perturb`
- `sparse_keep3`
- `sign_flip_even`
- `half_scale`
- `offset_plus`
- `offset_minus`

每组样本都执行完整链路：

- `DDR -> MM2S -> RadarAXISQMLP -> S2MM -> DDR`

并同时检查：

- DDR 回写 logits
- `QMLP_LAST_LOGIT0/1`
- `QMLP_IN_BEATS / OUT_BEATS / FRAME_COUNT / LAST_KEEP`
- `QMLP_RUN_CYCLES`

## 3. 关键结果

本轮所有 `8` 组样本均对拍通过，最终：

- `AXI_DMA_REGRESSION_PASSED`
- `QMLP passed`

关键计数器稳定为：

- `IN=4`
- `OUT=1`
- `FRAMES=1`
- `KEEP=0x000000ff`

## 4. 性能摘要

日志打印的多样本 summary 为：

- `cases=8`
- `hw_cycles_avg=3554`
- `hw_cycles_min=3554`
- `hw_cycles_max=3554`
- `e2e_cycles_avg=8933432`
- `inf_per_sec=14068`

其中：

- `hw_cycles` 表示 `QMLP` 硬件内部计算阶段的周期计数
- `e2e_cycles` 表示软件发起 DMA 到完成轮询返回的端到端周期

在当前 `50 MHz` 下，可直接得到：

- 单次推理硬件计算延迟约 `3554 / 50e6 = 71.08 us`
- 端到端单次调度延迟约 `8933432 / 50e6 = 178.67 ms`

## 5. 当前结论

当前已经确认：

1. 第一版固定 `21 -> 64 -> 32 -> 2 INT8 QMLP` 加速器已完成板级多样本验证
2. 当前硬件本体计算延迟稳定，样本间无波动
3. 当前主要开销不在 `QMLP` 算子本体，而在 bare-metal + DMA + `uart_tsi` 这条板级 bring-up/调度链
4. 后续如果要做论文中的性能提升，应重点转向：
   - 更通用的 PE/MAC 阵列
   - 更高复用的数据流
   - 更轻的软件调度与批处理方式
