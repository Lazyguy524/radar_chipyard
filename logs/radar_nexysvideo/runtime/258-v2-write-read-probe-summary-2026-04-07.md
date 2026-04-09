# QMLP PE-array v2 最小读写事务摘要

更新时间：2026-04-07

## 1. 测试目的

在 `PE-array v2` bitstream 已通过 `50 MHz` 时序、但板级综合回归尚未进入程序主体的情况下，进一步确认当前问题到底落在：

- 写事务
- 还是读事务

## 2. 最小探针结果

### 2.1 init_write

命令语义：

- `+no_hart0_msip +init_write=0x80000000:0x11223344 none`

现场输出已经确认：

- `Writing 80000000 with 11223344`
- `Done writing 80000000 with 11223344`

对应日志：

- [256-v2-init-write-probe-after-reset-2026-04-07.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/256-v2-init-write-probe-after-reset-2026-04-07.log)

结论：

- **当前写事务是通的**

### 2.2 init_read

命令语义：

- `+no_hart0_msip +init_read=0x80000000 none`

现场现象：

- 终端停在 `Reading 80000000 ...`
- 长时间无返回值

对应日志：

- [255-v2-init-read-probe-after-reset-2026-04-07.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/255-v2-init-read-probe-after-reset-2026-04-07.log)
- [257-v2-init-read-after-write-2026-04-07.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/257-v2-init-read-after-write-2026-04-07.log)

结论：

- **当前读事务仍未建立返回**

## 3. 当前判断

这轮已经把问题从“程序太大/回归入口太复杂”进一步缩小为：

- UART TSI 到板子的 **初始化写** 是可完成的
- UART TSI 到板子的 **初始化读** 仍然卡住

因此，当前 `PE-array v2` 还不能进入 `QMLP` 功能与性能对拍，不是因为：

- 算法本体已经报错
- 或 `RUN_CYCLES` 已经异常

而是因为：

- **更前面的 init_read / readback 路径本身没有恢复正常**

## 4. 对后续测试的意义

当前最可信的结论是：

1. `PE-array v2` bitstream 可综合、可出 bit、时序通过
2. 现场写通、读不回
3. 因此后续要继续推进，优先级应放在：
   - UART TSI / init_read / 读回应答路径定位
   - 或者寻找不依赖当前读回链路的更稳妥 bring-up 手段
