# 2026-06-07 周报素材：Feature21/QMLP 75 MHz 收口与 Xradar Phase 0

## 一句话主线

本周把 Feature21 + QMLP 的频率工作从“单点调时序”收敛为两类可复用成果：一是 75 MHz timing-clean 候选已经归档，最终限制转移到 Rocket 前端/核心路径；二是启动 Xradar/RISC-V core co-design 的 Phase 0 baseline gate，用本地证据约束后续自定义指令、RoCC 控制路径和 Gemmini 对照实验，避免论文中出现未经测量的速度或资源结论。

## 可放进周报的工作内容

### 1. 75 MHz timing closure 归档

- 完成 Feature21 + QMLP 75 MHz 候选 bitstream/timing 归档。
- 当前 promoted 75 MHz 结果：
  - WNS `+0.040 ns`
  - TNS `0.000 ns`
  - WHS `+0.017 ns`
  - setup/hold failing endpoints 均为 `0`
- 最终 worst path 已经不是 QMLP、Feature21 普通量化写回或 UART-TSI TL-A 路径，而是 Rocket frontend/icache/fetch-queue/control 到 execute decode 的 route-dominated path。
- 对 FullChain v2 后续优化的经验已经单独整理：需要先识别 path class，再做结构性 pipeline；post-route physopt 只能作为 finishing tool。

证据文档：

- `docs/feature21_qmlp_frequency_limit_2026-06-02/75mhz_timing_closure_report_for_fullchain_v2_2026-06-06.md`
- `docs/feature21_qmlp_frequency_limit_2026-06-02/rolling_summary.md`

### 2. 有效/无效时序优化的边界

本周确认有效的 timing cuts：

- UART-TSI / FBUS：
  - 加 `TLBuffer(BufferParams.pipe)` 边界。
  - 在 `TSIToTileLink` 内部增加 TL-A request staging。
- QMLP：
  - 将每层 MAC 拆成 `Load -> Prep -> Mac`。
  - 注册 activation lanes、weight lanes、bias stage。
  - 将 requant shift-add 改为 balanced fixed-width sum。
- Feature21：
  - 将 feature byte generation 拆成 select、quant multiply、round/clamp、writeback。
  - 对 density quant product 单独加寄存。

也确认了一些不值得继续追的方向：

- 更深的 density DSP pipeline 试验没有改善 75 MHz，且引入/转移了 DRC 风险，已回退。
- 多轮 post-place route/physopt directive 探索没有把 WNS 从 `+0.040 ns` 推到 `+0.100 ns`；继续纯 directive sweep 收益很低。

### 3. Xradar / RISC-V core optimization plan

为了避免论文里 SoC/core 部分被理解成“只是用了 Rocket”，本周提出新的研究主线：

> 面向 radar Feature21 + QMLP workload 的轻量 RISC-V ISA/core/accelerator coupling-point exploration。

候选方向：

- `rq*` arithmetic/data custom instructions：
  - `rqdot4`
  - `rqmac4`
  - `rqscale8`
  - `rqpack`
- `racc.*` accelerator-control custom instructions：
  - `racc.cfg`
  - `racc.start`
  - `racc.wait`
  - `racc.stat`
- 初期优先通过 RoCC/custom opcode prototype 验证；只有在 profile 证明收益足够时，再考虑迁移到 Rocket execute-stage。

计划文档：

- `docs/riscv_core_feature21_qmlp_optimization_plan_2026-06-06.md`

### 4. Phase 0 baseline gate 已经建立

新增 Phase 0 baseline gate 文档，重点不是宣称完成优化，而是把后续 go/no-go 判断口径固定下来。

当前已经有的证据：

- CPU-only QMLP 历史板测总周期：
  - `avg_cycles=165343`
  - `min=165204`
  - `max=165500`
- 当前 QMLP DMA profile：
  - `batch=1`: `prep=1148`, `ctrl=60`, `dma=1622`, `verify=247`, `hw=1301` cycles/sample
  - `batch=511`: `prep=1142`, `ctrl=0`, `dma=1306`, `verify=88`, `hw=1301`
- 75 MHz radar config 资源：
  - top `NexysVideoHarness`: 29815 LUT, 19222 FF, 2 RAMB36, 14 RAMB18, 12 DSP
  - `feature21`: 2470 LUT, 1210 FF, 2 DSP
  - `qmlp`: 2468 LUT, 1580 FF, 0 DSP
