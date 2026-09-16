"""Two fixed random forests as a representation crosscheck, not feature search."""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='2'
import csv
import hashlib
import json
from pathlib import Path
import time
import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/conditional_statistics_20260916'
PLAN=json.loads((HERE/'plan.json').read_text())
GROUPS={'position_range':[1,2,7,8,9],'shape':[3,4,5,6,10,11,12],'count_density':[0,13],'doppler':[14,15,16,17],'rcs':[18,19,20]}

def metric(y,p):
    c=np.bincount(y*2+p,minlength=4).reshape(2,2);den=c.sum(0)+c.sum(1)
    f=np.divide(2*np.diag(c),den,out=np.zeros(2),where=den>0)
    return dict(macro_f1=float(f.mean()),accuracy=float(np.trace(c)/c.sum()),confusion_matrix=c.tolist())
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def main():
    out=LOG/'rf';out.mkdir(exist_ok=False);started=time.monotonic();cfg=PLAN['rf']
    y=np.load(LOG/'data/train/labels.npy');vy=np.load(LOG/'data/val/labels.npy');dy=np.load(LOG/'data/diagnostic/labels.npy')
    with (LOG/'data/diagnostic/metadata.csv').open() as f:seq=np.array([r['sequence'] for r in csv.DictReader(f)])
    reports=[];permutations=[]
    for mode in cfg['representations']:
        if time.monotonic()-started>PLAN['budget']['rf_seconds']:raise TimeoutError('RF budget')
        x=np.load(LOG/'data/train'/(mode+'.npy'));vx=np.load(LOG/'data/val'/(mode+'.npy'))
        model=RandomForestClassifier(**{k:cfg[k] for k in ['random_state','n_estimators','max_depth','min_samples_leaf','max_samples','class_weight','n_jobs']})
        model.fit(x,y);joblib.dump(model,out/(mode+'.joblib'))
        p=model.predict(vx);np.save(out/(mode+'_validation_predictions.npy'),p)
        diagnostic={}
        for condition in PLAN['diagnostics']['paired_conditions']:
            xx=np.load(LOG/'data/diagnostic'/(mode+'_'+condition+'.npy'));pred=model.predict(xx)
            np.save(out/(mode+'_'+condition+'_predictions.npy'),pred);diagnostic[condition]=metric(dy,pred)
        clean=np.load(LOG/'data/diagnostic'/(mode+'_clean.npy'));baseline=diagnostic['clean']['macro_f1']
        for name,columns in GROUPS.items():
            changes=[]
            for repeat in range(cfg['group_permutation_repeats']):
                if time.monotonic()-started>PLAN['budget']['rf_seconds']:raise TimeoutError('RF permutation budget')
                rng=np.random.default_rng(20260916+repeat);z=clean.copy()
                for sid in sorted(set(seq)):
                    ids=np.flatnonzero(seq==sid);donor=rng.permutation(ids)
                    z[np.ix_(ids,columns)]=clean[np.ix_(donor,columns)]
                value=metric(dy,model.predict(z))['macro_f1'];changes.append(baseline-value)
            permutations.append(dict(mode=mode,group=name,columns=columns,macro_f1_drop_repeats=changes,mean_drop=float(np.mean(changes))))
        report=dict(mode=mode,validation=metric(vy,p),diagnostic=diagnostic,impurity_importance=model.feature_importances_.tolist())
        reports.append(report);dump(out/(mode+'_summary.json'),report)
        print(json.dumps(dict(mode=mode,validation=report['validation'],wall_seconds=time.monotonic()-started)),flush=True)
    result=dict(status='PASS',reports=reports,group_permutation=permutations,wall_seconds=time.monotonic()-started,
        environment=dict(python=__import__('sys').version,numpy=np.__version__,sklearn=sklearn.__version__),
        plan_sha256=hashlib.sha256((HERE/'plan.json').read_bytes()).hexdigest(),
        interpretation='Two fixed classifier-family controls. Grouped within-sequence permutation on diagnostic clean subset, 3 repeats. Not a deletion ranking, causal importance, independent test or deployed RF.')
    dump(out/'summary.json',result);print(json.dumps(dict(status='PASS',wall_seconds=result['wall_seconds'])),flush=True)

if __name__=='__main__':main()
