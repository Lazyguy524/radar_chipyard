"""Frozen input lineage, exact rational oracle, invariants and bounded simulation."""
from dim_common import *
from fractions import Fraction
from itertools import combinations_with_replacement

def quant(a,b):return max(-127,min(127,round(Fraction(int(a),int(b))))) if b else 0
def oracle(p):
    n=len(p);z=[quant(127,n)]+[0]*12
    for c in range(4):
        a=sorted(int(x) for x in p[:,c]);qq=[]
        for k in [1,2,3]:
            j,r=divmod(k*(n-1),4);qq.append((4-r)*a[j]+r*a[min(j+1,n-1)])
        q1,q2,q3=qq;span=a[-1]-a[0]
        z[1+c]=quant(127*(q3-q1),4*span);z[5+c]=quant(127*(q3+q1-2*q2),q3-q1);z[9+c]=quant(127*(2*q2-4*(a[0]+a[-1])),4*span)
    return np.array(z,np.int8)

def main():
    LOG.mkdir(exist_ok=False);start=time.monotonic();checked={}
    for source in [ex.HERE/'evidence_manifest.json',ab.HERE/'evidence_manifest.json',sw.HERE/'evidence_manifest.json',base.HERE/'evidence_manifest.json']:
        for rel,r in json.loads(source.read_text())['files'].items():
            h=r['sha256'] if isinstance(r,dict) else r
            if rel not in checked:assert sha(ROOT/rel)==h,rel;checked[rel]=h
    deps=json.loads((ABL/'dependency_manifest.json').read_text())
    for rel,h in deps['sha256'].items():assert sha(ROOT/rel)==h,rel;checked[rel]=h
    dump(LOG/'dependency_manifest.json',dict(sha256=checked,scope='Old immutable evidence verified before preparation'))
    native=Native(True);old=ex.Native();rng=np.random.default_rng(20260917);cases=[]
    for n in [1,2,3,4,7,8,31,128,255,511]:
        for v in [-32768,-256,-1,0,1,128,32767]:cases.append(np.full((n,4),v,np.int16))
        for _ in range(8):cases.append(rng.integers(-32768,32768,(n,4),dtype=np.int16))
    for p in cases:
        x=native(p);assert np.array_equal(x[:23],old(p));assert np.array_equal(x[23:],oracle(p))
        assert np.array_equal(x,native(p[rng.permutation(len(p))]))
        if len(p)==1:assert x[23]==127 and not x[24:].any()
        if len(p)==2:
            assert x[23]==64
            for c in range(4):
                if p[0,c]!=p[1,c]:assert x[24+c]==64 and x[28+c]==x[32+c]==0
    for n in [1,2,3,8,31,127]:
        p=rng.integers(-256,256,(n,4),dtype=np.int16);assert np.array_equal(native(p)[23:],native((p*2+11).astype(np.int16))[23:])
    # Moment-matched unlabelled RCS sets, preserving all existing23 descriptors.
    found=[];seen={}
    for mid in combinations_with_replacement(range(13),5):
        values=(0,)+mid+(12,);key=(sum(values),sum(v*v for v in values));p=np.zeros((7,4),np.int16);p[:,0]=256;p[:,3]=np.array(values)*256;x=native(p)
        if key in seen:
            q,y=seen[key]
            if np.array_equal(x[:23],y[:23]) and (x[31]!=y[31] or x[35]!=y[35]):
                found.append(dict(first=q.tolist(),second=p.tolist(),base23=x[:23].tolist(),new_first=y[23:].tolist(),new_second=x[23:].tolist(),class_labels_assigned=False));break
        else:seen[key]=(p,x)
    assert found
    init=[];z=rng.normal(size=(128,36))
    for tag in VARIANTS:
        _,net=model(tag,7);reference='core8' if tag in ['core8','distribution12','combined15'] else 'proxy12' if tag=='proxy12' else 'base16';_,ref=model(reference,7)
        ztag=z[:,take(tag)].copy()
        if tag=='redundant36':ztag[:,24:]=z[:,take(tag)[24:]]
        with torch.inference_mode():error=float((net(torch.tensor(ztag,dtype=torch.float32))-ref(torch.tensor(z[:,take(reference)],dtype=torch.float32))).abs().max())
        assert error<2e-6;init.append(dict(tag=tag,reference=reference,max_error=error))
    rates=[]
    for n in [2,8,32,128,511]:
        p=rng.integers(-4096,4096,(n,4),dtype=np.int16);s=time.monotonic()
        for _ in range(200):native(p)
        rates.append(dict(points=n,seconds_per_cluster=(time.monotonic()-s)/200,scope='Python call plus CPU C extraction smoke timing; not FPGA latency'))
    # Different type7 estimates after duplication are a disclosed estimator property.
    a=np.zeros((4,4),np.int16);a[:,3]=np.array([0,1,2,8])*256
    repetition=dict(original=native(a)[23:].tolist(),duplicated=native(np.repeat(a,2,axis=0))[23:].tolist(),scope='Linear sample-quantile interpolation may change under repeated points; support also changes. Not independent information or a replication-invariance claim.')
    dump(LOG/'synthetic_preflight.json',dict(status='PASS',cases=len(cases),counterexamples=found,initialization=init,smoke_cost=rates,finite_sample_repetition=repetition,upstream_files_verified=len(checked),seconds=time.monotonic()-start,source_sha256={str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.suffix in ['.py','.json','.c','.md']}))
    print('PREFLIGHT_PASS',time.monotonic()-start,flush=True)
if __name__=='__main__':main()
