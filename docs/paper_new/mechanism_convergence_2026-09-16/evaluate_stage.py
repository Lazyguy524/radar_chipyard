"""Fixed-duration comparisons, crossed mechanism effects and coverage audit."""
import argparse
import csv
import time
from common import *

def rows(p):
    with Path(p).open() as f:return list(csv.DictReader(f))
def write_csv(p,data):
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def metric(y,p):return pc.metrics(pc.cm(y,p))
def groups(meta,condition):
    n=np.array([int(r['n']) for r in meta])
    if condition.startswith('uniform_half') or condition=='central_half':n=(n+1)//2
    elif condition.startswith('uniform_quarter'):n=(n+3)//4
    elif condition=='kept_single':n=np.array([int(r['raw_points']) for r in meta])
    count=np.select([n<=2,n<=4,n<=8,n<=16,n<=32,n<=64],['1-2','3-4','5-8','9-16','17-32','33-64'],default='65-511')
    shape=np.array([r['shape_group'] for r in meta]);result=[]
    for name in ['1-2','3-4','5-8','9-16','17-32','33-64','65-511']:result.append(('retained_N',name,count==name))
    for name in sorted(set(shape)):result.append(('original_shape',name,shape==name))
    for nname in ['1-2','3-4','5-8','9-16','17-32','33-64','65-511']:
        for sname in ['elongated','intermediate','compact']:result.append(('N_x_original_shape',nname+':'+sname,(count==nname)&(shape==sname)))
    return result
def support(y,seq,mask):return mask.sum()>=100 and len(set(seq[mask]))>=3 and len(np.unique(y[mask]))==2
def native_model(path):
    c=qc.CTrace.__new__(qc.CTrace);c.lib=ctypes.CDLL(str(path/'inference_trace.so'))
    c.lib.trace_batch.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p];return c
