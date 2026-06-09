# 架构图说明

## 图 1：SoC 总体架构

目标：展示 CPU、DDR、DMA、Feature21、QMLP、RoCC 的相对位置。

必须出现：

- Rocket core
- TileLink/SoC bus
- AXI4 MMIO control bridge
- AXI DMA
- MIG/DDR
- AXI4-Stream Feature21
- AXI4-Stream QMLP
- Xradar RoCC
- UART-TSI

核心叙事：

```text
CPU 控制，DDR 存数据，DMA 搬运，AXI4-Stream 算子计算，RoCC 作为另一条指令级算术优化路径。
```

## 图 2：端到端数据流

目标：展示数据内容和类型变化。

必须出现：

```text
多帧融合点集 -> [x,y,doppler,rcs] -> Feature21 -> int8[21] -> QMLP 32B frame -> int8 hidden -> int32 logits[2]
```

需要标注：

- Feature21 output 是 21 个 int8，但 QMLP frame 是 32 B 对齐。
- QMLP output 是 8 B，包含两个 int32 logits。
- logits 不是 softmax/probability。

## 图 3：RoCC `rqdot4` 路径

目标：解释 `.insn r CUSTOM_0, 7, 0` 如何从 Rocket 到 RoCC，再写回 rd。

必须出现：

- `rs1/rs2` packed int8x4
- `funct3=7` -> `xd/xs1/xs2=1`
- RoCC command queue
- `sIdle -> sMul -> sSum -> sResp`
- sign-extend writeback
- 当前只实现 `rqdot4`

## 颜色建议

- 控制面：浅蓝
- 数据面：浅绿
- 存储：浅黄
- 自定义指令/RoCC：浅紫
- 验证/host：浅灰

颜色只是图形提示，不应让正文依赖颜色理解。
