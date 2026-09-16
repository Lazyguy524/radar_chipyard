"""Isolated frozen-scale training and existing QMLP arithmetic contract."""
import os
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='2'
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOG=ROOT/'logs/qmlp_int8_convergence_20260916'
PILOT=ROOT/'logs/feature_approximation_pilot_20260916'
PLAN=json.loads((HERE/'plan.json').read_text())
sys.path.insert(0,str(ROOT/'docs/paper_new/feature_approximation_pilot_2026-09-16'))
import pilot_common as pc
torch.set_num_threads(2)
torch.set_num_interop_threads(1)
torch.use_deterministic_algorithms(True)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def metric(y,p):return pc.metrics(pc.cm(y,p))
def model():return nn.Sequential(nn.Linear(21,64),nn.ReLU(),nn.Linear(64,32),nn.ReLU(),nn.Linear(32,2))
def fold(net,mean,std):
    import copy
    folded=copy.deepcopy(net).double()
    with torch.no_grad():
        w=folded[0].weight.clone()/torch.as_tensor(std,dtype=torch.float64)
        folded[0].weight.copy_(w)
        folded[0].bias.sub_(w@torch.as_tensor(mean,dtype=torch.float64))
    return folded

def ste_round(x):
    # Exact rounded forward values; derivative only through the unrounded term.
    return torch.round(x).detach()+(x-x.detach())

class FrozenQAT(nn.Module):
    def __init__(self,folded,calibration):
        super().__init__()
        self.layers=nn.ModuleList([folded[i] for i in [0,2,4]])
        sw=torch.tensor([max(float(l.weight.detach().abs().max())/127,1e-10) for l in self.layers],dtype=torch.float64)
        self.register_buffer('weight_scales',sw)
        self.register_buffer('input_scales',torch.ones(3,dtype=torch.float64))
        self.register_buffer('multipliers',torch.zeros(2,dtype=torch.int64))
        with torch.no_grad():
            cur=calibration.double()
            for i,l in enumerate(self.layers[:2]):
                qi=torch.round(l.weight/sw[i]).clamp(-127,127)
                qb=torch.round(l.bias/(self.input_scales[i]*sw[i]))
                acc=F.linear(cur,qi,qb)
                threshold=np.percentile((acc.clamp(min=0)*self.input_scales[i]*sw[i]).numpy(),PLAN['training']['activation_percentile'])
                sa=max(float(threshold)/127,1e-10)
                self.input_scales[i+1]=sa
                # Positive Scala math.round semantics, explicitly shared by export.
                m=int(np.floor(float(self.input_scales[i]*sw[i]/sa)*65536+0.5))
                assert 0<m<2**31
                self.multipliers[i]=m
                cur=torch.round(acc*m/65536).clamp(0,127)

    def forward(self,x,trace=False):
        cur=x.double();hidden=[]
        for i,l in enumerate(self.layers):
            qi=ste_round((l.weight/self.weight_scales[i]).clamp(-127,127))
            qb=ste_round(l.bias/(self.input_scales[i]*self.weight_scales[i]))
            acc=F.linear(cur,qi,qb)
            if i<2:
                cur=ste_round(acc*int(self.multipliers[i])/65536).clamp(0,127)
                hidden.append(cur)
            else:
                if trace:return hidden+[acc]
                return acc*(self.input_scales[2]*self.weight_scales[2])

    def export(self):
        layers=[]
        for i,l in enumerate(self.layers):
            w=np.clip(np.rint(l.weight.detach().numpy()/float(self.weight_scales[i])),-127,127).astype(np.int8)
            b64=np.rint(l.bias.detach().numpy()/float(self.input_scales[i]*self.weight_scales[i])).astype(np.int64)
            assert np.max(np.abs(b64))<2**31
            bound=np.abs(b64)+127*np.abs(w.astype(np.int64)).sum(1)
            assert bound.max()<2**31,'Accumulator overflow possible'
            if i<2:assert int(bound.max())*int(self.multipliers[i])<2**53,'Float64 exact-forward bound exceeded'
            layers.append(dict(weight=w,bias=b64.astype(np.int32),input_scale=float(self.input_scales[i]),weight_scale=float(self.weight_scales[i]),
                output_scale=float(self.input_scales[i+1]) if i<2 else float(self.input_scales[i]*self.weight_scales[i]),
                accumulator_abs_bound=int(bound.max())))
        return dict(layers=layers,multipliers=self.multipliers.tolist(),shift=16)

def round_shift(a,m):
    product=a.astype(np.int64)*int(m);absolute=np.abs(product)
    q=absolute>>16;r=absolute&65535
    q=q+((r>32768)|((r==32768)&((q&1)!=0)))
    return np.where(product<0,-q,q)

def integer_trace(x,bundle):
    cur=np.asarray(x,dtype=np.int64);values=[]
    for i,l in enumerate(bundle['layers']):
        acc=cur@l['weight'].astype(np.int64).T+l['bias'].astype(np.int64)
        assert np.abs(acc).max()<2**31
        cur=np.clip(round_shift(acc,bundle['multipliers'][i]),0,127) if i<2 else acc
        values.append(cur.copy())
    return values

