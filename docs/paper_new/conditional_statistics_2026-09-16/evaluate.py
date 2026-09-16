"""Integer trace checks, conditional damage and fixed-model precision analysis."""
import csv
import time
from kernel import *
sys.path.insert(0,str(ROOT/'docs/paper_new/qmlp_int8_convergence_2026-09-16'))
import common as qc
from verify import restore_qat
torch=qc.torch

def metric(y,p):return pc.metrics(pc.cm(y,p))
def read_csv(p):
    with p.open() as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def groups(meta,condition='clean'):
    n=np.array([int(r['n']) for r in meta])
    if condition in ['uniform_half','central_half']:n=(n+1)//2
    elif condition=='uniform_quarter':n=(n+3)//4
    count=np.where(n<=4,'1-4',np.where(n<=16,'5-16',np.where(n<=64,'17-64','65-511')))
    shape=np.array([r['shape_group'] for r in meta])
    return [('retained_N',g,count==g) for g in ['1-4','5-16','17-64','65-511']]+[('original_shape',g,shape==g) for g in ['elongated','intermediate','compact']]

def main():
    started=time.monotonic();out=LOG/'evaluation';out.mkdir(exist_ok=False)
    train=json.loads((LOG/'training/summary.json').read_text());assert train['status']=='SIX_MATCHED_TRAJECTORIES_COMPLETE'
    for name,h in train['source_sha256'].items():assert sha(ROOT/name)==h
    y=np.load(LOG/'data/val/labels.npy');meta=read_csv(LOG/'data/val/metadata.csv');seq=np.array([r['sequence'] for r in meta])
    dy=np.load(LOG/'data/diagnostic/labels.npy');dm=read_csv(LOG/'data/diagnostic/metadata.csv');ds=np.array([r['sequence'] for r in dm])
    predictions={};checks=[];numeric=[];diag_predictions={};all_modes=['legacy']+PLAN['training']['representations']
    for mode in all_modes:
        for seed in PLAN['training']['seeds']:
            tag=mode+'_seed'+str(seed)
            directory=(qc.LOG/'training'/f'seed{seed}') if mode=='legacy' else LOG/'training'/tag
            export=directory/('final_export' if mode=='legacy' else 'export');bundle=qc.load_export(export)
            if mode=='legacy':
                c=qc.CTrace.__new__(qc.CTrace);c.lib=ctypes.CDLL(str(export/'inference_trace.so'))
                c.lib.trace_batch.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
                full=np.load(directory/'final_val_logits.npy')
            else:
                c=qc.CTrace(export);q=restore_qat(directory/'frozen_qat.pt');x=np.load(LOG/'data/val'/(mode+'.npy'))
                check=[0,0,0];values=[]
                for offset in range(0,len(x),4096):
                    if time.monotonic()-started>PLAN['budget']['evaluation_seconds']:raise TimeoutError('Evaluation budget')
                    z=x[offset:offset+4096];ct=c(z);nt=qc.integer_trace(z,bundle)
                    with torch.inference_mode():tt=[v.numpy() for v in q(torch.tensor(z),trace=True)]
                    for i,(a,b,d) in enumerate(zip(ct,nt,tt)):check[i]+=int(np.count_nonzero(a!=b))+int(np.count_nonzero(a!=d))
                    values.append(ct[-1])
                assert not any(check);full=np.concatenate(values)
                assert np.array_equal(full,np.load(directory/'final_val_logits.npy'))
                np.save(out/(tag+'_c_full_logits.npy'),full);checks.append(dict(tag=tag,rows=len(y),layer_mismatches=check))
            predictions[tag]=full.argmax(1)
            for condition in PLAN['diagnostics']['paired_conditions']:
                dx=np.load(LOG/'data/diagnostic'/(mode+'_'+condition+'.npy'))
                logits=c(dx)[-1];np.save(out/(tag+'_'+condition+'_logits.npy'),logits)
                diag_predictions[(tag,condition)]=logits.argmax(1)
            if mode=='moment24':
                for alternative in ['moment16','uncentered16']:
                    xx=np.load(LOG/'data/val'/(alternative+'.npy'));p=c(xx)[-1].argmax(1)
                    item=dict(seed=seed,path=alternative,condition='full_validation',metrics=metric(y,p),
                        delta_macro_f1=metric(y,p)['macro_f1']-metric(y,predictions[tag])['macro_f1'],
                        harm=int(np.count_nonzero((predictions[tag]==y)&(p!=y))),repair=int(np.count_nonzero((predictions[tag]!=y)&(p==y))))
                    numeric.append(item)
                    for condition in PLAN['diagnostics']['paired_conditions']:
                        xx=np.load(LOG/'data/diagnostic'/(alternative+'_'+condition+'.npy'));p=c(xx)[-1].argmax(1);ref=diag_predictions[(tag,condition)]
                        numeric.append(dict(seed=seed,path=alternative,condition=condition,metrics=metric(dy,p),
                            delta_macro_f1=metric(dy,p)['macro_f1']-metric(dy,ref)['macro_f1'],
                            harm=int(np.count_nonzero((ref==dy)&(p!=dy))),repair=int(np.count_nonzero((ref!=dy)&(p==dy)))))
    full_metrics={tag:metric(y,p) for tag,p in predictions.items()};condition_metrics=[];group_rows=[];pairs=[]
    for seed in PLAN['training']['seeds']:
        for mode in all_modes:
            tag=mode+'_seed'+str(seed);ref_tag='proxy_scaled_seed'+str(seed)
            p=predictions[tag];ref=predictions[ref_tag]
            pairs.append(dict(mode=mode,seed=seed,condition='full_validation',reference='proxy_scaled',delta_macro_f1=metric(y,p)['macro_f1']-metric(y,ref)['macro_f1'],bootstrap=pc.paired_sequence_bootstrap(y,p,ref,seq)))
            for condition in PLAN['diagnostics']['paired_conditions']:
                pred=diag_predictions[(tag,condition)];clean=diag_predictions[(tag,'clean')];baseline=diag_predictions[(ref_tag,condition)]
                result=dict(mode=mode,seed=seed,condition=condition,**metric(dy,pred),
                    harm_vs_own_clean=int(np.count_nonzero((clean==dy)&(pred!=dy))),repair_vs_own_clean=int(np.count_nonzero((clean!=dy)&(pred==dy))),
                    delta_f1_vs_own_clean=metric(dy,pred)['macro_f1']-metric(dy,clean)['macro_f1'],
                    delta_f1_vs_proxy=metric(dy,pred)['macro_f1']-metric(dy,baseline)['macro_f1'])
                condition_metrics.append(result)
                if mode in ['moment24','moment16']:
                    pairs.append(dict(mode=mode,seed=seed,condition=condition,reference='proxy_scaled',delta_macro_f1=result['delta_f1_vs_proxy'],bootstrap=pc.paired_sequence_bootstrap(dy,pred,baseline,ds)))
            for condition,label,metadata,sids in [('full_validation',y,meta,seq)]+[(c,dy,dm,ds) for c in PLAN['diagnostics']['paired_conditions']]:
                pred=predictions[tag] if condition=='full_validation' else diag_predictions[(tag,condition)]
                baseline=predictions[ref_tag] if condition=='full_validation' else diag_predictions[(ref_tag,condition)]
                for axis,name,mask in groups(metadata,condition):
                    n=int(mask.sum());ns=len(set(sids[mask]));both=len(np.unique(label[mask]))==2
                    supported=n>=100 and ns>=3 and both
                    group_rows.append(dict(mode=mode,seed=seed,condition=condition,axis=axis,group=name,samples=n,sequences=ns,supported=supported,
                        accuracy=float(np.mean(pred[mask]==label[mask])) if n else None,
                        macro_f1=metric(label[mask],pred[mask])['macro_f1'] if n and both else None,
                        delta_accuracy_vs_proxy=float(np.mean(pred[mask]==label[mask])-np.mean(baseline[mask]==label[mask])) if n else None))
    precision=[]
    for seed in PLAN['training']['seeds']:
        fail=[]
        for condition,label,metadata,sids in [('full_validation',y,meta,seq)]+[(c,dy,dm,ds) for c in PLAN['diagnostics']['paired_conditions']]:
            a=predictions['moment16_seed'+str(seed)] if condition=='full_validation' else diag_predictions[('moment16_seed'+str(seed),condition)]
            b=predictions['moment24_seed'+str(seed)] if condition=='full_validation' else diag_predictions[('moment24_seed'+str(seed),condition)]
            delta=metric(label,a)['macro_f1']-metric(label,b)['macro_f1']
            if delta < -PLAN['decision']['precision_tolerance_global_f1']:fail.append(dict(condition=condition,reason='global_f1',delta=delta))
            for axis,g,mask in groups(metadata,condition):
                if mask.sum()>=100 and len(set(sids[mask]))>=3 and len(np.unique(label[mask]))==2:
                    d=float(np.mean(a[mask]==label[mask])-np.mean(b[mask]==label[mask]))
                    if d < -PLAN['decision']['precision_tolerance_group_accuracy']:fail.append(dict(condition=condition,reason=axis+':'+g,delta=d))
        precision.append(dict(seed=seed,accepted_within_predeclared_development_tolerances=not fail,failures=fail))
    # Independent integer front-end quantizer on saved raw diagnostic clusters.
    frontend_src=(LOG/'native/kernel.c').read_text()+(HERE/'frontend_output.c').read_text()
    (out/'frontend.c').write_text(frontend_src)
    subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(out/'frontend.c'),'-o',str(out/'frontend.so')],check=True,timeout=30,capture_output=True)
    lib=ctypes.CDLL(str(out/'frontend.so'));lib.frontend.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p]
    points=np.load(LOG/'data/diagnostic/points_q8.npy');offsets=np.load(LOG/'data/diagnostic/offsets.npy')
    exps=json.loads((LOG/'data/output_scale_exponents.json').read_text());frontend_cases=0
    for mi,mode in enumerate(MODES):
        shift=np.ascontiguousarray(np.array(exps[mode])+(PROXY_FRACS if mode=='proxy_scaled' else FRACS),np.int32)
        expected=np.load(LOG/'data/diagnostic'/(mode+'_clean.npy'))
        for i in range(len(offsets)-1):
            q=np.ascontiguousarray(points[offsets[i]:offsets[i+1]],np.int16);got=np.empty(21,np.int8)
            lib.frontend(q.ctypes.data,len(q),mi,shift.ctypes.data,got.ctypes.data)
            assert np.array_equal(got,expected[i]);frontend_cases+=1
    feature_error=[]
    high=np.load(LOG/'data/val/moment24.npy').astype(np.int16)
    for mode in ['moment16','uncentered16']:
        low=np.load(LOG/'data/val'/(mode+'.npy')).astype(np.int16);d=np.abs(low-high)
        feature_error.append(dict(mode=mode,disagreement_by_feature=np.mean(d!=0,axis=0).tolist(),mean_abs_output_lsb=np.mean(d,axis=0).tolist(),max_abs_output_lsb=np.max(d,axis=0).tolist()))
    write_csv(out/'conditional_groups.csv',group_rows)
    report=dict(status='PASS',full_metrics=full_metrics,condition_metrics=condition_metrics,paired_comparisons=pairs,
        fixed_moment24_model_precision=numeric,precision_acceptance=precision,feature_precision_error=feature_error,
        integer_checks=checks,frontend_clean_cases=frontend_cases,wall_seconds=time.monotonic()-started,
        plan_sha256=sha(HERE/'plan.json'),source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'evaluate.py',HERE/'frontend_output.c',qc.HERE/'common.py',qc.HERE/'verify.py']},
        scope='Exploratory paired sensitivity and natural groups; no new independent test or actual hardware-cost evidence')
    dump(out/'summary.json',report);print(json.dumps(dict(status='PASS',full_metrics=full_metrics,precision_acceptance=precision,wall_seconds=report['wall_seconds'])),flush=True)

if __name__=='__main__':main()
