"""Reproducible full tables, conditional choice and plain Chinese findings."""
from dim_common import *

NAMES={'A':'旧A主基线','B':'旧B困难备选','base16':'旧16维','combined23':'旧23维',
 'core8':'8维基础量','proxy12':'12维代理量','distribution12':'12维速度/反射补充','combined15':'15维分布补充',
 'support17':'17维：16＋点数','support24':'24维：23＋点数','width28':'28维：加四分位宽度','asymmetry28':'28维：加分位不对称',
 'quantile32':'32维：两分位组','full36':'36维：再加中位位置','redundant36':'36维：仅重复旧输入'}
ORDER=['core8','proxy12','distribution12','combined15','base16','support17','combined23','support24','width28','asymmetry28','quantile32','full36','redundant36']

def main():
    e=json.loads((LOG/'evaluation/summary.json').read_text());t=json.loads((LOG/'training/summary.json').read_text());pkg=json.loads((LOG/'package/summary.json').read_text());raw=json.loads((LOG/'evaluation/metrics.json').read_text())
    m={(r['tag'],r['seed'],r['condition']):r for r in raw};intervals=readcsv(LOG/'evaluation/paired_sequence_intervals.csv')
    def mean(tag,c):return float(np.mean([m[(tag,s,c)]['macro_f1'] for s in SEEDS]))
    def score(tag,s):return previous.composite({c:m[(tag,s,c)]['macro_f1'] for c in CONDITIONS})
    def ci(tag,ref):return next(r for r in intervals if r['tag']==tag and r['reference']==ref and r['condition']=='composite' and r['seed']=='mean3')
    results=[];table=['| 方案 | 常规 | 均匀四分之一 | 中心一半 | 真少点当前帧 | 真少点加历史 | 综合 |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for tag in ['A','B']+ORDER:
        values=[mean(tag,'clean'),float(np.mean([mean(tag,'uniform_quarter_'+str(i)) for i in range(3)])),mean(tag,'central_half'),mean(tag,'sparse_single'),mean(tag,'sparse_context'),float(np.mean([score(tag,s) for s in SEEDS]))]
        row=dict(tag=tag,name=NAMES[tag],dim=21 if tag in ['A','B'] else len(take(tag)),clean=values[0],quarter=values[1],central=values[2],sparse_single=values[3],sparse_context=values[4],composite=values[5],**{'seed'+str(s):score(tag,s) for s in SEEDS})
        results.append(row);table.append('| '+NAMES[tag]+' | '+' | '.join(f'{100*v:.3f}' for v in values)+' |')
    writecsv(HERE/'results.csv',results);lookup={r['tag']:r for r in results}
    base_names=['点数','x代理均值','y代理均值','x跨度','y跨度','点距离代理最小值','点距离代理最大值','代理中心距离','原LUT密度代理','径向速度代理均值','径向速度离散代理（跨度右移2）','径向速度最小值','径向速度最大值','RCS代理均值','RCS离散代理（跨度右移2）','RCS最大值']
    names=base_names+PLAN['features']['geometry']+PLAN['features']['distribution']+PLAN['features']['new'];assert len(names)==36
    exponents,fractions=base.scales();dictionary=[]
    for i,name in enumerate(names):
        dictionary.append(dict(canonical_column=i,stable_feature_id=COLS[i] if i<16 else i+5,name=name,encoding=('Frozen raw integer shifted by '+str(int((exponents+fractions)[0,COLS[i]]))) if i<16 else 'Normalized analytical descriptor times127, ties-to-even',scope='Selected from actual retained point view; total N may include history'))
    writecsv(HERE/'feature_dictionary.csv',dictionary)
    writecsv(HERE/'variant_columns.csv',[dict(tag=tag,input_column=j,canonical_column=i,feature_name=names[i]) for tag in ORDER for j,i in enumerate(take(tag))])
    flat=[]
    for r in raw:
        row={k:r[k] for k in ['tag','seed','condition','samples','accuracy','macro_f1']}
        for cls in [0,1]:
            row['recall_class'+str(cls)]=r['recall'][cls];row['f1_class'+str(cls)]=r['per_class_f1'][cls]
            denominator=sum(r['confusion_matrix'][truth][cls] for truth in [0,1]);row['precision_class'+str(cls)]=r['confusion_matrix'][cls][cls]/denominator if denominator else 0.
            for pred in [0,1]:row['true%d_pred%d'%(cls,pred)]=r['confusion_matrix'][cls][pred]
        flat.append(row)
    writecsv(LOG/'evaluation/full_metrics.csv',flat)
    costrows=[costs(tag) for tag in ORDER];writecsv(HERE/'costs.csv',costrows)
    # A descriptive Pareto set in explicit cost dimensions; group guards remain separate.
    pareto=[];axes=['network_macs','extra_products_per_point','ratio_quantizers','channel_sorts']
    for a in costrows:
        dominated=[]
        for b in costrows:
            if b['tag']==a['tag']:continue
            weak=all(b[k]<=a[k] for k in axes) and lookup[b['tag']]['composite']>=lookup[a['tag']]['composite']
            strict=any(b[k]<a[k] for k in axes) or lookup[b['tag']]['composite']>lookup[a['tag']]['composite']
            if weak and strict:dominated.append(b['tag'])
        pareto.append(dict(tag=a['tag'],non_dominated=not dominated,dominated_by=dominated,scope='Mean composite plus separate analytical cost counts; no uncertainty dominance or FPGA performance claim'))
    dump(LOG/'evaluation/pareto.json',pareto)
    chosen=e['decision']['conditional'];main=e['decision']['main'];gates={g['tag']:g for g in e['dimension_gates']}
    decision=('旧23维仍是本轮默认软件候选，新方案未形成足以替换它的综合质量—成本优势。' if chosen=='combined23' else f"本轮默认软件候选选为{NAMES[chosen]}，通过冻结的相对旧23维要求及简洁性规则。")
    decision+=(' 旧A主基线/B困难备选保持：没有方案同时通过本轮相对23维要求与旧A/B要求。24维单独通过旧A/B要求，但未达到本轮替换23维的增益要求；不能写成所有方案均未过旧门槛。' if main=='A' else f" {NAMES[main]}另外通过旧A/B推广门槛，成为开发域的新主候选；仍未确认独立泛化。")
    write_decision_review(e,lookup,ci)
    plain=[
        '**维度先收在23维软件候选；本轮没有找到稳定、值得替换它的新方案。** 这不是说23维在所有数据和模型下都最优，也不表示它已全面替代旧基线。',
        f"**往下删：** 8维综合{100*lookup['core8']['composite']:.3f}%，两种12维为{100*lookup['proxy12']['composite']:.3f}%和{100*lookup['distribution12']['composite']:.3f}%，15维为{100*lookup['combined15']['composite']:.3f}%；都低于23维的{100*lookup['combined23']['composite']:.3f}%。这些具体删组方案在本训练协议下退化，加入更丰富的少数统计量也没有补回全部分数。",
        f"**往上加：** 加点数支持码的24维为{100*lookup['support24']['composite']:.3f}%，几乎持平；加四分位宽度的28维最高，为{100*lookup['width28']['composite']:.3f}%，但一个种子变差、一个少点紧凑组平均下降1.462个百分点，还要增加排序。32/36维也没有稳定替代优势。",
        '**为什么没有继续涨：** 输入只有1～2个点时，本轮新增分位数特征可由已有特征确定，并未增加独立信息。点更多时可以补充内部排序分布，但这次重训的增益不足以抵消局部回退和计算代价。',
        '**24维的特殊情况：** 它通过旧门槛，并不等于旧问题解决。此前116条紧凑少点组，相对旧A三个种子分别净多错3条、4条、0条；只是第三个种子打平，避开了“全部种子退步”的否决条件。原23维该组三个种子各净多错3条，同样不能忽略。',
        '**现在收敛了什么：** 可停止本轮维度扩张，保留23维作为开发中的表示候选，并保留旧A普通主基线、旧B困难条件备选。尚缺独立数据确认；当前23维的局部缺口须继续披露，不以“收敛”宣称它已全局更好。'
    ]
    best=max((r for r in results if r['tag'] not in ['A','B','redundant36']),key=lambda r:r['composite'])
    intro=f'''# 8～36维双向实验：先看结论

**{decision}**

完成11组×3种子＝33条新训练，并复用核验过的六个16/23维模型；这轮最低8维，最高36维。综合分最高的是{NAMES[best['tag']]}（{100*best['composite']:.3f}%），但选型还要满足全部条件/类别/分组要求以及计算成本偏好，不能只挑最高分。

[白话解释与未解问题](02_白话解释与收敛判断.md)｜[全部结果、门槛与失败组](03_完整结果与决策.md)｜[门槛敏感性复核](10_门槛敏感性与最终评审.md)｜[公式与成本](04_公式成本与软件包.md)｜[复现与审计](05_复现审计与设计反思.md)。图：[质量](figures/quality.png)、[成本](figures/cost.png)、[少点分解](figures/low_points.png)。

'''
    (HERE/'README.md').write_text(intro+'\n\n'.join(plain[1:4])+'\n\n'+'\n'.join(table)+'\n\n表内为三个种子平均Macro-F1百分数。综合为五项等权；均匀四分之一先平均三个固定抽样。所有分数属于反复使用的开发数据，不是独立测试或板测。门槛以未四舍五入数值判断，28维平均增益为0.0991296个百分点，且另有种子及类别/分组退步，不只是舍入边界问题。较小维数并非独立信息数量，较大维数也不保证改善；本轮只对所测信息组收口，不宣称全局最优。\n\n'+plain[4]+'\n\n[逐项特征字典](feature_dictionary.csv)、[各方案保留哪些项](variant_columns.csv)、[少点下的确定性冗余](06_少点下的有效信息.md)、[分位定义与文献](07_分位定义与文献边界.md)。\n')
    details=['# 全部指标与冻结规则的决定','',decision,'','\n'.join(table),'','## 相对23维的差值','',
        '| 方案 | seed7/pp | seed17/pp | seed37/pp | 平均/pp | 序列配对95%区间/pp | 通过本轮要求 |','| --- | ---: | ---: | ---: | ---: | --- | --- |']
    for tag in VARIANTS:
        g=gates[tag];r=ci(tag,'combined23');details.append('| '+NAMES[tag]+' | '+' | '.join(f'{100*v:+.3f}' for v in g['composite_delta'])+f" | {100*float(r['delta']):+.3f} | [{100*float(r['low']):+.3f}, {100*float(r['high']):+.3f}] | "+('是' if g['accepted'] else '否')+' |')
    details+=['','区间以27个完整序列配对重采样2000次，三个训练种子固定；未经选择/多重比较调整，不能把开发域选型当作独立显著性或形式化非劣效证明。','',
        '## 每个方案为什么通过或失败','']
    for tag in VARIANTS:
        g=gates[tag];details+=['### '+NAMES[tag],'','失败项：'+('、'.join(g['failures']) or '无')+'。']
        for ref,ds in g['additional'].items():details.append('相对'+NAMES[ref]+'的综合差值（三种子/pp）：'+str([round(100*v,4) for v in ds])+'。')
        for r in sorted(g['group_failures'],key=lambda r:r['mean'])[:8]:details.append(f"- {r['condition']} / {r['axis']} / {r['group']}：{r['samples']}条、{r['sequences']}序列，平均准确率{100*r['mean']:+.3f}pp，三个种子{[round(100*v,3) for v in r['per_seed']]}。")
        details.append('')
    details+=['## 旧A/B推广要求','']
    for g in e['promotion_gates']:details.append('- '+NAMES[g['tag']]+'：'+('通过' if g['accepted'] else '未过：'+'、'.join(g['failures']))+'；失败分组'+str(len(g['group_failures']))+'。')
    details+=['','[全部指标/两类混淆矩阵](../../../logs/feature_dimension_sweep_20260917/evaluation/full_metrics.csv)、[全部支持与不足分组](../../../logs/feature_dimension_sweep_20260917/evaluation/conditional_groups.csv)、[修复和新增错误](../../../logs/feature_dimension_sweep_20260917/evaluation/paired_errors.csv)、[全部配对区间](../../../logs/feature_dimension_sweep_20260917/evaluation/paired_sequence_intervals.csv)、[门槛全部失败项](../../../logs/feature_dimension_sweep_20260917/evaluation/summary.json)。组可能重叠，失败组数不是独立错误样本数。']
    (HERE/'03_完整结果与决策.md').write_text('\n'.join(details)+'\n')
    physical=['# 这轮新增维度到底值不值','','\n\n'.join(plain),'','[24维与28维的具体审查](10_门槛敏感性与最终评审.md)，以下是完整机制对照。','','## 先把三个问题分开','',
        '1. **更少能否保留任务信息？** 8/12/15维按固定物理组删减，并比较两种内容不同的12维。不能把某个12维失败说成所有12维都不行。',
        '2. **少点编码是不是症结？** 17维只给旧16增加1/N，24维只给旧23增加1/N；它们分别是匹配对照，不把全部收益预先归给几何分布。',
        '3. **内部排序分布是否值得额外成本？** 28/32/36维从已补点数的24维出发增加分位宽度、不对称和中位位置；36维再对照同维的冗余模型，检查收益是否只是来自增加参数量。','',
        '## 实测差值','']
    for tag,ref in PLAN['evaluation']['comparisons']:
        r=ci(tag,ref);physical.append(f"- {NAMES[tag]} 对 {NAMES[ref]}：综合{100*float(r['delta']):+.3f}pp，序列配对区间[{100*float(r['low']):+.3f}, {100*float(r['high']):+.3f}]。")
    r=next(r for r in json.loads((LOG/'evaluation/interaction.json').read_text()) if r['condition']=='composite')
    physical+=['',f"分位宽度与不对称两组的交互项为{100*r['mean']:+.3f}pp，区间[{100*r['low']:+.3f}, {100*r['high']:+.3f}]。它是固定重训协议下的关联，不能据此直接证明物理因果协同。",'',
        '## 如何解释少点','',
        '1/N把N=1和2分别编码127、64，而旧N/4编码都为0；但这是含历史的总点数，不能直接称当前目标回波数。非零跨度下N=2/3的IQR/范围恒为1/2，N=3时两个不对称描述互为负数，说明增维会产生随点数变化的冗余。[N1/N2/N3/4～8/≥9完整结果](../../../logs/feature_dimension_sweep_20260917/explanation/exact_N_metrics.json)用于检查这一机制，不能只看总分。',
        '新增细分N组是解释性报告，冻结门槛沿用原点数/形态/距离/历史划分。支持与误差不能靠维度数推出；分位估计在点数少、存在历史重复和量化饱和时仍有限制。反例只证明旧23维未记录某些内部排序差别，没有给合成点簇强行贴上类别。','',
        '## 旧局部缺口有没有改善','',
        '[上轮116条/19序列的紧凑少点组](../../../logs/feature_dimension_sweep_20260917/explanation/previous_116_row_group.csv)按原身份完整保留，不为该组增加训练权重或新门槛。24维相对旧A准确率差值为−2.586、−3.448、0个百分点，平均−2.011；不能认为问题可靠解决。原23维三个种子均为−2.586个百分点。该组是必须回看的失败案例之一，不能单独主导选型。','',
        '## 本轮能收口到什么程度','',
        '这组有限实验可以确定所测表示在固定开发域内的质量—成本取舍，不能证明所有更高/更低维都已经穷尽。标准统计量不等于原创算法。独立泛化、历史关联/坐标时间对齐、真正硬件代价仍分别待验证；不以新软件分数替代板测。所有失败方案、三个种子和最终轮都保留，不继续搜超参数来修饰结果。']
    (HERE/'02_白话解释与收敛判断.md').write_text('\n'.join(physical)+'\n')
    tablecost=['| 方案 | 网络MAC/簇 | 新增乘积/点 | 新增比值量化/簇 | 通道排序/簇 | 显式排序数组/B |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for r in costrows:tablecost.append(f"| {NAMES[r['tag']]} | {r['network_macs']} | {r['extra_products_per_point']} | {r['ratio_quantizers']} | {r['channel_sorts']} | {r['quantile_buffer_bytes_at_N511']} |")
    (HERE/'04_公式成本与软件包.md').write_text('# 公式、成本和软件接口\n\n'+ '\n'.join(tablecost)+'\n\n网络MAC与INT8权重字节数相同，偏置392B；每簇比值通过商/余数和ties-to-even实现，不等于一个FPGA周期。统计比值的组合乘法、极值比较等另存在；表中乘积只数新增逐点累积。排序家族额外读取四个通道并排序，三个分位组共享排序结果。1022B仅指显式INT16数组，不含qsort库内部工作区、调用栈、已有统计状态和模型缓冲，非总存储上限。当前小模型C前端仍计算完整基础16统计，不把网络减少冒充前端全部减少。\n\n'+(HERE/'01_数学定义与实现审查.md').read_text()+'\n\n[C软件包](candidate_c_bundle.zip)含33个新模型及原16/23的六个完整参考包、特征定义、映射、原尺度、新解析尺度、训练归一化与校准身份。每个子目录的candidate.c和params.h可直接gcc编译，输入是1～511个INT16四通道点，Q8.8；历史组织属于上游，当前参考实现不包含检测/跟踪能力，也不表示旧位流支持这些维度。\n')
    pre=json.loads((LOG/'training_preflight.json').read_text());prep=json.loads((LOG/'preparation.json').read_text())
    (HERE/'05_复现审计与设计反思.md').write_text(f'''# 复现、验证与停止位置

本轮33条新训练全部保留，用时{t['wall_seconds']:.1f}秒；原点重建{prep['wall_seconds']:.1f}秒，实际训练池预检及旧模型回放{pre['seconds']:.1f}秒。评价{e['wall_seconds']:.1f}秒，C包验证{pkg['wall_seconds']:.1f}秒；完整后处理计时另见finishing_stage_times.json，不把人工代码审读当成模型计算计时。

33个新模型在三种完整原始点视图上共{pkg['complete_point_to_logit_rows']:,}次点→特征→logits比较零差异；三实现逐层整数校验另有记录。六个冻结参考模型在78个条件/种子组合回放一致。上述次数是模型/视图核对次数，不是独立样本数或板测。

{decision}

原始数据、旧证据与新训练输入SHA均保留。训练前独立Git侧分支备份，训练开始冻结学习/评价核心源码；后处理说明/图表单独生成，没有为了结果修改模型或阈值。原HEAD/暂存区和旧位流保留；最终校验见validation.json，归档与Obsidian本地共享目录同步见backup_sync_receipt.json。

本地环境Python3.10、PyTorch2.4.1 CPU、NumPy1.26.4、h5py及gcc，训练解释器`/tmp/radar_training_audit_20260915/bin/python`。独立重跑须在新目录/LOG和新备份分支执行，默认拒绝覆盖，顺序如下：

```bash
python docs/paper_new/feature_dimension_sweep_2026-09-17/preflight.py
python docs/paper_new/feature_dimension_sweep_2026-09-17/prepare.py
python docs/paper_new/feature_dimension_sweep_2026-09-17/training_preflight.py
python docs/paper_new/feature_dimension_sweep_2026-09-17/backup_git.py --phase before
python docs/paper_new/feature_dimension_sweep_2026-09-17/train.py
python docs/paper_new/feature_dimension_sweep_2026-09-17/finish_software.py
python docs/paper_new/feature_dimension_sweep_2026-09-17/final_audit.py
```

finish_software依次执行评价、完整C包验证、解释、报告和绘图，采用两CPU线程；绘图使用本地matplotlib环境。大数组单独归档，Git保存代码、模型及小证据。没有调用GPU/远端服务器，也没有新增RTL/SoC/位流或板测。
''')
    norm=np.load(LOG/'training_preflight/calibration.npz');cal=[]
    for tag in VARIANTS:
        cols=take(tag);path=LOG/'package'/(tag+'_train_calibration.npz');np.savez(path,mean=norm['mean'][cols],std=norm['std'][cols],calibration=norm['calibration'],class_weights=norm['class_weights'],columns=columns(tag));cal.append(dict(tag=tag,path=str(path.relative_to(ROOT)),sha256=sha(path)))
    dump(LOG/'package/calibration_manifest.json',cal)
    hypotheses=[]
    for tag,ref in PLAN['evaluation']['comparisons']:
        r=ci(tag,ref);hypotheses.append(dict(candidate=tag,reference=ref,composite_delta=float(r['delta']),low=float(r['low']),high=float(r['high']),scope='Matched software retraining contrast, fixed final epochs; no claim that individual feature contribution or physical causality is isolated'))
    dump(LOG/'explanation/hypothesis_evidence.json',hypotheses)
    ambiguity=readcsv(LOG/'explanation/train_input_ambiguity.csv');arows=['# 相同输入编码是否产生类别冲突','',
        '对357780条原保留训练观测及474582条真实少点训练观测合并检查，仅计算已量化输入的完全相等关系，不训练新分类器，也不用于改变冻结选型。这里包含全部恢复的真实训练观测，不等于每轮匹配抽样的访问分布，也不作为实际加权训练损失的下界。若相同输入对应两类，任何只接收这些特征的确定性分类器，至少错分该编码下的少数类数量。该数是这批训练观测上的准确率错误数下界，不是Macro-F1下界或独立泛化结论。','',
        '| 方案 | 不同编码数 | 冲突编码数 | 冲突中的观测数 | 最少误判数下界 |','| --- | ---: | ---: | ---: | ---: |']
    for r in ambiguity:arows.append('| '+NAMES[r['tag']]+' | '+' | '.join(r[k] for k in ['distinct_encoded_inputs','conflicting_inputs','observations_in_conflicting_inputs','unavoidable_train_errors'])+' |')
    arows+=['','实际检查中，23维与24维的不同编码数相同，所有23～36维方案的异类完全同码下界都仍为5条。新增分位数拆分了一些原同码输入，但没有消除这5条下界。这些数量远不足以解释观察到的全部分类误差，不能把模型退步简单归因为完全同码冲突。N1/N2无标签反例仅说明存在可被区分的合法输入，并不表示本批训练观测包含该成对反例。',
        '简单重复特征应与24维具有相同的编码分组和误判下界，脚本对此断言；由此区分名义维度与信息量。即使下界为0，也不证明特征没有损失信息或模型能学好，因为相近编码的可分性、泛化和模型容量未被这个计数衡量。反之冲突也可能包含测量歧义、标签或量化因素，不能一概归为浮点/整数实现错误。']
    (HERE/'09_编码冲突与信息压缩.md').write_text('\n'.join(arows)+'\n')
    (HERE/'08_论文文段与适用边界.md').write_text('# 可用于方法与实验章节的文段\n\n为避免仅以输入维数判断表示效率，本文在固定数据身份、历史规则、训练访问预算、隐藏层和量化协议下，比较了8～36维的预定义信息组。实验同时包括同维不同信息的紧凑表示、仅增加低点数支持编码的对照、逐组加入分位数描述的扩展，以及等维冗余输入对照。11个新方案各训练三个种子并统一采用最终轮，旧16/23维六个模型经输入和整数预测重放核验后复用。\n\n'+decision+' 数值结果、局部失败与质量容忍度一起报告，不将最高总体分数直接作为最终选型。成本分别记录网络乘加、逐点乘积、每簇比值量化、排序和临时存储，避免以输入维数替代完整实现代价。\n\n对于固定线性分位定义，N=1/2时新增分位组可由已有统计确定；N=3时部分新增项之间存在精确依赖。因此，名义维数变化并不等于观测信息量变化，低点数切片的分类变化必须考虑共享训练、参数化与量化因素。全部视图的整数依赖核验及按准确点数分层的指标用于约束解释。\n\n以上结论定位于有限表示集合中的软件开发与选型，不声明全局最优维数。既有开发数据已重复使用，独立泛化、实际检测/跟踪关联、时间坐标对齐及板级资源/性能仍须单独验证。分位数和已有统计量不是本工作的原创发明，贡献须以有证据支持的误差机制与质量—成本取舍表述。\n')
    print(decision,flush=True)

def write_decision_review(e,lookup,ci):
    """Report gate sensitivity without changing a frozen rule or chosen model."""
    rows=readcsv(LOG/'explanation/previous_116_row_group.csv')
    group={(r['tag'],int(r['seed'])):r for r in rows}
    old={g['tag']:g for g in e['promotion_gates']};new={g['tag']:g for g in e['dimension_gates']}
    assert old['support24']['accepted'] and new['support24']['failures']==['minimum_composite_gain']
    per_seed=[]
    for s in SEEDS:
        a=group[('A',s)];b=group[('combined23',s)];c=group[('support24',s)];n=int(a['samples'])
        assert n==116 and int(a['sequences'])==19
        counts=[round(float(r['accuracy'])*n) for r in [a,b,c]]
        assert all(abs(float(r['accuracy'])-count/n)<1e-12 for r,count in zip([a,b,c],counts))
        per_seed.append(dict(seed=s,samples=n,sequences=19,A_correct=counts[0],combined23_correct=counts[1],support24_correct=counts[2],support24_extra_errors_vs_A=counts[0]-counts[2],support24_accuracy_delta_vs_A=(counts[2]-counts[0])/n))
    assert [r['support24_extra_errors_vs_A'] for r in per_seed]==[3,4,0]
    dump(LOG/'explanation/gate_sensitivity.json',dict(status='PASS',old_gate_support24_pass=True,new_gate_support24_pass=False,tracked_group=per_seed,decision_unchanged=e['decision'],scope='Descriptive review of a frozen all-three-negative rule; no post-hoc replacement threshold or new training'))
    support=ci('support24','combined23');width=ci('width28','combined23');full=ci('full36','redundant36')
    width_group=new['width28']['group_failures'];assert len(width_group)==1
    g=width_group[0];recall=next(r for r in new['width28']['conditions'] if r['condition']=='kept_single')['recall_delta'][0]
    text=['# 门槛敏感性与最终评审','',
        '本页在全部训练和冻结选型结束后复核“数值通过”是否被过度解释。不修改任何门槛、预测、模型、随机种子或正式决定。','',
        '## 24维确实通过旧要求，但没有可靠修复局部问题','',
        f"24维相对23维的综合分平均只提高{100*float(support['delta']):.6f}个百分点，三种子分别为{[round(100*v,6) for v in new['support24']['composite_delta']]}，序列配对95%区间为[{100*float(support['low']):+.6f}, {100*float(support['high']):+.6f}]个百分点。未达到事先约定的平均至少+0.1个百分点且三个种子同向要求，因此不能作为本轮替换候选。",
        '它独立通过了旧A/B门槛，这一事实必须保留。不过，旧分组否决要求“三个种子全部退步且平均下降超过1个百分点”；一个种子打平，就不会触发。此前均匀保留四分之一的紧凑少点组（116条、19序列）如下。','',
        '| 种子 | 旧A正确条数 | 23维正确条数 | 24维正确条数 | 24维相对A净新增错误 | 24维准确率差/pp |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for r in per_seed:text.append(f"| {r['seed']} | {r['A_correct']} | {r['combined23_correct']} | {r['support24_correct']} | {r['support24_extra_errors_vs_A']} | {100*r['support24_accuracy_delta_vs_A']:+.6f} |")
    text+=['',f"24维该组平均仍比A低{abs(100*np.mean([r['support24_accuracy_delta_vs_A'] for r in per_seed])):.6f}个百分点。seed37只是打平，另两个种子各净多错3条和4条。只能写“通过冻结规则”，不能写“局部问题已解决”或“普遍不退步”。这里的净新增错误是总错数之差，不等于逐观测负翻转总数。23维三个种子均比A少判断正确3条，也不是已解决该缺口的方案。",'',
        '## 28维的否决不只是差0.001个百分点','',
        f"四分位宽度28维的综合增益为{100*float(width['delta']):.7f}个百分点，区间[{100*float(width['low']):+.6f}, {100*float(width['high']):+.6f}]。三种子差值为{[round(100*v,6) for v in new['width28']['composite_delta']]}，其中一个为负。表格四舍五入后看似刚好+0.100，但门槛按原数值判定。",
        f"同时，{g['condition']} / {g['axis']} / {g['group']}共{g['samples']}条、{g['sequences']}序列，准确率三个种子分别{[round(100*v,6) for v in g['per_seed']]}个百分点，平均{100*g['mean']:+.6f}个百分点；kept_single条件下class0召回率平均{100*recall:+.6f}个百分点，超过0.5个百分点容忍度。即便宽容处理综合分的边界，其他冻结要求仍失败。分位家族还需要四通道排序。",'',
        '## 多维和更大参数量不能直接等同于更多有效信息','',
        f"36维相对同维冗余对照仅平均提高{100*float(full['delta']):.6f}个百分点，区间[{100*float(full['low']):+.6f}, {100*float(full['high']):+.6f}]跨零。这个对照没有建立稳定的额外信息收益，也不能凭未显著就宣称两者严格等效。",
        'N1/N2分位组的确定性依赖说明，少点切片上分数变化可以来自共享训练、重参数化或量化，而非该切片新增形状信息。不能以跨切片总体关联代替这一数学事实。', '',
        '## 最终判断与下一阶段边界','',
        '冻结决定保持：23维为所测表示中的默认软件候选，旧A为普通主基线、旧B为困难条件备选。没有同时通过新旧要求的替换方案。本次收敛的是有限特征集合中的选型，不是宣布23维全局最优或已经形成全面优于基线的最终算法。',
        '“所有种子同向”门槛对小组少量样本的变化敏感，应在论文中与实际错误数一起报告；不在看到本轮结果后改门槛来选喜欢的模型。后续如设置新接受标准，须另行事前冻结，并使用未参与选型的序列。',
        '继续盲目扩维的证据不足。更有依据的下一步是固定表示后确认独立序列上的表现，并核查历史时间跨度/坐标漂移与局部错误的关系。后者在当前数据上的分析仍属开发诊断，不能包装成独立验证；本次评审没有在固定33条之外追加训练，也没有启动硬件工作。', '',
        '证据：[冻结决策](../../../logs/feature_dimension_sweep_20260917/evaluation/summary.json)、[116条组逐种子](../../../logs/feature_dimension_sweep_20260917/explanation/previous_116_row_group.csv)、[门槛复核数据](../../../logs/feature_dimension_sweep_20260917/explanation/gate_sensitivity.json)、[完整配对区间](../../../logs/feature_dimension_sweep_20260917/evaluation/paired_sequence_intervals.csv)。']
    (HERE/'10_门槛敏感性与最终评审.md').write_text('\n'.join(text)+'\n')
    return per_seed

if __name__=='__main__':main()
