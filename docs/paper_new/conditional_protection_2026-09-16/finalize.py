"""Audit frozen experiment; then archive and mirror after the result Git snapshot."""
import argparse
import functools
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import zipfile
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/conditional_protection_20260916';MECH=ROOT/'logs/mechanism_convergence_20260916'
VAULT=Path('/home/soooarr/obsidian');REL=Path('项目/毕业论文——研究生/Chipyard论文知识库/论文写作/条件保护训练与设计账本_2026-09-16');DEST=VAULT/REL
LINK=re.compile(r'!?\[([^\]\n]+)\]\(([^)\n]+)\)')
def get(p):return json.loads(Path(p).read_text())
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
@functools.lru_cache(maxsize=None)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def target(src,url):
    raw=url.strip('<>').split('#',1)[0]
    if not raw or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',raw):return None
    return (src.parent/raw).resolve()
def audit():
    plan=get(HERE/'plan.json');t=get(LOG/'training/summary.json');e=get(LOG/'evaluation/summary.json');impl=get(LOG/'implementations/summary.json')
    checks=0
    for name in ['preflight.json','objective_mask_checks.json','training/summary.json','evaluation/summary.json','implementations/summary.json','execution_summary.json']:
        r=get(LOG/name);assert r['status']=='PASS'
        if 'plan_sha256' in r:assert r['plan_sha256']==sha(HERE/'plan.json')
        for path,digest in r.get('source_sha256',{}).items():assert sha(ROOT/path)==digest,path;checks+=1
    for path,digest in get(LOG/'training/source_manifest.json')['sha256'].items():assert sha(ROOT/path)==digest,path;checks+=1
    assert len(t['runs'])==6 and impl['complete_c_rows']==482700
    y=np.load(MECH/'data/val/labels.npy');numeric=0
    def metric(label,p,row):
        nonlocal numeric
        c=np.bincount(label.astype(np.int64)*2+p.astype(np.int64),minlength=4).reshape(2,2)
        f=2*np.diag(c)/(c.sum(0)+c.sum(1));assert c.tolist()==row['confusion_matrix'] and abs(f.mean()-row['macro_f1'])<1e-12
        assert abs(c.trace()/c.sum()-row['accuracy'])<1e-12;numeric+=1
    for run in t['runs']:
        d=LOG/'training'/(run['method']+'_seed'+str(run['seed']));r=get(d/'summary.json');assert r['integer_layer_mismatches']==[0,0,0] and r['fold_max_error']<1e-9
        old=get(MECH/'augmentation_v2'/('proxy_seed'+str(run['seed']))/'summary.json');assert r['initialization_sha256']==old['initialization_sha256']
        for phase,n in [('warmup',20),('qat',60)]:
            rs=[x for x in r['curve'] if x['phase']==phase];assert [x['epoch'] for x in rs]==list(range(1,n+1))
            assert all(x['student_examples']==357780 and x['optimizer_steps']==350 for x in rs)
        for row in r['curve']:
            if 'validation' in row:metric(y,np.load(d/('epoch'+str(row['epoch']))/'val_logits.npy').argmax(1),row['validation'])
    for kind in ['metrics','sparse_metrics']:
        for r in e[kind]:
            condition=r['condition'] if kind=='metrics' else r['view'];tag=r['method']+'_seed'+str(r['seed'])
            label=y if kind=='metrics' else np.load(MECH/'raw'/condition/'labels.npy')
            metric(label,np.load(LOG/'evaluation'/(tag+'_'+condition+'_prediction.npy')),r)
    for method in plan['training']['methods']:
        gates=[r for r in e['gates'] if r['method']==method];assert len(gates)==3
        assert e['method_accepted'][method]==all(not r['failures'] for r in gates)
    for r in e['gates']:assert r['accepted']==(not r['failures'])
    budgets=plan['budgets'];assert t['wall_seconds']<budgets['training_seconds'] and e['wall_seconds']<budgets['evaluation_seconds']
    assert get(LOG/'preflight.json')['wall_seconds']<budgets['preparation_seconds']
    size=sum(p.stat().st_size for p in LOG.rglob('*') if p.is_file());assert size<budgets['max_output_bytes']
    reserve=get(LOG/'reserve_audit.json');assert reserve['model_scoring_runs']==0 and all(r['target_track_points']==0 for r in reserve['unused_in_binary_manifest'])
    guards=[]
    for package in ['training_and_gemmini_retest_2026-09-15','gemmini_qmlp_comparison_2026-09-15']:
        p=ROOT/'docs/paper_new'/package/'protected_artifacts_before.json';f=get(p)['files'];entries=f.items() if isinstance(f,dict) else [(r['path'],r) for r in f]
        count=0
        for name,row in entries:assert sha(ROOT/name)==row['sha256'],name;count+=1
        guards.append(dict(package=package,unchanged=count))
    for package in ['feature_approximation_pilot','qmlp_int8_convergence','conditional_statistics','mechanism_convergence','moment_encoding']:
        p=ROOT/'docs/paper_new'/(package+'_2026-09-16')/'evidence_manifest.json';f=get(p)['files']
        for name,row in f.items():assert sha(ROOT/name)==row['sha256'],name
        guards.append(dict(package=package,unchanged=len(f)))
    contract=get(HERE/'research_contract.json');assert hashlib.sha256(contract['user_research_question'].encode()).hexdigest()==contract['question_sha256']
    with zipfile.ZipFile(HERE/'candidate_c_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('README.txt','Six host C functional candidates, all seeds retained. This does not mean the development acceptance gates passed. gcc -O2 -std=c99 candidate.c -o candidate ; ./candidate example.int16le . Input: 1..511 upstream GT-track/K7 points, four little-endian signed Q8.8 values x/y/compensated velocity/RCS per point. Teacher and groups are training-only. No RISC-V ELF or bitstream.\n')
        for r in t['runs']:
            tag=r['method']+'_seed'+str(r['seed'])
            for name in ['candidate.c','params.h','example.int16le','example.json']:z.write(LOG/'implementations'/tag/name,tag+'/'+name)
        for p in HERE.glob('*.md'):z.write(p,p.name)
        for name in ['plan.json','research_contract.json','results.csv']:z.write(HERE/name,name)
    generated={HERE/n for n in ['validation.json','evidence_manifest.json','obsidian_sync_manifest.json','backup_archive.json']}
    generated.add(LOG/'git_backup_after.json');links=0
    for p in HERE.glob('*.md'):
        for _,url in LINK.findall(p.read_text()):
            dest=target(p,url)
            if dest:assert dest.exists() or dest in generated,(p,url);links+=1
    validation=dict(status='PASS',trajectories=6,numeric_metrics_recomputed=numeric,source_hash_checks=checks,integer_complete_c_rows=482700,
        original_problem_sha256=contract['question_sha256'],old_artifact_guards=guards,method_accepted=e['method_accepted'],
        original_validation_sequences=27,no_new_historical_test_scoring=True,reserve_target_rows=0,output_bytes=size,local_markdown_links=links,
        gpu_jobs=0,new_rtl_jobs=0,new_board_jobs=0,scope='Execution and reproducibility PASS; method promotion separately follows predeclared gates. No independent test/hardware/novelty claim')
    dump(HERE/'validation.json',validation)
    excluded={'evidence_manifest.json','obsidian_sync_manifest.json','backup_archive.json','git_backup_after.json','git_payload_after.json','git_remote_retry_after.json'}
    paths=[p for base in [HERE,LOG] for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in excluded]
    dump(HERE/'evidence_manifest.json',dict(scope='Frozen experiment before result Git snapshot; post-commit backup receipts and sync/archive records explicitly excluded',excluded=sorted(excluded),
        files={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)}))
    print(json.dumps(validation,ensure_ascii=False),flush=True)
