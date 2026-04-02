# uncached alias 并入综合回归后的板测结论

## 板测结果
- 日志：`185-run-integrated-regression-with-uncached-2026-04-01.log`
- 最终结果：`AXI_DMA_REGRESSION_PASSED`

## 单 ELF 覆盖情况
- `[MMIO]` 通过
- `[CACHE]` 通过，并再次确认：
  - no-maint 在 `word 0` 暴露非一致性
  - pre-only / full-maint 可通过
- `[UNCACHED]` 通过
  - `TX_CPU=0x0000001081000000`
  - `RX_CPU=0x0000001081001000`
  - `compare passed`
- `[CONSISTENCY]` 通过
  - 4/8/15/16/31/32/33/63/64 words 全通过

## 当前结论
- `ExtTLMem incoherent alias + source-width fix` 已在板上被正向验证
- 现在系统同时具备两条可工作的 DMA buffer 使用路径：
  - cacheable DDR + 软件 cache maintenance
  - uncached DDR alias + 无需 cache maintenance
- 单 ELF 综合回归已经覆盖这两条路径，并在当前 bitstream 上通过
