#!/usr/bin/env python3
"""At most 3 representations x 2 seeds; no hyperparameter or checkpoint search."""
import os
os.environ['OPENBLAS_NUM_THREADS']='2'
os.environ['OMP_NUM_THREADS']='2'
os.environ['MKL_NUM_THREADS']='2'
import argparse
import csv
import gzip
import json
import time
import numpy as np
from pilot_common import HERE,ROOT,LOG,PLAN,Native,reconstruct,cm,metrics,paired_sequence_bootstrap,sha


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['prepare','train'],required=True)
    args=parser.parse_args()
    diagnostic=json.loads((LOG/'full/summary.json').read_text())
    assert diagnostic['plan_sha256']==sha(HERE/'plan.json')
    gate=diagnostic['candidate_gate']
    if not gate['training_allowed']:
        print(json.dumps(dict(status='STOPPED_AT_DIAGNOSTIC_GATE',reason='No predeclared eligible candidate')));return
    candidate=gate['selected'];names=['software_reference','deployment',candidate]
    assert len(set(names))==3
    if args.phase=='prepare':
        native=Native(LOG/'native')
        arrays,y,rows,summary=reconstruct('train',PLAN['data']['training_max_rows_per_sequence'],LOG/'train_subset',native)
        assert summary['sequences']==PLAN['data']['training_sequences_expected']
        print(json.dumps(dict(status='TRAIN_SUBSET_READY',samples=len(y),selected_candidate=candidate)));return

    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
    out=LOG/'training';out.mkdir(exist_ok=False)
    prep=LOG/'train_subset';val=LOG/'full'
    preparation=json.loads((prep/'reconstruction_summary.json').read_text())
    assert preparation['source_sha256'][str((HERE/'plan.json').relative_to(ROOT))]==sha(HERE/'plan.json')
    y=np.load(prep/'labels.npy');vy=np.load(val/'labels.npy')
    with gzip.open(val/'metadata.csv.gz','rt') as f:rows=list(csv.DictReader(f))
    seq=np.asarray([r['sequence_id'] for r in rows])
    counts=np.bincount(y,minlength=2);weights=torch.tensor(len(y)/(2*counts),dtype=torch.float32)
    target=torch.from_numpy(y)
    results={};predictions={};started=time.monotonic()
    source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'plan.json',HERE/'run_bounded_training.py',HERE/'pilot_common.py']}
    for seed in PLAN['training']['seeds']:
        for name in names:
            runstart=time.monotonic()
            if runstart-started>PLAN['resources']['training_timeout_seconds']:raise TimeoutError('Training budget exhausted before next model')
            torch.manual_seed(seed)
            model=torch.nn.Sequential(torch.nn.Linear(21,64),torch.nn.ReLU(),torch.nn.Linear(64,32),torch.nn.ReLU(),torch.nn.Linear(32,2))
            init_hash=__import__('hashlib').sha256(b''.join(x.detach().numpy().tobytes() for x in model.parameters())).hexdigest()
            tx=np.load(prep/(name+'.npy')).astype(np.float32)
            vx=np.load(val/(name+'.npy')).astype(np.float32)
            mean=tx.mean(0,dtype=np.float64).astype(np.float32);scale=tx.std(0,dtype=np.float64).astype(np.float32)
            scale[scale<1e-6]=1
            x=torch.from_numpy((tx-mean)/scale);v=torch.from_numpy((vx-mean)/scale)
            optim=torch.optim.AdamW(model.parameters(),lr=PLAN['training']['learning_rate'],weight_decay=PLAN['training']['weight_decay'])
            lossfn=torch.nn.CrossEntropyLoss(weight=weights)
            rng=np.random.default_rng(seed)
            curve=[];batch=PLAN['training']['batch_size']
            for epoch in range(PLAN['training']['epochs']):
                model.train();order=rng.permutation(len(y));total=0.0
                for begin in range(0,len(y),batch):
                    if time.monotonic()-started>PLAN['resources']['training_timeout_seconds']:raise TimeoutError('Training budget exhausted in epoch')
                    ix=order[begin:begin+batch];optim.zero_grad(set_to_none=True)
                    loss=lossfn(model(x[ix]),target[ix]);loss.backward();optim.step()
                    total+=float(loss.detach())*len(ix)
                curve.append(dict(epoch=epoch+1,training_weighted_loss_batch_average=total/len(y)))
            model.eval()
            with torch.inference_mode():
                logits=torch.cat([model(v[i:i+4096]) for i in range(0,len(v),4096)]).numpy()
                train_pred=torch.cat([model(x[i:i+4096]) for i in range(0,len(x),4096)]).argmax(1).numpy()
            p=logits.argmax(1);tag=name+'_seed'+str(seed)
            np.save(out/(tag+'_val_logits.npy'),logits)
            torch.save(dict(state_dict=model.state_dict(),mean=mean,scale=scale,
                architecture=[21,64,32,2],seed=seed,representation=name,
                warning='FP32 representation probe. Not a deployed or exported QAT checkpoint.'),out/(tag+'.pt'))
            result=dict(representation=name,seed=seed,initialization_sha256=init_hash,
                train=metrics(cm(y,train_pred)),validation=metrics(cm(vy,p)),training_curve=curve,
                wall_seconds=time.monotonic()-runstart,
                input_sha256={str((root/(name+'.npy')).relative_to(ROOT)):sha(root/(name+'.npy')) for root in [prep,val]})
            results[tag]=result;predictions[tag]=p
            (out/(tag+'.json')).write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(dict(phase='training',tag=tag,train_macro_f1=result['train']['macro_f1'],val_macro_f1=result['validation']['macro_f1'],wall_seconds=result['wall_seconds'])),flush=True)
    assert len(results)<=PLAN['training']['max_runs']
    paired=[];byseq=[]
    for seed in PLAN['training']['seeds']:
        assert len({results[name+'_seed'+str(seed)]['initialization_sha256'] for name in names})==1
        base=predictions['deployment_seed'+str(seed)]
        for name in names:
            tag=name+'_seed'+str(seed);p=predictions[tag]
            delta=results[tag]['validation']['macro_f1']-results['deployment_seed'+str(seed)]['validation']['macro_f1']
            paired.append(dict(seed=seed,representation=name,macro_f1_delta_vs_deployment=delta,
                harm=int(np.count_nonzero((base==vy)&(p!=vy))),repair=int(np.count_nonzero((base!=vy)&(p==vy))),
                bootstrap=paired_sequence_bootstrap(vy,p,base,seq)))
            for sid in sorted(set(seq)):
                mask=seq==sid
                byseq.append(dict(seed=seed,representation=name,sequence=sid,samples=int(mask.sum()),
                    accuracy_delta=float(np.mean(p[mask]==vy[mask])-np.mean(base[mask]==vy[mask]))))
    with (out/'paired_sequence_metrics.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(byseq[0]));writer.writeheader();writer.writerows(byseq)
    summary=dict(status='BOUNDED_MATCHED_REPRESENTATION_PROBE_COMPLETE',selected_candidate=candidate,
        train_samples=len(y),validation_samples=len(vy),runs=len(results),wall_seconds=time.monotonic()-started,
        representation_metrics={name:dict(val_macro_f1_by_seed=[results[name+'_seed'+str(s)]['validation']['macro_f1'] for s in PLAN['training']['seeds']],
            mean_val_macro_f1=float(np.mean([results[name+'_seed'+str(s)]['validation']['macro_f1'] for s in PLAN['training']['seeds']]))) for name in names},
        paired_comparisons=paired,source_sha256=source_hashes,
        environment=dict(torch=torch.__version__,numpy=np.__version__,threads=torch.get_num_threads(),device='cpu'),
        limitations=['FP32 weights/activations, standardized INT8 input representations; not a frozen integer deployment result.',
            'Capped training sample per sequence, only two seeds and fixed 20 epochs; not convergence or full-training proof.',
            'Candidate selected on this validation split; results are exploratory and intervals are not selection adjusted.',
            'Historical test not read. K7 historical temporal assumptions unchanged.','No hardware cost or board performance measured.'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
