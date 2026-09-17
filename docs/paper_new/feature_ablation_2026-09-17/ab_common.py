"""Isolated variable-input-dimension controls over frozen proxy features."""
import importlib.util
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('sw_common',ROOT/'docs/paper_new/software_convergence_2026-09-17/sw_common.py')
sw=importlib.util.module_from_spec(spec);sys.modules['sw_common']=sw;spec.loader.exec_module(sw)
np=sw.np;torch=sw.torch;qc=sw.qc;pc=sw.pc;F=sw.F;base=sw.base
json=sw.json;hashlib=sw.hashlib;time=sw.time;ctypes=sw.ctypes;subprocess=sw.subprocess
sha=sw.sha;dump=sw.dump;readcsv=sw.readcsv;writecsv=sw.writecsv
OLD=sw.LOG;MECH=sw.MECH;LOG=ROOT/'logs/feature_ablation_20260917'
PLAN=json.loads((HERE/'plan.json').read_text());SEEDS=PLAN['training']['seeds'];VARIANTS=PLAN['variants']
pools=base.module('ab_previous_pools',sw.HERE/'pools.py')
previous=base.module('ab_previous_evaluation',sw.HERE/'evaluate.py')
import copy

def keep(tag):return [i for i in range(21) if i not in VARIANTS[tag]['remove']]
def old_export(seed):return OLD/'training'/('proxy_natural_seed'+str(seed))/'epoch60/export'
def model(tag,seed):
    torch.manual_seed(seed);original=qc.model();net=copy.deepcopy(original);cols=keep(tag)
    w=original[0].weight.detach().clone()
    if 10 not in cols and 6 in cols:w[:,6]+=w[:,10]
    net[0].weight=torch.nn.Parameter(w[:,cols].clone());net[0].in_features=len(cols)
    return original,net
def merge_bundle(bundle):
    b=copy.deepcopy(bundle);w=b['layers'][0]['weight'].astype(np.int16);w[:,6]+=w[:,10]
    b['layers'][0]['weight']=w[:,keep('dedup20')]
    b['layers'][0]['accumulator_abs_bound']=int((np.abs(b['layers'][0]['bias'].astype(np.int64))+127*np.abs(b['layers'][0]['weight'].astype(np.int64)).sum(1)).max())
    return b
def bounds(bundle):
    for i,l in enumerate(bundle['layers']):
        a=np.abs(l['bias'].astype(np.int64))+127*np.abs(l['weight'].astype(np.int64)).sum(1)
        assert a.max()<2**31
        if i<2:assert int(a.max())*int(bundle['multipliers'][i])<2**53
def export(directory,bundle,columns,kind='trained_int8'):
    bounds(bundle);directory.mkdir(parents=True,exist_ok=False);dim=len(columns)
    header=['#ifndef AB_PARAMS_H','#define AB_PARAMS_H','#include <stdint.h>',f'#define RADAR_MLP_INPUT_DIM {dim}','#define RADAR_QMLP_REQUANT_SHIFT 16',
        '#define RADAR_QMLP_L1_MULTIPLIER '+str(bundle['multipliers'][0]),'#define RADAR_QMLP_L2_MULTIPLIER '+str(bundle['multipliers'][1])]
    arrays={};meta=[]
    for i,l in enumerate(bundle['layers'],1):
        w=l['weight'];b=l['bias'];rows,cols=w.shape;storage='int16_t' if w.dtype==np.int16 else 'int8_t'
        header += [f'#define RADAR_MLP_L{i}_IN {cols}',f'#define RADAR_MLP_L{i}_OUT {rows}',
            f'static const {storage} radar_mlp_l{i}_weight[{rows*cols}] = {{'+','.join(map(str,w.ravel()))+'};',
            f'static const int32_t radar_mlp_l{i}_bias[{rows}] = {{'+','.join(map(str,b))+'};']
        arrays['w'+str(i)]=w;arrays['b'+str(i)]=b;meta.append({k:v for k,v in l.items() if k not in ('weight','bias')})
    header.append('#endif');(directory/'params.h').write_text('\n'.join(header)+'\n');np.savez(directory/'integer_params.npz',**arrays)
    dump(directory/'params.json',dict(layers=meta,multipliers=bundle['multipliers'],shift=16,columns=columns,input_dim=dim,kind=kind,
        input='Selected frozen proxy INT8 slots; no runtime normalization',frontend='proxy only; original shifts; no new board artifact'))
class Trace:
    def __init__(self,directory,build=True):
        directory=Path(directory);self.dim=json.loads((directory/'params.json').read_text())['input_dim']
        if build:
            text=(ROOT/'tests/radar-feature21-qmlp-cpu-fullchain-profile.c').read_text()
            rounding=text[text.index('static int32_t round_shift_even_i64'):text.index('static uint64_t round_div_even_u64')]
            infer=text[text.index('static int8_t requant_relu_clamp'):text.index('int main(void)')]
            old='static void qmlp_infer(const int8_t input[RADAR_MLP_INPUT_DIM], int32_t logits[2])';assert infer.count(old)==1
            infer=infer.replace(old,'static void qmlp_infer(const int8_t *input,int32_t *logits,int8_t *l1_out,int8_t *l2_out)').replace('  int8_t l1_out[RADAR_MLP_L1_OUT];\n','').replace('  int8_t l2_out[RADAR_MLP_L2_OUT];\n','')
            wrapper='\nvoid trace_batch(const int8_t*x,uint32_t n,int8_t*a,int8_t*b,int32_t*y){for(uint32_t i=0;i<n;i++)qmlp_infer(x+i*RADAR_MLP_INPUT_DIM,y+i*2,a+i*64,b+i*32);}\nvoid test_round(const int64_t*x,uint32_t n,int32_t*y){for(uint32_t i=0;i<n;i++)y[i]=round_shift_even_i64(x[i],16);}\n'
            (directory/'inference_trace.c').write_text('#include "params.h"\n'+rounding+infer+wrapper)
            subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(directory/'inference_trace.c'),'-o',str(directory/'inference_trace.so')],check=True,capture_output=True,timeout=30)
        self.lib=ctypes.CDLL(str(directory/'inference_trace.so'));self.lib.trace_batch.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
        self.lib.test_round.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p]
    def __call__(self,x):
        x=np.ascontiguousarray(x,np.int8);assert x.ndim==2 and x.shape[1]==self.dim;n=len(x)
        a=np.empty((n,64),np.int8);b=np.empty((n,32),np.int8);y=np.empty((n,2),np.int32)
        self.lib.trace_batch(x.ctypes.data,n,a.ctypes.data,b.ctypes.data,y.ctypes.data);return [a,b,y]
def size_guard():
    n=sum(p.stat().st_size for p in LOG.rglob('*') if p.is_file());assert n<=PLAN['budget']['max_output_bytes'];return n

def frontend_source(tag):
    cols=keep(tag);ex,fr=base.scales()
    config='\n#define RADAR_MLP_INPUT_DIM %d\n#define HAS_RCS %d\n#define ACTIVE_CHANNELS %d\n#define HAS_SHAPE_PROXY %d\n#define HAS_DUPLICATE %d\n'%(len(cols),tag!='no_rcs18',3 if tag=='no_rcs18' else 4,tag!='less_shape16',10 in cols)
    config+='static const int selected_columns[]={'+','.join(map(str,cols))+'};\n'
    config+='static const int selected_shifts[]={'+','.join(map(str,(ex+fr)[0,cols]))+'};\n'
    return (base.PREV/'native/kernel.c').read_text()+config+(HERE/'proxy_subset.c').read_text()
