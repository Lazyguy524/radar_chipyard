#!/usr/bin/env python3
"""One frozen-model diagnostic; smoke must pass before the full validation phase."""
import argparse
import csv
import ctypes
import gzip
import json
import time
import numpy as np
from pilot_common import HERE,ROOT,LOG,PLAN,MODES,Native,reconstruct,cm,metrics,paired_sequence_bootstrap,sha


def group_values(rows):
    result={k:[] for k in ['point_count','boundary','shape','angle','range','window']}
    for r in rows:
        n=int(r['n'])
        result['point_count'].append(str(next(x for x in PLAN['groups']['point_count_upper_edges'] if n<=x)))
        result['boundary'].append('power_of_two' if n&(n-1)==0 else 'power_plus_one' if (n-1)&(n-2)==0 else 'other')
        ratio=float(r['minor_major_ratio'])
        result['shape'].append('line_like' if ratio<=.1 else 'elongated' if ratio<=.5 else 'rounder')
        angle=abs(float(r['principal_angle_degrees']))
        result['angle'].append('isotropic_or_undefined' if ratio>.5 else '0_30' if angle<30 else '30_60' if angle<60 else '60_90')
        d=float(r['centroid_range']);result['range'].append('<20' if d<20 else '20_40' if d<40 else '40_80' if d<80 else '80_plus')
        w=float(r['window_seconds']);result['window'].append('<=0.3s' if w<=.3 else '0.3_1s' if w<=1 else '>1s')
    return {k:np.asarray(v) for k,v in result.items()}


