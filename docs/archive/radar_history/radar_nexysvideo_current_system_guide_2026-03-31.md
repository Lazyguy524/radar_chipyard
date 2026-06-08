# Radar Nexys Video 当前系统整理文档

更新时间：2026-04-01

## 1. 文档目标

这份文档用于总结当前 `Nexys Video + Chipyard + Rocket + DDR + AXI DMA` 项目的**实际可运行状态**。本文档只记录当前已经成立的系统结论、结构、边界和建议，不记录具体 debug 过程。

本文档重点回答五个问题：

1. 当前系统架构到底长成什么样。
2. 哪些链路已经在板上被验证通过。
3. CPU、DDR、DMA、互连之间目前真实的工作关系是什么。
4. 当前软件应该如何正确使用 DMA buffer。
5. 仓库里哪些文件是这套系统的关键组成部分。

---

## 2. 当前项目总结论

截至 2026-04-01，当前系统已经完成以下板级验证：

1. `UART-TSI` 串口下载、自检和程序运行正常。
2. Rocket CPU 可以稳定启动并执行裸机测试程序。
3. DDR 主存可以被 CPU 正常访问。
4. DMA 的 CSR 控制口已经稳定可用。
5. DMA 的 `MM2S` 主读口已经修通。
6. DMA 的 `S2MM` 主写口已经修通。
7. 端到端的 `DDR -> MM2S -> AXIS -> S2MM -> DDR` loopback 已经在板上通过。
8. `ExtTLMem` 的 `uncached alias` 路径已经在板上验证通过。
9. 单 ELF 综合回归已经同时覆盖 `cache-maint` 路径与 `uncached-alias` 路径，并在板上通过。

因此，从系统 bring-up 的角度看，这个项目的主链路已经跑通，而且当前已经具备**两条都能工作的 DMA buffer 使用路径**：

1. `cacheable DDR + 软件 cache maintenance`
2. `uncached DDR alias + 无需 cache maintenance`

这说明当前系统不只是“基础链路勉强可用”，而是已经具备了面向后续流式处理扩展的稳定原型形态。

---

## 3. 当前系统最重要的边界条件

### 3.1 cacheable DDR 路径

如果 CPU 和 DMA 共享的 buffer 仍然放在 Rocket 眼里是 **cacheable DDR** 的地址空间里，那么：

- Rocket D-cache 与 AXI DMA 不是自动 coherent 的；
- CPU 写 TX buffer 后，如果不做 cache maintenance，DMA 可能从 DDR 读到旧值；
- DMA 写 RX buffer 后，如果 CPU 不做 cache maintenance，再比较时也可能读到 cache 里的旧数据。

所以这条路径下，软件必须显式做 cache maintenance 或等效 eviction/flush/invalidate。

### 3.2 uncached alias 路径

当前系统已经新增并验证通过了一条 **uncached DDR alias** 路径：

- DMA 仍然使用原始 DDR 地址；
- CPU 改为通过 uncached alias 地址访问同一片物理 DDR buffer；
- 这样 CPU 读写 DMA buffer 时可以绕开 Rocket D-cache；
- 当前测试已经证明这条路径下 loopback 无需额外 cache maintenance 也能通过。

这意味着当前系统已经不只有“靠软件 sweep 才能正确工作”的一种方案。

---

## 4. 当前硬件平台概况

### 4.1 FPGA 平台

- 开发板：`Digilent Nexys Video`
- DDR 控制器：板载 `MIG`
- 板级验证方式：通过 `uart_tsi` 将程序下载到 DDR 后在 Rocket 上运行

### 4.2 SoC 主体

根据当前生成 DTS 和现有配置，系统核心参数如下：

- CPU：`1 x Rocket`
- ISA：`rv64imac_zicsr_zifencei_zihpm_xrocket`
- I-cache：`4 KiB`
- D-cache：`4 KiB`
- cache line：`64 B`
- 主存窗口：`0x8000_0000` 起，大小 `0x2000_0000`，即 `512 MiB`
- 当前 bus clocks：`50 MHz`

### 4.3 当前板级配置风格

当前系统并不是“单纯的 CPU + DDR”最小系统，而是在此基础上额外挂接了一个内部接好的 AXI DMA，用于完成：

