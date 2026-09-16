"""Post-result attribution audit; no additional training or candidate selection."""
from evaluate import read_csv,groups,metric,qc
from kernel import *

def main():
    out=LOG/'attribution';out.mkdir(exist_ok=False)
    y=np.load(LOG/'data/val/labels.npy');meta=read_csv(LOG/'data/val/metadata.csv')
    seq=np.array([r['sequence'] for r in meta]);checks=[]
    for seed in PLAN['training']['seeds']:
        exp=LOG/'training'/f'moment24_seed{seed}'/'export'
        c=qc.CTrace.__new__(qc.CTrace);c.lib=ctypes.CDLL(str(exp/'inference_trace.so'))
        c.lib.trace_batch.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
        a=c(np.load(LOG/'data/val/moment16.npy'))[-1].argmax(1)
        b=np.load(LOG/'training'/f'moment24_seed{seed}'/'final_val_logits.npy').argmax(1)
        rows=[]
        for axis,name,mask in groups(meta):
            supported=mask.sum()>=100 and len(set(seq[mask]))>=3 and len(np.unique(y[mask]))==2
            rows.append(dict(axis=axis,group=name,samples=int(mask.sum()),supported=supported,
                delta_accuracy=float(np.mean(a[mask]==y[mask])-np.mean(b[mask]==y[mask])) if mask.any() else None,
                harm=int(np.count_nonzero((b[mask]==y[mask])&(a[mask]!=y[mask]))),
                repair=int(np.count_nonzero((b[mask]!=y[mask])&(a[mask]==y[mask])))))
        checks.append(dict(seed=seed,delta_f1=metric(y,a)['macro_f1']-metric(y,b)['macro_f1'],groups=rows,
            note='Q24-trained weights fixed; this isolates front-end reciprocal precision, unlike separately trained models.'))
    coordinate=[]
    for mode in ['legacy']+PLAN['training']['representations']:
        a=np.load(LOG/'data/diagnostic'/(mode+'_clean.npy'));b=np.load(LOG/'data/diagnostic'/(mode+'_xy_fraction6.npy'))
        coordinate.append(dict(mode=mode,changed_feature_rows=int(np.any(a!=b,axis=1).sum()),changed_feature_entries=int(np.count_nonzero(a!=b))))
    prep=json.loads((LOG/'data/summary.json').read_text());filters=[]
    for split,c in prep['filter_totals'].items():
        missing=c['1']+c['2'];total=sum(c.values())
        filters.append(dict(split=split,below_three=missing,total_target_track_observations=total,fraction=missing/total))
    report=dict(status='PASS',analysis_phase='POST_RESULT_ATTRIBUTION_ONLY',fixed_weight_precision_full_groups=checks,
        coordinate_quantization=coordinate,filter_coverage=filters,
        interpretation='Do not attribute independently trained model differences to reciprocal bit width. Negative variance counts are numerical defects, not evidence of harmful classification. No new trajectory, no changed predeclared decision.',
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'audit_findings.py',LOG/'evaluation/summary.json',LOG/'data/summary.json']})
    dump(out/'summary.json',report);print(json.dumps(report))

if __name__=='__main__':main()
