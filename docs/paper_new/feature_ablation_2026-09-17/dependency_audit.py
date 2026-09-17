"""Post-training arithmetic explanation; train-only, no new candidate or fit."""
from ab_common import *

def main():
    assert json.loads((LOG/'training/summary.json').read_text())['status']=='PASS'
    out=LOG/'dependency_audit.json';assert not out.exists();rows=[]
    # Pairs follow source definitions: span/4 then an adjusted output shift.
    # Finite intermediate truncation means the first two are not assumed equal.
    for pool,path in [('kept',MECH/'data/train/proxy.npy'),('quarter',MECH/'raw/train/proxy/uniform_quarter_0.npy'),('central',MECH/'raw/train/proxy/central_half.npy'),('natural_sparse',OLD/'data/train/natural_proxy.npy')]:
        x=np.load(path)
        for a,b in [(3,5),(4,6),(6,10)]:
            delta=x[:,a].astype(np.int16)-x[:,b].astype(np.int16)
            rows.append(dict(pool=pool,slots=[a,b],rows=len(x),different=int(np.count_nonzero(delta)),different_fraction=float(np.mean(delta!=0)),max_abs_difference=int(np.abs(delta).max()),source_sha256=sha(path)))
    dump(out,dict(status='PASS',rows=rows,scope='Post-training descriptive audit on train pools only. Pairs fixed from existing arithmetic definitions; no selection, new candidate or retraining. Similarity is not an integer equivalence proof except pair6/10.'))
    text=['# 派生特征为什么不能直接当作新信息\n','本附录在12条训练之后生成，只检查训练池，不改变已冻结候选或门槛。前三对来自源码的明确依赖，不是用开发分数重新搜索删除项。\n','| 训练输入池 | 槽位对 | 不同的观测数/总数 | 不同比例 | 最大 INT8 差 |','| --- | --- | ---: | ---: | ---: |']
    for r in rows:text.append(f"| {r['pool']} | {r['slots']} | {r['different']}/{r['rows']} | {100*r['different_fraction']:.5f}% | {r['max_abs_difference']} |")
    text+=['\n3/5、4/6分别来自同一 x/y 跨度，先除4再使用不同输出移位；中间整数截断会影响最终 ties-to-even 舍入，所以不能像6/10一样直接宣称逐整数恒等。11/12是跨距派生的最大/最小，且量化尺度不同；即使原始量可由共享跨度求出，量化后仍可能保留不同分辨率的信息。\n','该审计帮助解释为何“候选特征个数”“底层统计量个数”和“共享硬件计算次数”不是同一个概念。不能凭高度相关或近似重复，就断言固定INT8分类器无损删掉它们。对应质量仍以本轮实际重训结果及分组门槛为准。\n','[数值与来源 SHA](../../../logs/feature_ablation_20260917/dependency_audit.json)']
    (HERE/'04_派生依赖补充.md').write_text('\n'.join(text)+'\n');print(json.dumps(rows),flush=True)
if __name__=='__main__':main()
