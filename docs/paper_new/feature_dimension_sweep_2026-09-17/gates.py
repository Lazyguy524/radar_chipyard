"""Predeclared gates, separable from inference and report rendering."""
from dim_common import *

def gate(e,tag):
    reference='combined23';fail=[];groups=[];conditions=[]
    for seed in SEEDS:
        if e.metrics[(tag,seed,'clean')]['macro_f1']-e.metrics[(reference,seed,'clean')]['macro_f1']<-.002-1e-12:fail.append('clean_seed'+str(seed))
    for c in CONDITIONS:
        delta=float(np.mean([e.metrics[(tag,s,c)]['macro_f1']-e.metrics[(reference,s,c)]['macro_f1'] for s in SEEDS]))
        recall=np.mean([np.array(e.metrics[(tag,s,c)]['recall'])-e.metrics[(reference,s,c)]['recall'] for s in SEEDS],axis=0)
        conditions.append(dict(condition=c,f1_delta=delta,recall_delta=recall.tolist()))
        if delta<-.003-1e-12:fail.append(c+'_f1')
        for cls,value in enumerate(recall):
            if value<-.005-1e-12:fail.append(c+'_recall'+str(cls))
        for axis,name,mask,support in e.groups[c]:
            if support['supported']:
                d=[e.groupstats[(tag,s,c)][(axis,name)]-e.groupstats[(reference,s,c)][(axis,name)] for s in SEEDS]
                if max(d)<0 and np.mean(d)<-.01-1e-12:groups.append(dict(condition=c,axis=axis,group=name,per_seed=d,mean=float(np.mean(d)),**support))
    if groups:fail.append('supported_group_regression')
    d=[float(e.score(tag,s)-e.score(reference,s)) for s in SEEDS];family=VARIANTS[tag]['family'];additional={}
    if family=='reduction':
        if np.mean(d)<-.001-1e-12:fail.append('composite_loss')
    elif family!='redundant_control':
        if np.mean(d)<.001-1e-12 or min(d)<=0:fail.append('minimum_composite_gain')
    if family=='quantile':
        for ref in ['support24']+(['redundant36'] if tag=='full36' else []):
            ds=[float(e.score(tag,s)-e.score(ref,s)) for s in SEEDS];additional[ref]=ds
            if np.mean(ds)<.001-1e-12 or min(ds)<=0:fail.append('gain_vs_'+ref)
    if family=='redundant_control':fail.append('control_only')
    return dict(tag=tag,accepted=not fail,failures=fail,conditions=conditions,group_failures=groups,composite_delta=d,additional=additional,composite_mean=float(np.mean([e.score(tag,s) for s in SEEDS])))

def choose(candidates):
    high=max(r['composite_mean'] for r in candidates);near=[r for r in candidates if r['composite_mean']>=high-.001-1e-12]
    def priority(r):
        c=costs(r['tag']);return (c['channel_sorts']>0,c['extra_products_per_point'],c['network_macs'],c['ratio_quantizers'],-r['composite_mean'])
    return min(near,key=priority)['tag']
