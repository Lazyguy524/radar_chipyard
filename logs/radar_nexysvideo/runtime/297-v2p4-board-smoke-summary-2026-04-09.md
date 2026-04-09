# QMLP PE-array v2.4 板级 smoke 摘要（2026-04-09）

## 测试对象

- bitstream：
  [NexysVideoHarness.bit](/home/soooarr/chipyard/fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideoConfig/obj/NexysVideoHarness.bit)
- 版本摘要：
  [289-qmlp-pe-array-v2p4-bitstream-summary-2026-04-08.md](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/289-qmlp-pe-array-v2p4-bitstream-summary-2026-04-08.md)
- 串口：
  `/dev/ttyUSB0`

## 本轮测试顺序

1. `init_write` 探针
2. `init_read` 探针
3. `hello.riscv` 最小 ELF
4. `radar-axi-dma-regression.riscv` 综合回归

## 关键结果

### 1. 串口连接正常

- `/dev/ttyUSB0` 存在并可打开
- `Connection succeeded` 能稳定出现

### 2. 写事务正常

- 日志：
  [294-v2p4-init-write-clean-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/294-v2p4-init-write-clean-2026-04-09.log)
- 关键现象：
  - `Writing 80000000 with 11223344`
  - `Done writing 80000000 with 11223344`

结论：
- `init_write` 正常

### 3. 读事务仍然卡住

- 日志：
  [295-v2p4-init-read-clean-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/295-v2p4-init-read-clean-2026-04-09.log)
- 关键现象：
  - `Connection succeeded`
  - 停在 `Reading 80000000 ...`

结论：
- `init_read` 仍未恢复

### 4. 最小 ELF 仍未真正起主体

- 日志：
  [292-v2p4-hello-noselfcheck-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/292-v2p4-hello-noselfcheck-2026-04-09.log)
- 关键现象：
  - 仅到 `Connection succeeded`
  - 未见 `hello` 输出

结论：
- ELF 装载/起始执行阶段仍不干净

### 5. 综合回归卡在第一个 selfcheck chunk

- 日志：
  [296-v2p4-integrated-regression-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/296-v2p4-integrated-regression-2026-04-09.log)
- 关键现象：
  - `Performing self check`
  - 卡在 `Self check chunk 80000000 to 80000400`

结论：
- 当前阻塞点仍然在最前面的读回 / selfcheck 路径

## 额外说明

- 本轮测试中发现过一次残留 `uart_tsi` 进程占用串口，已清理后重跑。
- 清理串口占用后，结论仍然不变：
  - 写能通
  - 读不回
  - 程序主体未真正启动

## 当前判断

- `v2.4` 的离线实现结果是好的，且优于 `v2.2/v2.3`
- 但板级 smoke 现象与前几版类似：
  - 写事务正常
  - 读事务返回路径仍然异常
- 因此目前还拿不到：
  - `QMLP logits`
  - `RUN_CYCLES`
  - 与 baseline `3554 cycles` 的新对比数据

## 下一步建议

1. 先做一次真正 fresh 的板级复位，再重复最小 `init_read`
2. 如果仍卡住，应优先把问题归因到：
   - `UART TSI` / 装载返回链
   - 而不是 `QMLP` 算法本体
3. 在读回路径恢复前，不建议继续用大 ELF 反复硬撞
