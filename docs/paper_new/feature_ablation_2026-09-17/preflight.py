"""Train-only review of projection, frozen sources and integer/C execution."""
from ab_common import *

def main():
    start=time.monotonic();LOG.mkdir(exist_ok=False);out=LOG/'preflight';out.mkdir()
    manifest=json.loads((sw.HERE/'evidence_manifest.json').read_text())['files']
    for name,entry in manifest.items():assert sha(ROOT/name)==entry['sha256'],name
    audit=json.loads((OLD/'preparation.json').read_text());assert audit['status']=='PASS'
    sets=[{x['sequence'] for x in s['sequences']} for s in audit['splits']]
    assert list(map(len,sets))==[113,27] and not sets[0]&sets[1]
    p=pools.Pools('proxy');saved=np.load(OLD/'prepared/proxy.npz')
    for key,value in [('mean',p.mu),('std',p.std),('calibration',p.cal),('class_weights',p.class_weights)]:assert np.array_equal(saved[key],value),key
    assert all(np.array_equal(x[:,6],x[:,10]) for x in p.arrays)
    schedules=[]
    for seed in SEEDS:
        for epoch in [1,2,20,21,80]:
            ids,views=p.schedule(seed,epoch,1);counts=np.bincount(views,minlength=4).tolist()
            assert counts==[178890,44722+(epoch%2==0),44723-(epoch%2==0),89445]
            assert len(ids)==357780 and np.all((ids>=0)&(ids<len(p.x)))
            schedules.append(dict(seed=seed,epoch=epoch,counts=counts))
    rng=np.random.default_rng(20260917);native=base.Native();checks=[]
    points=[np.full((n,4),v,np.int16) for n in [1,2,3,4,7,16,63,128,511] for v in [-32768,-256,-1,0,1,256,32767]]
    points += [rng.integers(-32768,32768,size=(int(rng.integers(1,512)),4),dtype=np.int16) for _ in range(93)]
    for tag in VARIANTS:
        cols=keep(tag);dim=len(cols);d=out/tag;d.mkdir();original,net=model(tag,7)
        normalized=(p.x[p.cal[:128]]-p.mu)/p.std;masked=normalized.copy()
        for j in VARIANTS[tag]['remove']:
            if j!=10 or 6 not in cols:masked[:,j]=0
        with torch.inference_mode():err=float((original(torch.tensor(masked,dtype=torch.float32))-net(torch.tensor(normalized[:,cols],dtype=torch.float32))).abs().max())
        assert err<2e-6,(tag,err)
        ix,_=p.schedule(7,1,1);ix=ix[:128];raw=torch.tensor(p.x[ix][:,cols],dtype=torch.float64)
        opt=torch.optim.AdamW(net.parameters(),lr=.001);loss=F.cross_entropy(net(torch.tensor(((p.x[ix]-p.mu)/p.std)[:,cols],dtype=torch.float32)),torch.tensor(p.y[ix]));loss.backward();opt.step()
        net.eval();folded=qc.fold(net,p.mu[cols],p.std[cols])
        with torch.inference_mode():fold_err=float((net.double()(torch.tensor(((p.x[ix]-p.mu)/p.std)[:,cols],dtype=torch.float64))-folded(raw)).abs().max())
        assert fold_err<1e-9
        q=qc.FrozenQAT(folded,torch.tensor(p.x[p.cal][:,cols],dtype=torch.float64));q.eval();bundle=q.export();export(d/'export',bundle,cols);c=Trace(d/'export')
        with torch.inference_mode():qt=[v.numpy() for v in q(raw,trace=True)]
        assert all(np.array_equal(a,b) and np.array_equal(a,cc) for a,b,cc in zip(qt,qc.integer_trace(p.x[ix][:,cols],bundle),c(p.x[ix][:,cols])))
        z=rng.integers(-127,128,size=(257,dim),dtype=np.int8)
        assert all(np.array_equal(a,b) for a,b in zip(c(z),qc.integer_trace(z,bundle)))
        ties=np.array([sign*((k<<16)+32768) for sign in [-1,1] for k in range(32)],np.int64);got=np.empty(len(ties),np.int32)
        c.lib.test_round(ties.ctypes.data,len(ties),got.ctypes.data);assert np.array_equal(got,np.rint(ties/65536).astype(np.int32))
        source=frontend_source(tag)+'\nvoid subset_test(const radar_feature21_golden_point_t*p,uint32_t n,int8_t*x){subset_frontend(p,n,x);}\n'
        (d/'frontend.c').write_text(source);subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(d/'frontend.c'),'-o',str(d/'frontend.so')],check=True,capture_output=True)
        lib=ctypes.CDLL(str(d/'frontend.so'));lib.subset_test.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p]
        for point in points:
            got=np.empty(dim,np.int8);lib.subset_test(point.ctypes.data,len(point),got.ctypes.data);expected=native(point)[1][0,cols]
            assert np.array_equal(got,expected),(tag,len(point),got.tolist(),expected.tolist())
        checks.append(dict(tag=tag,columns=cols,initialization_error=err,fold_error=fold_err,frontend_cases=len(points),qat_numpy_c_exact=True))
    duplicate=[]
    for seed in SEEDS:
        b=qc.load_export(old_export(seed));m=merge_bundle(b);d=out/('merged_seed'+str(seed));export(d,m,keep('dedup20'),'diagnostic_signed9_logical_int16_storage');c=Trace(d)
        x=np.vstack([p.x[p.cal],rng.integers(-127,128,size=(1024,21),dtype=np.int8)]);x[:,10]=x[:,6]
        old=qc.integer_trace(x,b);new=qc.integer_trace(x[:,keep('dedup20')],m);ct=c(x[:,keep('dedup20')])
        assert all(np.array_equal(a,z) and np.array_equal(a,cc) for a,z,cc in zip(old,new,ct))
        w=m['layers'][0]['weight'][:,6]
        duplicate.append(dict(seed=seed,rows=len(x),outside_int8=int(np.sum((w<-127)|(w>127))),min=int(w.min()),max=int(w.max()),all_layer_exact=True))
    seconds=time.monotonic()-start;assert seconds<PLAN['budget']['preparation_seconds']
    frozen={str(x.relative_to(ROOT)):sha(x) for x in HERE.iterdir() if x.suffix in ['.py','.c','.json','.md']}
    dump(LOG/'preflight.json',dict(status='PASS',wall_seconds=seconds,old_manifest_files=len(manifest),train_sequences=113,val_sequences=27,checks=checks,schedules=schedules,duplicate=duplicate,source_sha256=frozen,scope='Train-only plus arithmetic boundary/random tests; no validation selection'))
    print('PREFLIGHT_PASS',seconds,flush=True)
if __name__=='__main__':main()
