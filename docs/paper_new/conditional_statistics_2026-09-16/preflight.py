"""Synthetic mechanism, integer equivalence and width proof before data fitting."""
from kernel import *

def main():
    LOG.mkdir(exist_ok=False);k=Kernel(LOG/'native');rng=np.random.default_rng(20260916)
    checked=0;worst=0
    for n in [1,2,3,4,5,7,8,9,16,17,64,65,128,129,256,257,511]:
        for t in range(8):
            q=rng.integers(-32768,32768,(n,4),dtype=np.int16)
            raw,legacy,neg=k(q)
            reconstructed=np.clip(np.rint(raw[0].astype(float)*105/65536),-127,127).astype(np.int8)
            reconstructed[13]=raw[0,13];assert np.array_equal(reconstructed,legacy)
            for mode,r,center in [(1,24,True),(2,16,True),(3,16,False)]:
                mu,var,negative=python_moments(q,r,center)
                assert np.array_equal(raw[mode,[1,2,14,18]],mu)
                assert np.array_equal(raw[mode,[3,4,10]],var) and neg[mode-1]==negative
            checked+=1
    a=np.zeros((5,4),np.int16);a[:,0]=np.array([-4,0,0,0,4])*256
    b=a.copy();b[:,0]=np.array([-4,-4,0,4,4])*256
    ra,la,_=k(a);rb,lb,_=k(b)
    assert np.array_equal(la,lb) and ra[1,3]!=rb[1,3]
    shifted=a.copy();shifted[:,0]+=100*256
    rs,ls,_=k(shifted)
    assert np.array_equal(ra[1,[3,4,10,11,12]],rs[1,[3,4,10,11,12]])
    constant=np.tile(np.array([10*256,0,0,0],np.int16),(5,1));rc,lc,_=k(constant)
    assert rc[0,1]==1600 and rc[1,1]==2560
    # All N and all signed Q8.8 values: absolute differences <=65535.
    bounds=[]
    for r in [16,24]:
        invprod=max(n*65535**2*reciprocal(n,r) for n in range(1,512))
        muprod=max(n*65535*reciprocal(n,r) for n in range(1,512))
        mumax=max(abs(rnd(n*65535*reciprocal(n,r),r-4)) for n in range(1,512))
        assert max(invprod,muprod,mumax**2)<2**63
        bounds.append(dict(reciprocal_bits=r,max_sum_square_times_reciprocal=invprod,max_sum_times_reciprocal=muprod,
            max_mean_q12_square=mumax**2,reciprocal_rom_bits=512*(r+1),signed64_safe=True))
    report=dict(status='PASS',integer_cases=checked,python_c_equal=True,proxy_reconstruction_equal=True,
        same_extent_different_interior=dict(old_features_equal=True,new_x_variance=[int(ra[1,3]),int(rb[1,3])]),
        centered_shape_translation_invariant=True,mean_n5_constant10=dict(old=6.25,new=10.0),bounds=bounds,
        plan_sha256=sha(HERE/'plan.json'),source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'kernel.py',HERE/'moments.c',HERE/'preflight.py']})
    dump(LOG/'preflight.json',report);print(json.dumps(report))

if __name__=='__main__':main()
