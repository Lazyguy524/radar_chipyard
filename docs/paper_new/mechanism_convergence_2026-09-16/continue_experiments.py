"""Sequential bounded continuation; never overlap two compute-heavy stages."""
import json
import os
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/mechanism_convergence_20260916'
PYTHON='/tmp/radar_training_audit_20260915/bin/python';PLAN=json.loads((HERE/'plan.json').read_text())
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def running_factorial():
    expected=str((HERE/'train_fixed_v2.py').relative_to(ROOT))
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:args=(p/'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError,PermissionError,ProcessLookupError):continue
        if len(args)>=4 and args[0].decode(errors='ignore')==PYTHON and args[1].decode(errors='ignore')==expected and b'factorial' in args:return True
    return False
def main():
    started=time.monotonic();record=[];execution=LOG/'execution';execution.mkdir(exist_ok=True)
    def run(name,script,args,timeout):
        t=time.monotonic();print(json.dumps(dict(start=name,timeout=timeout)),flush=True)
        with (execution/(name+'.log')).open('w') as log:
            result=subprocess.run([PYTHON,str((HERE/script).relative_to(ROOT)),*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
        record.append(dict(stage=name,returncode=result.returncode,seconds=time.monotonic()-t,log=str((execution/(name+'.log')).relative_to(ROOT))))
        dump(LOG/'continuation_progress.json',dict(status='RUNNING',stages=record))
        if result.returncode:raise RuntimeError(name+' failed; inspect its preserved log')
        print(json.dumps(dict(done=name,seconds=record[-1]['seconds'])),flush=True)
    try:
        deadline=time.monotonic()+PLAN['budgets']['factorial_training_seconds']
        while not (LOG/'factorial_v2/summary.json').exists():
            if time.monotonic()>deadline or not running_factorial():raise RuntimeError('Factorial training stopped without a successful summary')
            time.sleep(2)
        assert json.loads((LOG/'factorial_v2/summary.json').read_text())['status']=='PASS'
        run('raw_validation','prepare_views.py',['--split','val'],PLAN['budgets']['raw_preparation_seconds'])
        run('factorial_evaluation','evaluate_stage.py',['--stage','factorial'],PLAN['budgets']['evaluation_seconds'])
        gate=json.loads((LOG/'factorial_evaluation/augmentation_gate.json').read_text())
        if gate['triggered']:
            previous=json.loads((LOG/'raw/val_summary.json').read_text())['wall_seconds']
            run('raw_train_augmentation','prepare_views.py',['--split','train'],max(1,PLAN['budgets']['raw_preparation_seconds']-previous))
            run('augmentation_training','train_fixed_v2.py',['--stage','augmentation'],PLAN['budgets']['augmentation_training_seconds'])
            run('augmentation_evaluation','evaluate_stage.py',['--stage','augmentation'],PLAN['budgets']['evaluation_seconds'])
        run('single_pass_implementations','build_candidates.py',[],180)
        run('mechanism_attribution','explain_mechanisms.py',[],120)
        dump(LOG/'continuation_summary.json',dict(status='PASS',augmentation_triggered=gate['triggered'],stages=record,wall_seconds=time.monotonic()-started))
        print(json.dumps(dict(status='PASS',augmentation_triggered=gate['triggered'],seconds=time.monotonic()-started)),flush=True)
    except Exception as e:
        dump(LOG/'continuation_summary.json',dict(status='FAILED',error=repr(e),stages=record,wall_seconds=time.monotonic()-started));raise

if __name__=='__main__':main()
