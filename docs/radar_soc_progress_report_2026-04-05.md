# 雷达微系统 SoC 阶段性总结

更新时间：2026-04-05

本文档按当前阶段已经完成的设计、验证、纠错和板级结果进行总结，不展开过多意义分析，重点记录系统现状、做过什么、验证到了什么程度，以及当前可确认的性能边界。

---

## 1. 当前 SoC 架构说明

### 1.1 当前硬件组成

当前平台基于 `Nexys Video + Chipyard + Rocket + DDR + AXI DMA + AXI-Stream Preprocessor` 搭建，顶层可概括为以下几个部分：

- `Rocket RISC-V CPU`
  - 单核 `RV64`
  - 作为软件控制核心，负责程序执行、寄存器配置、DMA 启动、结果校验
  - 当前配置为小核，无 FPU
  - 当前缓存规模：
    - `I$ = 4 KiB`
    - `D$ = 4 KiB`

- `AXI / TileLink 互连`
  - SoC 内部主干仍然以 `TileLink` 为主
  - 在外设、DDR 与 DMA 边界使用 AXI 协议族完成桥接
  - 当前实际使用的协议包括：
    - `AXI4`：DDR 主存搬运
    - `AXI4-Lite`：DMA / preproc 寄存器配置
    - `AXI4-Stream`：流式数据处理

- `DDR / MIG`
  - 通过 Nexys Video 的 MIG 接入板载 DDR
  - 当前有效主存窗口为 `0x8000_0000` 起始的 `512 MiB`
  - 已支持 `uncached alias` 视图，用于 CPU 与 DMA 共享 buffer 时绕开 D-cache

- `RadarAXIDMA 子系统`
  - 包含 `MM2S` 和 `S2MM`
  - 数据宽度为 `64-bit`
  - 负责 `DDR <-> AXI-Stream` 数据搬运

- `RadarAXISPreprocessor`
  - 插在 `MM2S -> S2MM` 的 AXI-Stream 数据路径中
  - 当前已实现并板测通过的模式：
    - `ADD32`
    - `RELU16`
  - 其余已实现模式：
    - `BYPASS`
    - `SHIFT16_AR`
    - `SWAP32`

### 1.2 当前数据通路

当前系统已经形成一条明确的数据通路：

`CPU -> DDR buffer -> AXI DMA(MM2S) -> AXI-Stream Preprocessor -> AXI DMA(S2MM) -> DDR buffer -> CPU compare`

这里 CPU 不承担主数据计算，而是承担：

- 输入数据生成或读取
- DMA / preproc 配置
- 传输启动
- 完成等待
- 输出比对

真正的数据搬运和流式计算由 DMA 与 AXIS 模块完成。

### 1.3 当前控制面

当前控制面已经稳定工作，CPU 通过 MMIO 控制以下寄存器空间：

- `AXI DMA CSR`
  - `MM2S_DMACR / DMASR / SA / LENGTH`
  - `S2MM_DMACR / DMASR / DA / LENGTH`

- `Preproc CSR`
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

对应的软件封装在：

- [radar_axi_dma_common.h](/home/soooarr/chipyard/tests/radar_axi_dma_common.h)

其中 `preproc_dump_status()` 会打印当前模式、参数、状态和 beat/frame 计数，便于板级验证。

### 1.4 当前 buffer 协议

当前已经把 CPU / DMA / future accelerator 共用的 buffer 访问规则固定下来，主要区域定义在：

- `buf_in`
- `buf_mid0`
- `buf_mid1`
- `buf_out`
- `desc_ring`

统一定义在：

- [radar_axi_dma_common.h](/home/soooarr/chipyard/tests/radar_axi_dma_common.h)

当前同时保留两种 buffer 访问方式：

- `cacheable DDR + cache maintenance`
- `uncached DDR alias`

其中 `uncached alias` 是当前为共享 buffer 引入的重要机制，用于避免 CPU D-cache 和 DMA 读写同一 DDR 区域时出现不一致。

### 1.5 当前软件测试入口

当前主要测试程序包括：

- [radar-axi-dma-loopback.c](/home/soooarr/chipyard/tests/radar-axi-dma-loopback.c)
- [radar-axi-dma-regression.c](/home/soooarr/chipyard/tests/radar-axi-dma-regression.c)
- [radar-axi-dma-preproc.c](/home/soooarr/chipyard/tests/radar-axi-dma-preproc.c)

