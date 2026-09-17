# PMU 计划、执行前模拟与 HPM4 实施记录

日期：2026-09-12。按用户授权顺序执行：**计划 → 独立审计 → Python 行为模拟与复核 → HPM4 实施 → 实际验证与实现审计**。本包接续 [PMU 难度与论文准备包](../pmu_thesis_readiness_2026-09-12/README.md)，新增事实以本包为准，前一包保留实施前的评估背景。

**本轮本地实施与验证已完成。** 独立 HPM4 配置、RV64 裸机采样接口、计数自检和 CPU 算法采样程序已经落地；参数测试、RTL 生成、软件编译、真实 Rocket 自检及 **32 帧完整算法校准通过**。新 FPGA bitstream 与独立布线后审计也已通过，副本见 [HPM4 候选交付包](../../../fpga/deliverables/radar_pmu_hpm4_20260912/README.md)。1000 帧 RTL 因实际运行成本主动停止，保留全量 ELF 供上板验证。本机未发现串口设备，没有执行板卡下载或板测。

## 1. 五分钟阅读

| 顺序 | 文件 | 需要掌握的内容 |
| --- | --- | --- |
| 1 分钟 | 本页 §2、§3 | 最终选择、已经增加的能力与使用边界 |
| 2 分钟 | [Python 结论](PYTHON_PREFLIGHT.md) §4–5 | 为什么先做观测，为什么暂不改等待策略 |
| 1 分钟 | [计划审计](PLAN_AUDIT.md) | 时钟 Tcl、CSR 恢复、精确计数窗口三个阻断项如何关闭 |
| 1 分钟 | [实现审计](IMPLEMENTATION_AUDIT.md) §4 | 哪些结果来自真实 RTL，哪些还缺实测 |

需要直接使用实验数据：读 [CPU_RESULTS.md](CPU_RESULTS.md) 和 [FPGA_RESULTS.md](FPGA_RESULTS.md)。

完整顺序和验收条件见 [PLAN.md](PLAN.md)。执行门槛在 [EXECUTION_GATE.json](EXECUTION_GATE.json)，门槛时刻的审计、计划和 Python summary 原文保存在 `gate_snapshot/`；之后追加的实现结论不冒充事先批准。

最终分层状态见 [EXECUTION_SUMMARY.json](EXECUTION_SUMMARY.json)。G4 独立审计已通过，没有未关闭的实现阻断项；这一定义包含本地 CPU32/FPGA 验证及明确保留的板卡验证边界。

## 2. Python 模拟改变了什么决定

执行前已通过 **13 组自检、21 个 PM 策略窗口、1458 个等待策略扫描**。独立审计重新运行后，主要输出与归档逐字节一致。其作用是检查事件、计时和恢复语义，发现可检验的参数范围；没有用 Python 预测 FPGA 资源、真实唤醒代价或节能百分比。

- **实施 HPM4。** 四个 slot 足以先观察 load、store、D$ blocked 和 D$ miss，服务 CPU 算法成本归因。
- **保留现有 EMA 门控与 IRQ/WFI。** 连续任务没有自然休眠空间；公共窗口末尾的空闲不能算连续推理收益。
- **混合等待留作有条件实验。** 243 个假设负载/成本组合中，141 个存在某个预算在 CPU 活跃量和 p95 两项上不差于直接 WFI、且至少一项更好；这不是现实成功概率。真正选预算前要测 service/poll/IRQ 成本。
- **拒绝错误时间口径。** 模型复现了用 WFI 中停增的 `mcycle` 得到虚假加速，以及 mtime 量化、32 bit 饱和、累计计数分母错误。

模型输入、假设和负例见 [PYTHON_PREFLIGHT.md](PYTHON_PREFLIGHT.md)，可复算数据见 [preflight/summary.json](preflight/summary.json)。

汇报时可直接用 [两面板模型图与图注](figures/README.md)，提供 SVG、PNG、PDF。图中同时显示连续任务的开钟率均为 1，以及代表成本下 hybrid16 对长任务增加 CPU 开销、对混合任务可能减少开销；两者都不是功耗实测。

## 3. 已实现的最小增量

