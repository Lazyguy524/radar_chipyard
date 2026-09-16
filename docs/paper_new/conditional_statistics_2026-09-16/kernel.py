"""Shared first/second moments with explicit finite precision and C mirror."""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='2'
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOG=ROOT/'logs/conditional_statistics_20260916'
PLAN=json.loads((HERE/'plan.json').read_text())
MODES=['proxy_scaled','moment24','moment16','uncentered16']
FRACS=np.array([8]*21);FRACS[[3,4,10,11,12]]=16;FRACS[13]=0
PROXY_FRACS=np.array([8]*21);PROXY_FRACS[13]=0
sys.path.insert(0,str(ROOT/'docs/paper_new/feature_approximation_pilot_2026-09-16'))
import pilot_common as pc

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def rnd(a,bits):
    a=int(a)
    if bits<=0:return a<<(-bits)
    q,r=divmod(abs(a),1<<bits);half=1<<(bits-1)
    q+=int(r>half or (r==half and q%2));return -q if a<0 else q
def reciprocal(n,r):
    q,rem=divmod(1<<r,n);return q+int(2*rem>n or (2*rem==n and q%2))

def python_moments(q,r,centered=True):
    p=np.asarray(q,dtype=np.int64);n=len(p);origin=p[0] if centered else np.zeros(4,np.int64)
    d=p-origin;inv=reciprocal(n,r);s=d.sum(0)
    mu=np.array([rnd(int(v)*inv,r-4) for v in s],np.int64)
    means=np.clip(origin+np.array([rnd(v,4) for v in mu]),-32768,32767)
    xx=rnd(int((d[:,0]**2).sum())*inv,r)-rnd(int(mu[0])**2,8)
    yy=rnd(int((d[:,1]**2).sum())*inv,r)-rnd(int(mu[1])**2,8)
    xy=rnd(int((d[:,0]*d[:,1]).sum())*inv,r)-rnd(int(mu[0])*int(mu[1]),8)
    return means,np.array([max(0,xx),max(0,yy),xy],np.int64),int(xx<0)+int(yy<0)

class Kernel:
    def __init__(self,directory,build=True):
        directory.mkdir(parents=True,exist_ok=True)
        if build:
            text=(ROOT/'tests/radar-feature21-qmlp-cpu-fullchain-profile.c').read_text()
            body=text[text.index('static int32_t round_shift_even_i64'):text.index('static int8_t requant_relu_clamp')]
            old='''static void feature21_density_exact_lut(uint32_t sample, int8_t out[CPU_FULLCHAIN_FEATURE_DIM])
{
  uint32_t start = radar_feature21_golden_offsets[sample];
  uint32_t raw_count = radar_feature21_golden_offsets[sample + 1u] - start;'''
            new='''static void feature21_density_exact_lut(const radar_feature21_golden_point_t *points, uint32_t raw_count, int8_t out[CPU_FULLCHAIN_FEATURE_DIM])
{'''
            assert body.count(old)==1
            body=body.replace(old,new).replace('&radar_feature21_golden_points[start + i]','&points[i]')
            start=body.index('static void feature21_density_exact_lut(')
            raw=body[start:].replace('feature21_density_exact_lut','proxy_raw').replace('int8_t out[CPU_FULLCHAIN_FEATURE_DIM]','int32_t out[CPU_FULLCHAIN_FEATURE_DIM]')
            raw=raw.replace('quant_raw_count(count)','(int32_t)(count << 8)').replace('quant_q8p8(','(')
            tables='\n'.join('static const uint32_t recip'+str(r)+'[512] = {0,'+','.join(str(reciprocal(n,r)) for n in range(1,512))+'};' for r in [16,24])
            prefix='#include <stdint.h>\n#define CPU_FULLCHAIN_FEATURE_DIM 21\n#define CPU_FULLCHAIN_MAX_POINTS 511u\ntypedef struct {int16_t x,y,doppler,rcs;} radar_feature21_golden_point_t;\n'
            source=prefix+body+raw+tables+'\n'+(HERE/'moments.c').read_text()
            (directory/'kernel.c').write_text(source)
            subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(directory/'kernel.c'),'-o',str(directory/'kernel.so')],check=True,timeout=30,capture_output=True)
        self.lib=ctypes.CDLL(str(directory/'kernel.so'))
        self.lib.extract_all.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
    def __call__(self,points):
        q=np.ascontiguousarray(points,dtype=np.int16);assert q.shape[1]==4 and 0<len(q)<=511
        raw=np.empty((4,21),np.int64);legacy=np.empty(21,np.int8);neg=np.zeros(3,np.int32)
        self.lib.extract_all(q.ctypes.data,len(q),raw.ctypes.data,legacy.ctypes.data,neg.ctypes.data)
        return raw,legacy,neg

def fit_scale(raw,mode):
    fr=PROXY_FRACS if mode=='proxy_scaled' else FRACS
    # Quantiles in integer units; only the training split is admitted by callers.
    threshold=np.percentile(np.abs(raw.astype(np.float64)),99.99,axis=0)/np.exp2(fr)
    exponent=np.ceil(np.log2(np.maximum(threshold/127,2.0**-16))).astype(int)
    exponent[13]=0
    return exponent

def quantize(raw,exponent,mode):
    fr=PROXY_FRACS if mode=='proxy_scaled' else FRACS
    shift=np.asarray(exponent)+fr
    return np.clip(np.rint(np.asarray(raw,dtype=np.float64)/np.exp2(shift)),-127,127).astype(np.int8)
