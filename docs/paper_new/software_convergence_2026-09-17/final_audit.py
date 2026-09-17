"""Recompute decision guards from public tables and protect earlier evidence."""
from sw_common import *

def main():
    train=json.loads((LOG/'training/summary.json').read_text());evaluation=json.loads((LOG/'evaluation/summary.json').read_text())
    package=json.loads((LOG/'package/summary.json').read_text());assert all(x['status']=='PASS' for x in [train,evaluation,package])
    expected={(m,c,s) for m in MODES for c in PLAN['training']['coverage'] for s in SEEDS}
    assert {(r['mode'],r['coverage'],r['seed']) for r in train['runs']}==expected and len(train['runs'])==12
    for s in SEEDS:assert len(set(r['initialization_sha256'] for r in train['runs'] if r['seed']==s))==1
    for c in PLAN['training']['coverage']:
        for s in SEEDS:assert len(set(r['schedule_sha256'] for r in train['runs'] if r['coverage']==c and r['seed']==s))==1
    for r in train['runs']:
        assert r['integer_layer_mismatches']==[0,0,0]
        curve=json.loads((LOG/'training'/r['tag']/'summary.json').read_text())['curve']
        assert [x['epoch'] for x in curve if x['phase']=='warmup']==list(range(1,21))
        assert [x['epoch'] for x in curve if x['phase']=='qat']==list(range(1,61))
    for rel,h in train['source_sha256'].items():assert sha(ROOT/rel)==h,rel
    metric=readcsv(LOG/'evaluation/full_metrics.csv');mi={(r['tag'],int(r['seed']),r['condition']):float(r['macro_f1']) for r in metric}
    groups=readcsv(LOG/'evaluation/conditional_groups.csv');gi={(r['tag'],int(r['seed']),r['condition'],r['axis'],r['group']):r for r in groups}
    assert len(mi)==(3+4+4)*3*13
    def score(tag,s):
        return sum([mi[(tag,s,'clean')],sum(mi[(tag,s,'uniform_quarter_'+str(i))] for i in range(3))/3,
            mi[(tag,s,'central_half')],mi[(tag,s,'sparse_single')],mi[(tag,s,'sparse_context')]])/5
    rows=[]
    for gate in evaluation['final_gates']:
        t=gate['tag'];fail=[]
        for s in SEEDS:
            if mi[(t,s,'clean')]-mi[('A',s,'clean')]<-.002-1e-12:fail.append('clean_seed'+str(s))
        for c in ['quarter_mean','central_half','sparse_single','sparse_context']:
            cs=['uniform_quarter_'+str(i) for i in range(3)] if c=='quarter_mean' else [c]
            if sum(mi[(t,s,v)]-mi[('B',s,v)] for s in SEEDS for v in cs)/(3*len(cs))<-.003-1e-12:fail.append(c)
        bad=0
        for r in groups:
            if r['tag']==t and r['seed']=='7' and r['supported']=='True':
                c,a,g=r['condition'],r['axis'],r['group'];delta=[float(gi[(t,s,c,a,g)]['accuracy'])-float(gi[('A',s,c,a,g)]['accuracy']) for s in SEEDS]
                if max(delta)<0 and sum(delta)/3<-.01-1e-12:bad+=1
        if bad:fail.append('supported_group_regression')
        gains=[score(t,s)-score('B',s) for s in SEEDS]
        if min(gains)<=0 or sum(gains)/3<.001-1e-12:fail.append('composite_gain')
        assert fail==gate['failures'] and bad==len(gate['group_failures'])
        assert all(abs(a-b)<1e-12 for a,b in zip(gains,gate['composite_vs_B']))
        rows.append(dict(tag=t,failures=fail,group_failures=bad,recomputed_from_csv=True))
    for r in evaluation['precision']:
        tag=r['tag'];alias=tag+'_q'+str(r['bits']);bad=0
        for s in SEEDS:
            for c in PLAN['evaluation']['conditions']:
                bad+=int(mi[(alias,s,c)]-mi[(tag,s,c)]<-.001-1e-12)
        for rgroup in groups:
            if rgroup['tag']==alias and rgroup['supported']=='True':
                s,c,a,g=int(rgroup['seed']),rgroup['condition'],rgroup['axis'],rgroup['group']
                bad+=int(float(rgroup['accuracy'])-float(gi[(tag,s,c,a,g)]['accuracy'])<-.005-1e-12)
        assert bad==len(r['failures']) and r['accepted']==(bad==0)
    accepted=[g for g in evaluation['final_gates'] if g['accepted']];decision=evaluation['decision']
    if not accepted:assert decision['main']=='A' and decision['alternative']=='B'
    else:assert any(g['tag']==decision['evaluation_tag'] for g in accepted)
    assert package['decision']==decision and len(package['checks'])==18
    assert all(r['feature_mismatches']==r['logit_mismatches']==0 for r in package['checks'])
    old=[]
    for name,date in [('mechanism_convergence','2026-09-16'),('moment_encoding','2026-09-16'),('conditional_protection','2026-09-16'),('representative_rtl','2026-09-17')]:
        manifest=ROOT/'docs/paper_new'/(name+'_'+date)/'evidence_manifest.json';data=json.loads(manifest.read_text());entries=data.get('files',data);count=0
        for rel,value in entries.items():
            h=value.get('sha256') if isinstance(value,dict) else value
            if isinstance(h,str) and len(h)==64:assert sha(ROOT/rel)==h,rel;count+=1
        assert count;old.append(dict(package=name,files=count,manifest_sha256=sha(manifest)))
    prep=json.loads((LOG/'preparation.json').read_text())
    # Include review and before-backup elapsed wall time in preparation bound.
    preparation_wall=(LOG/'training/source_manifest.json').stat().st_mtime-(LOG/'synthetic_preflight.json').stat().st_mtime
    runtime=dict(preparation_compute_seconds=prep['wall_seconds'],preparation_elapsed_to_training_seconds=preparation_wall,
        training_seconds=train['wall_seconds'],evaluation_seconds=evaluation['wall_seconds'],package_seconds=package['wall_seconds'],output_bytes=size_guard())
    assert preparation_wall<1800 and runtime['training_seconds']<2400 and runtime['evaluation_seconds']+runtime['package_seconds']<1800
    dump(HERE/'validation.json',dict(status='PASS',scope='Bounded software selection complete; no independent generalization or hardware performance claim',
        decision=decision,training_trajectories=12,decision_rechecks=rows,previous_evidence=old,runtime=runtime,source_manifest_verified=True,
        single_executor_review=True,remaining_gaps=['Independent generalization confirmation','Autonomous tracking and bounded/compensated history','Matched hardware cost, timing and board measurements']))
    print(json.dumps(dict(status='PASS',runtime=runtime,decision=decision)),flush=True)
if __name__=='__main__':main()
