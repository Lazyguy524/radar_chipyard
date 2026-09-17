"""Freeze current evidence, selective Git backup, and local Obsidian mirror."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
LOG=ROOT/'logs/representative_rtl_20260917'
REF='refs/heads/backup/radar-thesis-20260917-rtl'
PARENT='df7774f3ae93e286dab0fcf6a0e27d3b939c9e8e'
ARCHIVE=Path('/home/soooarr/radar_thesis_backups_20260917')
MIRROR=Path('/home/soooarr/obsidian/项目/毕业论文——研究生/Chipyard论文知识库/论文写作/代表方案硬件衔接_2026-09-17')

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def git(args,**kw):return subprocess.check_output(['git',*args],cwd=ROOT,**kw)

def main():
    assert json.loads((LOG/'summary.json').read_text())['status']=='PASS'
    assert not (LOG/'git_backup.json').exists()
    # Verify the older frozen research evidence without regenerating its outputs.
    guards=[]
    for name in ('mechanism_convergence','moment_encoding','conditional_protection'):
        m=ROOT/'docs/paper_new'/(name+'_2026-09-16')/'evidence_manifest.json'
        data=json.loads(m.read_text())
        entries=data.get('files',data)
        if isinstance(entries,list):raise AssertionError('Inspect manifest format before proceeding')
        checked=0
        for rel,value in entries.items():
            if not isinstance(value,(str,dict)):continue
            h=value.get('sha256') if isinstance(value,dict) else value
            if not h or len(h)!=64:continue
            p=ROOT/rel
            assert p.is_file() and sha(p)==h,rel
            checked+=1
        assert checked>0
        guards.append(dict(package=name,verified_files=checked,manifest_sha256=sha(m)))
    dump(LOG/'previous_evidence_check.json',dict(status='PASS',checks=guards))
    # Portable binding for future integration: none of the null board fields may
    # be filled from a different old release merely because architecture matches.
    import workflow as w
    bindings=[]
    for model,export in w.EXPORTS.items():
        d=LOG/model
        bindings.append(dict(model=model,seed=7,lanes=4,feature_shifts=w.PLAN['frontend_shifts'],
            model_export={str(p.relative_to(ROOT)):sha(p) for p in export.iterdir() if p.suffix in ('.h','.json','.npz','.scala','.c')},
            isolated_rtl={str(p.relative_to(ROOT)):sha(p) for p in (d/'rtl').glob('*.sv')},
            rtl_result_sha256=sha(d/'rtl_result.json'),
            stage='STANDALONE_RTL_VERIFIED_NOT_BOARD_READY',
            soc_config=None,bitstream_sha256=None,elf_sha256=None,clock_hz=None,board_log_sha256=None,
            algorithm_promotion=False))
    dump(HERE/'model_bindings.json',dict(models=bindings,scope='Feature scaling, model and RTL are bound; complete SoC/board artifacts remain unbuilt.'))
    source_paths=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    logs=[p for p in LOG.rglob('*') if p.is_file() and not any(x in p.parts for x in ('obj','classes','__pycache__'))
          and p.suffix in ('.json','.log','.scala','.sv','.c','.f','.patch')]
    frozen=sorted(source_paths+logs)
    dump(HERE/'evidence_manifest.json',dict(files={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in frozen},
        exclusions='Generated object/classes, large input vectors, shared objects, and later backup/sync receipts. Vectors have their own SHA in preflight and full archive.'))
    paths=set(frozen+[HERE/'evidence_manifest.json',ROOT/'docs/paper_new/README.md',ROOT/'docs/paper_new/00_project_requirements_and_memory.md'])
    # Include new experiment's direct production-source inputs, without changing
    # those paths on the current work branch or backing up unrelated dirty files.
    paths.update(ROOT/'generators/chipyard/src/main/scala/radar'/n for n in ('RadarFeature21.scala','RadarQMLP.scala','RadarStream.scala'))
    for p in paths:
        if p.suffix in ('.md','.py','.json','.scala','.c','.h','.log'):
            assert not any(line.strip().startswith(b'-----BEGIN ') and b'PRIVATE KEY' in line for line in p.read_bytes().splitlines()),p
    head=git(['rev-parse','HEAD'],text=True).strip();branch=git(['symbolic-ref','HEAD'],text=True).strip()
    idx=Path(git(['rev-parse','--absolute-git-dir'],text=True).strip())/'index';idx_sha=sha(idx)
    assert subprocess.run(['git','show-ref','--verify','--quiet',REF],cwd=ROOT).returncode!=0
    dump(LOG/'git_payload.json',dict(parent=PARENT,files={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}));paths.add(LOG/'git_payload.json')
    with tempfile.TemporaryDirectory(prefix='radar_rtl_snapshot_') as td:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(td)/'index'))
        subprocess.run(['git','read-tree',PARENT],cwd=ROOT,env=env,check=True)
        entries=[]
        for p in sorted(paths):
            blob=git(['hash-object','-w','--',str(p)],text=True).strip()
            entries.append(('100644 '+blob+'\t'+str(p.relative_to(ROOT))).encode()+b'\0')
        subprocess.run(['git','update-index','-z','--index-info'],cwd=ROOT,env=env,input=b''.join(entries),check=True)
        tree=git(['write-tree'],env=env,text=True).strip()
        commit=git(['commit-tree',tree,'-p',PARENT],input='radar thesis: bind frozen representatives to verified isolated RTL\n',text=True).strip()
        subprocess.run(['git','update-ref',REF,commit,'0'*40],cwd=ROOT,check=True)
    for p in paths:assert hashlib.sha256(git(['show',commit+':'+str(p.relative_to(ROOT))])).hexdigest()==sha(p)
    assert git(['rev-parse','HEAD'],text=True).strip()==head and git(['symbolic-ref','HEAD'],text=True).strip()==branch and sha(idx)==idx_sha
    ARCHIVE.mkdir(exist_ok=False)
    bundle=ARCHIVE/'representative_rtl.bundle'
    subprocess.run(['git','bundle','create',str(bundle),REF,'^'+head],cwd=ROOT,check=True,capture_output=True)
    subprocess.run(['git','bundle','verify',str(bundle)],cwd=ROOT,check=True,capture_output=True)
    assert git(['remote','get-url','origin'],text=True).strip()=='git@github.com:Lazyguy524/radar_chipyard.git'
    env=dict(os.environ,GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10')
    try:
        p=subprocess.run(['git','push','origin',REF+':'+REF],cwd=ROOT,env=env,text=True,capture_output=True,timeout=50)
        remote=git(['ls-remote','--heads','origin',REF],env=env,text=True,timeout=20).strip()
        push=dict(returncode=p.returncode,stderr=p.stderr,remote=remote,verified=bool(remote) and remote.split()[0]==commit)
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as e:push=dict(verified=False,error=str(e))
    dump(LOG/'git_backup.json',dict(commit=commit,ref=REF,parent=PARENT,files=len(paths),push=push,
        original_head=head,original_index_unchanged=True,bundle_sha256=sha(bundle),bundle_requires_base=head))
    archive=ARCHIVE/'representative_rtl_results.tar.gz'
    # Vectors, raw SV, logs and runnable simulator are archived; rebuildable
    # compiler intermediate objects/classes are omitted.
    allpaths=sorted(p for base in (HERE,LOG) for p in base.rglob('*') if p.is_file() and
        '__pycache__' not in p.parts and 'classes' not in p.parts and ('obj' not in p.parts or p.name=='candidate_sim'))
    with tarfile.open(archive,'w:gz') as tar:
        for p in allpaths:tar.add(p,arcname=str(p.relative_to(ROOT)),recursive=False)
    with tarfile.open(archive) as tar:
        for p in allpaths:assert hashlib.sha256(tar.extractfile(str(p.relative_to(ROOT))).read()).hexdigest()==sha(p)
    MIRROR.mkdir(parents=True,exist_ok=False)
    for p in HERE.iterdir():
        if p.is_file():shutil.copyfile(p,MIRROR/p.name)
    md='项目/毕业论文——研究生/Chipyard论文知识库/论文写作/代表方案硬件衔接_2026-09-17'
    block='\n\n<!-- representative-rtl-20260917 -->\n2026-09-17：[['+md+'/README|代表方案硬件衔接]]：三种已冻结候选的实际 Feature21＋QMLP RTL 对拍完成；原发布版保留，完整 SoC/板测及独立质量确认待补。\n'
    for index in (Path('/home/soooarr/obsidian/项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md'),Path('/home/soooarr/obsidian/Codex/Chipyard/Chipyard Index.md')):
        text=index.read_text();assert 'representative-rtl-20260917' not in text;index.write_text(text+block)
    backup=MIRROR/'备份';backup.mkdir()
    for p in (bundle,archive):
        shutil.copyfile(p,backup/p.name);assert sha(p)==sha(backup/p.name)
    receipt=dict(status='PASS',git=json.loads((LOG/'git_backup.json').read_text()),
        archive=str(archive),archive_sha256=sha(archive),archived_files=len(allpaths),
        mirrored_files={p.name:sha(p) for p in MIRROR.iterdir() if p.is_file()},
        mirror=str(MIRROR),cloud_sync_verified=False)
    for name,h in receipt['mirrored_files'].items():assert sha(HERE/name)==h
    dump(HERE/'backup_sync_receipt.json',receipt);shutil.copyfile(HERE/'backup_sync_receipt.json',MIRROR/'backup_sync_receipt.json')
    print(json.dumps(dict(status='PASS',commit=commit,remote_verified=push['verified'],archived_files=len(allpaths))),flush=True)

if __name__=='__main__':main()
