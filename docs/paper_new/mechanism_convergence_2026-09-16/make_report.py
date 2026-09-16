"""Assemble the completed studies into comparable tables and Chinese figures."""
import csv
import json
from pathlib import Path
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/mechanism_convergence_20260916'
ENC=ROOT/'logs/moment_encoding_20260916';EDOC=ROOT/'docs/paper_new/moment_encoding_2026-09-16'
def get(p):return json.loads(Path(p).read_text())
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def avg(report,mode,condition,seeds,view=False):
    key='sparse_metrics' if view else 'metrics';field='view' if view else 'condition'
    a=np.array([r['macro_f1'] for r in report[key] if r['mode']==mode and r[field]==condition and r['seed'] in seeds])*100
    assert len(a)==len(seeds);return float(a.mean()),float(a.std(ddof=1))
def main():
    assert get(LOG/'continuation_summary.json')['status']=='PASS' and get(ENC/'continuation_summary.json')['status']=='PASS'
    a=get(LOG/'factorial_evaluation/summary.json');b=get(LOG/'augmentation_evaluation/summary.json');c=get(ENC/'evaluation/summary.json')
    p=get(ENC/'preflight.json');audit=get(LOG/'mechanism_audit/summary.json');seeds=[7,17,37];five=[7,17,37,47,57]
    names={'proxy':'旧代理＋逐特征定标','mean':'只修正均值','shape':'只替换空间矩','moment':'均值＋空间矩','linear_fine':'矩＋更细线性定标','root':'矩＋开平方编码'}
    primary=['clean','uniform_half_0','uniform_quarter_0','central_half'];cnames=['原始 K7','均匀保留一半','均匀保留四分之一','中心保留一半']
    font=subprocess.check_output(['fc-match','Noto Sans CJK SC','--format=%{file}'],text=True).strip();font_manager.fontManager.addfont(font)
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=font).get_name(),'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    figures=HERE/'figures';figures.mkdir(exist_ok=True)
    def save(f,name):f.savefig(figures/(name+'.png'),dpi=180,bbox_inches='tight');f.savefig(figures/(name+'.pdf'),bbox_inches='tight');plt.close(f)
    f,axes=plt.subplots(2,2,figsize=(11,7),sharey=True)
    for ax,condition,title in zip(axes.flat,primary,cnames):
        for j,mode in enumerate(['proxy','mean','shape','moment']):
            values=np.array([r['macro_f1'] for r in a['metrics'] if r['mode']==mode and r['condition']==condition])*100
            ax.scatter(j+np.linspace(-.12,.12,5),values,s=24,color='#597da0',alpha=.8)
            ax.errorbar(j,values.mean(),yerr=values.std(ddof=1),fmt='D',color='#8d432f',capsize=4,markersize=5)
        ax.set_xticks(range(4),['原代理','均值修正','空间矩','两者组合']);ax.set_title(title);ax.grid(axis='y',alpha=.2)
    axes[0,0].set_ylabel('Macro-F1 (%)');axes[1,0].set_ylabel('Macro-F1 (%)')
    f.suptitle('完整验证集 80,450 条；五种子、相同训练轮数\n散点为单种子，菱形为均值，误差棒为种子间样本标准差');f.tight_layout();save(f,'factorial_five_seeds')
    configs=[('A 原代理',a,'proxy'),('A 均值修正',a,'mean'),('A 共享矩',a,'moment'),('B 原代理＋扰动训练',b,'proxy'),('B 均值＋扰动训练',b,'mean'),('B 矩＋扰动训练',b,'moment'),('C 更细线性定标',c,'linear_fine'),('C 开平方编码',c,'root')]
    columns=['clean','uniform_quarter_0','central_half','kept_single','sparse_single','sparse_context']
    matrix=np.array([[avg(r,m,case,seeds,case.startswith('sparse'))[0] for case in columns] for _,r,m in configs])
    f,ax=plt.subplots(figsize=(11,6));im=ax.imshow(matrix,cmap='YlGnBu',vmin=88,vmax=99,aspect='auto')
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):ax.text(j,i,f'{matrix[i,j]:.2f}',ha='center',va='center',color='white' if matrix[i,j]>95 else 'black')
    ax.set_yticks(range(len(configs)),[v[0] for v in configs]);ax.set_xticks(range(6),['原始 K7','均匀 1/4','中心 1/2','保留观测\n只用当前帧','被过滤观测\n当前 1/2 点','被过滤观测\n保留历史上下文'])
    ax.set_title('相同三个种子的平均 Macro-F1 (%)\n前四列为 80,450 个保留观测，后两列为 97,734 个真实被过滤观测')
    f.colorbar(im,ax=ax,shrink=.75);f.tight_layout();save(f,'training_encoding_coverage')
    old=get(ROOT/'logs/conditional_statistics_20260916/data/summary.json')
    original=next(v for v in old['output_quantization_profiles'] if v['split']=='val' and v['mode']=='moment24')['zero_fraction']
    j=[3,4,10,11,12];profiles=[original]+[next(v for v in p['output_profiles'] if v['split']=='val' and v['mode']==m)['zero_fraction'] for m in ['linear_fine','root']]
    f,ax=plt.subplots(figsize=(10,4.5))
    for i,(values,label,color) in enumerate(zip(profiles,['原线性 99.99% 标定','更细线性 99% 标定','开平方后 99.99% 标定'],['#617a91','#ce874f','#248277'])):
        ax.bar(np.arange(5)+(i-1)*.24,np.array(values)[j]*100,width=.23,label=label,color=color)
    ax.set_xticks(range(5),['x 离散程度','y 离散程度','xy 交叉统计','较大离散程度','较小离散程度']);ax.set_ylabel('输出为零的验证观测比例 (%)');ax.set_ylim(0,100)
    ax.legend(fontsize=9);ax.set_title('同一二阶信息，输出编码决定能否保留小尺度变化');ax.grid(axis='y',alpha=.2);f.tight_layout();save(f,'output_zero_rates')
    t1=table(['表示']+cnames,[[names[m]]+[f'{avg(a,m,k,five)[0]:.4f} ± {avg(a,m,k,five)[1]:.4f}' for k in primary] for m in ['proxy','mean','shape','moment']])
    t2=table(['训练/表示','原始 K7','均匀 1/4','中心 1/2','保留观测当前帧','过滤观测 1/2 点','过滤观测＋历史'],[[name]+[f'{avg(r,m,k,seeds,k.startswith("sparse"))[0]:.4f}' for k in columns] for name,r,m in configs])
    t3=table(['条件','效应','五种子均值差 pp','配对序列＋种子重采样 95% 区间 pp'],[[r['condition'],r['effect'],f'{r["mean"]*100:+.4f}',f'[{r["percentile95"][0]*100:+.4f}, {r["percentile95"][1]*100:+.4f}]'] for r in a['factorial_effects'] if r['condition'] in ['clean','uniform_quarter_0','central_half'] and r['effect'] in ['mean_with_proxy_shape','shape_after_mean','interaction']])
    precision=[]
    for report,m,label,s in [(a,'mean','均值修正 A',five),(a,'moment','共享矩 A',five),(b,'proxy','原代理 B',seeds),(b,'mean','均值修正 B',seeds),(b,'moment','共享矩 B',seeds),(c,'linear_fine','更细线性 C',seeds),(c,'root','开平方 C',seeds)]:
        if m=='proxy':continue
        row=[label]
        for bits in [(8,8),(12,12),(16,16),(12,24),(24,12)]:
            selected=[r for r in report['precision_acceptance'] if r['mode']==m and r['seed'] in s and (r['mean_bits'],r['moment_bits'])==bits]
            assert len(selected)==len(s);row.append(f'{sum(r["accepted"] for r in selected)}/{len(s)}')
        precision.append(row)
    t4=table(['模型/训练','均值8/空间8','12/12','16/16','12/24','24/12'],precision)
    t5=table(['编码','x/y 两槽输出尺度指数 e','验证 x/y 输出零比例','验证空间槽位最大实际限幅比例'],[[m,str(get(ENC/'data/scales.json')['exponents'][m][3:5]),
        '/'.join(f'{next(v for v in p["output_profiles"] if v["split"]=="val" and v["mode"]==m)["zero_fraction"][k]*100:.4f}%' for k in [3,4]),
        f'{max(next(v for v in p["output_profiles"] if v["split"]=="val" and v["mode"]==m)["actual_clipped_fraction"][k] for k in j)*100:.4f}%'] for m in ['linear_fine','root']])
    duplicate_text='；'.join(r['mode']+'：'+str(r['columns']) for r in audit['exact_duplicate_pairs']) or '未发现全 train 和 validation 同时精确相同的槽位对'
    training_seconds=sum(get(path)['wall_seconds'] for path in [LOG/'factorial_v2/summary.json',LOG/'augmentation_v2/summary.json',ENC/'training/summary.json'])
    report=f'''# 扩展试验结果与所得认识

2026-09-16。完成 **35 条固定轮数训练轨迹**：四组机制×五种子 20 条、三表示×三种子的扰动训练 9 条、两种输出编码×三种子 6 条。每条都是完整 train 357,780 条、20 轮 FP32＋60 轮冻结 QAT，固定采用第 60 轮，未挑验证最高 checkpoint。前一次研究的提前停止模型只作历史，不混入新公平对照。

训练总耗时 {training_seconds/60:.2f} 分钟，CPU 2 线程，GPU 0。验证仍为熟悉的 27 序列/80,450 条；新增检查 97,734 个真实被过滤的目标类有轨迹观测。派生输入和多个 seed 不是新增独立数据集。旧 test 不再参与本轮。

## 1. 五种子机制拆分：修正收益不能直接相加

固定原 21 个槽位，只改变均值路径与五个空间统计槽。A 阶段全部使用原始训练输入，输出定标沿用此前 train 冻结结果。

{t1}

表中为 Macro-F1 % 的均值±种子间标准差，不是置信区间。共同 seed 为 7/17/37/47/57；同 seed 初始网络哈希一致，训练更新次数一致。

![五种子机制对照](figures/factorial_five_seeds.png)

{t3}

`shape_after_mean` 是增加空间矩相对只修正均值；`interaction` 为“两者组合−均值−空间矩＋原代理”。非零交互说明两种修正的模型收益不能机械相加。区间采用整序列和匹配 seed 重采样 2,000 次，属于探索性证据，未校正多重比较及长期使用 validation 的选择效应。

完整结果：[A 评价](../../../logs/mechanism_convergence_20260916/factorial_evaluation/summary.json)、[A 条件及交叉分组](../../../logs/mechanism_convergence_20260916/factorial_evaluation/conditional_groups.csv)。支持门槛为 ≥100 条、≥3 序列、两类均存在；不把不充分的组补成 0 分。

## 2. 训练覆盖、统计和输出编码分别比较

B 阶段由预先门槛触发：至少 4/5 个原代理 seed 在均匀四分之一或中心一半条件损失 ≥1 个 F1 百分点。训练每轮仍访问每个原样本一次，输入视图按 50% 原始、25% 均匀四分之一、25% 中心一半选择；统计量、类别权重与轨迹划分保持对应约束，标准化和 QAT 校准仅使用 train 混合分布。没有额外训练数据标签、教师、网络结构或损失搜索。

C 是另行冻结的六条编码试验，针对发现的二阶量输出大量为零；它没有做扰动训练。下表统一仅取 seed 7/17/37，避免拿五种子平均与三种子平均解释纯训练差。

{t2}

![训练、编码及覆盖对照](figures/training_encoding_coverage.png)

前四列对应相同的保留观测身份；后两列来自原 min_points=3 过滤掉的观测，不能把跨列差值当同一群体的因果下降。所有输入仍基于 GT track；模拟删点尚非经过标定的遮挡模型。

每次均匀减点实际做了三个固定随机重复，中心保留一半与均匀保留一半使用相同保留点数；另外检查坐标小数位 8→6/4。完整逐 seed/重复、类别 F1、混淆矩阵及有害/修复翻转保留在 [A 汇总](../../../logs/mechanism_convergence_20260916/factorial_evaluation/summary.json)、[B 汇总](../../../logs/mechanism_convergence_20260916/augmentation_evaluation/summary.json)与 [C 汇总](../../../logs/moment_encoding_20260916/evaluation/summary.json)，不能只挑一条最好的减点随机序列。

## 3. 更准确的二阶矩，可能被输出量化消掉

原 Q24 空间统计的 x/y 原始方差在完整验证集中均非零，最终 INT8 却分别有 **67.1361%/91.2020%** 为零。这里直接核对了原始整数矩和输出值，不能把这些零解释为所有目标都没有空间变化。

原因是方差与标准差的动态范围不同，而原试验对方差按高百分位做均匀 INT8 定标。平方根编码将方差变为标准差，对协方差使用保留符号的平方根，复用两轴标准差得到最大/最小输出；不增加点循环中的乘积数量，但增加三次簇末整数平方根。

{t5}

![输出为零比例](figures/output_zero_rates.png)

更细线性方案是必要对照：只降低空间槽的标定百分位，判断是否用简单的尾部限幅就能恢复足够信息。不得把尺度变化的全部收益记在非线性变换名下。C 的计划、Python/C 全量根号一致性及训练协议见[输出编码专项](../moment_encoding_2026-09-16/README.md)。

## 4. 位宽结论要与输出编码及共享依赖一起看

固定每个已经训练好的权重，仅更换均值/空间矩倒数精度；对四个主要条件及支持充分的点数、形态、交叉组检查。以下为通过所有门槛的 seed 数/全部 seed 数，门槛为整体 F1 下降≤0.1 pp、组 accuracy 下降≤0.5 pp。它是预定探索约束，不是业务安全指标。

{t4}

最小可用位宽是当前表示、权重、条件和支持范围下的结果。尤其不能用粗输出下“不敏感”的结果，直接替细输出做精度保证。单组接近 100 条时少数翻转就可能触发保守门槛，未通过也不等于证明统计显著损害。

均值和协方差共用一阶和与倒数。把两个输出分别降到各自最低位宽，可能需要第二个倒数和重复空间均值计算；未必比统一使用一个稍高精度倒数更便宜。结构成本见[共享计算图](../../../logs/mechanism_convergence_20260916/implementations/cost_graph.json)。所有 C 交付候选仍采用明确的 Q24 参考配置，低位宽对照没有被悄悄当成已发布硬件。

## 5. 真实少点观测揭示了适用范围

本次恢复验证域内全部 **97,734** 个目标标签、非空 GT track、当前观测仅 1/2 点的样本；加上原 80,450 个保留观测，共 **178,184** 个目标观测。原保留覆盖率为 **45.1500%**。这不是全部雷达点或独立物体的覆盖率。

两个视图分别使用当前点，以及前面最多六个原流程保留观测＋当前点；被过滤观测不更新历史，以隔离原筛选策略。每个原保留 K7 观测都重新匹配了冻结输入，没有悄悄改掉基线。上下文、当前点数、距离的分组结果见 [A 少点分组](../../../logs/mechanism_convergence_20260916/factorial_evaluation/sparse_groups.csv)、[B 少点分组](../../../logs/mechanism_convergence_20260916/augmentation_evaluation/sparse_groups.csv)。

自然少点改善可以作为迁移线索，但这些仍来自已有 validation 序列，不能充当新的独立最终测试，也没有解决无 GT 轨迹的检测、聚类、关联问题。当前历史 K7 无时间到期和跨帧姿态补偿的限制继续存在。

## 6. 21 维与分档均值的具体证据

在完整 train 和 validation 同时精确相同的槽位对：**{duplicate_text}**（槽号从 0 开始）。精确重复仅对相应表示成立；新协方差槽与旧 y 跨度的语义已经不同，不能套同一份删除清单。本轮没有把 21 维写成独立且最优，也没有通过零值或 RF 排名自动删维。

原分档均值在舍入前相当于给真实均值乘 `N / 2^ceil(log2(N))`。本验证集这一系数的均值为 **{audit['count_bin_mean']['mean_attenuation']:.6f}**，恰好为 1 的观测比例为 **{audit['count_bin_mean']['fraction_exact_power_of_two']*100:.4f}%**。它是确定的数值偏差，不是同等比例的分类错误；网络可能补偿部分偏差。按减点前后该系数变化分组的结果见[机制归因](../../../logs/mechanism_convergence_20260916/mechanism_audit/count_phase_groups.csv)。

## 7. 实现与证据边界

35 个最终模型都完成完整 validation 的逐层 C/NumPy/QAT 一致性检查；真正按编译时开关裁掉不用运算的单遍 C 统计＋整数网络，累计 **2,815,750** 个模型/观测组合对拍通过。原代理没有二阶乘积；均值修正只有四通道一阶和与簇末倒数乘法；空间矩增加每点三个乘积；开平方编码再增加每簇三次整数平方根。这里报告的是可运行 C 及逻辑计算依赖，不是 FPGA LUT/DSP、时钟、功耗或实测加速比。

一条早期训练因新包装器接口错误在首次验证输出前终止，原源码与日志保留，修正后所有有效比较统一用相同版本。编码专项的来源路径错误在任何模型初始化前修复，未产生额外模型。详见两包 `runner_fix.json`；不能把失败尝试伪装为有效训练或悄悄删除。

最终执行、旧工件保护与同步校验见[validation.json](validation.json)。方法是否构成论文原创贡献、独立确认集、真实硬件质量—成本证据，仍需分别完成；现有板卡资源充足，不以“塞不下”为泛化理由。
'''
    (HERE/'02_结果与所得认识.md').write_text(report)
    with (HERE/'comparison.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['configuration','condition','seed_count','macro_f1_mean_percent','seed_standard_deviation_pp'])
        for name,r,m in configs:
            for k in columns:w.writerow([name,k,3,*avg(r,m,k,seeds,k.startswith('sparse'))])
    edoc=f'''# 二阶统计输出编码专项

2026-09-16。已按[冻结计划](plan.json)完成更细线性定标/开平方编码两种表示×三个 seed 的六条固定轮数训练。它针对二阶信息在 INT8 输出处大量变零的问题，与前一轮机制/扰动训练独立立项；没有继续扩大 transform、百分位或 seed 搜索。

请优先阅读[统一结果与所得认识](../mechanism_convergence_2026-09-16/02_结果与所得认识.md)，其中统一比较了 35 条新训练、自然少点观测及位宽变化，避免割裂地看本专项最高分。

{table(['表示']+cnames,[[names[m]]+[f'{avg(c,m,k,seeds)[0]:.4f} ± {avg(c,m,k,seeds)[1]:.4f}' for k in primary] for m in ['linear_fine','root']])}

单位为开发 validation Macro-F1 % 的三个 seed 均值±样本标准差。数据为 80,450 条、27 序列，非独立最终测试。

{t5}

- [执行前审查及已有方法边界](00_计划审查与方法边界.md)：平方根、signed power normalization 与非均匀编码均不是新概念。
- [两条补充文献 RIS](encoding_references.ris)：可导入 Zotero。
- [整数预检与定标统计](../../../logs/moment_encoding_20260916/preflight.json)：4096 个整数根案例，完整 438,230 条根号变换 Python/C 一致，完整 80,450 个点簇前端一致。
- [评价和精度门槛](../../../logs/moment_encoding_20260916/evaluation/summary.json)、[条件分组](../../../logs/moment_encoding_20260916/evaluation/groups.csv)。
- [完整 C 候选检查](../../../logs/moment_encoding_20260916/implementations/summary.json)：六个模型共 482,700 个组合对拍。
- [独立可编译源码包](candidate_c_bundle.zip)、[来源路径修复记录](runner_fix.json)。旧源码、数据、权重和位流均保留。

训练入口为 `train_encoding_v2.py --stage encoding`。`train_encoding.py` 及 `run_after_mechanism.py` 保留原先的运行前失败记录，不是推荐重跑入口。成功输出拒绝原地覆盖；重跑需新目录。
'''
    (EDOC/'README.md').write_text(edoc)
    print('Unified report, encoding README, comparison CSV and three figure pairs written')

if __name__=='__main__':main()
