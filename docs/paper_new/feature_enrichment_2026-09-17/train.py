"""Fifteen fixed-budget physical-group and same-dimension control trajectories."""
from ex_common import *

def main():
    assert json.loads((LOG/'training_preflight.json').read_text())['status']=='PASS'
    assert (LOG/'git_backup_before.json').is_file(),'Create selective Git backup before full training'
    out=LOG/'training';out.mkdir(exist_ok=False);start=time.monotonic();cfg=PLAN['training'];runs=[]
    sources=[p for p in HERE.iterdir() if p.name in ['plan.json','ex_common.py','features.c','preflight.py','prepare.py','training_preflight.py','train.py','evaluate.py','build_package.py','explain.py'] or p.suffix=='.md']
    sources += [ab.HERE/'ab_common.py',ab.HERE/'train.py',sw.HERE/'pools.py',qc.HERE/'common.py',qc.HERE/'plan.json',MECH/'data/scales.json',LOG/'training_preflight.json',OLD/'data/matching.json']
    sources += [p for p in (LOG/'data').rglob('*.npy')]
    sources += [LOG/'preparation.json',LOG/'synthetic_preflight.json',MECH/'data/train/labels.npy',MECH/'data/val/labels.npy',OLD/'data/train/natural_labels.npy',OLD/'data/train/synthetic_labels.npy']
    sources += [MECH/'data/train/proxy.npy',MECH/'raw/train/proxy/uniform_quarter_0.npy',MECH/'raw/train/proxy/central_half.npy',OLD/'data/train/natural_proxy.npy',OLD/'data/train/synthetic_proxy.npy']
    frozen={str(p.relative_to(ROOT)):sha(p) for p in sources};dump(out/'source_manifest.json',dict(status='FROZEN_BEFORE_FULL_TRAINING',sha256=frozen))
    def budget():
        if time.monotonic()-start>PLAN['budget']['training_seconds']:raise TimeoutError('Training stage budget; no extra trajectories')
    data=Pools();weights=torch.tensor(data.class_weights,dtype=torch.float64);target=torch.tensor(data.y)
    vy=np.load(MECH/'data/val/labels.npy')
    for tag_base in VARIANTS:
        cols=take(tag_base);mu=data.mu[cols];std=data.std[cols];x=data.x[:,cols]
        norm=torch.tensor((x-mu)/std,dtype=torch.float32);raw=torch.tensor(x,dtype=torch.float64)
        vx=validation('clean')[0][:,cols]
        source=1
        for seed in SEEDS:
                began=time.monotonic();tag=tag_base+'_seed'+str(seed);d=out/tag;d.mkdir();curve=[];original,net=model(tag_base,seed)
                init=hashlib.sha256(b''.join(p.detach().numpy().tobytes() for p in net.parameters())).hexdigest()
                opt=torch.optim.AdamW(net.parameters(),lr=cfg['warmup_lr'],weight_decay=cfg['weight_decay'])
                schedules=hashlib.sha256()
                for epoch in range(1,21):
                    net.train();ids,_=data.schedule(seed,epoch,source);schedules.update(ids.tobytes());total=0.;den=0.
                    for begin in range(0,len(ids),1024):
                        budget();ix=ids[begin:begin+1024];opt.zero_grad(set_to_none=True)
                        loss=F.cross_entropy(net(norm[ix]),target[ix],weight=weights.float());assert torch.isfinite(loss)
                        loss.backward();opt.step();w=float(weights[target[ix]].sum());total+=float(loss.detach())*w;den+=w
                    curve.append(dict(phase='warmup',epoch=epoch,train_ce=total/den))
                net.eval();folded=qc.fold(net,mu,std)
                with torch.inference_mode():err=float((net.double()(torch.tensor((x[data.cal]-mu)/std,dtype=torch.float64))-folded(raw[data.cal])).abs().max())
                assert err<1e-9
                q=qc.FrozenQAT(folded,raw[data.cal]);state=base.buffers_hash(q)
                opt=torch.optim.AdamW(q.parameters(),lr=cfg['qat_lr'],weight_decay=cfg['weight_decay'])
                for epoch in range(1,61):
                    q.train();ids,_=data.schedule(seed,epoch+20,source);schedules.update(ids.tobytes());total=0.;den=0.
                    lr=cfg['qat_lr']*.5**((epoch-1)//20)
                    for g in opt.param_groups:g['lr']=lr
                    for begin in range(0,len(ids),1024):
                        budget();ix=ids[begin:begin+1024];opt.zero_grad(set_to_none=True)
                        loss=F.cross_entropy(q(raw[ix]),target[ix],weight=weights);assert torch.isfinite(loss)
                        loss.backward();opt.step();w=float(weights[target[ix]].sum());total+=float(loss.detach())*w;den+=w
                    q.eval();q.export();assert base.buffers_hash(q)==state
                    with torch.inference_mode():probe=float(F.cross_entropy(q(raw[data.cal]),target[data.cal],weight=weights))
                    row=dict(phase='qat',epoch=epoch,lr=lr,train_ce=total/den,train_probe_ce=probe)
                    if epoch in cfg['checkpoints']:
                        logits=[]
                        with torch.inference_mode():
                            for i in range(0,len(vx),4096):logits.append(q(torch.tensor(vx[i:i+4096]),trace=True)[-1].numpy())
                        logits=np.concatenate(logits).astype(np.int32);metric=qc.metric(vy,logits.argmax(1));row['validation']=metric
                        snap=d/('epoch'+str(epoch));snap.mkdir();np.save(snap/'val_logits.npy',logits)
                        torch.save(dict(state_dict=q.state_dict(),variant=tag_base,columns=cols,seed=seed,epoch=epoch),snap/'frozen_qat.pt')
                        export(snap/'export',q.export(),columns(tag_base))
                        print(json.dumps(dict(tag=tag,epoch=epoch,f1=metric['macro_f1'],seconds=round(time.monotonic()-start,1))),flush=True)
                    curve.append(row)
                export_dir=d/'epoch60/export';c=Trace(export_dir);bundle=q.export();mismatch=[0,0,0]
                for i in range(0,len(vx),4096):
                    budget();z=vx[i:i+4096];ct=c(z);nt=qc.integer_trace(z,bundle)
                    with torch.inference_mode():qt=[v.numpy() for v in q(torch.tensor(z),trace=True)]
                    for j,(a,b,cc) in enumerate(zip(ct,nt,qt)):mismatch[j]+=int(np.count_nonzero(a!=b))+int(np.count_nonzero(a!=cc))
                assert not any(mismatch)
                reproduction=None
                if tag_base=='base16':
                    old=qc.load_export(old_export(seed));new=q.export()
                    assert old['multipliers']==new['multipliers']
                    for oldlayer,newlayer in zip(old['layers'],new['layers']):
                        for key in ['weight','bias']:assert np.array_equal(oldlayer[key],newlayer[key]),(seed,key)
                    assert np.array_equal(np.load(old_export(seed).parent/'val_logits.npy'),np.load(d/'epoch60/val_logits.npy'))
                    reproduction='EXACT_PREVIOUS_LESS_SHAPE16'
                report=dict(variant=tag_base,columns=cols,seed=seed,tag=tag,validation=metric,initialization_sha256=init,schedule_sha256=schedules.hexdigest(),
                    base16_reproduction=reproduction,fold_error=err,integer_layer_mismatches=mismatch,qat_buffer_sha256=state,wall_seconds=time.monotonic()-began,curve=curve)
                dump(d/'summary.json',report);runs.append({k:v for k,v in report.items() if k!='curve'});size_guard()
                print(json.dumps(dict(tag=tag,complete=True,seconds=round(time.monotonic()-start,1))),flush=True)
        del norm,raw,x
    for name,h in frozen.items():assert sha(ROOT/name)==h,name
    result=dict(status='PASS',runs=runs,wall_seconds=time.monotonic()-start,source_sha256=frozen,plan_sha256=sha(HERE/'plan.json'),training_budget_complete=True)
    dump(out/'summary.json',result);print(json.dumps(dict(status='PASS',trajectories=len(runs),seconds=result['wall_seconds'])),flush=True)
if __name__=='__main__':main()
