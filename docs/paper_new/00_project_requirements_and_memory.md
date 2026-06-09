# 项目剖析要求与延续记忆

## 用户目标

本项目是研究生毕业课题，需要从工程可运行状态提升到“能彻底解释、能写论文、能画图、能答辩”的知识结构。后续优化仍然重要，但当前阶段优先做项目剖析和论文知识库。

## 内容要求

- 必须解释数据输入是什么、规格大小是什么、是否已经定型、数据类型和位宽是什么。
- 必须解释不同输入类型或不同处理路径是否有区分设计。
- 必须解释数据从输入到输出经过哪些步骤，每一步数据内容、类型、shape、位宽如何变化。
- 必须解释 RISC-V 自定义指令如何调度，尤其是 RoCC `rqdot4` 的指令编码、执行路径和板级验证边界。
- 必须解释整体数据流通路：CPU、DDR、DMA、Feature21、QMLP、RoCC 之间怎么连，为什么需要 TileLink、AXI4、AXI4-Lite、AXI4-Stream 等协议。
- 必须深入解释 Feature21 和 QMLP 内部细节：状态机、定点化、pipeline、关键寄存器、周期、吞吐、瓶颈和误差。
- 必须分析是否数据搬运足够快，是否让计算空拍，哪些 profile 可以支持该判断。
- 必须整理相关论文和类似架构对比，但不能用外部论文结论替代本项目证据。

## 写作和维护偏好

- 中文优先。英文仅用于专有名词、文件名、模块名、指令名和论文/工具名。
- 结论必须带证据路径；不写“感觉上更快”这种无法追踪的表述。
- 性能数字要标明口径：kernel、DMA timed interval、validation e2e、Feature21-only、QMLP-only、RoCC profile、full-chain 等不能混写。
- 当前 RoCC `2.689x` 只能写成 QMLP kernel/profile 加速，不能写成完整 Feature21+QMLP 端到端加速。
- 旧 `docs/paper/` 是历史材料；可以参考，但不能让过时结论覆盖 2026-06-09 后的 75 MHz/RoCC 证据。
- Obsidian 文件要使用 `[[WikiLink]]` 串主题，repo 文档要使用相对 Markdown 链接串证据。
- 图纸描述要尽量中文化，并保留 Visio COM 可读的 JSON 结构，方便 Windows 下自动画图。

## 固定入口

- Repo 事实源：`/home/soooarr/chipyard/docs/paper_new/README.md`
- Obsidian 主入口：`/home/soooarr/obsidian/项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md`
- Obsidian 辅助索引：`/home/soooarr/obsidian/Codex/Chipyard/Chipyard Index.md`
- 项目专用 skill：`/home/soooarr/.codex/skills/radar-paper-knowledge/SKILL.md`

## 后续窗口规则

1. 先读 `docs/paper_new/README.md`，再按任务进入对应章节。
2. 写论文或答辩材料时，先查 `08_performance_timing_evidence.md`，避免用旧数字。
3. 讨论 RoCC 时必须记住：当前 RTL 只实现 `rqdot4`；`rqscale8`、`rqpack`、`racc.*` 未实现。
4. 讨论板级测试时默认 `/dev/ttyUSB0`、`115200`、每个 fresh ELF 前按 `CPU_RESET`。
5. 更新 repo 文档后，同步 Obsidian 镜像入口或主题页；至少更新主入口的“最近更新”。
6. 新增图时同时维护 `pic/*.visio.json` 和 `pic/architecture_diagrams.md`。
