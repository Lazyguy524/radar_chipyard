"""Run an already-verified isolated C candidate on raw Feature21 INT8 rows."""
import argparse
import ctypes
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
LOG=ROOT/'logs/qmlp_int8_convergence_20260916'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--seed',type=int,choices=[7,17],required=True)
    p.add_argument('--input',type=Path,required=True,help='N x 21 .npy, dtype=int8, original Feature21 mirror values')
    p.add_argument('--output',type=Path,required=True,help='New .npy output of N x 2 INT32 logits')
    args=p.parse_args()
    assert json.loads((LOG/'verification/summary.json').read_text())['status']=='PASS'
    assert args.output.suffix=='.npy' and not args.output.exists(),'Use a new .npy output file'
    x=np.load(args.input,allow_pickle=False)
    assert x.dtype==np.int8 and x.ndim==2 and x.shape[1]==21 and len(x)>0
    assert int(x.min())>=-127,'Input contract is symmetric INT8 [-127,127]'
    directory=LOG/'training'/f'seed{args.seed}'/'final_export'
    lib=ctypes.CDLL(str(directory/'inference_trace.so'))
    lib.trace_batch.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
    output=np.empty((len(x),2),np.int32)
    for i in range(0,len(x),4096):
        z=np.ascontiguousarray(x[i:i+4096]);n=len(z)
        a=np.empty((n,64),np.int8);b=np.empty((n,32),np.int8);y=np.empty((n,2),np.int32)
        lib.trace_batch(z.ctypes.data,n,a.ctypes.data,b.ctypes.data,y.ctypes.data)
        output[i:i+n]=y
    with args.output.open('xb') as f:np.save(f,output)
    print(json.dumps(dict(status='OFFLINE_C_INFERENCE_COMPLETE',seed=args.seed,samples=len(x),output=str(args.output))))

if __name__=='__main__':main()
