"""Build executable single-pass candidates; verify all primary validation rows."""
import shutil
import time
from common import *

def main():
    start=time.monotonic();out=LOG/'implementations';out.mkdir(exist_ok=False)
    points=np.ascontiguousarray(np.load(LOG/'raw/val/points_q8.npy'),np.int16)
    offsets=np.ascontiguousarray(np.load(LOG/'raw/val/offsets.npy'),np.uint64);n=len(offsets)-1
    assert n==80450 and offsets[0]==0 and offsets[-1]==len(points) and (np.diff(offsets)>0).all() and (np.diff(offsets)<=511).all()
    ex,fr=scales();checks=[];source_hashes={};models=[]
    for stage in ['factorial','augmentation']:
        summary=LOG/(stage+'_v2')/'summary.json'
        if summary.exists():
            r=json.loads(summary.read_text());assert r['status']=='PASS';models.extend(r['runs'])
    assert len(models) in [20,29]
    legacy=(PREV/'native/kernel.c').read_text();single=(HERE/'single_variant.c').read_text()
    main_src=(ROOT/'docs/paper_new/conditional_statistics_2026-09-16/inference_main.c').read_text()
    batch='''\nvoid candidate_batch(const radar_feature21_golden_point_t *p,const uint64_t *offset,uint32_t rows,int8_t *x,int32_t *logits) {
      int8_t h1[64],h2[32];for(uint32_t i=0;i<rows;i++)candidate_infer(p+offset[i],offset[i+1]-offset[i],x+i*21,h1,h2,logits+i*2);
    }\n'''
    for run in models:
        stage,mode,seed=run['stage'],run['mode'],run['seed'];flag=PLAN['factorial']['flags'][mode];tag=stage+'_'+mode+'_seed'+str(seed)
        d=out/tag;d.mkdir();export=LOG/(stage+'_v2')/(mode+'_seed'+str(seed))/'epoch60/export'
        shutil.copyfile(export/'params.h',d/'params.h')
        config='\n#define FEATURE_FLAGS %d\n#define MEAN_RECIP_BITS 24\n#define SPATIAL_RECIP_BITS 24\n#define CANDIDATE_MODE %d\n'%(flag,flag)
        config+='static const int32_t candidate_shifts[21]={'+','.join(map(str,(ex+fr)[flag]))+'};\n'
        network=(export/'inference_trace.c').read_text().replace('round_shift_even_i64','qmlp_round_shift_even_i64')
        (d/'candidate.c').write_text(legacy+config+single+network+main_src+batch)
        for flags,name in [(['-shared','-fPIC'],'candidate.so'),([],'candidate')]:
            subprocess.run(['gcc','-O2','-std=c99',*flags,str(d/'candidate.c'),'-o',str(d/name)],check=True,timeout=30,capture_output=True)
        lib=ctypes.CDLL(str(d/'candidate.so'));lib.candidate_batch.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p]
        x=np.empty((n,21),np.int8);logits=np.empty((n,2),np.int32)
        lib.candidate_batch(points.ctypes.data,offsets.ctypes.data,n,x.ctypes.data,logits.ctypes.data)
        assert np.array_equal(x,np.load(LOG/'data/val'/(mode+'.npy')))
        expected=np.load(export.parent/'val_logits.npy');assert np.array_equal(logits,expected)
        points[:offsets[1]].astype('<i2').tofile(d/'example.int16le')
        got=json.loads(subprocess.check_output([str(d/'candidate'),str(d/'example.int16le')],text=True,timeout=5))
        assert got['features']==x[0].tolist() and got['logits']==logits[0].tolist();dump(d/'example.json',got)
        checks.append(dict(stage=stage,mode=mode,seed=seed,feature_rows=n,logit_rows=n,exact=True))
        source_hashes[str(d.relative_to(ROOT))+'/candidate.c']=sha(d/'candidate.c');source_hashes[str(d.relative_to(ROOT))+'/params.h']=sha(d/'params.h')
    costs={
      'scope':'Logical execution structure only. No new FPGA/ASIC/board resource, timing, power or energy results. C compiler can eliminate compile-time disabled moment products; neither model size nor logical ROM bits implies measured physical savings.',
      'shared':{'point_passes':1,'first_moment_accumulators':4,'classifier':[21,64,32,2],'weights':3456,'biases':98,'spatial_eigensolver':False},
      'proxy':{'point_centering_subtractions':0,'additional_spatial_products_per_point':0,'spatial_second_accumulators':0,'mean_finish':'original count-bin shift'},
      'mean':{'point_centering_subtractions':4,'additional_spatial_products_per_point':0,'spatial_second_accumulators':0,'reciprocal_lookups_per_cluster':1,'mean_reciprocal_products_per_cluster':4},
      'shape':{'point_centering_subtractions':2,'additional_spatial_products_per_point':3,'spatial_second_accumulators':3,'reciprocal_lookups_per_cluster':1,'mean_outputs':'original count-bin shift; two centered sums restored before old x/y means'},
      'moment':{'point_centering_subtractions':4,'additional_spatial_products_per_point':3,'spatial_second_accumulators':3,'reciprocal_lookups_per_cluster':1,'reciprocal_products_per_cluster':7,'mean_products_for_covariance':3},
      'mixed_precision':'Using different reciprocals for mean and covariance may require a second lookup and recomputing spatial mean terms. It is not automatically cheaper than one shared higher-precision reciprocal.'}
    dump(out/'cost_graph.json',costs)
    report=dict(status='PASS',models=len(checks),rows_per_model=n,complete_c_rows=n*len(checks),checks=checks,source_sha256=source_hashes,
        wall_seconds=time.monotonic()-start,scope='Single-pass host C candidate with fixed compile-time feature family and matching epoch60 weights; no RTL/bitstream installation')
    dump(out/'summary.json',report);print(json.dumps(dict(status='PASS',models=len(checks),complete_c_rows=report['complete_c_rows'],seconds=report['wall_seconds'])))

if __name__=='__main__':main()
