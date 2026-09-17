"""Complete the frozen evaluation and review pipeline once, without retraining."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOG = ROOT / 'logs/feature_enrichment_20260917'


def main():
    assert json.loads((LOG / 'training/summary.json').read_text())['status'] == 'PASS'
    journal = LOG / 'finishing_stage_times.json'
    assert not journal.exists(), 'Preserve the previous attempt and review before resuming.'
    started = time.monotonic()
    budget = json.loads((HERE / 'plan.json').read_text())['budget']['evaluation_and_package_seconds']
    env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
    records = []
    stages = ['evaluate.py', 'build_package.py', 'explain.py', 'point_count_simulation.py', 'report.py', 'plot_results.py']
    for name in stages:
        interpreter = '/tmp/gemmini_qmlp_plot_venv_20260915/bin/python' if name == 'plot_results.py' else sys.executable
        remaining = budget - (time.monotonic() - started)
        assert remaining > 0, 'Finishing budget exhausted; keep outputs, do not add training.'
        at = time.monotonic()
        record = dict(stage=name, status='RUNNING', elapsed_before=at-started)
        records.append(record)
        def save(status):
            journal.write_text(json.dumps(dict(status=status, stages=records, wall_seconds=time.monotonic()-started,
                scope='Includes evaluation, C packaging, explanations and plots; archive/sync are recorded separately.'), indent=2)+'\n')
        save('RUNNING')
        try:
            with (LOG / (name.removesuffix('.py') + '_stdout.log')).open('x') as output:
                result = subprocess.run([interpreter, '-u', str(HERE / name)], cwd=ROOT, env=env,
                                        stdout=output, stderr=subprocess.STDOUT, timeout=remaining)
            record.update(status='PASS' if result.returncode == 0 else 'FAIL', returncode=result.returncode)
            assert result.returncode == 0, name
        except Exception as error:
            record.update(status='FAIL', error=repr(error), wall_seconds=time.monotonic()-at)
            save('FAIL')
            raise
        record['wall_seconds'] = time.monotonic()-at
        save('RUNNING')
        print(json.dumps(record), flush=True)
    save('PASS')


if __name__ == '__main__':
    main()
