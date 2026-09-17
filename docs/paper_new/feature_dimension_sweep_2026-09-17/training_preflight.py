"""Actual train pools, paired initialization, fold and exact variable-dim QAT/C."""
from dim_common import *
def main():
    assert json.loads((LOG/'preparation.json').read_text())['status']=='PASS';start=time.monotonic();out=LOG/'training_preflight';out.mkdir(exist_ok=False);p=Pools();checks=[];rng=np.random.default_rng(20260917)
    native=Native();low=[]
    for n in [1,2,3]:
        for _ in range(20):
            points=rng.integers(-32768,32768,(n,4),dtype=np.int16);v=native(points)
            for ch in range(4):
                if np.ptp(points[:,ch].astype(np.int64)) and n in [2,3]:assert v[24+ch]==64
                if n==3:assert int(v[28+ch])==-int(v[32+ch])
        low.append(dict(n=n,cases=20,scope='N2/N3 normalized IQR constant for nonzero range; N3 quartile asymmetry is negative median position'))
    dump(out/'low_count_properties.json',low)
    previous_cal=np.load(ENR/'training_preflight/calibration.npz')
    assert np.array_equal(p.mu[:23],previous_cal['mean']) and np.array_equal(p.std[:23],previous_cal['std'])
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
    stats=[];names=PLAN['features']['new']
    for pool in [0,4]:
        a=p.arrays[pool];y=p.ys[pool]
        for cls in [0,1]:
            z=a[y==cls,23:]
            for j,name in enumerate(names):stats.append(dict(pool='kept' if pool==0 else 'natural_sparse',label=cls,feature=name,samples=len(z),mean=float(z[:,j].mean()/127),q10=float(np.quantile(z[:,j],.1)/127),median=float(np.median(z[:,j])/127),q90=float(np.quantile(z[:,j],.9)/127),zero_fraction=float(np.mean(z[:,j]==0)),maximum_fraction=float(np.mean(np.abs(z[:,j].astype(int))==127))))
    writecsv(LOG/'train_feature_distributions.csv',stats)
    dump(LOG/'training_preflight.json',dict(status='PASS',seconds=time.monotonic()-start,checks=checks,calibration_rows=16384,calibration_sha256=hashlib.sha256(p.cal.tobytes()).hexdigest(),class_weights=p.class_weights.tolist(),visited_per_epoch=357780,scope='Train-only microsteps and descriptive class distributions; not additional complete training or feature selection',source_sha256={str(f.relative_to(ROOT)):sha(f) for f in HERE.iterdir() if f.suffix in ['.py','.c','.json','.md']}))
    replay=[]
    for tag in REFERENCES:
        for seed in SEEDS:
            c=Trace(export_path(tag,seed),False)
            for condition in CONDITIONS:
                x=validation(condition)[0][:,take(tag)];got=c(x)[-1]
                expected=np.load(ENR/'evaluation'/(tag+'_seed%d_%s_prediction.npy'%(seed,condition)))
                assert np.array_equal(got.argmax(1),expected)
                if condition=='clean':assert np.array_equal(got,np.load(export_path(tag,seed).parent/'val_logits.npy'))
                replay.append(dict(tag=tag,seed=seed,condition=condition,rows=len(x),prediction_mismatches=0))
    dump(LOG/'reference_replay.json',dict(status='PASS',checks=replay,scope='Six frozen reference models rerun without training; same reconstructed features and integer outputs'))
    record=json.loads((LOG/'training_preflight.json').read_text());record['seconds']=time.monotonic()-start;record['includes_reference_replay']=True;dump(LOG/'training_preflight.json',record)
    print('TRAINING_PREFLIGHT_PASS',flush=True)
if __name__=='__main__':main()
