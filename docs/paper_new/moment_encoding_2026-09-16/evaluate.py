"""Encoding comparisons to matched clean-trained seeds and precision effects."""
import time
from common_encoding import *
sys.path.insert(0,str(ROOT/'docs/paper_new/mechanism_convergence_2026-09-16'))
ev=base.module('encoding_base_evaluation',ROOT/'docs/paper_new/mechanism_convergence_2026-09-16/evaluate_stage.py')

def main():
    started=time.monotonic();out=LOG/'evaluation';out.mkdir(exist_ok=False)
    train=json.loads((LOG/'training/summary.json').read_text());assert train['status']=='PASS' and len(train['runs'])==6
    y=np.load(LOG/'data/val/labels.npy');meta=ev.rows(MECH/'raw/val/metadata.csv');seq=np.array([r['sequence'] for r in meta])
    cases=PLAN['diagnostics']['conditions'];primary=PLAN['diagnostics']['primary'];seeds=PLAN['encoding']['seeds'];cached={c:ev.groups(meta,c) for c in cases}
    metrics=[];groups=[];precision=[];accept=[];sparse=[];sources=[HERE/'evaluate.py',LOG/'training/summary.json',LOG/'preflight.json'];paired=[]
    def budget():
        if time.monotonic()-started>PLAN['budgets']['evaluation_seconds']:raise TimeoutError('Encoding evaluation budget')
    for mode in MODES:
        for seed in seeds:
            budget();directory=LOG/'training'/(mode+'_seed'+str(seed));c=ev.native_model(directory/'epoch60/export');pred={}
            for condition in cases:
                pred[condition]=np.load(directory/'epoch60/val_logits.npy').argmax(1) if condition=='clean' else c(np.load(LOG/'raw/val'/mode/(condition+'.npy')))[-1].argmax(1)
                p=pred[condition];np.save(out/(mode+'_seed'+str(seed)+'_'+condition+'_prediction.npy'),p.astype(np.int8));value=ev.metric(y,p)
                ref=np.load(MECH/'factorial_evaluation'/('moment_seed'+str(seed)+'_'+condition+'_prediction.npy'))
                metrics.append(dict(mode=mode,seed=seed,condition=condition,**value,delta_f1_vs_linear_moment=value['macro_f1']-ev.metric(y,ref)['macro_f1'],
                    harm_vs_clean=int(np.count_nonzero((pred['clean']==y)&(p!=y))),repair_vs_clean=int(np.count_nonzero((pred['clean']!=y)&(p==y)))))
                if condition in primary:paired.append(dict(mode=mode,seed=seed,condition=condition,delta_f1=value['macro_f1']-ev.metric(y,ref)['macro_f1'],bootstrap=pc.paired_sequence_bootstrap(y,p,ref,seq)))
                for axis,name,mask in cached[condition]:
                    n=int(mask.sum());both=len(np.unique(y[mask]))==2
                    groups.append(dict(mode=mode,seed=seed,condition=condition,axis=axis,group=name,samples=n,sequences=len(set(seq[mask])),supported=ev.support(y,seq,mask),
                        accuracy=float(np.mean(p[mask]==y[mask])) if n else None,macro_f1=ev.metric(y[mask],p[mask])['macro_f1'] if n and both else None,
                        delta_accuracy_vs_linear_moment=float(np.mean(p[mask]==y[mask])-np.mean(ref[mask]==y[mask])) if n else None))
            for mb,vb in PLAN['diagnostics']['precision']:
                failures=[]
                for condition in primary:
                    budget();x=np.load(LOG/'raw/precision'/('m%d_v%d'%(mb,vb))/condition/(mode+'.npy'));p=c(x)[-1].argmax(1);ref=pred[condition]
                    delta=ev.metric(y,p)['macro_f1']-ev.metric(y,ref)['macro_f1'];np.save(out/('%s_seed%d_m%d_v%d_%s_prediction.npy'%(mode,seed,mb,vb,condition)),p.astype(np.int8))
                    precision.append(dict(mode=mode,seed=seed,mean_bits=mb,moment_bits=vb,condition=condition,delta_f1=delta,
                        harm=int(np.count_nonzero((ref==y)&(p!=y))),repair=int(np.count_nonzero((ref!=y)&(p==y))),**ev.metric(y,p)))
                    if delta<-.001:failures.append(dict(condition=condition,axis='global',group='all',delta=delta))
                    for axis,name,mask in cached[condition]:
                        if ev.support(y,seq,mask):
                            d=float(np.mean(p[mask]==y[mask])-np.mean(ref[mask]==y[mask]))
                            if d<-.005:failures.append(dict(condition=condition,axis=axis,group=name,delta=d))
                accept.append(dict(mode=mode,seed=seed,mean_bits=mb,moment_bits=vb,accepted=not failures,failures=failures))
            for view in PLAN['diagnostics']['sparse_views']:
                label=np.load(LOG/'raw'/view/'labels.npy');p=c(np.load(LOG/'raw'/view/(mode+'.npy')))[-1].argmax(1)
                np.save(out/(mode+'_seed'+str(seed)+'_'+view+'_prediction.npy'),p.astype(np.int8));ref=np.load(MECH/'factorial_evaluation'/('moment_seed'+str(seed)+'_'+view+'_prediction.npy'))
                sparse.append(dict(mode=mode,seed=seed,view=view,**ev.metric(label,p),delta_f1_vs_linear_moment=ev.metric(label,p)['macro_f1']-ev.metric(label,ref)['macro_f1']))
            print(json.dumps(dict(mode=mode,seed=seed,complete=True,seconds=round(time.monotonic()-started,2))),flush=True)
    ev.write_csv(out/'groups.csv',groups)
    result=dict(status='PASS',metrics=metrics,paired_comparisons=paired,precision_metrics=precision,precision_acceptance=accept,sparse_metrics=sparse,
        wall_seconds=time.monotonic()-started,source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},plan_sha256=sha(HERE/'plan.json'),
        scope='Matched fixed-epoch clean-training encoding controls, familiar validation sequences and fixed perturbations; not independent test or final hardware Pareto evidence')
    dump(out/'summary.json',result);print(json.dumps(dict(status='PASS',seconds=result['wall_seconds'],metric_rows=len(metrics),precision_rows=len(precision))),flush=True)

if __name__=='__main__':main()
