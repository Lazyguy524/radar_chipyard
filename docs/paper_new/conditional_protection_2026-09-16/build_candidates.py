"""Build matching single-pass proxy frontends and all six final integer models."""
import shutil
import time
from protection_common import *

def main():
    start=time.monotonic();out=LOG/'implementations';out.mkdir(exist_ok=False)
    t=json.loads((LOG/'training/summary.json').read_text());assert t['status']=='PASS'
    points=np.ascontiguousarray(np.load(MECH/'raw/val/points_q8.npy'),np.int16);offsets=np.ascontiguousarray(np.load(MECH/'raw/val/offsets.npy'),np.uint64)
    expected_x=np.load(MECH/'data/val/proxy.npy');n=len(offsets)-1;assert n==80450
    ex,fr=base.scales();legacy=(base.PREV/'native/kernel.c').read_text();single=(base.HERE/'single_variant.c').read_text()
    main_src=(ROOT/'docs/paper_new/conditional_statistics_2026-09-16/inference_main.c').read_text()
    batch='\nvoid candidate_batch(const radar_feature21_golden_point_t *p,const uint64_t *offset,uint32_t rows,int8_t *x,int32_t *logits){int8_t a[64],b[32];for(uint32_t i=0;i<rows;i++)candidate_infer(p+offset[i],offset[i+1]-offset[i],x+i*21,a,b,logits+i*2);}\n'
    checks=[];sources={}
    for r in t['runs']:
        tag=r['method']+'_seed'+str(r['seed']);d=out/tag;d.mkdir();export=LOG/'training'/tag/'epoch60/export';shutil.copyfile(export/'params.h',d/'params.h')
        config='\n#define FEATURE_FLAGS 0\n#define MEAN_RECIP_BITS 24\n#define SPATIAL_RECIP_BITS 24\n#define CANDIDATE_MODE 0\n'
        config+='static const int32_t candidate_shifts[21]={'+','.join(map(str,(ex+fr)[0]))+'};\n'
        network=(export/'inference_trace.c').read_text().replace('round_shift_even_i64','qmlp_round_shift_even_i64')
        (d/'candidate.c').write_text(legacy+config+single+network+main_src+batch)
        for flags,name in [(['-shared','-fPIC'],'candidate.so'),([],'candidate')]:subprocess.run(['gcc','-O2','-std=c99',*flags,str(d/'candidate.c'),'-o',str(d/name)],check=True,timeout=30,capture_output=True)
        lib=ctypes.CDLL(str(d/'candidate.so'));lib.candidate_batch.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p]
        x=np.empty((n,21),np.int8);logits=np.empty((n,2),np.int32);lib.candidate_batch(points.ctypes.data,offsets.ctypes.data,n,x.ctypes.data,logits.ctypes.data)
        assert np.array_equal(x,expected_x) and np.array_equal(logits,np.load(export.parent/'val_logits.npy'))
        points[:offsets[1]].astype('<i2').tofile(d/'example.int16le');got=json.loads(subprocess.check_output([str(d/'candidate'),str(d/'example.int16le')],text=True,timeout=5))
        assert got['logits']==logits[0].tolist();dump(d/'example.json',got)
        checks.append(dict(method=r['method'],seed=r['seed'],rows=n,exact=True))
        for file in ['candidate.c','params.h']:sources[str((d/file).relative_to(ROOT))]=sha(d/file)
    report=dict(status='PASS',checks=checks,complete_c_rows=n*len(checks),wall_seconds=time.monotonic()-start,source_sha256=sources,
        cost='Same proxy frontend and 21-64-32-2 integer inference. Teacher and group metadata are training-only; no extra runtime model or input. Physical cost unmeasured.')
    dump(out/'summary.json',report);print(json.dumps(dict(status='PASS',complete_c_rows=report['complete_c_rows'])),flush=True)
if __name__=='__main__':main()
