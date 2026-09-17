"""Shareable plots from frozen development tables; no new analysis choices."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/feature_ablation_20260917'

def main():
    out=HERE/'figures';out.mkdir(exist_ok=True)
    rows=json.loads((LOG/'evaluation/metrics.json').read_text());m={(r['tag'],r['seed'],r['condition']):r for r in rows}
    plan=json.loads((HERE/'plan.json').read_text());tags=['dedup20','no_rcs18','less_shape16'];conditions=plan['evaluation']['conditions'];seeds=[7,17,37]
    with (LOG/'evaluation/paired_sequence_intervals.csv').open() as f:intervals=list(csv.DictReader(f))
    data=np.array([[100*np.mean([m[(t,s,c)]['macro_f1']-m[('full21',s,c)]['macro_f1'] for s in seeds]) for c in conditions] for t in tags])
    fig,axes=plt.subplots(2,1,figsize=(12,6.8),gridspec_kw={'height_ratios':[1.2,1]})
    lim=max(.3,np.max(np.abs(data)));im=axes[0].imshow(data,cmap='RdBu',vmin=-lim,vmax=lim,aspect='auto');axes[0].set_xticks(range(len(conditions)),[c.replace('uniform_','u_').replace('sparse_','real_') for c in conditions],rotation=45,ha='right');axes[0].set_yticks(range(3),tags)
    for i in range(3):
        for j in range(len(conditions)):axes[0].text(j,i,f'{data[i,j]:+.2f}',ha='center',va='center',fontsize=8,color='white' if abs(data[i,j])>.55*lim else 'black')
    axes[0].set_title('Mean Macro-F1 change vs matched full21 (percentage points)');fig.colorbar(im,ax=axes[0],fraction=.025)
    for i,t in enumerate(tags):
        r=next(r for r in intervals if r['tag']==t and r['reference']=='full21' and r['condition']=='composite' and r['seed']=='mean3');d,lo,hi=[100*float(r[k]) for k in ['delta','low','high']]
        axes[1].plot([lo,hi],[i,i],color='#287a9a',linewidth=2);axes[1].scatter(d,i,color='#287a9a',s=45)
        for s in seeds:
            r=next(r for r in intervals if r['tag']==t and r['reference']=='full21' and r['condition']=='composite' and r['seed']==str(s));axes[1].scatter(100*float(r['delta']),i+.18,s=18,color='#777777')
    axes[1].set_yticks(range(3),tags);axes[1].invert_yaxis();axes[1].axvline(0,color='black',lw=.8);axes[1].axvline(-.1,color='#b45645',linestyle='--',lw=1,label='Frozen composite tolerance');axes[1].set_xlabel('Composite change (percentage points)');axes[1].set_title('Three-seed mean and paired whole-sequence 95% interval; gray dots = seeds');axes[1].legend(fontsize=8)
    fig.suptitle('Feature ablation on reused development data — no independent significance claim',fontsize=12);fig.tight_layout()
    for ext in ['png','pdf']:fig.savefig(out/('ablation_quality.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)
    with (HERE/'costs.csv').open() as f:cost=list(csv.DictReader(f))
    with (HERE/'results.csv').open() as f:results=list(csv.DictReader(f))
    fig,ax=plt.subplots(figsize=(7,4))
    for c in cost:
        t=c['tag'];r=next(r for r in results if r['tag']==t);x=int(c['network_macs']);y=100*float(r['composite']);ax.scatter(x,y,s=70);ax.annotate(t,(x,y),xytext=(5,6),textcoords='offset points')
    ax.set_xlabel('Network MACs per inference (operation count, not latency)');ax.set_ylabel('Five-condition composite Macro-F1 (%)');ax.set_title('Quality vs network arithmetic; frontend costs reported separately');ax.grid(alpha=.2);fig.tight_layout()
    for ext in ['png','pdf']:fig.savefig(out/('quality_cost.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)
if __name__=='__main__':main()
