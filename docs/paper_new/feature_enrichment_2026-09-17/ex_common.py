"""Complementary feature study; imports frozen training/integer machinery."""
import importlib.util,sys,copy
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('ab_common',ROOT/'docs/paper_new/feature_ablation_2026-09-17/ab_common.py');ab=importlib.util.module_from_spec(spec);sys.modules['ab_common']=ab;spec.loader.exec_module(ab)
np=ab.np;torch=ab.torch;qc=ab.qc;pc=ab.pc;F=ab.F;base=ab.base;sw=ab.sw
json=ab.json;hashlib=ab.hashlib;time=ab.time;ctypes=ab.ctypes;subprocess=ab.subprocess
sha=ab.sha;dump=ab.dump;readcsv=ab.readcsv;writecsv=ab.writecsv;Trace=ab.Trace
MECH=ab.MECH;OLD=ab.OLD;ABL=ab.LOG;LOG=ROOT/'logs/feature_enrichment_20260917'
PLAN=json.loads((HERE/'plan.json').read_text());SEEDS=PLAN['training']['seeds'];VARIANTS=PLAN['variants'];COLS=PLAN['base_columns'];previous=ab.previous
def take(tag):return list(range(16))+[16+i for i in VARIANTS[tag]['extra']]+VARIANTS[tag].get('repeat_base_positions',[])
def columns(tag):return [COLS[i] if i<16 else i+5 for i in take(tag)]
def old_export(s):return ABL/'training'/('less_shape16_seed'+str(s))/'epoch60/export'
def model(tag,seed):
    original,net=ab.model('less_shape16',seed);w=net[0].weight.detach();d=VARIANTS[tag]['dim']
    net[0].weight=torch.nn.Parameter(torch.cat([w,torch.zeros((64,d-16),dtype=w.dtype)],dim=1));net[0].in_features=d;return original,net
def export(directory,bundle,cols,kind='trained_int8'):
    ab.export(directory,bundle,cols,kind);p=json.loads((directory/'params.json').read_text());p.update(input='Frozen16 proxy + specified new normalized distribution descriptors or redundant old inputs; no runtime normalization',frontend='feature_enrichment one-pass CPU reference; no hardware claim');dump(directory/'params.json',p)
def size_guard():
    size=sum(p.stat().st_size for p in LOG.rglob('*') if p.is_file());assert size<=PLAN['budget']['max_output_bytes'];return size
def native_source(geometry=1,distribution=1):
    source=(base.PREV/'native/kernel.c').read_text();ex,fr=base.scales()
    config='\n#define WANT_GEOMETRY %d\n#define WANT_DISTRIBUTION %d\n'%(geometry,distribution)
    config+='static const int base_columns[16]={'+','.join(map(str,COLS))+'};\n'
    config+='static const int base_shifts[16]={'+','.join(map(str,(ex+fr)[0,COLS]))+'};\n'
    return source+config+(HERE/'features.c').read_text()
class Native:
    def __init__(self,build=False):
        d=LOG/'native';d.mkdir(parents=True,exist_ok=True)
        if build:
            (d/'features.c').write_text(native_source());subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(d/'features.c'),'-o',str(d/'features.so')],check=True,capture_output=True)
        self.lib=ctypes.CDLL(str(d/'features.so'));self.lib.enrichment.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p]
    def __call__(self,p):
        p=np.ascontiguousarray(p,np.int16);assert p.ndim==2 and p.shape[1]==4 and 1<=len(p)<=511;x=np.empty(23,np.int8);self.lib.enrichment(p.ctypes.data,len(p),x.ctypes.data);return x
class Pools:
    def __init__(self):
        p=ab.pools.Pools('proxy');self.original=p;self.n=p.n;self.y=p.y;self.ys=p.ys;self.cal=p.cal;self.class_weights=p.class_weights;self.offsets=p.offsets;self.p=p.p;self.indices=p.indices
        names=['clean','uniform_quarter_0','central_half','synthetic','natural']
        self.arrays=[np.concatenate([a[:,COLS],np.load(LOG/'data/train'/(name+'.npy'))],axis=1) for a,name in zip(p.arrays,names)];self.x=np.concatenate(self.arrays)
        means=[];seconds=[]
        for a in self.arrays[:3]:means.append(a.mean(0,dtype=np.float64));seconds.append((a.astype(float)**2).mean(0))
        for a,groups in zip(self.arrays[3:],p.indices):
            mu=np.zeros(23);sec=np.zeros(23)
            for k,ids in enumerate(groups):
                if p.p[k]:mu+=p.p[k]*a[ids].mean(0,dtype=np.float64);sec+=p.p[k]*(a[ids].astype(float)**2).mean(0)
            means.append(mu);seconds.append(sec)
        w=np.array([.5,.125,.125,.125,.125]);self.mu=w@np.array(means);self.std=np.sqrt(np.maximum(w@np.array(seconds)-self.mu*self.mu,0));self.std[self.std<1e-6]=1
        assert np.array_equal(self.mu[:16],p.mu[COLS]) and np.array_equal(self.std[:16],p.std[COLS])
    def schedule(self,*args):return self.original.schedule(*args)
def validation(condition):
    a,y,meta=sw.validation(condition);return np.concatenate([a[:,COLS],np.load(LOG/'data/val'/(condition+'.npy'))],axis=1),y,meta
