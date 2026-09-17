"""Recompute all decisions from emitted tables, protect frozen history."""
from ab_common import *

def main():
    train=json.loads((LOG/'training/summary.json').read_text());e=json.loads((LOG/'evaluation/summary.json').read_text());p=json.loads((LOG/'package/summary.json').read_text());pre=json.loads((LOG/'preflight.json').read_text())
    assert all(v['status']=='PASS' for v in [train,e,p,pre]);assert len(train['runs'])==12
    dependencies=json.loads((LOG/'dependency_manifest.json').read_text());assert dependencies['status']=='PASS'
    for name,h in dependencies['sha256'].items():assert sha(ROOT/name)==h,name
    assert {(r['variant'],r['seed']) for r in train['runs']}=={(t,s) for t in VARIANTS for s in SEEDS}
    for seed in SEEDS:
        runs=[r for r in train['runs'] if r['seed']==seed];assert len({r['schedule_sha256'] for r in runs})==1
        ref=json.loads((OLD/'training'/('proxy_natural_seed'+str(seed))/'summary.json').read_text());assert runs[0]['schedule_sha256']==ref['schedule_sha256']
        full=next(r for r in runs if r['variant']=='full21');assert full['full21_reproduction']=='EXACT_OLD_PROXY_NATURAL' and full['initialization_sha256']==ref['initialization_sha256']
    bounds_report=[]
    for r in train['runs']:
        assert r['integer_layer_mismatches']==[0,0,0];d=LOG/'training'/r['tag'];curve=json.loads((d/'summary.json').read_text())['curve']
        assert [x['epoch'] for x in curve if x['phase']=='warmup']==list(range(1,21))
        assert [x['epoch'] for x in curve if x['phase']=='qat']==list(range(1,61))
        bundle=qc.load_export(d/'epoch60/export');bounds(bundle);assert bundle['columns']==keep(r['variant'])
        assert bundle['layers'][0]['weight'].shape==(64,VARIANTS[r['variant']]['dim'])
        aa=[int((np.abs(l['bias'].astype(np.int64))+127*np.abs(l['weight'].astype(np.int64)).sum(1)).max()) for l in bundle['layers']]
        bounds_report.append(dict(tag=r['tag'],absolute_accumulator_bounds=aa,hidden_requant_product_bounds=[aa[i]*int(bundle['multipliers'][i]) for i in range(2)]))
    for name,h in train['source_sha256'].items():assert sha(ROOT/name)==h,name
    for name,h in pre['source_sha256'].items():assert sha(ROOT/name)==h,name
    metrics=readcsv(LOG/'evaluation/full_metrics.csv');m={(r['tag'],int(r['seed']),r['condition']):r for r in metrics};assert len(m)==6*3*13
    prediction_checks=0
    for c in PLAN['evaluation']['conditions']:
        labels=np.load(MECH/'raw'/c/'labels.npy') if c.startswith('sparse_') else np.load(MECH/'data/val/labels.npy')
        for t in ['A','B',*VARIANTS]:
            for s in SEEDS:
                pred=np.load(LOG/'evaluation'/(t+'_seed%d_%s_prediction.npy'%(s,c)))
                assert pred.shape==labels.shape and np.all((pred==0)|(pred==1))
                calc=pc.metrics(pc.cm(labels,pred));row=m[(t,s,c)]
                for k in ['accuracy','macro_f1']:assert abs(calc[k]-float(row[k]))<1e-12
                for cls in range(2):
                    assert abs(calc['recall'][cls]-float(row['recall_class'+str(cls)]))<1e-12
                    assert abs(calc['per_class_f1'][cls]-float(row['f1_class'+str(cls)]))<1e-12
                    for pcls in range(2):assert calc['confusion_matrix'][cls][pcls]==int(row['true%d_pred%d'%(cls,pcls)])
                prediction_checks+=1
    groups=readcsv(LOG/'evaluation/conditional_groups.csv');gi={(r['tag'],int(r['seed']),r['condition'],r['axis'],r['group']):r for r in groups}
    def metric(t,s,c):return float(m[(t,s,c)]['macro_f1'])
    def score(t,s):return previous.composite({c:metric(t,s,c) for c in PLAN['evaluation']['conditions']})
    rechecks=[]
    def group_failures(t,ref):
        bad=[]
        for r in groups:
            if r['tag']!=t or r['seed']!='7' or r['supported']!='True':continue
            c,a,g=r['condition'],r['axis'],r['group'];ds=[float(gi[(t,s,c,a,g)]['accuracy'])-float(gi[(ref,s,c,a,g)]['accuracy']) for s in SEEDS]
            if max(ds)<0 and sum(ds)/3<-.01-1e-12:bad.append((c,a,g))
        return bad
    for gate in e['ablation_gates']:
        t=gate['tag'];fail=[]
        for s in SEEDS:
            if metric(t,s,'clean')-metric('full21',s,'clean')<-.002-1e-12:fail.append('clean_seed'+str(s))
        for c in PLAN['evaluation']['conditions']:
            if sum(metric(t,s,c)-metric('full21',s,c) for s in SEEDS)/3<-.003-1e-12:fail.append(c+'_f1')
            for cls in range(2):
                d=sum(float(m[(t,s,c)]['recall_class'+str(cls)])-float(m[('full21',s,c)]['recall_class'+str(cls)]) for s in SEEDS)/3
                if d<-.005-1e-12:fail.append(c+'_recall'+str(cls))
        if sum(score(t,s)-score('full21',s) for s in SEEDS)/3<-.001-1e-12:fail.append('composite')
        bad=group_failures(t,'full21')
        if bad:fail.append('supported_group_regression')
        assert fail==gate['failures'];assert bad==[(r['condition'],r['axis'],r['group']) for r in gate['group_failures']]
        assert gate['accepted']==(not fail);rechecks.append(dict(tag=t,gate='ablation',failures=fail,group_failures=len(bad)))
    for gate in e['promotion_gates']:
        t=gate['tag'];fail=[]
        for s in SEEDS:
            if metric(t,s,'clean')-metric('A',s,'clean')<-.002-1e-12:fail.append('clean_seed'+str(s))
        for c in ['quarter_mean','central_half','sparse_single','sparse_context']:
            cs=['uniform_quarter_'+str(i) for i in range(3)] if c=='quarter_mean' else [c]
            if np.mean([metric(t,s,v)-metric('B',s,v) for s in SEEDS for v in cs])<-.003-1e-12:fail.append(c)
        bad=group_failures(t,'A')
        if bad:fail.append('supported_group_regression')
        gains=[score(t,s)-score('B',s) for s in SEEDS]
        if min(gains)<=0 or np.mean(gains)<.001-1e-12:fail.append('composite_gain')
        assert fail==gate['failures'] and len(bad)==len(gate['group_failures']) and gate['accepted']==(not fail)
        rechecks.append(dict(tag=t,gate='promotion',failures=fail,group_failures=len(bad)))
    passing=[g for g in e['ablation_gates'] if g['accepted']];passing.sort(key=lambda g:(g['dim'],-g['composite_mean'],g['tag']))
    assert e['decision']['conditional_subset']==(passing[0]['tag'] if passing else 'full21')
    if not any(g['accepted'] for g in e['promotion_gates']):assert e['decision']['main']=='A'
    assert len(p['checks'])==36 and p['complete_point_to_logit_rows']==3311016
    assert all(r['feature_mismatches']==r['logit_mismatches']==0 for r in p['checks'])
    assert len(e['duplicate_exact'])==39 and all(r['layer_mismatches']==[0,0,0] for r in e['duplicate_exact'])
    old=[]
    for name,date in [('mechanism_convergence','2026-09-16'),('moment_encoding','2026-09-16'),('conditional_protection','2026-09-16'),('representative_rtl','2026-09-17'),('software_convergence','2026-09-17'),('research_status','2026-09-17')]:
        path=ROOT/'docs/paper_new'/(name+'_'+date)/('delivery_manifest.json' if name=='research_status' else 'evidence_manifest.json');data=json.loads(path.read_text());entries=data.get('files',data);count=0
        for rel,value in entries.items():
            h=value.get('sha256') if isinstance(value,dict) else value
            if isinstance(h,str) and len(h)==64:
                if name=='research_status' and rel in ['docs/paper_new/README.md','docs/paper_new/00_project_requirements_and_memory.md']:
                    historical=subprocess.check_output(['git','show','152a4bf9cecdbee1120b9593f0e2d850dd18805b:'+rel],cwd=ROOT)
                    assert hashlib.sha256(historical).hexdigest()==h and (ROOT/rel).read_bytes().endswith(historical),rel
                else:assert sha(ROOT/rel)==h,rel
                count+=1
        old.append(dict(package=name,files=count,manifest_sha256=sha(path)))
    # Whole-sequence pairing and reported group fields independently reconstructible.
    assert len(e['sequence_names'])==27 and e['bootstrap_repetitions']==2000
    runtime=dict(preflight_seconds=pre['wall_seconds'],preparation_elapsed_from_preflight_start_to_training=(LOG/'training/source_manifest.json').stat().st_mtime-(LOG/'preflight.json').stat().st_mtime+pre['wall_seconds'],training_seconds=train['wall_seconds'],evaluation_seconds=e['wall_seconds'],package_seconds=p['wall_seconds'],output_bytes=size_guard())
    assert runtime['preparation_elapsed_from_preflight_start_to_training']<900 and runtime['training_seconds']<2400 and runtime['evaluation_seconds']+runtime['package_seconds']<1800
    backup=json.loads((LOG/'git_backup_before.json').read_text());head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();index=ROOT/'.git/index'
    assert head==backup['base_head'] and sha(index)==backup['original_index_sha256']
    dump(HERE/'validation.json',dict(status='PASS',decision=e['decision'],training_trajectories=12,prediction_metric_rechecks=prediction_checks,runtime=runtime,decision_rechecks=rechecks,previous_evidence=old,integer_bounds=bounds_report,source_manifest_verified=True,original_head_index_unchanged=True,single_executor_review=True,scope='Feature necessity within frozen proxy/natural coverage on reused development data; no independent generalization or hardware performance claim'))
    print(json.dumps(dict(status='PASS',decision=e['decision'],runtime=runtime)),flush=True)
if __name__=='__main__':main()
