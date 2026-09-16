"""Recompute metrics, verify provenance/guards, package and mirror both studies."""
import csv
import functools
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
EDOC=ROOT/'docs/paper_new/moment_encoding_2026-09-16'
M=ROOT/'logs/mechanism_convergence_20260916';E=ROOT/'logs/moment_encoding_20260916'
VAULT=Path('/home/soooarr/obsidian');PARENT=Path('项目/毕业论文——研究生/Chipyard论文知识库/论文写作')
DESTS={HERE:VAULT/PARENT/'机制收敛与条件稳健性_2026-09-16',EDOC:VAULT/PARENT/'矩统计输出编码_2026-09-16'}
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
def main():
    print('Checking stage provenance',flush=True)
    records=[];hash_checks=0
    names_m=['preflight.json','raw/val_summary.json','raw/train_summary.json','raw/summary.json','factorial_v2/summary.json','augmentation_v2/summary.json',
             'factorial_evaluation/summary.json','augmentation_evaluation/summary.json','implementations/summary.json','mechanism_audit/summary.json','continuation_summary.json']
    names_e=['preflight.json','training/summary.json','evaluation/summary.json','implementations/summary.json','continuation_summary.json']
    for log,doc,names in [(M,HERE,names_m),(E,EDOC,names_e)]:
        for name in names:
            p=log/name;records.append(p);r=get(p);assert r['status']=='PASS',p
            if 'plan_sha256' in r:assert r['plan_sha256']==sha(doc/'plan.json'),p
            for path,digest in r.get('source_sha256',{}).items():assert sha(ROOT/path)==digest,path;hash_checks+=1
    for p in [M/'pre_raw_evaluation_manifest.json',EDOC/'pre_execution_manifest.json',M/'factorial_v2/source_manifest.json',M/'augmentation_v2/source_manifest.json',E/'training/source_manifest.json']:
        records.append(p)
        for path,digest in get(p)['sha256'].items():assert sha(ROOT/path)==digest,path;hash_checks+=1
    # Rehash every original raw HDF5, not merely its size/mtime.
    raw_count=0
    for split in ['train','val']:
        r=get(M/'raw'/(split+'_summary.json'));assert r['primary_feature_reconstruction_mismatches']==0
        for row in r['raw_hdf5_metadata']:
            assert sha(Path(row['path']))==row['sha256'],row['path'];raw_count+=1
    assert raw_count==140
    print('Checking 35 fixed-budget trajectories and saved predictions',flush=True)
    numeric=0;initial={};train_count=0;stage_times={}
    def check(label,pred,row):
        nonlocal numeric
        pred=np.asarray(pred,dtype=np.int64);label=np.asarray(label,dtype=np.int64)
        assert pred.shape==label.shape and ((pred==0)|(pred==1)).all()
        cm=np.bincount(label*2+pred,minlength=4).reshape(2,2)
        f=2*np.diag(cm)/(cm.sum(0)+cm.sum(1))
        assert cm.tolist()==row['confusion_matrix']
        assert abs(f.mean()-row['macro_f1'])<1e-12
        assert abs(np.trace(cm)/cm.sum()-row['accuracy'])<1e-12
        if 'per_class_f1' in row:assert np.allclose(f,row['per_class_f1'],atol=1e-14,rtol=0)
        numeric+=1
    for log,folder,eval_name,expected in [(M,'factorial_v2','factorial_evaluation',20),(M,'augmentation_v2','augmentation_evaluation',9),(E,'training','evaluation',6)]:
        t=get(log/folder/'summary.json');v=get(log/eval_name/'summary.json');assert len(t['runs'])==expected
        stage_times[folder if log==M else 'encoding_training']=t['wall_seconds']
        y=np.load(log/'data/val/labels.npy');assert len(y)==80450
        assert np.array_equal(y,np.load(M/'data/val/labels.npy'))
        for run in t['runs']:
            tag=run['mode']+'_seed'+str(run['seed']);base=log/folder/tag;r=get(base/'summary.json')
            assert r['qat_epochs']==60 and r['integer_layer_mismatches']==[0,0,0] and r['fold_max_error']<1e-9
            initial.setdefault(r['seed'],set()).add(r['initialization_sha256']);train_count+=1
            for phase,total in [('warmup',20),('qat',60)]:assert [x['epoch'] for x in r['curve'] if x['phase']==phase]==list(range(1,total+1))
            for row in r['curve']:
                if 'validation' in row:
                    assert row['epoch'] in [20,40,60]
                    check(y,np.load(base/('epoch'+str(row['epoch']))/'val_logits.npy').argmax(1),row['validation'])
            assert (base/'epoch60/export/params.h').is_file()
        for kind in ['metrics','precision_metrics','sparse_metrics']:
            for r in v[kind]:
                tag=r['mode']+'_seed'+str(r['seed']);label=y
                if kind=='precision_metrics':tag+='_m%d_v%d'%(r['mean_bits'],r['moment_bits'])
                condition=r['view'] if kind=='sparse_metrics' else r['condition']
                if kind=='sparse_metrics':
                    label=np.load(log/'raw'/condition/'labels.npy');assert len(label)==97734
                    assert np.array_equal(label,np.load(M/'raw'/condition/'labels.npy'))
                check(label,np.load(log/eval_name/(tag+'_'+condition+'_prediction.npy')),r)
        for row in v['precision_acceptance']:
            assert row['accepted']==(not row['failures'])
            if row['mean_bits']==row['moment_bits']==16:assert row['accepted']
        if log==M:
            sy=np.load(M/'raw/sparse_context/labels.npy')
            for r in v['coverage_policy']:
                tag=r['mode']+'_seed'+str(r['seed'])
                pp=np.concatenate([np.load(log/eval_name/(tag+'_clean_prediction.npy')),np.load(log/eval_name/(tag+'_sparse_context_prediction.npy'))])
                check(np.concatenate([y,sy]),pp,r['retained_plus_context_probe'])
    assert train_count==35 and all(len(x)==1 for x in initial.values())
    budgets=get(HERE/'plan.json')['budgets'];eb=get(EDOC/'plan.json')['budgets']
    assert stage_times['factorial_v2']<budgets['factorial_training_seconds']
    assert stage_times['augmentation_v2']<budgets['augmentation_training_seconds']
    assert stage_times['encoding_training']<eb['encoding_training_seconds']
    raw_seconds=sum(get(M/'raw'/(s+'_summary.json'))['wall_seconds'] for s in ['train','val'])
    assert raw_seconds<budgets['raw_preparation_seconds']
    for p in [M/'factorial_evaluation/summary.json',M/'augmentation_evaluation/summary.json']:assert get(p)['wall_seconds']<budgets['evaluation_seconds']
    assert get(E/'evaluation/summary.json')['wall_seconds']<eb['evaluation_seconds']
    assert get(E/'preflight.json')['wall_seconds']<eb['prepare_seconds']
    sizes={str(log.relative_to(ROOT)):sum(p.stat().st_size for p in log.rglob('*') if p.is_file()) for log in [M,E]}
    assert sizes[str(M.relative_to(ROOT))]<budgets['max_output_bytes'] and sizes[str(E.relative_to(ROOT))]<eb['max_output_bytes']
    c_count=sum(get(log/'implementations/summary.json')['complete_c_rows'] for log in [M,E]);assert c_count==2815750
    assert get(M/'factorial_evaluation/augmentation_gate.json')['triggered']
    print('Checking historical protected artifacts',flush=True)
    guards=[]
    for package in ['training_and_gemmini_retest_2026-09-15','gemmini_qmlp_comparison_2026-09-15']:
        p=ROOT/'docs/paper_new'/package/'protected_artifacts_before.json';files=get(p)['files']
        entries=files.items() if isinstance(files,dict) else [(r['path'],r) for r in files]
        count=0
        for path,row in entries:assert sha(ROOT/path)==row['sha256'],path;count+=1
        guards.append(dict(manifest=str(p.relative_to(ROOT)),unchanged=count))
    for package in ['feature_approximation_pilot_2026-09-16','qmlp_int8_convergence_2026-09-16','conditional_statistics_2026-09-16']:
        p=ROOT/'docs/paper_new'/package/'evidence_manifest.json';files=get(p)['files']
        for path,row in files.items():assert sha(ROOT/path)==row['sha256'],path
        guards.append(dict(manifest=str(p.relative_to(ROOT)),unchanged=len(files)))
    for doc,log in [(HERE,M),(EDOC,E)]:
        with zipfile.ZipFile(doc/'candidate_c_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('README.txt','Host C functional candidates, not RISC-V ELF or bitstream. Each folder: gcc -O2 -std=c99 candidate.c -o candidate ; ./candidate example.int16le . Input: 1..511 upstream GT-track/K7 points, little-endian signed int16 Q8.8 x,y,compensated velocity,RCS. All seeds preserved; no best-validation model selection. All delivered frontends use Q24 reference reciprocal. See Chinese notes for development-validation and coverage limits.\n')
            for base in sorted((log/'implementations').iterdir()):
                if base.is_dir():
                    for name in ['candidate.c','params.h','example.int16le','example.json']:z.write(base/name,base.name+'/'+name)
            for p in doc.glob('*.md'):z.write(p,p.name)
            z.write(doc/'plan.json','plan.json')
    generated={doc/n for doc in [HERE,EDOC] for n in ['validation.json','evidence_manifest.json','obsidian_sync_manifest.json']}
    links=0
    for doc in [HERE,EDOC]:
        for p in doc.glob('*.md'):
            for _,url in LINK.findall(p.read_text()):
                dest=target(p,url)
                if dest:assert dest.exists() or dest in generated,(p,url);links+=1
    validation=dict(status='PASS',completed_trajectories=train_count,fixed_epochs=dict(fp32=20,qat=60),same_seed_initializations_match=True,
        numeric_metrics_recomputed=numeric,source_hash_checks=hash_checks,raw_hdf5_rehashed=raw_count,complete_c_model_observation_pairs=c_count,
        historical_guards=guards,stage_training_seconds=stage_times,raw_seconds=raw_seconds,output_bytes=sizes,local_markdown_links=links,
        failures_preserved=dict(mechanism_partial_training_wrapper_failure=1,encoding_initialization_smoke_fix=1,encoding_pre_model_source_path_failure=1),
        gpu_jobs=0,new_rtl_jobs=0,new_board_runs=0,scope='Evidence integrity and bounded execution PASS, not acceptance of every hypothesis, independent generalization, or measured hardware quality-cost advantage')
    for doc in [HERE,EDOC]:dump(doc/'validation.json',validation)
    excluded={'evidence_manifest.json','obsidian_sync_manifest.json'}
    for doc,log in [(HERE,M),(EDOC,E)]:
        paths=[p for base in [doc,log] for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in excluded]
        dump(doc/'evidence_manifest.json',dict(scope='Isolated study files; upstream sources additionally hashed in stage records',files={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)}))
    print('Writing local Obsidian mirrors',flush=True)
    assert VAULT.is_dir();mapping={};owner={}
    for doc,log in [(HERE,M),(EDOC,E)]:
        dest=DESTS[doc];dest.mkdir(parents=True,exist_ok=True)
        for p in doc.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.name!='obsidian_sync_manifest.json':mapping[p.resolve()]=dest/p.relative_to(doc);owner[p.resolve()]=doc
        snapshot=[p for p in records if log in p.parents]
        snapshot.extend(p for p in log.rglob('*.csv'))
        snapshot.extend(p for folder in ['factorial_v2','augmentation_v2','training'] for p in (log/folder).glob('*/summary.json'))
        snapshot.extend(p for p in [log/'implementations/cost_graph.json',log/'data/scales.json',log/'factorial_evaluation/augmentation_gate.json'] if p.exists())
        for p in snapshot:mapping[p.resolve()]=dest/'证据快照'/p.relative_to(log);owner[p.resolve()]=doc
    rows={HERE:[],EDOC:[]}
    for src,dst in sorted(mapping.items()):
        dst.parent.mkdir(parents=True,exist_ok=True)
        if src.suffix=='.md':
            def rewrite(m):
                label,url=m.groups();p=target(src,url);to=mapping.get(p)
                if to:
                    name=to.relative_to(VAULT)
                    if name.suffix=='.md':name=name.with_suffix('')
                    return '![[%s]]'%name if m.group(0).startswith('!') else '[[%s|%s]]'%(name,label)
                if p and ROOT in p.parents:return label+'（仓库路径：`'+str(p.relative_to(ROOT))+'`）'
                return m.group(0)
            dst.write_text(LINK.sub(rewrite,src.read_text())+'\n\n仓库来源：`'+str(src.relative_to(ROOT))+'`；本地共享 vault 镜像，云端同步未验证。\n')
        else:shutil.copyfile(src,dst);assert sha(src)==sha(dst)
        rows[owner[src]].append(dict(source=str(src.relative_to(ROOT)),source_sha256=sha(src),destination=str(dst.relative_to(VAULT)),destination_sha256=sha(dst)))
    marker='mechanism-convergence-20260916';start='<!-- '+marker+':start -->';end='<!-- '+marker+':end -->'
    rel=DESTS[HERE].relative_to(VAULT)
    block=start+'\n2026-09-16 最新算法入口：[['+str(rel/'README')+'|35 条训练后的机制收敛]]。完成五 seed 机制、三 seed 条件训练/编码、11 输入条件和真实被过滤观测审计。简单定标＋条件覆盖是强基线；高精度矩/根号未建立全面优势，少点改善与近距离/历史充分组回退同时保留。先读[['+str(rel/'03_评审与收敛决定')+'|收敛评审]]和[['+str(rel/'05_分组收益与回退')+'|条件回退]]。没有新增 RTL/位流/板测，不以开发 validation 替代独立确认。\n'+end
    for rel in ['项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md','Codex/Chipyard/Chipyard Index.md']:
        p=VAULT/rel;body=p.read_text()
        if start in body:body=re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:block,body,flags=re.S)
        else:first,rest=body.split('\n',1);body=first+'\n\n'+block+'\n'+rest
        p.write_text(body)
    for doc in [HERE,EDOC]:
        record=dict(status='LOCAL_VAULT_WRITTEN_AND_HASH_CHECKED',cloud_sync='NOT_VERIFIED',destination=str(DESTS[doc].resolve()),files=rows[doc])
        dump(doc/'obsidian_sync_manifest.json',record);shutil.copyfile(doc/'obsidian_sync_manifest.json',DESTS[doc]/'obsidian_sync_manifest.json')
    print(json.dumps(dict(validation=validation,mirror_counts={p.name:len(v) for p,v in rows.items()}),ensure_ascii=False))
if __name__=='__main__':main()
