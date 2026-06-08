# Radar NexysVideo QMLP 加速器设计与验证说明

更新时间：2026-04-10

## 1. 文档目的

本文档用于说明当前第一版 NN 硬件加速器的完整设计思路、实现内容、测试方法与阶段性结果。

本文档聚焦的对象是已经冻结的部署模型：

- `k=3 + rcs21 + 21 -> 64 -> 32 -> 2 INT8 QMLP`

对应交接文件为：

- [hardware_handoff_model_spec.md](/home/soooarr/chipyard/docs/hardware_handoff_model_spec.md)
- [README.md](/home/soooarr/chipyard/releases/input_convergence_k3_rcs21_20260406/README.md)
- [golden_input.h](/home/soooarr/chipyard/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_input.h)
- [golden_logits.h](/home/soooarr/chipyard/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_logits.h)
- [golden_intermediate.json](/home/soooarr/chipyard/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_intermediate.json)

## 2. 设计目标

当前平台已经稳定具备：

- Rocket 单核 CPU
- DDR / MIG
- AXI DMA
- AXI4-Stream 预处理链
- uncached alias buffer 协议

在此基础上，第一版 NN accelerator 的目标不是做通用可编程神经网络处理器，而是优先完成一个**面向冻结模型的固定功能推理加速器**，让当前 SoC 从“通路样机”推进到“真实模型板上推理样机”。

本轮目标具体包括：

1. 在现有 `MM2S -> AXIS -> S2MM` 数据通路中插入一个固定功能 `QMLP` 模块
2. 支持 21 维 `INT8` 输入
3. 在硬件中完成三层全连接推理：
   - `21 -> 64`
   - `64 -> 32`
   - `32 -> 2`
4. 输出最终 `INT32 logits`
5. 通过 bare-metal 程序与 golden 数据做单样本对拍

## 3. 为什么当前先做固定 QMLP

当前这样设计主要基于三个工程判断：

### 3.1 当前平台主频有限

当前 Nexys Video 上的稳定主频是 `50 MHz`，前面做过上探：

- `60 MHz`：实现后时序失败
- `75 MHz`：实现后时序失败

因此当前不适合第一版就做大型可重构阵列，而更适合先做结构清晰、路径短、资源受控的固定算子链。

### 3.2 当前模型已经冻结

训练侧已经给出了明确的冻结模型和 golden 数据：

- 输入维度固定为 `21`
- 网络层数和维度固定
- 量化规则固定
- golden 输入与 golden logits 已交付

这使得硬件侧可以直接对着固定模型实现，而不需要先搭一整套通用指令调度框架。

### 3.3 当前 SoC 更适合“流式固定功能块”接入

平台当前最稳定的主数据路径是：

`DDR -> MM2S -> AXIS block -> S2MM -> DDR`

因此第一版 accelerator 直接复用这条链路，风险最低，也最容易形成完整闭环。

## 4. SoC 中的接入位置

当前 QMLP 模块没有绕开现有 DMA 框架，而是直接插入已验证通过的 AXI4-Stream 路径：

`DDR -> MM2S -> RadarAXISQMLP -> S2MM -> DDR`

角色分工如下：

- CPU：
  - 准备输入样本
  - 配置 CSR
  - 启动 DMA
  - 等待完成
  - 读回结果并比较
- DMA：
  - 负责 DDR 和 AXI-Stream 之间的数据搬运
- `RadarAXISQMLP`：
  - 负责模型推理本体

因此 CPU 在当前设计中**不参与主计算**，只负责控制与验证。

## 5. 硬件实现内容

### 5.1 新增模块

本轮新增和修改的核心文件如下：

- 新增 QMLP 硬件模块：
  - [RadarQMLP.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarQMLP.scala)
- 集成到 DMA / 本地 CSR：
  - [RadarAXIDMA.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala)
- 软件公共头文件：
  - [radar_axi_dma_common.h](/home/soooarr/chipyard/tests/radar_axi_dma_common.h)
