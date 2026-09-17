"""Independent table/prediction reconstruction and provenance verification."""
from ex_common import *

def main():
    train=json.loads((LOG/'training/summary.json').read_text());e=json.loads((LOG/'evaluation/summary.json').read_text());pkg=json.loads((LOG/'package/summary.json').read_text());prep=json.loads((LOG/'preparation.json').read_text());pre=json.loads((LOG/'training_preflight.json').read_text());sim=json.loads((LOG/'synthetic_preflight.json').read_text())
    assert all(x['status']=='PASS' for x in [train,e,pkg,prep,pre,sim]);assert len(train['runs'])==15
    assert {(r['variant'],r['seed']) for r in train['runs']}=={(t,s) for t in VARIANTS for s in SEEDS}
    for name,h in train['source_sha256'].items():assert sha(ROOT/name)==h,name
    adjust=json.loads((LOG/'source_manifest_scope_adjustment.json').read_text());assert sha(LOG/'train_source_at_preflight.py')==adjust['preflight_train_source_sha256'] and sha(HERE/'train.py')==adjust['actual_train_source_sha256']
    bounds=[]
    for seed in SEEDS:
        runs=[r for r in train['runs'] if r['seed']==seed];assert len({r['schedule_sha256'] for r in runs})==1
        original=json.loads((ABL/'training'/('less_shape16_seed'+str(seed))/'summary.json').read_text());control=next(r for r in runs if r['variant']=='base16')
        assert control['schedule_sha256']==original['schedule_sha256'] and control['initialization_sha256']==original['initialization_sha256'] and control['base16_reproduction']=='EXACT_PREVIOUS_LESS_SHAPE16'
    for r in train['runs']:
        assert r['integer_layer_mismatches']==[0,0,0];d=LOG/'training'/r['tag'];curve=json.loads((d/'summary.json').read_text())['curve']
        assert [v['epoch'] for v in curve if v['phase']=='warmup']==list(range(1,21)) and [v['epoch'] for v in curve if v['phase']=='qat']==list(range(1,61))
        b=qc.load_export(d/'epoch60/export');ab.bounds(b);assert b['columns']==columns(r['variant']);assert b['input_dim']==VARIANTS[r['variant']]['dim'];assert b['layers'][0]['weight'].shape==(64,b['input_dim'])
        a=[int((np.abs(l['bias'].astype(np.int64))+127*np.abs(l['weight'].astype(np.int64)).sum(1)).max()) for l in b['layers']]
        bounds.append(dict(tag=r['tag'],absolute_accumulator_bounds=a,requant_product_bounds=[a[i]*int(b['multipliers'][i]) for i in range(2)]))
    metrics=readcsv(LOG/'evaluation/full_metrics.csv');m={(r['tag'],int(r['seed']),r['condition']):r for r in metrics};assert len(m)==7*3*13
    for c in PLAN['evaluation']['conditions']:
        labels=np.load(MECH/'raw'/c/'labels.npy') if c.startswith('sparse_') else np.load(MECH/'data/val/labels.npy')
        for tag in ['A','B',*VARIANTS]:
            for s in SEEDS:
                prediction=np.load(LOG/'evaluation'/(tag+'_seed%d_%s_prediction.npy'%(s,c)));assert prediction.shape==labels.shape and np.all((prediction==0)|(prediction==1))
                v=pc.metrics(pc.cm(labels,prediction));row=m[(tag,s,c)]
                for key in ['macro_f1','accuracy']:assert abs(v[key]-float(row[key]))<1e-12
                for cls in range(2):
                    for key in ['recall','f1']:assert abs(v['recall' if key=='recall' else 'per_class_f1'][cls]-float(row[key+'_class'+str(cls)]))<1e-12
                    for j in range(2):assert v['confusion_matrix'][cls][j]==int(row['true%d_pred%d'%(cls,j)])
    gr=readcsv(LOG/'evaluation/conditional_groups.csv');gi={(r['tag'],int(r['seed']),r['condition'],r['axis'],r['group']):r for r in gr}
    def metric(t,s,c):return float(m[(t,s,c)]['macro_f1'])
    def score(t,s):return previous.composite({c:metric(t,s,c) for c in PLAN['evaluation']['conditions']})
    def badgroups(t,ref):
        bad=[]
        for r in gr:
            if r['tag']!=t or r['seed']!='7' or r['supported']!='True':continue
            c,a,g=r['condition'],r['axis'],r['group'];ds=[float(gi[(t,s,c,a,g)]['accuracy'])-float(gi[(ref,s,c,a,g)]['accuracy']) for s in SEEDS]
            if max(ds)<0 and sum(ds)/3<-.01-1e-12:bad.append((c,a,g))
        return bad
    recheck=[]
    for g in e['enrichment_gates']:
        t=g['tag'];fail=[]
        for s in SEEDS:
            if metric(t,s,'clean')-metric('base16',s,'clean')<-.002-1e-12:fail.append('clean_seed'+str(s))
        for c in PLAN['evaluation']['conditions']:
            if np.mean([metric(t,s,c)-metric('base16',s,c) for s in SEEDS])<-.003-1e-12:fail.append(c+'_f1')
            for cls in range(2):
                if np.mean([float(m[(t,s,c)]['recall_class'+str(cls)])-float(m[('base16',s,c)]['recall_class'+str(cls)]) for s in SEEDS])<-.005-1e-12:fail.append(c+'_recall'+str(cls))
        delta=[score(t,s)-score('base16',s) for s in SEEDS]
        if min(delta)<=0 or np.mean(delta)<.001-1e-12:fail.append('minimum_composite_gain')
        groups=badgroups(t,'base16')
        if groups:fail.append('supported_group_regression')
        if t=='combined23':
            delta=[score(t,s)-score('redundant23',s) for s in SEEDS]
            if min(delta)<=0 or np.mean(delta)<.001-1e-12:fail.append('same_dimension_control')
        assert fail==g['failures'] and len(groups)==len(g['group_failures']) and g['accepted']==(not fail)
        recheck.append(dict(tag=t,gate='enrichment',failures=fail,group_failures=len(groups)))
    for g in e['promotion_gates']:
        t=g['tag'];fail=[]
        for s in SEEDS:
            if metric(t,s,'clean')-metric('A',s,'clean')<-.002-1e-12:fail.append('clean_seed'+str(s))
        for c in ['quarter_mean','central_half','sparse_single','sparse_context']:
            cs=['uniform_quarter_'+str(i) for i in range(3)] if c=='quarter_mean' else [c]
            if np.mean([metric(t,s,v)-metric('B',s,v) for s in SEEDS for v in cs])<-.003-1e-12:fail.append(c)
        bad=badgroups(t,'A')
        if bad:fail.append('supported_group_regression')
        ds=[score(t,s)-score('B',s) for s in SEEDS]
        if min(ds)<=0 or np.mean(ds)<.001-1e-12:fail.append('composite_gain')
        assert fail==g['failures'] and len(bad)==len(g['group_failures']) and g['accepted']==(not fail);recheck.append(dict(tag=t,gate='promotion',failures=fail,group_failures=len(bad)))
    def choose(candidates,fallback):
        if not candidates:return fallback
        highest=max(g['composite_mean'] for g in candidates);near=[g for g in candidates if g['composite_mean']>=highest-.001-1e-12];near.sort(key=lambda g:({'geometry19':3,'distribution20':2,'combined23':5}[g['tag']],VARIANTS[g['tag']]['dim'],-g['composite_mean']));return near[0]['tag']
    ok=[g for g in e['enrichment_gates'] if g['accepted']];assert e['decision']['conditional']==choose(ok,'base16')
    promoted={g['tag'] for g in e['promotion_gates'] if g['accepted']};assert e['decision']['main']==choose([g for g in ok if g['tag'] in promoted],'A')
    assert len(pkg['checks'])==45 and pkg['complete_point_to_logit_rows']==4138770 and all(r['feature_mismatches']==r['logit_mismatches']==0 for r in pkg['checks'])
    explanation=json.loads((LOG/'explanation/summary.json').read_text());assert explanation['status']=='PASS'
    pointrows=json.loads((LOG/'explanation/performance_by_exact_low_N.json').read_text());pointchecks=0
    for c in ['clean','sparse_single','sparse_context']:
        raw=MECH/'raw/val' if c=='clean' else OLD/'data'/c
        counts=np.diff(np.load(raw/'offsets.npy'))
        labels=np.load(MECH/'data/val/labels.npy') if c=='clean' else np.load(MECH/'raw'/c/'labels.npy')
        for r in pointrows:
            if r['condition']!=c:continue
            mask={'N1':counts==1,'N2':counts==2,'Nge3':counts>=3}[r['retained_point_group']]
            pred=np.load(LOG/'evaluation'/(r['tag']+'_seed%d_%s_prediction.npy'%(r['seed'],c)))
            expected=pc.metrics(pc.cm(labels[mask],pred[mask]))
            assert expected['confusion_matrix']==r['confusion_matrix'] and abs(expected['macro_f1']-r['macro_f1'])<1e-12
            pointchecks+=1
    mc=json.loads((LOG/'explanation/point_count_simulation.json').read_text());assert mc['status']=='PASS' and len(mc['rows'])==24
    for r in mc['rows']:
        if r['points']==1:assert r['mean']==0 and r['zero_span']==2000
        if r['points']==2:assert abs(r['mean']-(2000-r['zero_span'])/2000)<1e-12
    protected=[]
    for name,date in [('mechanism_convergence','2026-09-16'),('moment_encoding','2026-09-16'),('conditional_protection','2026-09-16'),('representative_rtl','2026-09-17'),('software_convergence','2026-09-17'),('feature_ablation','2026-09-17')]:
        manifest=ROOT/'docs/paper_new'/(name+'_'+date)/'evidence_manifest.json';data=json.loads(manifest.read_text())['files']
        for rel,item in data.items():assert sha(ROOT/rel)==(item['sha256'] if isinstance(item,dict) else item),rel
        protected.append(dict(package=name,files=len(data),manifest_sha256=sha(manifest)))
    backup=json.loads((LOG/'git_backup_before.json').read_text());assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==backup['base_head'] and sha(ROOT/'.git/index')==backup['original_index_sha256']
    finishing=json.loads((LOG/'finishing_stage_times.json').read_text());assert finishing['status']=='PASS'
    runtime=dict(preparation_seconds=prep['wall_seconds']+sim['seconds'],training_seconds=train['wall_seconds'],evaluation_seconds=e['wall_seconds'],package_seconds=pkg['wall_seconds'],full_finishing_seconds=finishing['wall_seconds'],output_bytes=size_guard());assert runtime['preparation_seconds']<1800 and runtime['training_seconds']<2400 and runtime['full_finishing_seconds']<1800
    dump(HERE/'validation.json',dict(status='PASS',decision=e['decision'],training_trajectories=15,prediction_metric_rechecks=len(m),low_point_checks_from_raw_offsets=pointchecks,decision_rechecks=recheck,integer_bounds=bounds,previous_evidence=protected,runtime=runtime,original_head_index_unchanged=True,single_executor_review=True,scope='Bounded interpretable enrichment on reused development data; independent generalization and hardware cost remain unverified'))
    print(json.dumps(dict(status='PASS',decision=e['decision'],runtime=runtime)),flush=True)
if __name__=='__main__':main()