| 内容 | 新入口 | 实现范围 |
| --- | --- | --- |
| FPGA 配置 | [Configs.scala](../../../fpga/src/main/scala/nexysvideo/Configs.scala) 中 `RadarAXIMMIOWide23QMLP8DualGatedRocketWFIHPM4IRQNexysVideo50MHzConfig` | 独立 FULL/HPM4 名称；现有 Small Rocket 加四个 HPM，其余 tile 参数由测试确认保持；[Makefile](../../../fpga/Makefile) 同时接入 FULL dual-root 时钟 Tcl |
| CPU 仿真配置 | 同文件 `RadarAXIMMIOHPM4SimConfig` | CPU、cache 和 clock-gating 参数与候选 FPGA 对齐；外部采用 TestHarness/SimDRAM，不代表 FPGA 的 Wide23 DMA 系统 |
| 采样接口 | [radar_pmu.h](../../../tests/radar_pmu.h)、[radar_pmu.c](../../../tests/radar_pmu.c) | M-mode、RV64、单 hart 独占；保存/恢复 HPM3–6、selector、inhibit，MIE 最后按位恢复；拒绝嵌套和非法 selector |
| 计数校准 | [radar-pmu-selftest.c](../../../tests/radar-pmu-selftest.c) | 8 load/4 store 单汇编窗口、OR、40 bit 回卷、zero event、单 slot inhibit、空窗、非零状态/MIE=1 恢复 |
| CPU 实际算法 | [radar-pmu-cpu-profile.c](../../../tests/radar-pmu-cpu-profile.c) | 复用原 Feature21 exact-LUT mirror、QMLP 和冻结 board-logit oracle；独立 32/1000 样本 ELF；warmup、空窗和三种阶段窗口 |
| 可复现执行 | [build_pmu_candidate.py](../../../scripts/radar_delivery/build_pmu_candidate.py)、[run_pmu_simulation.py](../../../scripts/radar_delivery/run_pmu_simulation.py) | 新 attempt 目录、命令数组、日志和 SHA；构建先检查审计门槛；不连接板卡 |

第一版事件编码来自本仓库 Rocket：load=`0x0200`、store=`0x0400`、D$ blocked=`0x1001`、D$ miss=`0x0202`。这不是跨 RISC-V 核统一事件 ABI。同组多位表示 OR，HPM 物理宽度为 40 bit，硬件没有为这些附加 counter 提供 reset 初始化，因此采样前显式清零。

接口会在独占 session 内暂停窗外的基础计数，并临时关闭 MIE；`mcycle/minstret` 不清零、不回写过去数值。它用于无 WFI 的纯 CPU 窗口，不能放进 ISR 或直接套在 IRQ/WFI 等待流程，也不能在 session 内依赖暂停的 rdcycle 做超时。

## 4. 当前验证记录

| 验证层 | 状态 | 原始证据 |
| --- | --- | --- |
| G0 计划审计、G1 Python 模拟及复核 | PASS | [PLAN_AUDIT.md](PLAN_AUDIT.md)、[PYTHON_PREFLIGHT.md](PYTHON_PREFLIGHT.md) |
| Scala 参数检查 | 3/3 PASS | [测试与 assembly 日志](../../../logs/radar_pmu/2026-09-12/config-test-and-assembly-attempt2.log) |
| RV64 编译与反汇编 | 三个 ELF PASS | [软件身份记录](../../../logs/radar_pmu/2026-09-12/software-build-manifest.json) |
| 新 FPGA RTL 生成、Verilator 构建 | BUILD_PASS | [RTL](../../../logs/radar_pmu/2026-09-12/rtl-attempt1/result.json)、[simulator](../../../logs/radar_pmu/2026-09-12/simulator-attempt1/result.json) |
| HPM4 真实 Rocket 自检 | PASS，failures=0 | [原始日志](../../../logs/radar_pmu/2026-09-12/selftest-attempt1/simulation.log) |
| 旧 HPM0 真实 Rocket 负对照 | PASS，目标返回 UNSUPPORTED/exit 2 | [最终严格判定](../../../logs/radar_pmu/2026-09-12/negative-attempt3/result.json) |
| FPGA bitstream 与独立 post-route 审计 | PASS，已约束 setup/hold 满足 | [FPGA_RESULTS.md](FPGA_RESULTS.md)：WNS `0.894 ns`、WHS `0.016 ns`，4 门/1 专用 root；外部 I/O 边界保留 |
| CPU 算法 RTL | PASS，32 帧；warmup/QMLP/fullchain logits 均 0 mismatch | [CPU_RESULTS.md](CPU_RESULTS.md)、[8 个原始窗口 CSV](cpu_rtl_results/raw_windows.csv) |
| G4 实现与结果独立审计 | PASS；独立复算 CPU CSV/JSON 逐字节一致 | [IMPLEMENTATION_AUDIT.md](IMPLEMENTATION_AUDIT.md) |
| 1000 帧全量 RTL | 主动停止，NOT_PASS；ELF 保留供上板全量验证 | [停止请求与实测耗时依据](../../../logs/radar_pmu/2026-09-12/full-attempt1/stop_request.json)、[实际停止结果](../../../logs/radar_pmu/2026-09-12/full-attempt1/stop_result.json) |
| 新镜像板测、外部功耗、新 ASIC | NOT_RUN | [环境检测](../../../logs/radar_pmu/2026-09-12/environment.json) 未发现串口设备 |

