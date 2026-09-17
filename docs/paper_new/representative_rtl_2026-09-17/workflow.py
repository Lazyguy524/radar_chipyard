"""Isolated real-Chisel frontend/classifier closure; never rewrite production RTL."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '2'
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'logs/representative_rtl_20260917'
MECH = ROOT / 'logs/mechanism_convergence_20260916'
PROT = ROOT / 'logs/conditional_protection_20260916'
PLAN = json.loads((HERE / 'plan.json').read_text())
SHIFTS = np.array(PLAN['frontend_shifts'], dtype=np.int64)
EXPORTS = {
    'A': MECH / 'factorial_v2/proxy_seed7/epoch60/export',
    'B': MECH / 'augmentation_v2/proxy_seed7/epoch60/export',
    'C': PROT / 'training/clean_guard_seed7/epoch60/export',
}
IMPLEMENTATIONS = {
    'A': MECH / 'implementations/factorial_proxy_seed7',
    'B': MECH / 'implementations/augmentation_proxy_seed7',
    'C': PROT / 'implementations/clean_guard_seed7',
}
RTL = ROOT / 'generators/chipyard/src/main/scala/radar'
JAR = ROOT / '.classpath_cache/chipyard_fpga_gemmini_qmlp_compare_20260915_r1.jar'
CACHE = Path('/home/soooarr/.cache/coursier/v1/https/repo1.maven.org/maven2')
COMPILER = CACHE / 'org/scala-lang/scala-compiler/2.13.12/scala-compiler-2.13.12.jar'
REFLECT = CACHE / 'org/scala-lang/scala-reflect/2.13.12/scala-reflect-2.13.12.jar'
PLUGIN = CACHE / 'org/chipsalliance/chisel-plugin_2.13.12/6.5.0/chisel-plugin_2.13.12-6.5.0.jar'

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def dump(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

def command(args, cwd, log, timeout):
    start = time.monotonic()
    env = dict(os.environ, MAKEFLAGS='-j2')
    env['PATH'] = str(ROOT / '.conda-env/bin') + ':' + env['PATH']
    with Path(log).open('x') as f:
        p = subprocess.run(list(map(str,args)), cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    dump(str(log)+'.json', dict(command=list(map(str,args)), cwd=str(cwd), returncode=p.returncode,
        wall_seconds=time.monotonic()-start, log_sha256=sha(log)))
    if p.returncode:
        raise RuntimeError('Command failed; preserved log: '+str(log))

def round_even(a, s):
    a = np.asarray(a, dtype=np.int64)
    mag = np.abs(a); q = mag >> s
    if s:
        rem = mag & ((1 << s)-1)
        q += (rem > (1 << (s-1))) | ((rem == (1 << (s-1))) & ((q & 1) != 0))
    return np.where(a < 0, -q, q)

def scalar_round(a, s):
    q, r = divmod(abs(int(a)), 1 << s)
    q += int(2*r > (1 << s) or (2*r == (1 << s) and q%2))
    return -q if a < 0 else q

def prepare():
    OUT.mkdir(exist_ok=False)
    source_files = [HERE/'plan.json', HERE/'workflow.py', HERE/'sim_main.cpp', HERE/'CandidateTop.scala',
        ROOT/'docs/paper_new/conditional_protection_2026-09-16/research_contract.json']
    source_files += [RTL/n for n in ('RadarFeature21.scala','RadarQMLP.scala','RadarStream.scala')]
    for d in EXPORTS.values():
        source_files += [d/n for n in ('params.json','integer_params.npz','Radar_frozen_qmlpParams.scala','params.h','inference_trace.c')]
    source_files += [d/'candidate.c' for d in IMPLEMENTATIONS.values()]
    dump(OUT/'input_manifest.json', {str(p.relative_to(ROOT)):sha(p) for p in source_files})
    # Real, pre-existing C raw proxy (independent from the new Chisel patch).
    legacy = ROOT/'logs/conditional_statistics_20260916/native/kernel.c'
    wrapper = legacy.read_text()+'''\nvoid raw_batch(const radar_feature21_golden_point_t *p,const uint64_t *offset,uint32_t n,int32_t *raw,int8_t *old){
      for(uint32_t i=0;i<n;i++){proxy_raw(p+offset[i],offset[i+1]-offset[i],raw+i*21);feature21_density_exact_lut(p+offset[i],offset[i+1]-offset[i],old+i*21);}}
    '''
    (OUT/'raw_proxy.c').write_text(wrapper)
    command(['gcc','-O2','-std=c99','-shared','-fPIC',OUT/'raw_proxy.c','-o',OUT/'raw_proxy.so'], OUT, OUT/'gcc.log', 30)
    p = np.ascontiguousarray(np.load(MECH/'raw/val/points_q8.npy'),dtype=np.int16)
    o = np.ascontiguousarray(np.load(MECH/'raw/val/offsets.npy'),dtype=np.uint64)
    x = np.load(MECH/'data/val/proxy.npy'); assert len(o)==80451
    lib = ctypes.CDLL(str(OUT/'raw_proxy.so'))
    lib.raw_batch.argtypes = [ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p]
    raw = np.empty((80450,21),np.int32); old = np.empty_like(x)
    lib.raw_batch(p.ctypes.data,o.ctypes.data,80450,raw.ctypes.data,old.ctypes.data)
    z = np.stack([np.clip(round_even(raw[:,j],int(s)),-127,127) for j,s in enumerate(SHIFTS)],axis=1).astype(np.int8)
    assert np.array_equal(x,z)
    # Full feasible raw integer range conservatively covers count/range/span/means.
    a = np.arange(-131072,131073,dtype=np.int64); checks = 0
    for s in sorted(set(SHIFTS.tolist())):
        assert np.array_equal(round_even(a,s),np.fromiter((scalar_round(v,s) for v in a),dtype=np.int64,count=len(a)))
        checks += len(a)
    collisions=[]
    for j in range(21):
        for byte in np.unique(old[:,j]):
            indices=np.flatnonzero(old[:,j]==byte)
            vals=z[indices,j]
            if vals.min()!=vals.max():
                ia=int(indices[vals.argmin()]);ib=int(indices[vals.argmax()])
                collisions.append(dict(slot=j,old_byte=int(byte),rows=[ia,ib],new_bytes=[int(z[ia,j]),int(z[ib,j])]))
                break
    # Fixed boundary workload, does not use labels or choose favorable examples.
    rng=np.random.default_rng(20260917)
    extra=[rng.integers(-32768,32768,(n,4),dtype=np.int16) for n in range(1,512)]
    for n in (1,2,3,7,8,9,255,256,257,511):
        for value in (0,-32768,32767):extra.append(np.full((n,4),value,np.int16))
    extra += [np.array([[-32768,-32768,-32768,-32768],[32767,32767,32767,32767]],np.int16)]
    ep=np.concatenate(extra);eo=np.r_[0,np.cumsum([len(t) for t in extra])].astype(np.uint64)
    points=np.concatenate([p,ep]);offsets=np.r_[o,eo[1:]+len(p)].astype(np.uint64)
    data=OUT/'vectors';data.mkdir()
    points.astype('<i2').tofile(data/'points.bin');offsets.astype('<u8').tofile(data/'offsets.bin')
    bindings=[]
    expected=None
    for name,impl in IMPLEMENTATIONS.items():
        cl=ctypes.CDLL(str(impl/'candidate.so'))
        cl.candidate_batch.argtypes=lib.raw_batch.argtypes
        features=np.empty((len(offsets)-1,21),np.int8); logits=np.empty((len(offsets)-1,2),np.int32)
        cl.candidate_batch(points.ctypes.data,offsets.ctypes.data,len(features),features.ctypes.data,logits.ctypes.data)
        assert np.array_equal(features[:80450],x)
        assert np.array_equal(logits[:80450],np.load(EXPORTS[name].parent/'val_logits.npy'))
        if expected is None:expected=features.copy();features.tofile(data/'features.bin')
        else:assert np.array_equal(features,expected)
        logits.astype('<i4').tofile(data/(name+'_logits.bin'))
        meta=json.loads((EXPORTS[name]/'params.json').read_text())
        text=(EXPORTS[name]/'Radar_frozen_qmlpParams.scala').read_text()
        mul=[]
        for i in (1,2):
            v=[float(re.search(r'val l'+str(i)+k+r' = ([^\n]+)',text).group(1)) for k in ('InputScale','WeightScale','OutputScale')]
            mul.append(int(np.floor(v[0]*v[1]/v[2]*65536+.5)))
        assert mul==meta['multipliers']
        assert max(l['accumulator_abs_bound'] for l in meta['layers'])<2**31
        bindings.append(dict(model=name,seed=7,export_sha256=sha(EXPORTS[name]/'integer_params.npz'),multipliers=mul,
            validation_logits_exact=True,metadata_accumulator_bound=max(l['accumulator_abs_bound'] for l in meta['layers'])))
    report=dict(status='PASS',real_rows=80450,synthetic_rows=len(extra),total_rows=len(offsets)-1,
        python_rounding_cases=checks,raw_proxy_scaled_exact=True,legacy_byte_information_collisions=collisions,
        legacy_different_feature_bytes=int(np.count_nonzero(old!=x)),model_bindings=bindings,
        vector_sha256={p.name:sha(p) for p in data.iterdir()},scope='Pre-RTL numerical preparation, no training or independent test scoring')
    dump(OUT/'preflight.json',report)
    print(json.dumps({k:report[k] for k in ('status','real_rows','synthetic_rows','python_rounding_cases')}),flush=True)

def sources():
    assert json.loads((OUT/'preflight.json').read_text())['status']=='PASS'
    dest=OUT/'scala';dest.mkdir(exist_ok=False)
    package='package chipyard.radar.candidate20260917'
    stream=(RTL/'RadarStream.scala').read_text().replace('package chipyard.radar',package,1)
    feature=(RTL/'RadarFeature21.scala').read_text().replace('package chipyard.radar',package,1)
    # Keep the pipeline and all protocol/accumulation/density behavior. Replace only
    # the ordinary feature output scaling; density already is the retained INT8 slot.
    old='featureQuantProductReg := multiplyByQ8p8QuantConstant(featureQ8p8Reg)'
    assert feature.count(old)==1
    feature=feature.replace(old,'featureQuantProductReg := featureQ8p8Reg')
    old='val featureRounded = bankRoundShift(featureQuantProductReg, 16)'
    assert feature.count(old)==1
    cases=',\n        '.join(str(j)+'.U -> '+('featureQuantProductReg' if s==0 else 'bankRoundShift(featureQuantProductReg, '+str(s)+')') for j,s in enumerate(SHIFTS))
    feature=feature.replace(old,'val featureRounded = MuxLookup(featureIdx, 0.S(57.W))(Seq(\n        '+cases+'))')
    qmlp=(RTL/'RadarQMLP.scala').read_text().replace('package chipyard.radar',package,1)
    old='''val releaseRelativePath =
    "releases/input_convergence_k3_rcs21_20260406/rcs_fix_k7_rcs21_20260414/" +
      "Radar_mlp_binary_k7_rcs21_rcsfixParams.scala"'''
    assert qmlp.count(old)==1
    qmlp=qmlp.replace(old,'val releaseRelativePath = sys.props("radar.candidate.params")')
    for name,body in [('RadarStream.scala',stream),('RadarFeature21.scala',feature),('RadarQMLP.scala',qmlp)]:
        (dest/name).write_text(body)
    shutil.copyfile(HERE/'CandidateTop.scala',dest/'CandidateTop.scala')
    classes=OUT/'classes';classes.mkdir()
    command(['java','-XX:ActiveProcessorCount=2','-Xmx4G','-cp',':'.join(map(str,[COMPILER,REFLECT,JAR])),
        'scala.tools.nsc.Main','-classpath',JAR,'-Xplugin:'+str(PLUGIN),'-d',classes,*sorted(dest.glob('*.scala'))],
        OUT, OUT/'scala_compile.log',900)
    dump(OUT/'isolated_source_manifest.json',{str(p.relative_to(ROOT)):sha(p) for p in dest.iterdir()})
    print('ISOLATED_SCALA_COMPILED',flush=True)

def build(name):
    assert (OUT/'isolated_source_manifest.json').is_file(), 'Compile Scala successfully before elaboration'
    d=OUT/name;d.mkdir(exist_ok=False)
    command(['java','-XX:ActiveProcessorCount=2','-Xmx4G','-Dradar.candidate.params='+str(EXPORTS[name]/'Radar_frozen_qmlpParams.scala'),
        '-cp',str(OUT/'classes')+':'+str(JAR),'chipyard.radar.candidate20260917.CandidateEmit'],d,d/'elaboration.log',900)
    compile_rtl(name)

def compile_rtl(name):
    d=OUT/name
    # CIRCT returns a concatenated multi-file stream, including a non-Verilog
    # resource .f list. Preserve the stream and split on its explicit markers.
    parts=re.split(r'// ----- 8< ----- FILE "([^"]+)" ----- 8< -----\n', (d/'CandidateTop.sv').read_text())
    rtl=d/'rtl';rtl.mkdir(exist_ok=False)
    (rtl/'CandidateTop.sv').write_text(parts[0])
    for filename,body in zip(parts[1::2],parts[2::2]):
        target=rtl/Path(filename).name
        assert not target.exists()
        target.write_text(body)
    sv=sorted(rtl.glob('*.sv'))+sorted(rtl.glob('*.v'))
    assert sv
    command([ROOT/'.conda-env/bin/verilator','--cc','--exe','--build','-j','2','-Wno-fatal',
        '--top-module','CandidateTop','--Mdir',d/'obj','-CFLAGS','-O2',*sv,HERE/'sim_main.cpp','-o','candidate_sim'],
        d,d/'verilator_build.log',900)
    print(name+'_BUILT',flush=True)

def simulate(name):
    d=OUT/name
    command([d/'obj/candidate_sim',OUT/'vectors',name],d,d/'simulation.log',600)
    r=json.loads((d/'rtl_result.json').read_text());assert r['status']=='PASS'
    print(json.dumps(dict(model=name,**r)),flush=True)

def audit():
    original=json.loads((OUT/'input_manifest.json').read_text())
    revisions=json.loads((OUT/'source_revisions.json').read_text()) if (OUT/'source_revisions.json').exists() else {}
    for p,h in original.items():assert sha(ROOT/p)==revisions.get(p,{}).get('after',h),p
    runs={name:json.loads((OUT/name/'rtl_result.json').read_text()) for name in EXPORTS}
    assert all(r['status']=='PASS' for r in runs.values())
    result=dict(status='PASS',runs=runs,input_hashes_unchanged=len(original)-len(revisions),tooling_revisions=revisions,
        preflight_sha256=sha(OUT/'preflight.json'),plan_sha256=sha(HERE/'plan.json'),
        scope='Actual isolated Feature21 + QMLP Chisel RTL simulated with Verilator; not full RISC-V SoC, bitstream, board or independent evaluation.')
    dump(OUT/'summary.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','sources','build','compile_rtl','simulate','audit']);parser.add_argument('--model',choices=list(EXPORTS));a=parser.parse_args()
    if a.stage in ('build','compile_rtl','simulate'):
        assert a.model;globals()[a.stage](a.model)
    else:globals()[a.stage]()
