"""Local data reconstruction and frozen-model wrappers for a bounded pilot."""
import os
os.environ['OPENBLAS_NUM_THREADS']='2'
os.environ['OMP_NUM_THREADS']='2'
os.environ['MKL_NUM_THREADS']='2'
from collections import deque
import csv
import ctypes
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import h5py
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOG=ROOT/'logs/feature_approximation_pilot_20260916'
REC=ROOT/'logs/training_server_recovery_20260915/recovered'
PACKED=REC/'logs/multiframe_k_sweep_rcsfix_2026-04-14/packed/k7_rcs21'
MANIFEST=ROOT/'logs/training_server_recovery_20260915/dataset_audit/split_manifest.csv.gz'
RAW=Path('/home/soooarr/radardetect/datasets/RadarScenes/data')
PLAN=json.loads((HERE/'plan.json').read_text())
MODES=PLAN['diagnostic_modes']


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj)
    return obj


class Native:
    def __init__(self,directory):
        directory.mkdir(parents=True,exist_ok=True)
        source=ROOT/'tests/radar-feature21-qmlp-cpu-fullchain-profile.c'
        full=source.read_text()
        body=full[full.index('static int32_t round_shift_even_i64'):full.index('int main(void)')]
        old='''static void feature21_density_exact_lut(uint32_t sample, int8_t out[CPU_FULLCHAIN_FEATURE_DIM])
{
  uint32_t start = radar_feature21_golden_offsets[sample];
  uint32_t raw_count = radar_feature21_golden_offsets[sample + 1u] - start;'''
        new='''static void feature21_density_exact_lut(const radar_feature21_golden_point_t *points, uint32_t raw_count, int8_t out[CPU_FULLCHAIN_FEATURE_DIM])
{'''
        assert body.count(old)==1
        body=body.replace(old,new).replace('&radar_feature21_golden_points[start + i]','&points[i]')
        start=body.index('static void feature21_density_exact_lut(')
        end=body.index('static int8_t requant_relu_clamp(')
        corrected=body[start:end].replace('feature21_density_exact_lut','feature21_mean_corrected').replace('mean_shift_v1p3(','mean_round_div(')
        prefix='''#include <stdint.h>
#include <math.h>
#include "frozen_params.h"
#define CPU_FULLCHAIN_FEATURE_DIM 21
#define CPU_FULLCHAIN_MAX_POINTS 511u
typedef struct { int16_t x,y,doppler,rcs; } radar_feature21_golden_point_t;
'''
        helper='''
static int32_t mean_round_div(int64_t total,uint32_t count) {
  if (!count) return 0;
  uint64_t a=total<0?(uint64_t)(-total):(uint64_t)total;
  int32_t v=(int32_t)round_div_even_u64(a,count);
  return total<0?-v:v;
}
'''
        wrapper='''
void features_pair(const radar_feature21_golden_point_t *points,uint32_t count,int8_t *base,int8_t *mean) {
  feature21_density_exact_lut(points,count,base); feature21_mean_corrected(points,count,mean);
}
void quantize_rows(const float *features,uint32_t n,int8_t *out) {
  for(uint32_t i=0;i<n*21;i++) out[i]=clamp_s8_symmetric((int32_t)lrintf(features[i]/radar_mlp_l1_input_scale));
}
void infer_rows(const int8_t *features,uint32_t n,int32_t *logits) {
  for(uint32_t i=0;i<n;i++) qmlp_infer(features+i*21,logits+i*2);
}
'''
        header=ROOT/'docs/feature_preproc_compare_20260420/feature21/qmlp_params_21.h'
        (directory/'frozen_params.h').write_bytes(header.read_bytes())
        (directory/'pilot_native.c').write_text(prefix+body+helper+corrected+wrapper)
        subprocess.run(['gcc','-shared','-fPIC','-O2','-std=c99',str(directory/'pilot_native.c'),'-lm','-o',str(directory/'pilot_native.so')],check=True,capture_output=True,timeout=30)
        self.lib=ctypes.CDLL(str(directory/'pilot_native.so'))
        self.lib.features_pair.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p]
        for name in ['quantize_rows','infer_rows']:
            getattr(self.lib,name).argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p]
        self.inputs={str(p.relative_to(ROOT)):sha(p) for p in [source,header]}

    def quantize(self,x):
        x=np.ascontiguousarray(x,dtype=np.float32).reshape(-1,21)
        out=np.empty(x.shape,dtype=np.int8)
        self.lib.quantize_rows(x.ctypes.data,len(x),out.ctypes.data)
        return out

    def infer(self,x):
        x=np.ascontiguousarray(x,dtype=np.int8)
        logits=np.empty((len(x),2),dtype=np.int32)
        self.lib.infer_rows(x.ctypes.data,len(x),logits.ctypes.data)
        return logits


