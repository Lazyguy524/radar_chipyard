"""Selective side-branch snapshots, preserving the user's HEAD/index/worktree."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/feature_dimension_sweep_20260917'
REF='refs/heads/backup/radar-thesis-20260917-feature-dimension-sweep'
PACKAGES=['feature_dimension_sweep']
def git(args,**kw):return subprocess.check_output(['git',*args],cwd=ROOT,**kw)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['before','after'],required=True);a=parser.parse_args()
    record=LOG/('git_backup_'+a.phase+'.json');assert not record.exists()
    head=git(['rev-parse','HEAD'],text=True).strip();branch=git(['symbolic-ref','HEAD'],text=True).strip()
    gitdir=Path(git(['rev-parse','--absolute-git-dir'],text=True).strip());index=gitdir/'index';index_hash=sha(index)
    old_ref=subprocess.run(['git','rev-parse','--verify',REF],cwd=ROOT,capture_output=True,text=True)
    old=old_ref.stdout.strip() if old_ref.returncode==0 else None
    if a.phase=='before':assert old is None,'Backup branch already exists; use a new explicit snapshot branch'
    else:assert old==json.loads((LOG/'git_backup_before.json').read_text())['commit']
    paths=set();doc_ext={'.py','.c','.h','.md','.json','.csv','.ris','.bib','.mmd','.scala','.txt','.png'}
    for package in PACKAGES:
        d=ROOT/'docs/paper_new'/(package+'_2026-09-17')
        paths.update(p for p in d.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and (p.suffix in doc_ext or (p.suffix=='.pdf' and 'figures' in p.parts)))
        l=ROOT/'logs'/(package+'_20260917')
        # Raw points, row-level identities, predictions and compiled binaries are
        # archived separately. Git holds scientific source, models and small evidence.
        paths.update(p for p in l.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix in {'.py','.c','.h','.scala','.json','.pt','.npz','.csv','.md'}
                     and not any(x in p.parts for x in ['raw','data','prepared']) and not p.name.startswith('git_backup_'))
    paths.update(ROOT/p for p in ['docs/paper_new/README.md','docs/paper_new/00_project_requirements_and_memory.md'])

    paths={p for p in paths if p.stat().st_size<=10*1024*1024 and p.name!='obsidian_sync_manifest.json'}
    assert all(ROOT in p.parents for p in paths)
    for p in paths:
        if p.suffix in {'.py','.c','.h','.md','.json','.txt'}:
            content=p.read_bytes();assert not any(line.strip().startswith(b'-----BEGIN ') and b'PRIVATE KEY' in line for line in content.splitlines()),p
    manifest=LOG/('git_payload_'+a.phase+'.json')
    manifest.write_text(json.dumps(dict(scope='Selective thesis algorithm sources, design notes, model parameters and small evidence; excludes raw arrays/data and unrelated dirty RTL/bitstreams',
        base_head=head,files={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)}),ensure_ascii=False,indent=2)+'\n')
    paths.add(manifest)
    with tempfile.TemporaryDirectory(prefix='radar_software_git_') as temporary:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temporary)/'snapshot.index'))
        subprocess.run(['git','read-tree',old or '502a17950b9506de6d9b92fb401c53d7f5abaa7f'],cwd=ROOT,env=env,check=True)
        entries=[]
        for p in sorted(paths):
            blob=git(['hash-object','-w','--',str(p)],text=True).strip();mode='100755' if p.stat().st_mode&0o111 else '100644'
            entries.append((mode+' '+blob+'\t'+str(p.relative_to(ROOT))).encode()+b'\0')
        subprocess.run(['git','update-index','-z','--index-info'],input=b''.join(entries),cwd=ROOT,env=env,check=True)
        tree=git(['write-tree'],env=env,text=True).strip()
        message='radar thesis: '+('freeze bounded feature dimension sweep plan and preflight' if a.phase=='before' else 'archive bounded feature dimension sweep results and design reflection')+'\n\nSelective backup branch; original work branch and staged index preserved. Large raw data are separately indexed, not included.\n'
        commit=git(['commit-tree',tree,'-p',old or '502a17950b9506de6d9b92fb401c53d7f5abaa7f'],input=message,text=True).strip()
        subprocess.run(['git','update-ref',REF,commit,old or '0'*40],cwd=ROOT,check=True)
    assert git(['rev-parse','HEAD'],text=True).strip()==head and git(['symbolic-ref','HEAD'],text=True).strip()==branch and sha(index)==index_hash
    for p in paths:assert hashlib.sha256(git(['show',commit+':'+str(p.relative_to(ROOT))])).hexdigest()==sha(p),p
    bundle=Path('/home/soooarr')/'radar_thesis_backups_20260917';bundle.mkdir(exist_ok=True)
    bundle_path=bundle/('feature_dimension_sweep_'+a.phase+'.bundle')
    subprocess.run(['git','bundle','create',str(bundle_path),REF,'^'+head],cwd=ROOT,check=True,capture_output=True)
    verify=subprocess.run(['git','bundle','verify',str(bundle_path)],cwd=ROOT,check=True,capture_output=True,text=True)
    # The configured origin is the user's existing project repository, never upstream.
    assert git(['remote','get-url','origin'],text=True).strip()=='git@github.com:Lazyguy524/radar_chipyard.git'
    env=dict(os.environ,GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10')
    try:
        push=subprocess.run(['git','push','origin',REF+':'+REF],cwd=ROOT,env=env,text=True,capture_output=True,timeout=45)
        remote=git(['ls-remote','--heads','origin',REF],env=env,text=True,timeout=30).strip()
        remote_ok=push.returncode==0 and remote.split()[0]==commit if remote else False
        status=dict(returncode=push.returncode,stdout=push.stdout,stderr=push.stderr,remote_ref=remote,remote_verified=remote_ok)
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as e:status=dict(remote_verified=False,error='Remote operation timed out',command=str(e.cmd))
    result=dict(status='REMOTE_VERIFIED' if status['remote_verified'] else 'LOCAL_COMMIT_AND_BUNDLE_ONLY',phase=a.phase,commit=commit,branch=REF,base_head=head,
        original_head_unchanged=True,original_index_sha256=index_hash,files=len(paths),payload_manifest=str(manifest.relative_to(ROOT)),bundle=str(bundle_path),bundle_sha256=sha(bundle_path),
        bundle_requires_base=head,push=status,scope='Selective algorithm and thesis backup, not a complete backup of the dirty Chipyard worktree or original radar dataset')
    record.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
