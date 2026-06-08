# Radar Nexys Video DMA 一致性收口方案

更新时间：2026-03-31

## 1. 文档目的

本文档用于说明当前 `Nexys Video + Rocket + DDR + AXI DMA` 系统在后续接入雷达预处理或神经网络加速器之前，为什么要先完成 DMA/CPU 一致性收口，以及本轮已经落地了哪些改动。

本文档不记录历史 debug 过程，只说明当前系统应遵守的使用协议和下一步验证方式。

## 2. 当前判断

当前系统主链路已经板级跑通，但软件和 DMA 之间仍然有一个明确边界：

- Rocket 的 D-cache 与当前 AXI DMA 路径不是硬件自动一致性关系。
- CPU 与 DMA 共享的 DDR buffer 如果仍然被当作 cacheable memory 使用，就必须在 DMA 前后做显式 cache maintenance。

这意味着，后续无论接的是雷达预处理模块还是 NN 加速器，只要继续沿用：

`DDR -> MM2S -> AXIS accelerator -> S2MM -> DDR`

这条链路，就必须先把 buffer 使用协议固定下来，否则后续算法 bring-up 会反复混入缓存伪问题。

## 3. 本轮采取的路线

本轮没有优先去改 Rocket 微结构、L1 参数或主频，而是先做了对时序影响最小的软件侧收口：

1. 把 DMA 控制、buffer 准备、cache sweep、compare 等重复逻辑抽成统一基础头文件。
2. 把当前 loopback、cache probe、cache maintenance probe 都改为走同一套一致性辅助函数。
3. 新增一个多长度一致性回归测试，用于把“单次 256B loopback 能跑通”扩展成“多种长度和边界都能复验”。

这条路线的优点是：

- 对 FPGA 主 RTL 和时序主干几乎零影响。
- 能先把 CPU/DMA 共享内存协议固化下来。
- 后续接入真实 AXIS 计算模块时，软件底层不需要再反复重写。

## 4. 已落地的代码结构

### 4.1 新增统一 DMA 基础层

新增文件：

- `tests/radar_axi_dma_common.h`

当前头文件统一提供：

- DMA MMIO 常量定义
- `MM2S/S2MM` reset / start / wait 封装
- `TX/RX` buffer 访问封装
- 统一 `cache sweep` 过程
- `dma_prepare_cpu_to_device()`
- `dma_prepare_device_to_cpu()`
- 通用 compare 与单次 loopback 执行函数

这里最关键的是两个语义化接口：

- `dma_prepare_cpu_to_device()`：CPU 写完 buffer 后，在 DMA 读之前执行
- `dma_prepare_device_to_cpu()`：DMA 写完 buffer 后，在 CPU compare 之前执行

后续即使换成真实加速器，也仍然建议保留这两个阶段性接口。

### 4.2 已改造现有 bring-up 测试

已统一改造：

- `tests/radar-axi-dma-loopback.c`
- `tests/radar-axi-dma-loopback-cacheprobe.c`
- `tests/radar-axi-dma-loopback-cachemaint.c`

其中：

- `radar-axi-dma-loopback.c` 继续保留详细寄存器观测，适合作为主 bring-up test。
- `radar-axi-dma-loopback-cacheprobe.c` 继续用于证明 cache coherence 假设。
- `radar-axi-dma-loopback-cachemaint.c` 继续作为“带正确 cache maintenance 的最简通过版”。

### 4.3 新增一致性回归测试

新增：

- `tests/radar-axi-dma-consistency.c`

它会按多个 word 长度顺序执行：

- 4
- 8
- 15
- 16
- 31
- 32
- 33
- 63
- 64

每个 case 都会执行：

1. 填充 TX
2. 清空 RX
3. Pre-DMA cache prepare
4. 运行一次 `MM2S -> AXIS -> S2MM`
5. Post-DMA cache prepare
6. compare

这组用例的目的不是做性能测试，而是先覆盖：

- 非整齐边界长度
- 16 / 32 word 临界点
- 64 word 现有基准长度

## 5. 为什么这一轮不优先改 CPU

当前不优先改 CPU 主频、L1 cache 参数或 Rocket 微结构，原因如下：

1. 当前已知系统问题首先是共享 buffer 的使用协议，而不是 Rocket 无法完成控制任务。
2. 当前主 SoC 域在 `50 MHz` 下时序余量已经不大，贸然扩 cache 或提频只会提高噪声。
3. 后续接入加速器后，首先暴露问题的更可能是流接口、buffer 协议和数据格式，而不是 Rocket 算力本身。

因此，当前推荐顺序仍然是：

1. 先把 DMA/CPU 一致性协议固定
2. 再接一个小型流式计算 demo
3. 最后再评估是否需要提 CPU 主频或扩 L1

## 6. 明天上板建议验证顺序

建议按下面顺序跑：

1. `hello.riscv`
2. `radar-axi-mmio-smoke.riscv`
3. `radar-axi-dma-loopback-cacheprobe.riscv`
4. `radar-axi-dma-loopback-cachemaint.riscv`
5. `radar-axi-dma-loopback.riscv`
6. `radar-axi-dma-consistency.riscv`

如果前五项都通过，而第六项在某个特定长度失败，就可以非常快地把后续问题收敛到：

- DMA 长度边界
- AXIS `tlast` 处理
- 后续加速器接口约束

而不是再回到“系统到底通不通”的阶段。

## 7. 下一阶段推荐动作

完成一致性回归后，再进入下一步：

1. 选一个小型流式算子作为第一颗真实 accelerator demo
2. 保持 `AXIS in -> AXIS out` 的纯流式接口
3. 继续沿用当前 DMA buffer prepare/compare 测试框架
4. 只有在功能链路稳定后，再考虑提主频或扩 cache

这会比一开始就把 CPU/L1/frequency 和 accelerator 一起改动，更稳，也更容易定位问题。
