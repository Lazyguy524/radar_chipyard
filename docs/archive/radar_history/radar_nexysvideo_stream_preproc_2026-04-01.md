# Radar Nexys Video Buffer 协议与 AXIS 预处理骨架说明

更新时间：2026-04-01

## 1. 文档目的

本文档说明两件事：

1. 当前项目已经落地的 DMA buffer 使用协议；
2. 当前已经接入 `MM2S -> AXIS preprocessor -> S2MM` 的可配置流处理骨架。

本文档不记录 debug 过程，只描述当前实现、接口和推荐使用方式。

## 2. 当前 buffer 协议

为了避免后续雷达预处理模块、NN 加速模块各自重新发明一套 buffer 习惯，本轮已经把 DDR buffer 的角色固定为下面五块区域：

- `buf_in`：`0x8100_0000`
- `buf_mid0`：`0x8180_0000`
- `buf_mid1`：`0x8200_0000`
- `buf_out`：`0x8280_0000`
- `desc_ring`：`0x8300_0000`

其中：

- `buf_in/buf_mid0/buf_mid1/buf_out` 每块大小固定为 `0x0080_0000`（8 MiB）
- `desc_ring` 大小固定为 `0x0010_0000`
- CPU 如果需要走 uncached 视图，则统一在原始 DDR 地址上加 `0x1000_000000`

因此，**同一块物理 buffer 存在三种地址语义**：

1. DMA 地址  
   直接使用原始 DDR 地址，如 `0x8100_0000`

2. CPU cached 地址  
   与 DMA 地址相同，但会经过 Rocket D-cache

3. CPU uncached 地址  
   在 DMA 地址基础上加 `0x1000_000000`

当前测试公共头文件 [radar_axi_dma_common.h](/home/soooarr/chipyard/tests/radar_axi_dma_common.h) 已经把这三种视图统一封装为：

- `radar_buffer_region_desc()`
- `radar_buffer_dma_addr()`
- `radar_buffer_cpu_addr()`
- `radar_buffer_ptr32()`

这意味着后续新程序不应该再手写一堆散乱的裸地址，而应该统一走这套接口。

## 3. 当前推荐的软件使用约定

### 3.1 如果 CPU 访问 cached DDR buffer

推荐约定：

1. CPU 写 TX / 输入 buffer
2. 调 `dma_prepare_cpu_to_device()`
3. 启动 DMA 或加速器
4. DMA / 加速器写回输出 buffer
5. 调 `dma_prepare_device_to_cpu()`
6. CPU 再 compare 或继续处理

这条路径适合：

- 保持当前 Rocket 默认 cacheable 主存模型
- 先快速 bring-up 新算法

### 3.2 如果 CPU 访问 uncached alias buffer

推荐约定：

1. DMA 地址仍然使用原始 DDR 地址
2. CPU 改走 `radar_buffer_cpu_addr(..., RADAR_BUF_VIEW_UNCACHED, ...)`
3. 普通读写和 compare 不再依赖 cache maintenance

这条路径适合：

- 把 DMA buffer 规范化成“软件直接视为 non-coherent I/O buffer”
- 后续流式加速器程序减少 cache 噪声

## 4. 当前 AXIS 预处理骨架

之前的 DMA 数据面是：

`MM2S AXIS -> 直接硬回环 -> S2MM AXIS`

现在已经改成：

`MM2S AXIS -> RadarAXISPreprocessor -> S2MM AXIS`

这个模块的目标不是现在就实现完整雷达前端或 NN 内核，而是先提供一个稳定的、可配置的流处理插槽。

当前 RTL 文件在：

- [RadarAXIDMA.scala](/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala)

实现特点：

- 数据宽度固定为 `64-bit AXIS`
- `tkeep/tlast` 全链路保留
- 数据变换放在一级寄存器缓冲后，不是纯组合硬穿
- 默认关闭时保持旁路，不会改变现有 loopback 语义

## 5. 当前 CSR 地址分配

当前仍然共用 `0x6000_0000` 这个外设窗口：

- `0x000 ~ 0x0ff`：Xilinx AXI DMA CSR
- `0x200 ~ 0x224`：本轮新增的 preprocessor CSR

新增寄存器如下：

- `0x200 PREPROC_CTRL`
  - bit0：enable
  - bit1：clear counters（写脉冲）