- 单独 QMLP 测试程序：
  - [radar-axi-dma-qmlp.c](/home/soooarr/chipyard/tests/radar-axi-dma-qmlp.c)
- 单 ELF 综合回归入口：
  - [radar-axi-dma-regression.c](/home/soooarr/chipyard/tests/radar-axi-dma-regression.c)

### 5.2 参数来源

QMLP 不是手工把权重常量硬编码在测试里，而是由硬件在 elaboration 阶段读取冻结版本的参数文件：

- [Radar_mlp_binary_k3_rcs21Params.scala](/home/soooarr/chipyard/releases/input_convergence_k3_rcs21_20260406/Radar_mlp_binary_k3_rcs21Params.scala)

当前 `RadarQMLP.scala` 会从 release 目录读取：

- `l1/l2/l3` 的权重
- 偏置
- 各层 scale
- 输入/输出维度

这样做的目的是：

1. 保证硬件参数与训练侧冻结版本严格一致
2. 避免手工抄写参数导致出错
3. 让后续更换冻结模型时仍然可以复用同一套硬件读取框架

### 5.3 内部计算流程

当前硬件模块 `RadarAXISQMLP` 的内部流程为：

1. `sIdle`
   - 等待使能与输入到来
2. `sRecv`
   - 从 AXI-Stream 收集一个样本包
   - 当前固定样本包长度为 `32B`
   - 其中前 `21B` 为有效特征，其余补零
3. `sL1`
   - 执行 `21 -> 64` 全连接
   - `INT32` 累加
   - requant
   - ReLU
   - 输出 `INT8`
4. `sL2`
   - 执行 `64 -> 32` 全连接
   - `INT32` 累加
   - requant
   - ReLU
   - 输出 `INT8`
5. `sL3`
   - 执行 `32 -> 2` 全连接
   - 输出最终 `INT32 logits`
6. `sEmit`
   - 将两个 `INT32 logits` 打包成一个 `64-bit` AXI-Stream beat
   - 送到 S2MM

### 5.4 数据宽度与打包方式

当前数据约定为：

- 输入 AXI-Stream：
  - `32B`
  - 共 `4` 个 beat
  - 每 beat `64-bit`
- 输出 AXI-Stream：
  - `8B`
  - 共 `1` 个 beat
  - 内容为：
    - `logit0 : int32`
    - `logit1 : int32`

### 5.5 CSR 设计

当前新增 CSR 页位于本地 CSR 窗口中，主要包括：

- `QMLP_CTRL`
- `QMLP_STATUS`
- `QMLP_IN_BEATS`
- `QMLP_OUT_BEATS`
- `QMLP_FRAME_COUNT`
- `QMLP_LAST_KEEP`
- `QMLP_LAST_LOGIT0`
- `QMLP_LAST_LOGIT1`
- `QMLP_RUN_CYCLES`
- `QMLP_CAPABILITIES`
- `QMLP_SAMPLE_BYTES`
- `QMLP_OUTPUT_BYTES`

这些 CSR 用于：

- 开关模块
- 清计数器
- 读取当前状态
- 检查流量是否完整
- 读取最后一次推理的 logits

## 6. 软件测试设计

### 6.1 单独 QMLP 测试程序

当前单独测试程序为：

- [radar-axi-dma-qmlp.c](/home/soooarr/chipyard/tests/radar-axi-dma-qmlp.c)

其当前测试流程已经扩展为：

1. 读取冻结 `golden_input`
2. 基于该样本构造 `8` 组确定性测试输入
3. 对每组输入先执行软件侧参考推理，得到期望 logits
4. 将样本打包到 `32B` 输入缓冲区
5. 清空接收缓冲区
6. 关闭 preproc，开启 QMLP
7. 启动 DMA：
   - `MM2S_LENGTH = 32`
   - `S2MM_LENGTH = 8`
