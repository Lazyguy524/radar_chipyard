"""Physical group factorial and equal-width redundancy controls on all views."""
from ex_common import *

def enrichment_gate(e,t):
    cfg=PLAN['evaluation'];fails=[];gf=[];deltas=[]
    for s in SEEDS:
        if e.metrics[(t,s,'clean')]['macro_f1']-e.metrics[('base16',s,'clean')]['macro_f1']<-.002-1e-12:fails.append('clean_seed'+str(s))
    for c in cfg['conditions']:
        delta=np.mean([e.metrics[(t,s,c)]['macro_f1']-e.metrics[('base16',s,c)]['macro_f1'] for s in SEEDS]);recall=np.mean([np.array(e.metrics[(t,s,c)]['recall'])-e.metrics[('base16',s,c)]['recall'] for s in SEEDS],axis=0)
        deltas.append(dict(condition=c,mean_f1_delta=float(delta),mean_recall_delta=recall.tolist()))
        if delta<-.003-1e-12:fails.append(c+'_f1')
        for j,v in enumerate(recall):
            if v<-.005-1e-12:fails.append(c+'_recall'+str(j))
        for axis,g,mask,sup in e.groups[c]:
            if sup['supported']:
                ds=[e.groupstats[(t,s,c)][(axis,g)]-e.groupstats[('base16',s,c)][(axis,g)] for s in SEEDS]
                if max(ds)<0 and np.mean(ds)<-.01-1e-12:gf.append(dict(condition=c,axis=axis,group=g,per_seed=ds,mean=float(np.mean(ds)),**sup))
    ds=[float(e.score(t,s)-e.score('base16',s)) for s in SEEDS]
    if min(ds)<=0 or np.mean(ds)<.001-1e-12:fails.append('minimum_composite_gain')
    if gf:fails.append('supported_group_regression')
    redundancy=None
    if t=='combined23':
        redundancy=[float(e.score(t,s)-e.score('redundant23',s)) for s in SEEDS]
        if min(redundancy)<=0 or np.mean(redundancy)<.001-1e-12:fails.append('same_dimension_control')
    return dict(tag=t,accepted=not fails,failures=fails,conditions=deltas,group_failures=gf,composite_delta=ds,composite_mean=float(np.mean([e.score(t,s) for s in SEEDS])),composite_vs_redundancy=redundancy)

def main():
    assert json.loads((LOG/'training/summary.json').read_text())['status']=='PASS';e=previous.Evaluation(LOG/'evaluation');e.arrays={}
    for c in PLAN['evaluation']['conditions']:
        e.arrays[(c,'new',24)]=validation(c)[0]
        shape=np.array([r['shape_group'] for r in e.meta[c]])
        for other in sorted(set(shape)-{'elongated','intermediate','compact'}):
            for axis,g,mask,_ in list(e.groups[c]):
                if axis=='retained_N':
                    m=mask&(shape==other);n=int(m.sum());seq=len(set(e.seq[c][m]));both=len(np.unique(e.labels[c][m]))==2
                    e.groups[c].append(('N_x_original_shape',g+':'+other,m,dict(samples=n,sequences=seq,supported=n>=100 and seq>=3 and both)))
    for t in ['A','B']:
        for s in SEEDS:
            for c in PLAN['evaluation']['conditions']:e.add(t,s,c,sw.old_prediction('factorial' if t=='A' else 'augmentation',s,c))
    for t in VARIANTS:
        for s in SEEDS:
            trace=Trace(LOG/'training'/(t+'_seed'+str(s))/'epoch60/export',False)
            for c in PLAN['evaluation']['conditions']:
                prediction=trace(e.arrays[(c,'new',24)][:,take(t)])[-1].argmax(1)
                if t=='base16':assert np.array_equal(prediction,np.load(ABL/'evaluation'/('less_shape16_seed%d_%s_prediction.npy'%(s,c))))
                e.add(t,s,c,prediction)
            print(json.dumps(dict(tag=t,seed=s,seconds=time.monotonic()-e.start)),flush=True)
    contrasts=[('geometry19','base16'),('distribution20','base16'),('combined23','base16'),('redundant23','base16'),('combined23','geometry19'),('combined23','distribution20'),('combined23','redundant23')]
    for t,r in contrasts:e.paired(t,r)
    for t in VARIANTS:
        for r in ['A','B']:e.paired(t,r)
    interaction=[]
    for c in PLAN['evaluation']['conditions']+['composite']:
        values=[];boots=[]
        for s in SEEDS:
            def value(t):return e.score(t,s) if c=='composite' else e.metrics[(t,s,c)]['macro_f1']
            def boot(t):return e.score(t,s,True) if c=='composite' else e.boot[(t,s,c)]
            v=value('combined23')-value('geometry19')-value('distribution20')+value('base16');b=boot('combined23')-boot('geometry19')-boot('distribution20')+boot('base16');values.append(v);boots.append(b)
        bs=np.mean(boots,axis=0);interaction.append(dict(condition=c,per_seed=values,mean=float(np.mean(values)),low=float(np.quantile(bs,.025)),high=float(np.quantile(bs,.975))))
    gates=[enrichment_gate(e,t) for t in ['geometry19','distribution20','combined23']];passing=[g for g in gates if g['accepted']]
    if passing:
        high=max(g['composite_mean'] for g in passing);near=[g for g in passing if g['composite_mean']>=high-.001-1e-12];near.sort(key=lambda g:({'geometry19':3,'distribution20':2,'combined23':5}[g['tag']],VARIANTS[g['tag']]['dim'],-g['composite_mean']));conditional=near[0]['tag']
    else:conditional='base16'
    promotion=[e.gate(t) for t in VARIANTS];valid=[g for g in promotion if g['accepted'] and g['tag'] in [r['tag'] for r in passing]]
    if valid:
        top=max(g['composite_mean'] for g in valid);near=[g for g in valid if g['composite_mean']>=top-.001-1e-12]
        near.sort(key=lambda g:({'geometry19':3,'distribution20':2,'combined23':5}[g['tag']],VARIANTS[g['tag']]['dim'],-g['composite_mean']));main=near[0]['tag']
    else:main='A'
    dump(e.out/'metrics.json',e.metricrows);writecsv(e.out/'conditional_groups.csv',e.grouprows);writecsv(e.out/'paired_errors.csv',e.pairrows);writecsv(e.out/'paired_sequence_intervals.csv',e.bootrows);dump(e.out/'error_cases.json',e.cases);dump(e.out/'interaction.json',interaction)
    dump(e.out/'summary.json',dict(status='PASS',wall_seconds=time.monotonic()-e.start,enrichment_gates=gates,promotion_gates=promotion,decision=dict(conditional=conditional,main=main,alternative='B'),bootstrap_repetitions=2000,sequence_names=e.names,scope='Reused development data, paired whole-sequence intervals with three trained seeds fixed; no independent generalization/causality proof',output_bytes=size_guard(),plan_sha256=sha(HERE/'plan.json')))
    print('DECISION',conditional,main,flush=True)
if __name__=='__main__':main()
