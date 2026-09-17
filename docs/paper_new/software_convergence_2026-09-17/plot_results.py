"""Standalone thesis figure from frozen tables; no fitting or model selection."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/software_convergence_20260917'

def main():
    with (HERE/'results.csv').open() as f:rows=list(csv.DictReader(f))
    with (LOG/'evaluation/paired_sequence_intervals.csv').open() as f:intervals=list(csv.DictReader(f))
    tags=['A','B','proxy_synthetic','proxy_natural','mean_synthetic','mean_natural']
    names=['A: original','B: prior augmentation','Proxy + synthetic','Proxy + natural','Mean + synthetic','Mean + natural']
    fig,axes=plt.subplots(1,2,figsize=(11.5,4),gridspec_kw={'width_ratios':[1,1.05]})
    colors=['#777777','#222222','#2377b4','#0c8f85','#cb821b','#ad446c']
    for i,(tag,name,color) in enumerate(zip(tags,names,colors)):
        r=next(r for r in rows if r['tag']==tag and r['condition']=='composite')
        vs=np.array([float(r['seed7']),float(r['seed17']),float(r['seed37'])])*100
        axes[0].scatter(vs,np.array([i-.09,i,i+.09]),s=25,color=color)
        axes[0].scatter(float(r['mean'])*100,i,s=60,color=color,marker='|',linewidth=2)
    axes[0].set_yticks(range(len(tags)),names);axes[0].invert_yaxis();axes[0].set_xlabel('Five-condition composite Macro-F1 (%)')
    axes[0].set_title('Q24 reference: all three seeds')
    for i,tag in enumerate(tags[2:]):
        r=next(r for r in intervals if r['tag']==tag and r['reference']=='B' and r['condition']=='composite' and r['seed']=='mean3')
        lo,hi=float(r['low'])*100,float(r['high'])*100;v=float(r['delta'])*100
        axes[1].plot([lo,hi],[i,i],color=colors[i+2],lw=2);axes[1].scatter(v,i,color=colors[i+2],s=35)
    axes[1].axvline(0,color='#777777',lw=.8);axes[1].axvline(.1,color='#777777',ls=':',lw=.8)
    axes[1].set_yticks(range(4),names[2:]);axes[1].invert_yaxis();axes[1].set_xlabel('Composite difference vs B (percentage points)')
    axes[1].set_title('Paired whole-sequence 95% intervals')
    for ax in axes:ax.grid(axis='x',alpha=.2);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Software development comparison — reused validation data',fontsize=12)
    fig.tight_layout();out=HERE/'figures';out.mkdir(exist_ok=True)
    for suffix in ['png','pdf']:fig.savefig(out/('software_comparison.'+suffix),dpi=180,bbox_inches='tight')
    plt.close(fig)
if __name__=='__main__':main()
