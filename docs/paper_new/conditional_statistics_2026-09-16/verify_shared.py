"""Verify a genuinely shared, single-pass C implementation and record cost bounds."""
import csv
from kernel import *

def main():
    out=LOG/'shared';out.mkdir(exist_ok=False)
    (out/'shared.c').write_text((LOG/'native/kernel.c').read_text()+(HERE/'shared_candidate.c').read_text())
    subprocess.run(['gcc','-O2','-std=c99','-shared','-fPIC',str(out/'shared.c'),'-o',str(out/'shared.so')],check=True,timeout=30,capture_output=True)
    lib=ctypes.CDLL(str(out/'shared.so'))
    lib.shared_extract.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_void_p]
    lib.shared_frontend.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p]
    k=Kernel(LOG/'native',False);exps=json.loads((LOG/'data/output_scale_exponents.json').read_text())
    with (LOG/'data/diagnostic/metadata.csv').open() as f:meta=list(csv.DictReader(f))
    points=np.load(LOG/'data/diagnostic/points_q8.npy');offsets=np.load(LOG/'data/diagnostic/offsets.npy')
    expected={(m,c):np.load(LOG/'data/diagnostic'/(m+'_'+c+'.npy')) for m in ['proxy_scaled','moment24','moment16'] for c in PLAN['diagnostics']['paired_conditions']}
    cases=0;raw_cases=0
    for i,row in enumerate(meta):
        q=points[offsets[i]:offsets[i+1]];n=len(q)
        seed=int.from_bytes(hashlib.sha256((row['sequence']+row['packed_row']+'perturb').encode()).digest()[:8],'little')
        order=np.random.default_rng(seed).permutation(n);center=np.mean(q[:,:2].astype(float),axis=0)
        near=np.argsort(np.sum((q[:,:2]-center)**2,axis=1),kind='stable')
        coarse=q.copy();coarse[:,:2]=np.clip(np.rint(q[:,:2].astype(float)/4)*4,-32768,32767).astype(np.int16)
        conditions={'clean':q,'uniform_half':q[np.sort(order[:max(1,(n+1)//2)])],
            'uniform_quarter':q[np.sort(order[:max(1,(n+3)//4)])],'central_half':q[np.sort(near[:max(1,(n+1)//2)])],'xy_fraction6':coarse}
        for c,p in conditions.items():
            p=np.ascontiguousarray(p,np.int16);ref,_,_=k(p)
            for mode,r,index in [('proxy_scaled',0,0),('moment24',24,1),('moment16',16,2)]:
                raw=np.empty(21,np.int64);lib.shared_extract(p.ctypes.data,len(p),r,raw.ctypes.data)
                assert np.array_equal(raw,ref[index]);raw_cases+=1
                shift=np.ascontiguousarray(np.array(exps[mode])+(PROXY_FRACS if mode=='proxy_scaled' else FRACS),np.int32)
                got=np.empty(21,np.int8);lib.shared_frontend(p.ctypes.data,len(p),r,shift.ctypes.data,got.ctypes.data)
                assert np.array_equal(got,expected[(mode,c)][i]);cases+=1
    bounds=json.loads((LOG/'preflight.json').read_text())['bounds']
    graph={
      'scope':'Logical operations and proven widths, not measured FPGA LUT/DSP/cycles/power. C tables both uint32_t[512]; hardware width pruning unverified.',
      'proxy_scaled':{'point_passes':1,'first_moment_accumulators':4,'additional_spatial_product_accumulators':0,'additional_xy_products_per_point':0,'output_bits_per_feature':8},
      'centered_moments':{'point_passes':1,'first_moment_accumulators':4,'additional_spatial_product_accumulators':3,'additional_xy_products_per_point':3,
        'centering_subtractions_per_point':4,'input_bits':16,'centered_delta_signed_bits':17,'sum_delta_signed_bits':26,
        'sum_square_unsigned_bits':41,'sum_cross_signed_bits':42,'reciprocal_lookup_per_cluster':1,'shared_finalize_reciprocal_products':7,
        'shared_finalize_mean_products':3,'mean_extra_fraction_bits':4,'sqrt_eigensolver':False,'output_bits_per_feature':8,
        'note':'Four first-moment sums shared by means and covariance; extrema/range/density shared, no repeated point scans. Hardware may serialize three products or parallelize them; resource and latency effects remain unmeasured.'},
      'precision_bounds':bounds,
      'classifier':{'shape':[21,64,32,2],'weight_count':3456,'bias_count':98,'changed_weights_and_requant_multipliers_require_new_physical_checks':True}}
    dump(out/'cost_graph.json',graph)
    report=dict(status='PASS',single_pass_raw_equivalence_cases=raw_cases,integer_frontend_equivalence_cases=cases,
        conditions=PLAN['diagnostics']['paired_conditions'],source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'shared_candidate.c',HERE/'verify_shared.py',LOG/'native/kernel.c']},
        scope='Implemented one-pass C statistical candidate; cost graph is structural, not measured hardware performance')
    dump(out/'summary.json',report);print(json.dumps(report))

if __name__=='__main__':main()
