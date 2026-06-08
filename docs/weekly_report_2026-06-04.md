# 2026-06-04 组会周报整理

## 建议汇报主线

本周建议只讲两条主线，不展开所有调试细节：

1. FullChain v2 四路 RX 多通道链路完成 Chipyard/Nexys Video 集成，并完成 50 MHz 板级 DMA E2E golden 对拍。
2. 对 Feature21 + QMLP 的频率上限做了定位，从“是不是某一个模块拖频率”推进到“60 MHz 下 QMLP、Feature21、UART-TSI/FBUS 同时接近临界”的结论。

一句话总结可以放第一页：

> 本周完成了 4RX 多通道 radar fullchain 的 50 MHz bitstream、资源/时序归档和板级 golden 验证；同时对 Feature21/QMLP 系统频率上限做了 post-route 证据定位，确认 50 MHz 是稳定点，60 MHz 需要对 QMLP MAC、Feature21 量化写回和 UART-TSI request path 分别加流水。

## 推荐 6 页组会结构

### 1. 本周目标与结果

讲什么：

- 目标 1：把多通道 FullChain v2 从独立 RTL/SW 包接入 Chipyard SoC。
- 目标 2：完成可上板 bitstream、RISC-V 测试程序、UART 板级验证。
- 目标 3：解释当前 Chipyard radar 系统为什么频率主要停在 50 MHz 附近。

可放结果表：

| 工作项 | 本周状态 | 关键结果 |
| --- | --- | --- |
| FullChain v2 4RX 集成 | 完成 | 50 MHz bitstream 过 post-route timing |
| FullChain v2 板级验证 | 完成 | `FullChain DMA E2E test PASSED`，16384 个 128-bit golden beat 全比较 |
| 多通道资源分析 | 完成 | LUT 71.71%，BRAM Tile 65.21%，DSP 44.32% |
| 51.282 MHz/cache 候选 | 完成失败归因 | route 完成但 timing failed，WNS -3.835 ns |
| Feature21/QMLP 60 MHz 定位 | 完成阶段性定位 | WNS -1.578 ns，QMLP/Feature21/TSI 三类路径共同临界 |

### 2. 多通道部署：系统结构

讲什么：

- 本周接入的是 `fullchain_v2/260601_4C`，不是旧单通道版本。
- 链路为 4 路 RX 分发、每路 FFT/cache、功率合并、2D CFAR 输出。
- Chipyard 侧用 AXI-Lite 控制、AXI DMA MM2S/S2MM 搬运数据。

建议图示：

```text
DDR -> AXI DMA MM2S
    -> 32-bit AXIS input
    -> rx_axis_dispatcher
    -> 4x single_fft_chain / cache / doppler FFT
    -> 4-way power_merge
    -> 2D CFAR
    -> 128-bit goal stream
    -> 128-to-64 downsizer
    -> AXI DMA S2MM -> DDR
```

关键参数：

| 项 | 值 |
| --- | --- |
| Range points | 128 |
| Doppler points | 128 |
| RX enable mask | `0xF` |
| 输入 | `65536 x 32-bit` |
| 输出 golden | `16384 x 128-bit` |
| Expected detections | 5 |
| Version | `0x20260527` |

截图/证据来源：

- 结构说明：`/home/soooarr/chipyard_copy/fullchain_v2/260601_4C/HW_SW_README.md`
- Chipyard wrapper：`/home/soooarr/chipyard_copy/fpga/src/main/scala/nexysvideo/FullChainAXIDMA.scala`
- 多通道核心：`/home/soooarr/chipyard_copy/fullchain_v2/260601_4C/HW/multi_rx_cfar_core.v`
- AXI-Lite/AXIS 顶层：`/home/soooarr/chipyard_copy/fullchain_v2/260601_4C/HW/multi_rx_cfar_accel_axi.v`

### 3. 多通道综合与资源：50 MHz 可用，但资源压力明显

讲什么：

- 50 MHz FullChain v2 multi-RX bitstream 已通过 post-route timing。
- 资源增长来自四路 FFT/cache 链路复制，BRAM/DSP 占用显著增加。
- 这解释了后续频率提升困难：不是单个资源耗尽，而是高占用下布线余量变小。

建议表格：

| 指标 | 单通道参考 | 4RX v2 | 增长 |
| --- | ---: | ---: | ---: |
| Slice LUTs | 46746 | 96526 | 2.06x |
| Slice Registers | 25349 | 48707 | 1.92x |
| Block RAM Tiles | 54 | 238 | 4.41x |
| DSP48E1 | 94 | 328 | 3.49x |

4RX v2 资源：

```text
Slice LUTs      : 96526 / 134600 = 71.71%
Block RAM Tile  :   238 /    365 = 65.21%
DSP48E1         :   328 /    740 = 44.32%
```

时序：

```text
WNS = +0.852 ns
TNS = 0.000 ns
WHS = +0.051 ns
THS = 0.000 ns
```

