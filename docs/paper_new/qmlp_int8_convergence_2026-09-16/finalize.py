"""Check frozen evidence and mirror this isolated result to the local vault."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOG=ROOT/'logs/qmlp_int8_convergence_20260916'
VAULT=Path('/home/soooarr/obsidian')
REL=Path('项目/毕业论文——研究生/Chipyard论文知识库/论文写作/冻结INT8训练与收敛_2026-09-16')
LINK=re.compile(r'!?\[([^\]\n]+)\]\(([^)\n]+)\)')

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
def target(src,url):
    raw=url.strip('<>').split('#',1)[0]
    if not raw or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',raw):return None
    return (src.parent/raw).resolve()

def main():
    plan=json.loads((HERE/'plan.json').read_text());source_checks=0
    records=[LOG/'preflight.json',LOG/'train/summary.json',LOG/'training/summary.json',LOG/'verification/summary.json']
    for path in records:
        r=json.loads(path.read_text())
        assert r['status'] in ['PASS','TWO_SEED_TRAINING_COMPLETE']
        if 'plan_sha256' in r:assert sha(HERE/'plan.json')==r['plan_sha256']
        for name,digest in r.get('source_sha256',{}).items():assert sha(ROOT/name)==digest,name;source_checks+=1
    frozen=json.loads((LOG/'pre_training_source_manifest.json').read_text())
    for name,digest in frozen['sha256'].items():assert sha(ROOT/name)==digest,name;source_checks+=1
    training=json.loads((LOG/'training/summary.json').read_text());verify=json.loads((LOG/'verification/summary.json').read_text())
    prep=json.loads((LOG/'train/summary.json').read_text());assert not any(prep['checks'].values())
    assert json.loads((LOG/'cli_smoke/summary.json').read_text())['status']=='PASS'
    assert training['train_rows']==357780 and training['validation_rows']==80450
    labels=np.load(ROOT/'logs/feature_approximation_pilot_20260916/full/labels.npy');numeric=0
    for r in training['runs']:
        base=LOG/'training'/f"seed{r['seed']}";summary=json.loads((base/'summary.json').read_text())
        for prefix,key in [('warmup','warmup_validation'),('ptq','ptq_validation'),('final','qat_validation')]:
            prediction=np.load(base/(prefix+'_val_logits.npy')).argmax(1)
            cm=np.bincount(labels*2+prediction,minlength=4).reshape(2,2)
            f1=(2*np.diag(cm)/(cm.sum(0)+cm.sum(1))).mean()
            assert cm.tolist()==summary[key]['confusion_matrix'] and abs(f1-summary[key]['macro_f1'])<1e-12
            numeric+=1
        curve=[c for c in summary['curve'] if c['phase']=='qat'];values=[c['train_probe_ce'] for c in curve]
        w=plan['plateau']['window_epochs'];streak=0;first_stop=None
        for end in range(plan['training']['qat_min_epochs'],len(values)+1):
            old=np.mean(values[end-2*w:end-w]);new=np.mean(values[end-w:end])
            tolerance=max(plan['plateau']['absolute_loss_change_tolerance'],plan['plateau']['relative_loss_change_tolerance']*abs(old))
            streak=streak+1 if abs(new-old)<=tolerance else 0
            if streak>=plan['plateau']['consecutive_checks']:first_stop=end;break
        assert summary['train_loss_plateau']==(first_stop is not None)
        assert len(values)==(first_stop if first_stop is not None else plan['training']['qat_max_epochs'])
        span=max(c['validation_macro_f1'] for c in curve[-5:])-min(c['validation_macro_f1'] for c in curve[-5:])
        assert abs(span-summary['last_five_validation_f1_span'])<1e-12
    assert len(training['runs'])==2
    times=dict(prepare=prep['wall_seconds'],training=training['wall_seconds'],verification=verify['wall_seconds'])
    for stage,seconds in times.items():assert seconds<plan['budgets'][stage+'_timeout_seconds']
    size=sum(p.stat().st_size for p in LOG.rglob('*') if p.is_file());assert size<plan['budgets']['output_soft_limit_bytes']
    guards=[]
    for name in ['training_and_gemmini_retest_2026-09-15','gemmini_qmlp_comparison_2026-09-15']:
        path=ROOT/'docs/paper_new'/name/'protected_artifacts_before.json';files=json.loads(path.read_text())['files']
        entries=files.items() if isinstance(files,dict) else [(r['path'],r) for r in files]
        count=0
        for rel,info in entries:assert sha(ROOT/rel)==info['sha256'],rel;count+=1
        guards.append(dict(snapshot=str(path.relative_to(ROOT)),files_unchanged=count))
    old_manifest=ROOT/'docs/paper_new/feature_approximation_pilot_2026-09-16/evidence_manifest.json'
    previous=json.loads(old_manifest.read_text())['files']
    for rel,info in previous.items():assert sha(ROOT/rel)==info['sha256'],rel
    links=0
    # validation.json is produced below; the README reference is intentional.
    for src in HERE.glob('*.md'):
        for _,url in LINK.findall(src.read_text()):
            p=target(src,url)
            if p:
                assert p.exists() or p==HERE/'validation.json',(str(src),url);links+=1
    validation=dict(status='PASS',source_hash_checks=source_checks,numeric_results_recomputed=numeric,
        plateau_stop_epochs_recomputed=[r['qat_epochs'] for r in training['runs']],protected_guards=guards,
        previous_pilot_files_unchanged=len(previous),local_links_checked=links,stages_seconds=times,output_bytes=size,
        complete_validation_rows_per_seed=80450,new_board_runs=0,gpu_jobs=0,
        scope='Offline integer training and export evidence, operational loss plateau; not global convergence or independent test/board evidence')
    dump(HERE/'validation.json',validation)
    bundle=HERE/'candidate_parameters.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('README.txt','Two isolated candidate exports. No bitstream included. Existing RTL release loader still points to old parameters. C source can be rebuilt with gcc -O2 -std=c99 -shared -fPIC inference_trace.c -o inference_trace.so. See repository report for input and evaluation scope.\n')
        for seed in [7,17]:
            base=LOG/'training'/f'seed{seed}'
            for p in (base/'final_export').iterdir():
                if p.suffix!='.so':z.write(p,str(Path(f'seed{seed}')/'final_export'/p.name))
            for name in ['frozen_qat.pt','summary.json']:z.write(base/name,f'seed{seed}/'+name)
        for name in ['plan.json','01_计划与部署契约.md','02_结果与收敛判定.md','03_审查与后续边界.md','04_先完成特征筛选与样本审计.md']:z.write(HERE/name,name)
    excludes={'validation.json','evidence_manifest.json','obsidian_sync_manifest.json'}
    paths=[p for base in [HERE,LOG] for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in excludes]
    dump(HERE/'evidence_manifest.json',dict(scope='Isolated INT8 convergence package; external inputs separately hashed in phase summaries',files={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)}))
    assert VAULT.is_dir();dest=VAULT/REL;dest.mkdir(parents=True,exist_ok=True)
    mapping={p.resolve():dest/p.relative_to(HERE) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='obsidian_sync_manifest.json'}
    snapshots=records+[LOG/'pre_training_source_manifest.json',LOG/'verification/sequence_metrics.csv',LOG/'cli_smoke/summary.json']
    for seed in [7,17]:
        base=LOG/'training'/f'seed{seed}';snapshots.append(base/'summary.json')
        snapshots.extend(p for p in (base/'final_export').iterdir() if p.suffix!='.so')
    for p in snapshots:mapping[p.resolve()]=dest/'证据快照'/p.relative_to(LOG)
    external={ROOT/'docs/paper_new/feature_approximation_pilot_2026-09-16/README.md':VAULT/'项目/毕业论文——研究生/Chipyard论文知识库/论文写作/近似特征受控试验_2026-09-16/README.md'}
    rows=[]
    for source,destination in sorted(mapping.items()):
        destination.parent.mkdir(parents=True,exist_ok=True)
        if source.suffix=='.md':
            def rewrite(m):
                label,url=m.groups();p=target(source,url);d=mapping.get(p,external.get(p))
                if d:
                    name=d.relative_to(VAULT)
                    if name.suffix=='.md':name=name.with_suffix('')
                    return ('![['+str(name)+']]' if m.group(0).startswith('!') else '[['+str(name)+'|'+label+']]')
                if p and ROOT in p.parents:return label+'（仓库路径：`'+str(p.relative_to(ROOT))+'`）'
                return m.group(0)
            destination.write_text(LINK.sub(rewrite,source.read_text())+'\n\n仓库来源：`'+str(source.relative_to(ROOT))+'`；本地共享 vault 镜像，云端同步未验证。\n')
        else:shutil.copyfile(source,destination);assert sha(source)==sha(destination)
        rows.append(dict(source=str(source.relative_to(ROOT)),source_sha256=sha(source),destination=str(destination.relative_to(VAULT)),destination_sha256=sha(destination)))
    marker='qmlp-int8-convergence-20260916';start='<!-- '+marker+':start -->';end='<!-- '+marker+':end -->'
    block=start+'\n2026-09-16：[['+str(REL/'README')+'|冻结 INT8 训练与收敛]]。完整 train 357,780 条，两 seed 在 QAT 第 28/39 epoch 达到预设损失平台期；开发 validation Macro-F1 97.4957%/97.5364%，原模型同集 96.6527%。完整验证逐层 C/NumPy/QAT 一致，提供独立参数候选；未新建位流、未上板，不是新独立测试成绩。后续优先[['+str(REL/'04_先完成特征筛选与样本审计')+'|随机森林参照、特征消融与样本过滤审计]]，RTL 后置。\n'+end
    for rel in ['项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md','Codex/Chipyard/Chipyard Index.md']:
        p=VAULT/rel;body=p.read_text()
        if start in body:body=re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:block,body,flags=re.S)
        else:first,rest=body.split('\n',1);body=first+'\n\n'+block+'\n'+rest
        p.write_text(body)
    record=dict(status='LOCAL_VAULT_WRITTEN_AND_HASH_CHECKED',cloud_sync='NOT_VERIFIED',destination=str(dest.resolve()),files=rows)
    dump(HERE/'obsidian_sync_manifest.json',record);shutil.copyfile(HERE/'obsidian_sync_manifest.json',dest/'obsidian_sync_manifest.json')
    print(json.dumps(dict(validation=validation,mirrored_files=len(rows)),ensure_ascii=False))

if __name__=='__main__':main()
