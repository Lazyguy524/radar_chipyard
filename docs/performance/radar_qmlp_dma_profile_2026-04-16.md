# QMLP DMA 高性能 Profile 与 SoC BRAM 资源记录

日期：2026-04-16  
对象：`RadarAXIMMIONexysVideoConfig` / Nexys Video / `xc7a200tsbg484-1`  
参考 bitstream：当前 `RadarAXIMMIONexysVideoConfig` word-bank QMLP 版本  
参考报告：`fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/report/utilization.txt`

## 1. 本轮目标

本轮不是继续使用原 `dma_run_stream_once()` 的 reset-per-batch 测试，而是新增一个独立 profile 程序：

- `tests/radar-axi-dma-qmlp-profile.c`
- `tests/radar-axi-dma-qmlp-profile.riscv`

该程序使用当前 `large_golden` 的 `1000` 组样本，按不同 batch size 统计：

- CPU 写 input / 清 output buffer 的 prepare cycles
- QMLP 控制寄存器 wait / clear / enable 的 control cycles
- no-reset DMA 事务本体 cycles
- counter check / golden compare / cleanup 的 verify cycles
- QMLP 硬件内部 `QMLP_RUN_CYCLES`

## 2. 高性能 DMA 流程

新增 profile 使用的流程是：

```text
初始化阶段：
  dma_stream_prepare_noreset()
    -> reset MM2S 一次
    -> reset S2MM 一次
    -> 清状态
    -> 置 RUN

每个 batch：
  准备输入与输出 buffer
  qmlp_wait_idle / clear / enable
  dma_run_stream_once_noreset()
    -> 检查 DMA 可复用
    -> 清状态
    -> 写 S2MM 地址/长度
    -> 写 MM2S 地址/长度
    -> 等 MM2S done
    -> 等 S2MM done
  读取 QMLP counters / logits 对拍
```

关键区别：

- 不再每个 batch 都 reset DMA
- timed DMA 区间内没有正常路径 `printf`
- batch size 会测试 `1 / 8 / 32 / 64 / 256 / 511`
- 原 `radar-axi-dma-qmlp-validation.c` 保留不变，继续作为保守正确性验证程序

当前 AXI DMA `Width of Buffer Length Register` 为 `14` bit，单次 DMA 最大长度为 `16383` B。QMLP 输入为 `32 B/sample`，所以单次合法最大 batch 为 `511` samples；`1000` samples 需要拆包或重配 DMA IP。

## 3. 当前 SoC BRAM 数据

Vivado post-route hierarchical utilization：

| 层级 | RAMB36 | RAMB18 | 说明 |
|---|---:|---:|---|
| `NexysVideoHarness` 全设计 | 2 | 14 | 整个 SoC + MIG shell + DMA + QMLP |
| `chiptop0/system` | 0 | 12 | Rocket SoC 内部 cache/tag 为主 |
| `radarDMA` | 2 | 2 | AXI DMA 内部 MM2S/S2MM FIFO |
| `RadarAXISQMLP` | 0 | 0 | QMLP 权重 ROM 为 distributed ROM / LUT，不占 BRAM |

等效 RAMB36 估算：

```text
2 RAMB36 + 14 RAMB18 / 2 = 9 RAMB36-equivalent
9 / 365 ~= 2.47%
```

原始 BRAM bit 容量：

```text
2 * 36864 + 14 * 18432 = 331776 bit = 40.5 KiB
```

主要 BRAM 明细来自 `report_ram_utilization -detail`：

| 用途 | Primitive | 数量 | 典型结构 |
|---|---:|---:|---|
| ICache data array | RAMB18E1 | 2 | `512 x 32` 两路 |
| ICache tag array | RAMB18E1 | 1 | `64 x 26` |
| DCache data array | RAMB18E1 | 8 | `512 x 8` 八块 |
| DCache tag array | RAMB18E1 | 1 | `64 x 27` |
| DMA MM2S FIFO | RAMB36E1 + RAMB18E1 | 1 + 1 | `128 x 72` + `128 x 2` |
| DMA S2MM FIFO | RAMB36E1 + RAMB18E1 | 1 + 1 | `128 x 72` + `128 x 2` |

结论：

- 当前 BRAM 占用很低，剩余空间充足。
- 当前 QMLP 没有占用 BRAM。
- 如果后续要把权重改成 BRAM ROM 或做前处理缓存，资源容量不是主要瓶颈，主要风险会转移到时序、读端口数和控制复杂度。

## 4. 已知性能基线

当前已通过板测的保守 validation 数据：

| 测试 | 样本数 | batch | QMLP kernel | e2e |
|---|---:|---:|---:|---:|
| `large_golden` validation | 1000 | 8 | `1301 cycles/sample` | `1117247 cycles/sample` |
| `large_golden` validation @50MHz | 1000 | 8 | `26.02 us/sample` | `22.345 ms/sample` |
| `boundary_cases` validation | 54 | 1 | `1301 cycles/sample` | `8941730 cycles/sample` |
| `boundary_cases` validation @50MHz | 54 | 1 | `26.02 us/sample` | `178.835 ms/sample` |

说明：

- 上表 e2e 来自 reset-per-batch 保守验证，不代表优化后的 DMA 性能。
- 该 e2e 包含每个 batch 两次 DMA reset 和 reset 内部打印，主要用于正确性验证，不适合作为最终性能论证。

