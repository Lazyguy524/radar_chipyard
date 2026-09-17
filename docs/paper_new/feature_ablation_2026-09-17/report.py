"""Render bounded ablation evidence without changing selection rules."""
from ab_common import *

def main():
    result=json.loads((LOG/'evaluation/summary.json').read_text());train=json.loads((LOG/'training/summary.json').read_text());pre=json.loads((LOG/'preflight.json').read_text());package=json.loads((LOG/'package/summary.json').read_text())
    rows=json.loads((LOG/'evaluation/metrics.json').read_text());m={(r['tag'],r['seed'],r['condition']):r for r in rows};intervals=readcsv(LOG/'evaluation/paired_sequence_intervals.csv')
    def f(tag,c):return np.mean([m[(tag,s,c)]['macro_f1'] for s in SEEDS])
    def score(tag,s):return previous.composite({c:m[(tag,s,c)]['macro_f1'] for c in PLAN['evaluation']['conditions']})
    def composite(tag):return np.mean([score(tag,s) for s in SEEDS])
    display={'A':'A：常规主基线','B':'B：困难备选','full21':'21 维对照','dedup20':'20 维去重复','no_rcs18':'18 维去 RCS','less_shape16':'16 维去部分形态代理'}
    table=['| 方案 | 常规 F1 | 均匀四分之一 F1 | 中心一半 F1 | 真实少点当前帧 F1 | 真实少点加历史 F1 | 五项综合 |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    summary=[]
    for t in ['A','B',*VARIANTS]:
        vals=[f(t,'clean'),np.mean([f(t,'uniform_quarter_'+str(i)) for i in range(3)]),f(t,'central_half'),f(t,'sparse_single'),f(t,'sparse_context'),composite(t)]
        table.append('| '+display[t]+' | '+' | '.join(f'{100*v:.3f}' for v in vals)+' |')
        summary.append(dict(tag=t,dim=VARIANTS[t]['dim'] if t in VARIANTS else 21,clean=vals[0],quarter_mean=vals[1],central=vals[2],sparse_single=vals[3],sparse_context=vals[4],composite=vals[5]))
    writecsv(HERE/'results.csv',summary)
    detailed=[]
    for r in rows:
        cm=r['confusion_matrix'];detailed.append(dict(tag=r['tag'],seed=r['seed'],condition=r['condition'],samples=r['samples'],accuracy=r['accuracy'],macro_f1=r['macro_f1'],f1_class0=r['per_class_f1'][0],f1_class1=r['per_class_f1'][1],recall_class0=r['recall'][0],recall_class1=r['recall'][1],true0_pred0=cm[0][0],true0_pred1=cm[0][1],true1_pred0=cm[1][0],true1_pred1=cm[1][1]))
    writecsv(LOG/'evaluation/full_metrics.csv',detailed)
    gates=['| 方案 | 删维容忍度 | 阻止通过的项目 | 不合格分组数 | 旧 A/B 推广门槛 |','| --- | --- | --- | ---: | --- |']
    for g in result['ablation_gates']:
        prom=next(x for x in result['promotion_gates'] if x['tag']==g['tag'])
        gates.append('| '+display[g['tag']]+' | '+('通过' if g['accepted'] else '未通过')+' | '+(('常规、受扰、召回及分组退化；详表见结果页' if g['tag']=='no_rcs18' else '、'.join(g['failures'])) or '无')+f" | {len(g['group_failures'])} | "+('通过' if prom['accepted'] else '未通过')+' |')
    chosen=result['decision']['conditional_subset'];main=result['decision']['main']
    conclusion=('本轮没有删维候选通过全部预设容忍度，当前覆盖下保留 21 维对照。' if chosen=='full21' else '在本轮真实少点覆盖训练条件下，'+display[chosen]+'通过预设删维容忍度，被选为该覆盖下的简化候选。')
    conclusion+=(' 四组均未过完整推广门槛，整体仍保留 A 为主基线、B 为困难条件备选。' if main=='A' else ' 通过旧 A/B 推广规则的本轮候选为 '+display[main]+'；仍需独立确认。')
    heading='# 特征消融结果：先看这一页\n\n'+conclusion+'\n\n已完成 21/20/18/16 维四组、各三个种子，共 12 条固定训练。维度是真正减少输入列；不是置零或随机打乱。\n\n'
    diagnostic='重复的 y 跨度两项确实携带相同输入信息；冻结权重相加并允许有符号 9 位后，三种子、13 种条件共 '+f"{result['duplicate_exact_rows']:,}"+' 次输入/模型组合的三层输出与旧模型完全相同。但合并后每个种子有 '+str([x['outside_int8'] for x in pre['duplicate']])+' 个权重超过 INT8 对称范围。全 INT8 重训是另一个问题，不能把代数等价当作其质量保证。'
    (HERE/'README.md').write_text(heading+'\n'.join(table)+'\n\n表内为三个种子平均百分数；综合分不代表上线性能。\n\n'+diagnostic+'\n\n'+ '\n'.join(gates)+'\n\n**论文能新增的证据：** 当前代理的槽位数与独立信息量不同；特征是否必要应结合固定精度、受扰条件和局部分组判断。删维的网络 MAC 节省只有约 1.85%～9.26%，不能写成板卡资源耗尽或硬件收益已测得。\n\n先读 [结果与反例](01_结果与选型.md)，需要解释原理再读 [算法、成本与论文文段](02_算法成本与论文文段.md)。[执行反思与复现](03_反思与复现.md)保留失败与适用边界。[完整 CSV](results.csv)、[C 参考包](candidate_c_bundle.zip)。\n\n本轮属于重复使用开发数据的方案分析。独立泛化、真实目标关联、历史时空对齐与板级成本仍是明确缺口；没有新增硬件工作。旧研究包和历史结论不改。\n')
    detail=['# 完整结果与选型\n',conclusion,'\n'+'\n'.join(table),'\n'+'\n'.join(gates),'\n## 三种子与配对区间\n','所有模型固定最终第 60 轮 QAT；不挑种子。序列内观测保持整体，27 个开发序列配对重采样 2,000 次。三个已训练种子各报告，并在相同序列抽样下取种子平均；没有推断未训练种子的总体分布。以下差值单位均为百分点。\n','| 删维方案 | seed 7 综合差 | seed 17 综合差 | seed 37 综合差 | 平均差 | 序列配对 95% 区间 |','| --- | ---: | ---: | ---: | ---: | --- |']
    for g in result['ablation_gates']:
        t=g['tag'];ci=next(r for r in intervals if r['tag']==t and r['reference']=='full21' and r['condition']=='composite' and r['seed']=='mean3')
        detail.append('| '+display[t]+' | '+' | '.join(f'{100*d:+.3f}' for d in g['composite_delta'])+f" | {100*np.mean(g['composite_delta']):+.3f} | [{100*float(ci['low']):+.3f}, {100*float(ci['high']):+.3f}] |")
    detail+=['\n## 不通过的分组与条件\n','相对 matched full21；至少 100 条、3 个序列且包含两类才进入分组否决。全量组（含低支持、少点形态未定义）仍保留在 CSV。形态组取原始代理输入的分组，不能把删点后的观测形态或历史聚合形态称为单帧真实物理形状。']
    failures=[]
    for g in result['ablation_gates']:
        detail+=['\n### '+display[g['tag']]+'\n','失败项目：'+('、'.join(g['failures']) or '无')+'。']
        for r in g['group_failures']:failures.append(dict(tag=g['tag'],**r))
        for r in sorted(g['group_failures'],key=lambda x:x['mean'])[:8]:detail.append(f"- {r['condition']} / {r['axis']} / {r['group']}：{r['samples']} 条、{r['sequences']} 序列，平均准确率变化 {100*r['mean']:+.3f} 个百分点；三 seed {str([round(100*v,3) for v in r['per_seed']])}。")
        worst=min(g['conditions'],key=lambda x:x['mean_delta_f1']);detail.append(f"\n最不利整体 F1 条件：{worst['condition']}，平均变化 {100*worst['mean_delta_f1']:+.3f} 个百分点。")
    dump(LOG/'evaluation/ablation_group_failures.json',failures)
    detail+=['\n## 旧推广规则单列\n','删维容忍度与替换 A/B 是不同问题，不相互代替。']
    for g in result['promotion_gates']:detail.append('- '+display[g['tag']]+'：'+('通过' if g['accepted'] else '未通过：'+'、'.join(g['failures']))+'；分组失败 '+str(len(g['group_failures']))+'。')
    detail+=['\n## 精确去重与全 INT8 重训分开解释\n',diagnostic,'\n冻结模型的恒等式为 `w6*x6+w10*x10=(w6+w10)*x6`（x6=x10）。偏置、定标、乘数和后两层不变，整数累加无溢出。对应有符号 9 位诊断只验证代数关系，不是第五组训练；用 int16 保存整个第一层会增加当前 C 包存储，不能当作已优化的混合精度实现。\n','[全指标](../../../logs/feature_ablation_20260917/evaluation/full_metrics.csv)、[全部分组](../../../logs/feature_ablation_20260917/evaluation/conditional_groups.csv)、[新增/修复错误](../../../logs/feature_ablation_20260917/evaluation/paired_errors.csv)、[区间](../../../logs/feature_ablation_20260917/evaluation/paired_sequence_intervals.csv)、[固定顺序抽取的错误案例](../../../logs/feature_ablation_20260917/evaluation/error_cases.json)。案例按 seed 7 的首三条取，不选戏剧化个例；开发数据反复使用，区间不构成独立显著性证明。']
    (HERE/'01_结果与选型.md').write_text('\n'.join(detail)+'\n')
    names=['点数','x 均值代理','y 均值代理','x 跨度/4','y 跨度/4','x 跨度','y 跨度','最小近似距离','最大近似距离','均值坐标的近似距离','y 跨度（重复）','两跨距/4 的较大值','两跨距/4 的较小值','密度倒数代理','速度均值代理','速度跨度/4','最小速度','最大速度','RCS 均值代理','RCS 跨度/4','最大 RCS']
    ex,fr=base.scales();scale=['| 原槽位 | 当前实际定义 | 最终移位 |','| ---: | --- | ---: |']
    for i,name in enumerate(names):scale.append(f'| {i} | {name} | {(ex+fr)[0,i]} |')
    costs=[]
    for tag,v in VARIANTS.items():
        d=v['dim'];c=3 if tag=='no_rcs18' else 4;mac=64*d+2112
        costs.append(dict(tag=tag,dim=d,network_macs=mac,mac_saved=3456-mac,mac_saved_fraction=(3456-mac)/3456,int8_weight_bytes=mac,int32_bias_bytes=392,input_feature_bytes=d,logical_sum_channels=c,scan_adds_per_point=c,extrema_comparisons_after_first=2*c+2,raw_input_bytes_per_point=8,mean_proxy_results=c,span_subtractions=c))
    writecsv(HERE/'costs.csv',costs)
    costtable=['| 方案 | MAC/推理 | MAC 减少 | INT8 权重字节 | 每点通道累加 | 首点后极值比较/点 |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for c in costs:costtable.append(f"| {display[c['tag']]} | {c['network_macs']} | {100*c['mac_saved_fraction']:.2f}% | {c['int8_weight_bytes']} | {c['scan_adds_per_point']} | {c['extrema_comparisons_after_first']} |")
    costtext='# 算法表示、共享成本与论文文段\n\n单遍扫描产生各通道的和、最小值、最大值及距离极值。跨度同时供应尺度、形态派生项和密度，输出个数不能等同于独立计算模块数量。代理均值为 `sum >> ceil(log2 N)`；它与真均值的差异属于已保留的研究问题，本轮不同时更改。\n\n'+ '\n'.join(scale)+'\n\n除密度外原量以 Q8.8 为主；密度函数本身已带量化/饱和。最后按冻结移位 ties-to-even 并饱和 [-127,127]。不得把代理3/4/11/12直接写成真实标准差或协方差特征值。\n\n'+ '\n'.join(costtable)+'\n\n网络 MAC = 64d + 64×32 + 32×2，偏置共 98 个 INT32（392 B）不变。不计偏置加法、激活和重新量化为 MAC。去重20省64次第一层MAC，但 y 跨度仍必需；18维去 RCS 省相应通道累加、2个极值比较/点、1个跨度和1个均值代理；16维方案主要省最终派生输出及第一层MAC，共享扫描统计仍保留。极值比较计数包含两个距离极值，不包含各方案相同的距离近似内部比较。\n\n四方案均单遍，原始输入仍是每点8B，历史状态/传输格式未缩短。软件的20/18/16维接口不代表现有21维硬件已兼容这些模型，不能直接加载旧位流并使用新软件质量指标。当前 C 用 int64 存储和、int32 存储极值/跨度；N≤511、INT16 输入时和可用有符号25位、跨度需无符号16位，但这里未生成更窄硬件。输出 INT8，模型累加 INT32，重新量化乘积 INT64；实测导出界见 audit。位宽建议不等于综合结果。\n\n9位精确去重诊断若仅将合并的64个系数从8位扩为9位，理论打包权重总数约为3400B；当前通用 C 导出将整个第一层存为int16，实际权重4672B（第一层2560B、后两层2112B），比3456B更大。没有优化此存储，也没有将它包装成资源节省。\n\n## 可用于论文的结果表述\n\n为检验统计代理输入的必要性，本文固定真实少点覆盖策略、训练样本访问预算及隐藏层结构，对完整21维、去重复20维、去RCS18维及去部分形态派生项16维执行配对重训，各保留三个随机种子的最终量化模型。通过固定样本顺序和训练校准身份，并逐整数复现完整对照，控制与删维无关的差异。'+conclusion+'\n\n重复输入的代数合并在放宽相应权重表示后实现逐层整数等价，但全INT8重训同时受到参数化、精度与优化轨迹影响。因此，“输入信息冗余”与“固定量化网络可无损删维”必须区分。重训对照同时改变参数化及优化轨迹，不能仅凭本轮结果把全部差异归因于INT8精度。分组对照及负结果用于限定简化方案的适用范围，而非证明一个全局最优维数。当前证据来自已多轮使用的开发数据，不构成独立泛化确认。\n\n研究贡献应落在误差机制、受约束的表示与精度选择，以及可核对的质量—计算成本关系；删组消融、标准QAT、普通重训本身不作为未经查证的原创算法。\n'
    (HERE/'02_算法成本与论文文段.md').write_text(costtext)
    norm=np.load(OLD/'prepared/proxy.npz');cal=[]
    for tag in VARIANTS:
        cols=keep(tag);d=LOG/'package';np.savez(d/(tag+'_train_calibration.npz'),mean=norm['mean'][cols],std=norm['std'][cols],calibration=norm['calibration'],class_weights=norm['class_weights'],columns=cols)
        cal.append(dict(tag=tag,path=str((d/(tag+'_train_calibration.npz')).relative_to(ROOT)),sha256=sha(d/(tag+'_train_calibration.npz'))))
    dump(LOG/'package/calibration_manifest.json',cal)
    review=f'''# 执行反思、复现与停止记录

本轮 12 条训练完成，耗时 {train['wall_seconds']:.1f} 秒；执行前 Python 预检 {pre['wall_seconds']:.1f} 秒；评价 {result['wall_seconds']:.1f} 秒，完整 C 打包验证 {package['wall_seconds']:.1f} 秒。每个方案严格使用 20 轮浮点和 60 轮 QAT、每轮 357,780 次访问。两个 CPU 线程；未调用 GPU、训练服务器或硬件。没有追加种子或因中间分数调整门槛。

完整 21 维三个种子全部复现旧 proxy_natural 的整数权重、偏置、乘数与常规 logits。每个模型对 80,450 条常规输入执行 QAT/NumPy/C 三实现逐层检查。所有12个模型又从真实点输入完整计算特征与logits，共 {package['complete_point_to_logit_rows']:,} 次模型/观测组合零差异。区别于 {result['duplicate_exact_rows']:,} 次去重诊断的缓存特征输入检查，不能把两种行数混称独立样本数。

执行前已明确输入槽位6/10重复；合并权重超INT8现象实测得到，并未截断后继续宣称等价。新增C批次步长按真实维数处理；原始案例覆盖单点、两点、511点、正负边界。CLI拒绝空输入、非8B整数倍及超过511点输入。单执行者代码及结果复核，不标为外部独立评审。

{conclusion}

## 反思与下一项明确缺口

这轮回答的是固定代理表示与真实少点训练条件下的有限必要性问题。去RCS与去形态组不是对所有可能子集的搜索；不能外推到另外三种训练覆盖/表示，更不能称“筛出了全局最优维度”。去形态16与去重20之间的配对表额外分离重复项以外四项的作用。初始函数中不保留被删信息；去重复时合并初始权重，浮点最大差异仅按预检实测披露。

不应在既有反复使用的开发集上无休止搜索一个全条件胜出的模型。下一阶段优先用真正独立的采集/序列验证已冻结的选择，或在另立预算后隔离历史时间跨度与位移的作用；不会悄悄改变历史规则以抹去本轮负结果。真实少点当前帧与历史聚合视图仍分开报告，GT轨迹关联不等于真实系统已提供可靠关联。当前二分类范围也不扩大解释成六类道路使用者识别。

## 复现

依赖原始审计包路径与 SHA；本轮直接复用冻结特征缓存。重新运行应使用独立工作副本、全新 LOG 目录及独立备份分支（ab_common.py 与 backup_git.py 的路径/分支需同时适配），脚本默认拒绝覆盖。以下是原执行顺序，不是在现有成果目录上的覆盖命令。Python 环境为 `/tmp/radar_training_audit_20260915/bin/python`（CPU PyTorch 2.4.1、NumPy 1.26.4）；C 使用 gcc，图另用 matplotlib 环境。固定 plan.json 是协议事实源。

```bash
python docs/paper_new/feature_ablation_2026-09-17/preflight.py
python docs/paper_new/feature_ablation_2026-09-17/backup_git.py --phase before
python docs/paper_new/feature_ablation_2026-09-17/train.py
python docs/paper_new/feature_ablation_2026-09-17/evaluate.py
python docs/paper_new/feature_ablation_2026-09-17/build_package.py
python docs/paper_new/feature_ablation_2026-09-17/dependency_freeze.py
python docs/paper_new/feature_ablation_2026-09-17/dependency_audit.py
python docs/paper_new/feature_ablation_2026-09-17/report.py
python docs/paper_new/feature_ablation_2026-09-17/final_audit.py
```

初检核对旧软件包969条证据。最终审计另外展开实际使用的上游训练源清单，并重建预检时的C源码做逐字节一致性核验；不把这项补充写成训练前已经完成。训练与导出核心脚本在训练前备份，训练启动时冻结源/数据哈希。报告与收尾审计脚本在训练期间编写，未参与训练；没有改已冻结训练源码。初始预检及完整训练源清单分别保留；结果整理新增文件不改历史源清单。

软件包包含全部四方案×三种子；各子目录有映射、尺度、INT8权重、INT32偏置、C源码、输入示例、契约。顶层另保存列投影后的训练归一化、共同校准行身份与类别权重；推理已经折叠归一化，不做运行期标准化。

Git 使用独立侧分支，不切换用户工作分支，不改真实暂存区。备份与本地 Obsidian 共享目录校验以 backup_sync_receipt.json 为准；外部云同步不可观测。旧软件及RTL证据包再次逐项SHA核对，旧未测位流不覆盖。
'''
    (HERE/'03_反思与复现.md').write_text(review)
    if chosen=='less_shape16':
        simple='\n\n**白话解释：21 维并非都要保留。删掉一个重复项和四个形态派生项后，16 维通过了本轮预设的质量容忍度；RCS 应保留，删掉它使常规 F1 下降约 1.85 个百分点。** 16 维仍保留 x/y 跨度、密度、位置、距离和速度，不能写成不需要形态信息。\n\n16 维相对本轮匹配的 21 维对照：常规 F1 98.047% → 98.143%，五项综合 96.672% → 96.763%，网络 MAC 3456 → 3136（减少 9.26%）。这是软件运算量，不是实测 FPGA 收益。选择16维主要因为较简洁且通过容忍度，不因那一点分数差宣称算法突破。\n\n为什么仍不换原主方案：16维在中心删点条件下比旧 B 低 0.420 个百分点，超过预设0.3；均匀四分之一的一个紧凑形态组（删点后3～4点，121条、18序列）比旧 A 的准确率平均低3.306个百分点。两种比较的参照不同，不能用“相对21维简化成功”掩盖它们。因此冻结16维为本覆盖下的软件简化候选，A/B仍按原边界保留。'
        path=HERE/'README.md';text=path.read_text();pos=text.index('\n\n');text=text[:pos]+simple+text[pos:];path.write_text(text)
    path=HERE/'README.md';path.write_text(path.read_text()+'\n[逐条件质量与配对区间图](figures/ablation_quality.png)、[质量—MAC图](figures/quality_cost.png)、[派生依赖补充](04_派生依赖补充.md)。\n')
    print(conclusion,flush=True)
if __name__=='__main__':main()
