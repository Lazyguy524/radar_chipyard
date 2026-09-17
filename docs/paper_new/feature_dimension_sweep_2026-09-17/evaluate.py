"""All conditions, support-controlled contrasts, fixed gates and paired errors."""
from dim_common import *
from gates import gate,choose

def main():
    assert json.loads((LOG/'training/summary.json').read_text())['status']=='PASS';e=previous.Evaluation(LOG/'evaluation');e.arrays={}
    for condition in CONDITIONS:
        e.arrays[(condition,'new',24)]=validation(condition)[0]
        shape=np.array([r['shape_group'] for r in e.meta[condition]])
        for other in sorted(set(shape)-{'elongated','intermediate','compact'}):
            for axis,name,mask,_ in list(e.groups[condition]):
                if axis=='retained_N':
                    m=mask&(shape==other);n=int(m.sum());seq=len(set(e.seq[condition][m]));both=len(np.unique(e.labels[condition][m]))==2
                    e.groups[condition].append(('N_x_original_shape',name+':'+other,m,dict(samples=n,sequences=seq,supported=n>=100 and seq>=3 and both)))
    for tag in ['A','B']:
        for seed in SEEDS:
            for c in CONDITIONS:e.add(tag,seed,c,sw.old_prediction('factorial' if tag=='A' else 'augmentation',seed,c))
    for tag in REFERENCES+list(VARIANTS):
        for seed in SEEDS:
            trace=Trace(export_path(tag,seed),False)
            for c in CONDITIONS:
                pred=trace(e.arrays[(c,'new',24)][:,take(tag)])[-1].argmax(1)
                if tag in REFERENCES:assert np.array_equal(pred,np.load(ENR/'evaluation'/(tag+'_seed%d_%s_prediction.npy'%(seed,c))))
                e.add(tag,seed,c,pred)
            print(json.dumps(dict(tag=tag,seed=seed,seconds=time.monotonic()-e.start)),flush=True)
    pairs=set(tuple(p) for p in PLAN['evaluation']['comparisons'])
    for tag in VARIANTS:
        for ref in ['A','B','base16','combined23']:pairs.add((tag,ref))
    for tag,ref in sorted(pairs):e.paired(tag,ref)
    results=[gate(e,t) for t in VARIANTS];promotion=[e.gate(t) for t in REFERENCES+list(VARIANTS)]
    fallback=dict(tag='combined23',composite_mean=float(np.mean([e.score('combined23',s) for s in SEEDS])))
    passed=[g for g in results if g['accepted']];conditional=choose(passed+[fallback])
    promoted={g['tag'] for g in promotion if g['accepted']};both=[g for g in passed+[fallback] if g['tag'] in promoted]
    main=choose(both) if both else 'A'
    interaction=[]
    for c in CONDITIONS+['composite']:
        values=[];draws=[]
        for s in SEEDS:
            def value(t):return e.score(t,s) if c=='composite' else e.metrics[(t,s,c)]['macro_f1']
            def boot(t):return e.score(t,s,True) if c=='composite' else e.boot[(t,s,c)]
            values.append(value('quantile32')-value('width28')-value('asymmetry28')+value('support24'))
            draws.append(boot('quantile32')-boot('width28')-boot('asymmetry28')+boot('support24'))
        b=np.mean(draws,axis=0);interaction.append(dict(condition=c,per_seed=values,mean=float(np.mean(values)),low=float(np.quantile(b,.025)),high=float(np.quantile(b,.975))))
    dump(e.out/'interaction.json',interaction);dump(e.out/'metrics.json',e.metricrows);writecsv(e.out/'conditional_groups.csv',e.grouprows)
    writecsv(e.out/'paired_errors.csv',e.pairrows);writecsv(e.out/'paired_sequence_intervals.csv',e.bootrows);dump(e.out/'error_cases.json',e.cases)
    dump(e.out/'summary.json',dict(status='PASS',wall_seconds=time.monotonic()-e.start,dimension_gates=results,promotion_gates=promotion,decision=dict(conditional=conditional,main=main,alternative='B'),sequence_names=e.names,bootstrap_repetitions=2000,scope='Reused development data; fixed33 new trajectories and6 reused models; paired intervals do not correct selection or establish independent significance',output_bytes=size_guard(),plan_sha256=sha(HERE/'plan.json')))
    print('DECISION',conditional,main,flush=True)
if __name__=='__main__':main()