截图/证据来源：

- 汇总：`/home/soooarr/chipyard_copy/docs/fullchainv2/evidence/fullchain-v2-bitstream-summary-2026-06-01.md`
- timing report：`/home/soooarr/chipyard_copy/docs/fullchainv2/reports/50mhz_multirx/post_route_timing_summary.txt`
- flat utilization：`/home/soooarr/chipyard_copy/docs/fullchainv2/reports/50mhz_multirx/post_route_utilization_flat.txt`
- hierarchical utilization：`/home/soooarr/chipyard_copy/docs/fullchainv2/reports/50mhz_multirx/post_route_utilization_hierarchical.txt`

### 4. 多通道板级验证：DMA E2E golden 对拍通过

讲什么：

- 板测路径是 UART-TSI 加载 RISC-V 测试，DDR 输入/输出 buffer 通过 AXI DMA 与 fullchain 硬件交互。
- 两次 CPU reset 后运行均 PASS。
- profile 版本把大量 debug printf 从测量窗口里移除，得到更可信的 streaming phase 时间。

关键打印：

```text
VERSION=0x20260527
EXPECT_IN=65536
EXPECT_OUT=16384
RX_CFG=0x0000000f
CACHE_CNT={16384,16384,16384,16384}
FullChain DMA E2E test PASSED
```

profile 结果：

```text
wait_done_cycles=196869 approx_us_at_50MHz=3937
active_from_ctrl_start_to_done_cycles=197110 approx_us_at_50MHz=3942
run_cycles=197199 approx_us_at_50MHz=3943
```

解释口径：

- 这个 profile 是软件可见的 DMA + accelerator streaming + S2MM/MM2S 交叠时间。
- 还不是 FFT/CFAR 各 stage 的纯硬件延迟。
- 后续若要细分，需要 RTL stage boundary counter 或 ILA。

截图/证据来源：

- 板测汇总：`/home/soooarr/chipyard_copy/docs/fullchainv2/evidence/fullchain-v2-board-validation-pass-2026-06-02.md`
- UART log：`/home/soooarr/chipyard_copy/docs/fullchainv2/uart/fullchain-v2-dma-e2e-profile-after-cpu-reset-ttyUSB0-noselfcheck-2026-06-02-202409.log`
- 测试源码：`/home/soooarr/chipyard_copy/tests/radar-fullchain-dma-e2e.c`

### 5. 频率探索：FullChain v2 51.282 MHz 候选失败，不建议直接跳 55 MHz

讲什么：

- 尝试了 `FullChainAXIMMIONexysVideo51p282MHzCacheConfig`。
- DTS 确认不是假配置：clock 是 51.282051 MHz，I/D cache 从 4 KiB 增到 8 KiB。
- route 能完成，但 post-route timing 失败，WNS -3.835 ns。

关键结论：

```text
50 MHz accepted: WNS +0.852 ns
51.282 MHz candidate: WNS -3.835 ns, TNS -89.322 ns
```

为什么不建议直接 55 MHz：

- 50 MHz 只有 0.852 ns 余量。
- 55 MHz 周期约 18.182 ns，比 50 MHz 少 1.818 ns。
- 即使不考虑布线扰动，也还缺约 0.966 ns。
- 实际 51.282 MHz 已经因布线/物理实现敏感性掉到 -3.835 ns。

截图/证据来源：

- 频率分析：`/home/soooarr/chipyard_copy/docs/fullchainv2/frequency-and-bottleneck-report.md`
- 失败摘要：`/home/soooarr/chipyard_copy/docs/fullchainv2/reports/51p282_cache_candidate/route-failure-summary.md`
- 候选日志：`/home/soooarr/chipyard_copy/docs/fullchainv2/logs/51p282_cache_candidate/fullchain-bitstream-2026-06-01-223251.log`

### 6. Feature21/QMLP 时序资源分析：60 MHz 不是单点问题

讲什么：

- 当前 `chipyard` 这边对 Feature21 + QMLP 做了 50/60/51.282/66.667 MHz elaboration 和 60 MHz bitstream 定位。
- 修复/验证了两类基础问题：
  - 频率参数不再被硬写成 50 MHz，fractional MHz 可以 elaboration。
  - 旧 60 MHz status LED reset 跨域失败不再是主失败路径。
- 插入 UART-TSI 边界 TLBuffer 后，60 MHz 的失败暴露为三类接近的临界路径。

60 MHz post-route 结果：

```text
WNS = -1.578 ns
TNS = -276.127 ns
Failing endpoints = 293
sys_clock WNS = +5.957 ns
clk_out1_harnessSysPLLNode WNS = -1.578 ns
```

Top paths：