def archive_sync():
    v=get(HERE/'validation.json');assert v['status']=='PASS';post=get(LOG/'git_backup_after.json')
    for name,row in get(HERE/'evidence_manifest.json')['files'].items():assert sha(ROOT/name)==row['sha256'],name
    backup=Path('/home/soooarr/radar_thesis_backups_20260916');archive=backup/'conditional_protection_results.tar.gz';assert not archive.exists()
    with tarfile.open(archive,'w:gz') as tar:
        for base in [HERE,LOG]:
            for p in sorted(base.rglob('*')):
                if p.is_file() and '__pycache__' not in p.parts:tar.add(p,arcname=str(p.relative_to(ROOT)),recursive=False)
    with tarfile.open(archive) as tar:
        members={m.name:m for m in tar.getmembers()}
        for name,row in get(HERE/'evidence_manifest.json')['files'].items():
            assert hashlib.sha256(tar.extractfile(members[name]).read()).hexdigest()==row['sha256'],name
    assert VAULT.is_dir();DEST.mkdir(parents=True,exist_ok=True);backdest=DEST/'备份';backdest.mkdir(exist_ok=True)
    archives=[]
    for src in [archive,Path(post['bundle']),Path(get(LOG/'git_backup_before.json')['bundle'])]:
        dst=backdest/src.name;shutil.copyfile(src,dst);assert sha(src)==sha(dst)
        archives.append(dict(source=str(src),destination=str(dst.resolve()),bytes=src.stat().st_size,sha256=sha(src)))
    dump(HERE/'backup_archive.json',dict(status='LOCAL_ARCHIVES_AND_SHARED_VAULT_COPIES_HASH_VERIFIED',git_result_commit=post['commit'],remote_verified=post['push']['remote_verified'],
        cloud_sync='NOT_VERIFIED',scope='Results archive includes this experiment and source, not upstream raw dataset; incremental Git bundles require base HEAD recorded in receipts',archives=archives))
    mapping={p.resolve():DEST/p.relative_to(HERE) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='obsidian_sync_manifest.json'}
    snapshots=[LOG/n for n in ['preflight.json','objective_mask_checks.json','reserve_audit.json','training/summary.json','evaluation/summary.json','evaluation/conditional_groups.csv','evaluation/sparse_groups.csv','implementations/summary.json','execution_summary.json','git_backup_before.json','git_remote_retry_before.json','git_backup_after.json','git_payload_before.json','git_payload_after.json']]
    snapshots.extend((LOG/'training').glob('*/summary.json'))
    for p in snapshots:
        if p.exists():mapping[p.resolve()]=DEST/'证据快照'/p.relative_to(LOG)
    prior=ROOT/'docs/paper_new/mechanism_convergence_2026-09-16';extern={prior/name:VAULT/REL.parent/'机制收敛与条件稳健性_2026-09-16'/name for name in ['README.md','03_评审与收敛决定.md']}
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
            dst.write_text(LINK.sub(rewrite,src.read_text())+'\n\n仓库来源：`'+str(src.relative_to(ROOT))+'`；共享 vault 本地镜像，云端同步未验证。\n')
        else:shutil.copyfile(src,dst);assert sha(src)==sha(dst)
        rows.append(dict(source=str(src.relative_to(ROOT)),source_sha256=sha(src),destination=str(dst.relative_to(VAULT)),destination_sha256=sha(dst)))
    marker='conditional-protection-20260916';start='<!-- '+marker+':start -->';end='<!-- '+marker+':end -->'
    block=start+'\n2026-09-16 最新接续：[['+str(REL/'README')+'|条件保护训练与设计账本]]。两种方法×三 seed 完成；判断以预设全部门槛为准。[['+str(REL/'00_设计账本与主线')+'|原问题与设计思想]]和运行前/结果后 Git 快照分别保留，不能将熟悉 validation 或已有训练技巧改写为独立测试/原创方法。\n'+end
    for name in ['项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md','Codex/Chipyard/Chipyard Index.md']:
        p=VAULT/name;body=p.read_text()
        if start in body:body=re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:block,body,flags=re.S)
        else:first,rest=body.split('\n',1);body=first+'\n\n'+block+'\n'+rest
        p.write_text(body)
    dump(HERE/'obsidian_sync_manifest.json',dict(status='LOCAL_VAULT_WRITTEN_AND_HASH_VERIFIED',cloud_sync='NOT_VERIFIED',files=rows,archives=archives))
    shutil.copyfile(HERE/'obsidian_sync_manifest.json',DEST/'obsidian_sync_manifest.json')
    print(json.dumps(dict(mirrored_files=len(rows),archives=len(archives),result_commit=post['commit'],remote_verified=post['push']['remote_verified']),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['audit','archive_sync'],required=True);a=p.parse_args()
    audit() if a.stage=='audit' else archive_sync()
