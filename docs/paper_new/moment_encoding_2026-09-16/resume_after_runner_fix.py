"""Continue verified prepared data after a pre-run source-path correction."""
import json
from pathlib import Path
import subprocess
import time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/moment_encoding_20260916';PY='/tmp/radar_training_audit_20260915/bin/python'
def main():
    assert json.loads((LOG/'preflight.json').read_text())['status']=='PASS';records=[];start=time.monotonic()
    for name,script,args,limit in [('training_v2','train_encoding_v2.py',['--stage','encoding'],900),('evaluation','evaluate.py',[],600),('implementations','build_candidates.py',[],180)]:
        print(json.dumps(dict(start=name)),flush=True);t=time.monotonic()
        with (LOG/'execution'/(name+'.log')).open('w') as f:r=subprocess.run([PY,str((HERE/script).relative_to(ROOT)),*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=limit)
        records.append(dict(stage=name,returncode=r.returncode,seconds=time.monotonic()-t))
        report=dict(status='FAILED' if r.returncode else 'RUNNING',stages=records,source_path_fix='See runner_fix.json; no model started in the failed pre-run attempt')
        (LOG/'continuation_progress_v2.json').write_text(json.dumps(report,indent=2)+'\n')
        if r.returncode:raise RuntimeError(name+' failed; inspect execution log')
        print(json.dumps(dict(done=name,seconds=records[-1]['seconds'])),flush=True)
    report=dict(status='PASS',stages=records,prepare_seconds=json.loads((LOG/'preflight.json').read_text())['wall_seconds'],resume_seconds=time.monotonic()-start)
    (LOG/'continuation_summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
