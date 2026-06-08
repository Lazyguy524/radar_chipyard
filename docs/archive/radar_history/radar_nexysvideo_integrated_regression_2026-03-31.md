# Radar Nexys Video 单 ELF 集成回归说明

更新时间：2026-03-31

## 1. 目标

当前板级 bring-up 的主要工程问题不是单个 DMA 测试跑不通，而是：

- 多个独立 `.riscv` 程序连续运行时，容易被 `uart_tsi selfcheck` 的固定装载窗口污染影响
- 结果就是用户在多项回归之间需要频繁手动按 `CPU_RESET`

为减少这种人工干预，本轮新增一个单 ELF 集成回归程序：

- `tests/radar-axi-dma-regression.c`
- 生成产物：`tests/radar-axi-dma-regression.riscv`

它的思路是把原来分散在多个 bring-up 程序里的关键验证，合并到同一次下载、同一进程执行中。

## 2. 当前集成内容

单 ELF 程序内部依次执行：

1. DMA CSR MMIO smoke
2. cache coherence probe
3. 多长度 consistency regression

这样做的目的不是替代所有单项测试，而是提供一个更适合板级日常回归的入口。

## 3. 当前收益

相比原来的方式：

- 原来需要：
  - 下载一个程序
  - 运行
  - 再下载下一个程序
  - 经常在中间按一次 `CPU_RESET`

现在改成：

- 一次下载 `radar-axi-dma-regression.riscv`
- 在同一程序里连续完成多项检查

这不能彻底消除所有 reset 需求，但可以显著减少“每跑一项按一次”的人工操作。

## 4. 当前边界

需要明确的是，这一改动解决的是：

- 多个独立 bring-up ELF 串行运行时的工程体验问题

它没有改变的部分是：

- Rocket 与 DMA 对 cacheable DDR buffer 仍然不是硬件自动一致性
- 软件侧仍然必须执行 pre/post cache maintenance

因此，即使后面大部分回归都切到单 ELF 模式，buffer 使用协议依然必须保留。

## 5. 使用建议

后续建议优先用下面这个程序做日常板级检查：

- `tests/radar-axi-dma-regression.riscv`

单项程序仍然保留，适合在某一环节失败后单独放大观察：

- `tests/radar-axi-mmio-smoke.riscv`
- `tests/radar-axi-dma-loopback-cacheprobe.riscv`
- `tests/radar-axi-dma-loopback-cachemaint.riscv`
- `tests/radar-axi-dma-loopback.riscv`
- `tests/radar-axi-dma-consistency.riscv`

## 6. 下一步建议

如果这个单 ELF 模式在板上表现稳定，下一步更推荐继续做：

1. 把未来的 accelerator smoke test 也并入同一回归框架
2. 让“平台回归”尽量变成一次下载、一键完成
3. 再逐步减少对手工 `CPU_RESET` 的依赖