真实自检得到 load/store/OR=`8/4/12`，40 bit 回卷结果 `4`；五个空窗为 `137/43/43/43/43 cycles`、均 `27 instret` 与 `2 load`。这说明首次窗口的开销不同，不能使用统一常数扣减所有窗口。

CPU profile 的 Feature21、QMLP、fullchain 是不同缓存历史下的三次完整子集窗口，均包含循环、输出存储和接口开销；不是同一次执行的可加分段。D$ 事件来自 CPU cache，不能解释成 DMA 字节数。仿真日志的 CPU clock 为 500 MHz、DRAM clock 约 666.7 MHz；候选 FPGA 为 50 MHz，**不能把仿真 cycle 除以 50 MHz 得到板上时间**。

32 帧 smoke 取原 1000 帧子集的前缀，标签均为 0（pedestrian）；只校准观测路径和算法 oracle 一致性，不是类别均衡的评价集，也不报告分类 accuracy 或总体平均性能。1000 帧独立 ELF 保留完整子集入口。

保留的失败尝试包括：Scala 首次错误 import；负对照脚本首次误把目标退出码等同宿主退出码。修正后分别重跑通过。有限周期的 trace 诊断以预定 timeout 结束，仅用于确认算法在运行，不列入功能 PASS。

32 帧三个算法窗的 cycle 分别为 Feature21=`90898`、QMLP=`5111917`、fullchain=`5209726`；完整 load/store/cache 计数见结果表。本机完成该 RTL 校准用时约 38.70 分钟。1000 帧受控停止的原 runner 保留 FAIL：仿真器经停止通道返回 0，但没有目标 PASS，因而没有误判成通过。

## 5. 复现与论文使用

在仓库根目录，先复现模型，再编译独立软件：

```bash
python3 -B scripts/analysis/radar_pmu_preflight.py --out /tmp/radar-pmu-review-new --seed 20260912
PATH="$PWD/.conda-env/riscv-tools/bin:$PATH" make -C tests radar-pmu-binaries
python3 -B scripts/radar_delivery/run_pmu_simulation.py --test selftest --out /tmp/radar-pmu-selftest-new
python3 -B scripts/radar_delivery/run_pmu_simulation.py --test negative --out /tmp/radar-pmu-negative-new
python3 -B scripts/radar_delivery/run_pmu_simulation.py --test smoke --out /tmp/radar-pmu-smoke-new
```

上述路径应为新目录；模拟器必须已按本包独立配置构建。完整 generator/JAR、RTL、FPGA 和运行命令见 [REPRODUCE.md](REPRODUCE.md) 以及各 attempt 的 `command.json`，运行结果在 `result.json`。板卡的身份核对、下载和原 DMA/IRQ/WFI 回归顺序见 [BOARD_RUNBOOK.md](BOARD_RUNBOOK.md)。

这项工作适合写进第 4 章“性能观测机制与事件语义”和第 5 章“计数校准及 CPU 开销分析”，与现有硬件加速、DMA 集成和门控主线相连。贡献表述应是**针对本系统建立经校准、可恢复的观测与实验方法**；启用 Rocket 已有 HPM 不单独宣称新 PMU 架构或 ISA 创新。代表文献与阅读顺序继续采用 [相关工作阅读表](../pmu_thesis_readiness_2026-09-12/03_related_work_reading.md) 和 [BibTeX](../pmu_thesis_readiness_2026-09-12/references.bib)。

可用于初稿的技术段落与证据对应表见 [THESIS_INSERT.md](THESIS_INSERT.md)，正式成稿时与导师确定的研究问题、学校模板和最终实验状态对齐。

既有 `75.76x`、IRQ/WFI 功耗变化、r5k/r4 ASIC 数据仍属于各自冻结设计。新增 HPM4 后不能直接沿用其性能/功耗结论；ASIC 既有数据始终限于 `DIGITAL_CORE / PRE_DFT / PRE_LAYOUT_NO_SPEF / GENERIC_CACHE_MEMORY / SIGNOFF=NO`。

改动范围可按 [implementation.patch](../../../logs/radar_pmu/2026-09-12/implementation.patch) 审阅，它相对 G2 前工作树快照生成，不混入原有未提交改动。目标软件/模型输入及运行产物的归档身份见 [输入审计](../../../logs/radar_pmu/2026-09-12/ARCHIVAL_INPUT_AUDIT.md)、[最终核查](../../../logs/radar_pmu/2026-09-12/final-input-recheck.json)。
