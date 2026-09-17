"""Standalone figures; all trained seeds and explicit cost dimensions."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/feature_dimension_sweep_20260917'

def read(p):
    with p.open() as f:return list(csv.DictReader(f))
def save(fig,name):
    (HERE/'figures').mkdir(exist_ok=True)
    for ext in ['png','pdf']:fig.savefig(HERE/'figures'/(name+'.'+ext),dpi=170,bbox_inches='tight')
    plt.close(fig)

def main():
    data={r['tag']:r for r in read(HERE/'results.csv')};cost={r['tag']:r for r in read(HERE/'costs.csv')};intervals=read(LOG/'evaluation/paired_sequence_intervals.csv');plan=json.loads((HERE/'plan.json').read_text())
    order=['core8','proxy12','distribution12','combined15','base16','support17','combined23','support24','width28','asymmetry28','quantile32','full36','redundant36']
    color={t:('#777777' if t in ['base16','combined23'] else {'reduction':'#23789b','support':'#459260','quantile':'#bf6d34','redundant_control':'#975ba6'}[plan['variants'][t]['family']]) for t in order}
    fig,axes=plt.subplots(1,2,figsize=(12,7.5))
    for i,t in enumerate(order):
        r=data[t];xs=[100*float(r['seed'+str(s)]) for s in [7,17,37]];axes[0].scatter(xs,[i-.15,i,i+.15],s=20,color=color[t]);axes[0].scatter(100*float(r['composite']),i,marker='|',s=100,color='black')
        ci=next((r for r in intervals if r['tag']==t and r['reference']=='combined23' and r['condition']=='composite' and r['seed']=='mean3'),None)
        if ci:
            d,lo,hi=[100*float(ci[k]) for k in ['delta','low','high']];axes[1].plot([lo,hi],[i,i],lw=1.7,color=color[t]);axes[1].scatter(d,i,s=25,color=color[t])
    for ax in axes:ax.set_yticks(range(len(order)),order);ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
    axes[0].set_xlabel('Composite Macro-F1 (%)');axes[0].set_title('Three seeds; black = mean')
    axes[1].axvline(0,color='black',lw=.7);axes[1].axvline(.1,color='gray',lw=.7,linestyle='--');axes[1].set_xlabel('Change vs previous23 (percentage points)');axes[1].set_title('Paired whole-sequence 95% interval')
    fig.suptitle('Fixed dimension sweep on reused development data');fig.tight_layout();save(fig,'quality')
    fig,ax=plt.subplots(figsize=(10,6))
    offsets={'proxy12':(-53,10),'distribution12':(8,-15),'combined15':(8,2),'width28':(-42,12),'asymmetry28':(6,-18),'full36':(-10,22),'quantile32':(-25,10),'redundant36':(-15,-25),'combined23':(5,-18),'support24':(8,8)}
    for t in order:
        x=int(cost[t]['network_macs']);y=100*float(data[t]['composite']);sort=int(cost[t]['channel_sorts'])>0
        ax.scatter(x,y,marker='s' if sort else 'o',s=65,color=color[t]);ax.annotate(t,(x,y),xytext=offsets.get(t,(7,4)),textcoords='offset points',fontsize=8,arrowprops=dict(arrowstyle='-',color='#888888',lw=.5))
    ax.margins(y=.12)
    ax.set_xlabel('Network MACs per observation (frontend costs shown separately)');ax.set_ylabel('Composite Macro-F1 (%)');ax.set_title('Circles: no channel sorting; squares: four channel sorts\nAnalytical counts only; no FPGA latency or power claim');ax.grid(alpha=.2);fig.tight_layout();save(fig,'cost')
    rows=json.loads((LOG/'explanation/exact_N_metrics.json').read_text());fig,axes=plt.subplots(1,2,figsize=(12,4.7));groups=['N1','N2','N3','N4to8','Nge9']
    for ax,c in zip(axes,['sparse_single','sparse_context']):
        for t in ['combined23','support24','quantile32','full36']:
            ys=[]
            for g in groups:
                a=[r['accuracy'] for r in rows if r['tag']==t and r['condition']==c and r['group']==g];ys.append(100*np.mean(a) if a else np.nan)
            ax.plot(range(5),ys,marker='o',label=t)
        counts={g:next((r['samples'] for r in rows if r['tag']=='combined23' and r['seed']==7 and r['condition']==c and r['group']==g),0) for g in groups}
        ax.set_xticks(range(5),[g+'\nn='+str(counts[g]) for g in groups]);ax.set_ylabel('Accuracy (%)');ax.set_title(c);ax.set_xlabel('Actual retained point count; empty groups have no point');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Descriptive exact-count slices; three-seed means, not independent tests');fig.tight_layout();save(fig,'low_points')
    case=json.loads((LOG/'synthetic_preflight.json').read_text())['counterexamples'][0];fig,ax=plt.subplots(figsize=(7,4.5))
    for key,name in [('first','cluster A'),('second','cluster B')]:
        x=np.sort(np.array(case[key])[:,3]/256);ax.step(x,np.arange(1,len(x)+1)/len(x),where='post',marker='o',label=name)
    ax.set_xlabel('RCS input units');ax.set_ylabel('Empirical cumulative fraction');ax.set_title('Same integer23 features, different quartile descriptors\nUnlabeled representation example, not a classification result');ax.legend();ax.grid(alpha=.2);fig.tight_layout();save(fig,'counterexample')

if __name__=='__main__':main()
