# DMA Buffer 协议标准化与 AXIS 预处理骨架离线收口摘要

更新时间：2026-04-01

## 1. 本轮完成的实现

本轮已经完成两类改动：

1. DMA buffer 使用协议标准化
2. AXI DMA 内部 loopback 升级为可配置的 AXIS 预处理骨架

对应代码如下：

- [radar_axi_dma_common.h](/home/soooarr/chipyard/tests/radar_axi_dma_common.h)
- [RadarAXIDMA.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala)
- [radar-axi-dma-preproc.c](/home/soooarr/chipyard/tests/radar-axi-dma-preproc.c)
- [radar_nexysvideo_stream_preproc_2026-04-01.md](/home/soooarr/chipyard/docs/radar_nexysvideo_stream_preproc_2026-04-01.md)

## 2. Buffer 协议当前状态

当前已经把 DDR buffer 的角色固定为：

- `buf_in`
- `buf_mid0`
- `buf_mid1`
- `buf_out`
- `desc_ring`

并统一封装了三种地址语义：

- DMA 地址
- CPU cached 地址
- CPU uncached alias 地址

后续 bring-up 程序不再建议手写散乱裸地址，而应统一使用公共头文件中的区域描述和地址转换接口。

## 3. 数据面当前状态

原来的内部数据面是：

`MM2S -> 直接 loopback -> S2MM`

现在已经改成：

`MM2S -> RadarAXISPreprocessor -> S2MM`

当前骨架支持的模式包括：

- bypass
- add32
- signed shift16 arithmetic
- relu16 + clip
- swap32 / halfword reorder

同时新增了一页本地 CSR，挂在同一个 `0x6000_0000` 外设窗口下的 `0x200 ~ 0x224`。

## 4. 离线验证结果

### 4.1 软件编译

`tests` 侧已通过：

- `radar-axi-dma-preproc.riscv`
- `radar-axi-dma-regression.riscv`

日志：

- [189-build-dma-preproc-suite-2026-04-01.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/189-build-dma-preproc-suite-2026-04-01.log)

### 4.2 FPGA 生成

`NexysVideo` 目标的 `verilog` 已通过。

关键信号已经出现在生成物中：

- `RadarAXISPreprocessor.sv`
- `RadarAXI4ToAXI4LiteBridge.sv` 中新增 `io_local_*`
- `RadarAXIDMA.sv` 中已经出现本地 CSR 写入/读取和 `preproc` 实例

日志：

- [190-fpga-verilog-dma-preproc-2026-04-01.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/190-fpga-verilog-dma-preproc-2026-04-01.log)

## 5. 当前还没做的事

本轮还没有上板验证新的 `preproc` 模式。

也就是说，当前状态是：

- 协议设计已落地
- 软件和 RTL 离线验证已通过
- 但 `ADD32 / RELU16` 等新模式还需要下一轮板测确认

## 6. 下次上板建议

下次建议优先跑：

1. `radar-axi-dma-regression.riscv`
2. `radar-axi-dma-preproc.riscv`

如果第一项通过，就说明原有稳定路径没有被这轮骨架改动破坏。

如果第二项通过，就说明：

- 新 CSR 页可访问
- `MM2S -> preproc -> S2MM` 可通
- 新模式的输出结果和计数器都符合预期