8. 等待 DMA 结束
9. 读取并检查：
   - DDR 中回写的 logits
   - `LAST_LOGIT0/LAST_LOGIT1`
   - `IN_BEATS/OUT_BEATS/FRAME_COUNT/LAST_KEEP`
   - `RUN_CYCLES`

### 6.2 单 ELF 综合回归

由于当前板级 bring-up 流程存在“连续独立 ELF 会话容易卡在 selfcheck”的现象，所以本轮已经把 QMLP 也并入单 ELF 综合回归入口：

- [radar-axi-dma-regression.c](/home/soooarr/chipyard/tests/radar-axi-dma-regression.c)

这样后续板测的推荐路径变成：

1. 一次下载
2. 同一个 ELF 中连续执行：
   - MMIO smoke
   - cache probe
   - uncached alias
   - consistency
   - QMLP

QMLP 在该入口中也已经扩展为：

- 多样本对拍
- `RUN_CYCLES` 周期统计
- 端到端 DMA 调度周期统计

这个改动的目标是：

- 避免反复手动 `CPU_RESET`
- 避免第二个独立程序再次卡住 `uart_tsi selfcheck`

## 7. 已完成的验证

### 7.1 构建与生成验证

已经完成：

- bare-metal 编译通过：
  - [222-build-qmlp-test-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/222-build-qmlp-test-2026-04-06.log)
- `verilog` 生成通过：
  - [224-fpga-verilog-qmlp-rerun-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/224-fpga-verilog-qmlp-rerun-2026-04-06.log)
- bitstream 生成通过：
  - [226-fpga-bitstream-qmlp-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/226-fpga-bitstream-qmlp-2026-04-06.log)

### 7.2 时序结果

当前 `QMLP` 版 50 MHz bitstream 时序已通过：

- `WNS = 0.220 ns`
- `WHS = 0.051 ns`

说明当前这版固定 QMLP 加速器已经可以在现有稳定频点下实现。

### 7.3 已验证未回退内容

`QMLP` 集成后，已有 DMA 主链综合回归仍然通过：

- [229-run-integrated-regression-on-qmlp-bitstream-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/229-run-integrated-regression-on-qmlp-bitstream-2026-04-06.log)

这说明：

- DDR / DMA 主链未回退
- uncached alias 未回退
- 原有基础链路仍然保持可用

### 7.4 单 ELF 板测通过结果

在将 `QMLP` 并入单 ELF 综合回归后，当前板上已经完成并通过：

- [240-run-integrated-regression-with-qmlp-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/240-run-integrated-regression-with-qmlp-2026-04-06.log)

本轮板测结果如下：

- `AXI_DMA_REGRESSION_PASSED`
- `QMLP` 流量统计：
  - `IN = 4`
  - `OUT = 1`
  - `FRAMES = 1`
  - `KEEP = 0xFF`
  - `SAMPLE = 32`
  - `OUTPUT = 8`
- `QMLP` 最终 logits：
  - `hw = {855, -10706}`
  - `golden = {855, -10706}`

这说明当前第一版 `QMLP` accelerator 已经完成：

- DDR -> DMA -> QMLP -> DMA -> DDR 的板级闭环
- 与冻结 golden 数据的最终对拍通过

### 7.5 多样本与性能结果

在单样本 golden 对拍完成后，本轮进一步完成了 `8` 组确定性样本的板级验证：

- [242-run-integrated-regression-qmlp-multisample-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/242-run-integrated-regression-qmlp-multisample-2026-04-06.log)
- [243-qmlp-multisample-pass-summary-2026-04-06.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/243-qmlp-multisample-pass-summary-2026-04-06.md)

本轮样本包括：

- `golden_base`
- `zero`
- `alternating_perturb`
- `sparse_keep3`
- `sign_flip_even`
- `half_scale`
- `offset_plus`
- `offset_minus`

所有样本均完成：

- 硬件 logits 与软件参考对拍
- `LAST_LOGIT0/1` 对拍
- `IN/OUT/FRAMES/KEEP` 计数器检查

