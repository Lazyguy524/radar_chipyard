# QMLP PE-array v2 板测现场摘要

更新时间：2026-04-07

## 1. 本轮目的

在已经完成 `bitstream` 生成并满足 `50 MHz` 时序的前提下，对 `QMLP PE-array v2` 做板级 bring-up，重点确认：

1. 老链路综合回归是否仍然可运行
2. `QMLP_RUN_CYCLES` 是否较旧版 `3554 cycles` 下降

## 2. 当前结果

本轮尚未跑到 `QMLP` 程序主体，阻塞点出现在更前面的 UART TSI 装载/探针阶段。

关键现象：

- 带 `+selfcheck` 的单 ELF 综合回归，连续两次都卡在：
  - `Self check chunk 80000000 to 80000400`
- 关闭 `selfcheck` 后再跑综合回归，日志仅到：
  - `Connection succeeded`
- 最小探针：
  - `+init_read=0x80000000 none`
  也出现持续等待，没有返回读值

对应日志：

- [run-integrated-regression-manual-2026-04-07-145340.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/run-integrated-regression-manual-2026-04-07-145340.log)
- [run-integrated-regression-manual-2026-04-07-145502.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/run-integrated-regression-manual-2026-04-07-145502.log)
- [run-integrated-regression-manual-noselfcheck-2026-04-07-145605.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/run-integrated-regression-manual-noselfcheck-2026-04-07-145605.log)
- [253-v2-init-read-probe-2026-04-07.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/253-v2-init-read-probe-2026-04-07.log)
- [run-integrated-regression-manual-noselfcheck-2026-04-07-145955.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/run-integrated-regression-manual-noselfcheck-2026-04-07-145955.log)
- [255-v2-init-read-probe-after-reset-2026-04-07.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/255-v2-init-read-probe-after-reset-2026-04-07.log)

## 3. 当前判断

当前不能把问题归因到 `QMLP PE-array v2` 算法本体，因为：

1. bitstream 已成功生成
2. 时序已通过
3. 在再次执行 `CPU_RESET` 后，当前连最小 `init_read` 都仍然没有建立返回

因此更准确的判断是：

- **当前阻塞在更前面的 bring-up / UART TSI 装载与初始读事务层**
- **不是已经跑到 `QMLP` 再算错**

## 4. 旧版基线对比

当前已知稳定基线仍是旧版固定 `QMLP`：

- [243-qmlp-multisample-pass-summary-2026-04-06.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/243-qmlp-multisample-pass-summary-2026-04-06.md)
- 其 `QMLP` 本体平均周期为：
  - `3554 cycles`

本轮 `PE-array v2` 因尚未进入程序主体，所以还**不能给出新的 `RUN_CYCLES` 对比数据**。

## 5. 当前可保留的结论

1. `QMLP PE-array v2` 已完成 RTL 重构并重新通过 `50 MHz` 时序
2. 这版已经具备上板条件
3. 但本轮现场仍未拿到有效的板级功能数据
4. 下次继续测试前，应优先解决：
   - 当前 UART TSI bring-up 链路的稳定性
   - 是否需要更干净的板级复位/重新上电
   - 是否要改成更稳妥的单程序装载入口或更小探针程序
