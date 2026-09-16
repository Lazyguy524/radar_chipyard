# 雷达近似特征：有约束的真实数据试验

2026-09-16。完成的阶段与结论见[试验结果与决策](02_试验结果与决策.md)。

- [执行预算与自评](01_执行边界与评审.md)、[冻结机器可读计划](plan.json)。
- [后续优先级与停止条件](03_后续优先级与停止条件.md)：匹配重训未显示稳定收益；补查量化后信息分布，暂停硬件扩展。
- [研究问题与文献](../feature_approximation_research_2026-09-16/README.md)。
- 432 条 smoke → 80,450 条完整 validation 固定模型诊断 → 达到预定门槛后才进行最多 6 次匹配训练。
- 历史 test 未用于新候选选择或评价。固定模型干预是离线整数诊断；新训练是 FP32 表示对照，不能声称为部署 QAT、板级性能或已成立的论文创新。

## 复现

以下命令使用现有环境；原输出目录非空时重建阶段拒绝覆盖。重跑需新建独立输出配置，不能删除原结果后覆盖。

```bash
timeout 600s env OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 /tmp/radar_training_audit_20260915/bin/python docs/paper_new/feature_approximation_pilot_2026-09-16/run_diagnostic.py --phase smoke
timeout 600s env OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 /tmp/radar_training_audit_20260915/bin/python docs/paper_new/feature_approximation_pilot_2026-09-16/run_diagnostic.py --phase full
timeout 600s env OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 /tmp/radar_training_audit_20260915/bin/python docs/paper_new/feature_approximation_pilot_2026-09-16/run_bounded_training.py --phase prepare
timeout 900s env OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 /tmp/radar_training_audit_20260915/bin/python docs/paper_new/feature_approximation_pilot_2026-09-16/run_bounded_training.py --phase train
```

`plan.json` 定义阶段门槛；没有达到门槛时训练入口自行停止。`plot_results.py` 仅从结果生成 PDF/PNG，使用 `/tmp/gemmini_qmlp_plot_venv_20260915/bin/python`。环境目前位于 `/tmp`，后续复现应按结果中的版本信息建立新环境。

原始证据位于 `logs/feature_approximation_pilot_20260916/`。`validation.json` 检查计划/源码、重建、整数校验和运行预算；Obsidian 状态见 `obsidian_sync_manifest.json`，云同步未验证。