多样本性能摘要如下：

- `cases=8`
- `hw_cycles_avg=3554`
- `hw_cycles_min=3554`
- `hw_cycles_max=3554`
- `e2e_cycles_avg=8933432`
- `inf_per_sec=14068`

其中：

- `hw_cycles` 表示 `QMLP` 模块内部计算阶段周期
- `e2e_cycles` 表示软件发起 DMA 到轮询返回完成的端到端周期

在当前 `50 MHz` 下，可换算得到：

- 硬件本体单次推理延迟约 `71.08 us`
- 当前 bare-metal 调度路径下的端到端单次延迟约 `178.67 ms`

这说明当前主要性能瓶颈不在 `QMLP` 算子本体，而在软件调度与 bring-up 路径。

### 7.6 `v2.5` PE 阵列版本更新结果

在 baseline `QMLP` 跑通后，后续继续完成了 `4-lane PE` 阵列版本 `v2.5`，并已完成板级验证：

- 离线摘要：
  - [339-qmlp-pe-array-v2p5-bitstream-summary-2026-04-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/339-qmlp-pe-array-v2p5-bitstream-summary-2026-04-09.md)
- 板级摘要：
  - [344-v2p5-board-pass-summary-2026-04-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/344-v2p5-board-pass-summary-2026-04-09.md)

当前 `v2.5` 的关键结果如下：

- 保留 `4-lane PE`
- `hello + selfcheck @115200` 通过
- `integrated regression + selfcheck @115200` 通过
- `QMLP` 多样本 `8` 组全部通过

性能数据更新为：

- `hw_cycles_avg = 1301`
- `hw_cycles_min = 1301`
- `hw_cycles_max = 1301`
- `e2e_cycles_avg = 8915389`
- `inf_per_sec = 38431`

在当前 `50 MHz` 下，可换算得到：

- `QMLP kernel latency ≈ 26.02 us`
- `system end-to-end latency ≈ 178.31 ms`

与旧版 baseline 相比：

- baseline `hw_cycles_avg = 3554`
- `v2.5 hw_cycles_avg = 1301`
- 硬件本体周期数约提升：
  - `3554 / 1301 ≈ 2.73x`

需要特别说明的是：

- 本轮**已经完成的是 kernel latency 优化**
- 本轮**还没有完成 system e2e latency 的系统级优化**

也就是说，`v2.5` 已经明显缩短了 `QMLP` 模块内部计算时间，但端到端周期仍然主要受以下部分影响：

- CPU 端测试流程
- DMA 启停与轮询
- DDR 往返搬运
- bare-metal bring-up 路径

因此当前最准确的表述应当是：

- **QMLP 算子本体已经加速成功**
- **system e2e latency 优化仍属于下一阶段工作**

### 7.7 `v2.8` batch e2e 优化结果

在 `v2.5` 之后，后续工作没有继续削弱 `4-lane PE`，而是把优化重点转到 `system e2e latency`，具体是从 batch 数据路径入手。

本阶段关键文件为：

- e2e 测试程序：
  - [radar-axi-dma-qmlp-e2e.c](/home/soooarr/chipyard/tests/radar-axi-dma-qmlp-e2e.c)
- batch 修复离线摘要：
  - [412-qmlp-e2e-batchfix-v2p8-summary-2026-04-10.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/412-qmlp-e2e-batchfix-v2p8-summary-2026-04-10.md)
- batch 板级通过摘要：
  - [421-v2p8-batch-pass-summary-2026-04-10.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/421-v2p8-batch-pass-summary-2026-04-10.md)

#### 7.7.1 这轮具体修了什么

在 `batch-only` 诊断版里，旧版本已经出现下面这个特征：

- `out[0]` 正确
- `out[1]` 开始错位
- `sample = 32`
- `output = 8`
- 但 `out = 5`

这说明问题不在模型计算本体，而在样本边界的接收与打包。

