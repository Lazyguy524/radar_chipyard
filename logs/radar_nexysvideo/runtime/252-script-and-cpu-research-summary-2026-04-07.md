# 阶段摘要：明日板测脚本与 CPU 升级调研

更新时间：2026-04-07

## 1. 已新增脚本

为避免明日手工拼接 `uart_tsi` 命令，新增了以下脚本：

- [run_nexysvideo_uart_tsi.sh](/home/soooarr/chipyard/scripts/run_nexysvideo_uart_tsi.sh)
  - 通用串口加载脚本
  - 默认：
    - `tty=/dev/ttyUSB0`
    - `baudrate=921600`
    - `bin=tests/radar-axi-dma-regression.riscv`
    - 开启 `+selfcheck`
- [run_nexysvideo_integrated_regression.sh](/home/soooarr/chipyard/scripts/run_nexysvideo_integrated_regression.sh)
  - 直接跑当前推荐的单 ELF 综合回归
- [run_nexysvideo_qmlp.sh](/home/soooarr/chipyard/scripts/run_nexysvideo_qmlp.sh)
  - 直接跑 `QMLP` 单项程序

运行日志会自动写到：

- `logs/radar_nexysvideo/runtime/`

推荐明日上板顺序：

1. 烧录当前 `PE-array v2` bitstream
2. 接好 `/dev/ttyUSB0`
3. 先执行：
   - `scripts/run_nexysvideo_integrated_regression.sh`
4. 如需单独看 `QMLP`：
   - `scripts/run_nexysvideo_qmlp.sh`

## 2. CPU 升级调研文档

已新增中文调研报告：

- [radar_cpu_upgrade_research_report_2026-04-07.md](/home/soooarr/chipyard/docs/radar_cpu_upgrade_research_report_2026-04-07.md)

报告内容包括：

- 近五年高影响 RISC-V CPU / RVV / custom instruction / CPU+accelerator 协同代表工作
- 这些路线对当前 `Rocket + DDR + DMA + AXIS + QMLP` 项目的适配性分析
- 工作量判断
- 对论文质量提升的帮助判断
- 当前最合适的结论

报告的核心收口是：

- **当前项目不建议优先把 CPU 升级作为论文主线**
- **更推荐保持 Rocket 作为控制核，把主要创新放在 `PE/MAC` 阵列和数据搬运优化上**
- **若确实需要写 CPU 贡献，优先考虑轻量级 `CFU/custom instruction`，而不是重做 RVV/OOO 核**
