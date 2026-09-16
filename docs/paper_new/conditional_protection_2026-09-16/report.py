"""Generate results and reflection from frozen predictions, without selection."""
import csv
import json
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/conditional_protection_20260916';MECH=ROOT/'logs/mechanism_convergence_20260916'
def get(p):return json.loads(p.read_text())
def table(head,rows):return '\n'.join(['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def main():
    execution=get(LOG/'execution_summary.json');assert execution['status']=='PASS'
    a=get(MECH/'factorial_evaluation/summary.json');b=get(MECH/'augmentation_evaluation/summary.json');e=get(LOG/'evaluation/summary.json');t=get(LOG/'training/summary.json')
    configs=[('A 普通训练',a,'proxy','mode'),('B 扰动训练',b,'proxy','mode'),('C 正确判断保护',e,'clean_guard','method'),('D 保护＋分组约束',e,'group_guard','method')]
    conditions=['clean','uniform_quarter_0','central_half','kept_single','sparse_single','sparse_context']
    rows=[];csvrows=[]
    for name,source,mode,key in configs:
        values=[]
        for condition in conditions:
            sparse=condition.startswith('sparse');k='view' if sparse else 'condition'
            rs=[r for r in source['sparse_metrics' if sparse else 'metrics'] if r[key]==mode and r['seed'] in [7,17,37] and r[k]==condition]
            assert len(rs)==3;mean=statistics.mean(r['macro_f1']*100 for r in rs);std=statistics.stdev(r['macro_f1']*100 for r in rs)
            values.append(f'{mean:.4f} ± {std:.4f}');csvrows.append(dict(configuration=name,condition=condition,mean_f1_percent=mean,seed_std_pp=std))
        rows.append([name]+values)
    performance=table(['方案','原始 K7','均匀 1/4','中心 1/2','保留观测当前帧','过滤观测当前点','过滤观测＋历史'],rows)
    with (HERE/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
    sparse_sources={}
    for name,folder in [('A',MECH/'factorial_evaluation'),('B',MECH/'augmentation_evaluation'),('new',LOG/'evaluation')]:
        with (folder/'sparse_groups.csv').open() as f:sparse_sources[name]=list(csv.DictReader(f))
    groups=[]
    for axis,group in [('history','none'),('history','one_to_five'),('history','six'),('current_points','1'),('current_points','2'),('current_range','le20'),('current_range','20to40'),('current_range','gt40')]:
        vs=[]
        for source,key,mode in [('A','mode','proxy'),('B','mode','proxy'),('new','method','clean_guard'),('new','method','group_guard')]:
            rs=[r for r in sparse_sources[source] if r[key]==mode and int(r['seed']) in [7,17,37] and r['view']=='sparse_context' and r['axis']==axis and r['group']==group]
            assert len(rs)==3;vs.append(statistics.mean(float(r['macro_f1'])*100 for r in rs))
        groups.append([axis+':'+group,int(rs[0]['samples'])]+[f'{v:.4f}' for v in vs]+[f'{vs[2]-vs[0]:+.4f}',f'{vs[3]-vs[0]:+.4f}'])
    group_table=table(['自然少点组','观测数','A','B','C','D','C−A pp','D−A pp'],groups)
    decision_rows=[]
    for method in ['clean_guard','group_guard']:
        rs=[r for r in e['gates'] if r['method']==method];decision_rows.append([method,sum(r['accepted'] for r in rs),3,'通过' if e['method_accepted'][method] else '未通过'])
    gate_table=table(['方法','通过 seed','总 seed','方法门槛'],decision_rows)
    failures=[]
    for r in e['gates']:
        for f in r['failures']:
            failures.append([r['method'],r['seed'],f['gate'],f.get('condition',f.get('axis','')),f.get('group',''),f"{f['delta']*100:+.4f} pp" if 'delta' in f else f"new={f.get('new')}, B={f.get('baseline_B')}"])
    fail_table=table(['方法','seed','失败门槛','条件/轴','组','实际变化'],failures) if failures else '所有预设门槛通过。'
    flips=[]
    for source,mode,key,label in [(b,'proxy','mode','B'),(e,'clean_guard','method','C'),(e,'group_guard','method','D')]:
        for seed in [7,17,37]:
            import numpy as np
            y=np.load(MECH/'data/val/labels.npy');a_pred=np.load(MECH/'factorial_evaluation'/('proxy_seed%d_clean_prediction.npy'%seed))
            path=MECH/'augmentation_evaluation'/('proxy_seed%d_clean_prediction.npy'%seed) if label=='B' else LOG/'evaluation'/('%s_seed%d_clean_prediction.npy'%(mode,seed))
            pred=np.load(path);harm=int(((a_pred==y)&(pred!=y)).sum());repair=int(((a_pred!=y)&(pred==y)).sum())
            flips.append([label,seed,harm,repair,f'{harm/len(y)*100:.4f}%'])
    flip_table=table(['方案','seed','原对→新错','原错→新对','负翻转/全部观测'],flips)
    accepted=[k for k,v in e['method_accepted'].items() if v]
    decision=('本轮没有方法满足全部预设门槛，不推广替换旧模型。六条后按计划停止，保留 A 为基础参照、B 为有条件收益的增强对照；不追加系数或 seed 挽救假设。' if not accepted else '通过探索门槛的方法为 '+', '.join(accepted)+'；保留全部三个 seed 进入独立确认，尚不替代最终板测版本。')
    text=f'''# 条件保护训练：结果与反思

2026-09-16。**{decision}**

两种方法×三个 seed，共六条完整训练；每条 357,780 个 train 观测、20 FP32＋60 QAT，固定第 60 轮。学生每轮样本访问和更新次数与旧增强 B 一致；教师离线推理和额外损失计算另有开销。训练耗时 {t['wall_seconds']/60:.2f} 分钟，两个 CPU 线程，无 GPU/远端训练任务。

## 1. 同种子对照

{performance}

单位为开发 validation Macro-F1 %，相同 seed 7/17/37 的均值±样本标准差。前四列来自 80,450 个原保留观测，后两列来自 97,734 个历史过滤观测；跨列不是同一群体，不能把它们的差值当因果退化。新增模型没有训练自然过滤观测。

## 2. 保护是否覆盖原本受损的条件

{group_table}

全部是相同 sparse_context 观测、相同历史规则、共同三个 seed。预定保护的组为六个历史和距离≤20 m；全部支持充分组仍在门槛和原始 CSV 中保留。分组差异含类别/距离/历史相关因素，不证明其中单一变量的因果作用。

## 3. 总体分数之外，还看哪些旧错误被修复、新错误被引入

{flip_table}

“原”统一指同 seed 的 A 普通训练。负翻转和正翻转可能同时下降，意味着模型更接近旧边界，不能仅凭负翻转变少就称整体更好。旧教师只在 train 的 clean 且正确行施加约束，不能保证新数据不退步。

## 4. 按运行前门槛作决定

{gate_table}

{fail_table}

通过要求三个 seed 同时满足；不按平均值掩盖某个 seed 的失败。不通过是未满足探索门槛，并不自动证明统计显著更差。配对整序列 bootstrap 和每个类别指标见[完整评价](../../../logs/conditional_protection_20260916/evaluation/summary.json)，没有对多重比较/长期验证域选择作校正。

## 5. 对论文主线的反馈

这轮检验的是“已有简单表示的条件回退能否通过训练约束修复”，它帮助判断复杂统计硬件是否必要，不应把论文改写为蒸馏算法论文。正确判断保护和组风险优化已有直接文献，不能当新数学方法。新的主张必须由雷达条件诊断、表示/精度选择、共享实现及同配置实测来支撑。

目前没有独立确认域：历史清单外五个序列的目标类别有轨迹点数均为 0，只有标签 ID 5/10/11，不能拿来评价车辆/行人任务。此次只查身份和标注，无模型打分，也没有新增使用历史 test。把熟悉数据重新命名成 test 不会补上这一缺口。[标注审计](../../../logs/conditional_protection_20260916/reserve_audit.json)

算法阶段继续遵守六条上限。新模型全部通过全量 C/NumPy/QAT 逐层检查，单遍特征前端＋整数分类器共 482,700 个模型/观测组合一致；实验执行通过与算法门槛通过是两种状态。没有新增 RTL、位流、板测，现有板卡资源余量与最终板测口径不变。

设计理由见[设计账本](00_设计账本与主线.md)，预算/公式见[运行前审查](01_计划与预检审查.md)。模型参数、预测、失败门槛和源码都保留，Git/归档状态见[备份与验证](04_备份与复现.md)。
'''
    (HERE/'02_结果与反思.md').write_text(text)
    readme=f'''# 条件保护训练与论文主线记录

2026-09-16。{decision}

本轮已完成两种受约束训练各三个 seed、完整验证/真实少点分组、负翻转检查，以及六个完整 C 候选。方案是已有正确判断蒸馏和组风险思想的对照应用，不声称原创训练算法。独立确认数据仍有缺口，最终硬件性能仍以上板实测为准。

建议阅读：

1. [结果与反思](02_结果与反思.md)：只看表 1、表 2 和预设门槛即可了解是否有效。
2. [设计账本与主线](00_设计账本与主线.md)：保存原问题、为什么试、风险、查重与每次决定。
3. [运行前计划审查](01_计划与预检审查.md)、[冻结计划](plan.json)、[主线约束](research_contract.json)。
4. [Git 备份与复现](04_备份与复现.md)、[审计](validation.json)、[证据清单](evidence_manifest.json)、[本地 Obsidian 同步](obsidian_sync_manifest.json)。
5. [三条补充文献 RIS](references.ris)、[六个独立 C 候选](candidate_c_bundle.zip)。

前一轮的 [35 条训练包](../mechanism_convergence_2026-09-16/README.md)保持原样。当前是验证既有简单表示上的改进必要性，不能自动改成“21 维最优”“所有场景稳健”或“已经获得板级能效优势”。
'''
    (HERE/'README.md').write_text(readme)
    print(json.dumps(dict(method_accepted=e['method_accepted'],report='02_结果与反思.md'),ensure_ascii=False))
if __name__=='__main__':main()
