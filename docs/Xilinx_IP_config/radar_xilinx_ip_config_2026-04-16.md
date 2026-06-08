# Radar NexysVideo Xilinx IP 配置记录

日期：2026-04-16  
对象配置：`RadarAXIMMIONexysVideoConfig`  
生成目录：`fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig`

本文记录当前 bitstream 对应的主要 Xilinx IP 配置。后续修改 Vivado IP 参数、重新跑 bitstream 或对比其他平台时，应优先同步本文。

## 1. IP 清单

| IP 实例 | Xilinx IP | 工程作用 | 主要来源 |
|---|---|---|---|
| `radar_axi_dma` | `axi_dma` | DDR 与 AXI-Stream 加速器之间搬运数据 | `*.radar_axi_dma.vivado.tcl`, `obj/ip/radar_axi_dma/radar_axi_dma.xci` |
| `nexysvideomig` | `mig_7series` | Nexys Video DDR3 控制器 | `*.nexysvideomig.vivado.tcl`, `obj/ip/nexysvideomig/nexysvideomig.xci` |
| `harnessSysPLLNode` | `clk_wiz` | SoC harness 主时钟生成 | `*.harnessSysPLLNode.vivado.tcl`, `obj/ip/harnessSysPLLNode/harnessSysPLLNode.xci` |
| `mmcm` | `clk_wiz` | Nexys Video shell 辅助时钟 | `obj/ip/mmcm/mmcm.xci` |
| `reset_sys` | `proc_sys_reset` | shell 复位同步 | `obj/ip/reset_sys/reset_sys.xci` |
| `ila` | `ila` | Vivado debug/探针逻辑 | `obj/ip/ila/ila.xci` |

## 2. AXI DMA：`radar_axi_dma`

当前 DMA 是 Direct Register/simple mode，不启用 Scatter-Gather。

| 配置项 | 当前值 | 说明 |
|---|---:|---|
| Scatter Gather Engine | `0` | 关闭 |
| Micro DMA | `0` | 关闭 |
| Address Width | `32` bit | MM2S/S2MM 地址宽度 |
| Width of Buffer Length Register | `14` bit | Vivado 内部名 `c_sg_length_width` |
| 单次最大 LENGTH | `16383` B | `2^14 - 1` |
| MM2S Memory Map Data Width | `64` bit | DDR 读侧 AXI 宽度 |
| MM2S Stream Data Width | `64` bit | 输出到加速器 AXI-Stream 宽度 |
| S2MM Memory Map Data Width | `64` bit | DDR 写侧 AXI 宽度 |
| S2MM Stream Data Width | `64` bit | 加速器输出 AXI-Stream 宽度 |
| MM2S Max Burst Size | `8` | 当前 IP 配置 |
| S2MM Max Burst Size | `8` | 当前 IP 配置 |
| MM2S DRE | `0` | 不支持非对齐传输 |
| S2MM DRE | `0` | 不支持非对齐传输 |
| MM2S Store-and-Forward | `1` | 开启 |
| S2MM Store-and-Forward | `1` | 开启 |

对当前 QMLP 的影响：

| QMLP batch | 输入长度 | 输出长度 | 当前 14-bit LENGTH 是否可用 |
|---:|---:|---:|---|
| `1` | `32` B | `8` B | 可以 |
| `8` | `256` B | `64` B | 可以 |
| `64` | `2048` B | `512` B | 可以 |
| `256` | `8192` B | `2048` B | 可以 |
| `511` | `16352` B | `4088` B | 可以 |
| `1000` | `32000` B | `8000` B | 不可以，输入超过 `16383` B |

如果要一次 DMA 搬运 `256 * 128 * 32bit = 131072` B，当前 14-bit LENGTH 不够。该长度至少需要 `18` bit，因为 `2^17 - 1 = 131071` B 仍差 1 B；为了保留余量，建议后续改到 `25` 或 `26` bit。

## 3. DDR3 MIG：`nexysvideomig`

