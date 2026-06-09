# 协议与内存通路

## 为什么需要多种协议

本项目不是单个 RTL IP，而是一个 SoC。不同模块的访问形态不同，因此使用不同协议：

| 协议/通路 | 角色 | 为什么需要 |
| --- | --- | --- |
| TileLink | Rocket/Chipyard 内部 SoC 总线 | Rocket-chip 原生互连和外设接入机制 |
| AXI4 MMIO | CPU 访问外设控制窗口 | 与 FPGA shell、DMA wrapper 和 Xilinx 风格 IP 边界对接 |
| AXI4-Lite | DMA/control register 访问 | 控制寄存器低带宽、单次读写，适合 lite 化 |
| AXI4 memory-mapped | DMA 直接访问 DDR | 大块数据搬运，MM2S/S2MM 作为 AXI master |
| AXI4-Stream | DMA 与算子之间的数据流 | 无地址、ready/valid、适合 Feature21/QMLP 逐帧处理 |
| UART-TSI | host 装载 ELF 和调试读写 | 开发阶段程序下载、selfcheck、内存探针 |
| RoCC | Rocket 到协处理器指令接口 | 低延迟 custom instruction/自定义算术实验 |

## MMIO 控制面

CPU 通过 `DMA_BASE_ADDR = 0x60000000` 的 MMIO window 配置 DMA、preproc 和 QMLP。关键寄存器偏移：

| 区域 | 偏移 |
| --- | --- |
| MM2S DMA | `0x00` 到 `0x28` |
| S2MM DMA | `0x30` 到 `0x58` |
| Preproc/Feature21 CSR | `0x200` 到 `0x224` |
| QMLP CSR | `0x240` 到 `0x26c` |

证据：[../../tests/radar_axi_dma_common.h](../../tests/radar_axi_dma_common.h)

## DDR buffer 约定

当前 DDR buffer 区域：

| 区域 | DMA 地址 | 用途 |
| --- | --- | --- |
| `RADAR_BUF_IN_BASE` | `0x81000000` | 输入 buffer |
| `RADAR_BUF_MID0_BASE` | `0x81800000` | 中间 buffer |
| `RADAR_BUF_MID1_BASE` | `0x82000000` | 中间 buffer |
| `RADAR_BUF_OUT_BASE` | `0x82800000` | 输出 buffer |
| `RADAR_BUF_DESC_BASE` | `0x83000000` | 描述/辅助区 |

CPU 可以通过 cached 视图或 uncached alias 访问。当前 uncached alias offset 为 `0x1000000000`。DMA 使用原始 DDR 地址，CPU 若使用 uncached alias 访问同一物理 DDR，可避免 Rocket D-cache 与 DMA 非一致性问题。

## AXI4-Stream 数据面

DMA 的 MM2S 将 DDR buffer 中的字节流读出，转成 AXI4-Stream：

```text
tdata: 64 bit
tkeep: byte valid mask
tvalid/tready: ready-valid 握手
tlast: frame end
```

Feature21/QMLP 都是 Chisel `Decoupled` 风格 AXIS block。上游只有在 `valid && ready` 时推进数据；下游 backpressure 会通过 `ready` 反压。

## 链接方式

典型 QMLP direct path：

```text
DDR input -> DMA MM2S -> QMLP -> DMA S2MM -> DDR output
```

Feature21-only dump：

```text
DDR raw/fused point frame -> DMA MM2S -> Feature21 -> DMA S2MM -> DDR feature output
```

Feature21-to-QMLP chain 在 RTL 中有 `QMLP_CTRL_CHAIN_PREPROC` 和 `feature21Selected` 路由，但写论文时必须以实际 board validation 证据为准，避免把 mixed evidence 写成 full-chain pass。

## 调试规则

- fresh ELF 前按 `CPU_RESET`。
- UART-TSI 使用 `/dev/ttyUSB0` 和 `115200`。
- memory-smoke 这类程序如果故意 spin，timeout 不是失败；要读 DDR status words 判断。
