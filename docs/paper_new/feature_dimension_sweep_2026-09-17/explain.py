"""Exact-low-count attribution and prespecified failure tracking; no retraining."""
from dim_common import *
import csv

def point_counts(c,meta):
    if c=='clean':return np.diff(np.load(MECH/'raw/val/offsets.npy')).astype(np.int64)
    if c.startswith('sparse_'):return np.diff(np.load(OLD/'data'/c/'offsets.npy')).astype(np.int64)
    n=np.array([int(r['n']) for r in meta])
    if c.startswith('uniform_half') or c=='central_half':n=(n+1)//2
    elif c.startswith('uniform_quarter'):n=(n+3)//4
    elif c=='kept_single':n=np.array([int(r['raw_points']) for r in meta])
    return n

def bins(n):return [('N1',n==1),('N2',n==2),('N3',n==3),('N4to8',(n>=4)&(n<=8)),('Nge9',n>=9)]

def main():
    assert json.loads((LOG/'evaluation/summary.json').read_text())['status']=='PASS';start=time.monotonic();out=LOG/'explanation';out.mkdir(exist_ok=False)
    tags=['A','B']+REFERENCES+list(VARIANTS);metrics=[];dependencies=[]
    for c in CONDITIONS:
        features,y,meta=validation(c);n=point_counts(c,meta);seq=np.array([r['sequence'] for r in meta])
        for count in [1,2,3]:
            a=features[n==count]
            if not len(a):continue
            if count==1:assert not a[:,24:].any()
            if count in [2,3]:assert np.array_equal(a[:,24:28],(a[:,[16,17,19,20]]!=0).astype(np.int8)*64)
            if count==2:assert not a[:,28:].any()
            if count==3:assert np.array_equal(a[:,28:32].astype(int),-a[:,32:36].astype(int))
            dependencies.append(dict(condition=c,retained_N=count,rows=len(a),status='EXACT_INTEGER_IDENTITY'))
        for tag in tags:
            for seed in SEEDS:
                pred=np.load(LOG/'evaluation'/(tag+'_seed%d_%s_prediction.npy'%(seed,c)))
                for group,mask in bins(n):
                    if not mask.any():continue
                    m=pc.metrics(pc.cm(y[mask],pred[mask]));metrics.append(dict(tag=tag,seed=seed,condition=c,group=group,sequences=len(set(seq[mask])),both_classes=len(np.unique(y[mask]))==2,**m))
    dump(out/'exact_N_metrics.json',metrics)
    dump(out/'information_dependencies.json',dict(status='PASS',checks=dependencies,scope='N1/N2 quantile12 adds no new information given support24; N3 width4 is determined by old variances and median4 is negative asymmetry4. Performance differences on these slices can reflect shared training, parameterization and quantization, not newly observed shapes.'))
    # Detailed train distributions are descriptive and cannot create a new search.
    n=[]
    with (OLD/'data/train/observations.csv').open() as f:
        for r in csv.DictReader(f):
            if int(r['kept_row'])<0:n.append(int(r['n']))
    n=np.array(n);y=np.load(OLD/'data/train/natural_labels.npy');x=np.load(LOG/'data/train/natural.npy');assert len(n)==len(y)==len(x)==474582
    distributions=[]
    for group,mask in bins(n):
        for cls in [0,1]:
            a=x[mask&(y==cls)]
            for j,name in enumerate(PLAN['features']['new']):
                distributions.append(dict(group=group,label=cls,feature=name,samples=len(a),mean=float(a[:,j].mean()/127) if len(a) else None,q10=float(np.quantile(a[:,j],.1)/127) if len(a) else None,median=float(np.median(a[:,j])/127) if len(a) else None,q90=float(np.quantile(a[:,j],.9)/127) if len(a) else None,zero_fraction=float(np.mean(a[:,j]==0)) if len(a) else None))
    writecsv(out/'natural_train_by_exact_N.csv',distributions)
    cases=json.loads((LOG/'evaluation/error_cases.json').read_text());cache={};annotated=[]
    for case in cases:
        if case['reference'] not in ['combined23','support24']:continue
        c=case['condition'];i=case['row']
        if c not in cache:cache[c]=validation(c)[0]
        a=cache[c][i];annotated.append(dict(**case,canonical36_int8=a.tolist(),new13_normalized=(a[23:].astype(float)/127).tolist(),new13_names=PLAN['features']['new'],scope='Fixed first error/repair identities; values are not individual neural decision causality'))
    dump(out/'cases_with_features.json',annotated)
    tracked=[r for r in readcsv(LOG/'evaluation/conditional_groups.csv') if r['condition']=='uniform_quarter_1' and r['axis']=='N_x_original_shape' and r['group']=='1-2:compact']
    assert len(tracked)==len(tags)*3 and all(int(r['samples'])==116 and int(r['sequences'])==19 for r in tracked)
    writecsv(out/'previous_116_row_group.csv',tracked)
    pairs=[]
    gm={(r['tag'],int(r['seed']),r['condition'],r['group']):r for r in metrics}
    for tag,ref in PLAN['evaluation']['comparisons']:
        for c in CONDITIONS:
            for group,_ in bins(np.array([1,2,3,4,9])):
                if (tag,7,c,group) not in gm:continue
                ds=[gm[(tag,s,c,group)]['accuracy']-gm[(ref,s,c,group)]['accuracy'] for s in SEEDS]
                r=gm[(tag,7,c,group)];pairs.append(dict(tag=tag,reference=ref,condition=c,group=group,samples=r['samples'],sequences=r['sequences'],both_classes=r['both_classes'],per_seed=ds,mean=float(np.mean(ds))))
    dump(out/'low_N_paired_accuracy.json',pairs)
    # Exact input equivalence on real train observations only, no new classifier.
    kept=np.concatenate([np.load(MECH/'data/train/proxy.npy')[:,COLS],np.load(ENR/'data/train/clean.npy'),np.load(LOG/'data/train/clean.npy')],axis=1)
    natural=np.concatenate([np.load(OLD/'data/train/natural_proxy.npy')[:,COLS],np.load(ENR/'data/train/natural.npy'),np.load(LOG/'data/train/natural.npy')],axis=1)
    combined=np.concatenate([kept,natural]);labels=np.r_[np.load(MECH/'data/train/labels.npy'),np.load(OLD/'data/train/natural_labels.npy')];assert len(labels)==832362
    ambiguity=[]
    for tag in REFERENCES+list(VARIANTS):
        cols=take(tag);selected=np.ascontiguousarray(combined[:,cols]);keys=selected.view(np.dtype('V'+str(len(cols)))).ravel();unique,inv=np.unique(keys,return_inverse=True)
        counts=np.bincount(inv*2+labels,minlength=len(unique)*2).reshape(-1,2);conflict=np.all(counts>0,axis=1)
        ambiguity.append(dict(tag=tag,dim=len(cols),observations=len(labels),distinct_encoded_inputs=len(unique),conflicting_inputs=int(conflict.sum()),observations_in_conflicting_inputs=int(counts[conflict].sum()),unavoidable_train_errors=int(np.minimum(counts[:,0],counts[:,1]).sum()),scope='Exact quantized-input empirical lower bound for deterministic classifiers using only these inputs; real kept+natural train, not augmented views, F1 bound or independent generalization'))
    q={r['tag']:r for r in ambiguity}
    assert q['redundant36']['distinct_encoded_inputs']==q['support24']['distinct_encoded_inputs'] and q['redundant36']['unavoidable_train_errors']==q['support24']['unavoidable_train_errors']
    for tag,a in q.items():
        for ref,b in q.items():
            if set(take(tag))>=set(take(ref)):
                assert a['distinct_encoded_inputs']>=b['distinct_encoded_inputs'] and a['unavoidable_train_errors']<=b['unavoidable_train_errors']
    writecsv(out/'train_input_ambiguity.csv',ambiguity)
    dump(out/'summary.json',dict(status='PASS',exact_count_metric_sets=len(metrics),annotated_cases=len(annotated),tracked_group_rows=len(tracked),wall_seconds=time.monotonic()-start,scope='Post-training descriptive fine-N groups; frozen original condition/group gates remain unchanged. No new threshold, classifier, weighting or test split.'))
    print('EXPLANATION_PASS',len(metrics),len(annotated),flush=True)
if __name__=='__main__':main()
