"""Transitive provenance closure; verify references, not merely manifest files."""
from ab_common import *

def main():
    assert json.loads((LOG/'training/summary.json').read_text())['status']=='PASS'
    checked={};manifests=[]
    for directory in [OLD/'training',MECH/'factorial_v2',MECH/'augmentation_v2']:
        for path in directory.glob('source_manifest.json'):
            data=json.loads(path.read_text());mapping=data.get('sha256',data.get('source_sha256',{}))
            if not isinstance(mapping,dict):continue
            n=0
            for rel,value in mapping.items():
                h=value.get('sha256') if isinstance(value,dict) else value
                if not isinstance(h,str) or len(h)!=64:continue
                target=Path(rel) if Path(rel).is_absolute() else ROOT/rel
                assert target.is_file() and sha(target)==h,(path,rel);checked[str(target.relative_to(ROOT))]=h;n+=1
            manifests.append(dict(path=str(path.relative_to(ROOT)),references_checked=n,sha256=sha(path)))
    direct=[ROOT/'tests/radar-feature21-qmlp-cpu-fullchain-profile.c',base.PREV/'native/kernel.c',base.PREV/'data/output_scale_exponents.json',base.HERE/'common.py',base.HERE/'evaluate_stage.py',sw.HERE/'sw_common.py',sw.HERE/'evaluate.py',ROOT/'docs/paper_new/conditional_statistics_2026-09-16/inference_main.c']
    for p in direct:checked[str(p.relative_to(ROOT))]=sha(p)
    for tag in VARIANTS:
        d=LOG/'preflight'/tag;source=frontend_source(tag)
        assert (d/'frontend.c').read_text().startswith(source),'Preflight original C kernel/config no longer matches source'
    # Independent regeneration in isolated dirs checks the original C arithmetic body.
    out=LOG/'dependency_trace_verification';out.mkdir(exist_ok=False)
    import shutil
    for tag in VARIANTS:
        src=LOG/'preflight'/tag/'export';d=out/tag;d.mkdir()
        for name in ['params.h','params.json']:shutil.copyfile(src/name,d/name)
        Trace(d);assert (d/'inference_trace.c').read_bytes()==(src/'inference_trace.c').read_bytes()
    dump(LOG/'dependency_manifest.json',dict(status='PASS',sha256=checked,manifests=manifests,preflight_c_sources_reconstructed_exactly=True,scope='Post-training transitive closure of existing source manifests plus exact preflight C-source reconstruction. Initial preflight verified 969 entries of the previous software package; this closure is a final audit, not claimed to have happened before training.'))
    print('TRANSITIVE_DEPENDENCY_PASS',len(checked),flush=True)
if __name__=='__main__':main()