其中 `radar-axi-dma-preproc.c` 已经作为当前阶段验证 AXIS 算子插槽的主测试程序。

例如，`ADD32` 测试的关键代码路径如下：

```c
preproc_clear_counters();
preproc_configure(PREPROC_MODE_ADD32, add_lo, add_hi, 1);
fill_add32_pattern(TEST_WORD_COUNT, 0x21000000u);
clear_rx_uncached(TEST_WORD_COUNT);
riscv_fence_rw_rw();

if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR,
                          (uint32_t)TEST_BYTE_COUNT) != 0) {
  printf("[ADD32] DMA run failed\n");
  return -1;
}

if (compare_add32_expected(TEST_WORD_COUNT, add_lo, add_hi) >= 0) {
  return -1;
}
```

这段代码的作用是：

- 配置 preproc 为 `ADD32`
- 由 CPU 在 `TX buffer` 写入输入模式
- DMA 将数据从 DDR 拉出送入 AXIS 算子
- 结果回写到 `RX buffer`
- CPU 进行 golden compare

---

## 2. 当前架构对雷达系统搭建进度的推动

### 2.1 当前阶段已经完成的内容

截至目前，这个 SoC 原型已经不是“只有 CPU 和 DDR 的最小系统”，而是已经完成了以下几件关键工作：

1. `CPU + UART-TSI` 运行稳定
2. `DDR` 读写稳定
3. `DMA CSR` 配置稳定
4. `MM2S / S2MM` 主数据通路板测通过
5. `uncached alias` 路径板测通过
6. `AXI-Stream preprocessor` 已真正接入并完成板测

这些内容对应的阶段摘要分别见：

- [152-final-loopback-pass-summary-2026-03-31.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/152-final-loopback-pass-summary-2026-03-31.md)
- [186-integrated-regression-with-uncached-pass-summary-2026-04-01.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/186-integrated-regression-with-uncached-pass-summary-2026-04-01.md)
- [213-preproc-pass-summary-2026-04-01.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/213-preproc-pass-summary-2026-04-01.md)

### 2.2 设计、验证、纠错过程总结

#### 2.2.1 各个组件的使用需求

当前这套 SoC 不是为了做一个最小 CPU 演示，而是为了给后续雷达前处理和 NN 加速预留一条可持续扩展的数据通路，因此各个组件的选择都有明确需求。

- `Rocket RISC-V CPU`
  - 需求来源：项目需要一个可控、可编译、可在 Chipyard 内部参数化的 RISC-V 软件控制核心
  - 具体作用：程序装载、寄存器配置、DMA 启动、结果比对、后续 SD 数据调度

- `DDR + MIG`
  - 需求来源：雷达数据帧和后续中间结果体量明显大于片上寄存器/BRAM 能力
  - 具体作用：作为 CPU、DMA、后续加速器共享的统一工作存储区

- `AXI DMA`
  - 需求来源：不能让 CPU 逐字搬运雷达数据，必须把 `DDR <-> 流计算` 这段交给硬件搬运
  - 具体作用：把 DDR 中的数据转换为 AXI-Stream，再把处理后的 AXI-Stream 写回 DDR

- `AXI Interconnect / AXI4-Lite / AXI4-Stream`
  - 需求来源：控制面和数据面需要分离，协议要与 Xilinx MIG 和 DMA IP 对接
  - 具体作用：
    - `AXI4`：主存搬运
    - `AXI4-Lite`：控制寄存器
    - `AXI4-Stream`：流式算子接口

当前架构的关键不是“协议种类多”，而是把控制面和数据面拆开，使后续加速器接入点固定为：

`DDR -> MM2S -> AXIS 算子 -> S2MM -> DDR`

#### 2.2.2 RISC-V 编译链与 Xilinx IP 集成中的冲突及解决

这一阶段的工作量主要不在单点 RTL，而是在工具链、串口装载、Xilinx 官方 IP 集成三条线同时收口。

第一类问题是 `RISC-V` 工具链支撑问题：

- `spike-devices` 构建时缺少 `fdt` 头文件路径
- 这会影响相关工具链组件的构建连续性
- 最终通过补充 include path 解决

对应记录：

