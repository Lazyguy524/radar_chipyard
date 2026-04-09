# v2.1 串行探针摘要（2026-04-07）

## 背景

- 当前板上烧录版本：`radar-qmlp-pe-array-v2p1`
- 当前有效串口：`/dev/ttyUSB1`
- 本轮探针严格串行执行，避免多个 `uart_tsi` 进程同时占用同一串口导致结果失真。

## 可信结果

### 1. bootreg 读探针仍然卡住

- 日志：
  [278-v2p1-init-read-bootreg-serial-2026-04-07-171400.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/278-v2p1-init-read-bootreg-serial-2026-04-07-171400.log)
- 现象：
  - 能到 `Connection succeeded`
  - 但在 `+init_read=0x1000` 之后没有返回值
  - 15 秒超时退出

### 2. DDR 写探针仍然能完成

- 日志：
  [279-v2p1-init-write-serial-2026-04-07-171420.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/279-v2p1-init-write-serial-2026-04-07-171420.log)
- 现象：
  - 能到 `Connection succeeded`
  - 明确打印：
    - `Writing 80000000 with 11223344`
    - `Done writing 80000000 with 11223344`
  - 之后 `uart_tsi` 未主动退出，由外层 `timeout` 收尾

## 当前判断

- `v2.1` 的板上状态不是“串口完全不通”，而是：
  - `写事务可完成`
  - `读事务/读回返回路径仍不稳定`
- 由于 `bootreg` 读也卡住，这一问题已经不局限于 `DDR init_read`，而更像是全局读事务返回链路仍处于边缘状态。
- 因此当前还不能拿到 `QMLP v2.1` 的有效 `RUN_CYCLES` 板测数据。

## 后续动作

- 已经修正手工脚本，支持通过 wrapper 直接传入 `--tty /dev/ttyUSB1`
- 下一步将继续尝试更保守的 `PE` 并行度版本，以优先恢复板上读回稳定性
