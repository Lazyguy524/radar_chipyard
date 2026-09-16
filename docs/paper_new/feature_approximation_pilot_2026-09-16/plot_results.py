#!/usr/bin/env python3
"""Export scientific figures from completed results; do not recompute experiments."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
LOG=HERE.parents[2]/'logs/feature_approximation_pilot_20260916'


def main():
    d=json.loads((LOG/'full/summary.json').read_text())
    names=['mean_corrected','eigen_slots_exact','std_slots_exact','angle_slot_exact','range_slots_exact','mean_eigen_corrected']
    labels=['Mean','Covariance slots','Std slots','Azimuth slot','Range slots','Mean + covariance']
    base=d['metrics']['deployment']['macro_f1']
    value=np.array([100*(d['metrics'][n]['macro_f1']-base) for n in names])
    ci=np.array([d['metrics'][n]['paired_sequence_bootstrap_vs_deployment']['delta_macro_f1_percentile95'] for n in names])*100
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    ax=axes[0]
    ax.hlines(np.arange(len(names)),ci[:,0],ci[:,1],color='#446c91',lw=2)
    ax.scatter(value,np.arange(len(names)),color='#153f63',zorder=3)
    ax.set_yticks(np.arange(len(names)),labels);ax.invert_yaxis();ax.axvline(0,color='.55',ls='--',lw=1)
    ax.set_xlabel('Macro-F1 change (percentage points)')
    ax.set_title('Frozen old integer model\nPaired sequence bootstrap, exploratory 95% intervals')
    ax.grid(axis='x',alpha=.2)
    rows=list(csv.DictReader((LOG/'full/group_metrics.csv').open()))
    groups=['power_of_two','power_plus_one','other']
    xx=np.arange(3);width=.33
    for i,(name,label,color) in enumerate([('mean_corrected','Mean','#6b93b8'),('mean_eigen_corrected','Mean + covariance','#cf8448')]):
        values=[]
        for g in groups:
            r=next(r for r in rows if r['mode']==name and r['axis']=='boundary' and r['group']==g)
            values.append(100*(int(r['repair_vs_deployment'])-int(r['harm_vs_deployment']))/int(r['samples']))
        axes[1].bar(xx+(i-.5)*width,values,width,label=label,color=color)
    axes[1].set_xticks(xx,['N = 2^k\n(n=3232)','N = 2^k+1\n(n=4457)','Other N\n(n=72761)'])
    axes[1].set_ylabel('Accuracy change (percentage points)');axes[1].set_title('Conditional diagnostic, not a causal density claim')
    axes[1].legend(frameon=False);axes[1].grid(axis='y',alpha=.2)
    fig.suptitle('80,450 historical validation samples / 27 sequences / no new board experiment',fontsize=11)
    for ext in ['png','pdf']:fig.savefig(HERE/('diagnostic.'+ext),dpi=180)
    plt.close(fig)
    training=LOG/'training/summary.json'
    if training.exists():
        t=json.loads(training.read_text());names=list(t['representation_metrics'])
        labels=['Software statistics','Deployment mirror','Mean + covariance']
        fig,ax=plt.subplots(figsize=(7.8,4.6),layout='constrained')
        for i,seed in enumerate([7,17]):
            vals=[100*t['representation_metrics'][n]['val_macro_f1_by_seed'][i] for n in names]
            ax.plot(np.arange(3),vals,'o-',label='Seed '+str(seed),lw=1.5)
        ax.set_xticks(np.arange(3),labels);ax.set_ylabel('Validation Macro-F1 (%)');ax.grid(axis='y',alpha=.2)
        ax.set_title('Matched retraining: fixed 20 epochs, FP32 MLP\nFrozen INT8 inputs; train-only normalization; not deployed QAT')
        ax.legend(frameon=False)
        fig.supxlabel('Two exploratory seeds; candidate selected on this validation split',fontsize=9)
        for ext in ['png','pdf']:fig.savefig(HERE/('matched_training.'+ext),dpi=180)
        plt.close(fig)
    print(json.dumps(dict(status='FIGURES_EXPORTED',training_figure=training.exists())))


if __name__=='__main__':main()
