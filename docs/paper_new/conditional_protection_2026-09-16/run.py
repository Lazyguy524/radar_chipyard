"""Sequential bounded execution after preflight and source snapshot."""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/conditional_protection_20260916'
def main():
    assert json.loads((LOG/'preflight.json').read_text())['status']=='PASS'
    assert (LOG/'git_backup_before.json').exists()
    out=LOG/'execution';out.mkdir(exist_ok=False);stages=[]
    for name,script,budget in [('training','train.py',1900),('evaluation','evaluate.py',650),('implementations','build_candidates.py',120)]:
        start=time.monotonic();print(json.dumps(dict(start=name)),flush=True)
        with (out/(name+'.log')).open('w') as f:r=subprocess.run([sys.executable,str(HERE/script)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=budget)
        stages.append(dict(stage=name,seconds=time.monotonic()-start,returncode=r.returncode))
        if r.returncode:
            (LOG/'execution_summary.json').write_text(json.dumps(dict(status='FAILED',stages=stages),indent=2)+'\n');raise RuntimeError(name)
        print(json.dumps(stages[-1]),flush=True)
    (LOG/'execution_summary.json').write_text(json.dumps(dict(status='PASS',stages=stages),indent=2)+'\n')
if __name__=='__main__':main()
