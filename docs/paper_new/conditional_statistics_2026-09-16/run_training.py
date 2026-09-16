"""Matched representation training, reusing the verified frozen-QAT arithmetic."""
import time
from kernel import *
sys.path.insert(0,str(ROOT/'docs/paper_new/qmlp_int8_convergence_2026-09-16'))
import common as qc
from train import tensor_predictions,buffers_hash
torch=qc.torch;F=qc.F

def main():
    prep=json.loads((LOG/'data/summary.json').read_text());assert prep['status']=='PASS'
    assert prep['plan_sha256']==sha(HERE/'plan.json')
    for name,digest in prep['source_sha256'].items():assert sha(ROOT/name)==digest
    out=LOG/'training';out.mkdir(exist_ok=False);start=time.monotonic();cfg=qc.PLAN['training'];all_runs=[]
    y=np.load(LOG/'data/train/labels.npy');vy=np.load(LOG/'data/val/labels.npy');target=torch.tensor(y)
    weights=torch.tensor(len(y)/(2*np.bincount(y,minlength=2)),dtype=torch.float64)
    ids=np.random.default_rng(PLAN['data']['seed']).choice(len(y),16384,replace=False);np.save(out/'calibration_rows.npy',ids)
    sources=[HERE/'plan.json',HERE/'run_training.py',HERE/'kernel.py',qc.HERE/'common.py',qc.HERE/'train.py',qc.HERE/'plan.json',LOG/'data/output_scale_exponents.json',LOG/'data/train/labels.npy',LOG/'data/val/labels.npy']
    def budget():
        if time.monotonic()-start>PLAN['budget']['training_seconds']:raise TimeoutError('Six-trajectory total budget')
    for mode in PLAN['training']['representations']:
        x=np.load(LOG/'data/train'/(mode+'.npy'));vx=np.load(LOG/'data/val'/(mode+'.npy'))
        sources.extend([LOG/'data/train'/(mode+'.npy'),LOG/'data/val'/(mode+'.npy')])
        mu=x.mean(0,dtype=np.float64);std=x.std(0,dtype=np.float64);std[std<1e-6]=1
        raw=torch.tensor(x,dtype=torch.float64);vraw=torch.tensor(vx,dtype=torch.float64);norm=torch.tensor((x-mu)/std,dtype=torch.float32)
        for seed in PLAN['training']['seeds']:
            began=time.monotonic();directory=out/(mode+'_seed'+str(seed));directory.mkdir(exist_ok=False)
            torch.manual_seed(seed);net=qc.model();rng=np.random.default_rng(seed);curve=[]
            initial=hashlib.sha256(b''.join(p.detach().numpy().tobytes() for p in net.parameters())).hexdigest()
            optim=torch.optim.AdamW(net.parameters(),lr=cfg['warmup_lr'],weight_decay=cfg['weight_decay'])
            for epoch in range(1,cfg['warmup_epochs']+1):
                net.train();order=rng.permutation(len(y));total=0.;denom=0.
                for begin in range(0,len(y),cfg['batch_size']):
                    budget();ix=order[begin:begin+cfg['batch_size']];optim.zero_grad(set_to_none=True)
                    loss=F.cross_entropy(net(norm[ix]),target[ix],weight=weights.float());assert torch.isfinite(loss)
                    loss.backward();optim.step();d=float(weights[target[ix]].sum());total+=float(loss.detach())*d;denom+=d
                curve.append(dict(phase='warmup',epoch=epoch,train_weighted_ce=total/denom))
            net.eval();folded=qc.fold(net,mu,std)
            with torch.inference_mode():
                error=float((net.double()(torch.tensor((x[ids]-mu)/std,dtype=torch.float64))-folded(raw[ids])).abs().max())
            assert error<1e-9
            warm_logits=tensor_predictions(folded,vraw);np.save(directory/'warmup_val_logits.npy',warm_logits)
            qat=qc.FrozenQAT(folded,raw[ids]);state=buffers_hash(qat)
            ptq_logits=tensor_predictions(qat,vraw,True).astype(np.int32);np.save(directory/'ptq_val_logits.npy',ptq_logits)
            optim=torch.optim.AdamW(qat.parameters(),lr=cfg['qat_lr'],weight_decay=cfg['weight_decay'])
            monitor=[];streak=0;plateau=False
            for epoch in range(1,cfg['qat_max_epochs']+1):
                qat.train();order=rng.permutation(len(y));total=0.;denom=0.
                lr=cfg['qat_lr']*.5**((epoch-1)//cfg['qat_lr_halve_every_epochs'])
                for group in optim.param_groups:group['lr']=lr
                for begin in range(0,len(y),cfg['batch_size']):
                    budget();ix=order[begin:begin+cfg['batch_size']];optim.zero_grad(set_to_none=True)
                    loss=F.cross_entropy(qat(raw[ix]),target[ix],weight=weights);assert torch.isfinite(loss)
                    loss.backward();optim.step();d=float(weights[target[ix]].sum());total+=float(loss.detach())*d;denom+=d
                qat.eval();qat.export()
                with torch.inference_mode():probe=float(F.cross_entropy(qat(raw[ids]),target[ids],weight=weights))
                logits=tensor_predictions(qat,vraw,True).astype(np.int32);val=qc.metric(vy,logits.argmax(1))
                assert buffers_hash(qat)==state;monitor.append(probe);w=qc.PLAN['plateau']['window_epochs']
                change=None;tol=None
                if epoch>=cfg['qat_min_epochs']:
                    old=float(np.mean(monitor[-2*w:-w]));new=float(np.mean(monitor[-w:]));change=abs(new-old)
                    tol=max(qc.PLAN['plateau']['absolute_loss_change_tolerance'],qc.PLAN['plateau']['relative_loss_change_tolerance']*abs(old))
                    streak=streak+1 if change<=tol else 0;plateau=streak>=qc.PLAN['plateau']['consecutive_checks']
                row=dict(phase='qat',epoch=epoch,lr=lr,train_weighted_ce=total/denom,train_probe_ce=probe,validation_macro_f1=val['macro_f1'],
                    plateau_window_difference=change,plateau_tolerance=tol,plateau_streak=streak)
                curve.append(row)
                if epoch%5==0 or plateau:print(json.dumps(dict(mode=mode,seed=seed,**row)),flush=True)
                if plateau:break
            qc.write_export(directory/'export',qat.export())
            torch.save(dict(state_dict=qat.state_dict(),seed=seed,mode=mode,plan_sha256=sha(HERE/'plan.json')),directory/'frozen_qat.pt')
            np.save(directory/'final_val_logits.npy',logits)
            endcurve=[r for r in curve if r['phase']=='qat']
            report=dict(mode=mode,seed=seed,initialization_sha256=initial,fold_max_error=error,qat_epochs=epoch,train_loss_plateau=plateau,
                warmup_validation=qc.metric(vy,warm_logits.argmax(1)),ptq_validation=qc.metric(vy,ptq_logits.argmax(1)),validation=val,
                last_five_validation_f1_span=max(r['validation_macro_f1'] for r in endcurve[-5:])-min(r['validation_macro_f1'] for r in endcurve[-5:]),
                frozen_buffers_sha256=state,wall_seconds=time.monotonic()-began,curve=curve)
            dump(directory/'summary.json',report);all_runs.append({k:v for k,v in report.items() if k!='curve'})
            print(json.dumps(dict(mode=mode,seed=seed,done=True,epochs=epoch,f1=val['macro_f1'],plateau=plateau)),flush=True)
    report=dict(status='SIX_MATCHED_TRAJECTORIES_COMPLETE',runs=all_runs,wall_seconds=time.monotonic()-start,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},plan_sha256=sha(HERE/'plan.json'),
        scope='Exploratory development validation; same fixed training protocol, final train-only stopping; no independent test or board cost claim')
    dump(out/'summary.json',report);print(json.dumps(report),flush=True)

if __name__=='__main__':main()
