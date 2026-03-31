# Radar Nexys Video 外部子模块补丁清单

更新时间：2026-03-31

## 目的

当前项目的最终可运行状态并不只依赖顶层仓库，还依赖若干子模块中的本地修改。  
为了保证顶层仓库在 GitHub 上至少保留完整的工程记录，这里把这些补丁的作用和位置明确列出。

本文件不展开 debug 过程，只记录**当前系统状态所依赖的子模块改动**。

---

## 1. `fpga/fpga-shells`

### 修改文件

- `fpga/fpga-shells/src/main/scala/devices/xilinx/xilinxnexysvideomig/XilinxNexysVideoMIG.scala`

### 作用

这是当前最关键的一处外部子模块修改，作用包括：

1. 修复 Nexys Video MIG wrapper 中的 AXI ID 宽度预算问题。
2. 确保共享 xbar 下的内部 ID 宽度不会超过 MIG 黑盒能够接收的 `4-bit AXI ID`。
3. 暴露 MIG 边界调试信号，辅助定位 MM2S 读返回路径问题。

### 工程意义

没有这部分修改，当前项目不会达到现在的“MM2S 主读口已修通”的状态。

---

## 2. `generators/testchipip`

### 修改文件

- `generators/testchipip/uart_tsi/testchip_uart_tsi.cc`

### 作用

在 `uart_tsi` 建立连接前，主动丢弃串口中遗留的 stale bytes，避免旧数据影响新的 TSI 会话。

### 工程意义

这不是 DMA 主链硬件修复，但它明显改善了板级 bring-up 阶段 `uart_tsi` 的稳定性和可重复性。

---

## 3. `toolchains/riscv-tools/riscv-spike-devices`

### 修改文件

- `toolchains/riscv-tools/riscv-spike-devices/Makefile`

### 作用

在构建 `libspikedevices.so` 时补充 `fdt` 头文件搜索路径，避免相关编译问题。

### 工程意义

这项修改属于工具链支撑层，作用是保证当前开发环境中的相关构建链可持续工作。

---

## 4. 当前建议

如果后续要把当前项目状态完整迁移到新的 GitHub 仓库或新的开发环境，建议按以下顺序处理：

1. 先同步顶层仓库中的文档、测试、构建入口和当前说明。
2. 再把上述三个子模块中的本地补丁单独提交到各自可访问的远端。
3. 最后再更新顶层仓库的 submodule pointer，使整个工程达到“clone 后可复现”的状态。

---

## 5. 结论

当前顶层仓库已经可以承载：

- 当前系统说明文档
- 当前测试程序
- 当前软件运行约束
- 当前可视化架构说明

而本文件用于补充说明：

> 当前系统最终能跑通，还依赖少量关键的外部子模块本地补丁。
