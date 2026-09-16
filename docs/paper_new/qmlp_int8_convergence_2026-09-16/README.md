# 当前 Feature21 对应的冻结 INT8 QMLP 基线

2026-09-16。承接[上一轮受控试验](../feature_approximation_pilot_2026-09-16/README.md)。本轮重点是训练与整数导出闭环。

- 当前后续顺序：[先完成特征筛选与样本审计，RTL 后置](04_先完成特征筛选与样本审计.md)。已完成的 21 维基线不等于已经证明 21 维最优。
- [先读：结果与收敛判定](02_结果与收敛判定.md)。
- [计划、预算与部署契约](01_计划与部署契约.md)、[冻结计划](plan.json)。
- [执行审查与尚未解决的边界](03_审查与后续边界.md)。
- [训练曲线 PNG](convergence.png)、[可导出 PDF](convergence.pdf)。

本轮完成两个 seed 的完整训练、固定尺度 QAT 和离线逐层整数校验，提供独立 C/Scala 参数候选；旧 RTL 和 bitstream 未切换到新模型。validation 是开发评价，不能写成新独立测试或上板测量。

## 复现与运行

现有环境为 `/tmp/radar_training_audit_20260915/bin/python`（PyTorch 2.4.1+cpu、NumPy 1.26.4、h5py 3.11.0）。完整执行顺序为 `preflight.py → prepare.py → train.py → verify.py`，分别以 60/600/900/600 s 的 `timeout` 启动。输出目录已冻结；重新训练需创建独立目录和计划，不能删除或覆盖本轮证据。绘图使用 `/tmp/gemmini_qmlp_plot_venv_20260915/bin/python plot_results.py`。

已有候选可以只做离线推理，例如在仓库根目录：

```bash
/tmp/radar_training_audit_20260915/bin/python docs/paper_new/qmlp_int8_convergence_2026-09-16/run_candidate.py --seed 7 --input logs/feature_approximation_pilot_20260916/full/deployment.npy --output /tmp/qmlp_seed7_new_logits.npy
```

输出路径必须不存在。输入必须已经是当前 Feature21 镜像的 INT8 特征；不能直接把浮点统计量或标准化特征传入。本入口仅调用已编译的本机 C 库，不执行训练或上板。

事实源为 `logs/qmlp_int8_convergence_20260916/`；包完整性见 `validation.json`，本地 Obsidian 状态见 `obsidian_sync_manifest.json`，云端同步未验证。
