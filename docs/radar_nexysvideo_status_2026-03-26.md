# Radar Nexys Video Phase-1 Work Summary

## Update: 2026-03-28 Runtime Bring-up

Phase-1 integration is still valid, but current board bring-up moved the
problem statement forward:

- `UART-TSI` is working
- DDR direct read/write through `uart_tsi` is working
- `hello.riscv` is working
- `radar-axi-mmio-smoke.riscv` is working
- `radar-axi-dma-loopback.riscv` is still failing

The failure is no longer "DMA CSR window completely hangs forever". The control
path is now good enough to pass a dedicated DMA CSR smoke test.

The current blocker is specifically the MM2S start/run phase:

- MM2S and S2MM reset/programming reads look sane before MM2S starts
- S2MM channel setup looks sane
- corruption appears immediately after the `MM2S_LENGTH` write that arms MM2S
- transient MM2S register reads can show `0xa5a5....` payload-looking values
- afterward the MM2S control registers settle back, but the channel times out
- RX buffer remains zero, so no completed loopback writeback is observed

A newer debug bitstream was then generated to expose software-readable DMA
debug counters for MM2S/S2MM/stream handshakes. That bitstream is the current
next-stage debug image.

Initial board result for that debug image:

- `hello.riscv` still runs
- but direct `uart_tsi` init-read behavior became unreliable
- `0x60000200` did not return a sane debug counter value in first-pass testing

Therefore that debug image should be treated as experimental until the control
path side effects are corrected.

Latest stable-bit loopback observation:

- S2MM channel setup is clean from reset through `S2MM_LENGTH`
- MM2S channel setup is clean through `MM2S_SA_MSB`
- the first bad point is immediately after writing `MM2S_LENGTH`
- the very next MM2S register dump can transiently show `0xa5a5....` payload-like values
- after the transient, MM2S control registers settle back to the programmed values
- final steady state is `MM2S DMASR = 0x00000000`, no RX data written, and loopback times out

This strengthens the current hypothesis that the remaining failure is tied to
the MM2S launch/run path, not to basic CSR programming or DDR accessibility.

## 1. 目标与结论

本轮工作的目标是把 AXI DMA 从原来的“可能外露为 FPGA 顶层接口”的状态，改成在 Nexys Video 设计内部完成焊接，并最终产出可直接上板的 bitstream。

截至 2026-03-26，目标已经达成：

- `CPU -> DDR -> AXI DMA (MM2S) -> 硬件 loopback -> AXI DMA (S2MM) -> DDR` 的硬件集成链路已经接入当前 Nexys Video FPGA 构建。
- `RadarAXIMMIONexysVideoConfig` 已成功完成 `make verilog`、`make bitstream`。
- 产出了可用于 JTAG 下载的 `.bit` 文件和可用于 SPI flash 的 `.mcs` 文件。
- 实现阶段通过，后端时序满足要求。

## 2. 最终产物

- JTAG bitstream:
  `/home/soooarr/chipyard/fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/NexysVideoHarness.bit`
- SPI flash image:
  `/home/soooarr/chipyard/fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/system.mcs`
- 实现日志:
  `/home/soooarr/chipyard/fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/vivado.log`
- Chisel elaboration 日志:
  `/home/soooarr/chipyard/fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig.chisel.log`

## 3. 关键修改方法

### 3.1 AXI DMA 内焊到 FPGA harness

新增并接通了 AXI DMA 黑盒与控制/数据路径：

- 新增 DMA 包装:
  `fpga/src/main/scala/nexysvideo/RadarAXIDMA.scala`
- 新增 MMIO harness binder:
  `fpga/src/main/scala/nexysvideo/HarnessBinders.scala`
- 在 Nexys Video harness 内将 DMA 主口直接接到 MIG:
  `fpga/src/main/scala/nexysvideo/Harness.scala`

集成策略：

- `WithCustomMMIOPort(0x6000_0000, 0x10000, 64, 4, 8)` 让 SoC 长出一个 AXI4 MMIO 端口。
- `WithNexysVideoAXI4MMIO` 在 harness 内把这个端口直接连到 `RadarAXIDMA.ctrl`。
- DMA 的 `mm2sNode` / `s2mmNode` 直接并到 `ddrOverlay.get.mig.axiNode`。
- Stream 部分在 `RadarAXIDMA.scala` 内部直接 loopback。

### 3.2 不再导出 AXI MMIO 板级引脚

本轮的核心 bug 就是“不要把 AXI MMIO 变成板级 package pins”。

最终状态：

- Chisel 日志里保留了 `mmio-port-axi4@60000000` 这个总线地址空间。
- 但 IOBinders 生成的 IOCells 只有 `CustomBoot`、`ClockTap`、`SerialTL`，没有额外 AXI MMIO 板级引脚。

这说明 DMA 控制总线是存在的，但它被终结在 harness 内部，而不是露到 Nexys Video 板子的顶层引脚上。

### 3.3 构建链问题修复

除了 DMA 集成本身，还修掉了几处会阻塞 FPGA 构建的系统性问题：

- `build.sbt`
  给 `fpga_shells` 和 `chipyard_fpga` 两个子工程补上了 `chiselSettings`。
  作用是让新加的 FPGA Scala 文件在编译时带上 Chisel compiler plugin。

- `fpga/fpga-shells/src/main/scala/devices/xilinx/xilinxnexysvideomig/XilinxNexysVideoMIG.scala`
  修复了新版 `AXI4Xbar()` API 兼容性问题。

- `fpga/Makefile`
  修复了 `sim_files.f` 和 `*.vsrcs.f` 不断追加、导致 Vivado 继续读取陈旧文件路径的问题。
  这是 bitstream 阶段出现错误文件名时的真正根因。

