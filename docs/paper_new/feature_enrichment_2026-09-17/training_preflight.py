"""Actual train pools, paired initialization, fold and exact variable-dim QAT/C."""
from ex_common import *
def main():
    assert json.loads((LOG/'preparation.json').read_text())['status']=='PASS';out=LOG/'training_preflight';out.mkdir(exist_ok=False);p=Pools();checks=[];rng=np.random.default_rng(20260917)
    native=Native();invariants=[]
    for n in [1,2,3,7,31,127]:
        z=rng.integers(-256,256,(n,4),dtype=np.int16);a=native(z);b=z.copy();b[:,:2]=2*b[:,:2]+111
        assert np.array_equal(a[16:19],native(b)[16:19])
        b=z.copy();b[:,3]=2*b[:,3]+123;assert np.array_equal(a[[20,22]],native(b)[[20,22]])
        assert np.array_equal(a[16:],native(np.repeat(z,2,axis=0))[16:])
        if n==2:
            for channel,index in [(0,16),(1,17),(2,19),(3,20)]:
                if z[0,channel]!=z[1,channel]:assert a[index]==127
        invariants.append(dict(n=n,geometry_translation_scale=True,rcs_affine=True,uniform_duplication=True))
    dump(out/'invariants.json',invariants)
    np.savez(out/'calibration.npz',mean=p.mu,std=p.std,calibration=p.cal,class_weights=p.class_weights)
    assert len(p.cal)==16384 and np.array_equal(p.cal,np.load(OLD/'prepared/proxy.npz')['calibration'])
    ids,views=p.schedule(7,1,1);assert np.bincount(views).tolist()==[178890,44722,44723,89445]
    for tag in VARIANTS:
        cols=take(tag);ix=ids[:128];x=p.x[:,cols];mu=p.mu[cols];std=p.std[cols];_,net=model(tag,7)
        raw=torch.tensor(x[ix],dtype=torch.float64);target=torch.tensor(p.y[ix]);opt=torch.optim.AdamW(net.parameters(),lr=.001)
        loss=F.cross_entropy(net(torch.tensor((x[ix]-mu)/std,dtype=torch.float32)),target);loss.backward();opt.step();net.eval();fold=qc.fold(net,mu,std)
        with torch.inference_mode():err=float((net.double()(torch.tensor((x[ix]-mu)/std,dtype=torch.float64))-fold(raw)).abs().max())
        assert err<1e-9;q=qc.FrozenQAT(fold,torch.tensor(x[p.cal],dtype=torch.float64));q.eval();bundle=q.export();ab.bounds(bundle);d=out/tag;export(d,bundle,columns(tag));c=Trace(d)
        with torch.inference_mode():qt=[z.numpy() for z in q(raw,trace=True)]
        assert all(np.array_equal(a,b) and np.array_equal(a,cc) for a,b,cc in zip(qt,qc.integer_trace(x[ix],bundle),c(x[ix])))
        z=rng.integers(-127,128,(1024,len(cols)),dtype=np.int8);assert all(np.array_equal(a,b) for a,b in zip(c(z),qc.integer_trace(z,bundle)))
        vals=np.array([sign*(k*65536+32768) for sign in [-1,1] for k in range(40)],np.int64);got=np.empty(len(vals),np.int32);c.lib.test_round(vals.ctypes.data,len(vals),got.ctypes.data);assert np.array_equal(got,np.rint(vals/65536).astype(np.int32))
        checks.append(dict(tag=tag,dimension=len(cols),fold_error=err,integer_three_implementations_exact=True))
    stats=[];names=PLAN['features']['geometry']+PLAN['features']['distribution']
    for pool in [0,4]:
        a=p.arrays[pool];y=p.ys[pool]
        for cls in [0,1]:
            z=a[y==cls,16:]
            for j,name in enumerate(names):stats.append(dict(pool='kept' if pool==0 else 'natural_sparse',label=cls,feature=name,samples=len(z),mean=float(z[:,j].mean()/127),q10=float(np.quantile(z[:,j],.1)/127),median=float(np.median(z[:,j])/127),q90=float(np.quantile(z[:,j],.9)/127),zero_fraction=float(np.mean(z[:,j]==0)),maximum_fraction=float(np.mean(np.abs(z[:,j].astype(int))==127))))
    writecsv(LOG/'train_feature_distributions.csv',stats)
    dump(LOG/'training_preflight.json',dict(status='PASS',checks=checks,calibration_rows=16384,calibration_sha256=hashlib.sha256(p.cal.tobytes()).hexdigest(),class_weights=p.class_weights.tolist(),visited_per_epoch=357780,scope='Train-only microsteps and descriptive class distributions; not additional complete training or feature selection',source_sha256={str(f.relative_to(ROOT)):sha(f) for f in HERE.iterdir() if f.suffix in ['.py','.c','.json','.md']}))
    print('TRAINING_PREFLIGHT_PASS',flush=True)
if __name__=='__main__':main()
