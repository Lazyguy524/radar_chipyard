"""Reload final candidates, independently verify integer traces and statistics."""
import csv
import gzip
import time
from common import *

def restore_qat(path):
    checkpoint=torch.load(path,map_location='cpu',weights_only=False)
    q=FrozenQAT.__new__(FrozenQAT);nn.Module.__init__(q)
    q.layers=nn.ModuleList([nn.Linear(21,64).double(),nn.Linear(64,32).double(),nn.Linear(32,2).double()])
    q.register_buffer('weight_scales',torch.ones(3,dtype=torch.float64))
    q.register_buffer('input_scales',torch.ones(3,dtype=torch.float64))
    q.register_buffer('multipliers',torch.zeros(2,dtype=torch.int64))
    q.load_state_dict(checkpoint['state_dict']);q.eval();return q

def main():
    started=time.monotonic();out=LOG/'verification';out.mkdir(exist_ok=False)
    trained=json.loads((LOG/'training/summary.json').read_text());assert trained['status']=='TWO_SEED_TRAINING_COMPLETE'
    for name,h in trained['source_sha256'].items():assert sha(ROOT/name)==h
    x=np.load(PILOT/'full/deployment.npy');y=np.load(PILOT/'full/labels.npy')
    with gzip.open(PILOT/'full/metadata.csv.gz','rt') as f:seq=np.asarray([r['sequence_id'] for r in csv.DictReader(f)])
    old=np.load(PILOT/'full/deployment_logits.npy').argmax(1)
    rng=np.random.default_rng(20260916)
    stress=np.concatenate([rng.integers(-127,128,(1024,21),dtype=np.int16).astype(np.int8),
        np.zeros((1,21),np.int8),np.full((1,21),127,np.int8),np.full((1,21),-127,np.int8),
        np.tile(np.asarray([127,-127]*10+[127],np.int8),(1,1))])
    checks=[];pairs=[];group_rows=[]
    for seed in PLAN['training']['seeds']:
        base=LOG/'training'/f'seed{seed}';export=base/'final_export'
        bundle=load_export(export);q=restore_qat(base/'frozen_qat.pt');cex=CTrace(export)
        b=q.export()
        assert b['multipliers']==bundle['multipliers']
        for p,r in zip(b['layers'],bundle['layers']):
            assert np.array_equal(p['weight'],r['weight']) and np.array_equal(p['bias'],r['bias'])
        mismatches=[0,0,0];c_outputs=[];max_act=[0,0,0];sat=[0,0]
        for a in [x,stress]:
            for offset in range(0,len(a),4096):
                if time.monotonic()-started>PLAN['budgets']['verification_timeout_seconds']:raise TimeoutError('Verification budget')
                z=a[offset:offset+4096];nt=integer_trace(z,bundle);ct=cex(z)
                with torch.inference_mode():tt=[v.numpy() for v in q(torch.tensor(z),trace=True)]
                for i,(n,c,t) in enumerate(zip(nt,ct,tt)):
                    mismatches[i]+=int(np.count_nonzero(n!=c))+int(np.count_nonzero(n!=t))
                    max_act[i]=max(max_act[i],int(np.abs(n).max()))
                if a is x:
                    c_outputs.append(ct[-1])
                    for i in range(2):sat[i]+=int(np.count_nonzero(ct[i]==127))
        assert not any(mismatches),mismatches
        logits=np.concatenate(c_outputs);saved=np.load(base/'final_val_logits.npy')
        assert np.array_equal(logits,saved)
        state=hashlib.sha256(b''.join(v.numpy().tobytes() for v in q.state_dict().values())).hexdigest()
        sample=x[:1024]
        with torch.inference_mode():
            reference=q(torch.tensor(sample),trace=True)[-1].numpy()
            for batch in [1,17,32,1024]:
                got=np.concatenate([q(torch.tensor(sample[i:i+batch]),trace=True)[-1].numpy() for i in range(0,len(sample),batch)])
                assert np.array_equal(got,reference)
            order=rng.permutation(len(sample));permuted=q(torch.tensor(sample[order]),trace=True)[-1].numpy()
            assert np.array_equal(permuted,reference[order])
        assert state==hashlib.sha256(b''.join(v.numpy().tobytes() for v in q.state_dict().values())).hexdigest()
        # C scale parser semantics must reproduce exported integer multipliers.
        import re
        scala=(export/'Radar_frozen_qmlpParams.scala').read_text()
        for i in [1,2]:
            vals=[float(re.search(r'val l'+str(i)+k+r' = ([^\n]+)',scala).group(1)) for k in ['InputScale','WeightScale','OutputScale']]
            assert int(np.floor(vals[0]*vals[1]/vals[2]*65536+0.5))==bundle['multipliers'][i-1]
        measured=metric(y,logits.argmax(1));summary=json.loads((base/'summary.json').read_text())
        assert measured==summary['qat_validation']
        prediction=logits.argmax(1);fp=np.load(base/'warmup_val_logits.npy').argmax(1)
        ptq=np.load(base/'ptq_val_logits.npy').argmax(1)
        for name,baseline in [('old_deployment',old),('folded_warmup',fp),('ptq',ptq)]:
            pair=dict(seed=seed,reference=name,macro_f1_delta=measured['macro_f1']-metric(y,baseline)['macro_f1'],
                harm=int(np.count_nonzero((baseline==y)&(prediction!=y))),repair=int(np.count_nonzero((baseline!=y)&(prediction==y))),
                bootstrap=pc.paired_sequence_bootstrap(y,prediction,baseline,seq))
            pairs.append(pair)
        for sid in sorted(set(seq)):
            mask=seq==sid
            group_rows.append(dict(seed=seed,sequence=sid,samples=int(mask.sum()),old_accuracy=float(np.mean(old[mask]==y[mask])),
                new_accuracy=float(np.mean(prediction[mask]==y[mask])),accuracy_delta=float(np.mean(prediction[mask]==y[mask])-np.mean(old[mask]==y[mask]))))
        np.save(out/f'seed{seed}_c_validation_logits.npy',logits)
        checks.append(dict(seed=seed,full_validation_rows=len(x),stress_rows=len(stress),layer_mismatches=mismatches,
            checkpoint_export_equal=True,saved_training_logits_equal=True,batch_partition_and_order_invariant=True,
            evaluation_state_unchanged=True,scala_multiplier_roundtrip=True,max_observed_abs_values=max_act,
            hidden_clamp127_fraction=[sat[0]/(len(x)*64),sat[1]/(len(x)*32)],metrics=measured))
    with (out/'sequence_metrics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(group_rows[0]));w.writeheader();w.writerows(group_rows)
    report=dict(status='PASS',checks=checks,paired_comparisons=pairs,old_deployment_validation=metric(y,old),
        wall_seconds=time.monotonic()-started,plan_sha256=sha(HERE/'plan.json'),
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'verify.py',HERE/'common.py',ROOT/'tests/radar-feature21-qmlp-cpu-fullchain-profile.c',ROOT/'generators/chipyard/src/main/scala/radar/RadarQMLP.scala']},
        scope='Offline integer arithmetic and exploratory validation only. No new RTL elaboration, simulation, FPGA timing or board run.')
    dump(out/'summary.json',report);print(json.dumps(report),flush=True)

if __name__=='__main__':main()