def hardware_stat_quant(x):
    q=np.rint(np.asarray(x,dtype=np.float64)*256).astype(np.int64)
    return np.clip(np.rint(q*105/65536.0),-127,127).astype(np.int8)


def reconstruct(split,limit,directory,native):
    assert split in ['train','val'], 'Historical test must not enter this pilot'
    directory.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    featmod=module('pilot_reference_features',REC/'src/radar_cluster_rocc/features.py')
    pymirror=module('pilot_python_mirror',ROOT/'tools/feature21_hw_approx_eval.py')
    byseq={}
    with gzip.open(MANIFEST,'rt') as f:
        for row in csv.DictReader(f):
            if row['split']==split:byseq.setdefault(row['sequence_id'],[]).append(row)
    expected=np.load(PACKED/(split+'_feat.npy'),mmap_mode='r')
    labels=np.load(PACKED/(split+'_label.npy'),mmap_mode='r')
    features={m:[] for m in MODES};metadata=[];maxdiff=np.zeros(21)
    checks=dict(feature_tolerance_mismatches=0,label_mismatches=0,count_mismatches=0,python_native_feature_mismatches=0)
    saturated_input_elements=0;input_elements=0;hdf5_meta={}
    for seq,rows in byseq.items():
        seed=int.from_bytes(hashlib.sha256((str(PLAN['data']['sampling_seed'])+seq+split).encode()).digest()[:8],'little')
        selected=set(np.random.default_rng(seed).choice(len(rows),min(limit,len(rows)),replace=False).tolist()) if limit else set(range(len(rows)))
        base=RAW/seq
        scenes=json.loads((base/'scenes.json').read_text())['scenes']
        h5=base/'radar_data.h5';stat=h5.stat()
        hdf5_meta[seq]=dict(bytes=stat.st_size,mtime_ns=stat.st_mtime_ns)
        with h5py.File(h5,'r') as f:radar=f['radar_data'][:]
        history=deque(maxlen=7);previous=None
        for j,row in enumerate(rows):
            sensor=int(row['sensor_id']);key=(sensor,row['track_id'])
            if key!=previous:history.clear();previous=key
            scene=scenes[row['frame_key']];assert int(scene['sensor_id'])==sensor
            begin,end=scene['radar_indices'];values=radar[begin:end]
            selected_points=values[(values['track_id']==row['track_id'].encode()) & np.isin(values['label_id'],[0,1,2,3,7,8])]
            assert len(selected_points)>0
            current=np.stack([selected_points['x_cc'],selected_points['y_cc'],selected_points['vr_compensated'],selected_points['rcs']],axis=1).astype(np.float32)
            history.append(current)
            if j not in selected:continue
            fused=np.concatenate(list(history),axis=0)
            idx=int(row['packed_row']);n=len(fused);assert 0<n<=511
            y=int(labels[idx]);original_label=int(np.bincount(selected_points['label_id'].astype(int)).argmax())
            checks['label_mismatches']+=int(y!=(0 if original_label in [7,8] else 1))
            checks['count_mismatches']+=int(n!=expected[idx,0])
            exact=featmod.extract_cluster_features(fused,'rcs21')
            diff=np.abs(exact.astype(np.float64)-expected[idx]);maxdiff=np.maximum(maxdiff,diff)
            checks['feature_tolerance_mismatches']+=int(not np.allclose(exact,expected[idx],rtol=1e-5,atol=1e-5))
            saturated_input_elements+=int(np.count_nonzero((fused*256<-32768)|(fused*256>32767)))
            input_elements+=fused.size
            qp=np.ascontiguousarray(np.clip(np.rint(fused*256),-32768,32767),dtype=np.int16)
            qexact=featmod.extract_cluster_features(qp.astype(np.float32)/256,'rcs21')
            basefeat=np.empty(21,dtype=np.int8);meanfeat=np.empty(21,dtype=np.int8)
            native.lib.features_pair(qp.ctypes.data,n,basefeat.ctypes.data,meanfeat.ctypes.data)
            if len(metadata)<64:
                pybase=np.asarray(pymirror.mirror_feature21(qp.tolist(),'density_recip_exact_lut'),dtype=np.int8)
                pymean=np.asarray(pymirror.mirror_feature21(qp.tolist(),'mean_density_recip_exact_lut'),dtype=np.int8)
                checks['python_native_feature_mismatches']+=int(not np.array_equal(pybase,basefeat))+int(not np.array_equal(pymean,meanfeat))
            qhw=hardware_stat_quant(qexact)
            variants={'software_reference':native.quantize(expected[idx])[0],
                'exact_quantized_input':native.quantize(qexact)[0],
                'exact_stats_hardware_quantizer':qhw,
                'deployment':basefeat,'mean_corrected':meanfeat}
            for name,columns in [('eigen_slots_exact',[11,12]),('std_slots_exact',[3,4,15,19]),('angle_slot_exact',[10]),('range_slots_exact',[7,8,9])]:
                v=basefeat.copy();v[columns]=qhw[columns];variants[name]=v
            both=meanfeat.copy();both[[11,12]]=qhw[[11,12]];variants['mean_eigen_corrected']=both
            for name in MODES:features[name].append(variants[name])
            xy=fused[:,:2].astype(np.float64);cov=np.cov(xy.T)
            angle=float(np.degrees(.5*np.arctan2(2*cov[0,1],cov[0,0]-cov[1,1])))
            metadata.append(dict(packed_row=idx,sequence_id=seq,sensor_id=sensor,track_id=row['track_id'],label=y,n=n,
                minor_major_ratio=float(max(0,exact[12])/max(float(exact[11]),1e-12)),
                principal_angle_degrees=angle,centroid_range=float(exact[9]),
                window_seconds=int(row['window_span_frame_key_units'])/1e6,
                input_saturated=int(np.count_nonzero((fused*256<-32768)|(fused*256>32767)))))
        del radar
        print(json.dumps(dict(phase='reconstruct',split=split,sequence=seq,total_samples=len(metadata),elapsed_seconds=round(time.monotonic()-started,2))),flush=True)
    assert not any(checks.values()),checks
    arrays={name:np.asarray(rows,dtype=np.int8) for name,rows in features.items()}
    for name,a in arrays.items():np.save(directory/(name+'.npy'),a)
    y=np.asarray([r['label'] for r in metadata],dtype=np.int64);np.save(directory/'labels.npy',y)
    with gzip.open(directory/'metadata.csv.gz','wt',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(metadata[0]));w.writeheader();w.writerows(metadata)
    summary=dict(split=split,samples=len(y),sequences=len(byseq),limit_per_sequence=limit,
        checks=checks,max_absolute_reconstruction_difference=maxdiff.tolist(),
        input_saturated_elements=saturated_input_elements,input_elements=input_elements,
        wall_seconds=time.monotonic()-started,raw_hdf5_metadata=hdf5_meta,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [MANIFEST,PACKED/(split+'_feat.npy'),PACKED/(split+'_label.npy'),REC/'src/radar_cluster_rocc/features.py',HERE/'plan.json',Path(__file__).resolve()]},
        limitations=['K7 and old split are intentionally unchanged; no time-expiry or pose-alignment repair.',
            'Exact slot interventions use rounded Q8.8 then the hardware output quantizer; not synthesized candidates.',
            'Frozen-model diagnostics reflect feature/model mismatch as well as representation information.'])
    (directory/'reconstruction_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return arrays,y,metadata,summary


def cm(y,p):return np.bincount(2*y+p,minlength=4).reshape(2,2)


def metrics(matrix):
    c=np.asarray(matrix,dtype=float)
    den=c.sum(0)+c.sum(1)
    f=np.divide(2*np.diag(c),den,out=np.zeros(2),where=den>0)
    return dict(samples=int(c.sum()),accuracy=float(np.trace(c)/c.sum()),macro_f1=float(f.mean()),
        per_class_f1=f.tolist(),recall=np.divide(np.diag(c),c.sum(1),out=np.zeros(2),where=c.sum(1)>0).tolist(),confusion_matrix=c.astype(int).tolist())


def paired_sequence_bootstrap(y,p,reference,seq,replicates=2000):
    ids=sorted(set(seq));a=[];b=[]
    seq=np.asarray(seq)
    for name in ids:
        mask=seq==name;a.append(cm(y[mask],p[mask]));b.append(cm(y[mask],reference[mask]))
    a=np.asarray(a);b=np.asarray(b)
    rng=np.random.default_rng(PLAN['data']['sampling_seed'])
    ix=rng.integers(len(ids),size=(replicates,len(ids)))
    aa=a[ix].sum(1);bb=b[ix].sum(1)
    def f1(c):
        diag=np.diagonal(c,axis1=1,axis2=2);den=c.sum(1)+c.sum(2)
        return np.divide(2*diag,den,out=np.zeros_like(diag,dtype=float),where=den>0).mean(1)
    d=f1(aa)-f1(bb)
    return dict(delta_macro_f1_percentile95=np.quantile(d,[.025,.975]).tolist(),replicates=replicates,
        unit='whole sequence, paired resampling',sequences=len(ids),selection_adjusted=False)
