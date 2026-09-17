"""Bounded dimension/representation sweep; frozen previous stage is read-only."""
import importlib.util,sys,copy
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('ex_common',ROOT/'docs/paper_new/feature_enrichment_2026-09-17/ex_common.py');ex=importlib.util.module_from_spec(spec);sys.modules['ex_common']=ex;spec.loader.exec_module(ex)
np=ex.np;torch=ex.torch;qc=ex.qc;pc=ex.pc;F=ex.F;base=ex.base;sw=ex.sw;ab=ex.ab
json=ex.json;hashlib=ex.hashlib;time=ex.time;ctypes=ex.ctypes;subprocess=ex.subprocess
sha=ex.sha;dump=ex.dump;readcsv=ex.readcsv;writecsv=ex.writecsv;Trace=ex.Trace;previous=ex.previous
OLD=ex.OLD;MECH=ex.MECH;ABL=ex.ABL;ENR=ex.LOG;LOG=ROOT/'logs/feature_dimension_sweep_20260917'
PLAN=json.loads((HERE/'plan.json').read_text());SEEDS=PLAN['training']['seeds'];VARIANTS=PLAN['variants'];COLS=ex.COLS
REFERENCES=['base16','combined23'];CONDITIONS=PLAN['evaluation']['conditions']
def take(tag):return list(range(16 if tag=='base16' else 23)) if tag in REFERENCES else VARIANTS[tag]['columns']
def columns(tag):return [COLS[i] if i<16 else i+5 for i in take(tag)]
def model(tag,seed):
    original,net=ex.model('base16',seed);w=net[0].weight.detach();weights=[]
    for position,col in enumerate(take(tag)):
        duplicate=tag=='redundant36' and position>=24
        weights.append(w[:,col].clone() if col<16 and not duplicate else torch.zeros(64,dtype=w.dtype))
    net[0].weight=torch.nn.Parameter(torch.stack(weights,1));net[0].in_features=len(weights);return original,net
def export(directory,bundle,cols):
    ab.export(directory,bundle,cols);p=json.loads((directory/'params.json').read_text());p.update(input='Selected frozen proxy/distribution/order-statistic INT8 descriptors; no runtime normalization',frontend='Dimension sweep CPU reference; no hardware claim');dump(directory/'params.json',p)
def export_path(tag,seed):return (ENR if tag in REFERENCES else LOG)/'training'/(tag+'_seed'+str(seed))/'epoch60/export'
def size_guard():
    size=sum(p.stat().st_size for p in LOG.rglob('*') if p.is_file());assert size<=PLAN['budget']['max_output_bytes'];return size
def costs(tag):
    c=set(take(tag));geometry=bool(c&{16,17,18});dist=bool(c&{19,20,21,22});quantile=bool(c&set(range(24,36)))
    # Existing C computes all base16 statistics even for reduced selected inputs.
    return dict(tag=tag,dim=len(take(tag)),network_macs=64*len(take(tag))+2112,weight_bytes=64*len(take(tag))+2112,bias_bytes=392,
        extra_products_per_point=3*int(geometry)+2*int(dist),channel_sorts=4*int(quantile),quantile_buffer_bytes_at_N511=1022*int(quantile),
        ratio_quantizers=3*int(geometry)+4*int(dist)+int(23 in c)+len(c&set(range(24,36))),base_frontend='All base16 sums/extrema/range/density remain in C; no base scan savings claimed')
def native_source(tag=None):
    c=set(range(36)) if tag is None else set(take(tag));g=bool(c&{16,17,18});d=bool(c&{19,20,21,22})
    s=ex.native_source(g,d);assert s.count('void enrichment(')==1;s=s.replace('void enrichment(','static void enrichment23(')
    flags={'WANT_SUPPORT':23 in c,'WANT_WIDTH':bool(c&set(range(24,28))),'WANT_ASYMMETRY':bool(c&set(range(28,32))),'WANT_MEDIAN':bool(c&set(range(32,36)))}
    return s+'\n#include <stdlib.h>\n'+''.join('#define %s %d\n'%(k,v) for k,v in flags.items())+(HERE/'dimension_features.c').read_text()
class Native:
    def __init__(self,build=False):
        d=LOG/'native';d.mkdir(parents=True,exist_ok=True)
        if build:
            (d/'features.c').write_text(native_source());subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(d/'features.c'),'-o',str(d/'features.so')],check=True,capture_output=True)
        self.lib=ctypes.CDLL(str(d/'features.so'));self.lib.enrichment.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p]
    def __call__(self,p):
        p=np.ascontiguousarray(p,np.int16);assert p.ndim==2 and p.shape[1]==4 and 1<=len(p)<=511;x=np.empty(36,np.int8);self.lib.enrichment(p.ctypes.data,len(p),x.ctypes.data);return x
class Pools:
    def __init__(self):
        p=ex.Pools();self.original=p;self.n=p.n;self.y=p.y;self.ys=p.ys;self.cal=p.cal;self.class_weights=p.class_weights
        names=['clean','uniform_quarter_0','central_half','synthetic','natural']
        extra=[np.load(LOG/'data/train'/(name+'.npy')) for name in names]
        self.arrays=[np.concatenate([a,z],axis=1) for a,z in zip(p.arrays,extra)];self.x=np.concatenate(self.arrays)
        means=[];seconds=[]
        for z in extra[:3]:means.append(z.mean(0,dtype=np.float64));seconds.append((z.astype(float)**2).mean(0))
        for z,groups in zip(extra[3:],p.original.indices):
            mu=np.zeros(13);sec=np.zeros(13)
            for k,ids in enumerate(groups):
                if p.original.p[k]:mu+=p.original.p[k]*z[ids].mean(0,dtype=np.float64);sec+=p.original.p[k]*(z[ids].astype(float)**2).mean(0)
            means.append(mu);seconds.append(sec)
        w=np.array([.5,.125,.125,.125,.125]);mu=w@np.array(means);std=np.sqrt(np.maximum(w@np.array(seconds)-mu*mu,0));std[std<1e-6]=1
        self.mu=np.r_[p.mu,mu];self.std=np.r_[p.std,std]
    def schedule(self,*args):return self.original.schedule(*args)
def validation(condition):
    x,y,meta=ex.validation(condition);return np.concatenate([x,np.load(LOG/'data/val'/(condition+'.npy'))],axis=1),y,meta
