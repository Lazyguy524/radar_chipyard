"""Fixed development gates, all original conditions and natural sparse groups."""
import csv
import time
from protection_common import *
ev=base.module('protection_evaluation_helpers',ROOT/'docs/paper_new/mechanism_convergence_2026-09-16/evaluate_stage.py')

def main():
    start=time.monotonic();t=json.loads((LOG/'training/summary.json').read_text());assert t['status']=='PASS' and len(t['runs'])==6
    out=LOG/'evaluation';out.mkdir(exist_ok=False);cfg=PLAN['evaluation'];rules=cfg['acceptance']
    y=np.load(MECH/'data/val/labels.npy');meta=ev.rows(MECH/'raw/val/metadata.csv');seq=np.array([r['sequence'] for r in meta])
    metrics=[];group_rows=[];sparse=[];sparse_rows=[];gates=[];pairs=[]
    def old(stage,seed,condition):return np.load(MECH/(stage+'_evaluation')/('proxy_seed%d_%s_prediction.npy'%(seed,condition)))
    def budget():
        if time.monotonic()-start>PLAN['budgets']['evaluation_seconds']:raise TimeoutError('Evaluation budget')
    for run in t['runs']:
        method,seed=run['method'],run['seed'];tag=method+'_seed'+str(seed);c=native_model(LOG/'training'/tag/'epoch60/export');fail=[];outputs={}
        for condition in cfg['conditions']:
            budget();x=np.load(MECH/'data/val/proxy.npy') if condition=='clean' else np.load(MECH/'raw/val/proxy'/(condition+'.npy'))
            pred=c(x)[-1].argmax(1);outputs[condition]=pred;np.save(out/(tag+'_'+condition+'_prediction.npy'),pred.astype(np.int8))
            a,b=old('factorial',seed,condition),old('augmentation',seed,condition)
            m=ev.metric(y,pred);ma,mb=ev.metric(y,a),ev.metric(y,b)
            row=dict(method=method,seed=seed,condition=condition,**m,delta_f1_vs_A=m['macro_f1']-ma['macro_f1'],delta_f1_vs_B=m['macro_f1']-mb['macro_f1'],
                negative_flips_vs_A=int(np.count_nonzero((a==y)&(pred!=y))),positive_flips_vs_A=int(np.count_nonzero((a!=y)&(pred==y))))
            metrics.append(row)
            pairs.append(dict(method=method,seed=seed,condition=condition,reference='A',**pc.paired_sequence_bootstrap(y,pred,a,seq)))
            if row['delta_f1_vs_B'] < -rules['retained_condition_f1_loss_vs_B_max']:fail.append(dict(gate='retained_vs_B',condition=condition,delta=row['delta_f1_vs_B']))
            if condition=='clean':
                if row['delta_f1_vs_A'] < -rules['clean_f1_loss_vs_A_max']:fail.append(dict(gate='clean_vs_A',delta=row['delta_f1_vs_A']))
                bn=int(np.count_nonzero((a==y)&(b!=y)))
                if row['negative_flips_vs_A']>bn:fail.append(dict(gate='negative_flips',new=row['negative_flips_vs_A'],baseline_B=bn))
            if condition in rules['difficult_conditions'] and row['delta_f1_vs_A']<rules['difficult_f1_gain_vs_A_min']:fail.append(dict(gate='difficult_gain',condition=condition,delta=row['delta_f1_vs_A']))
            for axis,g,mask in ev.groups(meta,condition):
                n=int(mask.sum());ok=ev.support(y,seq,mask)
                group_rows.append(dict(method=method,seed=seed,condition=condition,axis=axis,group=g,samples=n,sequences=len(set(seq[mask])),supported=ok,
                    accuracy=float(np.mean(pred[mask]==y[mask])) if n else None,macro_f1=ev.metric(y[mask],pred[mask])['macro_f1'] if n and len(np.unique(y[mask]))==2 else None,
                    delta_accuracy_vs_A=float(np.mean(pred[mask]==y[mask])-np.mean(a[mask]==y[mask])) if n else None))
        for view in cfg['sparse_views']:
            budget();label=np.load(MECH/'raw'/view/'labels.npy');sm=ev.rows(MECH/'raw'/view/'metadata.csv');ss=np.array([r['sequence'] for r in sm])
            pred=c(np.load(MECH/'raw'/view/'proxy.npy'))[-1].argmax(1);np.save(out/(tag+'_'+view+'_prediction.npy'),pred.astype(np.int8))
            a,b=old('factorial',seed,view),old('augmentation',seed,view);m=ev.metric(label,pred)
            sparse.append(dict(method=method,seed=seed,view=view,**m,delta_f1_vs_A=m['macro_f1']-ev.metric(label,a)['macro_f1'],delta_f1_vs_B=m['macro_f1']-ev.metric(label,b)['macro_f1']))
            pairs.append(dict(method=method,seed=seed,condition=view,reference='A',**pc.paired_sequence_bootstrap(label,pred,a,ss)))
            hist=np.array([int(r['retained_history_used']) for r in sm]);raw=np.array([int(r['raw_points']) for r in sm]);dist=np.array([float(r['current_centroid_range']) for r in sm])
            extra=[('history','none',hist==0),('history','one_to_five',(hist>=1)&(hist<6)),('history','six',hist==6),('current_points','1',raw==1),('current_points','2',raw==2),
                   ('current_range','le20',dist<=20),('current_range','20to40',(dist>20)&(dist<=40)),('current_range','gt40',dist>40)]
            for axis,g,mask in ev.groups(sm,view)+extra:
                n=int(mask.sum());ok=ev.support(label,ss,mask);both=n and len(np.unique(label[mask]))==2
                d=float(np.mean(pred[mask]==label[mask])-np.mean(a[mask]==label[mask])) if n else None
                f1=ev.metric(label[mask],pred[mask])['macro_f1'] if both else None
                df=f1-ev.metric(label[mask],a[mask])['macro_f1'] if both else None
                sparse_rows.append(dict(method=method,seed=seed,view=view,axis=axis,group=g,samples=n,sequences=len(set(ss[mask])),supported=ok,macro_f1=f1,
                    accuracy=float(np.mean(pred[mask]==label[mask])) if n else None,delta_accuracy_vs_A=d,delta_f1_vs_A=df))
                if view=='sparse_context' and ok:
                    if d < -rules['sparse_context_accuracy_loss_vs_A_max']:fail.append(dict(gate='sparse_supported_accuracy',axis=axis,group=g,delta=d))
                    if axis+':'+g in rules['protected_sparse_context_groups'] and df < -rules['protected_sparse_f1_loss_vs_A_max']:fail.append(dict(gate='protected_sparse_f1',axis=axis,group=g,delta=df))
        gates.append(dict(method=method,seed=seed,accepted=not fail,failures=fail))
        print(json.dumps(dict(method=method,seed=seed,accepted=not fail,failures=len(fail),seconds=time.monotonic()-start)),flush=True)
    ev.write_csv(out/'conditional_groups.csv',group_rows);ev.write_csv(out/'sparse_groups.csv',sparse_rows)
    decision={method:all(r['accepted'] for r in gates if r['method']==method) for method in PLAN['training']['methods']}
    result=dict(status='PASS',metrics=metrics,sparse_metrics=sparse,paired_bootstrap=pairs,gates=gates,method_accepted=decision,
        wall_seconds=time.monotonic()-start,plan_sha256=sha(HERE/'plan.json'),source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'evaluate.py',LOG/'training/summary.json']},
        scope='Predeclared exploratory development gates, including all supported sparse-context group accuracy; no independent test, novelty or physical-cost guarantee')
    dump(out/'summary.json',result);print(json.dumps(dict(status='PASS',method_accepted=decision,seconds=result['wall_seconds'])),flush=True)
if __name__=='__main__':main()
