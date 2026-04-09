# v2.4 板级根因收敛摘要（2026-04-09）

## 结论

当前 `v2.4` 的板级问题已经从“串口/TSI 全局不通”收敛为一个更具体的问题：

- `921600` 波特率下，`init_read / selfcheck / ELF` 装载很容易卡住
- 将波特率降到 `115200` 后，最小 `BootROM` 读、`DDR init_write`、`DDR init_readback` 都可以工作
- 在 `115200` 下继续做 `selfcheck`，问题不再是“卡住”，而是**固定在 `0x80000980` 附近出现数据不一致**
- 对该区域单独做地址窗口探针后，确认：
  - `0x80000980`
  - `0x80000984`
  - `0x80000988`
  - `0x8000098c`
  这 **4 个连续 32-bit 字** 读写异常
- 异常区前后地址可正常写回，另一组对照窗口 `0x80000a80..0x80000a8c` 也完全正常

因此，当前更准确的描述不是“QMLP 算法坏了”，而是：

**在 `v2.4` 当前板级状态下，DDR 低地址页存在一个固定的 16B 地址窗口异常，导致 `uart_tsi selfcheck` 在 `0x80000980` 首次报错。**

## 关键证据

### 1. 低波特率下最小读写恢复

- `BootROM init_read @115200` 成功，读回 `0x517`
  - [315-v2p4-init-read-bootrom-115200-serial-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/315-v2p4-init-read-bootrom-115200-serial-2026-04-09.log)
- `DDR init_write @115200` 成功
  - [316-v2p4-init-write-ddr-115200-serial-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/316-v2p4-init-write-ddr-115200-serial-2026-04-09.log)
- `DDR init_readback @115200` 成功，读回 `0x55667788`
  - [317-v2p4-init-read-ddr-115200-serial-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/317-v2p4-init-read-ddr-115200-serial-2026-04-09.log)

这说明：

- 低波特率下，`read` 返回链不是完全死掉
- `v2.4` 不是“板上完全不能执行”

### 2. `hello.riscv` 在 115200 下可以直接跑起来

- [318-v2p4-hello-115200-long-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/318-v2p4-hello-115200-long-2026-04-09.log)

关键输出：

- `Hello world from core 0, a rocket`

这说明：

- 低波特率下，`ELF` 下载和最小程序执行是可行的
- 问题已经不再是“CPU 完全起不来”

### 3. `selfcheck` 在 115200 下不再卡死，而是报固定地址错误

- `regression.riscv +selfcheck`
  - [319-v2p4-integrated-regression-115200-long-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/319-v2p4-integrated-regression-115200-long-2026-04-09.log)
- `hello.riscv +selfcheck`
  - [320-v2p4-hello-selfcheck-115200-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/320-v2p4-hello-selfcheck-115200-2026-04-09.log)

两者都表现为：

- 前两个 `selfcheck chunk` 正常
- 第三个 chunk 在 **`0x80000980`** 首次失败

其中：

- `regression` 报 `1 != 9b`
- `hello` 报 `1 != 0`

这说明：

- 问题与具体 ELF 内容无关
- 首个失败点具有明显的**固定地址性**

### 4. 固定失败地址窗口验证

对失败窗口周围地址做单独 `init_write/init_readback`，结果见：

- [327-v2p4-ddr-window-probe-115200-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/327-v2p4-ddr-window-probe-115200-2026-04-09.log)

结果如下：

- `0x8000097c` 写回正常
- `0x80000980` 写入 `0xA5A5A5A5`，读回 `0x00000001`
- `0x80000984` 写入 `0x99AABBCC`，读回 `0x00000000`
- `0x80000988` 写入 `0x13579BDF`，读回 `0x00000000`
- `0x8000098c` 写入 `0x2468ACE0`，读回 `0x00000000`
- `0x80000990` 写回正常
- `0x80000994` 写回正常

这说明：

- 异常不是随机分布
- 异常刚好覆盖 **`0x80000980..0x8000098c` 这一段连续 16B 窗口**

### 5. 对照窗口正常

对另一组对照窗口：

- `0x80000a7c`
- `0x80000a80`
- `0x80000a84`
- `0x80000a88`
- `0x80000a8c`
- `0x80000a90`

做相同验证，结果全部正常：

- [328-v2p4-ddr-control-window-115200-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/328-v2p4-ddr-control-window-115200-2026-04-09.log)

进一步又测试了同低位偏移、不同页：

- `0x80001980`
- `0x80001984`
- `0x80002980`
- `0x80002984`

这些地址也全部正常：

- [329-v2p4-ddr-repeat-offset-probe-115200-2026-04-09.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/329-v2p4-ddr-repeat-offset-probe-115200-2026-04-09.log)

这说明：

- 当前不是“所有 `...980` 偏移都坏”
- 更像是 **DDR 低地址页内一个固定 beat 出现异常**

## 当前判断

截至这一步，可以排除或弱化以下猜测：

- 不是单纯的 `QMLP logits` 算错
- 不是 `UART TSI` 完全不能工作
- 不是整个 DDR 区域都不可读写
- 不是所有相同低位偏移都会失败

当前最合理的工作判断是：

1. `921600` 会放大串口返回链不稳定，掩盖真实问题
2. 在 `115200` 下，系统已经能暴露出更底层、更稳定复现的故障点
3. 该故障点表现为：
   - **低 DDR 地址页内固定 16B 窗口异常**
   - 其首个暴露地址是 `0x80000980`
4. 这也是 `selfcheck` 在不同 ELF 上都先在 `0x80000980` 失败的原因

## 下一步建议

后续不要再先拿大程序硬撞，而应该优先查：

1. 为什么 `0x80000980..0x8000098c` 这一拍异常
   - 地址译码
   - DDR/MIG 低地址页行为
   - TSI/TL/AXI 路径在该 beat 上的掩码/拼接
2. 为什么 `921600` 会把问题表现成“读回挂住”
   - 当前更像是高波特率把串口层稳定性先拖垮
3. 是否为当前 `v2.4` 集成后新增的问题
   - 可与已知稳定旧 bit 做同样窗口探针比对
