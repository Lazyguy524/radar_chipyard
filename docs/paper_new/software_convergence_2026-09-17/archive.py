"""Freeze evidence, selective Git snapshot and verified local Obsidian mirror."""
import shutil
import tarfile
import zipfile
from sw_common import *

ARCHIVE=Path('/home/soooarr/radar_thesis_backups_20260917')
MIRROR=Path('/home/soooarr/obsidian/项目/毕业论文——研究生/Chipyard论文知识库/论文写作/软件收敛与真实少点覆盖_2026-09-17')

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['freeze','sync'],required=True);phase=p.parse_args().phase
    assert json.loads((HERE/'validation.json').read_text())['status']=='PASS'
    if phase=='freeze':
        assert not (HERE/'evidence_manifest.json').exists()
        z=HERE/'candidate_c_bundle.zip'
        with zipfile.ZipFile(z,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
            for f in sorted((LOG/'package').rglob('*')):
                if f.is_file() and (f.suffix in ('.c','.h','.json','.md','.npz','.int16le')):bundle.write(f,f.relative_to(LOG/'package'))
        with zipfile.ZipFile(z) as bundle:
            assert bundle.testzip() is None
            for name in bundle.namelist():assert hashlib.sha256(bundle.read(name)).hexdigest()==sha(LOG/'package'/name)
        paths=sorted(p for basepath in (HERE,LOG) for p in basepath.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.name.startswith('git_payload_'))
        manifest=dict(files={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in paths},
            exclusions='Python caches and Git payload manifests; after-backup/archive/sync receipts written later; raw original HDF5 referenced by SHA but not copied')
        dump(HERE/'evidence_manifest.json',manifest);print(json.dumps(dict(status='FROZEN',files=len(paths))),flush=True);return
    after=json.loads((LOG/'git_backup_after.json').read_text())
    manifest=json.loads((HERE/'evidence_manifest.json').read_text())
    for rel,value in manifest['files'].items():assert sha(ROOT/rel)==value['sha256'],rel
    archive=ARCHIVE/'software_convergence_results.tar.gz';assert not archive.exists()
    paths=sorted(p for basepath in (HERE,LOG) for p in basepath.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    with tarfile.open(archive,'w:gz',compresslevel=6) as tar:
        for p in paths:tar.add(p,arcname=str(p.relative_to(ROOT)),recursive=False)
    with tarfile.open(archive) as tar:
        for p in paths:
            stream=tar.extractfile(str(p.relative_to(ROOT)));h=hashlib.sha256()
            for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
            assert h.hexdigest()==sha(p),p
    MIRROR.mkdir(parents=True,exist_ok=False);mirrored=[]
    for p in sorted(HERE.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        target=MIRROR/p.relative_to(HERE);target.parent.mkdir(parents=True,exist_ok=True)
        if p.suffix=='.md':
            target.write_text(p.read_text().replace('../../../logs/software_convergence_20260917/','证据/'))
        else:shutil.copyfile(p,target)
        mirrored.append(dict(source=str(p.relative_to(ROOT)),source_sha256=sha(p),target=str(target.relative_to(MIRROR)),target_sha256=sha(target),markdown_link_rewrite=p.suffix=='.md'))
    # Include linked evidence in the mirror itself; do not leave dangling repo paths.
    for p in sorted(LOG.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        relative=p.relative_to(LOG)
        keep=(p.suffix in ('.json','.csv','.md') and p.stat().st_size<10*1024*1024) or ('package' in relative.parts and p.suffix in ('.c','.h','.npz','.int16le'))
        if not keep:continue
        target=MIRROR/'证据'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);assert sha(p)==sha(target)
        mirrored.append(dict(source=str(p.relative_to(ROOT)),source_sha256=sha(p),target=str(target.relative_to(MIRROR)),target_sha256=sha(target),markdown_link_rewrite=False))
    backup=MIRROR/'备份';backup.mkdir()
    for p in [ARCHIVE/'software_convergence_before.bundle',ARCHIVE/'software_convergence_after.bundle',archive]:
        shutil.copyfile(p,backup/p.name);assert sha(p)==sha(backup/p.name)
    md='项目/毕业论文——研究生/Chipyard论文知识库/论文写作/软件收敛与真实少点覆盖_2026-09-17'
    block='\n\n<!-- software-convergence-20260917 -->\n2026-09-17：[['+md+'/README|软件收敛与真实少点覆盖]]：恢复真实 1～2 点观测，完成固定 12 条训练、全条件/分组及精度审查；主方案与取舍见一页结论。软件开发选型证据，独立泛化与板级成本另列，不新增硬件工作。\n'
    for index in [Path('/home/soooarr/obsidian/项目/毕业论文——研究生/Chipyard论文知识库/Chipyard雷达SoC论文知识库.md'),Path('/home/soooarr/obsidian/Codex/Chipyard/Chipyard Index.md')]:
        s=index.read_text();assert 'software-convergence-20260917' not in s;index.write_text(s+block)
    receipt=dict(status='PASS',git=after,archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),archived_files=len(paths),
        mirror=str(MIRROR),files=mirrored,cloud_sync_verified=False,scope='Verified local shared Obsidian directory and archive; external cloud propagation is not observable')
    dump(HERE/'backup_sync_receipt.json',receipt);shutil.copyfile(HERE/'backup_sync_receipt.json',MIRROR/'backup_sync_receipt.json')
    print(json.dumps(dict(status='PASS',commit=after['commit'],remote_verified=after['push']['remote_verified'],mirror=str(MIRROR),archive_bytes=archive.stat().st_size)),flush=True)
if __name__=='__main__':main()
