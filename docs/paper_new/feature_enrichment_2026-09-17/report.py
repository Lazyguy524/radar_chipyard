"""Plain-language results, physical meaning, full evidence and limitations."""
from ex_common import *

def main():
    e=json.loads((LOG/'evaluation/summary.json').read_text());train=json.loads((LOG/'training/summary.json').read_text());prep=json.loads((LOG/'preparation.json').read_text());pkg=json.loads((LOG/'package/summary.json').read_text())
    metrics=json.loads((LOG/'evaluation/metrics.json').read_text());m={(r['tag'],r['seed'],r['condition']):r for r in metrics};ci=readcsv(LOG/'evaluation/paired_sequence_intervals.csv');names={'A':'旧A主基线','B':'旧B困难备选','base16':'16维对照','geometry19':'19维：加几何分布','distribution20':'20维：加速度/RCS分布','combined23':'23维：两组都加','redundant23':'23维：只重复旧信息'}
    def mean(t,c):return float(np.mean([m[(t,s,c)]['macro_f1'] for s in SEEDS]))
    def score(t,s):return previous.composite({c:m[(t,s,c)]['macro_f1'] for c in PLAN['evaluation']['conditions']})
    result=[];table=['| 方案 | 常规 | 均匀四分之一 | 中心一半 | 真实少点当前帧 | 真实少点加历史 | 五项综合 |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for t in ['A','B',*VARIANTS]:
        v=[mean(t,'clean'),float(np.mean([mean(t,'uniform_quarter_'+str(i)) for i in range(3)])),mean(t,'central_half'),mean(t,'sparse_single'),mean(t,'sparse_context'),float(np.mean([score(t,s) for s in SEEDS]))]
        table.append('| '+names[t]+' | '+' | '.join(f'{100*x:.3f}' for x in v)+' |');result.append(dict(tag=t,dim=VARIANTS[t]['dim'] if t in VARIANTS else 21,clean=v[0],quarter=v[1],central=v[2],sparse_single=v[3],sparse_context=v[4],composite=v[5],seed7=score(t,7),seed17=score(t,17),seed37=score(t,37)))
    writecsv(HERE/'results.csv',result)
    flat=[]
    for r in metrics:
        z={k:r[k] for k in ['tag','seed','condition','samples','accuracy','macro_f1']}
        for cls in range(2):
            z['f1_class'+str(cls)]=r['per_class_f1'][cls];z['recall_class'+str(cls)]=r['recall'][cls]
            for pcidx in range(2):z['true%d_pred%d'%(cls,pcidx)]=r['confusion_matrix'][cls][pcidx]
        flat.append(z)
    writecsv(LOG/'evaluation/full_metrics.csv',flat)
    chosen=e['decision']['conditional'];main=e['decision']['main']
    answer=('新增三种表示都没有通过本轮全部预设要求，保留16维作为该训练覆盖下的简化候选。' if chosen=='base16' else names[chosen]+'通过本轮信息补充门槛，被选为这套训练覆盖下的新软件候选。')
    answer+=(' 原A/B主备边界保持。' if main=='A' else ' '+names[main]+'同时通过旧A/B推广门槛，但独立泛化仍待验证。')
    gates=['| 新增组 | 相对16维综合变化/百分点 | 三种子同向 | 是否满足全部新增要求 | 失败项数 |','| --- | ---: | --- | --- | ---: |']
    for g in e['enrichment_gates']:gates.append('| '+names[g['tag']]+' | '+f"{100*np.mean(g['composite_delta']):+.3f}"+' | '+('是' if min(g['composite_delta'])>0 else '否')+' | '+('是' if g['accepted'] else '否')+' | '+str(len(g['failures']))+' |')
    simple='# 增加有解释意义的特征：先看结论\n\n'+answer+'\n\n**这轮已经允许超过21维：比较16、19、20、23维，并加入一个同为23维但只重复旧信息的对照。** 共15条固定训练、每组3个种子，最终轮统一评价，没有追加阈值或维度搜索。\n\n'+ '\n'.join(table)+'\n\n表内为三种子平均Macro-F1百分数，当前数据已经用于多轮开发，不能写成独立测试成绩。\n\n'+ '\n'.join(gates)+'\n\n新增量描述的是“相同外轮廓内点如何分布、径向速度如何分布、反射值更偏向哪一端”。先用同16维输出的具体反例证明表示差异，再用匹配训练验证是否真有分类价值；物理解释不自动等于分类增益。\n\n单点和两点的几何描述容易退化；旧点数编码又将N=1/2都量化为0，因此新增量可能同时提供点数不足的间接线索，不能把全部收益归因于更准确的目标形状。[低点数解释](06_数据解释与反例.md)明确保留这个替代解释。\n\n先读[具体结果与反例](03_结果与选型.md)，再看[公式与成本](04_公式成本与论文文段.md)、[数据解释](06_数据解释与反例.md)。[C软件包](candidate_c_bundle.zip)、[质量对照图](figures/quality.png)、[同16维但不同分布的点簇图](figures/counterexamples.png)。新特征尚未接入硬件，没有新板测或FPGA收益结论。\n'
    (HERE/'README.md').write_text(simple)
    details=['# 全部结果、交互与失败项\n',answer,'\n'+'\n'.join(table),'\n## 新增特征的匹配差值\n','单位为百分点；配对重采样27个完整序列2000次，三个已训练种子固定。区间未经选择/多重比较调整，不做独立显著性或物理因果声明。\n','| 方案 | seed7 | seed17 | seed37 | 平均 | 序列配对95%区间 |','| --- | ---: | ---: | ---: | ---: | --- |']
    for g in e['enrichment_gates']:
        row=next(r for r in ci if r['tag']==g['tag'] and r['reference']=='base16' and r['condition']=='composite' and r['seed']=='mean3')
        details.append('| '+names[g['tag']]+' | '+' | '.join(f'{100*x:+.3f}' for x in g['composite_delta'])+f" | {100*float(row['delta']):+.3f} | [{100*float(row['low']):+.3f}, {100*float(row['high']):+.3f}] |")
    for g in e['enrichment_gates']:
        details+=['\n## '+names[g['tag']]+'\n','未通过项目：'+('、'.join(g['failures']) or '无')+'。']
        if g['composite_vs_redundancy'] is not None:details.append('与等维冗余对照的综合变化（三种子，百分点）：'+str([round(100*x,4) for x in g['composite_vs_redundancy']])+'。不能只对照16维就认定新信息带来收益。')
        for r in sorted(g['group_failures'],key=lambda r:r['mean'])[:8]:details.append(f"- {r['condition']} / {r['axis']} / {r['group']}：{r['samples']}条、{r['sequences']}序列，平均准确率变化{100*r['mean']:+.3f}pp，三种子{str([round(100*v,3) for v in r['per_seed']])}。")
        worst=min(g['conditions'],key=lambda r:r['mean_f1_delta']);details.append(f"\n最差整体F1条件为{worst['condition']}，变化{100*worst['mean_f1_delta']:+.3f}pp。")
    interaction=json.loads((LOG/'evaluation/interaction.json').read_text());inter=next(x for x in interaction if x['condition']=='composite')
    details+=['\n## 两组是否互补\n',f"综合分交互项（合并−仅几何−仅速度/RCS＋基线）为{100*inter['mean']:+.4f}pp，配对区间[{100*inter['low']:+.4f}, {100*inter['high']:+.4f}]。这是固定训练协议下的效应组合，不能视为独立物理因果效应；条件结果见interaction.json。",'\n## 原A/B推广门槛\n']
    for g in e['promotion_gates']:details.append('- '+names[g['tag']]+'：'+('通过' if g['accepted'] else '未通过：'+'、'.join(g['failures']))+'；不合格分组数'+str(len(g['group_failures']))+'。')
    details+=['\n[全部指标与两类混淆矩阵](../../../logs/feature_enrichment_20260917/evaluation/full_metrics.csv)、[全部条件组](../../../logs/feature_enrichment_20260917/evaluation/conditional_groups.csv)、[新增与修复错误](../../../logs/feature_enrichment_20260917/evaluation/paired_errors.csv)、[所有配对区间](../../../logs/feature_enrichment_20260917/evaluation/paired_sequence_intervals.csv)、[固定顺序错误案例及特征值](../../../logs/feature_enrichment_20260917/explanation/cases_with_features.json)。不合格组会重叠，组数不是独立失败样本数。']
    (HERE/'03_结果与选型.md').write_text('\n'.join(details)+'\n')
    costs=[];ct=['| 方案 | 网络MAC/簇 | INT8权重/B | 额外乘积/点 | 额外平方和/交叉和状态 | 额外有理数量化/簇 |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for tag,v in VARIANTS.items():
        g=tag in ['geometry19','combined23'];d=tag in ['distribution20','combined23'];row=dict(tag=tag,dim=v['dim'],network_macs=64*v['dim']+2112,int8_weight_bytes=64*v['dim']+2112,int32_bias_bytes=392,new_products_per_point=3*int(g)+2*int(d),new_sum_states=3*int(g)+2*int(d),new_counts=int(d),new_ratio_quantizers=3*int(g)+4*int(d),raw_point_bytes=8)
        costs.append(row);ct.append(f"| {names[tag]} | {row['network_macs']} | {row['int8_weight_bytes']} | {row['new_products_per_point']} | {row['new_sum_states']} | {row['new_ratio_quantizers']} |")
    writecsv(HERE/'costs.csv',costs)
    (HERE/'04_公式成本与论文文段.md').write_text('# 公式、共享计算与论文表述\n\n'+(HERE/'00_设计思想与执行前审查.md').read_text().split('对任一通道a，')[1].split('先构造')[0].join(['对任一通道a，',''])+'\n\n'+ '\n'.join(ct)+'\n\n表中有理数量化器一次需商/余数及ties-to-even判断；编译器是否合并除法/取余属于实现，不把数量冒充CPU指令或FPGA周期。额外还需每簇组合N、和、平方和、跨度的乘法：每个方差/协方差比值上界6次，RCS位置比值上界4次，近零比例1次；可共享N²等乘积，未将这些算为逐点开销。原16维共享的4通道和/极值、距离极值及密度仍保留。新增组不需要排序、特征值求解或开平方，但引入整数除法与INT64状态，其真实硬件收益待另行测量。\n\n原始每点仍8B、输入仍1～511点；原型C用INT64保存平方和与乘积，模型权重INT8、偏置/累加INT32、重标定乘积INT64。总位宽界与实际导出累加界见validation.json。23维模型的网络MAC为3584，比16维3136增加14.29%，也略高于原21维3456；不能把新增特征称为免费或自动硬件更优。所有组合都保留，不以维数最小替代质量—成本判断。\n\n## 论文可用段落\n\n为区分外轮廓代理与内部点分布的贡献，本文在保留既有16维统计表示的基础上，增加范围归一化的几何二阶统计和径向速度/反射值分布描述，并设计等输入维数的冗余对照。在相同数据访问顺序、隐藏层、量化训练和校准身份下，对五种表示各训练三个随机种子，统一采用最终模型。'+answer+'新增量的公式、低点数退化以及共享扫描开销被显式记录；分类收益与局部退步均按点数、形态、距离及历史支持披露，而非仅报告最优总体分数。\n\n方差、协方差及速度比例均为已有统计思想。本轮不将它们包装成未经证实的原创算法；创新性讨论应限于有证据支撑的受约束表示组合、误差分解和质量—成本取舍。所有结果属于已多次使用的开发域，独立泛化仍待验证。\n')
    warning=json.loads((LOG/'explanation/count_precision_warning.json').read_text());coll=json.loads((LOG/'explanation/training_collision_diagnostic.json').read_text())
    (HERE/'06_数据解释与反例.md').write_text('# 如何解释这些数据\n\n1. **先解释输入差异。** 合成点簇保留相同N、旧均值/跨距/距离代理和RCS统计，使原16维逐整数相同；改变内部点分布或速度/反射分布后新增描述不同。这些反例无类别标签，只证明表示能够区分某些输入，不证明某个类别应是什么。[反例原值](../../../logs/feature_enrichment_20260917/synthetic_preflight.json)。\n\n2. **再解释统计分布。** [两类训练分布](../../../logs/feature_enrichment_20260917/train_feature_distributions.csv)与[按准确保留点数分组的真实少点训练分布](../../../logs/feature_enrichment_20260917/explanation/natural_train_by_N_and_class.csv)给出均值、分位数、零值和上界占比。两类均有重叠时，不能把一个特征直接写成确定分类规则；跨序列/传感器的因果解释没有在本轮建立。\n\n3. **最后检验分类效应。** 两组单独加、一起加和等维冗余对照用于区分条件作用及交互。修复/新增错误案例固定取首三条并附特征值，不事后挑最好看的例子；单个神经网络判断不能靠查看特征值就得到可靠因果归因。\n\n特别的替代解释：原点数编码对N=[1,2,3,4]得到'+str(warning['base_count_INT8'])+'。单点二阶散布为0；两点且有非零跨度时归一化方差为127。因此新增描述可能部分恢复丢失的低点数线索。已单列[各模型N1/N2/N≥3指标](../../../logs/feature_enrichment_20260917/explanation/performance_by_exact_low_N.json)，本矩阵没有额外训练“只修正点数”的控制，不能据此独断收益全部来自形态。\n\n确定性首100000条保留训练样本中，同16维编码的后续观测为'+str(coll['duplicate_base16_rows'])+'条，与该编码首条标签不同的为'+str(coll['opposite_label_vs_first'])+'条，其中新增量同时不同的为'+str(coll['opposite_label_and_different_extra_vs_first'])+'条。这是有界描述性检查，不是所有配对数，也不证明这些冲突都能分类解决。[口径与数值](../../../logs/feature_enrichment_20260917/explanation/training_collision_diagnostic.json)。\n\n下一步若专门处理历史混合或点数编码，应另冻结一个单变量方案及预算，保留这里的负结果，不能边看开发分数边变换主线。\n')
    (HERE/'05_反思复现与停止条件.md').write_text(f'''# 执行记录与复现

固定15条训练完成，耗时{train['wall_seconds']:.1f}秒；原点重建{prep['wall_seconds']:.1f}秒；评价{e['wall_seconds']:.1f}秒；C包验证{pkg['wall_seconds']:.1f}秒。三种子全部保留，完整16维对照复现上一轮整数模型。15个模型从点到特征/logits共{pkg['complete_point_to_logit_rows']:,}次对拍零差异，另核QAT/NumPy/C逐层一致。这些是软件一致性，不是板测或独立样本数。

{answer}

没有因为维度到16而停止，也没有单纯扩大网络。核心矩阵为两个有解释意义的统计组及等维冗余对照；对照不排除一切替代解释，尤其低点数编码、量化分辨率与重参数化可能共同影响收益。标准统计量已有文献基础；可解释性不能替代独立验证。原历史规则、GT关联、坐标未对齐/时间无上限等边界保持。

原数据、源码与旧包SHA在训练前核验，新训练启动时冻结脚本和全部新增特征数组。后续报告/审计脚本不参与模型训练。包内保存全部模型、C源码、尺度/列映射、训练归一化/校准身份、原始指标和失败分组。新C接口不表示原21维硬件已支持这些模型。

复现使用Python3.10、CPU PyTorch2.4.1、NumPy1.26.4、h5py及gcc；实际本地Python路径为`/tmp/radar_training_audit_20260915/bin/python`。C子目录可直接gcc编译并运行示例。完整重跑须在独立副本配置新LOG及备份分支，默认拒绝覆盖；以下是原执行顺序：

```bash
python docs/paper_new/feature_enrichment_2026-09-17/preflight.py
python docs/paper_new/feature_enrichment_2026-09-17/prepare.py
python docs/paper_new/feature_enrichment_2026-09-17/training_preflight.py
python docs/paper_new/feature_enrichment_2026-09-17/backup_git.py --phase before
python docs/paper_new/feature_enrichment_2026-09-17/train.py
python docs/paper_new/feature_enrichment_2026-09-17/evaluate.py
python docs/paper_new/feature_enrichment_2026-09-17/build_package.py
python docs/paper_new/feature_enrichment_2026-09-17/explain.py
python docs/paper_new/feature_enrichment_2026-09-17/report.py
python docs/paper_new/feature_enrichment_2026-09-17/final_audit.py
```

Git独立侧分支保留用户原HEAD/暂存区；结果归档与Obsidian本地共享目录SHA校验见backup_sync_receipt.json。旧模型/位流保留，无新增GPU、训练服务器、RTL/SoC或板测任务。
''')
    norm=np.load(LOG/'training_preflight/calibration.npz');cal=[]
    for tag in VARIANTS:
        col=take(tag);path=LOG/'package'/(tag+'_train_calibration.npz');np.savez(path,mean=norm['mean'][col],std=norm['std'][col],calibration=norm['calibration'],class_weights=norm['class_weights'],columns=columns(tag));cal.append(dict(tag=tag,path=str(path.relative_to(ROOT)),sha256=sha(path)))
    dump(LOG/'package/calibration_manifest.json',cal);print(answer,flush=True)
if __name__=='__main__':main()