- [radar_nexysvideo_submodule_patch_manifest_2026-03-31.md](/home/soooarr/chipyard/docs/radar_nexysvideo_submodule_patch_manifest_2026-03-31.md)
- `docs/submodule_patches/spike-devices-fdt-include-path.patch`

第二类问题是 `uart_tsi` 会话稳定性问题：

- 多次下载 `.riscv` 程序时，串口中残留的 stale bytes 会干扰新的装载会话
- 表现为第二个程序还没进入主体，就先在自检装载窗口失败
- 最终在 `testchip_uart_tsi.cc` 中增加 stale byte 丢弃逻辑解决

对应记录：

- [radar_nexysvideo_submodule_patch_manifest_2026-03-31.md](/home/soooarr/chipyard/docs/radar_nexysvideo_submodule_patch_manifest_2026-03-31.md)
- `docs/submodule_patches/testchipip-uart-tsi-stale-byte-discard.patch`

第三类问题是 `Xilinx` 官方 DMA / MIG IP 接入后的协议兼容问题：

- DMA 主读口最初在 `MM2S_LENGTH` 启动后立即异常
- 进一步定位后确认根因不在 C 程序，而在 MIG wrapper 一侧的 AXI ID 宽度处理
- 修复后，原来 `0xa5a5... / 0x31` 的污染读回消失

对应记录：

- [radar_nexysvideo_submodule_patch_manifest_2026-03-31.md](/home/soooarr/chipyard/docs/radar_nexysvideo_submodule_patch_manifest_2026-03-31.md)
- `docs/submodule_patches/fpga-shells-nexys-mig-idwidth-and-debug.patch`
- [152-final-loopback-pass-summary-2026-03-31.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/152-final-loopback-pass-summary-2026-03-31.md)

这一部分如果做截图，推荐截以下节点：

- `testchip_uart_tsi.cc` 的 stale byte 丢弃补丁
- `spike-devices/Makefile` 的 `fdt` include path 修复
- MIG wrapper 补丁说明文档中关于 AXI ID 宽度的描述

#### 2.2.3 CPU -> DMA -> DDR 主链是如何读通的

当前阶段并没有单独做复杂波形级 testbench，而是采用：

- 生成 Verilog/bitstream
- C 测试程序驱动
- 串口日志输出
- 板级结果 compare

的方式逐步读通 `CPU -> DMA -> DDR` 主链。

主链测试的关键点是：

1. CPU 先通过 MMIO 配置 DMA 寄存器
2. `S2MM` 配置目标地址
3. `MM2S` 配置源地址
4. DMA 从 DDR 读取数据，经流路径搬运后再写回 DDR
5. CPU 重新读回结果做 compare

当前公共封装中，DMA 的关键入口都已经统一在：

- [radar_axi_dma_common.h](/home/soooarr/chipyard/tests/radar_axi_dma_common.h)

对应的核心调用包括：

```c
dma_start_simple_s2mm(dst_addr, len);
dma_start_simple_mm2s(src_addr, len);
dma_wait_done("loopback");
```

后续在测试程序里直接通过：

```c
dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR, (uint32_t)TEST_BYTE_COUNT)
```

来跑一整次 loopback。

这一条链真正读通之前，出现过两个关键错误：

- `MM2S` 启动后立即异常，根因是 MIG 侧 AXI ID 宽度
- 主链修复后，结果在 `word 32` 开始不对，根因是 CPU / DMA cache 不一致

对应的最终通过结果为：

- [152-final-loopback-pass-summary-2026-03-31.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/152-final-loopback-pass-summary-2026-03-31.md)
- [186-integrated-regression-with-uncached-pass-summary-2026-04-01.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/186-integrated-regression-with-uncached-pass-summary-2026-04-01.md)

这一部分如果做截图，推荐截：

- `radar_axi_dma_common.h` 中 `dma_run_loopback_once()` 附近
- loopback 通过摘要
- integrated regression 通过摘要

#### 2.2.4 Preprocess 模块为什么要设计，以及如何测试

在 DMA 主链打通之后，继续设计 `RadarAXISPreprocessor` 的原因很明确：

- 仅有 `DDR -> DMA -> DDR` 还只是数据搬运链
- 后续雷达前处理和 NN 模块都需要一个明确的硬件算子接入位置
- 如果不先把 AXIS 算子插槽打通，后续每个新模块都要重新处理 DMA 接口和控制寄存器问题

