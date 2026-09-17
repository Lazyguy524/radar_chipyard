"""Create a portable report evidence snapshot without changing experiments."""
import csv
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

SOURCES = [
    ('E01', 'training_recovery_readme.txt', 'docs/paper_new/training_server_recovery_2026-09-15/README.md'),
    ('E02', 'scheiner_review_readme.txt', 'docs/paper_new/scheiner_feature21_review_2026-09-15/README.md'),
    ('E02', 'approximation_research_readme.txt', 'docs/paper_new/feature_approximation_research_2026-09-16/README.md'),
    ('E03', 'mechanism_review.txt', 'docs/paper_new/mechanism_convergence_2026-09-16/03_评审与收敛决定.md'),
    ('E03', 'conditional_protection_readme.txt', 'docs/paper_new/conditional_protection_2026-09-16/README.md'),
    ('E04', 'software_convergence_readme.txt', 'docs/paper_new/software_convergence_2026-09-17/README.md'),
    ('E05', 'ablation_readme.txt', 'docs/paper_new/feature_ablation_2026-09-17/README.md'),
    ('E05', 'ablation_results.csv', 'docs/paper_new/feature_ablation_2026-09-17/results.csv'),
    ('E06', 'enrichment_readme.txt', 'docs/paper_new/feature_enrichment_2026-09-17/README.md'),
    ('E06', 'enrichment_plain.txt', 'docs/paper_new/feature_enrichment_2026-09-17/08_白话解释与数据观察.md'),
    ('E06', 'enrichment_results.csv', 'docs/paper_new/feature_enrichment_2026-09-17/results.csv'),
    ('E07', 'dimension_readme.txt', 'docs/paper_new/feature_dimension_sweep_2026-09-17/README.md'),
    ('E07', 'dimension_results.csv', 'docs/paper_new/feature_dimension_sweep_2026-09-17/results.csv'),
    ('E07', 'dimension_costs.csv', 'docs/paper_new/feature_dimension_sweep_2026-09-17/costs.csv'),
    ('E07', 'dimension_gate_review.txt', 'docs/paper_new/feature_dimension_sweep_2026-09-17/10_门槛敏感性与最终评审.md'),
    ('E07', 'dimension_low_N.txt', 'docs/paper_new/feature_dimension_sweep_2026-09-17/06_少点下的有效信息.md'),
    ('E07', 'dimension_plan.json', 'docs/paper_new/feature_dimension_sweep_2026-09-17/plan.json'),
    ('E07', 'dimension_gates.json', 'logs/feature_dimension_sweep_20260917/evaluation/summary.json'),
    ('E08', 'dimension_validation.json', 'docs/paper_new/feature_dimension_sweep_2026-09-17/validation.json'),
    ('E08', 'dimension_C_checks.json', 'logs/feature_dimension_sweep_20260917/package/summary.json'),
    ('E09', 'gemmini_readme.txt', 'docs/paper_new/gemmini_qmlp_comparison_2026-09-15/README.md'),
    ('E10', 'representative_rtl_readme.txt', 'docs/paper_new/representative_rtl_2026-09-17/README.md'),
    ('E11', 'pmu_previous_week_readme.txt', 'docs/paper_new/pmu_execution_2026-09-12/README.md'),
]

EXPLANATIONS = {
    'E01': ('数据恢复与评价审计', '335个原文件、模型导出复现、历史test选K及量化尺度问题、历史规则；不能把历史软件复现称为新增板测。'),
    'E02': ('论文对照与研究主线', '本周阅读/整理的项目记录；只报告研究问题与比较范围，没有新增论文分数横比。原文献书目仍以原研究包为准。'),
    'E03': ('统计机制与条件保护', '35条机制训练及单列的条件保护阶段；只支持收益有条件、不能用精度单独判断分类质量的阶段认识。'),
    'E04': ('真实少点与12条覆盖对照', '474,582条真实少点训练观测；2表示×2覆盖×3种子；开发数据、主/备边界与提升范围。'),
    'E05': ('12条删维实验', '21/20/18/16维匹配重训，RCS删除及16维简化的结果；输入列是真删减。'),
    'E06': ('15条补维实验', '16维加几何/速度反射分布的对照，23维比16维综合+0.197个百分点，但当前帧真实少点−0.266个百分点。'),
    'E07': ('33条双向维度实验', '8～36维、六个复用参考、13条件、种子结果、成本与失败门槛；24维通过旧门槛不等于局部错误已解决。'),
    'E08': ('一致性与审计', '33新模型9,105,294次C核对零差异、585组指标重算；不是独立观测数或板测次数。'),
    'E09': ('Gemmini补充工作', '16×16不同Scale配置须区分，33.333333 MHz为已验证实现点而非Fmax；最终板测比较待完成。本次PPT不使用其中周期和资源。'),
    'E10': ('代表RTL补充工作', '前阶段三种21维候选的独立RTL核对，不代表最新23/28/36维已进入硬件。本次PPT不展开。'),
    'E11': ('前期PMU基础', '2026-09-12阶段记录，属于前一自然周基础，不算本周新增完成，不进入本次PPT。'),
}

