"""Integer oracle, invariants, same-base counterexamples and frozen dependencies."""
from ex_common import *

def rational(a,b):
    if not b:return 0
    s=-1 if a<0 else 1;q,r=divmod(abs(a),b)
    q+=int(2*r>b or (2*r==b and q%2));return max(-127,min(127,s*q))
def oracle(p):
    a=[[int(v) for v in row] for row in p];n=len(a);s=[sum(row[j] for row in a) for j in range(4)];lo=[min(row[j] for row in a) for j in range(4)];hi=[max(row[j] for row in a) for j in range(4)];span=[hi[j]-lo[j] for j in range(4)];ss=[sum(row[j]**2 for row in a) for j in range(4)]
    variance=[rational(508*(n*ss[j]-s[j]**2),n*n*span[j]**2) for j in range(4)]
    cov=rational(508*(n*sum(row[0]*row[1] for row in a)-s[0]*s[1]),n*n*span[0]*span[1])
    return np.array(variance[:2]+[cov]+variance[2:]+[rational(127*sum(abs(row[2])<=128 for row in a),n),rational(127*(2*s[3]-n*(lo[3]+hi[3])),n*span[3])],np.int8)
def main():
    LOG.mkdir(exist_ok=False);start=time.monotonic();checked={}
    for source in [ab.HERE/'evidence_manifest.json',sw.HERE/'evidence_manifest.json',base.HERE/'evidence_manifest.json']:
        entries=json.loads(source.read_text())['files']
        for rel,r in entries.items():
            h=r['sha256'] if isinstance(r,dict) else r
            if rel not in checked:assert sha(ROOT/rel)==h,rel;checked[rel]=h
    deps=json.loads((ABL/'dependency_manifest.json').read_text())
    for rel,h in deps['sha256'].items():assert sha(ROOT/rel)==h,rel;checked[rel]=h
    native=Native(True);old=base.Native();rng=np.random.default_rng(20260917);cases=[]
    for n in [1,2,3,4,7,8,31,128,255,511]:
        for v in [-32768,-256,-1,0,1,128,32767]:cases.append(np.full((n,4),v,np.int16))
        for _ in range(8):cases.append(rng.integers(-32768,32768,(n,4),dtype=np.int16))
    for p in cases:
        x=native(p);assert np.array_equal(x[:16],old(p)[1][0,COLS]);assert np.array_equal(x[16:],oracle(p))
        assert np.array_equal(x,native(p[rng.permutation(len(p))]))
    # Same N, means, extents and radial extrema; different interior distribution.
    xy=np.array([[-8,-8],[8,8],[0,0],[-4,-4],[-2,-2],[2,2],[4,4]],np.int16)*256
    p=np.c_[xy,np.zeros((7,2),np.int16)].astype(np.int16);p[:,3]=2560
    q=p.copy();q[3:,:2]=np.array([[-4,-4],[-4,-4],[4,4],[4,4]])*256
    r=p.copy();r[3:,1]=r[3:,1][::-1]
    pair=[]
    for name,z in [('interior_spread',q),('diagonal_orientation',r)]:
        a,b=native(p),native(z);assert np.array_equal(a[:16],b[:16]) and not np.array_equal(a[16:19],b[16:19]);pair.append(dict(name=name,first=p.tolist(),second=z.tolist(),base16=a[:16].tolist(),extra_first=a[16:].tolist(),extra_second=b[16:].tolist(),assigned_class_labels=False))
    p[:,2]=np.array([-4,4,0,-2,-1,1,2])*256;q=p.copy();q[:,2]=np.array([-4,4,0,-2,-.25,.25,2])*256
    a,b=native(p),native(q);assert np.array_equal(a[:16],b[:16]) and not np.array_equal(a[19:],b[19:]);pair.append(dict(name='velocity_distribution',first=p.tolist(),second=q.tolist(),base16=a[:16].tolist(),extra_first=a[16:].tolist(),extra_second=b[16:].tolist(),assigned_class_labels=False))
    p[:,3]=np.array([0,8,4,2,3,5,6])*256;q=p.copy();q[:,3]=np.array([0,8,4,1,1,7,7])*256
    a,b=native(p),native(q);assert np.array_equal(a[:16],b[:16]) and a[20]!=b[20];pair.append(dict(name='rcs_distribution',first=p.tolist(),second=q.tolist(),base16=a[:16].tolist(),extra_first=a[16:].tolist(),extra_second=b[16:].tolist(),assigned_class_labels=False))
    # Parameter-count controls initialize at the same normalized function.
    z=rng.normal(size=(128,23));init=[]
    for tag in VARIANTS:
        _,reference=model('base16',7);_,net=model(tag,7)
        ztag=z[:,take(tag)]
        with torch.inference_mode():err=float((reference(torch.tensor(z[:,:16],dtype=torch.float32))-net(torch.tensor(ztag,dtype=torch.float32))).abs().max())
        assert err<2e-6;init.append(dict(tag=tag,error=err))
    assert 508*511**2*65535**2 < 2**63
    dump(LOG/'synthetic_preflight.json',dict(status='PASS',cases=len(cases),counterexamples=pair,initialization=init,upstream_files_verified=len(checked),source_manifest_sha256={str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.suffix in ['.py','.json','.c','.md']},seconds=time.monotonic()-start,feature_numerator_conservative_abs_bound=508*511**2*65535**2,scope='Integer correctness/information counterexamples, no synthetic class or performance claims'))
    print('SYNTHETIC_PREFLIGHT_PASS',time.monotonic()-start,flush=True)
if __name__=='__main__':main()