def write_export(directory,bundle):
    directory.mkdir(parents=True,exist_ok=False)
    header=['#ifndef RADAR_FROZEN_QMLP_PARAMS_H','#define RADAR_FROZEN_QMLP_PARAMS_H','#include <stdint.h>',
        '#define RADAR_MLP_INPUT_DIM 21','#define RADAR_QMLP_REQUANT_SHIFT 16',
        '#define RADAR_QMLP_L1_MULTIPLIER '+str(bundle['multipliers'][0]),'#define RADAR_QMLP_L2_MULTIPLIER '+str(bundle['multipliers'][1])]
    scala=['// Isolated candidate: not connected to the existing release loader.','object Radar_frozen_qmlpParams {']
    arrays={};meta=[]
    for i,l in enumerate(bundle['layers'],1):
        w=l['weight'];b=l['bias'];r,c=w.shape
        header.extend([f'#define RADAR_MLP_L{i}_IN {c}',f'#define RADAR_MLP_L{i}_OUT {r}',
            f'static const int8_t radar_mlp_l{i}_weight[{r*c}] = {{'+','.join(map(str,w.reshape(-1)))+'};',
            f'static const int32_t radar_mlp_l{i}_bias[{r}] = {{'+','.join(map(str,b))+'};'])
        scala.extend([f'  val l{i}In = {c}',f'  val l{i}Out = {r}',f'  val l{i}Weight = Seq('+','.join(map(str,w.reshape(-1)))+')',
            f'  val l{i}Bias = Seq('+','.join(map(str,b))+')'])
        for key,suffix in [('input_scale','InputScale'),('weight_scale','WeightScale'),('output_scale','OutputScale')]:scala.append(f'  val l{i}{suffix} = {l[key]:.17g}')
        arrays[f'w{i}']=w;arrays[f'b{i}']=b
        meta.append({k:v for k,v in l.items() if k not in ['weight','bias']})
    header.append('#endif');scala.append('}')
    (directory/'params.h').write_text('\n'.join(header)+'\n')
    (directory/'Radar_frozen_qmlpParams.scala').write_text('\n'.join(scala)+'\n')
    np.savez(directory/'integer_params.npz',**arrays)
    dump(directory/'params.json',dict(layers=meta,multipliers=bundle['multipliers'],shift=16,input='Raw existing Feature21 INT8, no normalization at inference',
        arithmetic='row-major INT8 weight, INT32 bias/accumulator; ties-to-even shift 16; ReLU clamp 0..127; INT32 logits',
        status='ISOLATED_CANDIDATE_NOT_INSTALLED_IN_RTL_OR_BITSTREAM'))

def load_export(directory):
    b=json.loads((directory/'params.json').read_text());a=np.load(directory/'integer_params.npz')
    for i,l in enumerate(b['layers'],1):l.update(weight=a[f'w{i}'],bias=a[f'b{i}'])
    return b

class CTrace:
    """Existing deployed C arithmetic body, with candidate header and trace outputs."""
    def __init__(self,directory):
        source=ROOT/'tests/radar-feature21-qmlp-cpu-fullchain-profile.c';text=source.read_text()
        rounding=text[text.index('static int32_t round_shift_even_i64'):text.index('static uint64_t round_div_even_u64')]
        infer=text[text.index('static int8_t requant_relu_clamp'):text.index('int main(void)')]
        old='static void qmlp_infer(const int8_t input[RADAR_MLP_INPUT_DIM], int32_t logits[2])'
        assert infer.count(old)==1
        infer=infer.replace(old,'static void qmlp_infer(const int8_t *input, int32_t *logits, int8_t *l1_out, int8_t *l2_out)')
        infer=infer.replace('  int8_t l1_out[RADAR_MLP_L1_OUT];\n','').replace('  int8_t l2_out[RADAR_MLP_L2_OUT];\n','')
        wrapper='''
void trace_batch(const int8_t *x, uint32_t n, int8_t *h1, int8_t *h2, int32_t *y) {
  for(uint32_t i=0;i<n;i++) qmlp_infer(x+i*21,y+i*2,h1+i*64,h2+i*32);
}
void test_round(const int64_t *x,uint32_t n,int32_t *y) {
  for(uint32_t i=0;i<n;i++) y[i]=round_shift_even_i64(x[i],16);
}
'''
        (directory/'inference_trace.c').write_text('#include "params.h"\n'+rounding+infer+wrapper)
        subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(directory/'inference_trace.c'),'-o',str(directory/'inference_trace.so')],check=True,timeout=30,capture_output=True)
        self.lib=ctypes.CDLL(str(directory/'inference_trace.so'))
        self.lib.trace_batch.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
        self.lib.test_round.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p]
    def __call__(self,x):
        x=np.ascontiguousarray(x,dtype=np.int8);n=len(x)
        a=np.empty((n,64),np.int8);b=np.empty((n,32),np.int8);y=np.empty((n,2),np.int32)
        self.lib.trace_batch(x.ctypes.data,n,a.ctypes.data,b.ctypes.data,y.ctypes.data)
        return [a,b,y]
