"""Freeze chosen three seeds plus alternative, verify complete point-to-logit C."""
import shutil
from evaluate import export_path
from sw_common import *

def main():
    start=time.monotonic();decision=json.loads((LOG/'evaluation/summary.json').read_text())['decision']
    out=LOG/'package';out.mkdir(exist_ok=False);checks=[]
    ex,fr=base.scales();legacy=(base.PREV/'native/kernel.c').read_text();single=(base.HERE/'single_variant.c').read_text()
    main_src=(ROOT/'docs/paper_new/conditional_statistics_2026-09-16/inference_main.c').read_text()
    batch='\nvoid candidate_batch(const radar_feature21_golden_point_t *p,const uint64_t *offset,uint32_t rows,int8_t *x,int32_t *logits){int8_t a[64],b[32];for(uint32_t i=0;i<rows;i++)candidate_infer(p+offset[i],offset[i+1]-offset[i],x+i*21,a,b,logits+i*2);}\n'
    for role,tag,bits in [('main',decision['main'],decision['mean_bits']),('alternative',decision['alternative'],24)]:
        mode='mean' if tag.startswith('mean') else 'proxy';flag=int(mode=='mean')
        for seed in SEEDS:
            d=out/(role+'_seed'+str(seed));d.mkdir();export=export_path(tag,seed)
            for name in ['params.h','params.json','params.npz']:
                if (export/name).is_file():shutil.copyfile(export/name,d/name)
            config='\n#define FEATURE_FLAGS %d\n#define MEAN_RECIP_BITS %d\n#define SPATIAL_RECIP_BITS 24\n#define CANDIDATE_MODE %d\n'%(flag,bits,flag)
            config+='static const int32_t candidate_shifts[21]={'+','.join(map(str,(ex+fr)[flag]))+'};\n'
            network=(export/'inference_trace.c').read_text().replace('round_shift_even_i64','qmlp_round_shift_even_i64')
            (d/'candidate.c').write_text(legacy+config+single+network+main_src+batch)
            for flags,name in [(['-shared','-fPIC'],'candidate.so'),([],'candidate')]:
                subprocess.run(['gcc','-O2','-std=c99',*flags,str(d/'candidate.c'),'-o',str(d/name)],check=True,timeout=30,capture_output=True)
            lib=ctypes.CDLL(str(d/'candidate.so'));lib.candidate_batch.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p]
            reference=native_model(export)
            for condition in ['clean','sparse_single','sparse_context']:
                raw=MECH/'raw/val' if condition=='clean' else LOG/'data'/condition
                points=np.ascontiguousarray(np.load(raw/('points_q8.npy' if condition=='clean' else 'points.npy')),np.int16)
                offsets=np.ascontiguousarray(np.load(raw/'offsets.npy'),np.uint64);n=len(offsets)-1
                expected,_,_=validation(condition,mode,bits);expected_logits=reference(expected)[-1]
                x=np.empty((n,21),np.int8);logits=np.empty((n,2),np.int32)
                lib.candidate_batch(points.ctypes.data,offsets.ctypes.data,n,x.ctypes.data,logits.ctypes.data)
                assert np.array_equal(x,expected) and np.array_equal(logits,expected_logits),(tag,seed,condition)
                checks.append(dict(role=role,tag=tag,seed=seed,mean_bits=bits,condition=condition,rows=n,feature_mismatches=0,logit_mismatches=0))
                if condition=='clean':
                    points[:offsets[1]].astype('<i2').tofile(d/'example.int16le')
                    got=json.loads(subprocess.check_output([str(d/'candidate'),str(d/'example.int16le')],text=True,timeout=5));assert got['logits']==logits[0].tolist();dump(d/'example.json',got)
            contract=dict(role=role,tag=tag,seed=seed,mean_reciprocal_bits=bits,feature_flags=flag,feature_shifts=(ex+fr)[flag].tolist(),
                point_format='little-endian signed int16 [x,y,compensated_radial_velocity,rcs], each Q8.8; 1..511 points; 21 signed INT8 features; INT32 logits',
                history=PLAN['data']['history'],history_scope='GT track association is upstream and remains a deployment limitation; accumulated coordinates are not a single-frame physical shape',
                output='0 = original labels7/8, 1 = original0/1/2/3; logits argmax tie chooses0; no runtime normalization',source_export=str(export.relative_to(ROOT)))
            dump(d/'contract.json',contract)
            print(json.dumps(dict(package=role,seed=seed,exact_rows=sum(r['rows'] for r in checks if r['role']==role and r['seed']==seed))),flush=True)
    shutil.copyfile(HERE/'plan.json',out/'plan.json');shutil.copyfile(MECH/'data/scales.json',out/'feature_scales.json')
    dump(out/'summary.json',dict(status='PASS',decision=decision,checks=checks,complete_point_to_logit_rows=sum(r['rows'] for r in checks),wall_seconds=time.monotonic()-start,
        scope='CPU C reference correctness only; no new RTL/SoC/board measurement'))
    (out/'README.md').write_text('# 冻结的软件参考包\n\n主方案及备选均保留 seed 7、17、37，不挑选最佳种子。每个子目录的 contract.json 定义表示、尺度、标签和历史边界。\n\n编译并运行示例：\n\n```bash\ncd main_seed7\ngcc -O2 -std=c99 candidate.c -o candidate\n./candidate example.int16le\n```\n\n输出应与 example.json 一致。输入为上游已关联的一个点簇，不包含检测、关联或原始雷达信号处理。全部训练与评价脚本位于 docs/paper_new/software_convergence_2026-09-17。\n',encoding='utf8')
    size_guard()
if __name__=='__main__':main()
