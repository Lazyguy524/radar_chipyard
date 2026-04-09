# QMLP 阵列化原型 v2 bitstream 结果摘要

更新时间：2026-04-07

对应日志：

- [250-fpga-bitstream-qmlp-pe-array-v2-2026-04-06.log](/home/soooarr/chipyard/logs/radar_nexysvideo/runtime/250-fpga-bitstream-qmlp-pe-array-v2-2026-04-06.log)

关键结论：

- `QMLP PE array v2` 的 `Nexys Video` bitstream 已生成成功
- 路由阶段明确报出 `The design met the timing requirement`
- 最终 `timing.txt` 明确写出 `All user specified timing constraints are met`

结论判定：

- 这版已经从 `v1` 的严重时序违例，收敛到 **50 MHz 可实现、可烧录** 的状态
- 当前可进入下一阶段：
  1. 板级回归确认老链路未回退
  2. 跑 `QMLP` 多样本对拍
  3. 对比 `RUN_CYCLES`，验证阵列化是否真正带来周期下降
