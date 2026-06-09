# Xradar RoCC 与自定义指令

## 当前目标

Xradar 的当前目标是验证 radar/QMLP workload 中的小粒度 int8 MAC 是否适合 RISC-V custom instruction/core coupling。第一阶段只实现 `rqdot4`，用于替代 QMLP 中 4 个 signed int8 MAC 的组合。

## `rqdot4` 语义

输入：

- `rs1[31:0]`：4 个 packed int8 lane
- `rs2[31:0]`：4 个 packed int8 lane

输出：

```text
rd = sign_i8(rs1.byte0) * sign_i8(rs2.byte0)
   + sign_i8(rs1.byte1) * sign_i8(rs2.byte1)
   + sign_i8(rs1.byte2) * sign_i8(rs2.byte2)
   + sign_i8(rs1.byte3) * sign_i8(rs2.byte3)
```

例如：

```text
lhs = 0xfc03fe01 -> {1, -2, 3, -4}
rhs = 0x08f906fb -> {-5, 6, -7, 8}
dot = -70
```

## 指令编码规则

bare-metal C inline asm 必须使用：

```asm
.insn r CUSTOM_0, 7, 0, rd, rs1, rs2
```

关键点：RoCC custom instruction 的 `funct3` 位用于编码 `xd/xs1/xs2`。这里要读两个源寄存器并写回目标寄存器，所以 `funct3=7`。曾经使用 `funct3=0` 导致目标没有写回，板上症状是结果等于 packed `rs1` 值 `0xfc03fe01`，不是 arithmetic bug。

## RoCC RTL 调度

当前 RTL 在 [../../fpga/src/main/scala/nexysvideo/XradarRoCC.scala](../../fpga/src/main/scala/nexysvideo/XradarRoCC.scala)。

状态机：

| 状态 | 作用 |
| --- | --- |
| `sIdle` | 等待 RoCC command，捕获 `rd/rs1/rs2/funct` |
| `sMul` | 计算并寄存 4 个 signed int8 乘积 |
| `sSum` | 对 4 个乘积求和并寄存 |
| `sResp` | 通过 RoCC response 写回 `rd` |

该 pipelined 版本解决了一周期 combinational DSP/response path 的 timing 问题。

## 板级结果

2026-06-09 timing-clean pipelined RoCC bitstream：

- WNS `+0.004 ns`
- TNS `0.000 ns`
- WHS `+0.009 ns`
- `PROGRAM_DONE`

Functional validation：

- single probe PASS：`rqdot4` 返回 `-70`
- memory-smoke PASS：4/4 basic cases，8/8 QMLP semantic cases
- repeat-after-reset PASS
- HTIF probe PASS
- printable full smoke PASS

Cycle profile：

- scalar QMLP：`168203 cycles_avg`
- RoCC `rqdot4` QMLP：`62532 cycles_avg`
- speedup：`speedup_x1000=2689`，约 `2.689x`
- counts：`rqdot4_avg=848`，`scalar_tail_macs_avg=64`，`rqscale8_avg=96`，packed MAC coverage `98.14%`

证据：[../../logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-board-status-2026-06-09.md](../../logs/radar_nexysvideo/runtime/xradar-dot4-2026-06-09/artifacts/xradar-rocc-board-status-2026-06-09.md)

## 当前边界

- RoCC RTL 只实现 `rqdot4`。
- `rqscale8` 仍是软件函数。
- `rqpack` 没有 RTL。
- `racc.*` 只是保留/规划方向，还未实现。
- 2.689x 是 QMLP kernel/profile 口径，不是完整 Feature21+QMLP 系统口径。