## 4. 实际执行命令

### 4.1 生成 verilog

```bash
cd /home/soooarr/chipyard/fpga
export RISCV=/home/soooarr/chipyard/.conda-env/riscv-tools
export PATH=/home/soooarr/chipyard/.conda-env/riscv-tools/bin:$PATH
make SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideoConfig verilog
```

### 4.2 生成 bitstream

```bash
cd /home/soooarr/chipyard/fpga
export RISCV=/home/soooarr/chipyard/.conda-env/riscv-tools
export PATH=/tools/Xilinx/Vivado/2022.2/bin:/home/soooarr/chipyard/.conda-env/riscv-tools/bin:$PATH
make SUB_PROJECT=nexysvideo CONFIG=RadarAXIMMIONexysVideoConfig bitstream
```

### 4.3 生成 MCS

```bash
cd /home/soooarr/chipyard/fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig
export PATH=/tools/Xilinx/Vivado/2022.2/bin:$PATH
vivado -nojournal -mode batch \
  -source /home/soooarr/chipyard/fpga/fpga-shells/xilinx/common/tcl/write_cfgmem.tcl \
  -tclargs nexys_video obj/system.mcs obj/NexysVideoHarness.bit
```

## 5. 效果与验证

### 5.1 地址空间

Chisel 日志显示：

- DDR:
  `0x8000_0000 - 0xA000_0000`
- AXI MMIO port:
  `0x6000_0000 - 0x6001_0000`

符合 Phase-1 规划。

### 5.2 引脚问题已解除

这版构建已经不再因为额外 MMIO 顶层引脚而失败。
原来最担心的 “AXI MMIO 占用 package pins 导致实现失败” 在当前版本里没有再出现。

### 5.3 后端结果

`vivado.log` 中关键结果：

- Post-route timing:
  `WNS = 0.319 ns`
- Post-route hold:
  `WHS = 0.049 ns`
- `The design met the timing requirement.`
- `Bitgen Completed Successfully.`

## 6. 当前仍存在的 warning

当前 bitstream 成功，但仍有一些非阻塞 warning：

- `shell.xdc` 里有一条针对 `uart_rxd` 的 warning。
  这是因为当前配置使用的是 `WithNoUART + UARTTSI`，板级 UART 约束和当前实际端口不完全对应。
  不影响 bitstream 生成。

- MIG / AXI DMA / DSP 有一些 Vivado advisory 或 DRC warning。
  当前都没有升级为 error，bitstream 已成功生成。

如果后续要把日志收干净，可以优先处理 `shell.xdc` 里的 UART 约束。

## 7. 上板方案

### 7.1 JTAG 临时下载

适合快速验证：

- 文件：
  `obj/NexysVideoHarness.bit`
- 用 Vivado Hardware Manager 或 Digilent 工具直接下载到 FPGA。

### 7.2 写入板载 SPI Flash

适合断电保存：

- 文件：
  `obj/system.mcs`
- 用 Vivado `Program Configuration Memory Device` 写入板载 flash。

### 7.3 软件配套

当前仓库里已经有纯寄存器 DMA 裸机程序：

- `tests/radar-axi-dma-loopback.c`
- `tests/radar-axi-mmio-smoke.c`

建议后续上板顺序：

1. 先下载 `.bit`
2. 用 `radar-axi-mmio-smoke` 验证 `0x6000_0000` 控制口可读写
3. 再跑 `radar-axi-dma-loopback` 验证 DDR->DMA->loopback->DDR

## 8. 后续优化建议

建议后续按下面顺序推进：

1. 清理 `shell.xdc` 中与 `WithNoUART` 冲突的约束 warning
2. 把 DMA 软件测试切到与 `WithoutFPU` 一致的工具链/ABI
3. 增加 DMA 状态寄存器的更细粒度打印
4. 补一个上板 bring-up checklist
5. 若后续长期维护，考虑把 DMA 从 harness 集成进一步下沉到更稳定的系统级模块边界

## 9. 后续调试建议

建议保留下面几类调试抓手：

- `uart_tsi` printf 输出
- DMA 控制寄存器 dump
- MM2S / S2MM DMASR 状态轮询
- DDR init_calib_complete 指示
- 必要时接回 ILA 观察 AXI-Lite 和 AXI MM 主口握手

优先排查顺序建议：

1. DDR MIG 是否完成校准
2. `0x6000_0000` 控制口读写是否正常
3. DMA `RS` / `RESET` / `IDLE` / `HALTED` 状态是否符合预期
4. MM2S 是否真正发起读，S2MM 是否真正发起写
5. loopback 流握手是否完整
6. 结果 buffer 比对是否一致

## 10. 保存与恢复建议

为了避免后续迭代把当前好状态冲掉，建议至少保存三类内容：

1. 本文档
2. 本轮源码快照
3. 已生成的 `.bit` / `.mcs`

本轮已经额外生成本地快照文件，放在：

- `/home/soooarr/chipyard/fpga/deliverables/`

如果后续工作树被改乱，直接从这里恢复最稳。

## 11. 关于上传到 GitHub

当前仓库的 `origin` 指向上游官方仓库：

- `https://github.com/ucb-bar/chipyard.git`

因此本轮没有直接执行 `git push`，避免误推到上游仓库或因权限问题失败。

更稳妥的做法是：

1. 先把当前版本保存成本地快照/补丁/分支
2. 再推到你自己的 GitHub fork 或私有仓库

如果你下一步需要，我可以继续帮你做下面其中一项：

- 生成只包含本轮修改的 patch
- 生成一个本地备份分支名和恢复命令
- 帮你把当前版本整理成适合推到你个人 GitHub fork 的提交集合
