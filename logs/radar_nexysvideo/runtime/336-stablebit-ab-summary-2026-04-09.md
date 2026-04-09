# 旧稳定 Bit 对照摘要（2026-04-09）

## 对照对象

本轮对照使用的旧稳定 bit 为：

- [current_stable/NexysVideoHarness.bit](/home/soooarr/chipyard/fpga/deliverables/radar_nexysvideo_bits/current_stable/NexysVideoHarness.bit)

与当前 `v2.4` PE 版本不同：

- 旧稳定 bit SHA256: `3da3e145542834df324e158c1bd0f8a0d9f63e106f38840c5d649510acd58fcc`
- `v2.4` bit SHA256: `17bc8e9dfac0f0c4102f97a8271c944e2c68ae4a7174d8d6b10e58dba960790a`

## 结论

这轮对照说明：

1. **`0x80000980..0x8000098c` 固定坏窗不是旧稳定 bit 的固有问题**
   - 在旧稳定 bit 上，这一整段窗口写回正常
2. **但 `regression.riscv +selfcheck @115200` 在旧稳定 bit 上仍然会在 `0x80000980` 失败**
   - 说明“`selfcheck` 大程序下载/校验链在该地址首次暴露问题”并不完全是 `PE/QMLP` 新引入的
3. **最小程序和最小窗口探针在旧稳定 bit 上都正常**
   - 说明旧稳定 bit 的基本读写链没有坏

因此，目前最准确的阶段判断是：

**PE 版本 `v2.4` 确实引入了额外的固定坏窗现象；但 `0x80000980` 这个失败点本身也和当前 `uart_tsi selfcheck / 大程序下载链` 有更深层的共性问题，不是单一由 PE 版本独占产生。**

## 关键结果

### 1. 旧稳定 bit 的固定窗口探针全部正常

脚本入口：

- [probe_nexysvideo_ddr_window.sh](/home/soooarr/chipyard/scripts/probe_nexysvideo_ddr_window.sh)

运行日志：

- 驱动日志：
  [331-stablebit-ddr-window-probe-driver-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/331-stablebit-ddr-window-probe-driver-2026-04-09.log)
- 详细日志：
  [stablebit-ddr-window-probe-2026-04-09-2026-04-09-170025.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/stablebit-ddr-window-probe-2026-04-09-2026-04-09-170025.log)

关键现象：

- `0x80000980 -> 0xA5A5A5A5`，读回正常
- `0x80000984 -> 0x99AABBCC`，读回正常
- `0x80000988 -> 0x13579BDF`，读回正常
- `0x8000098c -> 0x2468ACE0`，读回正常
- 对照窗口 `0x80000a7c..0x80000a90` 也全部正常

这与 `v2.4` 上的现象形成了明确对比：

- `v2.4`：`0x80000980..0x8000098c` 异常
- 旧稳定 bit：同一窗口全部正常

### 2. `hello.riscv + selfcheck @115200` 在旧稳定 bit 上完全通过

日志：

- [332-stablebit-hello-selfcheck-115200-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/332-stablebit-hello-selfcheck-115200-2026-04-09.log)

关键结果：

- `Hello world from core 0, a rocket`
- `Self check succeeded chunk 80000000 to 80000400`
- `Self check succeeded chunk 80000400 to 80000800`
- `Self check succeeded chunk 80000800 to 80000990`
- `Self check success`

说明：

- 小 ELF 在旧稳定 bit 上工作正常
- `0x80000980` 并不是“只要读到这里就一定坏”

### 3. `regression.riscv + selfcheck @115200` 在旧稳定 bit 上仍在 `0x80000980` 首次失败

日志：

- [333-stablebit-integrated-regression-115200-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/333-stablebit-integrated-regression-115200-2026-04-09.log)

关键结果：

- 前两个 `selfcheck chunk` 成功
- 第三个 chunk 在 `0x80000980` 首次失败
- 报错形式与 `v2.4` 类似：
  - `Self check failed at address 80000980 1 != 9b`

这说明：

- 对于较大的 `regression.riscv`，`selfcheck` 路径本身在当前环境下仍可能在同一地址首次暴露问题
- 因而不能把所有问题都归因给 `PE` 版 QMLP

### 4. `regression.riscv @115200 --no-selfcheck` 仍然卡在下载后无进一步输出

日志：

- [335-stablebit-integrated-regression-noselfcheck-115200-stdline-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/335-stablebit-integrated-regression-noselfcheck-115200-stdline-2026-04-09.log)

当前可见现象：

- 到 `Connection succeeded` 为止
- 之后长时间无进一步输出

这说明：

- 非 `selfcheck` 路径也不是完全健康
- 只是它没有像 `selfcheck` 那样立即把问题暴露成固定地址比对失败

## 当前工作判断

当前应把问题拆成两层：

### A. `v2.4` 新引入的问题

`v2.4` 上确实出现了旧稳定 bit 不具备的固定窗口异常：

- 在 `v2.4` 上，单独地址探针就能复现 `0x80000980..0x8000098c` 坏窗
- 在旧稳定 bit 上，同一窗口单独探针全部正常

这部分可以视为 `v2.4 / PE 版本` 新增问题。

### B. 更底层、并非 PE 独占的问题

旧稳定 bit 上：

- `hello+selfcheck` 正常
- 但 `regression+selfcheck` 仍在 `0x80000980` 首次失败

这说明还存在一层更底的共性问题：

- 大 ELF 下载/校验路径
- `uart_tsi` 的 `selfcheck` 机制
- 或当前系统在持续装载时对该地址区间的处理

这部分并不是 `PE` 版本独占问题。

## 下一步建议

后续应该并行推进两条线：

1. **继续修 `v2.4` 的固定窗口异常**
   - 因为旧稳定 bit 上该窗口本身是好的
   - 这部分是 `v2.4` 自身需要解决的问题
2. **单独研究 `regression/selfcheck` 在旧稳定 bit 上也会触发的共性下载问题**
   - 这部分不应再简单归咎为 `PE` 引入

