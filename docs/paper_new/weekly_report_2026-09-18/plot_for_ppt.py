"""Small Chinese presentation figure from the exact, frozen result CSV."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent

def main():
    with (HERE/'assets/ppt_representative_results.csv').open(encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    candidates=[Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),Path('C:/Windows/Fonts/msyh.ttc')]
    font=next((p for p in candidates if p.exists()),None)
    if font is None:
        raise RuntimeError('A CJK font is required; configure a local Noto CJK or Microsoft YaHei font path.')
    font_manager.fontManager.addfont(str(font))
    bold=Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc')
    if bold.exists():font_manager.fontManager.addfont(str(bold))
    plt.rcParams.update({'font.family': font_manager.FontProperties(fname=str(font)).get_name(), 'font.size': 16, 'axes.unicode_minus': False, 'pdf.fonttype': 42, 'svg.fonttype': 'path'})
    fig, ax = plt.subplots(figsize=(11.2, 5.5))
    labels = [r['label'] for r in rows]
    for i,r in enumerate(rows):
        value=float(r['composite_percent'])
        color='#125a91' if r['tag']=='combined23' else '#bd671b' if r['tag']=='width28' else '#6e7d88'
        ax.scatter(value, i, color=color, s=120, zorder=3)
        ax.annotate(f'{value:.3f}%', (value,i), xytext=(11,-5), textcoords='offset points', fontsize=17, color=color, weight='bold')
    ax.set_yticks(range(len(rows)), labels)
    ax.invert_yaxis()
    ax.set_ylim(4.65,-.65)
    ax.set_xlim(95.5,97.48)
    ax.set_xticks([95.5,96,96.5,97])
    ax.set_xlabel('五条件综合 Macro-F1（%）',labelpad=10)
    ax.grid(axis='x', alpha=.2)
    ax.set_axisbelow(True)
    for side in ['top','right','left']:
        ax.spines[side].set_visible(False)
    ax.tick_params(axis='y',length=0,pad=10)
    fig.suptitle('维度增加后的平均收益有限，选型还需检查局部退步', fontsize=20, weight='bold', x=.5, y=.975)
    fig.text(.03,.035,'开发集 · 三种子均值 · 不同维数对应不同信息组；蓝色为当前候选，橙色为平均最高但未获选方案。', fontsize=11, color='#465563')
    fig.subplots_adjust(left=.27,right=.975,top=.88,bottom=.20)
    for ext in ['png','pdf','svg']:
        fig.savefig(HERE/'assets'/('ppt_feature_comparison.'+ext),dpi=200,facecolor='white')
    plt.close(fig)

if __name__=='__main__':
    main()
