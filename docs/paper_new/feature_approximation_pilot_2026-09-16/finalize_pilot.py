#!/usr/bin/env python3
"""Validate existing numeric outputs and mirror only readable pilot evidence."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOG=ROOT/'logs/feature_approximation_pilot_20260916'
VAULT=Path('/home/soooarr/obsidian')
REL=Path('项目/毕业论文——研究生/Chipyard论文知识库/论文写作/近似特征受控试验_2026-09-16')
LINK=re.compile(r'!?\[([^\]\n]+)\]\(([^)\n]+)\)')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def metrics(y,p):
    c=np.bincount(2*y+p,minlength=4).reshape(2,2)
    den=c.sum(0)+c.sum(1)
    f=np.divide(2*np.diag(c),den,out=np.zeros(2),where=den>0)
    return c,float(np.trace(c)/c.sum()),float(f.mean())


def target(src,url):
    raw=url.strip('<>').split('#',1)[0]
    if not raw or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',raw):return None
    return (src.parent/raw).resolve()


def main():
    plan=json.loads((HERE/'plan.json').read_text())
    smoke=json.loads((LOG/'smoke/summary.json').read_text())
    full=json.loads((LOG/'full/summary.json').read_text())
    train=json.loads((LOG/'training/summary.json').read_text())
    prep=json.loads((LOG/'train_subset/reconstruction_summary.json').read_text())
    assert smoke['status']=='SMOKE_PASS' and full['status']=='FIXED_MODEL_DIAGNOSTIC_COMPLETE'
    assert full['candidate_gate']['training_allowed'] and train['runs']==6
    assert train['selected_candidate']==full['candidate_gate']['selected']
    assert full['plan_sha256']==smoke['plan_sha256']==sha(HERE/'plan.json')
    source_checks=0
    for record in [smoke,full,train,prep,json.loads((LOG/'full/reconstruction_summary.json').read_text())]:
        for name,digest in record.get('source_sha256',{}).items():
            assert sha(ROOT/name)==digest, name
            source_checks+=1
    for phase in ['smoke','full','train_subset']:
        r=json.loads((LOG/phase/'reconstruction_summary.json').read_text())
        assert not any(r['checks'].values())
    assert full['samples']==80450 and full['sequences']==27 and prep['samples']==49255 and prep['sequences']==113
    assert smoke['integer_trace_crosscheck_samples']==full['integer_trace_crosscheck_samples']==64
    bounds={'smoke':600,'full':600,'train_subset':600,'training':900}
    times={'smoke':smoke['wall_seconds'],'full':full['wall_seconds'],'train_subset':prep['wall_seconds'],'training':train['wall_seconds']}
    for phase,elapsed in times.items():assert elapsed<bounds[phase]
    bytes_total=sum(p.stat().st_size for p in LOG.rglob('*') if p.is_file())
    assert bytes_total<plan['resources']['output_soft_limit_bytes']
    labels=np.load(LOG/'full/labels.npy');checked=0
    for mode,m in full['metrics'].items():
        prediction=np.load(LOG/'full'/(mode+'_logits.npy')).argmax(1)
        c,acc,f1=metrics(labels,prediction)
        assert c.tolist()==m['confusion_matrix'] and abs(acc-m['accuracy'])<1e-12 and abs(f1-m['macro_f1'])<1e-12
        checked+=1
    selected=train['selected_candidate'];names=['software_reference','deployment',selected]
    for seed in plan['training']['seeds']:
        initial=[]
        for mode in names:
            tag=mode+'_seed'+str(seed)
            r=json.loads((LOG/'training'/(tag+'.json')).read_text())
            assert len(r['training_curve'])==20
            initial.append(r['initialization_sha256'])
            p=np.load(LOG/'training'/(tag+'_val_logits.npy')).argmax(1)
            c,acc,f1=metrics(labels,p)
            assert c.tolist()==r['validation']['confusion_matrix'] and abs(f1-r['validation']['macro_f1'])<1e-12
            for name,digest in r['input_sha256'].items():assert sha(ROOT/name)==digest
            assert (LOG/'training'/(tag+'.pt')).is_file()
            checked+=1
        assert len(set(initial))==1
    sequence_sets=[]
    for phase in ['train_subset','full']:
        with gzip.open(LOG/phase/'metadata.csv.gz','rt') as f:
            sequence_sets.append({r['sequence_id'] for r in csv.DictReader(f)})
    assert not sequence_sets[0]&sequence_sets[1]
    links=0
    for src in HERE.glob('*.md'):
        for _,url in LINK.findall(src.read_text()):
            p=target(src,url)
            if p:
                assert p.exists(),(str(src),url);links+=1
    validation=dict(status='PASS',numeric_evaluations_recomputed=checked,source_hash_checks=source_checks,
        train_validation_sequence_overlap=0,stages_seconds=times,main_compute_wall_seconds=sum(times.values()),
        output_bytes=bytes_total,local_links_checked=links,trained_models=6,gpu_jobs=0,new_board_runs=0,
        scope='Local validation/representation pilot; no novelty certification, deployed QAT claim or hardware performance result.')
    (HERE/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
    excludes={'validation.json','obsidian_sync_manifest.json','evidence_manifest.json'}
    paths=[p for base in [HERE,LOG] for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in excludes]
    (HERE/'evidence_manifest.json').write_text(json.dumps(dict(scope='Pilot-only files; external source inputs separately hashed in phase summaries.',
        files={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)}),indent=2)+'\n')
    assert VAULT.is_dir();dest=VAULT/REL;dest.mkdir(parents=True,exist_ok=True)
    mapping={p.resolve():dest/p.relative_to(HERE) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='obsidian_sync_manifest.json'}
    evidence=[LOG/'smoke/summary.json',LOG/'full/summary.json',LOG/'full/reconstruction_summary.json',LOG/'full/group_metrics.csv',LOG/'full/sequence_metrics.csv',LOG/'train_subset/reconstruction_summary.json',LOG/'training/summary.json',LOG/'training/paired_sequence_metrics.csv']
    for p in evidence:mapping[p]=dest/'证据快照'/p.relative_to(LOG)
    oldsource=ROOT/'docs/paper_new/feature_approximation_research_2026-09-16/README.md'
    oldvault=VAULT/'项目/毕业论文——研究生/Chipyard论文知识库/论文写作/近似特征稳定性研究_2026-09-16/README.md'
    rows=[]
    for source,destination in sorted(mapping.items()):
        destination.parent.mkdir(parents=True,exist_ok=True)
        if source.suffix=='.md':
            def rewrite(m):
                label,url=m.groups();p=target(source,url)
                mapped=mapping.get(p)
                if p==oldsource and oldvault.exists():mapped=oldvault
                if mapped:
                    relative=mapped.relative_to(VAULT)
                    if relative.suffix=='.md':relative=relative.with_suffix('')
                    if m.group(0).startswith('!'):return '![['+str(relative)+']]'
                    return '[['+str(relative)+'|'+label+']]'
                if p and ROOT in p.parents:return label+'（仓库路径：`'+str(p.relative_to(ROOT))+'`）'
                return m.group(0)
            destination.write_text(LINK.sub(rewrite,source.read_text())+'\n\n仓库来源：`'+str(source.relative_to(ROOT))+'`；本地共享 vault 镜像，云同步未验证。\n')
        else:
            shutil.copyfile(source,destination);assert sha(source)==sha(destination)
        rows.append(dict(source=str(source.relative_to(ROOT)),source_sha256=sha(source),destination=str(destination.relative_to(VAULT)),destination_sha256=sha(destination)))
    marker='feature-approximation-pilot-20260916';start='<!-- '+marker+':start -->';end='<!-- '+marker+':end -->'
    block=start+'\n2026-09-16：[['+str(REL/'README')+'|近似特征受控试验]]。80,450 条 validation 固定模型诊断、49,255 条 train 子集六次匹配训练。固定模型修正 +0.4505 个 F1 百分点，重训后两 seed 为 -0.0892/+0.0180，区间跨零；预算内停止、暂缓硬件扩展。新训练为 FP32 表示对照，非部署 QAT/板测。\n'+end
    for relative in ['项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md','Codex/Chipyard/Chipyard Index.md']:
        p=VAULT/relative;body=p.read_text()
        if start in body:body=re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:block,body,flags=re.S)
        else:first,rest=body.split('\n',1);body=first+'\n\n'+block+'\n'+rest
        p.write_text(body)
    record=dict(status='LOCAL_VAULT_WRITTEN_AND_HASH_CHECKED',cloud_sync='NOT_VERIFIED',files=rows,destination=str(dest.resolve()))
    (HERE/'obsidian_sync_manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    shutil.copyfile(HERE/'obsidian_sync_manifest.json',dest/'obsidian_sync_manifest.json')
    print(json.dumps(dict(validation=validation,mirrored_files=len(rows)),ensure_ascii=False))


if __name__=='__main__':main()
