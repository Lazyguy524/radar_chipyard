"""Six equal-update runs, fixed final epoch, train-only correct-decision guard."""
import time
from protection_common import *

def main():
    start=time.monotonic();pre=json.loads((LOG/'preflight.json').read_text());assert pre['status']=='PASS'
    for p,h in pre['source_sha256'].items():assert sha(ROOT/p)==h,p
    cfg=PLAN['training'];tc=qc.PLAN['training'];out=LOG/'training';out.mkdir(exist_ok=False)
    x=np.stack([np.load(MECH/'data/train/proxy.npy')]+[np.load(MECH/'raw/train/proxy'/(v+'.npy')) for v in cfg['views'][1:]])
    y=np.load(MECH/'data/train/labels.npy');vx=np.load(MECH/'data/val/proxy.npy');vy=np.load(MECH/'data/val/labels.npy');n=len(y)
    prep=np.load(LOG/'prepared/normalization.npz');mu,std=prep['mean'],prep['std'];cal=prep['calibration_rows']+n*prep['calibration_views']
    raw=torch.tensor(x.reshape(-1,21),dtype=torch.float64);norm=torch.tensor((x.reshape(-1,21)-mu)/std,dtype=torch.float32)
    target=torch.tensor(y);weights=torch.tensor(n/(2*np.bincount(y,minlength=2)),dtype=torch.float64)
    source_groups=np.load(LOG/'prepared/source_groups.npy');vraw=torch.tensor(vx,dtype=torch.float64)
    paths=list(HERE.glob('*.py'))+[HERE/'plan.json',LOG/'preflight.json',MECH/'augmentation_v2/summary.json',MECH/'factorial_v2/summary.json']
    paths.extend(p for p in (LOG/'prepared').glob('*') if p.is_file())
    frozen={str(p.relative_to(ROOT)):sha(p) for p in paths};dump(out/'source_manifest.json',dict(status='FROZEN_BEFORE_TRAINING',sha256=frozen))
    def budget():
        if time.monotonic()-start>PLAN['budgets']['training_seconds']:raise TimeoutError('Training wall budget')
    runs=[]
    for method in cfg['methods']:
        for seed in cfg['seeds']:
            began=time.monotonic();d=out/(method+'_seed'+str(seed));d.mkdir();curve=[]
            teacher=torch.tensor(np.load(LOG/'prepared'/('teacher_seed%d_real.npy'%seed)))
            torch.manual_seed(seed);net=qc.model();rng=np.random.default_rng(seed);view_rng=np.random.default_rng(seed+912345)
            initial=hashlib.sha256(b''.join(p.detach().numpy().tobytes() for p in net.parameters())).hexdigest()
            old=get_previous(seed);assert initial==old['initialization_sha256']
            q=torch.ones(18,dtype=torch.float64)/18;optim=torch.optim.AdamW(net.parameters(),lr=tc['warmup_lr'],weight_decay=tc['weight_decay'])
            for phase in ['warmup','qat']:
                if phase=='qat':
                    net.eval();folded=qc.fold(net,mu,std)
                    with torch.inference_mode():fold_error=float((net.double()(torch.tensor((x.reshape(-1,21)[cal]-mu)/std,dtype=torch.float64))-folded(raw[cal])).abs().max())
                    assert fold_error<1e-9
                    net=qc.FrozenQAT(folded,raw[cal]);frozen_buffers=buffer_hash(net)
                    optim=torch.optim.AdamW(net.parameters(),lr=tc['qat_lr'],weight_decay=tc['weight_decay'])
                for epoch in range(1,cfg['warmup_epochs' if phase=='warmup' else 'qat_epochs']+1):
                    net.train();order=rng.permutation(n);which=view_rng.choice(3,n,p=cfg['probabilities'])
                    if phase=='qat':
                        lr=tc['qat_lr']*.5**((epoch-1)//tc['qat_lr_halve_every_epochs'])
                        for group in optim.param_groups:group['lr']=lr
                    numer=torch.zeros(18,dtype=torch.float64);denom=numer.clone();tot=guard=0.;steps=0
                    for begin in range(0,n,cfg['batch_size']):
                        budget();ix=order[begin:begin+cfg['batch_size']];view=which[ix];jx=ix+n*view;gg=torch.tensor(source_groups[ix]+6*view)
                        optim.zero_grad(set_to_none=True);z=net(norm[jx] if phase=='warmup' else raw[jx])
                        loss,parts=objective(z,target[ix],weights,teacher[ix],torch.tensor(view),gg,q,method)
                        assert torch.isfinite(loss);loss.backward();optim.step()
                        numer+=parts['group_num'].detach().double();denom+=parts['group_den'].detach().double()
                        tot+=float(loss.detach());guard+=float(parts['guard'].detach());steps+=1
                    assert (denom>0).all();group_losses=numer/denom
                    row=dict(phase=phase,epoch=epoch,batch_mean_objective=tot/steps,batch_mean_guard=guard/steps,
                        group_ce=group_losses.tolist(),group_q_used=q.tolist(),student_examples=n,optimizer_steps=steps)
                    if method=='group_guard':q=torch.softmax(torch.log(q)+.05*(group_losses-group_losses.mean()),0)
                    if phase=='qat':
                        net.eval();net.export();assert buffer_hash(net)==frozen_buffers
                        if epoch in cfg['snapshots']:
                            logits=prediction(net,vraw,True).astype(np.int32);metric=qc.metric(vy,logits.argmax(1));row['validation']=metric
                            snap=d/('epoch'+str(epoch));snap.mkdir();np.save(snap/'val_logits.npy',logits)
                            torch.save(dict(state_dict=net.state_dict(),method=method,seed=seed,epoch=epoch),snap/'frozen_qat.pt')
                            qc.write_export(snap/'export',net.export());params=json.loads((snap/'export/params.json').read_text())
                            params['input']=dict(representation='proxy',flags=0,scale_source='logs/mechanism_convergence_20260916/data/scales.json',runtime_normalization=False)
                            dump(snap/'export/params.json',params)
                            print(json.dumps(dict(method=method,seed=seed,epoch=epoch,f1=metric['macro_f1'],seconds=time.monotonic()-start)),flush=True)
                    curve.append(row)
            bundle=net.export();c=qc.CTrace(d/'epoch60/export');mismatch=[0,0,0]
            for begin in range(0,len(vx),4096):
                z=vx[begin:begin+4096];ct=c(z);nt=qc.integer_trace(z,bundle)
                with torch.inference_mode():tt=[v.numpy() for v in net(torch.tensor(z),trace=True)]
                for j,(a,b,e) in enumerate(zip(ct,nt,tt)):mismatch[j]+=int(np.count_nonzero(a!=b))+int(np.count_nonzero(a!=e))
            assert mismatch==[0,0,0]
            result=dict(method=method,seed=seed,initialization_sha256=initial,fold_max_error=fold_error,qat_epochs=60,
                validation=metric,integer_layer_mismatches=mismatch,frozen_buffers_sha256=frozen_buffers,
                student_examples=80*n,optimizer_steps=80*((n+cfg['batch_size']-1)//cfg['batch_size']),wall_seconds=time.monotonic()-began,curve=curve)
            dump(d/'summary.json',result);runs.append({k:v for k,v in result.items() if k!='curve'})
            print(json.dumps(dict(method=method,seed=seed,complete=True,seconds=time.monotonic()-start)),flush=True)
    for p,h in frozen.items():assert sha(ROOT/p)==h,p
    report=dict(status='PASS',runs=runs,wall_seconds=time.monotonic()-start,plan_sha256=sha(HERE/'plan.json'),source_sha256=frozen,
        scope='Six fixed final-epoch exploratory trials, known distillation/group-risk ideas; no architecture/runtime-feature change or final novelty claim')
    dump(out/'summary.json',report);print(json.dumps(dict(status='PASS',runs=len(runs),seconds=report['wall_seconds'])),flush=True)
def get_previous(seed):return json.loads((MECH/'augmentation_v2'/('proxy_seed'+str(seed))/'summary.json').read_text())
if __name__=='__main__':main()
