"""Independent saved-prediction/gate reconstruction and immutable-evidence audit."""
from dim_common import *

def main():
    t=json.loads((LOG/'training/summary.json').read_text());e=json.loads((LOG/'evaluation/summary.json').read_text());pkg=json.loads((LOG/'package/summary.json').read_text());prep=json.loads((LOG/'preparation.json').read_text());pre=json.loads((LOG/'training_preflight.json').read_text());sim=json.loads((LOG/'synthetic_preflight.json').read_text());finish=json.loads((LOG/'finishing_stage_times.json').read_text())
    assert all(x['status']=='PASS' for x in [t,e,pkg,prep,pre,sim,finish]);assert len(t['runs'])==33
    assert {(r['variant'],r['seed']) for r in t['runs']}=={(tag,s) for tag in VARIANTS for s in SEEDS}
    for path,h in t['source_sha256'].items():assert sha(ROOT/path)==h,path
    bounds=[]
    for s in SEEDS:
        runs=[r for r in t['runs'] if r['seed']==s];assert len({r['schedule_sha256'] for r in runs})==1
        old=json.loads((ENR/'training'/('base16_seed'+str(s))/'summary.json').read_text());assert runs[0]['schedule_sha256']==old['schedule_sha256']
    for r in t['runs']:
        assert r['integer_layer_mismatches']==[0,0,0];directory=LOG/'training'/r['tag'];curve=json.loads((directory/'summary.json').read_text())['curve']
        assert [r['epoch'] for r in curve if r['phase']=='warmup']==list(range(1,21)) and [r['epoch'] for r in curve if r['phase']=='qat']==list(range(1,61))
        bundle=qc.load_export(directory/'epoch60/export');ab.bounds(bundle);assert bundle['columns']==columns(r['variant']) and bundle['input_dim']==len(take(r['variant']))
        accum=[int((np.abs(layer['bias'].astype(np.int64))+127*np.abs(layer['weight'].astype(np.int64)).sum(1)).max()) for layer in bundle['layers']]
        bounds.append(dict(tag=r['tag'],accumulator_bounds=accum,requantization_bounds=[accum[i]*int(bundle['multipliers'][i]) for i in range(2)]))
    rows=readcsv(LOG/'evaluation/full_metrics.csv');m={(r['tag'],int(r['seed']),r['condition']):r for r in rows};assert len(m)==585
    for c in CONDITIONS:
        y=np.load(MECH/'raw'/c/'labels.npy') if c.startswith('sparse_') else np.load(MECH/'data/val/labels.npy')
        for tag in ['A','B']+REFERENCES+list(VARIANTS):
            for s in SEEDS:
                pred=np.load(LOG/'evaluation'/(tag+'_seed%d_%s_prediction.npy'%(s,c)));assert pred.shape==y.shape and np.all((pred==0)|(pred==1))
                expected=pc.metrics(pc.cm(y,pred));row=m[(tag,s,c)]
                for key in ['macro_f1','accuracy']:assert abs(expected[key]-float(row[key]))<1e-12
                for cls in [0,1]:
                    assert abs(expected['recall'][cls]-float(row['recall_class'+str(cls)]))<1e-12
                    assert abs(expected['per_class_f1'][cls]-float(row['f1_class'+str(cls)]))<1e-12
                    den=sum(expected['confusion_matrix'][truth][cls] for truth in [0,1]);precision=expected['confusion_matrix'][cls][cls]/den if den else 0.
                    assert abs(precision-float(row['precision_class'+str(cls)]))<1e-12
                    for p in [0,1]:assert expected['confusion_matrix'][cls][p]==int(row['true%d_pred%d'%(cls,p)])
                if tag in REFERENCES:assert np.array_equal(pred,np.load(ENR/'evaluation'/(tag+'_seed%d_%s_prediction.npy'%(s,c))))
    groups=readcsv(LOG/'evaluation/conditional_groups.csv');gi={(r['tag'],int(r['seed']),r['condition'],r['axis'],r['group']):r for r in groups}
    def metric(tag,s,c):return float(m[(tag,s,c)]['macro_f1'])
    def score(tag,s):return previous.composite({c:metric(tag,s,c) for c in CONDITIONS})
    def regressions(tag,reference):
        out=[]
        for r in groups:
            if r['tag']!=tag or r['seed']!='7' or r['supported']!='True':continue
            c,axis,name=r['condition'],r['axis'],r['group'];ds=[float(gi[(tag,s,c,axis,name)]['accuracy'])-float(gi[(reference,s,c,axis,name)]['accuracy']) for s in SEEDS]
            if max(ds)<0 and sum(ds)/3<-.01-1e-12:out.append((c,axis,name))
        return out
    decisions=[]
    for g in e['dimension_gates']:
        tag=g['tag'];fail=[];family=VARIANTS[tag]['family']
        for s in SEEDS:
            if metric(tag,s,'clean')-metric('combined23',s,'clean')<-.002-1e-12:fail.append('clean_seed'+str(s))
        for c in CONDITIONS:
            if np.mean([metric(tag,s,c)-metric('combined23',s,c) for s in SEEDS])<-.003-1e-12:fail.append(c+'_f1')
            for cls in [0,1]:
                if np.mean([float(m[(tag,s,c)]['recall_class'+str(cls)])-float(m[('combined23',s,c)]['recall_class'+str(cls)]) for s in SEEDS])<-.005-1e-12:fail.append(c+'_recall'+str(cls))
        bad=regressions(tag,'combined23')
        if bad:fail.append('supported_group_regression')
        ds=[score(tag,s)-score('combined23',s) for s in SEEDS]
        if family=='reduction':
            if np.mean(ds)<-.001-1e-12:fail.append('composite_loss')
        elif family!='redundant_control' and (np.mean(ds)<.001-1e-12 or min(ds)<=0):fail.append('minimum_composite_gain')
        if family=='quantile':
            for ref in ['support24']+(['redundant36'] if tag=='full36' else []):
                ds=[score(tag,s)-score(ref,s) for s in SEEDS]
                if np.mean(ds)<.001-1e-12 or min(ds)<=0:fail.append('gain_vs_'+ref)
        if family=='redundant_control':fail.append('control_only')
        assert g['failures']==fail and len(g['group_failures'])==len(bad) and g['accepted']==(not fail)
        decisions.append(dict(tag=tag,gate='dimension',failures=fail))
    for g in e['promotion_gates']:
        tag=g['tag'];fail=[]
        for s in SEEDS:
            if metric(tag,s,'clean')-metric('A',s,'clean')<-.002-1e-12:fail.append('clean_seed'+str(s))
        for c in ['quarter_mean','central_half','sparse_single','sparse_context']:
            cs=['uniform_quarter_'+str(i) for i in range(3)] if c=='quarter_mean' else [c]
            if np.mean([metric(tag,s,v)-metric('B',s,v) for s in SEEDS for v in cs])<-.003-1e-12:fail.append(c)
        bad=regressions(tag,'A')
        if bad:fail.append('supported_group_regression')
        ds=[score(tag,s)-score('B',s) for s in SEEDS]
        if min(ds)<=0 or np.mean(ds)<.001-1e-12:fail.append('composite_gain')
        assert g['failures']==fail and len(g['group_failures'])==len(bad) and g['accepted']==(not fail)
        decisions.append(dict(tag=tag,gate='promotion',failures=fail))
    # Remaining archive/provenance checks are defined below, separate from gates.
    complete_checks(t,e,pkg,prep,pre,sim,finish,m,score,bounds,decisions)

