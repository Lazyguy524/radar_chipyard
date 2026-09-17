"""Variable-dimension point-to-logit C packages and complete raw-view checks."""
from ex_common import *
import shutil

def main():
    evaluation=json.loads((LOG/'evaluation/summary.json').read_text());assert evaluation['status']=='PASS';start=time.monotonic();out=LOG/'package';out.mkdir(exist_ok=False);checks=[]
    main_src=(ROOT/'docs/paper_new/conditional_statistics_2026-09-16/inference_main.c').read_text().replace('shared_frontend(p,n,CANDIDATE_MODE,candidate_shifts,features);','int8_t full[23]; enrichment(p,n,full); for(int j=0;j<RADAR_MLP_INPUT_DIM;j++)features[j]=full[input_positions[j]];').replace('features[21]','features[RADAR_MLP_INPUT_DIM]').replace('i<21','i<RADAR_MLP_INPUT_DIM')
    batch='\nvoid candidate_batch(const radar_feature21_golden_point_t *p,const uint64_t *offset,uint32_t rows,int8_t *x,int32_t *logits){int8_t a[64],b[32];for(uint32_t i=0;i<rows;i++)candidate_infer(p+offset[i],offset[i+1]-offset[i],x+i*RADAR_MLP_INPUT_DIM,a,b,logits+i*2);}\n'
    for tag in VARIANTS:
        cols=take(tag);dim=len(cols)
        for seed in SEEDS:
            d=out/(tag+'_seed'+str(seed));d.mkdir();src=LOG/'training'/d.name/'epoch60/export'
            for name in ['params.h','params.json','integer_params.npz']:shutil.copyfile(src/name,d/name)
            network=(src/'inference_trace.c').read_text().replace('round_shift_even_i64','qmlp_round_shift_even_i64')
            positions='static const int input_positions[]={'+','.join(map(str,cols))+'};\n'
            (d/'candidate.c').write_text(native_source(tag in ['geometry19','combined23'],tag in ['distribution20','combined23'])+network+positions+main_src+batch)
            for flags,name in [(['-shared','-fPIC'],'candidate.so'),([],'candidate')]:subprocess.run(['gcc','-O2','-std=c99',*flags,str(d/'candidate.c'),'-o',str(d/name)],check=True,capture_output=True,timeout=30)
            lib=ctypes.CDLL(str(d/'candidate.so'));lib.candidate_batch.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p];reference=Trace(src,False)
            for condition in ['clean','sparse_single','sparse_context']:
                raw=MECH/'raw/val' if condition=='clean' else OLD/'data'/condition
                points=np.ascontiguousarray(np.load(raw/('points_q8.npy' if condition=='clean' else 'points.npy')),np.int16);offsets=np.ascontiguousarray(np.load(raw/'offsets.npy'),np.uint64);n=len(offsets)-1
                expected=validation(condition)[0][:,cols];want=reference(expected)[-1];x=np.empty((n,dim),np.int8);logits=np.empty((n,2),np.int32)
                lib.candidate_batch(points.ctypes.data,offsets.ctypes.data,n,x.ctypes.data,logits.ctypes.data)
                assert np.array_equal(x,expected) and np.array_equal(logits,want),(tag,seed,condition)
                checks.append(dict(tag=tag,seed=seed,condition=condition,rows=n,feature_mismatches=0,logit_mismatches=0))
                if condition=='clean':
                    points[:offsets[1]].astype('<i2').tofile(d/'example.int16le');got=json.loads(subprocess.check_output([str(d/'candidate'),str(d/'example.int16le')],text=True));assert got['logits']==logits[0].tolist();dump(d/'example.json',got)
                    for size in [0,7,512*8]:
                        bad=d/'invalid.tmp';bad.write_bytes(b'\0'*size);result=subprocess.run([str(d/'candidate'),str(bad)],capture_output=True);assert result.returncode==2;bad.unlink()
                assert time.monotonic()-start+evaluation['wall_seconds']<PLAN['budget']['evaluation_and_package_seconds']
            dump(d/'contract.json',dict(tag=tag,seed=seed,columns=columns(tag),feature_plan=PLAN['features'],input='1..511 points, little endian int16 [x,y,compensated radial velocity,RCS], Q8.8; upstream same-sequence/sensor/GT-track history; sparse observations do not update history',history=PLAN['data']['history'],output='class0 labels7/8; class1 labels0/1/2/3; tie chooses0',scope='Software candidate reference; no board measurement or deployment promotion',integer_weights='all INT8, biases INT32; ties-to-even and ReLU saturation127'))
            print(json.dumps(dict(packaged=tag,seed=seed,exact_rows=275918)),flush=True)
    shutil.copyfile(HERE/'plan.json',out/'plan.json');shutil.copyfile(MECH/'data/scales.json',out/'feature_scales.json')
    dump(out/'summary.json',dict(status='PASS',checks=checks,complete_point_to_logit_rows=sum(r['rows'] for r in checks),wall_seconds=time.monotonic()-start,scope='CPU reference exactness; no hardware measurement'))
    (out/'README.md').write_text('# 可解释特征补充软件参考包\n\n全部五组、三个种子保留。分析对照与当前主方案 A/B 区分见评价结论。每个子目录含原始槽位映射、尺度、模型、C 源码及单簇示例。\n\n```bash\ncd combined23_seed7\ngcc -O2 -std=c99 candidate.c -o candidate\n./candidate example.int16le\n```\n\n输出对照 example.json。历史关联属于上游，不包含检测/跟踪或板测。\n')
    size_guard()
if __name__=='__main__':main()