历史 batch-only 板测数据：

| 测试 | batch | QMLP kernel | e2e |
|---|---:|---:|---:|
| `v2.8 reset_batch_per_sample` | 8 | `1301 cycles/sample` | `1157261 cycles/sample` |
| @50MHz | 8 | `26.02 us/sample` | `23.145 ms/sample` |

## 5. 本轮 profile 构建状态

构建通过：

- build log：`logs/radar_nexysvideo/runtime/564-build-qmlp-profile-envfixed-2026-04-16.log`
- ELF size：`logs/radar_nexysvideo/runtime/567-size-qmlp-profile-2026-04-16.txt`

ELF size：

```text
text=34200 data=16 bss=0 dec=34216
```

源码改动留档：

- `logs/radar_nexysvideo/runtime/566-qmlp-profile-source-diff-2026-04-16.patch`
- `logs/radar_nexysvideo/code_backups/568-radar-axi-dma-qmlp-profile-after-2026-04-16.c`
- `logs/radar_nexysvideo/code_backups/569-tests-Makefile-after-qmlp-profile-2026-04-16.mk`

## 6. 当前板测状态与本轮修正

2026-04-16 追加修正：

- profile batch 从 `1 / 8 / 32 / 64 / 1000` 改为 `1 / 8 / 32 / 64 / 256 / 511`
- 输出 buffer 从 `RADAR_BUF_REGION_IN + 0x1000` 改到 `RADAR_BUF_REGION_MID0 + 0x0`
- 修正原因：
  - `batch=1000` 输入长度 `32000 B` 超过当前 DMA 14-bit LENGTH 上限
  - `RADAR_BUF_REGION_IN + 0x1000` 对大 batch 会与输入区域重叠

## 7. 当前板测结果

2026-04-16 clean reset 后，profile 已在当前 bitstream 上通过：

- 运行日志：`logs/radar_nexysvideo/runtime/598-qmlp-profile-after-clean-reset-2026-04-16-2026-04-16-212759.log`
- wrapper：`logs/radar_nexysvideo/runtime/598-qmlp-profile-after-clean-reset-wrapper-2026-04-16.log`
- 结果：`AXI DMA qmlp profile PASSED`

实测分阶段平均 cycles/sample：

| batch | samples | prep_avg | ctrl_avg | dma_avg | verify_avg | hw_avg | dma time @50MHz | hw time @50MHz |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1000 | 1148 | 60 | 1622 | 247 | 1301 | 32.44 us | 26.02 us |
| 8 | 1000 | 1142 | 7 | 1345 | 107 | 1301 | 26.90 us | 26.02 us |
| 32 | 1000 | 1142 | 2 | 1315 | 92 | 1301 | 26.30 us | 26.02 us |
| 64 | 1000 | 1142 | 1 | 1311 | 90 | 1301 | 26.22 us | 26.02 us |
| 256 | 1000 | 1142 | 0 | 1307 | 88 | 1301 | 26.14 us | 26.02 us |
| 511 | 1000 | 1142 | 0 | 1306 | 88 | 1301 | 26.12 us | 26.02 us |

关键结论：

- no-reset DMA 流程下，`dma_avg` 已从 batch=1 的 `1622 cycles/sample` 收敛到 batch=511 的 `1306 cycles/sample`。
- QMLP 内部 `hw_avg` 全部稳定为 `1301 cycles/sample`，即 `26.02 us/sample @ 50MHz`。
- batch=511 时，DMA 流本体仅比 QMLP 内部 kernel 多 `5 cycles/sample`，说明 AXI-Stream/DMA 流水已经非常接近硬件计算下限。
- 当前 `prep_avg ~= 1142 cycles/sample` 是 CPU 写 input / 清 output buffer 的软件准备开销；如果真实系统由上游前处理模块直接产生 DDR/stream 数据，这部分不应简单计入 QMLP kernel 本体。
- `verify_avg ~= 88 cycles/sample` 是测试程序读取 counter、golden compare、cleanup 的验证开销，不属于实际部署必要开销。

## 8. 与保守 validation 的差异

保守 validation 的 e2e 很大，是因为它面向正确性验证，包含 reset-per-batch、打印、逐样本/逐批检查等流程；profile 的 timed DMA 区间删除了正常路径打印，并且 DMA 只在初始化阶段 reset。

对比重点：

- 论文中若论证 QMLP RTL 计算能力，应使用 `hw_avg = 1301 cycles/sample`。
- 若论证 DMA 流式推理能力，应使用 no-reset profile 的 `dma_avg`，尤其是 batch=256/511。
- 若论证完整 demo 程序体验，不应直接使用保守 validation 的 e2e 作为优化后性能上限。

## 9. 当前仍需注意的测试口径

- 每次更换 ELF 前需要短按并松开 `CPU_RESET`。
- 如果不 reset，上一轮程序的 `tohost/fromhost` 状态可能污染下一轮 `selfcheck`。
- 当前 profile 的 batch=511 已是 14-bit DMA length 下限内的最大单次 batch；若要单次跑 1000 samples，需要拆包或把 AXI DMA `Width of Buffer Length Register` 提高到至少 15 bit。