def main():
    evidence = HERE/'证据'
    assets = HERE/'assets'
    evidence.mkdir(exist_ok=True)
    assets.mkdir(exist_ok=True)
    manifest = []
    for eid, filename, rel in SOURCES:
        source = ROOT/rel
        target = evidence/filename
        shutil.copyfile(source, target)
        assert sha(source) == sha(target)
        manifest.append(dict(id=eid, original_repo_path=rel, snapshot=str(target.relative_to(HERE)), sha256=sha(source), bytes=source.stat().st_size))
    counts = []
    for tag, expected in [('feature_ablation', 12), ('feature_enrichment', 15), ('feature_dimension_sweep', 33)]:
        p = ROOT/'logs'/(tag+'_20260917')/'training/summary.json'
        obj = json.loads(p.read_text())
        assert obj['status'] == 'PASS' and len(obj['runs']) == expected
        counts.append(dict(stage=tag, new_trajectories=len(obj['runs']), source=str(p.relative_to(ROOT)), sha256=sha(p)))
    (evidence/'training_count_audit.json').write_text(json.dumps(dict(status='PASS', dimension_trajectories=sum(r['new_trajectories'] for r in counts), stages=counts, reused_models_in_latest_stage=6, reused_not_counted_as_new=True, scope='Dimension studies only; not total weekly training count'), ensure_ascii=False, indent=2)+'\n')
    with (evidence/'dimension_results.csv').open() as f:
        metrics = {r['tag']: r for r in csv.DictReader(f)}
    labels = [('core8','8维·基础量'), ('base16','16维·基础表示'), ('combined23','23维·分布补充'), ('width28','28维·四分位宽度'), ('full36','36维·完整分位')]
    selected = []
    for tag, label in labels:
        r = metrics[tag]
        selected.append(dict(tag=tag, label=label, dim=int(r['dim']), composite_percent=100*float(r['composite']), clean_macro_f1_percent=100*float(r['clean']), seed7_composite_percent=100*float(r['seed7']), seed17_composite_percent=100*float(r['seed17']), seed37_composite_percent=100*float(r['seed37']), source='证据/dimension_results.csv', scope='Reused development data, three-seed mean, equal average of five input-condition Macro-F1 metrics'))
    with (assets/'ppt_representative_results.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    rows=['# 汇报证据索引', '', '本包提供适合Windows直接读取的来源快照，不需要从Windows访问Linux绝对路径。`.txt`是原研究文档的逐字存档，其中相对路径仍按原仓库解释；取用PPT材料请优先使用本页和本包CSV。完整SHA及原仓库路径见[来源清单](source_manifest.json)。', '', '汇报范围为2026-09-14～17；E11仅前期背景。PPT采用代表结果，不穷尽所有已完成方案；同时保留开发集和局部退步说明。', '', '[训练次数复核](证据/training_count_audit.json)：12+15+33=60条维度相关新训练，最新阶段六个复用模型不重复计数。', '', '五条件综合是常规、三次均匀四分之一Macro-F1的平均、中心一半、真实少点当前帧、真实少点加历史五项等权平均；表中的百分数不能改名为准确率。']
    for eid,(title,description) in EXPLANATIONS.items():
        rows += ['', '## '+eid, '', '**'+title+'。** '+description, '']
        for item in manifest:
            if item['id']==eid:
                rows.append('- ['+Path(item['snapshot']).name+']('+item['snapshot']+')；原路径：`'+item['original_repo_path']+'`。')
    (HERE/'05_证据索引.md').write_text('\n'.join(rows)+'\n')
    (HERE/'source_manifest.json').write_text(json.dumps(dict(status='PASS', sources=manifest, dimension_training_audit=counts, meeting_date='2026-09-18', cutoff='2026-09-17', scope='Read-only evidence excerpts and tables; no experiment or threshold changed'), ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status='PASS', snapshots=len(manifest), dimension_training_count=60, representative_rows=len(selected)), ensure_ascii=False))

if __name__=='__main__':
    main()