def crosscheck_integer_model(native,x):
    # Existing independent trace wrapper, using the same new validation inputs.
    lib=ctypes.CDLL(str(ROOT/'logs/training_server_recovery_20260915/integer_recheck/feature21/_trace_build/radar_mlp_trace.so'))
    fn=lib.radar_mlp_infer_trace;fn.argtypes=[ctypes.c_void_p]*4;fn.restype=None
    expected=np.empty((len(x),2),dtype=np.int32)
    a=np.empty(64,dtype=np.int8);b=np.empty(32,dtype=np.int8)
    for i in range(len(x)):fn(x[i].ctypes.data,expected[i].ctypes.data,a.ctypes.data,b.ctypes.data)
    assert np.array_equal(native.infer(x),expected),'Independent frozen integer trace mismatch'
    return len(x)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['smoke','full'],required=True)
    args=parser.parse_args();start=time.monotonic()
    LOG.mkdir(parents=True,exist_ok=True)
    out=LOG/args.phase
    if args.phase=='full':
        pre=json.loads((LOG/'smoke/summary.json').read_text());assert pre['status']=='SMOKE_PASS'
        assert pre['plan_sha256']==sha(HERE/'plan.json')
    native=Native(LOG/'native')
    arrays,y,rows,reconstruction=reconstruct('val',PLAN['data']['smoke_max_rows_per_sequence'] if args.phase=='smoke' else 0,out,native)
    checked=crosscheck_integer_model(native,np.ascontiguousarray(arrays['software_reference'][:64]))
    predictions={};allmetrics={};seq=np.asarray([r['sequence_id'] for r in rows])
    for name in MODES:
        logits=native.infer(arrays[name]);np.save(out/(name+'_logits.npy'),logits)
        predictions[name]=logits.argmax(1)
        allmetrics[name]=metrics(cm(y,predictions[name]))
    base=predictions['deployment'];ref=predictions['software_reference']
    groups=group_values(rows);group_rows=[];sequence_rows=[]
    for name in MODES:
        p=predictions[name]
        allmetrics[name].update(harm_vs_deployment=int(np.count_nonzero((base==y)&(p!=y))),
            repair_vs_deployment=int(np.count_nonzero((base!=y)&(p==y))),
            harm_vs_software_reference=int(np.count_nonzero((ref==y)&(p!=y))),
            repair_vs_software_reference=int(np.count_nonzero((ref!=y)&(p==y))),
            saturated_feature_values=int(np.count_nonzero(np.abs(arrays[name].astype(np.int16))==127)))
        seq_positive=seq_negative=0
        for sid in sorted(set(seq)):
            mask=seq==sid;delta=int(np.count_nonzero(p[mask]==y[mask])-np.count_nonzero(base[mask]==y[mask]))
            seq_positive+=int(mask.sum()>=100 and delta>0);seq_negative+=int(mask.sum()>=100 and delta<0)
            sequence_rows.append(dict(mode=name,sequence=sid,samples=int(mask.sum()),correct_change_vs_deployment=delta,
                accuracy_delta=delta/int(mask.sum()),**{k:v for k,v in metrics(cm(y[mask],p[mask])).items() if k in ['accuracy','macro_f1']}))
        allmetrics[name]['positive_sequences_at_least_100_samples']=seq_positive
        allmetrics[name]['negative_sequences_at_least_100_samples']=seq_negative
        if args.phase=='full':allmetrics[name]['paired_sequence_bootstrap_vs_deployment']=paired_sequence_bootstrap(y,p,base,seq)
        for axis,values in groups.items():
            for value in sorted(set(values)):
                mask=values==value;c=cm(y[mask],p[mask]);m=metrics(c)
                group_rows.append(dict(mode=name,axis=axis,group=value,samples=int(mask.sum()),
                    class0=int(np.count_nonzero(y[mask]==0)),class1=int(np.count_nonzero(y[mask]==1)),
                    accuracy=m['accuracy'],macro_f1=m['macro_f1'] if np.all(c.sum(1)>0) else '',
                    harm_vs_deployment=int(np.count_nonzero((base[mask]==y[mask])&(p[mask]!=y[mask]))),
                    repair_vs_deployment=int(np.count_nonzero((base[mask]!=y[mask])&(p[mask]==y[mask])))))
    for name,data in [('group_metrics.csv',group_rows),('sequence_metrics.csv',sequence_rows)]:
        with (out/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    selection=None;eligible=[]
    if args.phase=='full':
        assert len(y)==PLAN['data']['validation_rows_expected'] and len(set(seq))==PLAN['data']['validation_sequences_expected']
        for name in PLAN['training_gate']['eligible_modes']:
            v=allmetrics[name]
            if v['macro_f1']-allmetrics['deployment']['macro_f1']>=PLAN['training_gate']['min_macro_f1_gain_over_deployment'] and v['positive_sequences_at_least_100_samples']>=PLAN['training_gate']['min_sequences_with_positive_accuracy_change_and_at_least_100_samples']:
                eligible.append(name)
        if eligible:selection=max(eligible,key=lambda n:allmetrics[n]['macro_f1'])
    summary=dict(status='SMOKE_PASS' if args.phase=='smoke' else 'FIXED_MODEL_DIAGNOSTIC_COMPLETE',phase=args.phase,
        samples=len(y),sequences=len(set(seq)),plan_sha256=sha(HERE/'plan.json'),metrics=allmetrics,
        candidate_gate=dict(eligible=eligible,selected=selection,training_allowed=selection is not None,
            interpretation='Exploratory validation selection, not corrected significance or held-out generalization.'),
        integer_trace_crosscheck_samples=checked,reconstruction_checks=reconstruction['checks'],
        wall_seconds=time.monotonic()-start,source_sha256={**native.inputs,**{str(p.relative_to(ROOT)):sha(p) for p in [HERE/'pilot_common.py',HERE/'run_diagnostic.py']}},
        limitations=['Frozen old model; no matched retraining yet.','Full historical validation split, not an untouched final test.',
            'No historical test rows, training, GPU, RTL or board run.','Slot interventions have no verified hardware cost.','Bootstrap intervals are exploratory and not multiplicity/selection adjusted.'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
