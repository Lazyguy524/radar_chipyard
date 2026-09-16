"""Two seeds, one protocol, train-only stopping and frozen integer-aware QAT."""
import math
import time
from common import *

def tensor_predictions(net,x,qat=False):
    with torch.inference_mode():
        return torch.cat([net(x[i:i+4096],trace=True)[-1] if qat else net(x[i:i+4096]) for i in range(0,len(x),4096)]).numpy()

def buffers_hash(net):
    return hashlib.sha256(b''.join(v.detach().numpy().tobytes() for _,v in net.named_buffers())).hexdigest()

def main():
    pre=json.loads((LOG/'preflight.json').read_text());prep=json.loads((LOG/'train/summary.json').read_text())
    assert pre['status']==prep['status']=='PASS' and pre['plan_sha256']==sha(HERE/'plan.json')
    for path,digest in pre['source_sha256'].items():assert sha(ROOT/path)==digest
    out=LOG/'training';out.mkdir(exist_ok=False);started=time.monotonic()
    x=np.load(LOG/'train/features.npy');y=np.load(LOG/'train/labels.npy')
    vx=np.load(PILOT/'full/deployment.npy');vy=np.load(PILOT/'full/labels.npy')
    assert x.shape==(357780,21) and vx.shape==(80450,21)
    mean=x.mean(0,dtype=np.float64);std=x.std(0,dtype=np.float64);std[std<1e-6]=1
    norm=torch.tensor((x-mean)/std,dtype=torch.float32)
    raw=torch.tensor(x,dtype=torch.float64);vraw=torch.tensor(vx,dtype=torch.float64)
    target=torch.tensor(y);counts=np.bincount(y,minlength=2)
    class_weights=torch.tensor(len(y)/(2*counts),dtype=torch.float64)
    calibration_ids=np.random.default_rng(PLAN['data']['sampling_seed']).choice(len(y),min(len(y),PLAN['data']['calibration_rows_max']),replace=False)
    np.save(out/'calibration_rows.npy',calibration_ids)
    np.savez(out/'train_normalization.npz',mean=mean,std=std,class_weights=class_weights.numpy())
    cfg=PLAN['training'];runs=[]
    def budget():
        if time.monotonic()-started>PLAN['budgets']['training_timeout_seconds']:raise TimeoutError('Total training budget')
    for seed in cfg['seeds']:
        runstart=time.monotonic();directory=out/f'seed{seed}';directory.mkdir(exist_ok=False)
        torch.manual_seed(seed);net=model();rng=np.random.default_rng(seed)
        initial=hashlib.sha256(b''.join(p.detach().numpy().tobytes() for p in net.parameters())).hexdigest()
        optim=torch.optim.AdamW(net.parameters(),lr=cfg['warmup_lr'],weight_decay=cfg['weight_decay'])
        curve=[]
        for epoch in range(cfg['warmup_epochs']):
            net.train();order=rng.permutation(len(y));total=0.0;denom=0.0
            for begin in range(0,len(y),cfg['batch_size']):
                budget();ix=order[begin:begin+cfg['batch_size']];optim.zero_grad(set_to_none=True)
                loss=F.cross_entropy(net(norm[ix]),target[ix],weight=class_weights.float())
                assert torch.isfinite(loss);loss.backward();optim.step()
                d=float(class_weights[target[ix]].sum());total+=float(loss.detach())*d;denom+=d
            row=dict(phase='warmup',epoch=epoch+1,train_weighted_ce=total/denom)
            curve.append(row)
            if (epoch+1)%5==0:print(json.dumps(dict(seed=seed,**row)),flush=True)
        net.eval();folded=fold(net,mean,std)
        with torch.inference_mode():
            expected=net.double()(torch.tensor((x[calibration_ids]-mean)/std,dtype=torch.float64))
            folded_values=folded(raw[calibration_ids]);fold_error=float((expected-folded_values).abs().max())
        assert fold_error<1e-9
        warm_logits=tensor_predictions(folded,vraw);warm_metrics=metric(vy,warm_logits.argmax(1))
        np.save(directory/'warmup_val_logits.npy',warm_logits)
        torch.save(dict(state_dict=folded.state_dict(),normalization_folded=True,seed=seed),directory/'folded_warmup.pt')
        qat=FrozenQAT(folded,raw[calibration_ids]);frozen_hash=buffers_hash(qat)
        before=qat.export();write_export(directory/'ptq_export',before)
        ptq_logits=tensor_predictions(qat,vraw,True).astype(np.int32)
        np.save(directory/'ptq_val_logits.npy',ptq_logits);ptq_metrics=metric(vy,ptq_logits.argmax(1))
        optim=torch.optim.AdamW(qat.parameters(),lr=cfg['qat_lr'],weight_decay=cfg['weight_decay'])
        monitor=[];plateau_streak=0;plateau=False
        for epoch in range(1,cfg['qat_max_epochs']+1):
            qat.train();order=rng.permutation(len(y));total=0.0;denom=0.0
            lr=cfg['qat_lr']*0.5**((epoch-1)//cfg['qat_lr_halve_every_epochs'])
            for group in optim.param_groups:group['lr']=lr
            for begin in range(0,len(y),cfg['batch_size']):
                budget();ix=order[begin:begin+cfg['batch_size']];optim.zero_grad(set_to_none=True)
                loss=F.cross_entropy(qat(raw[ix]),target[ix],weight=class_weights)
                assert torch.isfinite(loss);loss.backward();optim.step()
                d=float(class_weights[target[ix]].sum());total+=float(loss.detach())*d;denom+=d
            qat.eval();qat.export()  # Enforce integer overflow bounds at every epoch.
            with torch.inference_mode():probe_loss=float(F.cross_entropy(qat(raw[calibration_ids]),target[calibration_ids],weight=class_weights))
            logits=tensor_predictions(qat,vraw,True).astype(np.int32);val=metric(vy,logits.argmax(1))
            assert buffers_hash(qat)==frozen_hash,'Evaluation or training mutated frozen scales'
            monitor.append(probe_loss);w=PLAN['plateau']['window_epochs'];change=None;tolerance=None
            if epoch>=cfg['qat_min_epochs'] and len(monitor)>=2*w:
                previous=float(np.mean(monitor[-2*w:-w]));recent=float(np.mean(monitor[-w:]))
                change=abs(recent-previous);tolerance=max(PLAN['plateau']['absolute_loss_change_tolerance'],PLAN['plateau']['relative_loss_change_tolerance']*abs(previous))
                plateau_streak=plateau_streak+1 if change<=tolerance else 0
                plateau=plateau_streak>=PLAN['plateau']['consecutive_checks']
            row=dict(phase='qat',epoch=epoch,lr=lr,train_weighted_ce=total/denom,train_probe_ce=probe_loss,
                validation_macro_f1=val['macro_f1'],plateau_window_difference=change,plateau_tolerance=tolerance,plateau_streak=plateau_streak)
            curve.append(row);print(json.dumps(dict(seed=seed,**row)),flush=True)
            if plateau:break
        qat.eval();bundle=qat.export();write_export(directory/'final_export',bundle)
        torch.save(dict(state_dict=qat.state_dict(),seed=seed,normalization_folded=True,plan_sha256=sha(HERE/'plan.json')),
            directory/'frozen_qat.pt')
        np.save(directory/'final_val_logits.npy',logits)
        train_logits=tensor_predictions(qat,raw,True).astype(np.int32)
        final_train=metric(y,train_logits.argmax(1));np.save(directory/'final_train_logits.npy',train_logits)
        qcurve=[r for r in curve if r['phase']=='qat'];span=max(r['validation_macro_f1'] for r in qcurve[-5:])-min(r['validation_macro_f1'] for r in qcurve[-5:])
        clipping=[float((l.weight.detach().abs()>127*qat.weight_scales[i]).double().mean()) for i,l in enumerate(qat.layers)]
        report=dict(seed=seed,initialization_sha256=initial,train_samples=len(y),validation_samples=len(vy),fold_max_error=fold_error,
            warmup_validation=warm_metrics,ptq_validation=ptq_metrics,qat_validation=val,qat_train=final_train,
            qat_epochs=epoch,train_loss_plateau=plateau,stop_reason='TRAIN_LOSS_PLATEAU' if plateau else 'MAX_EPOCHS_WITHOUT_PLATEAU',
            last_five_validation_f1_span=span,validation_stable_within_0p003=span<=.003,
            frozen_buffers_sha256=frozen_hash,weight_clipped_fraction=clipping,curve=curve,wall_seconds=time.monotonic()-runstart,
            final_multipliers=bundle['multipliers'])
        dump(directory/'summary.json',report);runs.append(report)
        print(json.dumps(dict(seed=seed,complete=True,epochs=epoch,f1=val['macro_f1'],plateau=plateau)),flush=True)
    sources=[HERE/'plan.json',HERE/'common.py',HERE/'train.py',LOG/'train/features.npy',LOG/'train/labels.npy',LOG/'train/metadata.csv.gz',
        PILOT/'full/deployment.npy',PILOT/'full/labels.npy',PILOT/'full/metadata.csv.gz']
    summary=dict(status='TWO_SEED_TRAINING_COMPLETE',runs=[{k:v for k,v in r.items() if k!='curve'} for r in runs],
        wall_seconds=time.monotonic()-started,train_rows=len(y),validation_rows=len(vy),calibration_rows=len(calibration_ids),
        environment=dict(torch=torch.__version__,numpy=np.__version__,threads=torch.get_num_threads(),device='cpu'),
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},
        scope='Development validation; frozen integer-aware QAT, no new RTL or board measurements; no independent test claim')
    dump(out/'summary.json',summary);print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
