# Radar NexysVideo AXIS Preproc 更新说明

更新时间：2026-04-02

## 1. 本轮更新目标

本轮更新的重点不是再次修改基础 CPU / DDR / DMA 主链，而是在已经跑通的 `Rocket + DDR + AXI DMA` 平台上，进一步接入一个可配置的 `AXI4-Stream` 预处理模块，并把后续雷达预处理或 NN 前级算子的接入方式固定下来。

当前实现的主链为：

`DDR -> MM2S -> RadarAXISPreprocessor -> S2MM -> DDR`

其中：

- CPU 负责生成输入数据、配置 CSR、启动 DMA、等待完成、读取结果并做 compare
- DMA 负责 DDR 和 AXI-Stream 之间的数据搬运
- `RadarAXISPreprocessor` 负责在流数据面上执行逐 beat 的数据变换

## 2. 本轮新增内容

### 2.1 新的预处理硬件骨架

新增 `RadarAXISPreprocessor`，并将其插入 DMA 数据路径：

- 实现文件：[RadarAXIDMA.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala)
- 生成 RTL：[RadarAXISPreprocessor.sv](/home/soooarr/chipyard/fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/gen-collateral/RadarAXISPreprocessor.sv)

当前模式包括：

- `BYPASS`
- `ADD32`
- `SHIFT16_AR`
- `RELU16`
- `SWAP32`

### 2.2 buffer 协议标准化

统一了 DMA / CPU cached / CPU uncached 三类 buffer 视图，并在公共头文件中收敛为统一接口：

- [radar_axi_dma_common.h](/home/soooarr/chipyard/tests/radar_axi_dma_common.h)

### 2.3 新测试与回归入口

新增预处理 bring-up 程序：

- [radar-axi-dma-preproc.c](/home/soooarr/chipyard/tests/radar-axi-dma-preproc.c)

保留并扩展综合回归入口：

- [radar-axi-dma-regression.c](/home/soooarr/chipyard/tests/radar-axi-dma-regression.c)

## 3. 当前板级验证状态

当前已经完成并通过的验证包括：

1. 预处理版 bitstream 已成功生成
2. 预处理版 bitstream 上，原 DMA 综合回归未回退
3. `ADD32` 模式板测通过
4. `RELU16` 模式板测通过

关键记录：

- bitstream 构建日志：[207-fpga-bitstream-dma-preproc-2026-04-01.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/207-fpga-bitstream-dma-preproc-2026-04-01.log)
- 综合回归通过：[209-run-integrated-regression-on-preproc-bitstream-2026-04-01.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/209-run-integrated-regression-on-preproc-bitstream-2026-04-01.log)
- 预处理板测通过：[212-run-dma-preproc-after-cpu-reset-2026-04-01.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/212-run-dma-preproc-after-cpu-reset-2026-04-01.log)
- 结果摘要：[213-preproc-pass-summary-2026-04-01.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/213-preproc-pass-summary-2026-04-01.md)

## 4. 推荐阅读入口

如果希望快速理解当前实现，推荐按以下顺序阅读：

1. 系统总览：
   [radar_nexysvideo_system_arch.html](/home/soooarr/chipyard/docs/radar_nexysvideo_system_arch.html)
2. 预处理块图：
   [radar_nexysvideo_axi_preproc_bd.html](/home/soooarr/chipyard/docs/radar_nexysvideo_axi_preproc_bd.html)
3. 预处理说明：
   [radar_nexysvideo_stream_preproc_2026-04-01.md](/home/soooarr/chipyard/docs/radar_nexysvideo_stream_preproc_2026-04-01.md)
4. 软件调用方式：
   [radar-axi-dma-preproc.c](/home/soooarr/chipyard/tests/radar-axi-dma-preproc.c)
5. RTL 编码规范：
   [radar_nexysvideo_rtl_coding_guidelines_2026-04-02.md](/home/soooarr/chipyard/docs/radar_nexysvideo_rtl_coding_guidelines_2026-04-02.md)

## 5. 对后续工作的意义

当前这轮更新之后，项目已经不再只是一个 DMA loopback 样机，而是具备了“可配置 AXIS 流处理插槽”的 SoC 原型。

这意味着后续可以沿两条方向继续扩展：

- 雷达方向：
  - 定点缩放
  - clip / threshold
  - 数据重排
  - 简化前处理链
- NN 方向：
  - 激活函数
  - layout transform
  - 轻量级前后处理
  - 后续更复杂算子的统一 AXIS 接入骨架