| 类别 | 起点 -> 终点 | Slack |
| --- | --- | ---: |
| QMLP | `radarDMA/qmlp/outIdx_reg[1]_replica -> radarDMA/qmlp/accReg_reg[27]` | -1.578 ns |
| Feature21 | `radarDMA/feature21/featureQ8p8Reg_reg[0] -> featureByteRegs_11_reg[1]` | -1.530 ns |
| UART-TSI/FBUS | `fbus/tsi2tl/addr_reg[5] -> coupler_from_uart_tsi/buffer/nodeOut_a_q` | -1.508 ns |

解释口径：

- QMLP 路径大概率是 `outIdx -> async ROM address/data -> lane multiply/sum -> accReg`，下一步要加 MAC-prep/read stage。
- Feature21 路径是 `quantQ8p8 -> round/clamp -> featureByteRegs indexed write`，下一步要拆分 quant/writeback。
- UART-TSI 边界 buffer 已改变 endpoint，但 `TSIToTileLink` 内部 request generation 仍需注册 A-channel。

截图/证据来源：

- 滚动总结：`/home/soooarr/chipyard/docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md`
- 60 MHz timing：`/home/soooarr/chipyard/fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo60MHzConfig/obj/report/timing.txt`
- 60 MHz bitstream log：`/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/tsi-buffer-experiment-2026-06-03/bitstream-60mhz-tsi-buffer-vivado2022p2-2026-06-03.log`
- 频率 config 修改：`/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/Configs.scala`
- harness reset 修改：`/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/Harness.scala`
- TSI buffer 实验 diff：`/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-03/tsi-buffer-experiment-2026-06-03/post-periphery-uarttsi-buffer.diff`

## 不建议展开讲的内容

这些内容可以准备，但组会上不建议主动展开：

- 早期 UART-TSI 921600/115200、自检、CPU reset 细节。除非老师问“为什么用 no-selfcheck/为什么 reset 后跑”。
- FullChain 旧单通道 bring-up 的全部过程。只保留资源对比即可。
- Feature21 4 月份 v1.3/v1.4a 的精度细节。除非本次组会重点是算法精度，否则只说这次关注时序上限。
- Vivado DRC 的所有 warning。只说没有阻止 bitstream，主要关注 timing/resource。

## 可截图清单

优先截图：

1. `/home/soooarr/chipyard_copy/docs/fullchainv2/evidence/fullchain-v2-board-validation-pass-2026-06-02.md`
   - 截 `FullChain DMA E2E test PASSED`
   - 截 `CACHE_CNT={16384,16384,16384,16384}`
   - 截 profile cycles
2. `/home/soooarr/chipyard_copy/docs/fullchainv2/evidence/fullchain-v2-bitstream-summary-2026-06-01.md`
   - 截 WNS/TNS
   - 截资源表
3. `/home/soooarr/chipyard_copy/docs/fullchainv2/frequency-and-bottleneck-report.md`
   - 截 50 MHz vs 51.282 MHz 对比
   - 截单通道 vs 4RX 资源增长表
4. `/home/soooarr/chipyard/docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md`
   - 截 60 MHz top paths 三项
   - 截 QMLP/Feature21/TSI path mapping
5. `/home/soooarr/chipyard_copy/fullchain_v2/260601_4C/HW_SW_README.md`
   - 截多通道链路图和参数表

## 一分钟口播版本

本周主要完成两件事。第一是把 FullChain v2 四路 RX 多通道雷达链路接入 Chipyard/Nexys Video，链路包括 4 路 RX 分发、每路 range/doppler FFT 和 cache、四路功率合并以及 2D CFAR。50 MHz bitstream 已通过 post-route timing，WNS 是 +0.852 ns，板上通过 AXI DMA 完成 65536 个 32-bit 输入和 16384 个 128-bit 输出的 golden 对拍，最终打印 `FullChain DMA E2E test PASSED`。

第二是做频率上限分析。FullChain v2 的 51.282 MHz + 8 KiB cache 候选能 route 完成，但 post-route WNS 是 -3.835 ns，没有接受 bitstream。当前 `chipyard` 的 Feature21/QMLP 60 MHz 实验也显示不是单一模块问题：QMLP async ROM/MAC、Feature21 量化写回、UART-TSI/FBUS request path 三类路径都在 -1.5 ns 左右。因此下一步不建议盲目升频，而是分别做 QMLP MAC 读权重流水、Feature21 quant/writeback 拆分，以及 TSIToTileLink A-channel 注册。

## 下周建议安排

建议把下周目标拆成两个层次：

1. FullChain v2：
   - 保持 50 MHz 作为可用基线。
   - 增加可选 stage latency counter，区分 MM2S、accelerator processing、S2MM、CFAR done。
   - 如果要继续升频，先处理 fbus/TSI 或做 floorplan/region 约束，不直接冲 55 MHz。

2. Feature21/QMLP：
   - QMLP 加 MAC-prep/read stage，切断 async ROM 到 accReg 的单周期路径。
   - Feature21 拆分 quant multiply、round/clamp、feature byte writeback。
   - 对 `TSIToTileLink` 做内部 A-channel register/queue 实验，并用 UART-TSI selfcheck 和 ELF load 验证。
