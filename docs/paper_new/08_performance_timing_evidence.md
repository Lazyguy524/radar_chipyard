# 性能与时序证据

## 75 MHz 时序

Feature21/QMLP promoted 75 MHz candidate：

| 指标 | 值 |
| --- | --- |
| WNS | `+0.040 ns` |
| TNS | `0.000 ns` |
| WHS | `+0.017 ns` |

解释：经过 QMLP、Feature21、UART-TSI pipeline/route 优化后，最终 limiter 转移到 Rocket frontend/icache/fetch-queue/control 到 execute decode 的 route-dominated path。普通 QMLP、Feature21 quant/writeback、UART-TSI TL-A 不再是最终 top path。

RoCC pipelined 75 MHz candidate：

| 指标 | 值 |
| --- | --- |
| WNS | `+0.004 ns` |
| TNS | `0.000 ns` |
| WHS | `+0.009 ns` |

解释：一周期 RoCC 尝试 WNS `-0.330 ns`，pipelined RoCC 修复 DSP/response path 后 timing-clean，但 slack 很薄。

## Feature21

2026-06-08 Feature21 v1.4a compact board dump：

| 指标 | 值 |
| --- | --- |
| samples | `1000` |
| cycles_avg | `455` |
| cycles_min | `420` |
| cycles_max | `662` |
| exact-LUT mirror match | `1000/1000` |
| QMLP prediction agreement | `95.20%` |
| changed predictions | `48/1000` |

口径：这是 Feature21 dump + host/software validation report，不是 board-side full QMLP hardware chain。

## QMLP

2026-06-08 direct QMLP validation：

| 指标 | 值 |
| --- | --- |
| large golden | `1000` samples PASS |
| boundary cases | `54` cases PASS |
| hw_cycles_avg | `2213` |

2026-04-16 older optimized DMA profile：

| 指标 | 值 |
| --- | --- |
| QMLP kernel | `1301 cycles/sample @ 50 MHz` |
| batch=511 DMA interval | only about `5 cycles/sample` over QMLP kernel |

口径：旧 profile 可用于说明 batch/no-reset DMA 形态下搬运接近计算下限，但不能直接替代 2026-06-08 75 MHz direct validation。

## CPU-only 与 RoCC

2026-06-08 CPU-only QMLP profile：

| 指标 | 值 |
| --- | --- |
| infer_avg | `168349` |
| dot_mac_upper | `93.43%` |
| quant_relu | `5.66%` |
| control_resid | `0.90%` |

2026-06-09 scalar-vs-RoCC QMLP profile：

| 指标 | Scalar | RoCC `rqdot4` |
| --- | --- | --- |
| count | `1600` | `1600` |
| cycles_avg | `168203` | `62532` |
| instret_avg | `26686` | `35016` |
| sink | `{-437,3496}` | `{-437,3496}` |

RoCC ops：

| 指标 | 值 |
| --- | --- |
| rqdot4_avg | `848` |
| scalar_tail_macs_avg | `64` |
| rqscale8_avg | `96` |
| packed_mac_coverage_x100 | `9814` |
| speedup_x1000 | `2689` |
| speedup | `2.689x` |

口径：这是 QMLP kernel/profile 的 custom instruction 路径对比，不是完整 Feature21+QMLP e2e。

## 论文引用规则

- 写 QMLP RTL 计算能力：优先引用 `hw_cycles_avg` 或 `hw_avg`，并标明频率和 bitstream。
- 写 DMA 是否空拍：引用 no-reset/batch profile，不引用 debug-heavy validation e2e。
- 写 RoCC 收益：引用 scalar-vs-RoCC profile，明确只覆盖 `rqdot4` scope。
- 写 Feature21：引用 compact dump、exact-LUT mirror 和 classification agreement。
- 写 full-chain：当前必须保守，除非后续有专门 full hardware chain board validation。
