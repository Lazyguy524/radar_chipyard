# QMLP Bitstream Bring-up Report

## 1. Current Bitstream Status

- Bitstream file:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/NexysVideoHarness.bit`
- Bitstream build log:
  - `logs/radar_nexysvideo/runtime/226-fpga-bitstream-qmlp-2026-04-06.log`
- Timing report:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/report/timing.txt`

### Timing conclusion

- This QMLP-integrated 50 MHz bitstream meets timing.
- Key summary:
  - `WNS = 0.220 ns`
  - `WHS = 0.051 ns`
  - `All user specified timing constraints are met`

## 2. Accelerator Target

Frozen deployment model:

- `k=3 + rcs21 + 21 -> 64 -> 32 -> 2 INT8 QMLP`

Reference handoff inputs:

- `docs/hardware_handoff_model_spec.md`
- `releases/input_convergence_k3_rcs21_20260406/`
- `releases/input_convergence_k3_rcs21_20260406/hardware_golden/`

## 3. Hardware Design Summary

### 3.1 Placement in the SoC

The new NN accelerator does not replace the existing DMA path. It is inserted into the established stream chain:

- `DDR -> MM2S -> RadarAXISQMLP -> S2MM -> DDR`

CPU participation remains control-only:

- prepare input buffer in DDR
- configure control registers
- start DMA
- wait for completion
- read back logits and compare with golden values

### 3.2 Main hardware modules

Implemented files:

