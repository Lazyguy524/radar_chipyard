# Radar Nexys Video 当前系统整理文档

更新时间：2026-03-31

## 1. 文档目标

这份文档用于总结当前 `Nexys Video + Chipyard + Rocket + DDR + AXI DMA` 项目的**实际可运行状态**，重点是：

- 当前系统到底长成什么样
- 哪些链路已经被板级验证通过
- 当前软件与硬件之间的真实边界条件是什么
- 仓库里哪些文件是这个系统的关键组成部分
- 后续继续扩展时应该沿着什么方向推进

本文档**不记录 debug 过程**，只保留当前已经确认成立的系统结论。

---

## 2. 当前项目结论

截至本次整理，当前系统已经完成以下板级验证：

1. `UART-TSI` 串口下载与自检工作正常。
2. Rocket CPU 能稳定启动并执行裸机测试程序。
3. DDR 作为系统主存可被 CPU 正常访问。
4. DMA 的 CSR 控制口已经稳定可用。
5. DMA 的 `MM2S` 主读口已经修通。
6. DMA 的 `S2MM` 主写口已经修通。
7. 在当前 loopback 测试结构下，端到端的 `DDR -> MM2S -> AXIS -> S2MM -> DDR` 已经通过。

因此，从系统 bring-up 的角度讲，这个项目的主链路已经跑通。

但需要明确一个非常重要的系统约束：

> 当前 Rocket 核心的 D-cache 与 AXI DMA **不是硬件自动一致性（coherent）** 的关系。
> 只要 CPU 和 DMA 共享的 buffer 仍然放在 cacheable DDR 中，软件就必须显式执行 cache maintenance 或等效的 eviction/flush/invalidate 手段。

这个约束不代表系统没跑通，而是代表**系统已经跑通，但它有明确的软件使用协议**。

---

## 3. 当前硬件平台概况

### 3.1 FPGA 平台

- 开发板：`Digilent Nexys Video`
- DDR 控制器：板载 `MIG`
- 板级验证环境：通过 `uart_tsi` 将程序下载到 DDR 后在 Rocket 上运行

### 3.2 SoC 主体

根据当前生成 DTS，系统核心参数如下：

- CPU：`1 x Rocket`
- ISA：`rv64imac_zicsr_zifencei_zihpm_xrocket`
- I-cache：`4 KiB`
- D-cache：`4 KiB`
- cache line：`64 B`
- 主存窗口：`0x8000_0000` 起，大小 `0x2000_0000`，也就是 `512 MiB`
- 当前 bus clocks：DTS 中显示为 `50 MHz`

### 3.3 当前验证所使用的配置风格

当前系统并不是“单纯的 CPU + DDR”最小系统，而是在此基础上额外挂接了一个内部接好的 AXI DMA，用于做：

- CPU 通过 MMIO 配置 DMA
- DMA 直接作为 AXI master 访问 DDR
- MM2S 和 S2MM 之间通过内部 AXI-Stream 回环做自检

也就是说，这个系统已经具备了一个非常有价值的能力：

> CPU 不只是能“看到 DMA”，而是能真正驱动 DMA 去搬 DDR 中的数据，并得到可验证的返回结果。

---

## 4. 系统架构拆解

### 4.1 控制面

控制面是 CPU 配置 DMA 的那部分路径。其逻辑关系可以概括为：

`Rocket CPU -> SoC bus fabric -> AXI4-MMIO aperture -> DMA CSR`

这条链路负责：

- DMA reset
- DMA run/stop
- MM2S 源地址配置
- S2MM 目的地址配置
- 传输长度配置
- 运行状态读取

当前这条链路已经稳定，表现在：

- reset 后寄存器可正常读写
- `MM2S` / `S2MM` 配置过程不会再出现控制口级别的卡死
- `radar-axi-mmio-smoke.riscv` 可以通过

### 4.2 数据面

数据面是 DMA 实际搬运数据的路径，逻辑关系如下：

1. `MM2S` 作为 AXI 读主设备，从 DDR 中读取源 buffer。
2. 读出的 payload 进入 `m_axis_mm2s`。
3. 当前测试中，`m_axis_mm2s` 直接接回 `s_axis_s2mm`，形成内部 stream loopback。
4. `S2MM` 作为 AXI 写主设备，把收到的数据写入目的 buffer。
5. CPU 最后读取目的 buffer，并与源 buffer 做比较。

