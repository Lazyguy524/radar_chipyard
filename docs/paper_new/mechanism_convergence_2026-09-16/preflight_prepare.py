"""Python integer preflight and factorial data composition before training."""
from common import *

def main():
    LOG.mkdir(exist_ok=False);native=Native(True)
    old=module('mechanism_old_kernel',ROOT/'docs/paper_new/conditional_statistics_2026-09-16/kernel.py')
    oldk=old.Kernel(PREV/'native',False);rng=np.random.default_rng(20260916);cases=0
    sizes=[1,2,3,4,5,7,8,9,15,16,17,31,32,33,63,64,65,127,128,129,255,256,257,511]
    ex,fr=scales()
    for n in sizes:
        for kind in range(4):
            p=rng.integers(-32768,32768,(n,4),dtype=np.int16)
            if kind==1:p[:]=p[0]
            if kind==2:p[:,1]=p[:,0]
            if kind==3:p[:,:2]//=64;p[:,:2]+=25000
            baseline,_,_=oldk(p)
            for mb,vb in [(24,24)]+[tuple(x) for x in PLAN['precision']['configurations']]:
                raw,z=native(p,mb,vb);expected=mixed(baseline[0],baseline[1])
                means,_,_=old.python_moments(p,mb);_,moments,_=old.python_moments(p,vb)
                for flag in range(4):
                    if flag&1:
                        expected[flag,[1,2,14,18]]=means
                        ax,ay=abs(int(means[0])),abs(int(means[1]));expected[flag,9]=max(ax,ay)+(min(ax,ay)>>1)
                    if flag&2:expected[flag,SHAPES]=[moments[0],moments[1],moments[2],max(moments[:2]),min(moments[:2])]
                assert np.array_equal(raw,expected)
                quant=np.clip(np.rint(expected.astype(float)/np.exp2(ex+fr)),-127,127).astype(np.int8)
                assert np.array_equal(quant,z);cases+=1
    points=np.load(PREV/'data/diagnostic/points_q8.npy');offsets=np.load(PREV/'data/diagnostic/offsets.npy')
    proxy=np.load(PREV/'data/diagnostic/proxy_scaled_clean.npy');moment=np.load(PREV/'data/diagnostic/moment24_clean.npy')
    for i in range(len(offsets)-1):
        _,z=native(points[offsets[i]:offsets[i+1]])
        assert np.array_equal(z,mixed(proxy[i],moment[i]))
    sources=[HERE/'plan.json',HERE/'common.py',HERE/'mechanism.c',HERE/'preflight_prepare.py',PREV/'native/kernel.c',PREV/'data/output_scale_exponents.json']
    sizes_out={};out=LOG/'data';out.mkdir()
    for split in ['train','val']:
        d=out/split;d.mkdir();p=PREV/'data'/split
        a=np.load(p/'proxy_scaled.npy');b=np.load(p/'moment24.npy');family=mixed(a,b)
        assert np.array_equal(family[0],a) and np.array_equal(family[3],b)
        for flag,mode in enumerate(MODES):np.save(d/(mode+'.npy'),family[flag])
        np.save(d/'labels.npy',np.load(p/'labels.npy'));sizes_out[split]=len(a)
        sources.extend([p/'proxy_scaled.npy',p/'moment24.npy',p/'labels.npy',p/'metadata.csv'])
    dump(out/'scales.json',dict(exponents=ex.tolist(),fractional_bits=fr.tolist(),modes=MODES))
    # Exact worst-case bounds for all retained counts and tested reciprocal widths.
    bounds=[]
    for r in [8,12,16,24]:
        maxima=[0,0]
        for n in range(1,512):
            inv=old.reciprocal(n,r);u=old.rnd(n*65535*inv,r-4)
            maxima[0]=max(maxima[0],n*65535**2*inv);maxima[1]=max(maxima[1],u*u)
        assert max(maxima)<2**63
        bounds.append(dict(reciprocal_fraction_bits=r,max_sum_square_times_inverse=maxima[0],max_centered_mean_square=maxima[1],signed64_safe=True))
    report=dict(status='PASS',python_integer_cases=cases,prior_real_cluster_equivalence=len(offsets)-1,samples=sizes_out,bounds=bounds,
        plan_sha256=sha(HERE/'plan.json'),source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources})
    dump(LOG/'preflight.json',report);print(json.dumps(report))

if __name__=='__main__':main()