- `fpga/src/main/scala/nexysvideo/RadarQMLP.scala`
- `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
- `tests/radar_axi_dma_common.h`
- `tests/radar-axi-dma-qmlp.c`

### 3.3 Data shape and packetization

- Input AXI-Stream packet: `32 bytes`
- Valid feature payload: first `21 bytes`
- Remaining bytes: zero padding
- Output AXI-Stream packet: `8 bytes`
  - `logit0 : int32`
  - `logit1 : int32`

### 3.4 Internal compute flow

The accelerator is implemented as a fixed-function stream inference engine:

1. Receive one sample packet from MM2S
2. Decode first 21 bytes into signed feature vector
3. Run L1:
   - `21 -> 64`
   - int32 accumulation
   - requant
   - ReLU
   - int8 output
4. Run L2:
   - `64 -> 32`
   - int32 accumulation
   - requant
   - ReLU
   - int8 output
5. Run L3:
   - `32 -> 2`
   - int32 accumulation
   - final logits output
6. Pack two logits into one AXI-Stream beat and send to S2MM

### 3.5 Internal state machine

Current state sequence:

- `sIdle`
- `sRecv`
- `sL1`
- `sL2`
- `sL3`
- `sEmit`

Meaning:

- `sRecv`: collect one sample frame from AXI-Stream
- `sL1/sL2/sL3`: sequential MAC + requant pipeline by layer
- `sEmit`: output final logits

This first version prioritizes correctness and clean integration with the existing DMA/AXIS chain over throughput maximization.

## 4. Control and Status Interface

New local CSR page offsets:

- `QMLP_CTRL      @ 0x240`
- `QMLP_STATUS    @ 0x244`
- `QMLP_IN_BEATS  @ 0x248`
- `QMLP_OUT_BEATS @ 0x24C`
- `QMLP_FRAME_COUNT @ 0x250`
- `QMLP_LAST_KEEP @ 0x254`
- `QMLP_LAST_LOGIT0 @ 0x258`
- `QMLP_LAST_LOGIT1 @ 0x25C`
- `QMLP_RUN_CYCLES @ 0x260`
- `QMLP_CAPABILITIES @ 0x264`
- `QMLP_SAMPLE_BYTES @ 0x268`
- `QMLP_OUTPUT_BYTES @ 0x26C`

These registers are used for:

- enable/disable
- activity/counter observation
- frame/beat verification
- direct readout of last logits

## 5. Software-side Bring-up Design

The new bare-metal test is:

- `tests/radar-axi-dma-qmlp.c`

Current test flow:

1. load golden input from:
   - `releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_input.h`
2. load expected logits from:
   - `releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_logits.h`
3. build a 32-byte uncached TX packet
4. clear RX buffer
5. disable preproc, enable QMLP
6. run DMA with asymmetric lengths:
   - `MM2S_LENGTH = 32`
   - `S2MM_LENGTH = 8`
7. check:
   - returned logits in DDR
   - QMLP counters
   - `LAST_LOGIT0/1`

## 6. 当前验证进展

### 6.1 已完成项

- bare-metal 测试程序已编译通过：
  - `logs/radar_nexysvideo/runtime/222-build-qmlp-test-2026-04-06.log`
- FPGA `verilog` 生成已通过：
  - `logs/radar_nexysvideo/runtime/224-fpga-verilog-qmlp-rerun-2026-04-06.log`
- bitstream 已生成并通过时序：
  - `logs/radar_nexysvideo/runtime/226-fpga-bitstream-qmlp-2026-04-06.log`
- 当前 50 MHz 实现指标：
  - `WNS = 0.220 ns`
  - `WHS = 0.051 ns`
  - `All user specified timing constraints are met`

### 6.2 本轮板测实际结果

- 综合回归已在 QMLP bitstream 上通过：
  - `logs/radar_nexysvideo/runtime/229-run-integrated-regression-on-qmlp-bitstream-2026-04-06.log`
- 该结果说明：
  - 原有 `DDR -> DMA -> DDR` 主链未回退
  - `uncached alias` 路径未回退
  - 综合回归入口仍可正常工作

### 6.3 QMLP 单测早期阻塞点

在单独运行 `radar-axi-dma-qmlp.riscv` 的早期尝试中，确实没有直接得到最终 logits 结果，已确认的现象如下：

- 第一次尝试时，宿主机串口设备缺失：
  - `logs/radar_nexysvideo/runtime/227-run-integrated-regression-on-qmlp-bitstream-2026-04-06.log`
- 串口恢复后，`QMLP` 单测多次未能进入可见程序主体：
  - `logs/radar_nexysvideo/runtime/230-run-qmlp-on-qmlp-bitstream-2026-04-06.log`
  - `logs/radar_nexysvideo/runtime/231-run-qmlp-after-cpu-reset-2026-04-06.log`
  - `logs/radar_nexysvideo/runtime/232-run-qmlp-after-clean-cpu-reset-2026-04-06.log`
  - `logs/radar_nexysvideo/runtime/233-run-qmlp-linebuffered-2026-04-06.log`

其中最关键的缩点是：

- `QMLP` 单测会稳定卡在 `uart_tsi selfcheck` 的第一个 chunk：
  - `Self check chunk 80000000 to 80000400`
- 这说明当前还不能判定是 logits 算错，更像是装载/自检链路在该镜像上先卡住

### 6.4 最小探针结果

为了排除程序主体本身的影响，又额外做了最小探针：

- `init_read 0x80000000`：
  - `logs/radar_nexysvideo/runtime/234-qmlp-probe-init-read-0x80000000-2026-04-06.log`
  - 读回结果为 `ffff`
- clean reset 后再次 `init_read 0x80000000`：
  - `logs/radar_nexysvideo/runtime/235-qmlp-probe-init-read-clean-2026-04-06.log`
  - 仍然返回 `ffff`
- `init_write 0x80000000 = 0x11223344`：
  - `logs/radar_nexysvideo/runtime/236-qmlp-probe-init-write-clean-2026-04-06.log`
  - 写命令返回完成
- 再次顺序执行写后读回时，串口事务本身又出现异常收尾：
  - `logs/radar_nexysvideo/runtime/237-qmlp-probe-write-then-read-write-2026-04-06.log`

据此当时可以确认：

- 问题还停留在更前置的 `uart_tsi / init_read / selfcheck` 事务层
- 不是当前已经拿到了 `QMLP` 的错误 logits
- 也不是 bitstream build/timing 的问题

### 6.5 单 ELF 板测通过结果

为避免“第二个独立 ELF 会话”带来的 `selfcheck` 装载问题，后续将 `QMLP` 并入现有单 ELF 综合回归入口，再次上板验证：

- `logs/radar_nexysvideo/runtime/240-run-integrated-regression-with-qmlp-2026-04-06.log`

该次板测已经完整通过，关键信息为：

- 综合回归最终打印：
  - `AXI_DMA_REGRESSION_PASSED`
- QMLP 部分打印：
  - `IN=4`
  - `OUT=1`
  - `FRAMES=1`
  - `KEEP=0x000000ff`
  - `LOGIT0=855`
  - `LOGIT1=-10706`
  - `CYC=3554`
- 硬件输出与 golden 对拍：
  - `hw={855, -10706}`
  - `golden={855, -10706}`
  - `compare passed`

据此现在已经可以确认：

- `QMLP` 硬件模块已在板级真正跑通
- 最终 `logits` 与冻结 golden 完全一致
- 单样本 `32B -> 8B` 推理闭环已完成
- 当前最稳的 bring-up 方式是：**将 QMLP 并入单 ELF 综合回归**

## 7. Recommended next verification items

1. 扩展更多 golden 样本
2. 继续记录并分析：
   - `IN_BEATS`
   - `OUT_BEATS`
   - `FRAME_COUNT`
   - `LAST_KEEP`
   - `RUN_CYCLES`
3. 评估多样本串行运行时的软件调度方式
4. 评估后续是否需要把固定 QMLP 扩展为更通用的 NN accelerator 骨架

## 8. 当前工程判断

当前第一版 NN accelerator 已经达到以下里程碑：

- 冻结模型已明确
- QMLP 硬件数据通路已插入 AXI-Stream 链
- DMA 集成已完成
- 软件控制与测试程序已完成
- elaboration / build / timing 全部通过
- 老链路综合回归在新 bitstream 上通过

当前剩余工作已经不在“第一版是否能跑通”，而在：

- 多样本对拍
- 性能数据采集
- 以及从固定 QMLP 向更一般 NN accelerator 继续扩展
