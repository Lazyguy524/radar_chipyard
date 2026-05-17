# FullChain RISC-V/DDR/DMA/AXI Integration Notes

工作目录：`/home/soooarr/chipyard_copy`

## 当前目标

在不复用 Feature21/QMLP 数据通路的前提下，新增一条独立 FullChain 数据链路：

```text
RISC-V CPU
  -> AXI4 MMIO
  -> FullChain control window
     - 0x000..0x0ff: Xilinx AXI DMA CSR
     - 0x200..0x23f: full_chain_axi_accel CSR

DDR -> AXI DMA MM2S -> full_chain_axi_accel -> AXI DMA S2MM -> DDR
```

## 新增配置

新增 Nexys Video 配置：

```text
chipyard.fpga.nexysvideo.FullChainAXIMMIONexysVideoConfig
```

该配置启用 `EnableNexysVideoFullChain`，NexysVideo harness 会实例化：

```text
FullChainAXIDMA
```

原来的 `RadarAXIDMA` 不会在该配置下实例化，避免 Feature21/QMLP 路径和 FullChain 路径混在一起。

## MMIO 地址

Base：

```text
0x6000_0000
```

DMA CSR：

| Offset | Register |
|---:|---|
| `0x000` | MM2S_DMACR |
| `0x004` | MM2S_DMASR |
| `0x018` | MM2S_SA |
| `0x01c` | MM2S_SA_MSB |
| `0x028` | MM2S_LENGTH |
| `0x030` | S2MM_DMACR |
| `0x034` | S2MM_DMASR |
| `0x048` | S2MM_DA |
| `0x04c` | S2MM_DA_MSB |
| `0x058` | S2MM_LENGTH |

FullChain CSR：

| Offset | Register |
|---:|---|
| `0x200` | CTRL |
| `0x204` | RANGE_CFG |
| `0x208` | DOPPLER_CFG |
| `0x20c` | CFAR_CFG |
| `0x210` | STATUS |
| `0x214` | IN_WORDS |
| `0x218` | MID_WORDS |
| `0x21c` | OUT_WORDS |
| `0x220` | DET_WORDS |
| `0x224` | STALL_IN |
| `0x228` | STALL_MID |
| `0x22c` | STALL_OUT |
| `0x230` | EXPECTED_IN |
| `0x234` | EXPECTED_OUT |
| `0x238` | CFAR_DIMS |
| `0x23c` | VERSION |

## AXI-Stream 宽度

师兄 FullChain IP 当前接口为：

| Direction | Width | Meaning |
|---|---:|---|
| DMA MM2S -> FullChain | `32 bit` | input word: `[31:16] real`, `[15:0] imag` |
| FullChain -> width adapter | `128 bit` | detection/output beat |
| width adapter -> DMA S2MM | `64 bit` | each 128-bit FullChain beat is split into two 64-bit DMA stream beats |

Vivado AXI DMA 对 S2MM stream/data width 有约束：如果 S2MM stream 是 `128 bit`，memory-mapped S2MM width 不能配置成 `64 bit`。因此当前链路保留 FullChain IP 的 `128 bit` 输出接口，在 DMA 前增加一个 128->64 AXI-Stream 适配器。

当前 DMA IP 配置为：

```text
MM2S memory width  = 64 bit
MM2S stream width  = 32 bit
S2MM stream width  = 64 bit
S2MM memory width  = 64 bit
```

换算关系：

```text
FullChain expected output = 4096 x 128-bit beats
DMA S2MM stream input     = 8192 x 64-bit beats
DDR output buffer length  = 4096 x 16 bytes = 65536 bytes
```

## 当前验证入口

新增最小 smoke test：

```text
tests/radar-fullchain-mmio-smoke.c
tests/radar_fullchain_common.h
```

该测试只做 MMIO bring-up，不送完整数据流：

1. reset MM2S/S2MM DMA channel
2. 读取 `VERSION`，期望 `0x20260509`
3. 写入 128 range x 64 doppler 默认配置
4. 检查 `EXPECTED_IN=8192`
5. 检查 `EXPECTED_OUT=4096`
6. 检查配置没有被标记为 illegal

## 已生成的本地 collateral

当前只生成了 Verilog/IP 检查 collateral，没有生成 bitstream：

```text
fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.FullChainAXIMMIONexysVideoConfig/
```

关键文件：

```text
gen-collateral/NexysVideoHarness.sv
gen-collateral/FullChainAXIDMA.sv
gen-collateral/FullChainAXIS128To64.sv
chipyard.fpga.nexysvideo.NexysVideoHarness.FullChainAXIMMIONexysVideoConfig.full_chain_axi_dma.vivado.tcl
```

最小 RISC-V smoke binary：

```text
tests/radar-fullchain-mmio-smoke.riscv
```

## 后续 TODO

- DONE: 借用 `/home/soooarr/chipyard/.conda-env/riscv-tools/bin` 后，已编译 `tests/radar-fullchain-mmio-smoke.riscv`
- DONE: `FullChainAXIMMIONexysVideoConfig` 已完成 Chisel elaboration，生成 `.fir` 和 chisel log
- DONE: 借用原 Chipyard 环境中的 `firtool` 后，已完成 split Verilog 生成
- DONE: Vivado IP 配置检查曾发现 `128-bit S2MM stream / 64-bit S2MM memory` 不是合法 AXI DMA 组合；已改为 FullChain 128-bit 输出后接 128->64 adapter，再进入 64-bit S2MM stream
- DONE: Vivado 已确认接受 32-bit MM2S stream / 64-bit S2MM stream / 64-bit memory 的 AXI DMA 配置
- DONE: 已确认本轮没有生成 `.bit` / `.mcs` / `.bin`
- TODO: 增加 DDR buffer 数据搬运测试
- TODO: 按师兄 README 的 8192 input words / 4096 output beats 做完整 FullChain 数据闭环
