"""Post-training tables and transparent derivations; not a new selection rule."""
from evaluate import composite,NEW
from sw_common import *

NAMES={'A':'A 原常规训练','B':'B 原扰动训练','C':'C 原保护训练',
 'proxy_synthetic':'代理＋合成少点','proxy_natural':'代理＋真实少点',
 'mean_synthetic':'均值＋合成少点','mean_natural':'均值＋真实少点'}
def main():
    d=LOG/'evaluation';summary=json.loads((d/'summary.json').read_text());metrics=json.loads((d/'metrics.json').read_text())
    mi={(r['tag'],r['seed'],r['condition']):r for r in metrics}
    def score(tag,seed,c):
        values={v:mi[(tag,seed,v)]['macro_f1'] for v in PLAN['evaluation']['conditions']}
        return composite(values) if c=='composite' else (np.mean([values['uniform_quarter_'+str(i)] for i in range(3)]) if c=='quarter_mean' else values[c])
    tags=['A','B','C']+NEW;conditions=['clean','quarter_mean','central_half','sparse_single','sparse_context','composite']
    rows=[]
    for tag in tags:
        for c in conditions:
            vs=[float(score(tag,s,c)) for s in SEEDS];rows.append(dict(tag=tag,condition=c,seed7=vs[0],seed17=vs[1],seed37=vs[2],mean=float(np.mean(vs)),min=min(vs),max=max(vs)))
    writecsv(HERE/'results.csv',rows)
    full=[]
    for r in metrics:
        cm=r['confusion_matrix'];full.append(dict(tag=r['tag'],seed=r['seed'],condition=r['condition'],samples=r['samples'],accuracy=r['accuracy'],macro_f1=r['macro_f1'],
            class0_f1=r['per_class_f1'][0],class1_f1=r['per_class_f1'][1],class0_recall=r['recall'][0],class1_recall=r['recall'][1],true0_pred0=cm[0][0],true0_pred1=cm[0][1],true1_pred0=cm[1][0],true1_pred1=cm[1][1]))
    writecsv(d/'full_metrics.csv',full)
    lines=['# 十二条训练的完整结果与判断','',
        '下表为三个种子的 Macro-F1 均值（%），Q24 参考；四分之一先平均三个删点重复。数值不是独立测试结果，也不是板测性能。','',
        '| 方案 | 常规 | 四分之一 | 中心一半 | 真实少点当前帧 | 真实少点加历史 | 五项综合 |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for tag in tags:lines.append('| '+NAMES[tag]+' | '+' | '.join('%.4f'%(100*np.mean([score(tag,s,c) for s in SEEDS])) for c in conditions)+' |')
    lines+=['','## 预设门槛','',
        '常规相对 A 每 seed 最多下降 0.2 个百分点；困难条件相对 B 三 seed 平均最多下降 0.3 个百分点；支持充分组若三 seed 同向下降且平均超过 1 个百分点，则拒绝推广。综合相对 B 平均至少 +0.1 个百分点且三个 seed 均为正。候选在所选精度下重新过门槛。','',
        '| 候选 | 最终均值倒数位宽 | 综合相对 B（百分点，7/17/37） | 失败项 | 支持充分退步组数 |','| --- | ---: | --- | --- | ---: |']
    for g in summary['final_gates']:
        lines.append('| '+NAMES[g['model_tag']]+' | '+str(g['mean_bits'])+' | '+', '.join('%+.4f'%(100*x) for x in g['composite_vs_B'])+' | '+(', '.join(g['failures']) or '全部通过')+' | '+str(len(g['group_failures']))+' |')
    lines+=['','## 固定权重精度检查','',
        '| 候选 | 位宽 | 所有条件/种子通过 | 最差 F1 变化（百分点） | 最差充分组准确率变化（百分点） |','| --- | ---: | --- | ---: | ---: |']
    for r in summary['precision']:lines.append('| '+NAMES[r['tag']]+' | '+str(r['bits'])+' | '+str(r['accepted'])+' | %.4f | %.4f |'%(100*r['worst_f1_delta'],100*r['worst_group_accuracy_delta']))
    lines+=['','通过低精度容差只表示在本次数据/固定权重下可采用相应精度，不等于该均值方案通过整体推广门槛。','',
        '## 对照能解释什么','',
        '以下区间是固定三种子平均、完整序列配对重采样 2000 次的 95% 分位区间。单位为 Macro-F1 百分点。区间未校正开发集选型及多重比较，不称独立显著性证明。','',
        '| 对照 | 条件 | 差值 | 95% 区间 |','| --- | --- | ---: | --- |']
    comparisons={('proxy_natural','proxy_synthetic'),('mean_natural','mean_synthetic'),('mean_synthetic','proxy_synthetic'),('mean_natural','proxy_natural')}
    intervals=readcsv(d/'paired_sequence_intervals.csv')
    for r in intervals:
        if (r['tag'],r['reference']) in comparisons and r['seed']=='mean3' and r['condition'] in ['clean','sparse_single','sparse_context','composite']:
            lines.append('| '+NAMES[r['tag']]+' − '+NAMES[r['reference']]+' | '+r['condition']+' | %+.4f | [%+.4f, %+.4f] |'%(100*float(r['delta']),100*float(r['low']),100*float(r['high'])))
    lines+=['','## 主要反例','',
        '下面按每候选平均损失最大的充分组列前五条；完整公开数据包括不充分组。此处只作解释，不新增门槛或重新选模型。','',
        '| 候选 | 输入条件 | 分组轴 / 组 | 样本 / 序列 | 相对 A 平均准确率（百分点） |','| --- | --- | --- | ---: | ---: |']
    for g in summary['final_gates']:
        for r in sorted(g['group_failures'],key=lambda r:r['mean'])[:5]:lines.append('| '+NAMES[g['model_tag']]+' | '+r['condition']+' | '+r['axis']+' / '+r['group']+' | %d / %d | %.4f |'%(r['samples'],r['sequences'],100*r['mean']))
    lines+=['','完整证据：','',
        '- [逐种子主表](results.csv)、[所有条件/类别/混淆矩阵](../../../logs/software_convergence_20260917/evaluation/full_metrics.csv)。',
        '- [全部分组](../../../logs/software_convergence_20260917/evaluation/conditional_groups.csv)、[少点形态交叉补表](../../../logs/software_convergence_20260917/evaluation/low_support_cross_groups.csv)。',
        '- [新增/修复错误](../../../logs/software_convergence_20260917/evaluation/paired_errors.csv)、[序列区间](../../../logs/software_convergence_20260917/evaluation/paired_sequence_intervals.csv)、[可追溯错误例](../../../logs/software_convergence_20260917/evaluation/error_cases.json)。',
        '- [门槛与精度判定](../../../logs/software_convergence_20260917/evaluation/summary.json)、[训练曲线与导出](../../../logs/software_convergence_20260917/training/summary.json)。','']
    (HERE/'02_结果与选型.md').write_text('\n'.join(lines))
    # Existing historical helper has no explicit N x undefined-shape row.
    # Prove low-support shape == N<=2 and publish the redundant intersections.
    # All nonempty cells equal an already-tested N group, so no gate can change.
    extra=[]
    group_rows=readcsv(d/'conditional_groups.csv')
    for c in ['sparse_single','sparse_context']:
        meta=readcsv(MECH/'raw'/c/'metadata.csv')
        assert all((r['shape_group']=='undefined_low_support')==(int(r['n'])<=2) for r in meta)
        for r in group_rows:
            if r['condition']==c and r['axis']=='retained_N' and r['group']=='1-2':
                extra.append(dict(r,axis='N_x_original_shape',group='1-2:undefined_low_support',equivalent_existing_group='retained_N:1-2'))
    writecsv(d/'low_support_cross_groups.csv',extra)
    # Physical-width derivations use integer enumeration, not measured FPGA data.
    bounds={}
    for bits in (12,16,24):
        products=[]
        for n in range(1,512):
            q,r=divmod(1<<bits,n);inv=q+int(2*r>n or (2*r==n and q%2))
            products.append((n-1)*65535*inv)
        maximum=max(products);assert maximum<2**63
        bounds[str(bits)]=dict(max_centered_sum_times_inverse=maximum,signed_product_bits=maximum.bit_length()+1,logical_inverse_table_bits=512*(bits+1),host_storage='Q24/Q16 uint32[512]; Q12 integer division, not compressed ROM')
    dump(d/'cost_and_widths.json',dict(single_pass=True,network_MACs=3456,weight_bytes=3456,bias_bytes=392,input_bits=16,centered_difference_bits=17,direct_sum_signed_bits=25,centered_sum_signed_bits=26,
        mean_additional_per_point_subtractions=4,mean_additional_per_cluster_multiplications=4,mean_shared_inverse_reads_per_cluster=1,extra_per_point_second_moment_products=0,precision=bounds,
        scope='Logical structural counts; no FPGA resource, throughput, latency or energy result'))
    curves=[]
    for p in sorted((LOG/'training').glob('*_seed*/summary.json')):
        r=json.loads(p.read_text());q=[x for x in r['curve'] if x['phase']=='qat'];curves.append(dict(tag=r['tag'],first10_mean_ce=float(np.mean([x['train_ce'] for x in q[:10]])),last10_mean_ce=float(np.mean([x['train_ce'] for x in q[-10:]])),last_epoch_ce=q[-1]['train_ce'],final_macro_f1=r['validation']['macro_f1'],epochs=60))
    writecsv(d/'training_curve_summary.csv',curves)
    dump(d/'report_audit.json',dict(status='PASS',low_support_cross_equivalence=True,selection_rules_unchanged=True,post_training_summary=True,curve_rows=len(curves)))
    print(json.dumps(dict(status='PASS',decision=summary['decision'])),flush=True)
if __name__=='__main__':main()
