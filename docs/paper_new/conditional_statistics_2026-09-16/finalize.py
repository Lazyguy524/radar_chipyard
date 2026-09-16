"""Audit frozen results, protect historical artifacts, package and mirror notes."""
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/conditional_statistics_20260916'
VAULT=Path('/home/soooarr/obsidian');REL=Path('项目/毕业论文——研究生/Chipyard论文知识库/论文写作/点数形态条件统计研究_2026-09-16')
LINK=re.compile(r'!?\[([^\]\n]+)\]\(([^)\n]+)\)')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def get(p):return json.loads(Path(p).read_text())
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def target(src,url):
    raw=url.strip('<>').split('#',1)[0]
    if not raw or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',raw):return None
    return (src.parent/raw).resolve()
def main():
    plan=get(HERE/'plan.json');hash_checks=0
    records=[LOG/r for r in ['preflight.json','data/summary.json','training/summary.json','evaluation/summary.json','rf/summary.json','shared/summary.json','attribution/summary.json','inference/summary.json']]
    for p in records:
        r=get(p);assert r['status'] in ['PASS','SIX_MATCHED_TRAJECTORIES_COMPLETE']
        if 'plan_sha256' in r:assert r['plan_sha256']==sha(HERE/'plan.json')
        for name,digest in r.get('source_sha256',{}).items():assert sha(ROOT/name)==digest,name;hash_checks+=1
    for name,digest in get(LOG/'pre_training_manifest.json')['sha256'].items():assert sha(ROOT/name)==digest,name;hash_checks+=1
    t=get(LOG/'training/summary.json');e=get(LOG/'evaluation/summary.json');d=get(LOG/'data/summary.json')
    assert len(t['runs'])==6 and d['filter_eligible_matches_manifest']
    assert d['splits']['train']['samples']==357780 and d['splits']['val']['samples']==80450
    assert d['diagnostic_samples']==3448 and all(v['legacy_feature_mismatches']==0 for v in d['splits'].values())
    qc_plan=get(ROOT/'docs/paper_new/qmlp_int8_convergence_2026-09-16/plan.json')
    stops=[]
    for r in t['runs']:
        report=get(LOG/'training'/(r['mode']+'_seed'+str(r['seed']))/'summary.json')
        curve=[v for v in report['curve'] if v['phase']=='qat'];values=[v['train_probe_ce'] for v in curve]
        w=qc_plan['plateau']['window_epochs'];streak=0;stop=None
        for end in range(qc_plan['training']['qat_min_epochs'],len(values)+1):
            a=np.mean(values[end-2*w:end-w]);b=np.mean(values[end-w:end])
            tolerance=max(qc_plan['plateau']['absolute_loss_change_tolerance'],qc_plan['plateau']['relative_loss_change_tolerance']*abs(a))
            streak=streak+1 if abs(a-b)<=tolerance else 0
            if streak>=qc_plan['plateau']['consecutive_checks']:stop=end;break
        assert report['train_loss_plateau']==(stop is not None)
        assert len(values)==(stop if stop is not None else qc_plan['training']['qat_max_epochs'])
        stops.append(dict(mode=r['mode'],seed=r['seed'],epochs=len(values),plateau=stop is not None))
    numeric=0;y=np.load(LOG/'data/val/labels.npy');dy=np.load(LOG/'data/diagnostic/labels.npy')
    def check(label,logits,result):
        nonlocal numeric
        p=np.load(logits).argmax(1);cm=np.bincount(label*2+p,minlength=4).reshape(2,2)
        f=(2*np.diag(cm)/(cm.sum(0)+cm.sum(1))).mean()
        assert cm.tolist()==result['confusion_matrix'] and abs(f-result['macro_f1'])<1e-12;numeric+=1
    for tag,result in e['full_metrics'].items():
        file=(ROOT/'logs/qmlp_int8_convergence_20260916/training'/tag.replace('legacy_','')/'final_val_logits.npy') if tag.startswith('legacy_') else LOG/'evaluation'/(tag+'_c_full_logits.npy')
        check(y,file,result)
    for r in e['condition_metrics']:check(dy,LOG/'evaluation'/(r['mode']+'_seed'+str(r['seed'])+'_'+r['condition']+'_logits.npy'),r)
    assert len(e['integer_checks'])==6 and all(r['layer_mismatches']==[0,0,0] for r in e['integer_checks'])
    assert all(not r['accepted_within_predeclared_development_tolerances'] for r in e['precision_acceptance'])
    assert get(LOG/'shared/summary.json')['integer_frontend_equivalence_cases']==51720
    assert sum(r['complete_c_rows'] for r in get(LOG/'inference/summary.json')['checks'])==20688
    stages=dict(prepare=d['wall_seconds'],training=t['wall_seconds'],evaluation=e['wall_seconds'],rf=get(LOG/'rf/summary.json')['wall_seconds'])
    for stage,time in stages.items():assert time<plan['budget'][stage+'_seconds']
    size=sum(p.stat().st_size for p in LOG.rglob('*') if p.is_file());assert size<plan['budget']['max_output_bytes']
    guards=[]
    for name in ['training_and_gemmini_retest_2026-09-15','gemmini_qmlp_comparison_2026-09-15']:
        p=ROOT/'docs/paper_new'/name/'protected_artifacts_before.json';files=get(p)['files']
        entries=files.items() if isinstance(files,dict) else [(r['path'],r) for r in files]
        count=0
        for name,r in entries:assert sha(ROOT/name)==r['sha256'],name;count+=1
        guards.append(dict(manifest=str(p.relative_to(ROOT)),unchanged=count))
    old=[]
    for name in ['feature_approximation_pilot_2026-09-16','qmlp_int8_convergence_2026-09-16']:
        p=ROOT/'docs/paper_new'/name/'evidence_manifest.json';files=get(p)['files']
        for name,r in files.items():assert sha(ROOT/name)==r['sha256'],name
        old.append(dict(manifest=str(p.relative_to(ROOT)),unchanged=len(files)))
    bundle=HERE/'candidate_c_bundle.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('README.txt','Host C candidates, no bitstream/ELF. Six configurations are preserved, no best-seed release selection. In each mode_seed directory: gcc -O2 -std=c99 candidate.c -o candidate ; ./candidate example.int16le . Input is one upstream K7-fused GT-track cluster, 1..511 points, four signed Q8.8 values per point in little endian x/y/compensated velocity/RCS order. See Chinese documents for development-validation and dataset coverage limits.\n')
        for r in t['runs']:
            tag=r['mode']+'_seed'+str(r['seed']);base=LOG/'inference'/tag
            for name in ['candidate.c','params.h','example.int16le','example.json']:z.write(base/name,tag+'/'+name)
        for name in ['README.md','01_算法与实现.md','02_结果与归因.md','03_评审与下一步门槛.md','plan.json','results.csv']:z.write(HERE/name,name)
        z.write(LOG/'data/output_scale_exponents.json','output_scale_exponents.json')
        z.write(LOG/'shared/cost_graph.json','cost_graph.json')
    links=0;generated={HERE/n for n in ['validation.json','evidence_manifest.json','obsidian_sync_manifest.json']}
    for src in HERE.glob('*.md'):
        for _,url in LINK.findall(src.read_text()):
            p=target(src,url)
            if p:assert p.exists() or p in generated,(src,url);links+=1
    validation=dict(status='PASS',source_hash_checks=hash_checks,numeric_metrics_recomputed=numeric,
        stopped_trajectories=stops,precision_retraining_decision='REJECTED_BOTH_SEEDS_AS_PLANNED',
        protected_artifacts=guards,previous_research_packages=old,local_markdown_links=links,stages_seconds=stages,output_bytes=size,
        single_pass_frontend_cases=51720,complete_c_inference_cases=20688,new_rtl_jobs=0,gpu_jobs=0,new_board_runs=0,
        scope='PASS means reproducible bounded execution and artifact checks, not acceptance of every hypothesis or final hardware quality-cost advantage')
    dump(HERE/'validation.json',validation)
    excluded={'evidence_manifest.json','obsidian_sync_manifest.json'}
    paths=[p for base in [HERE,LOG] for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in excluded]
    dump(HERE/'evidence_manifest.json',dict(scope='Isolated conditional-statistics research outputs; external inputs also hashed in stage records',files={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)}))
    assert VAULT.is_dir();dest=VAULT/REL;dest.mkdir(parents=True,exist_ok=True)
    mapping={p.resolve():dest/p.relative_to(HERE) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='obsidian_sync_manifest.json'}
    snapshots=records+[LOG/'pre_training_manifest.json',LOG/'data/output_scale_exponents.json',LOG/'data/filter_observations.csv',LOG/'data/filter_overview.csv',LOG/'evaluation/conditional_groups.csv',LOG/'shared/cost_graph.json']
    for r in t['runs']:snapshots.append(LOG/'training'/(r['mode']+'_seed'+str(r['seed']))/'summary.json')
    for p in snapshots:mapping[p.resolve()]=dest/'证据快照'/p.relative_to(LOG)
    extern={}
    for name,vault_name in [('feature_approximation_pilot_2026-09-16','近似特征受控试验_2026-09-16'),('qmlp_int8_convergence_2026-09-16','冻结INT8训练与收敛_2026-09-16')]:
        extern[ROOT/'docs/paper_new'/name/'README.md']=VAULT/REL.parent/vault_name/'README.md'
    rows=[]
    for src,dst in sorted(mapping.items()):
        dst.parent.mkdir(parents=True,exist_ok=True)
        if src.suffix=='.md':
            def rewrite(m):
                label,url=m.groups();p=target(src,url);to=mapping.get(p,extern.get(p))
                if to:
                    name=to.relative_to(VAULT)
                    if name.suffix=='.md':name=name.with_suffix('')
                    return '![[%s]]'%name if m.group(0).startswith('!') else '[[%s|%s]]'%(name,label)
                if p and ROOT in p.parents:return label+'（仓库路径：`'+str(p.relative_to(ROOT))+'`）'
                return m.group(0)
            dst.write_text(LINK.sub(rewrite,src.read_text())+'\n\n仓库来源：`'+str(src.relative_to(ROOT))+'`；本地共享 vault 镜像，云端同步未验证。\n')
        else:shutil.copyfile(src,dst);assert sha(src)==sha(dst)
        rows.append(dict(source=str(src.relative_to(ROOT)),source_sha256=sha(src),destination=str(dst.relative_to(VAULT)),destination_sha256=sha(dst)))
    marker='conditional-statistics-20260916';start='<!-- '+marker+':start -->';end='<!-- '+marker+':end -->'
    block=start+'\n2026-09-16 当前算法入口：[['+str(REL/'README')+'|点数、形态、统计精度与共享计算]]。原主线保持为“条件分类稳定性与可验证质量—成本取舍”，RF/删维/训练/RTL 均为支撑。完成六条受控训练、五条件配对、两个固定 RF、原始过滤审计及完整 C 候选。输出定标为强基线；矩统计只有条件性线索，Q16 重训未过门槛；不宣称最终硬件优势。后续优先读[['+str(REL/'03_评审与下一步门槛')+'|阶段评审]]，此前“先做森林筛选”的临时顺序以本次复核为准。\n'+end
    for rel in ['项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md','Codex/Chipyard/Chipyard Index.md']:
        p=VAULT/rel;body=p.read_text()
        if start in body:body=re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:block,body,flags=re.S)
        else:first,rest=body.split('\n',1);body=first+'\n\n'+block+'\n'+rest
        p.write_text(body)
    record=dict(status='LOCAL_VAULT_WRITTEN_AND_HASH_CHECKED',cloud_sync='NOT_VERIFIED',destination=str(dest.resolve()),files=rows)
    dump(HERE/'obsidian_sync_manifest.json',record);shutil.copyfile(HERE/'obsidian_sync_manifest.json',dest/'obsidian_sync_manifest.json')
    print(json.dumps(dict(validation=validation,evidence_files=len(paths),mirrored_files=len(rows)),ensure_ascii=False))

if __name__=='__main__':main()
