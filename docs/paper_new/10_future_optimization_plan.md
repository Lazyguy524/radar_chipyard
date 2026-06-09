# 后续优化计划

## 优先级原则

后续优化应围绕论文可解释贡献和已有证据推进，而不是盲目扩功能。每个优化都要回答：

- 是否有明确瓶颈证据？
- 是否能板级验证？
- 是否能进入论文叙事？
- 是否会破坏当前 timing-clean baseline？

## P0：知识库与证据闭环

- 保持 `docs/paper_new/` 与 Obsidian 镜像同步。
- 每次新增测试结果，更新 [08_performance_timing_evidence.md](08_performance_timing_evidence.md)。
- 图纸先维护 Visio JSON，再生成图。
- 对旧 `docs/paper/` 的有用内容逐步迁移到本目录，保留历史路径。

## P1：Feature21/QMLP full-chain 证据

目标：获得真正的 board-side full hardware chain evidence。

候选工作：

- 使用 `QMLP_CTRL_CHAIN_PREPROC` 或已有 RTL 路由验证 raw/fused point -> Feature21 -> QMLP -> logits。
- 明确 input frame 格式、output logits、expected counters。
- 对比 exact-LUT mirror + QMLP logits/labels。

风险：

- 不能把 Feature21 dump + host QMLP 当作 full-chain。
- batch DMA candidate timing-clean，但新 bitstream board validation 仍需补。

## P2：RoCC dot4 后续

当前 `rqdot4` 已经证明 QMLP kernel/profile 约 `2.689x`。后续可以：

- 做更多输入 case/stress，验证连续 RoCC 指令和不同数据分布。
- 分析 `instret_avg` 增加但 cycles 降低的原因，解释 pipeline/等待/指令调度口径。
- 评估是否要把 `rqdot4` 从 RoCC 迁到更低延迟 execute-stage，但这会显著增加 Rocket 修改风险。

## P3：`rqscale8` / `rqpack`

当前 profile 仍有 `rqscale8_avg=96` 在软件中。可评估：

- `rqscale8`：`acc * multiplier`、round-nearest-even、ReLU、clamp。
- `rqpack`：帮助数据 packing，减少循环中的 bit manipulation/load overhead。

实现前要先补 cycle share 估计，避免实现后收益很小。

## P4：`racc.*` 控制路径

`racc.*` 目标是减少小 batch 下 MMIO/DMA setup/polling overhead。当前已有 QMLP MMIO/DMA polling profile，可用于判断是否值得做。

必须避免：

- 在没有完整小 batch control overhead 证据时直接实现。
- 把 `racc.*` 和 `rqdot4` 混成同一类优化。前者是 accelerator control coupling，后者是 arithmetic custom instruction。

## P5：数据搬运是否空拍

当前旧 QMLP profile 显示 batch=511 时 DMA stream interval 已接近 QMLP kernel，说明大 batch 下搬运不明显拖慢 QMLP。但 Feature21/full-chain 和 75 MHz 最新 bitstream 仍需要单独证明。

后续测试建议：

- QMLP batch sweep at 75 MHz。
- Feature21 batch DMA board validation。
- Full-chain counters：in/out beats、frame count、QMLP run cycles、DMA cycles、CPU prep cycles。

## P6：时序余量

当前 75 MHz slack 很薄。任何 RTL 新增都需要：

- 先跑 Verilog/synth/implementation。
- 关注 Rocket frontend/core path 是否又成为 limiter。
- 对 RoCC 算术新增 pipeline，避免一周期 DSP/response path。
- 保留 timing-fail artifact，因为它能作为论文工程过程和设计取舍证据。
