"""Equal-budget factorial and predeclared conditional augmentation stages."""
import argparse
import time
from common import *
torch=qc.torch;F=qc.F

def predict_tensor_exact(net,x,integer=False):
    values=[];net.eval()
    with torch.inference_mode():
        for begin in range(0,len(x),4096):
            z=x[begin:begin+4096]
            values.append((net(z,trace=True)[-1] if integer else net(z)).numpy())
    return np.concatenate(values)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['factorial','augmentation'],required=True);args=parser.parse_args();stage=args.stage
    pre=json.loads((LOG/'preflight.json').read_text());assert pre['status']=='PASS'
    for name,h in pre['source_sha256'].items():assert sha(ROOT/name)==h,name
    config=PLAN[stage];cfg=qc.PLAN['training'];start=time.monotonic();out=LOG/(stage+'_v2');out.mkdir(exist_ok=False)
    if stage=='augmentation':
        gate=json.loads((LOG/'factorial_evaluation/augmentation_gate.json').read_text());assert gate['triggered']
        assert json.loads((LOG/'raw/summary.json').read_text())['status']=='PASS'
    source_paths=[HERE/'plan.json',HERE/'train_fixed_v2.py',HERE/'common.py',qc.HERE/'common.py',qc.HERE/'plan.json',LOG/'data/scales.json']
    source_paths.extend(LOG/'data'/split/(mode+'.npy') for mode in config['representations'] for split in ['train','val'])
    source_paths.extend(LOG/'data'/split/'labels.npy' for split in ['train','val'])
    if stage=='augmentation':source_paths.extend(LOG/'raw/train'/mode/(c+'.npy') for mode in config['representations'] for c in ['uniform_quarter_0','central_half'])
    frozen={str(p.relative_to(ROOT)):sha(p) for p in source_paths};dump(out/'source_manifest.json',dict(status='FROZEN_BEFORE_STAGE',sha256=frozen))
    y=np.load(LOG/'data/train/labels.npy');vy=np.load(LOG/'data/val/labels.npy');target=torch.tensor(y)
    weights=torch.tensor(len(y)/(2*np.bincount(y,minlength=2)),dtype=torch.float64)
    ids=np.random.default_rng(PLAN['data']['seed']).choice(len(y),16384,replace=False);np.save(out/'calibration_rows.npy',ids)
    all_runs=[]
    def budget():
        if time.monotonic()-start>PLAN['budgets'][stage+'_training_seconds']:raise TimeoutError(stage+' fixed budget')
    for mode in config['representations']:
        clean=np.load(LOG/'data/train'/(mode+'.npy'));vx=np.load(LOG/'data/val'/(mode+'.npy'))
        if stage=='augmentation':
            views=['clean','uniform_quarter_0','central_half'];prob=np.array([.5,.25,.25])
            x=np.stack([clean]+[np.load(LOG/'raw/train'/mode/(c+'.npy')) for c in views[1:]])
        else:views=['clean'];prob=np.array([1.]);x=clean[None,:,:]
        mu=np.sum(np.asarray([v.mean(0,dtype=np.float64) for v in x])*prob[:,None],axis=0)
        second=np.sum(np.asarray([np.mean(v.astype(float)**2,axis=0) for v in x])*prob[:,None],axis=0)
        std=np.sqrt(np.maximum(second-mu*mu,0));std[std<1e-6]=1
        raw=torch.tensor(x.reshape(-1,21),dtype=torch.float64);vraw=torch.tensor(vx,dtype=torch.float64)
        norm=torch.tensor((x.reshape(-1,21)-mu)/std,dtype=torch.float32)
        cal_view=np.random.default_rng(20260917).choice(len(views),len(ids),p=prob);cal=ids+len(y)*cal_view
        for seed in config['seeds']:
            began=time.monotonic();directory=out/(mode+'_seed'+str(seed));directory.mkdir();curve=[]
            torch.manual_seed(seed);net=qc.model();rng=np.random.default_rng(seed);view_rng=np.random.default_rng(seed+912345)
            initial=hashlib.sha256(b''.join(p.detach().numpy().tobytes() for p in net.parameters())).hexdigest()
            optim=torch.optim.AdamW(net.parameters(),lr=cfg['warmup_lr'],weight_decay=cfg['weight_decay'])
            for epoch in range(1,config['warmup_epochs']+1):
                net.train();order=rng.permutation(len(y));which=view_rng.choice(len(views),len(y),p=prob);total=0.;denom=0.
                for begin in range(0,len(y),cfg['batch_size']):
                    budget();ix=order[begin:begin+cfg['batch_size']];jx=ix+len(y)*which[ix];optim.zero_grad(set_to_none=True)
                    loss=F.cross_entropy(net(norm[jx]),target[ix],weight=weights.float());assert torch.isfinite(loss)
                    loss.backward();optim.step();d=float(weights[target[ix]].sum());total+=float(loss.detach())*d;denom+=d
                curve.append(dict(phase='warmup',epoch=epoch,train_weighted_ce=total/denom))
            net.eval();folded=qc.fold(net,mu,std)
            with torch.inference_mode():error=float((net.double()(torch.tensor((x.reshape(-1,21)[cal]-mu)/std,dtype=torch.float64))-folded(raw[cal])).abs().max())
            assert error<1e-9
            qat=qc.FrozenQAT(folded,raw[cal]);state=buffers_hash(qat)
            optim=torch.optim.AdamW(qat.parameters(),lr=cfg['qat_lr'],weight_decay=cfg['weight_decay'])
            for epoch in range(1,config['qat_epochs']+1):
                qat.train();order=rng.permutation(len(y));which=view_rng.choice(len(views),len(y),p=prob);total=0.;denom=0.
                lr=cfg['qat_lr']*.5**((epoch-1)//cfg['qat_lr_halve_every_epochs'])
                for group in optim.param_groups:group['lr']=lr
                for begin in range(0,len(y),cfg['batch_size']):
                    budget();ix=order[begin:begin+cfg['batch_size']];jx=ix+len(y)*which[ix];optim.zero_grad(set_to_none=True)
                    loss=F.cross_entropy(qat(raw[jx]),target[ix],weight=weights);assert torch.isfinite(loss)
                    loss.backward();optim.step();d=float(weights[target[ix]].sum());total+=float(loss.detach())*d;denom+=d
                qat.eval();qat.export()
                with torch.inference_mode():probe=float(F.cross_entropy(qat(raw[cal]),target[ids],weight=weights))
                row=dict(phase='qat',epoch=epoch,lr=lr,train_weighted_ce=total/denom,train_probe_ce=probe)
                if epoch in PLAN['factorial']['snapshots']:
                    logits=predict_tensor_exact(qat,vraw,True).astype(np.int32);val=qc.metric(vy,logits.argmax(1));row['validation']=val
                    snap=directory/('epoch'+str(epoch));snap.mkdir();np.save(snap/'val_logits.npy',logits)
                    torch.save(dict(state_dict=qat.state_dict(),mode=mode,seed=seed,epoch=epoch,stage=stage),snap/'frozen_qat.pt')
                    qc.write_export(snap/'export',qat.export())
                    params=json.loads((snap/'export/params.json').read_text())
                    params['input']=dict(representation=mode,flags=PLAN['factorial']['flags'][mode],statistics_precision=[24,24],feature_slots=21,
                        scale_source='logs/mechanism_convergence_20260916/data/scales.json',runtime_normalization=False)
                    dump(snap/'export/params.json',params)
                    print(json.dumps(dict(stage=stage,mode=mode,seed=seed,epoch=epoch,f1=val['macro_f1'],wall_seconds=time.monotonic()-start)),flush=True)
                assert buffers_hash(qat)==state;curve.append(row)
            # Full end-of-budget integer trace validation is part of each completed trajectory.
            bundle=qat.export();c=qc.CTrace(directory/'epoch60/export');mismatches=[0,0,0]
            for begin in range(0,len(vx),4096):
                z=vx[begin:begin+4096];ct=c(z);nt=qc.integer_trace(z,bundle)
                with torch.inference_mode():tt=[v.numpy() for v in qat(torch.tensor(z),trace=True)]
                for j,(a,b,d) in enumerate(zip(ct,nt,tt)):mismatches[j]+=int(np.count_nonzero(a!=b))+int(np.count_nonzero(a!=d))
            assert not any(mismatches)
            report=dict(stage=stage,mode=mode,seed=seed,initialization_sha256=initial,fold_max_error=error,qat_epochs=config['qat_epochs'],validation=val,
                frozen_buffers_sha256=state,integer_layer_mismatches=mismatches,wall_seconds=time.monotonic()-began,curve=curve,
                scope='Fixed epoch 60, no best-validation selection; synthetic point-removal training only in augmentation stage')
            dump(directory/'summary.json',report);all_runs.append({k:v for k,v in report.items() if k!='curve'})
            print(json.dumps(dict(stage=stage,mode=mode,seed=seed,complete=True,f1=val['macro_f1'],wall_seconds=time.monotonic()-start)),flush=True)
    for name,h in frozen.items():assert sha(ROOT/name)==h,name
    report=dict(status='PASS',stage=stage,runs=all_runs,wall_seconds=time.monotonic()-start,source_sha256=frozen,plan_sha256=sha(HERE/'plan.json'))
    dump(out/'summary.json',report);print(json.dumps(dict(status='PASS',stage=stage,runs=len(all_runs),wall_seconds=report['wall_seconds'])),flush=True)

if __name__=='__main__':main()
