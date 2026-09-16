"""Complete host C prototypes with three shared integer roots per root cluster."""
import shutil
import time
from common_encoding import *

def main():
    started=time.monotonic();out=LOG/'implementations';out.mkdir(exist_ok=False)
    points=np.ascontiguousarray(np.load(MECH/'raw/val/points_q8.npy'),np.int16);offsets=np.ascontiguousarray(np.load(MECH/'raw/val/offsets.npy'),np.uint64);n=len(offsets)-1
    shifts=json.loads((LOG/'data/scales.json').read_text())['shifts'];models=json.loads((LOG/'training/summary.json').read_text())['runs'];assert len(models)==6
    native=(LOG/'native/encoding.c').read_text();single=(ROOT/'docs/paper_new/mechanism_convergence_2026-09-16/single_variant.c').read_text()
    marker='  for(int j=0;j<21;j++){\n    int shift=shifts[j];';assert single.count(marker)==1
    single=single.replace(marker,'  if(ENCODING_ROOT)encoding_root_row(out,out);\n'+marker)
    main_src=(ROOT/'docs/paper_new/conditional_statistics_2026-09-16/inference_main.c').read_text()
    batch='''\nvoid candidate_batch(const radar_feature21_golden_point_t *p,const uint64_t *offset,uint32_t rows,int8_t *x,int32_t *logits) {
      int8_t h1[64],h2[32];for(uint32_t i=0;i<rows;i++)candidate_infer(p+offset[i],offset[i+1]-offset[i],x+i*21,h1,h2,logits+i*2);
    }\n'''
    checks=[]
    for r in models:
        mode,seed=r['mode'],r['seed'];i=MODES.index(mode);d=out/(mode+'_seed'+str(seed));d.mkdir();exp=LOG/'training'/(mode+'_seed'+str(seed))/'epoch60/export'
        shutil.copyfile(exp/'params.h',d/'params.h');network=(exp/'inference_trace.c').read_text().replace('round_shift_even_i64','qmlp_round_shift_even_i64')
        config='\n#define FEATURE_FLAGS 3\n#define MEAN_RECIP_BITS 24\n#define SPATIAL_RECIP_BITS 24\n#define CANDIDATE_MODE 3\n#define ENCODING_ROOT '+str(int(mode=='root'))+'\n'
        config+='static const int32_t candidate_shifts[21]={'+','.join(map(str,shifts[i]))+'};\n'
        (d/'candidate.c').write_text(native+config+single+network+main_src+batch)
        for flags,name in [(['-shared','-fPIC'],'candidate.so'),([],'candidate')]:subprocess.run(['gcc','-O2','-std=c99',*flags,str(d/'candidate.c'),'-o',str(d/name)],check=True,timeout=30,capture_output=True)
        lib=ctypes.CDLL(str(d/'candidate.so'));lib.candidate_batch.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p]
        x=np.empty((n,21),np.int8);y=np.empty((n,2),np.int32);lib.candidate_batch(points.ctypes.data,offsets.ctypes.data,n,x.ctypes.data,y.ctypes.data)
        assert np.array_equal(x,np.load(LOG/'data/val'/(mode+'.npy'))) and np.array_equal(y,np.load(exp.parent/'val_logits.npy'))
        points[:offsets[1]].astype('<i2').tofile(d/'example.int16le');got=json.loads(subprocess.check_output([str(d/'candidate'),str(d/'example.int16le')],text=True,timeout=5))
        assert got['features']==x[0].tolist() and got['logits']==y[0].tolist();dump(d/'example.json',got)
        checks.append(dict(mode=mode,seed=seed,rows=n,feature_and_logit_equal=True))
    report=dict(status='PASS',checks=checks,complete_c_rows=n*len(models),wall_seconds=time.monotonic()-started,
        root_cost='Three integer square roots per cluster, max/min reuse the two standard deviations; added to shared first/second-moment path. No measured FPGA/board benefit claimed.',
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'build_candidates.py',HERE/'encoding.c',ROOT/'docs/paper_new/mechanism_convergence_2026-09-16/single_variant.c']})
    dump(out/'summary.json',report);print(json.dumps(dict(status='PASS',complete_c_rows=report['complete_c_rows'],seconds=report['wall_seconds'])))

if __name__=='__main__':main()
