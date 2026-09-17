"""Explanatory Monte Carlo, no classifier fitting or tuning."""
from ex_common import *

def main():
    assert json.loads((LOG/'training/summary.json').read_text())['status']=='PASS';out=LOG/'explanation/point_count_simulation.json';assert not out.exists();rng=np.random.default_rng(20260917);rows=[]
    for shape in ['uniform','central','two_lobes']:
        for n in [1,2,3,4,8,16,32,64]:
            if shape=='uniform':x=rng.uniform(-1,1,(2000,n))
            elif shape=='central':x=np.clip(rng.normal(0,.3,(2000,n)),-1,1)
            else:x=np.clip(rng.choice([-1,1],(2000,n))*.8+rng.normal(0,.1,(2000,n)),-1,1)
            q=np.rint(x*256).astype(np.int64);s=q.sum(1);ss=(q*q).sum(1);span=q.max(1)-q.min(1);num=508*(n*ss-s*s);den=n*n*span*span
            code=np.zeros(2000,np.int64);valid=den>0;a=num[valid]//den[valid];r=num[valid]%den[valid];a+=((2*r>den[valid])|((2*r==den[valid])&(a%2==1))).astype(np.int64);code[valid]=a;assert np.all((code>=0)&(code<=127));normalized=code/127
            rows.append(dict(distribution=shape,points=n,replicates=2000,mean=float(normalized.mean()),q10=float(np.quantile(normalized,.1)),q50=float(np.median(normalized)),q90=float(np.quantile(normalized,.9)),zero_span=int(np.sum(~valid))))
    dump(out,dict(status='PASS',rows=rows,scope='Post-training fixed-seed unlabeled simulation of normalized variance vs point count; no classifier/threshold fitting or selection. Shapes are idealized input distributions, not radar classes.'))
    print('POINT_COUNT_SIMULATION_PASS',len(rows)*2000,flush=True)
if __name__=='__main__':main()
