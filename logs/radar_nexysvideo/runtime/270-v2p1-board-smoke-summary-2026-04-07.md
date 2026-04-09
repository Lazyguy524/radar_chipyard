## QMLP PE-array v2.1 板测冒烟摘要

- 时间：2026-04-07
- bitstream 摘要：
  `logs/radar_nexysvideo/runtime/261-qmlp-pe-array-v2p1-bitstream-summary-2026-04-07.md`
- 本轮串口设备：`/dev/ttyUSB1`

### 本轮观察到的现象

1. 串口设备号发生变化

- 本轮烧录后，UART 不再枚举成 `/dev/ttyUSB0`
- 实际可用口名是 `/dev/ttyUSB1`

2. 最小写事务可达

- 探针日志：
  `logs/radar_nexysvideo/runtime/264-v2p1-init-write-probe-seq-2026-04-07.log`
- 终端观测到：
  - `Writing 80000000 with 11223344`
  - `Done writing 80000000 with 11223344`

说明：
- `v2.1` 至少恢复到了“连接 + init_write 可达”的状态。

3. 读事务比上一轮更接近正常入口，但仍未完成返回

- 探针日志：
  `logs/radar_nexysvideo/runtime/265-v2p1-init-read-probe-seq-2026-04-07.log`

终端观测到：
- 已经能稳定走到 `Connection succeeded`
- 但没有进一步返回读值

说明：
- 相比上一版 `v2` 的“写通、读卡死”现象，`v2.1` 至少把串口连接和装载前入口稳定住了
- 但 `init_read` 仍未拿到最终数据

4. 单 ELF 综合回归仍停在装载早期

- 带 selfcheck：
  `logs/radar_nexysvideo/runtime/267-run-integrated-regression-v2p1-2026-04-07.log`
  - 停在 `Self check chunk 80000000 to 80000400`

- 不带 selfcheck：
  `logs/radar_nexysvideo/runtime/268-run-integrated-regression-v2p1-noselfcheck-2026-04-07.log`
  - 停在 `Connection succeeded`

5. 单独 QMLP ELF 仍未进入主体

- 日志：
  `logs/radar_nexysvideo/runtime/269-run-qmlp-v2p1-noselfcheck-2026-04-07.log`
  - 停在 `Connection succeeded`

### 当前判断

- `v2.1` 比 `v2` 更接近可用板测状态：
  - bitstream 时序更稳
  - UART / init_write 已恢复
  - 不再是完全无响应

- 但本轮仍然没有真正进入：
  - 综合回归主体
  - 或 QMLP 推理主体

- 因此当前仍拿不到：
  - `RUN_CYCLES`
  - 多样本 logits
  - 与 baseline `3554 cycles` 的有效板级对比

### 结论

- `v2.1` 不是失败版本，属于“比 v2 明显前进，但还没完全跑通”的状态。
- 下一步应继续查：
  - 为何 `init_write` 已恢复，但 `init_read / ELF 装载` 仍未完成
  - 是否还需要进一步降低 `QMLP + DMA` 组合后的边缘时序/返回路径压力
