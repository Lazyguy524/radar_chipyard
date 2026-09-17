"""Standalone research figures from frozen measurements and unlabeled cases."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/feature_enrichment_20260917'
def save(fig,name):
    out=HERE/'figures';out.mkdir(exist_ok=True)
    for ext in ['png','pdf']:fig.savefig(out/(name+'.'+ext),dpi=170,bbox_inches='tight')
    plt.close(fig)
def main():
    with (HERE/'results.csv').open() as f:results=list(csv.DictReader(f))
    with (LOG/'evaluation/paired_sequence_intervals.csv').open() as f:intervals=list(csv.DictReader(f))
    tags=['base16','geometry19','distribution20','combined23','redundant23'];colors={t:plt.get_cmap('tab10')(i) for i,t in enumerate(tags)};fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for i,t in enumerate(tags):
        r=next(r for r in results if r['tag']==t);vals=[100*float(r['seed'+str(s)]) for s in [7,17,37]];axes[0].scatter(vals,[i-.1,i,i+.1],s=25,color=colors[t]);axes[0].scatter(100*float(r['composite']),i,marker='|',s=120,color='black')
    axes[0].set_yticks(range(5),tags);axes[0].invert_yaxis();axes[0].set_xlabel('Five-condition composite Macro-F1 (%)');axes[0].set_title('All three seeds; black mark = mean')
    for i,t in enumerate(tags[1:]):
        r=next(r for r in intervals if r['tag']==t and r['reference']=='base16' and r['condition']=='composite' and r['seed']=='mean3');d,lo,hi=[100*float(r[k]) for k in ['delta','low','high']];axes[1].plot([lo,hi],[i,i],lw=2,color=colors[t]);axes[1].scatter(d,i,s=40,color=colors[t])
    axes[1].set_yticks(range(4),tags[1:]);axes[1].invert_yaxis();axes[1].axvline(0,color='black',lw=.8);axes[1].axvline(.1,color='gray',linestyle='--',lw=.8);axes[1].set_xlabel('Change vs base16 (percentage points)');axes[1].set_title('Paired whole-sequence 95% intervals')
    fig.suptitle('Feature enrichment on reused development data; no independent significance claim');fig.tight_layout();save(fig,'quality')
    cases=json.loads((LOG/'synthetic_preflight.json').read_text())['counterexamples'];fig,axes=plt.subplots(2,2,figsize=(10,8))
    for ax,c in zip(axes.ravel(),cases):
        a=np.array(c['first'])/256;b=np.array(c['second'])/256
        if c['name'] in ['interior_spread','diagonal_orientation']:
            ax.scatter(a[:,0],a[:,1],s=90,facecolors='none',edgecolors='#247ca7',linewidth=2,label='cluster A');ax.scatter(b[:,0],b[:,1],s=65,marker='x',color='#c05245',label='cluster B');ax.set_xlabel('x (m)');ax.set_ylabel('y (m)');ax.set_aspect('equal')
            for name,points,color in [('A',a,'#247ca7'),('B',b,'#c05245')]:
                coords,counts=np.unique(points[:,:2],axis=0,return_counts=True)
                for point,count in zip(coords,counts):
                    if count>1:ax.annotate(name+' x'+str(count),point,xytext=(8,8),textcoords='offset points',color=color,fontsize=9)
        else:
            j=2 if c['name']=='velocity_distribution' else 3;ax.plot(np.sort(a[:,j]),np.arange(1,8)/7,marker='o',drawstyle='steps-post',label='cluster A');ax.plot(np.sort(b[:,j]),np.arange(1,8)/7,marker='x',drawstyle='steps-post',label='cluster B');ax.set_xlabel('Compensated radial velocity (m/s)' if j==2 else 'RCS input units');ax.set_ylabel('Empirical cumulative fraction')
        ax.set_title(c['name']+'\nSame integer base16, different added descriptors');ax.legend(fontsize=8);ax.grid(alpha=.15)
    fig.suptitle('Unlabeled representation counterexamples — not classification evidence');fig.tight_layout();save(fig,'counterexamples')
    mc=json.loads((LOG/'explanation/point_count_simulation.json').read_text())['rows'];fig,ax=plt.subplots(figsize=(8,4.5))
    for name in ['uniform','central','two_lobes']:
        rows=[r for r in mc if r['distribution']==name];n=[r['points'] for r in rows];mu=[r['mean'] for r in rows];lo=[r['q10'] for r in rows];hi=[r['q90'] for r in rows];line=ax.plot(n,mu,marker='o',label=name)[0];ax.fill_between(n,lo,hi,color=line.get_color(),alpha=.12)
    ax.set_xscale('log',base=2);ax.set_xticks([1,2,4,8,16,32,64],[1,2,4,8,16,32,64]);ax.set_xlabel('Number of points');ax.set_ylabel('Quantized 4Var(x) / span(x)^2');ax.set_title('Unlabeled simulation: point count can dominate shape descriptors\n2000 draws/cell; mean and 10–90% interval');ax.legend();ax.grid(alpha=.2);fig.tight_layout();save(fig,'point_count_degeneracy')
if __name__=='__main__':main()
