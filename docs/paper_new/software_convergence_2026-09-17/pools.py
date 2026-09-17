"""Common train-only normalization/calibration and exactly paired epoch schedules."""
from sw_common import *

class Pools:
    def __init__(self,mode):
        self.mode=mode;d=LOG/'data/train';self.n=PLAN['data']['train_kept']
        self.arrays=[np.load(MECH/'data/train'/(mode+'.npy')),
            np.load(MECH/'raw/train'/mode/'uniform_quarter_0.npy'),np.load(MECH/'raw/train'/mode/'central_half.npy'),
            np.load(d/('synthetic_'+mode+'.npy')),np.load(d/('natural_'+mode+'.npy'))]
        self.offsets=np.r_[0,np.cumsum([len(a) for a in self.arrays])]
        old=np.load(MECH/'data/train/labels.npy')
        self.ys=[old,old,old,np.load(d/'synthetic_labels.npy'),np.load(d/'natural_labels.npy')]
        self.y=np.concatenate(self.ys);self.x=np.concatenate(self.arrays)
        match=json.loads((LOG/'data/matching.json').read_text());self.p=np.array(match['probabilities'])
        self.groups=[np.load(d/'synthetic_groups.npy'),np.load(d/'natural_groups.npy')]
        self.indices=[[np.flatnonzero(g==i) for i in range(12)] for g in self.groups]
        means=[];seconds=[]
        for a in self.arrays[:3]:means.append(a.mean(0,dtype=np.float64));seconds.append((a.astype(float)**2).mean(0))
        for a,groups in zip(self.arrays[3:],self.indices):
            mu=np.zeros(21);sec=np.zeros(21)
            for k,ids in enumerate(groups):
                if self.p[k]:mu+=self.p[k]*a[ids].mean(0,dtype=np.float64);sec+=self.p[k]*(a[ids].astype(float)**2).mean(0)
            means.append(mu);seconds.append(sec)
        weights=np.array([.5,.125,.125,.125,.125])
        self.mu=weights@np.array(means);self.std=np.sqrt(np.maximum(weights@np.array(seconds)-self.mu*self.mu,0));self.std[self.std<1e-6]=1
        classprob=.75*np.bincount(old,minlength=2)/len(old)+.25*np.array([self.p[:6].sum(),self.p[6:].sum()])
        self.class_weights=1/(2*classprob)
        rng=np.random.default_rng(20260917);cal=[]
        for v,n in enumerate((8192,2048,2048)):cal.append(self.offsets[v]+rng.choice(self.n,n,replace=False))
        for source in (0,1):cal.append(self.offsets[source+3]+self.draw_sparse(source,2048,rng))
        self.cal=np.concatenate(cal).astype(np.int64);assert len(self.cal)==16384
    def draw_sparse(self,source,n,rng):
        result=[]
        for group,count in enumerate(quota(n,self.p)):
            if count:
                ids=self.indices[source][group];assert len(ids)
                result.append(ids[np.floor(rng.random(int(count))*len(ids)).astype(np.int64)])
        return np.concatenate(result)
    def schedule(self,seed,epoch,source):
        nr=178890;nq=44722+(epoch%2==0);nc=44723-(epoch%2==0)
        rng=np.random.default_rng(seed+100003*epoch);order=rng.permutation(self.n)
        sparse=self.draw_sparse(source,89445,np.random.default_rng(seed+200003*epoch))
        ids=np.concatenate([order[:nr],self.offsets[1]+order[nr:nr+nq],
            self.offsets[2]+order[nr+nq:nr+nq+nc],self.offsets[3+source]+sparse])
        views=np.repeat([0,1,2,3],[nr,nq,nc,89445]);permutation=rng.permutation(self.n)
        return ids[permutation],views[permutation]

def preflight():
    assert json.loads((LOG/'preparation.json').read_text())['status']=='PASS'
    out=LOG/'prepared';out.mkdir(exist_ok=False);reports=[]
    previous=None
    for mode in MODES:
        p=Pools(mode);np.savez(out/(mode+'.npz'),mean=p.mu,std=p.std,calibration=p.cal,class_weights=p.class_weights)
        if previous is not None:assert np.array_equal(previous,p.cal)
        previous=p.cal.copy();checks=[]
        for seed in SEEDS:
            for epoch in (1,2,20,21,80):
                a,av=p.schedule(seed,epoch,0);b,bv=p.schedule(seed,epoch,1)
                assert len(a)==p.n and np.array_equal(av,bv)
                assert np.array_equal(a[av!=3],b[bv!=3])
                for source,ids in enumerate((a,b)):
                    ix=ids[av==3]-p.offsets[3+source]
                    assert np.array_equal(np.bincount(p.groups[source][ix],minlength=12),quota(89445,p.p))
                assert np.array_equal(p.y[a],p.y[b]),'Paired class sequence changed'
                checks.append(dict(seed=seed,epoch=epoch,view_counts=np.bincount(av,minlength=4).tolist(),class_counts=np.bincount(p.y[a],minlength=2).tolist()))
        # Train-only microstep, fold, exact QAT and NumPy integer forward.
        torch.manual_seed(7);net=qc.model();ix,_=p.schedule(7,1,0);ix=ix[:128]
        raw=torch.tensor(p.x[ix],dtype=torch.float64);norm=torch.tensor((p.x[ix]-p.mu)/p.std,dtype=torch.float32);y=torch.tensor(p.y[ix])
        opt=torch.optim.AdamW(net.parameters(),lr=.001);loss=F.cross_entropy(net(norm),y);loss.backward();opt.step()
        net.eval();folded=qc.fold(net,p.mu,p.std)
        with torch.inference_mode():err=float((net.double()(torch.tensor((p.x[ix]-p.mu)/p.std,dtype=torch.float64))-folded(raw)).abs().max())
        assert err<1e-9
        q=qc.FrozenQAT(folded,torch.tensor(p.x[p.cal],dtype=torch.float64));loss=F.cross_entropy(q(raw),y);loss.backward()
        q.eval();bundle=q.export()
        with torch.inference_mode():trace=[v.numpy() for v in q(raw,trace=True)]
        assert all(np.array_equal(a,b) for a,b in zip(trace,qc.integer_trace(p.x[ix],bundle)))
        reports.append(dict(mode=mode,schedules=checks,fold_error=err,qat_integer_exact=True,class_weights=p.class_weights.tolist(),calibration_sha256=hashlib.sha256(p.cal.tobytes()).hexdigest()))
    dump(LOG/'training_preflight.json',dict(status='PASS',checks=reports,scope='Train-only; no full training trajectory or validation-based decision'))
    print('TRAINING_PREFLIGHT_PASS',flush=True)

if __name__=='__main__':preflight()
