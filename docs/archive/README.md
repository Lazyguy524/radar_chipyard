# Docs 归档说明

更新时间：2026-04-09

本文档用于说明 `docs/archive/` 的用途，以及当前哪些文档被归档、哪些文档仍建议保留在 `docs/` 根目录。

---

## 1. 为什么新增 archive

随着项目推进，`docs/` 根目录里同时堆积了：

- 当前主线文档
- 早期 bring-up 记录
- 中间阶段方案
- 已被后续版本覆盖的阶段总结

这些文件都保留是有价值的，但全部平铺在一个目录下，会让“当前最重要的内容”很难快速找到。

因此本次整理采用的原则是：

- **不删除旧文档**
- **把阶段性、过渡性、已被后续主文档覆盖的内容移入 `docs/archive/`**
- **把当前主线最重要的文档保留在 `docs/` 根目录**

---

## 2. 当前建议优先看的主文档

如果只想快速了解项目当前状态，优先看：

1. [radar_project_status_index_2026-04-09.md](/home/soooarr/chipyard/docs/radar_project_status_index_2026-04-09.md)
2. [radar_soc_progress_report_2026-04-05.md](/home/soooarr/chipyard/docs/radar_soc_progress_report_2026-04-05.md)
3. [radar_nexysvideo_qmlp_accelerator_2026-04-06.md](/home/soooarr/chipyard/docs/radar_nexysvideo_qmlp_accelerator_2026-04-06.md)
4. [radar_qmlp_pe_array_prototype_2026-04-06.md](/home/soooarr/chipyard/docs/radar_qmlp_pe_array_prototype_2026-04-06.md)
5. [radar_nn_accel_dataflow_research_report_2026-04-06.md](/home/soooarr/chipyard/docs/radar_nn_accel_dataflow_research_report_2026-04-06.md)
6. [radar_cpu_upgrade_research_report_2026-04-07.md](/home/soooarr/chipyard/docs/radar_cpu_upgrade_research_report_2026-04-07.md)

---

## 3. 本次归档内容

### 3.1 `archive/radar_history/`

这一组主要是：

- bring-up 早期说明
- 中间阶段方案
- 被后续主线文档覆盖的阶段总结
- 仍然有参考价值，但不是当前第一入口的说明文档

当前已归档文件：

- [radar_nexysvideo_bringup_2026-03-26.md](/home/soooarr/chipyard/docs/archive/radar_history/radar_nexysvideo_bringup_2026-03-26.md)
- [radar_nexysvideo_current_system_guide_2026-03-31.md](/home/soooarr/chipyard/docs/archive/radar_history/radar_nexysvideo_current_system_guide_2026-03-31.md)
- [radar_nexysvideo_dma_consistency_plan_2026-03-31.md](/home/soooarr/chipyard/docs/archive/radar_history/radar_nexysvideo_dma_consistency_plan_2026-03-31.md)
- [radar_nexysvideo_integrated_regression_2026-03-31.md](/home/soooarr/chipyard/docs/archive/radar_history/radar_nexysvideo_integrated_regression_2026-03-31.md)
- [radar_nexysvideo_preproc_update_2026-04-02.md](/home/soooarr/chipyard/docs/archive/radar_history/radar_nexysvideo_preproc_update_2026-04-02.md)
- [radar_nexysvideo_progress_2026-03-25.md](/home/soooarr/chipyard/docs/archive/radar_history/radar_nexysvideo_progress_2026-03-25.md)
- [radar_nexysvideo_reproduction_guide_2026-03-31.md](/home/soooarr/chipyard/docs/archive/radar_history/radar_nexysvideo_reproduction_guide_2026-03-31.md)
- [radar_nexysvideo_status_2026-03-26.md](/home/soooarr/chipyard/docs/archive/radar_history/radar_nexysvideo_status_2026-03-26.md)
- [radar_nexysvideo_stream_preproc_2026-04-01.md](/home/soooarr/chipyard/docs/archive/radar_history/radar_nexysvideo_stream_preproc_2026-04-01.md)
- [radar_nexysvideo_submodule_patch_manifest_2026-03-31.md](/home/soooarr/chipyard/docs/archive/radar_history/radar_nexysvideo_submodule_patch_manifest_2026-03-31.md)

### 3.2 `archive/research_notes/`

这一组主要是：

- 被后续更完整研究报告覆盖的早期研究路线文档

当前已归档文件：

- [radar_nn_accel_three_paths_2026-04-06.md](/home/soooarr/chipyard/docs/archive/research_notes/radar_nn_accel_three_paths_2026-04-06.md)

---

## 4. 后续整理原则

后续如果继续新增文档，建议按下面规则：

- 当前主线、常查、会直接被引用的：留在 `docs/` 根目录
- 早期方案、阶段记录、已被覆盖的说明：移入 `docs/archive/`
- 如果某个主题后续明显会继续扩展，优先新增“总览/主线页”，不要一直叠加很多平级说明

---

## 5. 一句话说明

当前 `docs/` 根目录保留的是“现在最重要、最常用、最适合作为入口”的文档；  
`docs/archive/` 保留的是“仍然有价值，但不应继续占据主目录”的阶段性材料。
