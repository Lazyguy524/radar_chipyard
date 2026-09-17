"""Read-only train-feature identity check; no fitting or held-out scoring."""
import os
for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[name]='2'
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    target=HERE/'feature_identity_check.json';assert not target.exists()
    paths=[ROOT/'logs/mechanism_convergence_20260916/data/train'/(mode+'.npy') for mode in ('proxy','mean')]
    paths += [ROOT/'logs/software_convergence_20260917/data/train'/('natural_'+mode+'.npy') for mode in ('proxy','mean')]
    rows=[]
    for p in paths:
        x=np.load(p,mmap_mode='r');assert x.shape[1]==21 and x.dtype==np.int8
        rows.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p),rows=len(x),columns=[6,10],unequal_rows=int(np.count_nonzero(x[:,6]!=x[:,10]))))
    source=ROOT/'docs/paper_new/mechanism_convergence_2026-09-16/single_variant.c'
    scales=ROOT/'logs/mechanism_convergence_20260916/data/scales.json';cfg=json.loads(scales.read_text())
    shifts=[[a+b for a,b in zip(e,f)] for e,f in zip(cfg['exponents'],cfg['fractional_bits'])]
    assert all(shifts[i][6]==shifts[i][10]==7 for i in (0,1))
    assert all(r['unequal_rows']==0 for r in rows)
    result=dict(status='PASS',scope='Existing proxy/mean train features only; no deletion retraining, validation scoring or optimum-dimension claim',
        checks=rows,code_explanation='For FEATURE_FLAGS 0/1, output[6]=span_y and output[10]=cov=span_y; both use shift7 and identical saturation.',
        sources={str(p.relative_to(ROOT)):sha(p) for p in (source,scales,HERE/'feature_identity_check.py')},
        caveat='Equal inputs do not guarantee naive INT8 weight merging preserves quantized inference; deletion needs matched retraining/export checks. Other representations/scales require separate verification.')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
