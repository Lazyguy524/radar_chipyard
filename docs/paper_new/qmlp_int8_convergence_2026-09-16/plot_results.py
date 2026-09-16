"""Standalone scientific plots from completed runs, no further model fitting."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
LOG=HERE.parents[2]/'logs/qmlp_int8_convergence_20260916'

def main():
    verified=json.loads((LOG/'verification/summary.json').read_text())
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for seed in [7,17]:
        r=json.loads((LOG/'training'/f'seed{seed}'/'summary.json').read_text())
        curve=[c for c in r['curve'] if c['phase']=='qat'];epochs=[c['epoch'] for c in curve]
        axes[0].plot(epochs,[c['train_probe_ce'] for c in curve],label=f'Seed {seed}')
        axes[0].scatter([epochs[-1]],[curve[-1]['train_probe_ce']],s=25)
        axes[1].plot([0]+epochs,[100*r['ptq_validation']['macro_f1']]+[100*c['validation_macro_f1'] for c in curve],label=f'Seed {seed}')
    axes[0].set_xlabel('QAT epoch');axes[0].set_ylabel('Weighted cross entropy')
    axes[0].set_title('Fixed train calibration-subset loss\nStopping uses this loss only')
    axes[1].axhline(100*verified['old_deployment_validation']['macro_f1'],color='.4',ls='--',label='Old integer deployment mirror')
    axes[1].set_xlabel('QAT epoch (0 = PTQ before QAT)');axes[1].set_ylabel('Validation Macro-F1 (%)')
    axes[1].set_title('Integer forward / 80,450 validation rows\nFinal epoch retained; no best-validation selection')
    for ax in axes:ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=8)
    fig.suptitle('Frozen scales, folded normalization, full training split / no new board run',fontsize=11)
    for ext in ['png','pdf']:fig.savefig(HERE/('convergence.'+ext),dpi=180)
    plt.close(fig)
    print('FIGURES_WRITTEN')

if __name__=='__main__':main()
