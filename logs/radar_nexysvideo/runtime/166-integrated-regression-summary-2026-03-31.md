# 单 ELF 集成回归结果摘要

更新时间：2026-03-31

## 结果

- `tests/radar-axi-dma-regression.riscv` 已在板上通过
- 原始日志：`logs/radar_nexysvideo/runtime/165-run-integrated-regression-2026-03-31.log`

## 集成回归覆盖项

1. DMA CSR MMIO smoke
2. cache coherence probe
3. 多长度 consistency regression

## 关键结论

1. 通过把多项回归合并到同一个 ELF、同一次 `uart_tsi` 会话中，已经可以避免“每跑一项都要按一次 `CPU_RESET`”的流程问题。
2. 当前板上 `MMIO + cache maintenance + 多长度 DMA loopback` 已在单次运行中完整通过。
3. cache probe 的最新结果表明：
   - 完全不做 cache maintenance 时会失败
   - 仅做 pre-DMA maintenance 在本轮观测中已足以通过 compare
   - 做完整 pre/post maintenance 也稳定通过
4. 对工程使用来说，软件侧仍应继续保留完整 pre/post cache maintenance 协议，不建议因为个别观测结果放松这个约束。

## 当前推荐入口

后续板级日常回归优先使用：

- `tests/radar-axi-dma-regression.riscv`

单项测试仍保留，用于问题放大定位。
