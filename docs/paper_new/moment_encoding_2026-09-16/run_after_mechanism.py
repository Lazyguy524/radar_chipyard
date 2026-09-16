"""Run the separate six-trajectory encoding study after the preceding protocol."""
import json
from pathlib import Path
import shutil
import subprocess
import time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/moment_encoding_20260916'
MECH=ROOT/'logs/mechanism_convergence_20260916';PY='/tmp/radar_training_audit_20260915/bin/python'
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
    start=time.monotonic();records=[];tmp=Path('/tmp/moment_encoding_execution_20260916');tmp.mkdir(exist_ok=True)
    deadline=time.monotonic()+3600
    while not (MECH/'continuation_summary.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Previous experiment continuation did not finish')
        time.sleep(2)
    assert json.loads((MECH/'continuation_summary.json').read_text())['status']=='PASS'
    waited=time.monotonic()-start
    try:
        for name,script,args,timeout in [('prepare','prepare.py',[],900),('training','train_encoding.py',['--stage','encoding'],900),('evaluation','evaluate.py',[],600),('implementations','build_candidates.py',[],180)]:
            print(json.dumps(dict(start=name,timeout=timeout)),flush=True);t=time.monotonic();log=tmp/(name+'.log')
            with log.open('w') as f:r=subprocess.run([PY,str((HERE/script).relative_to(ROOT)),*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
            records.append(dict(stage=name,returncode=r.returncode,seconds=time.monotonic()-t))
            if LOG.exists():(LOG/'execution').mkdir(exist_ok=True);shutil.copyfile(log,LOG/'execution'/log.name)
            if r.returncode:raise RuntimeError(name+' failed; original log retained')
            dump(LOG/'continuation_progress.json',dict(status='RUNNING',stages=records));print(json.dumps(dict(done=name,seconds=records[-1]['seconds'])),flush=True)
        dump(LOG/'continuation_summary.json',dict(status='PASS',stages=records,wait_seconds=waited,execution_seconds=time.monotonic()-start-waited))
        print(json.dumps(dict(status='PASS',execution_seconds=time.monotonic()-start-waited)),flush=True)
    except Exception as e:
        if LOG.exists():dump(LOG/'continuation_summary.json',dict(status='FAILED',error=repr(e),stages=records,wait_seconds=waited))
        raise

if __name__=='__main__':main()
