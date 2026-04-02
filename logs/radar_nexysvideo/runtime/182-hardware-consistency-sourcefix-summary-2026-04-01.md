# sourcefix 后首轮板测摘要

## 结果 1：uncached alias 正式通过
- 日志：`180-run-uncached-alias-after-sourcefix-2026-04-01.log`
- 关键结论：
  - 程序已进入主体
  - `UNCACHED compare passed`
  - `AXI DMA uncached-alias PASSED`
- 说明：
  - 这版 `ExtTLMem incoherent alias + source-width fix` 已经在板上跑通
  - CPU 通过 uncached alias 访问 DDR buffer 时，DMA loopback 不再依赖 cache maintenance

## 结果 2：紧接着跑第二个独立程序仍会碰到老的 bring-up 问题
- 日志：`181-run-integrated-regression-on-uncached-alias-bitstream-2026-04-01.log`
- 关键结论：
  - 串口连接成功
  - `uart_tsi selfcheck` 前几块通过
  - 在后续块失败于 `80000dc0`
- 说明：
  - 这更像之前已经见过的“连续独立 ELF 会话 + 固定装载窗口”问题
  - 不能据此否定 sourcefix/uncached alias 本身

## 当前判断
- 新的硬件一致性路径已经被正向验证
- 若要继续跑综合回归，建议先做一次 `CPU_RESET`