- CPU 通过 MMIO 配置 DMA；
- DMA 直接作为 AXI master 访问 DDR；
- MM2S 和 S2MM 之间通过内部 AXI-Stream 回环做自检。

这意味着当前系统已经具备一个非常关键的能力：

> CPU 不只是能“看到 DMA”，而是能真正驱动 DMA 去搬 DDR 中的数据，并得到可验证的返回结果。

---

## 5. 系统架构拆解

### 5.1 控制面

控制面可以概括为：

`Rocket CPU -> SoC bus fabric -> AXI4-MMIO aperture -> DMA CSR`

它负责：

- DMA reset
- DMA run/stop
- MM2S 源地址配置
- S2MM 目的地址配置
- 传输长度配置
- 运行状态读取

当前这条链路已经稳定，`radar-axi-mmio-smoke.riscv` 可以通过。

### 5.2 数据面

数据面是真正的搬运链路，当前逻辑关系如下：

1. `MM2S` 作为 AXI 读主设备，从 DDR 中读取源 buffer。
2. 读出的 payload 进入 `m_axis_mm2s`。
3. 当前测试中，`m_axis_mm2s` 直接接回 `s_axis_s2mm`，形成内部 stream loopback。
4. `S2MM` 作为 AXI 写主设备，把收到的数据写入目的 buffer。
5. CPU 最后读取目的 buffer，并与源 buffer 做比较。

这代表当前验证的是一条完整的端到端真实路径，而不是某个局部模块的单点自检。

### 5.3 DDR/MIG 位置

DDR 通过 Nexys Video 的 MIG wrapper 接入整个设计。这一层承载了：

- Rocket/TL 到 DDR 的主存访问路径；
- DMA 的 MM2S AXI 主口；
- DMA 的 S2MM AXI 主口。

这也是本项目最关键的系统汇合点之一。

---

## 6. 地址空间与当前测试布局

### 6.1 主存地址空间

当前 DDR 主存区域为：

- 基地址：`0x8000_0000`
- 大小：`0x2000_0000`

### 6.2 uncached alias 地址空间

当前还额外实现了一条 uncached alias 视图：

- alias 基地址：`0x1080_000000`
- alias 大小：`0x2000_0000`

它和 `0x8000_0000` 这片 DDR 指向同一块物理内存，只是 CPU 通过 alias 访问时，不再走原有的 cacheable 视图。

补充说明：

- 当前这条 alias 已经在物理实现中生效；
- 但它还没有被正式写入现有 DTS 的 `memory` 描述里；
- 所以当前测试程序里是直接按约定地址使用，而不是从设备树动态发现。

### 6.3 DMA 控制窗口

当前外设 AXI4 MMIO aperture 位于：

- `0x6000_0000 - 0x6000_ffff`

DMA 控制寄存器就在这个窗口内。

### 6.4 当前测试 buffer 布局

当前 DMA bring-up 系列测试使用以下地址：

- TX buffer：`0x8100_0000`
- RX buffer：`0x8100_1000`
- cache sweep buffer：`0x8101_0000`

在 uncached alias 模式下，同一批 DMA buffer 会从 CPU 侧变成：

- TX buffer CPU alias：`0x1081_000000`
- RX buffer CPU alias：`0x1081_001000`

当前标准 loopback 测试长度为：

- `64 words`
- `256 bytes`

另外，多长度 consistency 回归已经覆盖：

- `4 / 8 / 15 / 16 / 31 / 32 / 33 / 63 / 64 words`

---

## 7. DMA 子系统当前状态

### 7.1 DMA 能力概况

当前设计中已经接入一个 Xilinx AXI DMA 风格的 DMA 模块，具备：

- `MM2S`：从 memory 读取，送入 stream
- `S2MM`：从 stream 接收，写回 memory
- AXI master data width：`64 bit`
- AXI stream width：`64 bit`

### 7.2 当前验证模式

当前项目跑通的是“内部 loopback 自检模式”，也就是：

- `m_axis_mm2s_tdata/tkeep/tvalid/tlast`
- 直接接到
- `s_axis_s2mm_tdata/tkeep/tvalid/tlast`

这意味着当前 DMA 已经具备了作为板上数据搬运核心的基础能力，后续可以把这段内部回环替换成：

- 雷达预处理模块
- 其它自定义 AXI-Stream 算法块
- NN 或信号处理前级模块

### 7.3 cacheable DDR 路径下的软件使用方式

