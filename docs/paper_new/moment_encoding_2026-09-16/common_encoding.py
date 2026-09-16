"""Shared training machinery and exact distribution-encoding transformations."""
import importlib.util
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('encoding_mechanism_common',ROOT/'docs/paper_new/mechanism_convergence_2026-09-16/common.py')
base=importlib.util.module_from_spec(spec);sys.modules[spec.name]=base;spec.loader.exec_module(base)
# Reused mechanism helpers import "common"; alias the initialized module so
# torch's process-wide interop-thread setting is not executed a second time.
sys.modules['common']=base
np=base.np;json=base.json;ctypes=base.ctypes;subprocess=base.subprocess;hashlib=base.hashlib
sha=base.sha;dump=base.dump;qc=base.qc;pc=base.pc;buffers_hash=base.buffers_hash
LOG=ROOT/'logs/moment_encoding_20260916';MECH=base.LOG;PREV=base.PREV
PLAN=json.loads((HERE/'plan.json').read_text());MODES=PLAN['encoding']['representations'];SHAPES=PLAN['encoding']['shape_slots']

def root_values(raw):
    a=np.abs(np.asarray(raw,dtype=np.int64));assert a.max()<2**48
    r=np.floor(np.sqrt(a.astype(float))).astype(np.int64)
    r-=r*r>a;r+=((r+1)*(r+1)<=a);r+=(a-r*r)>r
    return np.where(np.asarray(raw)<0,-r,r)
def transform(raw,mode):
    out=np.array(raw,dtype=np.int64,copy=True)
    if mode=='root':out[...,SHAPES]=root_values(out[...,SHAPES])
    return out
def fractions(mode):
    fr=np.array([8]*21);fr[13]=0
    if mode=='linear_fine':fr[SHAPES]=16
    return fr
def quantize(raw,mode,exponent):
    return np.clip(np.rint(np.asarray(raw,dtype=float)/np.exp2(np.asarray(exponent)+fractions(mode))),-127,127).astype(np.int8)
class Native:
    def __init__(self,build=False):
        d=LOG/'native';d.mkdir(parents=True,exist_ok=True)
        if build:
            (d/'encoding.c').write_text((MECH/'native/mechanism.c').read_text()+(HERE/'encoding.c').read_text())
            subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(d/'encoding.c'),'-o',str(d/'encoding.so')],check=True,capture_output=True,timeout=30)
        self.lib=ctypes.CDLL(str(d/'encoding.so'))
        self.lib.encode_raw_rows.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p]
        self.lib.encoding_features.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p]
        p=LOG/'data/scales.json';self.shifts=np.ascontiguousarray(json.loads(p.read_text())['shifts'],np.int32) if p.exists() else np.zeros((2,21),np.int32)
    def raw_root(self,raw):
        a=np.ascontiguousarray(raw,np.int64).reshape(-1,21);out=np.empty_like(a)
        self.lib.encode_raw_rows(a.ctypes.data,len(a),out.ctypes.data);return out
    def __call__(self,p,mb=24,vb=24):
        p=np.ascontiguousarray(p,np.int16);assert p.shape[1]==4 and 1<=len(p)<=511
        out=np.empty((2,21),np.int8);self.lib.encoding_features(p.ctypes.data,len(p),mb,vb,self.shifts.ctypes.data,out.ctypes.data);return out