因此，当前测试验证的不是“DMA 的某一个局部子功能”，而是：

> 从 DDR 发起真实 AXI Read，到 AXI-Stream 中转，再到真实 AXI Write 回 DDR 的完整端到端路径。

### 4.3 DDR/MIG 位置

DDR 不是由 Rocket 内核直接裸连，而是通过 Nexys Video 对应的 MIG wrapper 接入整个设计。当前这层 wrapper 还承载了：

- Rocket/TL 到 AXI 的 DDR 路径
- DMA 的 MM2S AXI 主口
- DMA 的 S2MM AXI 主口

也正因为如此，这一层是本项目中**最关键的系统汇合点之一**。

---

## 5. 地址空间与当前测试布局

### 5.1 主存地址空间

当前 DDR 主存区域为：

- 基地址：`0x8000_0000`
- 大小：`0x2000_0000`

### 5.2 DMA 控制窗口

当前外设 AXI4 MMIO aperture 位于：

- `0x6000_0000 - 0x6000_ffff`

DMA 控制寄存器就在这个窗口内。

### 5.3 当前测试 buffer 布局

当前 `radar-axi-dma-loopback.c` 及相关测试使用了以下地址：

- TX buffer：`0x8100_0000`
- RX buffer：`0x8100_1000`
- cache sweep buffer：`0x8101_0000`

当前 loopback 测试长度为：

- `64 words`
- `256 bytes`

这个测试规模不大，但它足以验证：

- MM2S 是否能真正把 DDR 数据读出来
- AXIS 路是否能传过去
- S2MM 是否能真正把数据写回 DDR
- 最终软件是否能看到正确结果

---

## 6. DMA 子系统当前状态

### 6.1 DMA 能力概况

当前设计中已经接入一个 Xilinx AXI DMA 风格的 DMA 模块，具备：

- `MM2S`：从 memory 读取，送入 stream
- `S2MM`：从 stream 接收，写回 memory
- AXI master data width：`64 bit`
- AXI stream width：`64 bit`

### 6.2 当前验证模式

当前项目跑通的是“内部 loopback 自检模式”，也就是：

- `m_axis_mm2s_tdata/tkeep/tvalid/tlast`
- 直接接到
- `s_axis_s2mm_tdata/tkeep/tvalid/tlast`

这代表当前 DMA 已经具备作为一个板上数据搬运核心的基础能力，后续完全可以把这段内部 loopback 替换成：

- 你自己的 stream 处理模块
- 雷达前端数据通路
- 其它 AXI-Stream 算法模块

### 6.3 当前 DMA 的软件使用方式

当前测试软件的基本流程是：

1. 填充 TX buffer
2. 清空 RX buffer
3. 做一次 Pre-DMA cache sweep
4. reset MM2S / S2MM
5. 配置 S2MM 目的地址和长度
6. 配置 MM2S 源地址和长度
7. 等待 DMA 完成
8. 做一次 Post-DMA cache sweep
9. 比较 TX 和 RX buffer

这个流程已经被证明能够在当前硬件上通过。

---

## 7. 当前已经确认的两个系统问题与最终结论

虽然本文档不记录 debug 过程，但为了让系统结论完整，必须把当前“已经被修掉的问题”和“仍然成立的运行条件”写清楚。

### 7.1 已经修复的硬件问题

当前系统曾经存在一个真正的硬件级问题：

- MIG 黑盒只支持 `4-bit AXI ID`
- 但 Nexys Video 对应 wrapper 那一层的共享 xbar 上，实际参与路由的 ID 宽度曾超出这个范围
- 导致 MM2S 发起 DDR 读后，返回响应在系统中被错误路由或截断

该问题修复后，原来那种：

- 一写 `MM2S_LENGTH` 就立刻出错
- 或者寄存器读回被异常污染

的现象已经消失。

这意味着：

> 当前 `MM2S` 的主读口硬件问题已经被修通。

### 7.2 当前仍然成立的软件约束

在硬件问题修掉之后，系统又暴露出另一个问题：