- `0x204 PREPROC_MODE`
- `0x208 PREPROC_PARAM0`
- `0x20c PREPROC_PARAM1`
- `0x210 PREPROC_STATUS`
- `0x214 PREPROC_IN_BEATS`
- `0x218 PREPROC_OUT_BEATS`
- `0x21c PREPROC_FRAME_COUNT`
- `0x220 PREPROC_LAST_KEEP`
- `0x224 PREPROC_CAPABILITIES`

公共头文件里已经有对应宏：

- `PREPROC_CTRL`
- `PREPROC_MODE`
- `PREPROC_PARAM0`
- `PREPROC_PARAM1`
- `PREPROC_STATUS`
- `PREPROC_IN_BEATS`
- `PREPROC_OUT_BEATS`
- `PREPROC_FRAME_COUNT`
- `PREPROC_LAST_KEEP`
- `PREPROC_CAPABILITIES`

以及配套软件接口：

- `preproc_configure()`
- `preproc_disable()`
- `preproc_clear_counters()`
- `preproc_dump_status()`

## 6. 当前已经实现的处理模式

### 6.1 `PREPROC_MODE_BYPASS`

直接透传，保持当前 loopback 语义。

### 6.2 `PREPROC_MODE_ADD32`

对每个 `64-bit beat` 内的两个 `32-bit lane` 分别加常数：

- 低 32 位加 `PARAM0`
- 高 32 位加 `PARAM1`

适合：

- 验证 lane 级数据变换
- 验证双通道并行参数加载

### 6.3 `PREPROC_MODE_SHIFT16_AR`

把每个 `64-bit beat` 视为四个有符号 `16-bit` lane，做算术右移。

适合：

- 定点缩放
- 雷达前处理中的简单幅度压缩
- NN 前后处理中的量化缩放雏形

### 6.4 `PREPROC_MODE_RELU16`

把每个 `64-bit beat` 视为四个有符号 `16-bit` lane：

- 负数清零
- 正数可按 `PARAM0[15:0]` 做上限裁剪

适合：

- 简单激活函数
- 阈值化或裁剪类预处理

### 6.5 `PREPROC_MODE_SWAP32`

用于做 `32-bit lane` 交换，以及可选的 `16-bit` 半字翻转。

适合：

- 数据布局调整
- I/Q 或特征块顺序重排

## 7. 当前新测试程序

新增 bring-up 测试：

- [radar-axi-dma-preproc.c](/home/soooarr/chipyard/tests/radar-axi-dma-preproc.c)

当前测试覆盖：

1. `ADD32` 模式
2. `RELU16` 模式
3. 预处理计数器读回

当前设计目标不是一次性覆盖所有模式，而是先把：

- CSR 可写
- 数据路径可通
- 计数器可读

这三件事收口成一条稳定 bring-up 入口。

## 8. 为什么这样做更适合后续雷达 / NN

这次不是直接做完整雷达预处理链或 NN 乘加阵列，而是先搭一个“软件协议 + AXIS 骨架”：

- 对雷达方向  
  可以继续往 `shift / clip / reorder / magnitude-like` 这类流式预处理中扩展

- 对 NN 方向  
  可以继续往 `quantize / relu / layout transform / tile pack` 这类前后处理中扩展

这样后续真正加复杂算子时，至少下面这些基础设施已经先固定住了：

- DMA buffer 放哪
- CPU 用 cached 还是 uncached
- AXIS 模块怎么接进 DMA 链
- CSR 放在哪
- bring-up 测试怎么写

## 9. 当前推荐的下一步

当前建议按下面顺序继续推进：

1. 先把 `radar-axi-dma-preproc.riscv` 上板跑通
2. 再决定第一颗真实算法 demo 是偏雷达还是偏 NN
3. 保持 `AXIS in -> AXIS out` 纯流式接口，不先引入复杂调度
4. 如果后续需要多级处理，再把 `buf_mid0/buf_mid1` 真正用起来

如果偏雷达，我建议第一颗真实模块优先做：

- I/Q 重排
- 定点缩放
- 门限/ReLU-like 裁剪

如果偏 NN，我建议第一颗真实模块优先做：

- 量化前后处理
- ReLU/clip
- layout transform

而不是一上来就做完整卷积阵列。
