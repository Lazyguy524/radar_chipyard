# Feature21 硬件前处理 v1.3 状态记录

日期：2026-04-22

## 当前结论

本轮已经完成 21 维雷达特征前处理硬件的第一版可实现链路：

```text
DMA MM2S -> Feature21Preprocessor -> QMLP(21->64->32->2) -> DMA S2MM
```

bitstream 已生成并通过 Vivado timing：

- bitstream：
  - `/home/soooarr/chipyard/fpga/deliverables/radar_nexysvideo_bits/646-feature21-v1p3-preproc-qmlp-2026-04-22.bit`
- 备份：
  - `/home/soooarr/chipyard/logs/radar_nexysvideo/bit_backups/646-feature21-v1p3-preproc-qmlp-2026-04-22.bit`
- SHA256：
  - `260e5353ed241dccf5eac2d53416c9b31bf43ae826557597aa64f77ad3725a56`

测试 ELF：

- `/home/soooarr/chipyard/tests/radar-axi-dma-feature21.riscv`

## 重要说明

当前 v1.3 是“可综合、可上板”的定点近似前处理版本，不是软件侧浮点 feature21 的逐 bit 等价实现。

主要原因：

- 软件 feature21 包含 `sqrt / atan / eigen / std / density` 等复杂浮点或非线性计算。
- 当前硬件第一版优先建立 SoC 数据链路和前处理加速闭环。
- 因此部分特征采用低成本定点近似，例如：
  - range 使用 `max(abs(x), abs(y)) + min(abs(x), abs(y))/2`
  - std 使用 `span / 4`
  - eig major/minor 使用 `std_x/std_y` 的大小近似
  - mean 使用 count 的 shift-bucket 近似除法

后续如果论文需要和软件 feature21 完全一致，需要再做精确定点化规格和 golden 重生成。

## 输入输出协议

输入到 Feature21Preprocessor 的 AXI-Stream 格式：

```text
beat0/header:
  data[15:0] = point_count

beat1..beatN:
  data[15:0]   = x       signed Q8.8
  data[31:16]  = y       signed Q8.8
  data[47:32]  = doppler signed Q8.8
  data[63:48]  = rcs     signed Q8.8
```

输出格式：

```text
4 beats x 64-bit = 32 bytes
byte[0..20]      = feature21 int8
byte[21..31]     = zero padding
```

该输出可以直接送入当前 QMLP，因为 QMLP 本来就按 4 个 64-bit beat 接收 21 维 int8 输入。

## 实现变化

修改文件：

- `/home/soooarr/chipyard/fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
- `/home/soooarr/chipyard/tests/radar_axi_dma_common.h`
- `/home/soooarr/chipyard/tests/Makefile`
- `/home/soooarr/chipyard/tests/radar-axi-dma-feature21.c`

新增模式：

```c
PREPROC_MODE_FEATURE21_Q8_8 = 5
```

v1.3 相比前两版的关键修正：

- v1.1/v1.2 的特征选择 + 量化路径太长。
- v1.3 将 `FeatureSelect` 和 `FeatureQuant` 拆成两拍。
- 最终 WNS 从中间负余量收敛为正余量。

## Timing 和资源

最终 timing：

```text
WNS = 0.130 ns
TNS = 0.000 ns
WHS = 0.052 ns
All user specified timing constraints are met.
```

整体资源：

```text
NexysVideoHarness:
  LUT  = 30714
  FF   = 18421
  BRAM = 14
  DSP  = 10
```

关键模块资源：

```text
RadarAXISFeature21Preprocessor:
  LUT = 2021
  FF  = 978
  DSP = 0
  BRAM = 0

RadarAXISQMLP:
  LUT = 3130
  FF  = 1491
  DSP = 0
  BRAM = 0
```

## 日志索引

- Verilog：
  - `/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/644-feature21-v1p3-verilog-2026-04-22.log`
- Bitstream：
  - `/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/645-feature21-v1p3-bitstream-2026-04-22.log`
- SHA256：
  - `/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/647-feature21-v1p3-bit-sha256-2026-04-22.txt`
- Test ELF build：
  - `/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/648-build-feature21-test-2026-04-22.log`

## 下一步上板测试

请烧录：

```text
/home/soooarr/chipyard/fpga/deliverables/radar_nexysvideo_bits/646-feature21-v1p3-preproc-qmlp-2026-04-22.bit
```

然后用 UART 115200、CPU_RESET 后运行：

```text
/home/soooarr/chipyard/tests/radar-axi-dma-feature21.riscv
```

预期测试内容：

- feature21 preproc-only：检查 21 个 int8 feature byte 和 padding。
- feature21 -> QMLP chain：检查 DMA/preproc/QMLP 计数器、输出 logits、整体链路是否完成。

通过该测试后，才能把“21 维前处理 + QMLP”称为板级闭环验证通过。

## 2026-04-23 上板测试结果

测试环境：

- bitstream：
  - `/home/soooarr/chipyard/fpga/deliverables/radar_nexysvideo_bits/646-feature21-v1p3-preproc-qmlp-2026-04-22.bit`
- ELF：
  - `/home/soooarr/chipyard/tests/radar-axi-dma-feature21.riscv`
- UART：
  - `/dev/ttyUSB0`
  - `115200 baud`

结果：

```text
AXI DMA feature21 PASSED
```

关键计数：

```text
feature21 preproc-only:
  input beats  = 5
  output beats = 4
  frames       = 1
  result       = preproc compare passed

feature21 -> QMLP chain:
  preproc input beats  = 5
  preproc output beats = 4
  QMLP input beats     = 4
  QMLP output beats    = 1
  QMLP kernel cycles   = 1301
  logits               = {-4117, 3007}
```

计时说明：

- 本次 `preproc cycles` 和 `chain cycles` 约为 `8.99M cycles`，对应约 `179 ms`。
- 该数值仍包含测试程序里的 DMA reset/init 流程，不等价于纯硬件流式计算延迟。
- 当前测试主要证明“21 维定点前处理硬件 + QMLP 链路”能在板上正确完成一次样例处理。

日志：

- `/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/650-feature21-v1p3-board-test-2026-04-23-2026-04-23-185901.log`
