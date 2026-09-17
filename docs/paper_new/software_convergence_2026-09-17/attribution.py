"""Post-selection interpretation of interaction and fragile groups; no refitting."""
from sw_common import *
from evaluate import composite,macro

def main():
    out=LOG/'evaluation';conditions=['clean','central_half','uniform_quarter_0','uniform_quarter_1','uniform_quarter_2','sparse_single','sparse_context']
    tags=['proxy_synthetic','proxy_natural','mean_synthetic','mean_natural'];values={};boots={};data={}
    for c in conditions:
        _,y,meta=validation(c);seq=np.array([r['sequence'] for r in meta]);names=sorted(set(seq));sid=np.searchsorted(names,seq)
        draw=np.random.default_rng(20260917).integers(len(names),size=(2000,len(names)))
        counts=np.array([np.bincount(a,minlength=len(names)) for a in draw])
        data[c]=(y,meta)
        for tag in tags:
            for seed in SEEDS:
                p=np.load(out/('%s_seed%d_%s_prediction.npy'%(tag,seed,c)))
                cm=np.bincount(sid*4+y*2+p,minlength=len(names)*4).reshape(len(names),2,2)
                values[(tag,seed,c)]=float(macro(cm.sum(0)));boots[(tag,seed,c)]=macro(np.einsum('bs,sij->bij',counts,cm))
    interactions=[]
    for c in conditions+['composite']:
        pts=[];bs=[]
        for seed in SEEDS:
            p=[];b=[]
            for tag in tags:
                p.append(composite({v:values[(tag,seed,v)] for v in conditions}) if c=='composite' else values[(tag,seed,c)])
                b.append(composite({v:boots[(tag,seed,v)] for v in conditions}) if c=='composite' else boots[(tag,seed,c)])
            pts.append(p[3]-p[1]-p[2]+p[0]);bs.append(b[3]-b[1]-b[2]+b[0])
        dist=np.mean(bs,axis=0);interactions.append(dict(condition=c,per_seed=pts,mean=float(np.mean(pts)),percentile95=np.quantile(dist,[.025,.975]).tolist()))
    summary=json.loads((out/'summary.json').read_text());reasons=[]
    for gate in summary['final_gates']:
        for r in gate['group_failures']:
            c=r['condition'];y,meta=data.get(c,(None,None))
            if y is None:_,y,meta=validation(c);data[c]=(y,meta)
            mask=next(mask for a,g,mask in allgroups(meta,c) if (a,g)==(r['axis'],r['group']))
            for seed in SEEDS:
                p=np.load(out/('%s_seed%d_%s_prediction.npy'%(gate['tag'],seed,c)));a=np.load(out/('A_seed%d_%s_prediction.npy'%(seed,c)))
                reasons.append(dict(tag=gate['tag'],seed=seed,condition=c,axis=r['axis'],group=r['group'],samples=int(mask.sum()),class0=int(np.sum(y[mask]==0)),class1=int(np.sum(y[mask]==1)),
                    old_errors=int(np.sum(a[mask]!=y[mask])),new_errors=int(np.sum(p[mask]!=y[mask])),harm=int(np.sum((a[mask]==y[mask])&(p[mask]!=y[mask]))),repair=int(np.sum((a[mask]!=y[mask])&(p[mask]==y[mask])))))
    writecsv(out/'failure_group_counts.csv',reasons)
    dump(out/'attribution.json',dict(status='PASS',post_selection=True,rule_changes=False,interaction_definition='(mean_natural - proxy_natural) - (mean_synthetic - proxy_synthetic)',interactions=interactions))
    groups=readcsv(out/'conditional_groups.csv');lines=['# 归因补充：收益为什么没有变成统一替代方案','',
        '本节是完整选型之后的解释，不用于改动门槛，也不追加训练。所有差值均为百分点。','',
        '## 表示与训练覆盖并非完全独立','',
        '交互项定义为（真实覆盖下均值−代理）−（合成覆盖下均值−代理）。它比较两种覆盖下“修正均值”的收益是否相同。区间仍为开发序列探索性区间。','',
        '| 条件 | 三种子平均交互 | 序列 95% 区间 |','| --- | ---: | --- |']
    for r in interactions:
        if r['condition'] in ['clean','central_half','sparse_single','sparse_context','composite']:lines.append('| %s | %+.4f | [%+.4f, %+.4f] |'%(r['condition'],r['mean']*100,*[v*100 for v in r['percentile95']]))
    lines+=['','## 真实少点的历史支持','',
        '以下为真实少点加历史视图的三种子平均准确率（%）。这里使用 accuracy，不与主表 Macro-F1 混淆。','',
        '| 方案 | 无历史 | 1～5 个历史 | 6 个历史 |','| --- | ---: | ---: | ---: |']
    for tag in ['A','B']+tags:
        vals=[np.mean([float(r['accuracy']) for r in groups if r['tag']==tag and r['condition']=='sparse_context' and r['axis']=='history' and r['group']==g])*100 for g in ['none','one_to_five','six']]
        lines.append('| '+tag+' | '+' | '.join('%.4f'%v for v in vals)+' |')
    lines+=['','## 小分组的绝对错误数','',
        '部分被拒绝的组仅有 116 或 121 条观测，虽然符合事先的支持门槛，百分比变化仍可由少量样本决定。不能据此说某方案对所有紧凑目标都无效；同样不能在看见结果后忽略这条保护门槛。完整类别构成与每 seed 新增/修复错误见 [失败组计数](../../../logs/software_convergence_20260917/evaluation/failure_group_counts.csv)。','',
        '均值＋真实少点的 Q16 检查在 seed 37、uniform_half_0 的 N=65～511 × intermediate 组出现 −0.5780 个准确率百分点，超过 0.5 的容差，故仍保留 Q24。这是 173 条观测组中净少判对 1 条的量级；全局 F1 很接近也不能替代局部分组检查。',
        '', '证据：[交互项](../../../logs/software_convergence_20260917/evaluation/attribution.json)、[全部条件分组](../../../logs/software_convergence_20260917/evaluation/conditional_groups.csv)。','']
    (HERE/'06_归因补充.md').write_text('\n'.join(lines))
if __name__=='__main__':main()
