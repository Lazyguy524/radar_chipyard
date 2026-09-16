"""Package complete C point-cluster -> features -> integer QMLP candidates."""
import shutil
from kernel import *

def main():
    out=LOG/'inference';out.mkdir(exist_ok=False)
    points=np.load(LOG/'data/diagnostic/points_q8.npy');offsets=np.load(LOG/'data/diagnostic/offsets.npy')
    exps=json.loads((LOG/'data/output_scale_exponents.json').read_text());checks=[]
    common=(LOG/'native/kernel.c').read_text()+(HERE/'shared_candidate.c').read_text()
    for mode,r in [('proxy_scaled',0),('moment24',24),('moment16',16)]:
        features=np.load(LOG/'data/diagnostic'/(mode+'_clean.npy'))
        shift=(np.array(exps[mode])+(PROXY_FRACS if not r else FRACS)).tolist()
        for seed in PLAN['training']['seeds']:
            tag=mode+'_seed'+str(seed);base=out/tag;base.mkdir();export=LOG/'training'/tag/'export'
            shutil.copyfile(export/'params.h',base/'params.h')
            network=(export/'inference_trace.c').read_text().replace('round_shift_even_i64','qmlp_round_shift_even_i64')
            config='\n#define CANDIDATE_MODE '+str(r)+'\nstatic const int32_t candidate_shifts[21] = {'+','.join(map(str,shift))+'};\n'
            (base/'candidate.c').write_text(common+network+config+(HERE/'inference_main.c').read_text())
            for flags,name in [(['-shared','-fPIC'],'candidate.so'),([],'candidate')]:
                subprocess.run(['gcc','-O2','-std=c99',*flags,str(base/'candidate.c'),'-o',str(base/name)],check=True,timeout=30,capture_output=True)
            lib=ctypes.CDLL(str(base/'candidate.so'))
            lib.candidate_infer.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
            expected=np.load(LOG/'evaluation'/(tag+'_clean_logits.npy'))
            for i in range(len(offsets)-1):
                p=np.ascontiguousarray(points[offsets[i]:offsets[i+1]],np.int16)
                x=np.empty(21,np.int8);h1=np.empty(64,np.int8);h2=np.empty(32,np.int8);y=np.empty(2,np.int32)
                lib.candidate_infer(p.ctypes.data,len(p),x.ctypes.data,h1.ctypes.data,h2.ctypes.data,y.ctypes.data)
                assert np.array_equal(x,features[i]) and np.array_equal(y,expected[i])
            input_file=base/'example.int16le';points[offsets[0]:offsets[1]].astype('<i2').tofile(input_file)
            got=json.loads(subprocess.check_output([str(base/'candidate'),str(input_file)],text=True,timeout=5))
            assert got['features']==features[0].tolist() and got['logits']==expected[0].tolist()
            dump(base/'example.json',got)
            invalid=base/'invalid.tmp';invalid.write_bytes(b'')
            assert subprocess.run([str(base/'candidate'),str(invalid)],capture_output=True,timeout=5).returncode==2
            invalid.write_bytes(b'\0'*(512*8))
            assert subprocess.run([str(base/'candidate'),str(invalid)],capture_output=True,timeout=5).returncode==2
            invalid.unlink()
            checks.append(dict(tag=tag,complete_c_rows=len(features),cli_example='PASS',invalid_lengths_rejected=2))
    report=dict(status='PASS',checks=checks,source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'build_inference.py',HERE/'inference_main.c',HERE/'shared_candidate.c']},
        scope='Host C executable only, K7/GT fusion upstream, no RISC-V cross-compile, RTL or bitstream; all six configurations retained, no best-seed release selection.')
    dump(out/'summary.json',report);print(json.dumps(report))

if __name__=='__main__':main()