| 配置项 | 当前值 |
|---|---:|
| Memory Device | `DDR3_SDRAM/Components/MT41K256M16XX-125` |
| Time Period | `2500` ps |
| PHY Ratio | `4:1` |
| DDR Data Width | `16` bit |
| Data Mask | `1` |
| ECC | `Disabled` |
| Ordering | `Normal` |
| Row Address Width | `15` |
| Bank Address Width | `3` |
| Memory Voltage | `1.5V` |
| User Port Interface | `AXI` |
| AXI Address Width | `29` |
| AXI Data Width | `64` bit |
| AXI ID Width | `4` |
| Narrow Burst | `0` |
| Arbitration | `RD_PRI_REG` |

说明：DDR3 MIG 是系统 DDR 的主入口，CPU、DMA 与 SoC 外设访问 DDR 时都经过该控制器。

## 4. Harness 时钟：`harnessSysPLLNode`

该 `clk_wiz` 从板载 `100 MHz` 输入生成 SoC 使用的多个时钟。

| 配置项 | 当前值 |
|---|---:|
| Input Frequency | `100.0 MHz` |
| Output Clock Count | `3` |
| `clk_out1` | `50.0 MHz` |
| `clk_out2` | `100.0 MHz` |
| `clk_out3` | `200.0 MHz` |
| MMCM `CLKFBOUT_MULT_F` | `10.000` |
| MMCM `DIVCLK_DIVIDE` | `1` |
| MMCM `CLKOUT0_DIVIDE_F` | `20.000` |
| MMCM `CLKOUT1_DIVIDE` | `10` |
| MMCM `CLKOUT2_DIVIDE` | `5` |

当前 QMLP kernel cycles 按 `50 MHz` 主域换算：`1301 cycles ~= 26.02 us`。

## 5. Shell 辅助时钟：`mmcm`

该 `clk_wiz` 属于 Nexys Video shell 辅助时钟，不是当前 QMLP kernel 计时主域。

| 配置项 | 当前值 |
|---|---:|
| Input Frequency | `100.000 MHz` |
| Output Clock Count | `3` |
| `clk_out1` requested | `8.388 MHz` |
| `clk_out2` requested | `65.000 MHz` |
| `clk_out3` requested | `32.500 MHz` |
| Generated `clk_out1` | `8.39220 MHz` |
| Generated `clk_out2` | `64.97396 MHz` |
| Generated `clk_out3` | `32.48698 MHz` |
| MMCM `CLKFBOUT_MULT_F` | `62.375` |
| MMCM `DIVCLK_DIVIDE` | `6` |
| MMCM `CLKOUT0_DIVIDE_F` | `123.875` |
| MMCM `CLKOUT1_DIVIDE` | `16` |
| MMCM `CLKOUT2_DIVIDE` | `32` |

## 6. Reset IP：`reset_sys`

| 配置项 | 当前值 |
|---|---:|
| Peripheral active-low reset outputs | `1` |
| Interconnect active-low reset outputs | `1` |
| Peripheral active-high reset outputs | `1` |
| Bus active-high reset outputs | `1` |
| Aux reset polarity | active-low (`0`) |
| External reset polarity | active-low (`0`) |

## 7. ILA：`ila`

| 配置项 | 当前值 |
|---|---:|
| Probe count | `1` |
| Probe0 width | `4` bit |
| Data depth | `1024` |
| Input pipeline stages | `0` |
| Advanced trigger | `false` |
| Storage qualifier | `0` |
| TRIGIN/TRIGOUT | disabled |

说明：ILA 属于调试 IP，不参与 QMLP 正常数据通路。

## 8. 当前测试与后续建议

当前 bitstream 可用于 QMLP correctness 与小/中 batch DMA profile 测试，但单次 DMA 长度受 `14-bit LENGTH` 限制，profile 应避免 `1000` 样本作为单次事务。

建议：

- 当前板测 profile 使用 batch：`1 / 8 / 32 / 64 / 256 / 511`。
- 若要做大块 DDR/DMA 对比，例如 `128 KiB` 级别，应把 DMA `Width of Buffer Length Register` 提升到至少 `18` bit，建议 `25` bit。
- 因 DRE 关闭，DMA buffer 地址和长度继续保持 64-bit 对齐；当前 QMLP 输入 `32 B/sample`、输出 `8 B/sample` 满足该要求。

