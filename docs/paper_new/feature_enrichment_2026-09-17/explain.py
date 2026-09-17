"""Descriptive conditional distributions and unselected error identities."""
from ex_common import *
import csv

def main():
    assert json.loads((LOG/'evaluation/summary.json').read_text())['status']=='PASS';out=LOG/'explanation';out.mkdir(exist_ok=False);rows=[]
    n=np.empty(474582,np.int32);labels=np.load(OLD/'data/train/natural_labels.npy');i=0
    with (OLD/'data/train/observations.csv').open() as f:
        for r in csv.DictReader(f):
            if int(r['kept_row'])<0:n[i]=int(r['n']);i+=1
    assert i==len(n);x=np.load(LOG/'data/train/natural.npy')
    names=PLAN['features']['geometry']+PLAN['features']['distribution']
    for label in [0,1]:
        for group,mask in [('N1',n==1),('N2',n==2),('N3to8',(n>=3)&(n<=8)),('Nge9',n>=9)]:
            z=x[mask&(labels==label)]
            for j,name in enumerate(names):rows.append(dict(label=label,retained_point_group=group,feature=name,samples=len(z),mean=float(z[:,j].mean()/127) if len(z) else None,q10=float(np.quantile(z[:,j],.1)/127) if len(z) else None,median=float(np.median(z[:,j])/127) if len(z) else None,q90=float(np.quantile(z[:,j],.9)/127) if len(z) else None,zero_fraction=float(np.mean(z[:,j]==0)) if len(z) else None,maximum_fraction=float(np.mean(z[:,j]==127)) if len(z) else None))
    writecsv(out/'natural_train_by_N_and_class.csv',rows)
    source=json.loads((LOG/'evaluation/error_cases.json').read_text());cases=[];cache={}
    for case in source:
        if case['tag'] not in ['geometry19','distribution20','combined23'] or case['reference']!='base16':continue
        c=case['condition'];i=case['row']
        if c not in cache:cache[c]=validation(c)[0]
        v=cache[c][i];cases.append(dict(**case,base16=v[:16].tolist(),added7_int8=v[16:].tolist(),added7_normalized=(v[16:].astype(float)/127).tolist(),feature_names=names,explanation_limit='Descriptor values accompany fixed first error/repair identities; no claim of a per-feature causal explanation of this neural decision'))
    dump(out/'cases_with_features.json',cases)
    # Report real same-base collisions separately: finite quantization makes these possible.
    tuples={};collisions=0;conflicting=0;changed=0;joint=0
    # Train retained subset only, deterministic first 100k; diagnostic bounded before results.
    base_x=np.load(MECH/'data/train/proxy.npy')[:100000,COLS];extra=np.load(LOG/'data/train/clean.npy')[:100000];y=np.load(MECH/'data/train/labels.npy')[:100000]
    for i,row in enumerate(base_x):
        key=row.tobytes()
        if key in tuples:
            j=tuples[key];collisions+=1;conflicting+=int(y[i]!=y[j]);changed+=int(not np.array_equal(extra[i],extra[j]));joint+=int(y[i]!=y[j] and not np.array_equal(extra[i],extra[j]))
        else:tuples[key]=i
    dump(out/'training_collision_diagnostic.json',dict(rows=len(base_x),duplicate_base16_rows=collisions,opposite_label_vs_first=conflicting,new_features_different_vs_first=changed,opposite_label_and_different_extra_vs_first=joint,scope='Post-training descriptive first100k retained train rows, not all pair counts and not a proof all ambiguous classes become separable; no new training or selection'))
    pointrows=[]
    for c in PLAN['evaluation']['conditions']:
        _,labels,meta=validation(c);nn=np.array([int(r['n']) for r in meta])
        if c.startswith('uniform_half') or c=='central_half':nn=(nn+1)//2
        elif c.startswith('uniform_quarter'):nn=(nn+3)//4
        elif c=='kept_single':nn=np.array([int(r['raw_points']) for r in meta])
        for t in VARIANTS:
            for seed in SEEDS:
                prediction=np.load(LOG/'evaluation'/(t+'_seed%d_%s_prediction.npy'%(seed,c)))
                for label,mask in [('N1',nn==1),('N2',nn==2),('Nge3',nn>=3)]:
                    if not mask.any():continue
                    metric=pc.metrics(pc.cm(labels[mask],prediction[mask]));pointrows.append(dict(tag=t,seed=seed,condition=c,retained_point_group=label,**metric))
    dump(out/'performance_by_exact_low_N.json',pointrows)
    ex,fr=base.scales();shift=int((ex+fr)[0,0]);coded=[int(np.rint((i*256)/2**shift)) for i in [1,2,3,4]]
    dump(out/'count_precision_warning.json',dict(counts=[1,2,3,4],base_count_INT8=coded,source='Frozen original output scale; count slot quantizes N/4 with ties-to-even',meaning='Gains may partly reflect low-count support cues. N1/N2 normalized variance degeneracy must not be interpreted as precise target shape; report N1/N2/ge3 separately. No dedicated count-only retraining control in this matrix.'))
    dump(out/'summary.json',dict(status='PASS',class_count_groups=len(rows),annotated_error_cases=len(cases),scope='Descriptive training distributions and reused-development identities; no independent test or individual causal attribution'))
    print('EXPLANATION_PASS',len(cases),flush=True)
if __name__=='__main__':main()
