# Radar NexysVideo RTL 编码规范与 NN 加速器实现建议

## 1. 文档目的

本文档用于统一当前 `Nexys Video + Chipyard + Rocket + DDR + AXI DMA + AXI-Stream Preprocessor` 工程的 RTL 编码风格，降低后续新增雷达前处理或 NN 加速模块时的维护成本、时序风险和综合风险。

本文档重点覆盖：

- Reset 风格约定
- Chisel 可综合写法约定
- AXI4 / AXI4-Lite / AXI4-Stream 接口约定
- 状态机、计数器、FIFO、寄存缓冲写法
- 调试逻辑与正式数据通路的隔离
- 后续 NN 加速器是否适合直接用 Chisel 实现
- 为什么业界仍然广泛使用 Verilog / SystemVerilog / HLS / DSL 等其他方法

## 2. 适用范围

适用于以下模块：

- `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
- 后续新增的 `AXI4-Stream` 雷达预处理模块
- 后续新增的 `NN accelerator` / `matrix / conv / activation / layout transform` 模块
- 与上述模块直接相连的 CSR、DMA、buffer 管理、计数器与调试模块

不直接约束第三方 IP 黑盒，但要求黑盒接口封装层遵守本文档的命名和连接原则。

## 3. 总体设计原则

### 3.1 控制面和数据面分离

必须明确区分两类路径：

- 控制面：
  - CPU 通过 MMIO / CSR 配置模块
  - 低带宽、强可观测、强调可读性
- 数据面：
  - DMA / AXI4 / AXI-Stream 传输真实 payload
  - 高带宽、强调时序边界、吞吐和 backpressure 正确性

禁止把“配置动作”和“逐拍数据计算”混写在同一段复杂逻辑中。

### 3.2 默认先保证可综合、再追求抽象优雅

Chisel 允许很多表达式级写法，但本项目中必须优先考虑：

- 生成后的 RTL 是否清晰
- 是否容易定位时序路径
- 是否容易验证握手边界
- 是否会被误解为行为级不可综合代码

如果某种 Chisel 写法虽然简洁，但生成 RTL 后过于晦涩，应优先改写为更直白的结构。

### 3.3 默认先做“小而清晰的模块”

后续新增模块优先拆成：

- CSR 配置层
- 数据搬运层
- 算子层
- 统计 / 调试层

避免把 AXI 接口、数据变换、状态统计、异常处理全堆到一个超大模块里。

## 4. Reset 规范

## 4.1 外部接口命名统一为低有效

对外暴露的 reset 信号统一命名为：

- `resetn`
- `rst_n`
- `ctrlResetN`
- `axi_resetn`

即：

- 低电平有效
- 名称中显式体现低有效语义

禁止外部接口出现语义模糊的 `reset`，除非该模块是纯内部局部模块且约定已经非常明确。

## 4.2 自定义模块内部推荐同步 reset

对于自定义数据通路模块，推荐优先使用：

- 同步 reset
- 仅 reset 必需状态

适合被 reset 的对象：

- valid 标志
- 状态机 state
- 计数器
- 配置寄存器

不必强制 reset 的对象：

- 在 `valid=0` 时无意义的数据寄存器
- 纯组合导出的中间信号

理由：

- 可减少 reset 扇出
- 更利于时序
- 更贴近高质量流处理 RTL 的常见风格

## 4.3 与 Xilinx IP 对接时允许单独适配

如 DMA / MIG 等 Xilinx IP 要求特定 reset 形式：

- 黑盒接口按 IP 官方要求接
- 在自定义封装层中完成极性转换

推荐模式：

- 系统外部统一低有效 `*_resetn`
- IP 封装层内部单独做 `!resetn`
- 不要让 reset 极性在工程里到处漂移

## 4.4 允许现有工程短期保留的风格

当前工程里 `RadarAXISPreprocessor` 是通过：

- `withClockAndReset(ctrlClock, (!ctrlResetN).asAsyncReset)`

生成出高有效内部 `reset` 端口的。

这在功能上成立，也可综合；但后续新增模块建议尽量统一成：

- 顶层低有效
- 内部清晰可追踪
- 对于纯自定义算子尽量不滥用异步 reset

## 5. Chisel 可综合写法规范

## 5.1 允许的“循环类”写法

以下写法允许使用：

- `Seq.tabulate`
- `.map`
- `VecInit`
- `Cat(...)`
- 固定边界的小范围 lane 展开

前提是：

- 循环边界必须是编译期常量
- 生成的是固定结构硬件
- 不依赖运行时动态长度

示例：

- 4 lane `16-bit` 变换
- 2 lane `32-bit` 加法
- 固定宽度字节写 strobe 合成

## 5.2 禁止行为级动态循环语义

禁止写出会让读者误以为是“软件循环执行”的结构，例如：

- 运行时可变次数 `for`
- 数据相关迭代直到收敛
- 隐含大规模优先级链的过度嵌套 `Mux`

若必须做多级归约或复杂选择器，建议：

- 显式拆成局部信号
- 分层命名
- 必要时手工展开关键路径

## 5.3 组合逻辑和时序逻辑必须清楚分离

推荐结构：

- 组合：
  - `WireDefault`
  - 函数式变换
  - lane 计算
- 时序：
  - `RegInit`
  - `when (fire)`
  - 状态更新

禁止把组合和寄存器更新混成不可读的大段逻辑。

## 5.4 不允许隐式锁存器风格

所有组合输出必须有默认值。

例如：

- `WireDefault(0.U)`
- `io.xxx := default`

避免因为分支不全导致隐含状态或难以读懂的综合结果。

## 5.5 复杂算子必须拆局部中间量

对于后续的卷积、矩阵乘、激活、归一化、重排逻辑：

- 不允许把完整算式全部写进一个大 `MuxLookup`
- 应先拆分：
  - lane 提取
  - 符号扩展
  - 乘法结果
  - 累加结果
  - 饱和 / 截断结果
  - 输出重组

原因：

- 便于查看生成 RTL
- 便于插流水线
- 便于后续做时序优化

## 6. AXI4 / AXI4-Lite / AXI4-Stream 接口规范

## 6.1 AXI4-Lite / MMIO 只承载配置，不承载 payload

禁止通过 CSR 端口传大块输入数据。

MMIO 只用于：

- enable / mode / param
- 状态读回
- 错误标志
- 计数器

大数据必须走：

- AXI4 memory-mapped master
- 或 AXI4-Stream

## 6.2 AXI4-Stream 模块必须显式处理 backpressure

所有自定义流模块必须遵守：

- `valid` 由源端保持直到握手
- `ready` 由目的端反馈
- `fire = valid && ready`
- `last` 和 `keep` 必须跟随 beat 一起传递

禁止默认假设：

- 下游永远 ready
- 不会出现停顿
- 每帧都是满 beat

## 6.3 对 `tkeep` 和 `tlast` 的约束

后续所有流模块必须满足：

- 非最后一拍时，`tkeep` 应保持全有效或符合上游规范
- 最后一拍时，`tkeep` 必须准确描述有效字节
- `tlast` 不得凭空生成或提前拉高

如果模块不改变 beat 数，则：

- 输出 `tlast` 应与输入帧边界保持一致

## 6.4 可插入寄存缓冲，但必须写清边界

允许使用：

- 1-deep register slice
- skid buffer
- 明确深度的 FIFO

要求写清楚：

- 缓冲深度
- 是否保序
- 是否允许一拍吞吐
- 什么时候会 backpressure 上游

## 7. 状态机规范

## 7.1 状态机命名必须语义化

允许使用：

- `sIdle`
- `sCfg`
- `sIssue`
- `sWaitResp`
- `sDrain`

禁止：

- `s0/s1/s2`
- 没有语义的数字状态

## 7.2 一个状态机只解决一类问题

例如：

- AXI4-Lite 适配状态机
- DMA 启动/轮询状态机
- 帧边界打包状态机

不要让一个状态机同时负责：

- 配置
- 数据计算
- 统计输出
- 错误恢复

## 8. 计数器与调试逻辑规范

## 8.1 调试计数器必须与功能路径解耦

调试信号允许存在，但应尽量满足：

- 只旁路观察
- 不回注主数据通路
- 不影响功能时序边界

例如：

- `inBeats`
- `outBeats`
- `frameCount`
- `stallCycles`
- `busyCycles`

## 8.2 Debug LED / 观测点必须可删除

调试观测点应：

- 放在独立区域
- 通过配置或条件编译开关管理
- 不让正式架构长期依赖它们存在

## 9. FIFO / Buffer 规范

## 9.1 先写 1-deep，再扩真正 FIFO

对新算子，建议顺序：

1. 先实现 `1-deep register buffer`
2. 板测通过后，再考虑更深 FIFO
3. 需要时再做参数化深度

原因：

- 易验证
- 易定位 bug
- 时序压力较小

## 9.2 若引入 FIFO，必须写明语义

必须说明：

- 深度
- ready/valid 是否完全透传
- 是否 first-word fall-through
- 是否会引入额外延迟

## 10. 仿真辅助代码规范

## 10.1 允许存在 FIRRTL/CIRCT 生成的随机初始化宏

例如生成 RTL 中常见的：

- `RANDOMIZE_REG_INIT`
- `initial`
- 随机化 `for` 循环

这些属于：

- 仿真辅助
- 非主功能逻辑

不应把它们误认为硬件运行时循环。

## 10.2 手写 RTL 不推荐加入大量仿真花活

如果手写 Verilog / SV：

- 尽量不要在正式模块里堆大量 `ifndef SYNTHESIS` 逻辑
- 更推荐 testbench 或 wrapper 做辅助

## 11. 后续 NN 加速器是否都能用 Chisel 实现

## 11.1 结论

可以。

从工程能力上讲，后续绝大多数 NN 算子都能用 Chisel 实现，包括：

- elementwise add / mul / shift
- ReLU / clip / quantize / dequantize
- 1D / 2D convolution
- matrix multiply
- pooling
- layout transform
- reduction
- simple attention 子结构
- streaming pre/post process

如果你的目标是：

- 明确位宽
- 明确接口
- 明确时序
- 面向 FPGA 原型

那么 Chisel 完全够用。

## 11.2 哪类模块尤其适合 Chisel

特别适合用 Chisel 的包括：

- 规则化 AXI / AXIS 接口模块
- 参数可变的数据宽度/并行度模块
- 定点数据通路
- 流水线结构
- 可复用模板化运算阵列
- 与 Chipyard / Diplomacy 深度集成的模块

## 11.3 哪类场景写 Chisel 会比较痛

以下场景用纯 Chisel 也能做，但开发成本可能更高：

- 非常成熟且已有现成 IP 的 FFT / DSP / 高速 SerDes 类模块
- 算法迭代特别快、结构变化特别大的原型
- 以浮点矩阵运算为主且更像软件循环描述的问题
- 强依赖厂商特定 primitive / DSP block / BRAM packing 的极致优化实现

## 12. 既然 Chisel 能做，为什么很多人还用别的方法

这是工程权衡，不是 Chisel 不行。

## 12.1 原因一：现成 IP 生态

很多团队直接用：

- Xilinx / Intel 官方 IP
- FFT、DMA、FIFO、DDR controller、PCIe、Ethernet MAC

原因是：

- 成熟
- 验证充分
- 时序更容易收敛

所以不是他们不会用 Chisel，而是没必要重造轮子。

## 12.2 原因二：HLS 更适合某些算法原型

有些人用 HLS / C++ / OpenCL，是因为：

- 算法工程师更熟悉 C/C++
- 可以更快从软件参考过渡到硬件原型
- 对规则矩阵运算、循环嵌套类问题，上手快

代价是：

- 生成结果有时不可控
- 接口和微架构不如手写 RTL 清晰

## 12.3 原因三：Verilog / SystemVerilog 更贴近最终门级控制

很多经验丰富的 RTL 设计师喜欢直接写 SV，因为：

- 对综合结果的心智模型更直接
- 更方便精细控制 reset、时序、DSP/BRAM 映射
- 调试波形和综合报告时更顺手

尤其在高性能、高时序压力模块里，这一点很常见。

## 12.4 原因四：团队和工具链惯性

项目采用什么语言，很多时候不只是技术问题，还取决于：

- 团队已有代码资产
- 仿真 / lint / CDC / DFT / IP 流程
- 评审人员习惯
- 公司内部规范

所以很多团队继续用 SV/HLS，不代表 Chisel 不适合，只是整体流程不同。

## 13. 对你这个项目的建议

## 13.1 当前最推荐的实现路线

对你现在的工程，建议这样分工：

- 系统集成、AXI/AXIS 边界、参数化算子骨架：
  - 优先用 Chisel
- Xilinx 成熟 IP：
  - 继续黑盒化接入
- 后续 NN/雷达算子主体：
  - 若是规则流处理、定点流水线，优先用 Chisel
  - 若是成熟复杂 DSP 功能，可评估直接接现成 IP

## 13.2 不建议一开始就混太多方法

当前阶段不建议同时混：

- Chisel
- 手写 SV
- HLS
- 厂商图形化 IP

到一个小算子里。

建议先用单一方法把一类模块做顺，再视需要引入例外。

## 13.3 推荐你的后续分层

可以按下面方式推进：

- 控制 / MMIO / CSR / AXI 边界：Chisel
- 流处理骨架 / 小中型定点算子：Chisel
- 特殊高速缓存或厂商依赖强的模块：IP 或手写 SV
- 极其算法导向、需快速试错的块：必要时局部评估 HLS

## 14. 当前可执行规范结论

后续新增模块默认按以下规则执行：

1. 顶层 reset 统一低有效命名。
2. 自定义流处理模块优先同步 reset，仅 reset 必需状态。
3. AXI4-Lite 只做配置，payload 一律不走 CSR。
4. AXI4-Stream 必须正确处理 `valid/ready/last/keep`。
5. 组合逻辑与时序逻辑拆开写。
6. 复杂算子必须分 lane、中间量、结果重组逐层展开。
7. 调试逻辑与主功能路径解耦。
8. 先实现清晰可综合版本，再做更激进的时序/资源优化。

## 15. 后续建议

建议下一步执行两件事：

1. 把 `RadarAXISPreprocessor` 重构成更“规范模板化”的版本：
   - reset 风格统一
   - lane 计算拆局部信号
   - 更方便后续插 pipeline

2. 给未来的 NN 模块先定义统一壳层接口：
   - `AXI4-Stream in`
   - `AXI4-Stream out`
   - `Local CSR config`
   - `status / counters`

这样你后面无论是接雷达预处理、还是接 NN accelerator，模块风格都不会散。