当前 `cache-maint` 版本的标准流程是：

1. 填充 TX buffer
2. 清空 RX buffer
3. 做一次 Pre-DMA cache sweep
4. reset MM2S / S2MM
5. 配置 S2MM 目的地址和长度
6. 配置 MM2S 源地址和长度
7. 等待 DMA 完成
8. 做一次 Post-DMA cache sweep
9. 比较 TX 和 RX buffer

这条路径已经被证明能够在当前硬件上稳定通过。

### 7.4 uncached alias 路径下的软件使用方式

当前新增的另一条使用方式是：

1. DMA 仍然使用原始 DDR 地址作为源/目的地址
2. CPU 不再通过 cacheable 视图读写 buffer
3. CPU 改为通过 `0x1080_000000` 起的 uncached alias 访问同一片物理 DDR
4. DMA 完成后，CPU 直接经 alias 地址比较 TX/RX

这条路径也已经通过板测，说明当前系统已经具备一条不依赖 cache maintenance 的 DMA buffer 使用方案。

---

## 8. 当前已经确认的系统问题与最终结论

### 8.1 已经修复的硬件问题一：MIG AXI ID 宽度不匹配

当前系统曾经存在一个真正的硬件级问题：

- MIG 黑盒只支持 `4-bit AXI ID`
- 但 Nexys Video 对应 wrapper 那一层的共享 xbar 上，实际参与路由的 ID 宽度一度超出这个范围
- 导致 MM2S 发起 DDR 读后，返回响应在系统中被错误路由或截断

该问题修复后，原来那种：

- 一写 `MM2S_LENGTH` 就立刻出错
- 或者寄存器读回被异常污染

的现象已经消失。

结论是：

> 当前 `MM2S` 的主读口硬件问题已经修通。

### 8.2 当前仍然成立的软件约束：cacheable 路径不自动一致

在硬件问题修掉之后，系统又暴露出另一个问题：

- CPU 写完 TX buffer 后，DMA 读到的不一定是 CPU 刚写的值
- DMA 写完 RX buffer 后，CPU 直接比较时也不一定能马上读到新数据

最终确认原因是：

- Rocket D$ 与 DMA 不是自动 coherent 的
- buffer 在 cacheable DDR 中
- 所以必须在软件中显式执行 cache maintenance

因此，对 cacheable DDR 路径的正确理解是：

> 硬件主链路已经跑通；  
> 如果继续在 cacheable DDR 中共享 DMA buffer，软件就必须遵守 cache maintenance 约束。

### 8.3 已经补上的系统级一致性缓解：uncached alias

为了解决“每次都靠软件 sweep”的使用门槛，当前系统又增加了一条系统级缓解路径：

- 为 `ExtTLMem` 增加了 DDR 的 uncached alias 视图
- 修正了 alias 接入后 `tl_mem source` 宽度被顶层截断的问题
- 最终让 CPU 能通过 uncached alias 访问 DMA buffer，而 DMA 继续使用原始 DDR 地址

这意味着当前项目已经不只是“知道不一致性问题存在”，而是已经在板上证明了一种实际可用的规避方案。

---

## 9. 当前“跑通”到底意味着什么

当前“跑通”具体意味着：

1. CPU 可以启动并执行自定义裸机程序。
2. CPU 可以通过 MMIO 完整配置 DMA。
3. DMA 的 MM2S 可以从 DDR 发起真实 AXI Read。
4. DMA 的 S2MM 可以对 DDR 发起真实 AXI Write。
5. AXI-Stream 回环链路已经打通。
6. 端到端 loopback 在板上已通过。
7. `uncached alias` 下的 DMA loopback 在板上已通过。
8. 单 ELF 综合回归已经覆盖 `cache-maint` 与 `uncached-alias` 两条路径，并在板上通过。

也就是说，当前系统已经具备一个完整、可被软件稳定驱动的数据搬运闭环。

---

## 10. 仓库中的关键文件与它们的职责

### 10.1 顶层与板级集成

- `fpga/src/main/scala/nexysvideo/Harness.scala`
  - Nexys Video 顶层 harness
  - 负责把 DDR overlay、DMA、外设连接到板级壳层中

- `fpga/src/main/scala/nexysvideo/HarnessBinders.scala`
  - 负责把 UART-TSI、DDR、AXI4-MMIO 等绑定到 harness
  - 也承载了这次 bring-up 中的 LED 观测口导出

