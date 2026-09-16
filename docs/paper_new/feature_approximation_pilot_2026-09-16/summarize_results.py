#!/usr/bin/env python3
"""Read completed outputs once, summarize scopes and preserve execution records."""
import csv
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOG=ROOT/'logs/feature_approximation_pilot_20260916'
LABELS={'software_reference':'软件统计参考','exact_quantized_input':'Q8.8 输入＋准确统计',
    'exact_stats_hardware_quantizer':'准确统计＋硬件输出量化','deployment':'当前部署镜像',
    'mean_corrected':'均值修正','eigen_slots_exact':'协方差槽位修正','std_slots_exact':'标准差槽位修正',
    'angle_slot_exact':'方位角槽位修正','range_slots_exact':'距离槽位修正','mean_eigen_corrected':'均值＋协方差槽位修正'}


def main():
    d=json.loads((LOG/'full/summary.json').read_text())
    tpath=LOG/'training/summary.json'
    t=json.loads(tpath.read_text()) if tpath.exists() else None
    base=d['metrics']['deployment']['macro_f1']
    lines=['# 有约束的真实数据试验结果','',
        '2026-09-16。以下均为本地离线计算；固定旧整数模型诊断与重新训练的 FP32 表示对照分表报告，不能混成新硬件精度。历史 test 未参与新候选评价或选择。','',
        '## 1. 固定旧模型：完整 validation','',
        f"共 {d['samples']:,} 条、{d['sequences']} 个序列，保持原 K7。原始数据恢复核对、C/Python 特征及独立整数推理检查均通过。",'',
        '| 模式 | Macro-F1（%） | 相对部署镜像（百分点） | 新增错误 | 修复错误 | ≥100样本序列：改善/退化 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name,v in d['metrics'].items():
        lines.append(f"| {LABELS[name]} | {v['macro_f1']*100:.4f} | {(v['macro_f1']-base)*100:+.4f} | {v['harm_vs_deployment']} | {v['repair_vs_deployment']} | {v['positive_sequences_at_least_100_samples']}/{v['negative_sequences_at_least_100_samples']} |")
    lines += ['', '新增错误指部署镜像原本正确、干预后错误；修复错误指反方向变化。二者都依真实标签判断，不是与软件预测的一致率。',
        '', '准确输入统计与原软件参考非常接近；当前观察主要指向统计/算式替换及模型适配，不能用这次结果证明“提高输入位宽”有必要。','',
        '![固定模型诊断](diagnostic.png)','',
        '## 2. 条件差异与不确定性','',
        '| 干预 | 整序列配对 bootstrap 的 F1 变化 95% 区间（百分点） |',
        '| --- | --- |']
    for name in ['mean_corrected','eigen_slots_exact','std_slots_exact','mean_eigen_corrected']:
        lo,hi=d['metrics'][name]['paired_sequence_bootstrap_vs_deployment']['delta_macro_f1_percentile95']
        lines.append(f'| {LABELS[name]} | [{100*lo:+.4f}, {100*hi:+.4f}] |')
    lines += ['', '这些区间使用 2,000 次、以整序列为单位的配对重采样，没有多候选/筛选校正；只能作为探索性不确定性描述。不得称为独立最终显著性证据。','',
        '点数分档中的边界组：N=2^k 有 3,232 条，N=2^k+1 有 4,457 条，其余 72,761 条。仅修正均值时，准确率变化分别约 +0.031、+1.189、+0.294 个百分点；2^k 组仍可能因舍入差别出现极少变化。',
        '', '单独修正协方差在 N=65..128 的 8,842 条中反而降低准确率约 0.746 个百分点，而在细长组总体有益。类别、距离和序列分布可能混杂；不能由分组相关性断言点数本身就是原因。',
        '', '形状误差与均值误差的收益不完全相加。上述槽位替换只是冻结模型上的诊断，成本与物理共享依赖尚未实现。',
        '', '## 3. 有条件触发的匹配重训','']
    if t:
        lines += [f"按预定规则选择 `{t['selected_candidate']}`。训练从 113 个 train 序列各取最多 512 条，共 {t['train_samples']:,} 条；保持原始 K7 历史并核对软件特征。",'',
            '三种表示均使用 21→64→32→2 的 FP32 MLP，相同 seed 对应完全相同初始化与洗牌顺序，固定 20 epoch、相同优化器/预算。标准化和类别权重只由选中 train 计算，没有选择最佳 val checkpoint。',
            '', '**输入已经量化为 INT8，但权重/激活和输入标准化使用 FP32。这是表示可学习性的对照，不是部署 QAT 或上板模型。不能把本表与上一表直接计算“训练带来的净提升”。**','',
            '| 表示 | seed 7 Macro-F1（%） | seed 17 Macro-F1（%） | 两 seed 均值（%） |',
            '| --- | ---: | ---: | ---: |']
        for name,v in t['representation_metrics'].items():
            a,b=v['val_macro_f1_by_seed'];lines.append(f"| {LABELS[name]} | {a*100:.4f} | {b*100:.4f} | {v['mean_val_macro_f1']*100:.4f} |")
        lines += ['', '| 候选相对当前镜像 | F1 变化（百分点） | 整序列 95% 区间（百分点） |', '| --- | ---: | --- |']
        selected=[]
        for r in t['paired_comparisons']:
            if r['representation']!=t['selected_candidate']:continue
            selected.append(r);lo,hi=r['bootstrap']['delta_macro_f1_percentile95']
            lines.append(f"| seed {r['seed']} | {100*r['macro_f1_delta_vs_deployment']:+.4f} | [{100*lo:+.4f}, {100*hi:+.4f}] |")
        lines += ['', '![匹配重训](matched_training.png)','',
            '两个 seed 和受限训练子集不足以证明收敛或稳健优势；候选还是在本 validation 上选出的。这里检验固定旧模型的现象能否在匹配重训后保留，而非最终论文成绩。']
        robust=all(r['macro_f1_delta_vs_deployment']>0 and r['bootstrap']['delta_macro_f1_percentile95'][0]>0 for r in selected)
        conclusion=('本轮两个 seed 的候选差值与区间均支持正向差异，但仍有选择偏差和部署缺口。下一步可制定独立的冻结 QAT/全量训练协议；本轮预算在六次训练后结束。' if robust else
            '候选在匹配重训后未达到两个 seed 均有明确正向差异的状态。应保留机制发现，同时暂停据此增加硬件复杂度；优先把当前镜像的匹配训练与冻结整数导出做扎实。该判断不等于证明候选永远无效。')
        lines += ['', '## 4. 本轮决策','',conclusion,'',
            '本轮不再扩大 seed、模型或参数网格，也不开始 RTL 设计。后续研究仍应区分“可训练适配的偏差”和“确实丢失的判别信息”；先修正评价闭环，再决定是否值得付出硬件代价。']
    else:
        lines += ['未触发/未完成训练阶段；以 gate 和原始结果状态为准。']
    lines += ['', '## 5. 资源与证据','',
        f"固定模型全量诊断 {d['wall_seconds']:.2f} s。"]
    if t:
        prep=json.loads((LOG/'train_subset/reconstruction_summary.json').read_text())
        lines += [f"训练数据准备 {prep['wall_seconds']:.2f} s；六次训练及汇总 {t['wall_seconds']:.2f} s。均未超过预定阶段上限，GPU 作业为 0。"]
    lines += ['', '- [冻结执行计划](plan.json)与[执行前评审](01_执行边界与评审.md)。',
        '- [完整固定模型结果](../../../logs/feature_approximation_pilot_20260916/full/summary.json)。',
        '- [分组结果 CSV](../../../logs/feature_approximation_pilot_20260916/full/group_metrics.csv)与[序列结果 CSV](../../../logs/feature_approximation_pilot_20260916/full/sequence_metrics.csv)。']
    if t:lines.append('- [匹配训练结果](../../../logs/feature_approximation_pilot_20260916/training/summary.json)；每个模型的曲线、checkpoint 与 validation logits 均保存在同目录。')
    lines += ['', '原权重、RTL、ELF、bitstream 保留；旧硬件正确性证据仍按原口径有效。本轮没有测量面积、时延或能耗，不能绘制真实质量—硬件成本 Pareto 前沿。','']
    (HERE/'02_试验结果与决策.md').write_text('\n'.join(lines))
    execution=LOG/'execution';execution.mkdir(exist_ok=True)
    for name in ['smoke','full','prepare','training']:
        source=Path('/tmp')/('feature_approx_pilot_'+name+'_20260916.log')
        if source.exists():shutil.copyfile(source,execution/(name+'.log'))
    readme='''# 雷达近似特征：有约束的真实数据试验

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
'''
    (HERE/'README.md').write_text(readme)
    print(json.dumps(dict(status='REPORT_WRITTEN',training=t is not None)))


if __name__=='__main__':main()