- CPU 写完 TX buffer 后，DMA 读到的并不总是 CPU 刚写的值
- DMA 写完 RX buffer 后，CPU 直接比较时也不一定能马上读到新数据

最终确认原因是：

- Rocket D$ 与 DMA 不是自动 coherent 的
- buffer 在 cacheable DDR 中
- 因此必须在软件中显式执行 cache maintenance

因此，当前系统的正确理解应该是：

> 硬件主链路已经跑通；  
> 软件若要正确共享 DMA buffer，必须遵守 cache maintenance 约束。

---

## 8. 当前“跑通”到底意味着什么

很多项目在 bring-up 阶段会出现“某一小段看起来是通的，但整个系统并不能真正工作”的情况。  
当前这个项目不是那种状态。

目前“跑通”具体意味着：

1. CPU 可以启动并执行自定义裸机程序。
2. CPU 可以通过 MMIO 完整配置 DMA。
3. DMA 的 MM2S 可以从 DDR 发起真实 AXI Read。
4. DMA 的 S2MM 可以对 DDR 发起真实 AXI Write。
5. AXI-Stream 回环链路已通。
6. 端到端 loopback 在板上已通过。

也就是说，当前系统已经具备了一个完整的、可被软件驱动的数据搬运闭环。

从系统工程角度，这已经不再是“零散模块拼起来了”，而是一个**真正可工作的基础原型**。

---

## 9. 仓库中的关键文件与它们的职责

下面列出当前项目里最关键的一批文件，方便后续维护。

### 9.1 顶层与板级集成

- `fpga/src/main/scala/nexysvideo/Harness.scala`
  - Nexys Video 顶层 harness
  - 负责把 DDR overlay、DMA、外设连接到板级壳层中

- `fpga/src/main/scala/nexysvideo/HarnessBinders.scala`
  - 负责把 UART-TSI、DDR、AXI4-MMIO 等绑定到 harness
  - 也承载了本次 bring-up 中的 LED 观测口导出

### 9.2 DMA 本体

