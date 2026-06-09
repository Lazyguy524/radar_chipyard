# Paper 目录说明

> 2026-06-09 note: this directory is now historical/reference material. For the current thesis knowledge base, start from [../paper_new/README.md](/home/soooarr/chipyard/docs/paper_new/README.md). Use this directory for earlier survey/framework text, but refresh all performance, timing, Feature21, QMLP, and RoCC claims against `docs/paper_new/` before writing thesis text.

本目录用于存放：

- 论文调研报告
- 可直接写入论文正文的对比材料
- 与当前 `QMLP / PE / RISC-V SoC` 相关的参考文献总结

当前主入口：

- [radar_thesis_logic_gap_audit_2026-04-16.md](/home/soooarr/chipyard/docs/paper/radar_thesis_logic_gap_audit_2026-04-16.md)
- [radar_hardware_strict_review_2026-04-15.md](/home/soooarr/chipyard/docs/paper/radar_hardware_strict_review_2026-04-15.md)
- [radar_qmlp_edge_paper_survey_2026-04-09.md](/home/soooarr/chipyard/docs/paper/radar_qmlp_edge_paper_survey_2026-04-09.md)
- [radar_hardware_thesis_framework_2026-04-13.md](/home/soooarr/chipyard/docs/paper/radar_hardware_thesis_framework_2026-04-13.md)
- [radar_hardware_ppt_material_2026-04-14.md](/home/soooarr/chipyard/docs/paper/radar_hardware_ppt_material_2026-04-14.md)
- [radar_hardware_ppt_diagrams_2026-04-14.html](/home/soooarr/chipyard/docs/paper/radar_hardware_ppt_diagrams_2026-04-14.html)

历史硬件实现与论文硬件部分的旧基线：

- `k=7 + rcs21`
- `21 -> 64 -> 32 -> 2 INT8 QMLP`
- `4-lane PE`
- `1000` 组 large golden 与 `54` 组 boundary cases 板级通过

对应工程说明：

- [radar_qmlp_k7_backend_and_validation_2026-04-14.md](/home/soooarr/chipyard/docs/radar_qmlp_k7_backend_and_validation_2026-04-14.md)