最终定位到 [RadarQMLP.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarQMLP.scala) 中的 `recvBeatCount`：

- 状态机回到 `sIdle` 时虽然会写 `recvBeatCount := 0`
- 但下一样本首拍仍可能在同一个周期里使用上一样本残留值参与 `baseByte` 计算
- 这样第二个样本第一拍就可能从错误偏移装载，导致 batch 输出从第二组开始整体错位

`v2.8` 的修法是：

- 增加显式 `recvBeatBase`
- 在 `state === sIdle` 时强制其视为 `0`
- `io.in.fire` 时统一使用 `recvBeatBase` 参与：
  - `baseByte`
  - `recvBeatCount` 递增
  - 样本结束判断

这轮修的是：

- **QMLP batch 接收边界**

而不是：

- 削弱 `PE`
- 改量化规则
- 降低模型复杂度

#### 7.7.2 离线实现结果

`v2.8` 的 bitstream 已通过：

- `sys_clock: WNS = 2.527 ns, WHS = 0.235 ns`
- `clk_out1_harnessSysPLLNode: WNS = 0.114 ns, WHS = 0.050 ns`

这说明：

- `50 MHz` DUT 主域仍然通过
- 修复 batch 接收逻辑后，当前版本仍可正常实现

#### 7.7.3 板级结果

在 fresh `CPU_RESET` 后，`batch-only` e2e 路径已经通过：

- 日志：
  - [420-v2p8-batch-only-after-user-reset-2026-04-10.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/420-v2p8-batch-only-after-user-reset-2026-04-10.log)

关键结果为：

- `AXI DMA qmlp e2e PASSED`
- `in = 32`
- `out = 8`
- `frames = 1`
- `keep = 0x000000ff`

前四组输出为：

- `out[0] = {855, -10706}`
- `out[1] = {861, 508}`
- `out[2] = {979, -8599}`
- `out[3] = {291, 151}`

说明 batch 接收错位问题已经消失。

#### 7.7.4 当前 e2e 数据

当前 `v2.8 batch-only` 路径给出的数据是：

- `hw_cycles_avg = 1301`
- `e2e_cycles_avg = 1157261`

按 `50 MHz` 换算：

- `kernel latency ≈ 26.02 us`
- `reset_batch_per_sample e2e latency ≈ 23.145 ms`

和旧单样本 e2e 对比：

- `v2.5` 单样本 e2e：`8915389 cycles`，约 `178.31 ms`
- `v2.8 batch-only` 每样本 e2e：`1157261 cycles`，约 `23.145 ms`

也就是说，当前已经不只是：

- `kernel latency` 优化成功

而是已经开始拿到：

- **真实 batch e2e 优化结果**

当前更准确的结论是：

- `v2.5` 是当前 `4-lane PE` 的板级稳定基线
- `v2.8` 是当前 batch e2e 的板级稳定基线

## 8. 当前板测阻塞与定位结果

### 8.1 当前未完成项

当前单样本 logits 对拍主目标已经完成。

### 8.2 当前现象

对 `radar-axi-dma-qmlp.riscv` 的直接板测，多次表现为：

- 程序没有进入可见主体输出
- 会话卡在 `uart_tsi selfcheck` 或更前面的最小事务阶段

相关记录：

- [230-run-qmlp-on-qmlp-bitstream-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/230-run-qmlp-on-qmlp-bitstream-2026-04-06.log)
- [231-run-qmlp-after-cpu-reset-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/231-run-qmlp-after-cpu-reset-2026-04-06.log)
- [232-run-qmlp-after-clean-cpu-reset-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/232-run-qmlp-after-clean-cpu-reset-2026-04-06.log)
- [233-run-qmlp-linebuffered-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/233-run-qmlp-linebuffered-2026-04-06.log)

### 8.3 最小探针结果

为了判断问题是不是已经发生在程序主体之前，又增加了最小探针：