- `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
  - DMA blackbox 的 Chisel 包装
  - AXI4 / AXIS 接线
  - 当前的调试计数和状态观测逻辑也在这里

### 9.3 DDR/MIG 关键层

- `fpga/fpga-shells/src/main/scala/devices/xilinx/xilinxnexysvideomig/XilinxNexysVideoMIG.scala`
  - Nexys Video MIG wrapper
  - 当前已经包含了与 MM2S 返回路由修复相关的关键逻辑

### 9.4 测试程序

- `tests/radar-axi-mmio-smoke.c`
  - 验证 DMA CSR 控制面是否正常

- `tests/radar-axi-dma-loopback.c`
  - 当前正式的端到端 loopback 回归测试
  - 已经加入 cache sweep，以满足当前系统的 cache maintenance 约束

- `tests/radar-axi-dma-loopback-cacheprobe.c`
  - 用于验证单纯“后处理 eviction”是否足够

- `tests/radar-axi-dma-loopback-cachemaint.c`
  - 用于验证加上前后 cache maintenance 后，系统可完整通过

- `tests/htif_crt0.S`
  - 当前 bring-up 裸机程序的启动入口

- `tests/htif_nolib.c`
  - 当前最小运行时依赖

### 9.5 当前文档

- `docs/radar_nexysvideo_system_arch.html`
  - 可视化架构图说明

- `docs/radar_nexysvideo_current_system_guide_2026-03-31.md`
  - 当前这份详细中文整理文档

---

## 10. 当前软件测试体系说明

### 10.1 `hello.riscv`

作用：

- 验证 CPU、UART、最基本运行环境是否健康

### 10.2 `radar-axi-mmio-smoke.riscv`

作用：

- 验证 DMA 的 MMIO CSR 通路
- 重点确认 reset/config/readback 是否健康

### 10.3 `radar-axi-dma-loopback.riscv`

作用：

- 当前最重要的系统级测试
- 验证 DMA 从 DDR 读出，再写回 DDR 的端到端 loopback

当前状态：

- 已通过
- 但依赖 cache sweep

### 10.4 `radar-axi-dma-loopback-cacheprobe.riscv`

作用：

- 用于区分“单纯 compare 时 cache stale”与“DMA 源/目的 buffer 都需要维护”的问题

### 10.5 `radar-axi-dma-loopback-cachemaint.riscv`

作用：

- 证明在加入前后 cache sweep 后，系统是完整工作的

---

## 11. 当前系统的运行约束

为了避免后续使用中再掉回“为什么又不对了”的状态，下面把当前系统最重要的运行约束单独列出来。

### 11.1 约束一：CPU 和 DMA 共享 cacheable DDR 时，要做 cache maintenance

这是当前最重要的一条。

如果以后继续采用：

- CPU 在 DDR 中准备 buffer
- DMA 直接从该 buffer 读写

那么必须考虑：

- DMA 启动前，CPU 写入过的 TX buffer 是否已经对 DDR 可见
- DMA 完成后，CPU 再读 RX buffer 时是否已经丢掉旧的 cache line

### 11.2 约束二：不要把 UART-TSI 当成系统数据通路的一部分

UART-TSI 是：

- 下载程序
- 自检
- 少量 debug init_read/init_write

它不是目标系统运行时的数据路径，不应与 DMA 数据路径混淆。

### 11.3 约束三：当前通过的是单段 loopback 基础能力

这意味着现在最稳定的“已通过定义”是：

- 单段源地址
- 单段目的地址
- 固定长度
- 内部 stream loopback

如果后续扩展到更复杂的 scatter-gather、长时间流式输入、外部 stream producer/consumer，需要继续增加覆盖测试。

---

## 12. 当前系统适合做什么

从目前状态来看，这个项目已经适合作为以下工作的基础平台：

### 12.1 作为 DMA/DDR 数据搬运基座

你现在已经拥有一个真实可工作的最小平台，可用于：

- 内存到内存搬运验证
- AXIS 前后级模块验证
- 更复杂 DMA 工作流的基础测试

### 12.2 作为雷达数据通路原型平台

如果后面你要把当前 loopback 替换成真正的雷达数据通道，那么当前结构已经很合适：

- MM2S 从 DDR 取输入
- 中间插入你的 stream 处理链
- S2MM 把结果写回 DDR
- CPU 读取结果并做后处理/校验

### 12.3 作为后续系统化优化的起点

下一阶段如果想让系统更“产品化”，可以考虑：

- uncached buffer 区域
- 更明确的 DMA buffer 管理策略
- 真正的 cache coherence 方案
- 更丰富的 DMA test suite
- 自动化 bitstream + regression 流程

---

## 13. 建议的下一阶段工作

按优先级排序，推荐后续工作如下。

### 13.1 第一优先级：把“buffer 使用协议”标准化

建议把当前 cache maintenance 约束变成明确规范，例如：

- 哪些地址区可以作为 DMA buffer
- DMA 启动前需要做什么
- DMA 完成后需要做什么
- 哪些 API 负责 sweep / flush / invalidate

### 13.2 第二优先级：把 loopback 升级成可插拔 stream 链

当前 MM2S 与 S2MM 之间是直接回环。下一步可引入：

- 数据过滤
- 格式整理
- FFT / 雷达相关预处理模块
- 自定义 AXI-Stream 算法块

### 13.3 第三优先级：补自动化回归

建议至少固化以下自动化检查：

- `hello`
- `radar-axi-mmio-smoke`
- `radar-axi-dma-loopback`

这样以后每次改 DMA、MIG wrapper、harness binder 或软件测试，都可以快速回归。

---

## 14. 总结

当前这个项目已经完成了从“板子能起来”到“CPU 能驱动 DMA 经由 DDR 完整搬运数据”的跃迁。

它现在不是一个只在结构图上成立的系统，而是一个已经在实际 Nexys Video 板子上证明：

- CPU 可用
- DDR 可用
- MMIO 可用
- DMA 可用
- AXI interconnect 可用
- MM2S/S2MM 可用
- 端到端 loopback 可用

的系统原型。

因此，当前项目最准确的定位是：

> 一个已经完成主链路打通、可继续承载更复杂流式数据处理工作的 Nexys Video 原型平台。

而当前最需要牢记的现实条件只有一条：

> Rocket cache 与 DMA 之间还没有自动一致性；共享 cacheable buffer 时，软件要负责 cache maintenance。

只要遵守这条系统协议，当前平台已经能够稳定支撑后续开发。
