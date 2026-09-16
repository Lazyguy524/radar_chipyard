"""Post-result group interpretation; no model, thresholds or data are changed."""
import csv
import json
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
LOG=ROOT/'logs/mechanism_convergence_20260916';SEEDS=[7,17,37]
def read(path):
    with path.open() as f:return list(csv.DictReader(f))
def table(head,rows):
    return '\n'.join(['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def main():
    result=[];sources={}
    for stage in ['factorial','augmentation']:
        sources[stage]=read(LOG/(stage+'_evaluation')/'sparse_groups.csv')
    for axis in ['history','current_points','current_range']:
        names=list(dict.fromkeys(r['group'] for r in sources['factorial'] if r['axis']==axis))
        for group in names:
            pair=[]
            for stage in ['factorial','augmentation']:
                rows=[r for r in sources[stage] if r['view']=='sparse_context' and r['mode']=='proxy' and int(r['seed']) in SEEDS and r['axis']==axis and r['group']==group]
                assert len(rows)==3 and all(r['supported']=='True' for r in rows)
                pair.append(statistics.mean(float(r['macro_f1'])*100 for r in rows))
            result.append(dict(axis=axis,group=group,samples=int(rows[0]['samples']),A_f1=pair[0],B_f1=pair[1],delta_pp=pair[1]-pair[0]))
    data=[]
    for stage in ['factorial','augmentation']:
        rows=read(LOG/(stage+'_evaluation')/'conditional_groups.csv')
        for mode in ['proxy','mean','moment']:
            for condition in ['uniform_half_0','central_half']:
                for group in ['elongated','intermediate','compact']:
                    subset=[r for r in rows if r['mode']==mode and int(r['seed']) in SEEDS and r['condition']==condition and r['axis']=='original_shape' and r['group']==group]
                    assert len(subset)==3 and all(r['supported']=='True' for r in subset)
                    data.append(dict(stage=stage,mode=mode,condition=condition,group=group,samples=int(subset[0]['samples']),macro_f1=statistics.mean(float(r['macro_f1'])*100 for r in subset)))
    repeat=[]
    a=json.loads((LOG/'factorial_evaluation/summary.json').read_text());b=json.loads((LOG/'augmentation_evaluation/summary.json').read_text())
    for condition in ['clean']+['uniform_'+fraction+'_'+str(i) for fraction in ['half','quarter'] for i in range(3)]+['central_half','xy_fraction6','xy_fraction4','kept_single']:
        pair=[[r for r in d['metrics'] if r['mode']=='proxy' and r['seed'] in SEEDS and r['condition']==condition] for d in [a,b]]
        vals=[statistics.mean(r['macro_f1']*100 for r in group) for group in pair]
        positive=sum(next(r['macro_f1'] for r in pair[1] if r['seed']==s)>next(r['macro_f1'] for r in pair[0] if r['seed']==s) for s in SEEDS)
        repeat.append(dict(condition=condition,A_f1=vals[0],B_f1=vals[1],delta_pp=vals[1]-vals[0],positive_seeds=positive))
    for name,rows in [('natural_group_comparison.csv',result),('shape_condition_comparison.csv',data),('repeat_comparison.csv',repeat)]:
        with (HERE/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    t1=table(['条件轴','组','观测数','原代理 A','原代理＋扰动训练 B','变化 pp'],[[r['axis'],r['group'],r['samples'],f"{r['A_f1']:.4f}",f"{r['B_f1']:.4f}",f"{r['delta_pp']:+.4f}"] for r in result])
    t2=table(['输入条件','A','B','变化 pp','改善 seed 数/3'],[[r['condition'],f"{r['A_f1']:.4f}",f"{r['B_f1']:.4f}",f"{r['delta_pp']:+.4f}",r['positive_seeds']] for r in repeat])
    shape_rows=[]
    for stage in ['factorial','augmentation']:
        for mode in ['proxy','mean','moment']:
            for group in ['elongated','intermediate','compact']:
                r=[next(r for r in data if r['stage']==stage and r['mode']==mode and r['condition']==c and r['group']==group) for c in ['uniform_half_0','central_half']]
                shape_rows.append([stage,mode,group,r[0]['samples'],f"{r[0]['macro_f1']:.4f}",f"{r[1]['macro_f1']:.4f}",f"{r[1]['macro_f1']-r[0]['macro_f1']:+.4f}"])
    t3=table(['阶段','表示','原始形态','观测数','均匀一半','中心一半','中心−均匀 pp'],shape_rows)
    (HERE/'05_分组收益与回退.md').write_text('''# 改善发生在哪里，哪些组出现回退

这是训练结束后的解释性汇总；没有据此重新设分组阈值、筛数据、选 seed 或继续训练。全部表格使用相同的 seed 7/17/37，单位为 Macro-F1 % 的均值。表内差值均为同组配对比较；组之间类别比例、距离、历史等因素不同，不能作为单一因素的因果实验。

## 1. 自然少点的改善并非均匀分布

以下都是原来被过滤的 97,734 条观测，使用“原保留历史＋当前点”的同一输入规则。

'''+t1+'''

`none` 为没有原保留历史，`one_to_five` 为 1–5 个原保留观测，`six` 为六个历史观测；历史仅沿用旧流程，无时间到期。本次增强主要改善无历史、单点和较远距离的组，近距离与六历史组有回退。不能只用总体 F1 隐藏这些变化，也不能未经验证按本表指定一个距离阈值切换两个模型。

这意味着“同样只有一个当前点”并不等于相同输入质量：能否获得可靠历史同样关键。历史数量、时长、坐标对齐应成为后续确认协议的输入条件；当前结果不证明缓存越长越好。

## 2. 检查均匀减点的三个随机重复

'''+t2+'''

重复是同一批观测的不同删点视图，不能当成三份独立数据或扩大置信区间的样本量。坐标小数位下降在这里量级较小，不能外推到不同传感器分辨率或未补偿速度。

## 3. 相同保留点数，不同保留位置

中心一半与均匀一半对每个簇保留相同数量。下表的差异因而不仅是点数减少，还涉及哪些点被保留及由此形成的分布变化。它是受控输入扰动，不是经过雷达物理标定的遮挡。

'''+t3+'''

形态来自原始 K7 簇浮点协方差的特征值比：≤0.1 为细长、>0.5 为紧凑，其余为中间；该计算仅用于离线分组，没有偷偷加入待部署硬件。仍需报告支持充分的点数×形态交叉组，避免只报大组平均。

原始证据：[A 分组](../../../logs/mechanism_convergence_20260916/factorial_evaluation/conditional_groups.csv)、[B 分组](../../../logs/mechanism_convergence_20260916/augmentation_evaluation/conditional_groups.csv)、[A 少点](../../../logs/mechanism_convergence_20260916/factorial_evaluation/sparse_groups.csv)、[B 少点](../../../logs/mechanism_convergence_20260916/augmentation_evaluation/sparse_groups.csv)。本表由 [summarize_groups.py](summarize_groups.py) 生成。
''')
    print('Post-result conditional and repeat summaries written')
if __name__=='__main__':main()
