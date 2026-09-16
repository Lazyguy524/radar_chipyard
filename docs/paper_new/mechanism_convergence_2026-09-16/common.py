"""Isolated factorial experiment paths, frozen scales and arithmetic imports."""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='2'
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
LOG=ROOT/'logs/mechanism_convergence_20260916';PREV=ROOT/'logs/conditional_statistics_20260916'
PLAN=json.loads((HERE/'plan.json').read_text());MODES=PLAN['factorial']['representations']
MEANS=PLAN['factorial']['mean_slots'];SHAPES=PLAN['factorial']['shape_slots']
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
qc=module('mechanism_qat_common',ROOT/'docs/paper_new/qmlp_int8_convergence_2026-09-16/common.py')
pc=module('mechanism_pilot_common',ROOT/'docs/paper_new/feature_approximation_pilot_2026-09-16/pilot_common.py')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def mixed(proxy,moment):
    result=np.repeat(np.asarray(proxy)[None,...],4,axis=0)
    for flag in range(4):
        if flag&1:result[flag][...,MEANS]=np.asarray(moment)[...,MEANS]
        if flag&2:result[flag][...,SHAPES]=np.asarray(moment)[...,SHAPES]
    return result
def scales():
    e=json.loads((PREV/'data/output_scale_exponents.json').read_text())
    # Explicit per-slot arrays avoid NumPy advanced-axis ambiguity for batches.
    exps=[];fracs=[]
    for flag in range(4):
        ex=np.array(e['proxy_scaled']);fr=np.array([8]*21);fr[13]=0
        if flag&1:ex[MEANS]=np.array(e['moment24'])[MEANS]
        if flag&2:ex[SHAPES]=np.array(e['moment24'])[SHAPES];fr[SHAPES]=16
        exps.append(ex);fracs.append(fr)
    return np.asarray(exps),np.asarray(fracs)
class Native:
    def __init__(self,build=False):
        d=LOG/'native';d.mkdir(parents=True,exist_ok=True)
        if build:
            source=(PREV/'native/kernel.c').read_text()+(HERE/'mechanism.c').read_text()
            (d/'mechanism.c').write_text(source)
            subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(d/'mechanism.c'),'-o',str(d/'mechanism.so')],check=True,capture_output=True,timeout=30)
        self.lib=ctypes.CDLL(str(d/'mechanism.so'))
        self.lib.family.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
        ex,fr=scales();self.shift=np.ascontiguousarray(ex+fr,np.int32)
    def __call__(self,p,mb=24,vb=24):
        q=np.ascontiguousarray(p,np.int16);assert q.ndim==2 and q.shape[1]==4 and 1<=len(q)<=511
        raw=np.empty((4,21),np.int64);z=np.empty((4,21),np.int8)
        self.lib.family(q.ctypes.data,len(q),mb,vb,self.shift.ctypes.data,raw.ctypes.data,z.ctypes.data)
        return raw,z
def predict_tensor(net,x,integer=False):
    a=[];net.eval()
    with qc.torch.inference_mode():
        for i in range(0,len(x),4096):
            a.append((net(x[i:i+4096],integer_logits=True) if integer else net(x[i:i+4096])).numpy())
    return np.concatenate(a)
def buffers_hash(net):return hashlib.sha256(b''.join(v.detach().numpy().tobytes() for _,v in net.named_buffers())).hexdigest()
