"""Post-result plain-language synthesis, without changing selection or models."""
import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOG=ROOT/'logs/feature_enrichment_20260917'

def read(p):
    with p.open() as f:return list(csv.DictReader(f))

def main():
    result={r['tag']:r for r in read(HERE/'results.csv')}
    summary=json.loads((LOG/'evaluation/summary.json').read_text())
    assert summary['decision']==dict(conditional='combined23',main='A',alternative='B')
    gates={r['tag']:r for r in summary['enrichment_gates']}
    chosen=result['combined23'];reference=result['base16']
    delta=lambda key:100*(float(chosen[key])-float(reference[key]))
    intervals=read(LOG/'evaluation/paired_sequence_intervals.csv')
    def ci(ref):return next(r for r in intervals if r['tag']=='combined23' and r['reference']==ref and r['condition']=='composite' and r['seed']=='mean3')
    promo=next(r for r in summary['promotion_gates'] if r['tag']=='combined23')
    assert len(promo['group_failures'])==1
    bad=promo['group_failures'][0]
    lines=['# 这次实验究竟说明了什么','',
        '**值得保留的是“16维基础＋7个分布描述”的23维方案。它通过了相对16维的本轮平衡要求；旧A仍保留为主基线，因为还有一个细分条件没有过关。**','',
        f"三种子平均综合分从{100*float(reference['composite']):.3f}%到{100*float(chosen['composite']):.3f}%，提升{delta('composite'):.3f}个百分点；常规从{100*float(reference['clean']):.3f}%到{100*float(chosen['clean']):.3f}%。这里的综合分等权计入常规、均匀四分之一、中心一半、真实少点当前帧和加历史五项。",'',
        '## 不用先记公式，先看增加了什么','',
        '- 原有跨度主要描述外轮廓。例如两个簇可以有同样的最远/最近位置、相同均值，但一个点集中在中间，一个集中在两端。几何分布组尝试把这个差别表示出来。',
        '- 速度/RCS组描述：点的径向速度有多分散、有多少接近零、反射值有多分散、反射均值偏向整个范围的哪一端。相同最大/最小值并不代表内部测量分布相同。',
        '- 本轮用四组无标签反例验证“原16维完全相同，新增量确实不同”，再用真实观测重训检验分类效果。反例本身不带行人/车辆标签，不冒充分类证据。','',
        '## 数据给出的答案','',
        f"只加几何的19维没有稳定综合收益（{100*sum(gates['geometry19']['composite_delta'])/3:+.3f}pp），单独补速度/RCS的20维有平均收益（{100*sum(gates['distribution20']['composite_delta'])/3:+.3f}pp），但真实少点的行人召回和若干紧凑组退步超限。两组一起加入的23维通过相对16维的全套要求。因此不能只按平均分或维数挑方案。",'',
        f"23维相对16维：常规{delta('clean'):+.3f}pp，均匀四分之一{delta('quarter'):+.3f}pp，中心一半{delta('central'):+.3f}pp，真实少点当前帧{delta('sparse_single'):+.3f}pp，真实少点加历史{delta('sparse_context'):+.3f}pp。**当前帧真实少点仍有损失，只是没有超过预先允许的容忍度；不能写成所有场景都改善。**",'',
        f"只复制旧输入也做成23维后，综合分为{100*float(result['redundant23']['composite']):.3f}%；真正补充信息的23维比它高{100*float(ci('redundant23')['delta']):.3f}pp，三个种子同向。新增信息的效果超过了这个特定的等维冗余对照，但它不能排除所有优化/参数化解释。",'',
        f"相对16维的序列配对95%区间为[{100*float(ci('base16')['low']):+.3f}, {100*float(ci('base16')['high']):+.3f}]pp；两组交互项的区间仍跨0，因此不能进一步宣称已证明统计上的协同效应。开发集已重复使用，区间未经选择/多重比较校正，不能写成独立泛化显著性。",'',
        '## 可以观察到哪些实际分布差别','',
        '下面只使用保留训练观测（含既有历史）的类别描述，不用于追加阈值。0类为行人，1类为车辆；每格为量化后归一化量的均值及10%～90%分位区间。','',
        '| 新增量 | 行人 | 车辆 |','| --- | --- | --- |']
    distributions=read(LOG/'train_feature_distributions.csv')
    chosen_features=[('4Var(y)/span(y)^2','y坐标的范围归一化散布'),('4Var(vr_compensated)/span(vr)^2','径向速度范围归一化散布'),('fraction_abs_vr_le_0.5_m_per_s','近零径向速度比例'),('4Var(RCS)/span(RCS)^2','反射值范围归一化散布'),('2*(mean_RCS-min_RCS)/span_RCS-1','反射均值在范围内的位置')]
    for feature,label in chosen_features:
        cells=[]
        for cls in ['0','1']:
            r=next(r for r in distributions if r['pool']=='kept' and r['label']==cls and r['feature']==feature)
            cells.append(f"{float(r['mean']):.3f} [{float(r['q10']):.3f}, {float(r['q90']):.3f}]")
        lines.append('| '+label+' | '+' | '.join(cells)+' |')
    lines+=['',
        '例如本训练域中行人的近零径向速度比例更高，但两类有重叠；还可能受到场景、运动方向、目标速度及采样方式影响。径向速度接近零不能直接说目标静止，也不能据此宣称发现普遍物理分类规律。按点数细分的数据与错误案例见06；本轮不能确定七个新增维度各自贡献了多少。','',
        '## 代价和剩下的一处主要缺口','',
        '23维网络每簇3584次MAC，相对16维3136次增加14.29%；新增统计共享同一遍点扫描，每点增加5个乘积，每簇增加7个有理数量化，使用INT64中间量。网络权重增加448B。相对原21维网络也多128次MAC。这些是软件运算/存储计数，没有换算FPGA收益。','',
        f"相对旧A的剩余失败组：{bad['condition']}（第二次均匀保留四分之一），原形态紧凑且扰动后仅1～2点，{bad['samples']}条、{bad['sequences']}个序列，三个种子准确率变化均为{100*bad['per_seed'][0]:+.3f}pp（净少判对3条，具体修复/新增错误另列）。原形态由扰动前定义，不能说1～2点本身测出了可靠的紧凑形状。故保留旧A/B，同时冻结23维候选。",'',
        '两个点的范围归一化方差恒到上界，而原点数编码又混淆N=1和N=2。下一项最值得澄清的是：只提高点数编码分辨率，能否解释或改善这个局部缺口。这里仅记录未解机制，本轮没有追加该训练、扩大搜索或修改选型门槛。独立泛化依然是单独保留的验证任务。']
    (HERE/'08_白话解释与数据观察.md').write_text('\n'.join(lines)+'\n')
    p=HERE/'README.md';s=p.read_text();marker='<!-- plain-enrichment-results -->'
    if marker not in s:
        pos=s.index('\n')+1
        brief=f"\n{marker}\n**先读这三句：已完成15条训练；23维比16维综合提高{delta('composite'):.3f}个百分点；仍有局部退步，所以保留为新软件候选，没有全面替换旧A。** [不用公式的解释与实际数据](08_白话解释与数据观察.md)。\n"
        p.write_text(s[:pos]+brief+s[pos:])
    print('INTERPRETATION_WRITTEN')

if __name__=='__main__':main()