def joint_effects(y,pred,seq,seeds,condition):
    names=sorted(set(seq));cm=np.array([[[pc.cm(y[seq==s],pred[(m,seed,condition)][seq==s]) for s in names] for seed in seeds] for m in MODES])
    rng=np.random.default_rng(20260916);qi=rng.integers(len(names),size=(2000,len(names)));si=rng.integers(len(seeds),size=(2000,len(seeds)))
    sampled=cm[:,:,qi].sum(3);diagonal=np.diagonal(sampled,axis1=-2,axis2=-1);den=sampled.sum(-1)+sampled.sum(-2)
    f=np.divide(2*diagonal,den,out=np.zeros_like(diagonal,dtype=float),where=den>0).mean(-1)
    full=np.array([[metric(y,pred[(m,seed,condition)])['macro_f1'] for seed in seeds] for m in MODES])
    definitions={'mean_with_proxy_shape':lambda a:a[1]-a[0],'shape_with_old_mean':lambda a:a[2]-a[0],
        'shape_after_mean':lambda a:a[3]-a[1],'mean_after_shape':lambda a:a[3]-a[2],
        'mean_marginal':lambda a:.5*((a[1]-a[0])+(a[3]-a[2])),
        'shape_marginal':lambda a:.5*((a[2]-a[0])+(a[3]-a[1])),
        'interaction':lambda a:a[3]-a[1]-a[2]+a[0]}
    result=[]
    for name,fun in definitions.items():
        delta=fun(f);boot=delta[si,np.arange(2000)[:,None]].mean(1);point=fun(full)
        result.append(dict(condition=condition,effect=name,per_seed=point.tolist(),mean=float(point.mean()),
            percentile95=np.quantile(boot,[.025,.975]).tolist(),bootstrap='Paired resampling of whole sequences and training seeds, 2000 repetitions; exploratory, no multiplicity/selection correction'))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['factorial','augmentation'],required=True);stage=p.parse_args().stage
    start=time.monotonic();train=json.loads((LOG/(stage+'_v2')/'summary.json').read_text());assert train['status']=='PASS'
    assert json.loads((LOG/'raw/val_summary.json').read_text())['status']=='PASS'
    out=LOG/(stage+'_evaluation');out.mkdir(exist_ok=False)
    cfg=PLAN[stage];seeds=cfg['seeds'];modes=cfg['representations'];conditions=PLAN['paired_diagnostics']['conditions']
    y=np.load(LOG/'data/val/labels.npy');meta=rows(LOG/'raw/val/metadata.csv');seq=np.array([r['sequence'] for r in meta])
    cached_groups={c:groups(meta,c) for c in conditions};pred={};metrics=[];group_rows=[];precision=[];precisions=[];snapshots=[]
    models={};sources=[HERE/'evaluate_stage.py',HERE/'plan.json',LOG/(stage+'_v2')/'summary.json',LOG/'raw/val_summary.json']
    def budget():
        if time.monotonic()-start>PLAN['budgets']['evaluation_seconds']:raise TimeoutError(stage+' evaluation budget')
    for seed in seeds:
        init=[r['initialization_sha256'] for r in train['runs'] if r['seed']==seed];assert len(set(init))==1
    for mode in modes:
        for seed in seeds:
            budget();base=LOG/(stage+'_v2')/(mode+'_seed'+str(seed));c=native_model(base/'epoch60/export');models[(mode,seed)]=c
            for epoch in [20,40,60]:snapshots.append(dict(mode=mode,seed=seed,epoch=epoch,**metric(y,np.load(base/('epoch'+str(epoch))/'val_logits.npy').argmax(1))))
            for condition in conditions:
                if condition=='clean':prediction=np.load(base/'epoch60/val_logits.npy').argmax(1)
                else:prediction=c(np.load(LOG/'raw/val'/mode/(condition+'.npy')))[-1].argmax(1)
                pred[(mode,seed,condition)]=prediction;np.save(out/(mode+'_seed'+str(seed)+'_'+condition+'_prediction.npy'),prediction.astype(np.int8))
            print(json.dumps(dict(stage=stage,mode=mode,seed=seed,predictions_done=True,seconds=round(time.monotonic()-start,2))),flush=True)
    for mode in modes:
        for seed in seeds:
            clean=pred[(mode,seed,'clean')]
            for condition in conditions:
                p=pred[(mode,seed,condition)];ref=pred[('proxy',seed,condition)];m=metric(y,p)
                metrics.append(dict(mode=mode,seed=seed,condition=condition,**m,harm_vs_clean=int(np.count_nonzero((clean==y)&(p!=y))),
                    repair_vs_clean=int(np.count_nonzero((clean!=y)&(p==y))),delta_f1_vs_clean=m['macro_f1']-metric(y,clean)['macro_f1'],
                    delta_f1_vs_proxy=m['macro_f1']-metric(y,ref)['macro_f1']))
                for axis,g,mask in cached_groups[condition]:
                    n=int(mask.sum());both=len(np.unique(y[mask]))==2
                    group_rows.append(dict(mode=mode,seed=seed,condition=condition,axis=axis,group=g,samples=n,sequences=len(set(seq[mask])),supported=support(y,seq,mask),
                        accuracy=float(np.mean(p[mask]==y[mask])) if n else None,macro_f1=metric(y[mask],p[mask])['macro_f1'] if n and both else None,
                        delta_accuracy_vs_proxy=float(np.mean(p[mask]==y[mask])-np.mean(ref[mask]==y[mask])) if n else None))
    if stage in ['factorial','augmentation']:
        for mode in [m for m in modes if m!='proxy']:
            for seed in seeds:
                c=models[(mode,seed)]
                for mb,vb in PLAN['precision']['configurations']:
                    failures=[]
                    for condition in PLAN['paired_diagnostics']['primary']:
                        budget();x=np.load(LOG/'raw/precision'/('m%d_v%d'%(mb,vb))/condition/(mode+'.npy'));p=c(x)[-1].argmax(1);ref=pred[(mode,seed,condition)]
                        delta=metric(y,p)['macro_f1']-metric(y,ref)['macro_f1']
                        np.save(out/('%s_seed%d_m%d_v%d_%s_prediction.npy'%(mode,seed,mb,vb,condition)),p.astype(np.int8))
                        precision.append(dict(mode=mode,seed=seed,mean_bits=mb,moment_bits=vb,condition=condition,**metric(y,p),delta_f1=delta,
                            harm=int(np.count_nonzero((ref==y)&(p!=y))),repair=int(np.count_nonzero((ref!=y)&(p==y)))))
                        if delta < -PLAN['precision']['tolerance_global_f1']:failures.append(dict(condition=condition,axis='global',group='all',delta=delta))
                        for axis,g,mask in cached_groups[condition]:
                            if support(y,seq,mask):
                                d=float(np.mean(p[mask]==y[mask])-np.mean(ref[mask]==y[mask]))
                                if d < -PLAN['precision']['tolerance_group_accuracy']:failures.append(dict(condition=condition,axis=axis,group=g,delta=d))
                    precisions.append(dict(mode=mode,seed=seed,mean_bits=mb,moment_bits=vb,accepted=not failures,failures=failures))
    sparse=[];sparse_groups=[];coverage=[]
    for view in ['sparse_single','sparse_context']:
        label=np.load(LOG/'raw'/view/'labels.npy');sm=rows(LOG/'raw'/view/'metadata.csv');ss=np.array([r['sequence'] for r in sm]);gm=groups(sm,view)
        for mode in modes:
            x=np.load(LOG/'raw'/view/(mode+'.npy'))
            for seed in seeds:
                budget();p=models[(mode,seed)](x)[-1].argmax(1);np.save(out/(mode+'_seed'+str(seed)+'_'+view+'_prediction.npy'),p.astype(np.int8))
                sparse.append(dict(mode=mode,seed=seed,view=view,**metric(label,p)))
                if view=='sparse_context':
                    combined_y=np.concatenate([y,label]);combined_p=np.concatenate([pred[(mode,seed,'clean')],p])
                    coverage.append(dict(mode=mode,seed=seed,original_retained_fraction=len(y)/len(combined_y),
                        retained_plus_context_probe=metric(combined_y,combined_p),
                        scope='All target-label, nonempty-GT-track validation observations only; rejected observations do not update history. Not all radar points or an autonomous tracking system.'))
                history=np.array([int(r['retained_history_used']) for r in sm]);current=np.array([int(r['raw_points']) for r in sm]);distance=np.array([float(r['current_centroid_range']) for r in sm])
                extra=[('history',v,mask) for v,mask in [('none',history==0),('one_to_five',(history>=1)&(history<6)),('six',history==6)]]
                extra+=[('current_points',str(n),current==n) for n in [1,2]]
                extra+=[('current_range',v,mask) for v,mask in [('le20',distance<=20),('20to40',(distance>20)&(distance<=40)),('gt40',distance>40)]]
                for axis,g,mask in gm+extra:
                    n=int(mask.sum());both=len(np.unique(label[mask]))==2
                    sparse_groups.append(dict(mode=mode,seed=seed,view=view,axis=axis,group=g,samples=n,sequences=len(set(ss[mask])),supported=support(label,ss,mask),
                        accuracy=float(np.mean(p[mask]==label[mask])) if n else None,macro_f1=metric(label[mask],p[mask])['macro_f1'] if n and both else None))
    effects=[];stage_pairs=[]
    if stage=='factorial':
        for condition in conditions:effects.extend(joint_effects(y,pred,seq,seeds,condition))
        gate_rows=[]
        for seed in seeds:
            clean=metric(y,pred[('proxy',seed,'clean')])['macro_f1'];drops={c:clean-metric(y,pred[('proxy',seed,c)])['macro_f1'] for c in ['uniform_quarter_0','central_half']}
            gate_rows.append(dict(seed=seed,drops=drops,trigger=any(d>=.01 for d in drops.values())))
        dump(out/'augmentation_gate.json',dict(triggered=sum(r['trigger'] for r in gate_rows)>=4,rows=gate_rows,rule=PLAN['augmentation']['trigger'],plan_sha256=sha(HERE/'plan.json')))
    else:
        for mode in modes:
            for seed in seeds:
                for condition in conditions:
                    p=pred[(mode,seed,condition)];ref=np.load(LOG/'factorial_evaluation'/(mode+'_seed'+str(seed)+'_'+condition+'_prediction.npy'))
                    stage_pairs.append(dict(mode=mode,seed=seed,condition=condition,delta_f1=metric(y,p)['macro_f1']-metric(y,ref)['macro_f1'],
                        bootstrap=pc.paired_sequence_bootstrap(y,p,ref,seq)))
    write_csv(out/'conditional_groups.csv',group_rows);write_csv(out/'sparse_groups.csv',sparse_groups)
    report=dict(status='PASS',stage=stage,metrics=metrics,snapshot_metrics=snapshots,factorial_effects=effects,precision_metrics=precision,precision_acceptance=precisions,
        sparse_metrics=sparse,coverage_policy=coverage,augmentation_vs_clean_training=stage_pairs,wall_seconds=time.monotonic()-start,source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},plan_sha256=sha(HERE/'plan.json'),
        scope='Exploratory development validation, paired input sensitivity, natural rejected-observation audit; no untouched test, no physical robustness guarantee, no new measured hardware cost')
    dump(out/'summary.json',report);print(json.dumps(dict(status='PASS',stage=stage,metric_rows=len(metrics),precision_rows=len(precision),sparse_rows=len(sparse),seconds=report['wall_seconds'])),flush=True)

if __name__=='__main__':main()