- Gemmini 本地证据：
  - `RadarNexysVideoConfig` 包含 `gemmini.LeanGemminiConfig`
  - generated `Gemmini.sv` 存在
  - 旧 `fpga/deliverables/v1_rocket_gemmini/NexysVideoHarness.bit` 存在

当前不能夸大的地方：

- CPU-only QMLP 只有 total cycles，dot/MAC、quant/relu、control/residual share 还没有板测。
- `ctrl_avg=60` 只代表 QMLP idle/clear/enable control，不等价于完整 accelerator control overhead。
- `dma_avg` 内部还混有 DMA MMIO setup 和 MM2S/S2MM polling，必须拆开后才能判断 `racc.*` 是否值得做。
- Feature21 + QMLP chain 的现有 cycle 证据包含 bypass-chain/软件 QMLP 口径，不能写成完整 raw-point Feature21 硬件全链路 baseline。
- Gemmini 只能说“本地配置/生成物/旧 bitstream 证据存在”，不能说它在 Artix-7 上资源过大、时序不可行或一定不适合；缺少匹配的 timing/utilization report。

Phase 0 gate 文档：

- `docs/performance/radar_core_extension_baseline_2026-06-06.md`

## 当前 gate 状态

| Gate | 当前状态 | 下一步 |
| --- | --- | --- |
| `rqdot4` | 未决策 | 上板运行 `tests/radar-qmlp-cpu-profile.riscv`，测 dot/MAC share、quant/relu share 和 `rdinstret`。 |
| `racc.*` | 尚未通过实现 gate | 增加 MMIO read/write counter 与 polling iteration counter，拆分 `dma_avg` 内部 setup/polling。 |
| quantize/round/clamp helper | 待 profile | 如果 quant/relu 或 control/residual 超过 dot/MAC，再优先做 scale/clamp/pack 指令。 |
| Gemmini baseline | 部分证据 | 补 LeanGemmini NexysVideo timing/utilization report，或记录无法实施的具体原因。 |

## 周报里建议这样讲

建议不要把本周包装成“已经完成 RISC-V 自定义指令优化”。更稳的说法是：

> 本周完成了 Feature21 + QMLP 75 MHz timing-clean 版本的归档，并把后续 RISC-V core/ISA co-design 转入 Phase 0 evidence gate。当前已经建立 CPU-only QMLP、DMA/QMLP profile、75 MHz 资源/时序、Gemmini 配置与 workload-shape 的证据矩阵；下一步先补板级 profile 与 MMIO/polling instrumentation，再决定 `rqdot4`、`racc.*` 或 quant/pack helper 哪条路线进入实现。

如果需要放一页“下一步计划”，可以写：

1. 上板运行 `radar-qmlp-cpu-profile.riscv`，得到 dot/MAC、quant/relu、control/residual cycle share。
2. 给 QMLP DMA wrapper 增加 MMIO 访问计数与 polling 迭代计数，拆分当前 `dma_avg`。
3. 补 LeanGemmini 在 NexysVideo/Artix-7 上的 utilization/timing 证据，作为 dense-GEMM design-space endpoint。
4. 根据 Phase 0 gate 结果选择第一条实现路线：`rqdot4`、`rqscale8/rqpack` 或 `racc.*`。

## Obsidian 归档建议

可以把本文件作为 Obsidian vault 里的入口笔记，建议标题：

```text
2026-06-07 Feature21 QMLP Xradar Phase0 周报素材
```

建议 tags：

```text
#chipyard #feature21 #qmlp #xradar #riscv #weekly-report #phase0
```

建议链接关系：

- `[[Feature21 QMLP 75MHz Timing Closure]]`
- `[[Xradar Phase0 Baseline Gate]]`
- `[[Gemmini Baseline Evidence]]`
- `[[RISC-V Custom Instruction Plan]]`
- `[[Weekly Reports]]`

Codex 当前可以直接读写普通 Markdown 文件。如果 Obsidian vault 是本机目录，最稳的集成方式是把 vault 路径告诉 Codex，然后把这些文档复制或同步到 vault 中；Obsidian 会直接把它们当作笔记索引。当前 `/home/soooarr/.codex/config.toml` 里还没有 Obsidian MCP/connector 配置，所以暂时不能通过 Obsidian API 写笔记，但文件级集成已经足够可用。

