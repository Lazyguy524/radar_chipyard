"""Matched feature ablations; no post-result gate tuning."""
from ab_common import *

def ablation_gate(e,tag):
    cfg=PLAN['evaluation'];fails=[];groupfails=[];clean=[];conditions=[]
    for s in SEEDS:
        delta=e.metrics[(tag,s,'clean')]['macro_f1']-e.metrics[('full21',s,'clean')]['macro_f1'];clean.append(delta)
        if delta < -cfg['clean_f1_max_loss_each_seed']-1e-12:fails.append('clean_seed'+str(s))
    for c in cfg['conditions']:
        f=float(np.mean([e.metrics[(tag,s,c)]['macro_f1']-e.metrics[('full21',s,c)]['macro_f1'] for s in SEEDS]))
        recall=np.mean([np.array(e.metrics[(tag,s,c)]['recall'])-e.metrics[('full21',s,c)]['recall'] for s in SEEDS],axis=0)
        conditions.append(dict(condition=c,mean_delta_f1=f,mean_delta_recall=recall.tolist()))
        if f < -cfg['all_conditions_mean_f1_max_loss']-1e-12:fails.append(c+'_f1')
        for cls,d in enumerate(recall):
            if d < -cfg['all_conditions_mean_each_class_recall_max_loss']-1e-12:fails.append(c+'_recall'+str(cls))
        for axis,g,mask,support in e.groups[c]:
            if support['supported']:
                ds=[e.groupstats[(tag,s,c)][(axis,g)]-e.groupstats[('full21',s,c)][(axis,g)] for s in SEEDS]
                if all(x<0 for x in ds) and np.mean(ds)<-.01-1e-12:groupfails.append(dict(condition=c,axis=axis,group=g,per_seed=ds,mean=float(np.mean(ds)),**support))
    ds=[float(e.score(tag,s)-e.score('full21',s)) for s in SEEDS]
    if np.mean(ds)<-cfg['composite_mean_f1_max_loss']-1e-12:fails.append('composite')
    if groupfails:fails.append('supported_group_regression')
    return dict(tag=tag,dim=VARIANTS[tag]['dim'],accepted=not fails,failures=fails,clean_delta=clean,conditions=conditions,group_failures=groupfails,composite_delta=ds,composite_mean=float(np.mean([e.score(tag,s) for s in SEEDS])))

def main():
    assert json.loads((LOG/'training/summary.json').read_text())['status']=='PASS'
    e=previous.Evaluation(LOG/'evaluation')
    # Publish previously omitted N x undefined-shape cells without changing old evidence.
    for c in PLAN['evaluation']['conditions']:
        undefined=np.array([r['shape_group']=='undefined_low_support' for r in e.meta[c]])
        if undefined.any():
            additions=[]
            for axis,name,mask,_ in e.groups[c]:
                if axis=='retained_N':
                    m=mask&undefined;samples=int(m.sum());seqs=len(set(e.seq[c][m]));both=len(np.unique(e.labels[c][m]))==2
                    additions.append(('N_x_original_shape',name+':undefined_low_support',m,dict(samples=samples,sequences=seqs,supported=samples>=100 and seqs>=3 and both)))
            e.groups[c]+=additions
    for tag in ['A','B']:
        for s in SEEDS:
            for c in PLAN['evaluation']['conditions']:e.add(tag,s,c,sw.old_prediction('factorial' if tag=='A' else 'augmentation',s,c))
    for tag in VARIANTS:
        for s in SEEDS:
            trace=Trace(LOG/'training'/(tag+'_seed'+str(s))/'epoch60/export',False)
            for c in PLAN['evaluation']['conditions']:e.add(tag,s,c,trace(e.features(c,'proxy',24)[:,keep(tag)])[-1].argmax(1))
            print(json.dumps(dict(evaluated=tag,seed=s,seconds=time.monotonic()-e.start)),flush=True)
    exact=[]
    for s in SEEDS:
        original=sw.native_model(old_export(s));merged=Trace(LOG/'preflight'/('merged_seed'+str(s)),False)
        for c in PLAN['evaluation']['conditions']:
            x=e.features(c,'proxy',24);a=original(x);b=merged(x[:,keep('dedup20')]);mismatch=[int(np.count_nonzero(v!=w)) for v,w in zip(a,b)];assert not any(mismatch)
            exact.append(dict(seed=s,condition=c,rows=len(x),layer_mismatches=mismatch))
    for tag in VARIANTS:
        for ref in ['A','B']+(['full21'] if tag!='full21' else []):e.paired(tag,ref)
    e.paired('less_shape16','dedup20')
    gates=[ablation_gate(e,tag) for tag in VARIANTS if tag!='full21'];passing=[g for g in gates if g['accepted']]
    passing.sort(key=lambda g:(g['dim'],-g['composite_mean'],g['tag']));selected=passing[0]['tag'] if passing else 'full21'
    promotion=[e.gate(tag) for tag in VARIANTS];valid=[g for g in promotion if g['accepted']]
    if valid:
        top=max(g['composite_mean'] for g in valid);near=[g for g in valid if g['composite_mean']>=top-.001-1e-12];near.sort(key=lambda g:(VARIANTS[g['tag']]['dim'],-g['composite_mean'],g['tag']));main=near[0]['tag']
    else:main='A'
    dump(e.out/'metrics.json',e.metricrows);writecsv(e.out/'conditional_groups.csv',e.grouprows);writecsv(e.out/'paired_errors.csv',e.pairrows);writecsv(e.out/'paired_sequence_intervals.csv',e.bootrows);dump(e.out/'error_cases.json',e.cases)
    summary=dict(status='PASS',wall_seconds=time.monotonic()-e.start,ablation_gates=gates,promotion_gates=promotion,decision=dict(conditional_subset=selected,main=main,alternative='B'),duplicate_exact=exact,duplicate_exact_rows=sum(x['rows'] for x in exact),sequence_names=e.names,bootstrap_repetitions=2000,scope='Reused development set; paired whole sequences, trained seeds fixed. No independent significance or formal noninferiority claim',plan_sha256=sha(HERE/'plan.json'),output_bytes=size_guard())
    dump(e.out/'summary.json',summary);print(json.dumps(summary['decision']),flush=True)
if __name__=='__main__':main()
