"""Isolated software convergence paths and shared frozen arithmetic."""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='2'
import importlib.util
import sys
from pathlib import Path
import csv
import json
import hashlib
import time
import ctypes
import subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
LOG=ROOT/'logs/software_convergence_20260917'
spec=importlib.util.spec_from_file_location('sw_mechanism',ROOT/'docs/paper_new/mechanism_convergence_2026-09-16/common.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base);sys.modules['common']=base
np=base.np;qc=base.qc;pc=base.pc;torch=qc.torch;F=qc.F
MECH=base.LOG;PROT=ROOT/'logs/conditional_protection_20260916'
PLAN=json.loads((HERE/'plan.json').read_text());MODES=['proxy','mean'];SEEDS=PLAN['training']['seeds']
views=base.module('sw_views',base.HERE/'prepare_views.py')
ev=base.module('sw_eval_helpers',base.HERE/'evaluate_stage.py')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def readcsv(p):
    with Path(p).open() as f:return list(csv.DictReader(f))
def writecsv(p,data):
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def hbin(n):return 0 if n==0 else (1 if n<6 else 2)
def stratum(label,count,history):return int(label)*6+(int(count)-1)*3+hbin(history)
def quota(n,p):
    raw=np.asarray(p,dtype=float)*n;q=np.floor(raw).astype(np.int64)
    # Stable index order breaks identical fractional remainders.
    q[np.argsort(-(raw-q),kind='stable')[:n-int(q.sum())]]+=1
    assert q.sum()==n;return q
def native_model(path):
    c=qc.CTrace.__new__(qc.CTrace);c.lib=ctypes.CDLL(str(path/'inference_trace.so'))
    c.lib.trace_batch.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p];return c
def allgroups(meta,condition):
    out=ev.groups(meta,condition)
    raw=np.array([int(r['raw_points']) for r in meta]);hist=np.array([int(r.get('prior_history',r.get('retained_history_used',int(r.get('retained_history','1'))-1))) for r in meta])
    dist=np.array([float(r.get('current_centroid_range',r.get('current_range',r.get('centroid_range',0)))) for r in meta])
    out += [('history','none',hist==0),('history','one_to_five',(hist>0)&(hist<6)),('history','six',hist==6),
        ('current_points','1',raw==1),('current_points','2',raw==2),('current_points','ge3',raw>=3),
        ('current_range','le20',dist<=20),('current_range','20to40',(dist>20)&(dist<=40)),('current_range','gt40',dist>40)]
    return out
def old_prediction(stage,seed,condition):return np.load(MECH/(stage+'_evaluation')/('proxy_seed%d_%s_prediction.npy'%(seed,condition)))
def validation(condition,mode='proxy',bits=24):
    if condition.startswith('sparse_'):
        d=MECH/'raw'/condition;y=np.load(d/'labels.npy');meta=readcsv(d/'metadata.csv')
        x=np.load(d/(mode+'.npy')) if bits==24 else np.load(LOG/'data/precision'/str(bits)/(condition+'.npy'))
    else:
        y=np.load(MECH/'data/val/labels.npy');meta=readcsv(LOG/'data/val/kept_metadata.csv')
        x=np.load(MECH/('data/val' if condition=='clean' else 'raw/val')/mode/ (condition+'.npy')) if condition!='clean' else np.load(MECH/'data/val'/(mode+'.npy'))
        if bits!=24:x=np.load(LOG/'data/precision'/str(bits)/(condition+'.npy'))
    return x,y,meta
def size_guard():
    n=sum(p.stat().st_size for p in LOG.rglob('*') if p.is_file())
    assert n<=PLAN['budgets']['max_output_bytes'],('Output budget',n)
    return n