因此当前先接入一个轻量级、可配置的预处理模块，放在：

`MM2S -> RadarAXISPreprocessor -> S2MM`

其目的不是直接实现完整雷达算法，而是先验证三件事：

1. AXIS 模块是否能被 DMA 流路径稳定驱动
2. 算子结果是否能回写到 DDR 并被 CPU 比对
3. beat/frame 计数器是否与传输长度一致

当前测试程序是：

- [radar-axi-dma-preproc.c](/home/soooarr/chipyard/tests/radar-axi-dma-preproc.c)

测试方式分为两类：

- `ADD32`
  - CPU 先生成输入数组
  - 低 32 位加 `PARAM0`
  - 高 32 位加 `PARAM1`
  - 结果写回后由 CPU 做 golden compare

- `RELU16`
  - CPU 生成正负混合的 `16-bit lane` 输入
  - AXIS 算子做 ReLU + clip
  - 结果写回后由 CPU 做 golden compare

`ADD32` 的关键代码节点如下：

```c
preproc_clear_counters();
preproc_configure(PREPROC_MODE_ADD32, add_lo, add_hi, 1);
preproc_dump_status("[ADD32] configured");

fill_add32_pattern(TEST_WORD_COUNT, 0x21000000u);
clear_rx_uncached(TEST_WORD_COUNT);
riscv_fence_rw_rw();

if (dma_run_loopback_once(TX_BUFFER_ADDR, RX_BUFFER_ADDR,
                          (uint32_t)TEST_BYTE_COUNT) != 0) {
  printf("[ADD32] DMA run failed\n");
  return -1;
}
```

当前已经完成的板级结果为：

```text
[ADD32] compare passed
[ADD32] counters: in=32 out=32 frames=1
[RELU16] compare passed
[RELU16] counters: in=32 out=32 frames=1
AXI DMA preprocessor PASSED
```

对应日志：

- [212-run-dma-preproc-after-cpu-reset-2026-04-01.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/212-run-dma-preproc-after-cpu-reset-2026-04-01.log)
- [213-preproc-pass-summary-2026-04-01.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/213-preproc-pass-summary-2026-04-01.md)

这一部分如果做截图，推荐截：

- `radar-axi-dma-preproc.c` 中 `run_add32_case()` 和 `run_relu16_case()` 片段
- 日志中 `configured / compare passed / counters` 三组输出
- `AXI DMA preprocessor PASSED`

### 2.3 对后续雷达系统搭建的直接推动

当前架构已经把后续雷达系统最底层的几项公共问题提前解决了：

- CPU 软件控制骨架已经有了
- DDR 统一工作空间已经有了
- DMA 数据搬运骨架已经有了
- 共享 buffer 协议已经固定了
- AXIS 可插拔算子位置已经有了

所以后续如果接入新的雷达前处理模块，工作重点不再是“从零搭 SoC”，而是：

- 在现有 AXIS 数据槽位中继续插入新算子
- 复用当前 DDR buffer 和 DMA 调度方式
- 在现有 C 测试框架中继续做 compare 和板测

换句话说，当前阶段已经把“CPU + 硬件加速器”这条异构路径从概念推进到了可运行的系统原型。

---

## 3. 整体性能说明

### 3.1 当前板级性能结论

当前阶段已经能明确确认以下功能性能结论：

- `DDR -> MM2S -> S2MM -> DDR` loopback 稳定通过
- `cacheable + cache maintenance` 路径通过
- `uncached alias` 路径通过
- 单 ELF 综合回归通过
- `ADD32` 板测通过
- `RELU16` 板测通过

这说明当前系统已经具备：

- 主存到流计算链的数据搬运能力
- 流式算子接入能力
- 软件到硬件再回软件的完整校验闭环

### 3.2 当前已实现的资源与时序结果

当前已板测通过、包含 `preproc` 的稳定版本，其实现结果为：

- 主频：`50 MHz`
- `WNS = 0.894 ns`
- `WHS = 0.050 ns`
- `LUT = 24991`
- `FF = 15950`
- `RAMB36 = 2`
- `RAMB18 = 14`
- `DSP = 10`

这说明：

