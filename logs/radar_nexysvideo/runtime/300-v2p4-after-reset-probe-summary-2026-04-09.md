# QMLP PE-array v2.4 reset 后探针摘要（2026-04-09）

## 测试前提

- 板子已重新按下 `CPU_RESET`
- 串口设备：`/dev/ttyUSB0`

## 本轮新增测试

### 1. fresh reset 后 `init_read`

- 日志：
  [298-v2p4-init-read-after-reset-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/298-v2p4-init-read-after-reset-2026-04-09.log)
- 结果：
  - `Connection succeeded`
  - 随后卡在 `Reading 80000000 ...`

结论：
- fresh reset 后，最小读事务仍未恢复

### 2. fresh reset 后 `hello.riscv`

- 日志：
  [299-v2p4-hello-after-reset-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/299-v2p4-hello-after-reset-2026-04-09.log)
- 结果：
  - `Connection succeeded`
  - 未见任何 `hello` 主体输出

结论：
- 程序主体仍未真正起跑

## 当前判断

- `v2.4` 的板级问题在 reset 后依然存在
- 现象仍然是：
  - 写事务可以完成
  - 读事务不返回
  - 最小 ELF 也起不来
- 因此当前阻塞点依旧在：
  - `UART TSI`
  - `init_read / selfcheck / ELF 装载返回链`
- 不是 `QMLP` 算法本体已经算错

## 与前一轮结论关系

- 本轮结果与
  [297-v2p4-board-smoke-summary-2026-04-09.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/297-v2p4-board-smoke-summary-2026-04-09.md)
  保持一致
- `CPU_RESET` 并没有把当前读回异常清掉
