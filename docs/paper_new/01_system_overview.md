# 系统总体架构

## 一句话概括

当前系统是在 Nexys Video FPGA 上运行的 Rocket-based Chipyard SoC，CPU 负责控制、装载、配置和校验；DDR 是共享工作区；AXI DMA 把 DDR 数据转成 AXI4-Stream；Feature21/QMLP 是流式硬件算子；Xradar RoCC 是另一条 RISC-V 自定义指令实验路径，用于验证小粒度 QMLP 算术是否值得进入 core/ISA 协同优化。

## 主要模块

| 模块 | 作用 | 当前状态 |
| --- | --- | --- |
| Rocket core | bare-metal 程序执行、MMIO 配置、DMA 启停、结果校验、RoCC 指令发射 | 可用；75 MHz 最终 timing limiter 主要回到 frontend/core routing |
| UART-TSI | host 到板上内存的程序装载和读写调试 | 可用；推荐 `/dev/ttyUSB0`、`115200`、fresh ELF 前 CPU_RESET |
| DDR/MIG | 共享主存，存 ELF、输入、输出、DMA buffer | 可用；CPU/DMA 非自动 coherent |
| AXI DMA | DDR 与 AXI4-Stream 之间的数据搬运 | 可用；长度寄存器历史限制影响最大 batch |
| AXI4-Lite/MMIO bridge | CPU 通过 MMIO 配置 DMA、preproc、QMLP control/status | 可用；本项目控制面核心 |
| Feature21 | raw/fused 点集到 21 维 int8 feature 的预处理 | 板级 compact dump 已对拍 exact-LUT mirror |
| QMLP | `21 -> 64 -> 32 -> 2` INT8 推理，输出 int32 logits | 板级 validation 通过 |
| Xradar RoCC | RISC-V custom0 的 `rqdot4` 原型 | timing-clean bitstream 已板测 PASS；仅 `rqdot4` |

## 两条硬件路径

### MMIO + DMA + AXI4-Stream 加速器路径

```text
Rocket 软件
  -> MMIO 配置 DMA / Feature21 / QMLP
  -> DDR 输入 buffer
  -> AXI DMA MM2S
  -> AXI4-Stream Feature21 或 QMLP
  -> AXI DMA S2MM
  -> DDR 输出 buffer
  -> Rocket 读取并校验
```

这是当前 Feature21/QMLP 硬件基线，也是论文中最稳的系统级贡献路径。

### RISC-V custom instruction / RoCC 路径

```text
Rocket 执行 .insn r CUSTOM_0, 7, 0
  -> RoCC command
  -> XradarRoCC 捕获 rs1/rs2/rd
  -> 4 lane signed int8 multiply
  -> sum/sign-extend
  -> RoCC response 写回 rd
```

这是当前 Xradar/core co-design 原型路径。它不经过 DDR/DMA，适合验证 CPU fallback 中密集小算子是否能靠自定义指令提速。

## 当前论文叙事建议

- 主线一：构建一个可运行的 RISC-V SoC 雷达边缘推理平台，打通 DDR/DMA/AXI4-Stream/Feature21/QMLP。
- 主线二：面向 `21 -> 64 -> 32 -> 2` INT8 QMLP 的计算形态，提出轻量 custom instruction/RoCC 原型，证明 `rqdot4` 对小批量 kernel 有实际板级收益。
- 主线三：通过 75 MHz timing closure 说明该系统不是只在仿真中成立，而是经过 FPGA 后端和板级验证的工程实现。

## 证据

- 总文档地图：[../README.md](../README.md)
- RTL 综述：[../radar_rtl_implementation_logic_review_2026-06-08.md](../radar_rtl_implementation_logic_review_2026-06-08.md)
- 75 MHz closure：[../feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md](../feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md)
- RoCC 状态：[../../logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-board-status-2026-06-09.md](../../logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-board-status-2026-06-09.md)