- 目前 `50 MHz` 版本是收敛并已实测通过的版本
- 当前板级资源尚未接近耗尽
- 频率上限更受时序路径影响，而不是受资源数量影响

### 3.3 当前 AXIS preproc 的验证方式

当前 `preproc` 不是仅做仿真验证，而是做了以下完整链路验证：

1. CPU 生成或写入输入数据
2. CPU 配置 preproc CSR
3. CPU 启动 DMA
4. DMA 把数据从 DDR 送入 AXIS 算子
5. AXIS 算子处理数据
6. S2MM 写回 DDR
7. CPU 读取结果并 compare
8. CPU 核对 `IN/OUT/FRAMES` 计数器

这套验证方式已经能够覆盖：

- 数据内容是否正确
- beat 数量是否匹配
- frame 结束是否正确
- 数据是否真正经过硬件算子而不是旁路

### 3.4 当前频率提升测试结果

本阶段还额外做了一个频率上探，目的不是换正式配置，而是判断当前系统频率边界。

当前已知结果如下：

- `50 MHz`
  - 当前稳定版本
  - 已板测通过

- `60 MHz`
  - 可进入实现
  - 最终时序失败
  - 失败量级：`-1.381 ns`
  - 日志：
    [220-fpga-bitstream-60mhz-2026-04-05.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/220-fpga-bitstream-60mhz-2026-04-05.log)

- `75 MHz`
  - 可进入实现
  - 最终时序失败
  - 失败量级：`-3.059 ns`
  - 关键路径摘要：
    [217-75mhz-criticalpath-summary-2026-04-05.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/217-75mhz-criticalpath-summary-2026-04-05.md)

- `65 MHz`
  - 未进入最终 timing 判断
  - 先被 PLL jitter 门限挡住
  - 日志：
    [219-fpga-bitstream-65mhz-2026-04-05.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/219-fpga-bitstream-65mhz-2026-04-05.log)

- `66.667 MHz`
  - 未进入实现
  - 先被 harness 频率整数化问题挡住
  - 日志：
    [218-fpga-bitstream-66p667mhz-2026-04-05.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/218-fpga-bitstream-66p667mhz-2026-04-05.log)

当前可以得出的实际结论是：

- 稳定已通过版本是 `50 MHz`
- 继续上探时，`60 MHz` 已经开始明显不收敛
- 当前项目的有效频率上限大致位于 `50~60 MHz` 区间内

### 3.5 当前关键路径结论

对 `75 MHz` 的关键路径做了专门读取，当前最坏路径不在 `preproc` 算子本体，也不在 Rocket 的运算单元本体，而是在：

- `fbus`
- `tsi2tl`
- `queue / buffer RAM`

也就是更偏 SoC 前端运输与装载路径，而不是当前新增的 AXIS 算子链本身。

这一点对后续工作有两个直接结论：

- 现阶段不能把频率上不去简单归因到 `preproc`
- 当前 SoC 如果继续提频，优先需要关注的是前端总线/装载路径，而不是先重写 AXIS 算子

---

## 附：本阶段关键记录文件

- 总体主记录页：  
  [radar_nexysvideo_system_arch.html](/home/soooarr/chipyard/docs/radar_nexysvideo_system_arch.html)

- AXIS preproc 结构页：  
  [radar_nexysvideo_axi_preproc_bd.html](/home/soooarr/chipyard/docs/radar_nexysvideo_axi_preproc_bd.html)

- preproc 说明：  
  [radar_nexysvideo_stream_preproc_2026-04-01.md](/home/soooarr/chipyard/docs/radar_nexysvideo_stream_preproc_2026-04-01.md)

- loopback 最终通过摘要：  
  [152-final-loopback-pass-summary-2026-03-31.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/152-final-loopback-pass-summary-2026-03-31.md)

- integrated regression 通过摘要：  
  [186-integrated-regression-with-uncached-pass-summary-2026-04-01.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/186-integrated-regression-with-uncached-pass-summary-2026-04-01.md)

- preproc 板测通过摘要：  
  [213-preproc-pass-summary-2026-04-01.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/213-preproc-pass-summary-2026-04-01.md)

- 75 MHz 关键路径摘要：  
  [217-75mhz-criticalpath-summary-2026-04-05.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/217-75mhz-criticalpath-summary-2026-04-05.md)
