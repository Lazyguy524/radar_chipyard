"""Train-only preparation and synthetic objective checks before model training."""
import csv
import gzip
import time
from protection_common import *

def main():
    start=time.monotonic();out=LOG/'prepared';out.mkdir(exist_ok=False)
    cfg=PLAN['training'];tc=qc.PLAN['training']
    paths=[HERE/'plan.json',HERE/'protection_common.py',HERE/'preflight.py',qc.HERE/'common.py',qc.HERE/'plan.json',MECH/'data/scales.json']
    x=np.stack([np.load(MECH/'data/train/proxy.npy')]+[np.load(MECH/'raw/train/proxy'/(v+'.npy')) for v in cfg['views'][1:]])
    y=np.load(MECH/'data/train/labels.npy');n=len(y);assert n==357780
    paths.extend([MECH/'data/train/proxy.npy',MECH/'data/train/labels.npy',MECH/'raw/train/metadata.csv'])
    paths.extend(MECH/'raw/train/proxy'/(v+'.npy') for v in cfg['views'][1:])
    with (MECH/'raw/train/metadata.csv').open() as f:meta=list(csv.DictReader(f))
    assert len(meta)==n
    raw=np.array([int(r['raw_points']) for r in meta]);history=np.array([int(r['retained_history'])-1 for r in meta])
    assert raw.min()>=3 and history.min()==0 and history.max()==6
    boundary=float(np.median(raw));hc=np.select([history==0,history<6],[0,1],default=2)
    support_group=2*hc+(raw>boundary);np.save(out/'source_groups.npy',support_group.astype(np.int64))
    counts=np.bincount(support_group,minlength=6);assert (counts>=512).all()
    ids=np.load(MECH/'augmentation_v2/calibration_rows.npy');views=np.random.default_rng(20260917).choice(3,len(ids),p=cfg['probabilities'])
    prob=np.array(cfg['probabilities']);mu=np.sum(np.asarray([v.mean(0,dtype=np.float64) for v in x])*prob[:,None],axis=0)
    second=np.sum(np.asarray([np.mean(v.astype(float)**2,axis=0) for v in x])*prob[:,None],axis=0)
    std=np.sqrt(np.maximum(second-mu*mu,0));std[std<1e-6]=1
    np.savez(out/'normalization.npz',mean=mu,std=std,calibration_rows=ids,calibration_views=views)
    teacher=[]
    for seed in cfg['seeds']:
        b=MECH/'factorial_v2'/('proxy_seed'+str(seed))/'epoch60/export';model=native_model(b);bundle=qc.load_export(b)
        pred=[]
        for begin in range(0,n,4096):pred.append(model(x[0,begin:begin+4096])[-1])
        logits=np.concatenate(pred);np.save(out/('teacher_seed%d_logits.npy'%seed),logits)
        scale=bundle['layers'][-1]['output_scale'];np.save(out/('teacher_seed%d_real.npy'%seed),logits.astype(float)*scale)
        paths.extend([b/'params.json',b/'integer_params.npz',b/'inference_trace.c',b/'inference_trace.so'])
        teacher.append(dict(seed=seed,train_correct=int(np.count_nonzero(logits.argmax(1)==y)),output_scale=scale))
    # Verify zero penalty when identical, masked wrong/perturbed teacher, invariance,
    # class weighting, and group update toward larger losses without any real fitting.
    labels=torch.tensor([0,1,0,1]);weight=torch.tensor([1.3,.7],dtype=torch.float64)
    target=torch.tensor([[3.,-2.],[-2.,3.],[2.,-1.],[-1.,2.]],dtype=torch.float64)
    view=torch.tensor([0,0,1,2]);group=torch.tensor([0,1,6,12]);q=torch.ones(18,dtype=torch.float64)/18
    z=target.clone().requires_grad_(True);loss,v=objective(z,labels,weight,target,view,group,q,'clean_guard')
    assert abs(float(v['guard']))<1e-12
    assert abs(float(loss)-float(F.cross_entropy(z,labels,weight=weight)))<1e-12
    wrong=-target;z=torch.zeros_like(target,requires_grad=True)
    loss,v=objective(z,labels,weight,wrong,view,group,q,'clean_guard');assert abs(float(v['guard']))<1e-12
    l1,a=objective(z,labels,weight,target,view,group,q,'group_guard');l1.backward();assert torch.isfinite(z.grad).all()
    _,b=objective(z.detach()+99,labels,weight,target+99,view,group,q,'group_guard');assert abs(float(a['guard']-b['guard']))<1e-12
    new=torch.softmax(torch.log(q)+.05*torch.arange(18,dtype=torch.float64),0);assert new[-1]>new[0] and abs(float(new.sum())-1)<1e-12
    # A small train-only step proves both objectives run in warmup and exact QAT.
    smoke=[]
    for method in cfg['methods']:
        torch.manual_seed(20260916);net=qc.model();ix=np.arange(64);vx=torch.tensor((x[0,ix]-mu)/std,dtype=torch.float32)
        yy=torch.tensor(y[ix]);cw=torch.tensor(len(y)/(2*np.bincount(y)),dtype=torch.float64)
        tt=torch.tensor(np.load(out/'teacher_seed7_real.npy')[ix]);vv=torch.zeros(64,dtype=torch.long);gg=torch.tensor(support_group[ix])
        opt=torch.optim.SGD(net.parameters(),lr=.0001);opt.zero_grad();l,_=objective(net(vx),yy,cw,tt,vv,gg,q,method);l.backward();opt.step()
        fold=qc.fold(net,mu,std);qat=qc.FrozenQAT(fold,torch.tensor(x[views,ids],dtype=torch.float64));before=buffer_hash(qat)
        opt=torch.optim.SGD(qat.parameters(),lr=.00001);opt.zero_grad();l,_=objective(qat(torch.tensor(x[0,ix])),yy,cw,tt,vv,gg,q,method);l.backward();opt.step();assert before==buffer_hash(qat)
        trace=qc.integer_trace(x[0,ix],qat.export())
        with torch.inference_mode():actual=qat(torch.tensor(x[0,ix]),trace=True)
        assert all(np.array_equal(a,b.numpy()) for a,b in zip(trace,actual));smoke.append(dict(method=method,rows=64,qat_exact=True))
    report=dict(status='PASS',synthetic_checks=['identical_zero_KL','wrong_teacher_mask','perturbed_view_mask','shift_invariance','finite_gradient','group_weight_direction'],
        smoke_training_only=smoke,source_point_count_median=boundary,source_group_counts=counts.tolist(),source_group_definition='2*history_bin+(original_current_points>train_median), before synthetic removal',
        teacher=teacher,train_rows=n,initial_views_shape=list(x.shape),wall_seconds=time.monotonic()-start,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},plan_sha256=sha(HERE/'plan.json'))
    assert report['wall_seconds']<PLAN['budgets']['preparation_seconds'];dump(LOG/'preflight.json',report);print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