### 10.2 DMA 本体

- `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
  - DMA blackbox 的 Chisel 包装
  - AXI4 / AXIS 接线
  - 当前的调试计数和状态观测逻辑也在这里

### 10.3 DDR/MIG 关键层

- `fpga/fpga-shells/src/main/scala/devices/xilinx/xilinxnexysvideomig/XilinxNexysVideoMIG.scala`
  - Nexys Video MIG wrapper
  - 当前已经包含 MM2S 返回路由修复、alias 相关 source 宽度约束等关键逻辑

- `generators/chipyard/src/main/scala/System.scala`
  - 当前 `ExtTLMem` 的 alias 接入逻辑位于这里
  - 也是这次 `tl_mem source-width` 修正的关键文件

### 10.4 测试程序

- `tests/radar-axi-mmio-smoke.c`
  - 验证 DMA CSR 控制面是否正常

- `tests/radar-axi-dma-loopback.c`
  - 当前正式的 cache-maint 版本端到端 loopback 回归测试

- `tests/radar-axi-dma-loopback-cacheprobe.c`
  - 用于验证 cacheable 路径下不一致性的暴露方式

- `tests/radar-axi-dma-loopback-cachemaint.c`
  - 用于验证前后 cache maintenance 后，系统可完整通过

- `tests/radar-axi-dma-uncached-alias.c`
  - 用于验证 uncached alias 路径下，loopback 无需 cache maintenance 即可通过

- `tests/radar-axi-dma-consistency.c`
  - 当前多长度 consistency 回归

- `tests/radar-axi-dma-regression.c`
  - 当前推荐的单 ELF 综合回归入口
  - 已覆盖 MMIO、cache probe、uncached alias、multi-length consistency

- `tests/radar_axi_dma_common.h`
  - 当前 DMA bring-up 测试共享的基础头文件
  - 统一定义 MMIO、reset、wait、loopback、cache sweep 等通用逻辑

### 10.5 当前文档

- `docs/radar_nexysvideo_system_arch.html`
  - 当前系统的 UTF-8 中文可视化架构说明页

- `docs/radar_nexysvideo_current_system_guide_2026-03-31.md`
  - 当前这份详细中文整理文档

- `docs/radar_nexysvideo_reproduction_guide_2026-03-31.md`
  - 当前版本复刻与子模块使用说明

---

## 11. 当前软件测试体系说明

### 11.1 `hello.riscv`

作用：

- 验证 CPU、UART、最基本运行环境是否健康

### 11.2 `radar-axi-mmio-smoke.riscv`

作用：

- 验证 DMA 的 MMIO CSR 通路
- 重点确认 reset/config/readback 是否健康

### 11.3 `radar-axi-dma-loopback.riscv`

作用：

- 当前正式的 cache-maint 版本端到端 loopback 回归测试

当前状态：

- 已通过
- 依赖 cache maintenance

### 11.4 `radar-axi-dma-loopback-cacheprobe.riscv`

作用：

- 用于区分“单纯 compare 时 cache stale”与“DMA 源/目的 buffer 都需要维护”的问题

### 11.5 `radar-axi-dma-loopback-cachemaint.riscv`

作用：

- 证明在加入前后 cache sweep 后，系统是完整工作的

### 11.6 `radar-axi-dma-uncached-alias.riscv`

作用：

- 证明 CPU 通过 uncached DDR alias 访问 buffer 时，DMA loopback 无需 cache maintenance 也能通过

### 11.7 `radar-axi-dma-consistency.riscv`

作用：

- 覆盖多种长度下的 DMA loopback 一致性

### 11.8 `radar-axi-dma-regression.riscv`

作用：

- 当前推荐的单 ELF 综合回归
- 一次下载、一次运行，同时覆盖：
  - MMIO smoke
  - cache probe
  - uncached alias
  - 多长度 consistency

当前状态：

- 已在当前 bitstream 上完整通过

---

## 12. 当前系统的运行约束

### 12.1 约束一：cacheable DDR 路径下要做 cache maintenance

如果以后继续采用：

- CPU 在 cacheable DDR 中准备 buffer
- DMA 直接从该 buffer 读写

那么必须考虑：

- DMA 启动前，CPU 写入过的 TX buffer 是否已经对 DDR 可见
- DMA 完成后，CPU 再读 RX buffer 时是否已经丢掉旧的 cache line

### 12.2 约束二：如果改用 uncached alias，则可绕开这条约束

当前已经验证通过的另一条协议是：

- DMA 继续使用 `0x8000_0000` 这片 DDR 的原始地址
- CPU 改为通过 `0x1080_000000` 起的 uncached alias 访问同一物理 buffer

在这条路径下，当前测试已经证明：

- TX 填充可被 DMA 正确读到
- RX 写回可被 CPU 直接看到
- 无需额外 cache maintenance

### 12.3 约束三：不要把 UART-TSI 当成系统数据通路的一部分

UART-TSI 负责：

- 下载程序
- 自检
- 少量 debug `init_read/init_write`

它不是目标系统运行时的数据路径，不应与 DMA 数据路径混淆。

### 12.4 约束四：当前通过的是 simple mode + 单段搬运基础能力

当前最稳定的“已通过定义”是：

- 单段源地址
- 单段目的地址
- 固定长度
- 内部 stream loopback

如果后续扩展到更复杂的 scatter-gather、长时间流式输入、外部 stream producer/consumer，还需要继续增加覆盖测试。

---

## 13. 当前系统适合做什么

### 13.1 作为 DMA/DDR 数据搬运基座

你现在已经拥有一个真实可工作的最小平台，可用于：

- 内存到内存搬运验证
- AXIS 前后级模块验证
- 更复杂 DMA 工作流的基础测试

### 13.2 作为雷达数据通路原型平台

如果后面你要把当前 loopback 替换成真正的雷达数据通道，那么当前结构已经很合适：

- MM2S 从 DDR 取输入
- 中间插入你的 stream 处理链
- S2MM 把结果写回 DDR
- CPU 读取结果并做后处理/校验

### 13.3 作为后续系统化优化的起点

下一阶段如果想让系统更“产品化”，可以考虑：

- 将 uncached alias 路径进一步标准化成固定 DMA buffer 使用规范
- 更明确的 DMA buffer 管理策略
- 真正的 cache coherence 方案
- 更丰富的 DMA test suite
- 自动化 bitstream + regression 流程

---

## 14. 建议的下一阶段工作

### 14.1 第一优先级：把 buffer 使用协议标准化

建议把当前两条已跑通的 buffer 使用协议都写成明确规范，例如：

- 哪些地址区可以作为 DMA buffer
- cacheable 路径下，DMA 启动前后分别要做什么
- uncached alias 路径下，CPU 应该访问哪片地址
- 哪些 API 负责 sweep / flush / invalidate

### 14.2 第二优先级：把 loopback 升级成可插拔 stream 链

当前 MM2S 与 S2MM 之间是直接回环。下一步可引入：

- 数据过滤
- 格式整理
- FFT / 雷达相关预处理模块
- 自定义 AXI-Stream 算法块

### 14.3 第三优先级：补自动化回归和文档化接口

建议至少固化以下自动化检查：

- `hello`
- `radar-axi-mmio-smoke`
- `radar-axi-dma-regression`

这样以后每次改 DMA、MIG wrapper、harness binder、alias 接法或软件测试，都可以快速回归。

---

## 15. 总结

当前这个项目已经完成了从“板子能起来”到“CPU 能驱动 DMA 经由 DDR 完整搬运数据”的跃迁。

它现在不是一个只在结构图上成立的系统，而是一个已经在实际 Nexys Video 板子上证明：

- CPU 可用
- DDR 可用
- MMIO 可用
- DMA 可用
- AXI interconnect 可用
- MM2S/S2MM 可用
- 端到端 loopback 可用
- uncached alias 可用
- 单 ELF 综合回归可用

的系统原型。

因此，当前项目最准确的定位是：

> 一个已经完成主链路打通、并且同时具备 cache-maint 路径与 uncached-alias 路径的 Nexys Video 原型平台。

当前最需要牢记的现实条件有两条：

> Rocket cache 与 DMA 之间还没有自动一致性；共享 cacheable buffer 时，软件要负责 cache maintenance。  
> 如果希望绕开这条约束，当前已经验证可用的做法是：让 CPU 通过 DDR 的 uncached alias 去访问 DMA buffer。

只要遵守这两类系统协议之一，当前平台已经能够稳定支撑后续开发。