def complete_checks(t,e,pkg,prep,pre,sim,finish,m,score,bounds,decisions):
    candidates=[r['tag'] for r in e['dimension_gates'] if r['accepted']]+['combined23']
    def choose(tags):
        if not tags:return 'A'
        value={tag:sum(score(tag,s) for s in SEEDS)/3 for tag in tags};maximum=max(value.values());near=[tag for tag in tags if value[tag]>=maximum-.001-1e-12]
        def key(tag):
            c=costs(tag);return (c['channel_sorts']>0,c['extra_products_per_point'],c['network_macs'],c['ratio_quantizers'],-value[tag])
        return min(near,key=key)
    assert e['decision']['conditional']==choose(candidates)
    promoted={g['tag'] for g in e['promotion_gates'] if g['accepted']};assert e['decision']['main']==choose([tag for tag in candidates if tag in promoted])
    assert len(pkg['checks'])==99 and pkg['complete_point_to_logit_rows']==9105294 and all(r['feature_mismatches']==r['logit_mismatches']==0 for r in pkg['checks'])
    assert len(json.loads((LOG/'reference_replay.json').read_text())['checks'])==78
    assert (LOG/'native/features.c').read_text()==native_source()
    dependencies=json.loads((LOG/'explanation/information_dependencies.json').read_text());assert dependencies['status']=='PASS' and len(dependencies['checks'])>0
    ambiguity={r['tag']:r for r in readcsv(LOG/'explanation/train_input_ambiguity.csv')};assert len(ambiguity)==13
    for tag,a in ambiguity.items():
        assert int(a['observations'])==832362 and 0<=int(a['unavoidable_train_errors'])<=int(a['observations_in_conflicting_inputs'])//2
        for ref,b in ambiguity.items():
            if set(take(tag))>=set(take(ref)):assert int(a['distinct_encoded_inputs'])>=int(b['distinct_encoded_inputs']) and int(a['unavoidable_train_errors'])<=int(b['unavoidable_train_errors'])
    for r in json.loads((LOG/'package/reused_references.json').read_text()):
        for name,h in r['sha256'].items():assert sha(LOG/'package/frozen_references'/(r['tag']+'_seed'+str(r['seed']))/name)==h
    pointrows=json.loads((LOG/'explanation/exact_N_metrics.json').read_text());countchecks=0
    for c in ['clean','sparse_single','sparse_context']:
        raw=MECH/'raw/val' if c=='clean' else OLD/'data'/c;n=np.diff(np.load(raw/'offsets.npy'));y=np.load(MECH/'data/val/labels.npy') if c=='clean' else np.load(MECH/'raw'/c/'labels.npy')
        masks={'N1':n==1,'N2':n==2,'N3':n==3,'N4to8':(n>=4)&(n<=8),'Nge9':n>=9}
        for r in pointrows:
            if r['condition']!=c:continue
            pred=np.load(LOG/'evaluation'/(r['tag']+'_seed%d_%s_prediction.npy'%(r['seed'],c)));mask=masks[r['group']];expect=pc.metrics(pc.cm(y[mask],pred[mask]));assert expect['confusion_matrix']==r['confusion_matrix'];countchecks+=1
    protected=[]
    for name,date in [('mechanism_convergence','2026-09-16'),('moment_encoding','2026-09-16'),('conditional_protection','2026-09-16'),('representative_rtl','2026-09-17'),('software_convergence','2026-09-17'),('feature_ablation','2026-09-17'),('feature_enrichment','2026-09-17')]:
        manifest=ROOT/'docs/paper_new'/(name+'_'+date)/'evidence_manifest.json';entries=json.loads(manifest.read_text())['files']
        for rel,item in entries.items():assert sha(ROOT/rel)==(item['sha256'] if isinstance(item,dict) else item),rel
        protected.append(dict(package=name,files=len(entries),manifest_sha256=sha(manifest)))
    backup=json.loads((LOG/'git_backup_before.json').read_text());assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==backup['base_head'] and sha(ROOT/'.git/index')==backup['original_index_sha256']
    runtime=dict(preparation_seconds=prep['wall_seconds']+pre['seconds']+sim['seconds'],training_seconds=t['wall_seconds'],finishing_seconds=finish['wall_seconds'],output_bytes=size_guard());assert runtime['preparation_seconds']<1800 and runtime['training_seconds']<3600 and runtime['finishing_seconds']<1800
    dump(HERE/'validation.json',dict(status='PASS',decision=e['decision'],new_training_trajectories=33,reused_reference_models=6,metric_rechecks=len(m),raw_offset_low_N_rechecks=countchecks,decision_rechecks=decisions,integer_bounds=bounds,previous_evidence=protected,runtime=runtime,original_head_index_unchanged=True,single_executor_review=True,scope='Finite software development sweep, not universal dimension optimality, independent generalization or hardware gain'))
    print(json.dumps(dict(status='PASS',decision=e['decision'],runtime=runtime)),flush=True)
if __name__=='__main__':main()
