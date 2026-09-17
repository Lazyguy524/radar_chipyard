"""Selective Git backup and byte-verified Obsidian copy of this report only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REF='refs/heads/backup/radar-thesis-20260918-weekly'
PARENT='d7621b2cc206277c706d2573c77662ce16a7585b'
VAULT=Path('/home/soooarr/obsidian')
REL='项目/毕业论文——研究生/Chipyard论文知识库/周报与组会/2026-09-18_本周进展与五分钟组会'
DEST=VAULT/REL

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def git(args,**kw):return subprocess.check_output(['git',*args],cwd=ROOT,**kw)

def snapshot():
    receipt=HERE/'git_backup_receipt.json'
    assert not receipt.exists()
    assert json.loads((HERE/'validation.json').read_text())['status']=='PASS'
    head=git(['rev-parse','HEAD'],text=True).strip()
    index=ROOT/'.git/index';index_sha=sha(index)
    assert subprocess.run(['git','show-ref','--verify','--quiet',REF],cwd=ROOT).returncode==1
    paths=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += [ROOT/'docs/paper_new/README.md',ROOT/'docs/paper_new/00_project_requirements_and_memory.md']
    payload=HERE/'git_payload.json'
    dump(payload,dict(files={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)},scope='Weekly report, five-slide brief, original-result snapshots and new presentation figures only; no experiment changes'))
    paths.append(payload)
    with tempfile.TemporaryDirectory(prefix='radar_weekly_git_') as d:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(d)/'index'))
        subprocess.run(['git','read-tree',PARENT],cwd=ROOT,env=env,check=True)
        entries=[]
        for p in sorted(paths):
            oid=git(['hash-object','-w','--',str(p)],text=True).strip()
            entries.append(('100644 '+oid+'\t'+str(p.relative_to(ROOT))).encode()+b'\0')
        subprocess.run(['git','update-index','-z','--index-info'],input=b''.join(entries),cwd=ROOT,env=env,check=True)
        tree=git(['write-tree'],env=env,text=True).strip()
        commit=git(['commit-tree',tree,'-p',PARENT],input='radar thesis: weekly report and five-minute meeting brief for 2026-09-18\n\nEvidence-backed slides, private speaker notes and Windows PPT handoff. No experiment or gate changes.\n',text=True).strip()
        subprocess.run(['git','update-ref',REF,commit,'0'*40],cwd=ROOT,check=True)
    assert git(['rev-parse','HEAD'],text=True).strip()==head and sha(index)==index_sha
    for p in paths:assert hashlib.sha256(git(['show',commit+':'+str(p.relative_to(ROOT))])).hexdigest()==sha(p)
    assert git(['remote','get-url','origin'],text=True).strip()=='git@github.com:Lazyguy524/radar_chipyard.git'
    bundle=Path('/home/soooarr/radar_thesis_backups_20260917/weekly_report_20260918.bundle')
    assert not bundle.exists()
    subprocess.run(['git','bundle','create',str(bundle),REF,'^'+head],cwd=ROOT,check=True,capture_output=True)
    subprocess.run(['git','bundle','verify',str(bundle)],cwd=ROOT,check=True,capture_output=True)
    env=dict(os.environ,GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10')
    try:
        pushed=subprocess.run(['git','push','origin',REF+':'+REF],cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
        remote=git(['ls-remote','--heads','origin',REF],env=env,text=True,timeout=30).strip()
        status=dict(remote_verified=pushed.returncode==0 and bool(remote) and remote.split()[0]==commit,returncode=pushed.returncode,remote=remote,stderr=pushed.stderr)
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as exc:
        status=dict(remote_verified=False,error=type(exc).__name__)
    dump(receipt,dict(status='REMOTE_VERIFIED' if status['remote_verified'] else 'LOCAL_BACKUP',commit=commit,parent=PARENT,branch=REF,original_head=head,original_index_sha256=index_sha,original_head_index_unchanged=True,files=len(paths),bundle=str(bundle),bundle_sha256=sha(bundle),bundle_requires_base=head,push=status))
    print(json.dumps(dict(status='REMOTE_VERIFIED' if status['remote_verified'] else 'LOCAL_BACKUP',commit=commit,files=len(paths))))

def sync():
    assert json.loads((HERE/'validation.json').read_text())['status']=='PASS'
    assert not DEST.exists(),'Use a new directory; never overwrite an existing Windows PPT output.'
    manifest=json.loads((HERE/'source_manifest.json').read_text())
    for item in manifest['sources']:
        assert sha(ROOT/item['original_repo_path'])==item['sha256']
        assert sha(HERE/item['snapshot'])==item['sha256']
    receipt=HERE/'obsidian_sync_receipt.json'
    assert not receipt.exists()
    DEST.mkdir(parents=True)
    files=[]
    for p in sorted(HERE.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        q=DEST/p.relative_to(HERE);q.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,q);assert sha(p)==sha(q)
        files.append(dict(relative_path=str(p.relative_to(HERE)),sha256=sha(p),bytes=p.stat().st_size))
    marker='weekly-report-20260918'
    block='\n\n<!-- '+marker+' -->\n2026-09-18组会资料：[['+REL+'/README|完整周报与5分钟组会]]。工作统计截至9月17日；用户选择5分钟、5页，正文只讲数据复现、特征增减与阶段结论，细节留在讲稿和后续专题。附[['+REL+'/04_Windows_Codex生成PPT的Prompt|Windows生成PPT的Prompt]]及核验图表。23维是软件候选，局部回退与独立验证缺口保留。\n'
    indices=[]
    for rel in ['项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md','Codex/Chipyard/Chipyard Index.md']:
        p=VAULT/rel;old=p.read_bytes();assert marker.encode() not in old
        p.write_bytes(old+block.encode());assert p.read_bytes().startswith(old)
        indices.append(dict(path=rel,old_sha256=hashlib.sha256(old).hexdigest(),new_sha256=sha(p),old_content_preserved=True))
    git_receipt=json.loads((HERE/'git_backup_receipt.json').read_text())
    dump(receipt,dict(status='PASS',destination=str(DEST),vault_relative_path=REL,files=files,index_updates=indices,git_commit=git_receipt['commit'],git_remote_verified=git_receipt['push']['remote_verified'],cloud_sync_verified=False,scope='Byte-verified local shared Obsidian vault; Windows/cloud download state is not observable; PPT to be generated by Windows handoff'))
    shutil.copyfile(receipt,DEST/receipt.name);assert sha(receipt)==sha(DEST/receipt.name)
    print(json.dumps(dict(status='PASS',destination=str(DEST),files=len(files),git_remote_verified=git_receipt['push']['remote_verified']),ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['git','sync'],required=True)
    (snapshot if p.parse_args().phase=='git' else sync)()