- `init_read 0x80000000`：
  - [234-qmlp-probe-init-read-0x80000000-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/234-qmlp-probe-init-read-0x80000000-2026-04-06.log)
  - [235-qmlp-probe-init-read-clean-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/235-qmlp-probe-init-read-clean-2026-04-06.log)
  - 返回值为 `ffff`
- `init_write 0x80000000 = 0x11223344`：
  - [236-qmlp-probe-init-write-clean-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/236-qmlp-probe-init-write-clean-2026-04-06.log)
  - 写入命令返回完成

当前这部分问题已经通过“并入单 ELF 综合回归”的方式绕开。

结论是：

- 独立 `QMLP` ELF 会话确实容易和现有 bring-up 链路互相干扰
- 但并不是 QMLP 算法本体错误
- 在单 ELF 回归方式下，QMLP 已能稳定跑通并通过 golden 对拍

## 9. 关于“虚拟按键 / 软复位”

当前系统里确实存在一个软件可访问的 tile reset 资源：

- `tile-reset-setter@0x110000`

相关依据：

- [TileResetCtrl.scala](/home/soooarr/chipyard/generators/testchipip/src/main/scala/boot/TileResetCtrl.scala)
- [RadarAXIMMIONexysVideoConfig.memmap.json](/home/soooarr/chipyard/fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig.memmap.json)

但当前判断是：

- 它更像是 **tile 级 reset**
- 不等价于板上的完整 `CPU_RESET`
- 目前没有证据表明它能完全清除 `uart_tsi` 自检窗口污染

因此在当前阶段：

- 它可以继续作为后续实验方向
- 但还不能直接替代人工 `CPU_RESET`

更稳妥的工程路线仍然是：

1. 尽量把测试并进单 ELF
2. 减少独立 ELF 次数
3. 再评估软复位是否值得继续打磨

## 10. 论文可写的创新点与工作量

就硕士论文工作量和完整性而言，当前这版 QMLP 加速器已经具备一条比较扎实的工程主线：

### 10.1 可写的创新点

1. **在 Chipyard/Rocket SoC 上完成固定量化 MLP 的流式硬件推理接入**
   - 不是单独 IP，而是完整接入 `DDR + DMA + AXIS + CSR + bare-metal`
2. **面向冻结模型的参数直读式硬件生成**
   - release 侧参数直接进入硬件 elaboration
   - 保证训练/部署版本一致
3. **兼容现有 DMA 主链的轻量级 NN 加速器接入框架**
   - 不重新设计访存系统
   - 以最小侵入方式插入现有 SoC
4. **带 golden 数据包的板级对拍闭环**
   - 不停留在 RTL 仿真
   - 明确推进到板级验证

### 10.2 可体现的工作量

1. 冻结模型规格整理与硬件 handoff 文件生成
2. Chisel 侧 QMLP 模块设计
3. AXI-Stream 数据路径接入
4. DMA/CSR 控制页扩展
5. bare-metal 测试程序编写
6. 单 ELF 综合回归改造
7. bitstream 生成与时序收敛
8. 板级 bring-up 与事务层问题定位

## 11. 下一步建议

当前最直接的下一步是：

1. 保持现有 `QMLP` 硬件结构不动
2. 继续用单 ELF 回归方式做板测
3. 扩展到：
   - 多样本对拍
   - 更多 golden case
   - `RUN_CYCLES` 性能统计
4. 再决定是否继续：
   - 优化吞吐
   - 增加 batch
   - 增加更多层
   - 或扩展为更通用的 NN accelerator 骨架

一句话总结：

当前这版并不是“还停留在概念设计”，而是已经完成了：

- 固定模型冻结
- 硬件架构接入
- 软件控制闭环
- bitstream 通过
- 基础 SoC 回归通过
- QMLP 单样本 golden 对拍通过

后续剩余工作将主要转向：

- 更多样本验证
- 性能测量
- 以及从固定 QMLP 向更一般 NN accelerator 骨架扩展
