"""Post-result mechanism attribution and exact redundancy, without model search."""
import csv
from common import *
from evaluate_stage import metric,rows,support,write_csv

def gamma(n):
    n=np.asarray(n,dtype=np.int64);d=np.left_shift(1,np.ceil(np.log2(n)).astype(int));return n/d
def main():
    out=LOG/'mechanism_audit';out.mkdir(exist_ok=False);duplicates=[];quantization=[]
    for mode in MODES:
        a=np.load(LOG/'data/train'/(mode+'.npy'));b=np.load(LOG/'data/val'/(mode+'.npy'))
        for i in range(21):
            for j in range(i+1,21):
                if np.array_equal(a[:,i],a[:,j]) and np.array_equal(b[:,i],b[:,j]):duplicates.append(dict(mode=mode,columns=[i,j],train_equal_rows=len(a),validation_equal_rows=len(b)))
        quantization.append(dict(mode=mode,train_zero_fraction=(a==0).mean(0).tolist(),validation_zero_fraction=(b==0).mean(0).tolist(),
            train_at_limit=(np.abs(a)==127).mean(0).tolist(),validation_at_limit=(np.abs(b)==127).mean(0).tolist(),
            note='At-limit values are not identical to actual overflow/clipping counts. Exact duplicate inputs need not be redundant under a changed representation.'))
    meta=rows(LOG/'raw/val/metadata.csv');seq=np.array([r['sequence'] for r in meta]);n=np.array([int(r['n']) for r in meta]);y=np.load(LOG/'data/val/labels.npy')
    g0=gamma(n);phase_rows=[]
    for stage in ['factorial','augmentation']:
        summary=LOG/(stage+'_evaluation')/'summary.json'
        if not summary.exists():continue
        for seed in PLAN[stage]['seeds']:
            for condition in ['uniform_half_0','uniform_quarter_0','central_half']:
                retained=(n+3)//4 if condition=='uniform_quarter_0' else (n+1)//2
                difference=gamma(retained)-g0
                bins=np.select([difference<1e-12,difference<=.05,difference<=.15],['zero','le_0.05','0.05_to_0.15'],default='gt_0.15')
                for mode in PLAN[stage]['representations']:
                    p=np.load(LOG/(stage+'_evaluation')/(mode+'_seed'+str(seed)+'_'+condition+'_prediction.npy'))
                    ref=np.load(LOG/(stage+'_evaluation')/('proxy_seed'+str(seed)+'_'+condition+'_prediction.npy'))
                    for name in ['zero','le_0.05','0.05_to_0.15','gt_0.15']:
                        mask=bins==name;nrows=int(mask.sum());both=len(np.unique(y[mask]))==2
                        phase_rows.append(dict(stage=stage,mode=mode,seed=seed,condition=condition,mean_attenuation_change_group=name,samples=nrows,sequences=len(set(seq[mask])),
                            supported=support(y,seq,mask),macro_f1=metric(y[mask],p[mask])['macro_f1'] if nrows and both else None,
                            delta_accuracy_vs_proxy=float(np.mean(p[mask]==y[mask])-np.mean(ref[mask]==y[mask])) if nrows else None,
                            interpretation='Association conditional on count-bin attenuation changes; groups also differ in point count and history, not isolated physical causality'))
    a=np.load(LOG/'data/val/proxy.npy').astype(np.int16);b=np.load(LOG/'data/val/mean.npy').astype(np.int16);delta=np.abs(a-b)
    write_csv(out/'count_phase_groups.csv',phase_rows)
    result=dict(status='PASS',exact_duplicate_pairs=duplicates,quantization_profiles=quantization,
        count_bin_mean=dict(formula='old mean = floor(sum / 2^ceil(log2(N))); before rounding its multiplicative attenuation is N / 2^ceil(log2(N))',
            mean_attenuation=float(g0.mean()),fraction_exact_power_of_two=float(np.mean(g0==1)),attenuation_quantiles=np.quantile(g0,[0,.1,.5,.9,1]).tolist(),
            note='Attenuation is a deterministic numerical property, not the fraction of classification errors it causes. Uniform/central ceil-based subsampling changes N and can change this factor.'),
        mean_slot_changes=dict(columns=MEANS,any_changed_rows=int(np.any(delta[:,MEANS]!=0,axis=1).sum()),mean_abs_int8_lsb=delta[:,MEANS].mean(0).tolist(),
            p99_abs_int8_lsb=np.quantile(delta[:,MEANS],.99,axis=0).tolist()),
        scope='Post-result explanatory audit, no feature deletion, no retraining, no new physical cost evidence',
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'explain_mechanisms.py',LOG/'factorial_evaluation/summary.json']})
    dump(out/'summary.json',result);print(json.dumps(result))

if __name__=='__main__':main()
