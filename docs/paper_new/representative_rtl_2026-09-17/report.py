"""Write outcome-first Chinese notes from completed RTL receipts."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];LOG=ROOT/'logs/representative_rtl_20260917'

def main():
    result=json.loads((LOG/'summary.json').read_text());assert result['status']=='PASS'
    pre=json.loads((LOG/'preflight.json').read_text())
    rows=sum(r['rows'] for r in result['runs'].values())
    names={'A':'普通训练','B':'扰动训练','C':'正确判断保护'}
    table=['| 方案 | 真实点簇 | 边界点簇 | 特征与 logits | 取消/恢复、阻塞、帧格式 |','| --- | ---: | ---: | --- | --- |']
    for name,r in result['runs'].items():
        assert r['rows']==pre['total_rows'] and r['abort_recovery'] and r['malformed_header_flag']
        table.append(f'| {name} {names[name]}，seed 7 | {pre["real_rows"]:,} | {pre["synthetic_rows"]} | 完全一致 | 通过 |')
    text='''# 硬件衔接结果与反思

本轮完成了三种冻结代表方案的实际 Chisel RTL 对拍。功能上已经能够让新定标的 Feature21 输出进入现有 QMLP 结构，并产生与 C/训练导出一致的结果。

## 实际完成的检查

'''+ '\n'.join(table)+f'''

共 **{rows:,} 次模型—点簇检查**。每条包括 21 个特征、11 个填充字节及两个 INT32 logits；真实部分是原开发 validation，另加每个 N=1…511 的确定性随机边界簇及零/极值簇。先完成 {pre['python_rounding_cases']:,} 个 Python 舍入检查，并将原始 C proxy 逐特征定标与全部 80,450 条保存输入比对一致。

仿真还插入输入空拍、持续输出阻塞，检查输出在等待期间保持稳定、样本顺序、TKEEP/TLAST、取消半帧、取消已进入分类器的样本、非法 512 点头部报错，以及恢复后没有残留输出。完整报告见 [summary.json](../../../logs/representative_rtl_20260917/summary.json)；各模型的原日志和命令在同级 A/B/C 目录。

## 这次解决了什么

三者使用完全相同的 proxy 结构和输出尺度，不需要为训练保护增加教师模型、距离输入或历史组信息。教师/分组只参与训练。网络参数和逐特征尺度通过 [model_bindings.json](model_bindings.json) 绑定。

旧 Feature21 普通特征先乘 105、右移 16，再压到 INT8；新表示是在压到 INT8 之前用逐特征移位。在实际数据中，有 {len(pre['legacy_byte_information_collisions'])} 个特征槽找到“旧字节相同、新字节不同”的实例，因此旧输出不足以重建新表示。所需改动位置已经确定，不能只换网络权重。密度槽沿用旧倒数 LUT 量化，其他统计定义未变。

实现采用当前 `RadarFeature21.scala`、`RadarQMLP.scala`、`RadarStream.scala` 的隔离副本和新 Scala package；普通特征输出换为固定逐槽移位，QMLP 参数路径明确指向已冻结候选，保留既有 4 lane、两上下文和流水线。不是另写一个只会计算正确答案的仿真行为模型。可审查差异见 [isolated_changes.patch](../../../logs/representative_rtl_20260917/isolated_changes.patch)。

三种权重在结构上兼容，不证明三者综合资源或时序完全相同。当前仿真周期包含主动插入的阻塞，只用于复现正确性检查，不列为最终性能对比。

## 执行中修正与边界

首次 Scala 编译遇到 `chisel3.util` 导入遮蔽根 `circt` 名称；改为 `_root_.circt` 后通过。随后发现 CIRCT 单文件输出包含黑盒资源文件清单，需要按显式文件边界拆分给 Verilator。这两项是构建脚本/验证顶层修正，没有改变模型、定标或运算假设；首次失败日志与隔离源码保留，见 [修正记录](../../../logs/representative_rtl_20260917/source_revisions.json)。随后三种完整功能对拍均通过，没有根据结果重训、改尺度或选择 seed。

没有生成新的完整 SoC、FPGA 位流或板端数据。原工程和历史模型/位流未改。A/B/C 的科学结论仍是存在条件性收益和代价，不能将本轮功能 PASS 等同于算法全面更优或满足上一轮推广门槛。

## 结果后的设计反馈

这次证据说明：当前三种代表的部署差别主要体现在参数与共同输出定标，复杂新增统计算子没有因此成为必要条件。后续可以把精力放在匹配的 SoC 接入、量化表示成本和真实运行窗口，而不是继续增加训练次数。

原主线依然包含统计近似、精度选择和共享计算；前面矩统计/输出编码的正负结果必须保留，用于解释为什么选择当前结构。下一步见 [最终验证如何收口](02_最终验证如何收口.md)，已有方法的借鉴关系见前一轮设计账本，本轮不增加未经查重的算法原创性声明。
'''
    (HERE/'01_结果与设计反馈.md').write_text(text)
    (HERE/'README.md').write_text('''# 这一步已经推进到哪里

**三种候选方案已经通过真实硬件代码的仿真对拍。** 每种检查 80,450 条真实点簇和 542 组边界输入，特征和分类输出都与参考程序一致。

简单说：之前是“训练程序能算对”，现在补上了“Feature21＋QMLP 硬件代码也能算对”。也弄清楚了怎样接入新模型：需要同时匹配特征定标和权重，不能只替换旧权重。

这不改变之前的算法判断：新方法有收益，也有退步；没有宣布它全面胜出。原工程、权重和位流保留。

下一步是独立 SoC 接入和匹配的板测。**当前还没有这三种候选的新位流或上板成绩。** 独立质量确认的数据缺口仍保留。

- [结果与设计反馈](01_结果与设计反馈.md)：测试了什么、为什么这样改。
- [后续只补哪些验证](02_最终验证如何收口.md)：避免重新陷入无限训练。
- [原问题与执行前计划](00_计划与设计记录.md)、[参数与 RTL 绑定](model_bindings.json)。
- [代码备份和复现](03_备份与复现.md)、[备份/同步回执](backup_sync_receipt.json)。
''')
    (HERE/'03_备份与复现.md').write_text('''# 备份与复现

本轮计划、源码、测试程序、模型绑定、生成 RTL、结果和设计反思进入独立备份分支 `backup/radar-thesis-20260917-rtl`，其父提交为前阶段结果备份 `df7774f3`。备份使用独立 index，不切换用户工作分支，不改变已有暂存区；这不是整个脏工作树的完整备份。

提交号和远端是否成功以 [备份回执](backup_sync_receipt.json) 为准；只有远端回读一致才写已推送。本地归档位于 `/home/soooarr/radar_thesis_backups_20260917/`。Git bundle 是相对于原工作分支基点的增量包，需要回执中的基点，不是无依赖仓库镜像。

完整结果 tar 包含本轮输入向量、预期输出、仿真程序、生成 RTL、构建日志和源码；不包含原始 RadarScenes HDF5 或可重建的 C++ object/Scala classes。模型原参数通过父备份中的已冻结导出和本轮绑定 SHA 追溯。

Obsidian 共享目录保存本轮说明、代码、小型证据和归档副本，复制后逐项校验。共享目录写入不能证明 Obsidian 云端已同步，云端仍未验证。

## 运行与边界

主程序 [workflow.py](workflow.py) 的顺序是 `prepare` → `sources` → 对每个 A/B/C 执行 `build --model X`、`simulate --model X` → `audit`。使用 `/tmp/radar_training_audit_20260915/bin/python`（Python 3.10、NumPy 1.26.4），本地 Chipyard assembly、Scala 2.13.12/Chisel 6.5.0、CIRCT 1.62.0、Verilator 5.022、GCC。每步命令、日志和耗时保存在 logs 目录，限制两个构建线程。

原输出目录已冻结，脚本拒绝覆盖。重新实验须复制脚本并指定新的输出目录，不能直接重跑覆盖。只重复检查现有仿真器，可在新临时工作目录运行 `<本轮日志>/A/obj/candidate_sim <本轮日志>/vectors A`；B/C 同理，程序会在当前工作目录写结果。

`CandidateTop.sv` 原始输出是 CIRCT 的多文件流，含非 Verilog 的资源清单，不能直接交给 Verilator。用于编译的文件在各模型 `rtl/`；分割过程保留原流，不改硬件逻辑。

顶层只包含 Feature21 与 QMLP，带验证用特征观察口。尚不是完整 Chipyard SoC，不提供可直接烧录的位流。完整 SoC 构建必须采用独立配置，并将正确的逐特征尺度和候选参数接入；不能误用旧发布版。
''')
    print('RESULT_DOCS_WRITTEN')

if __name__=='__main__':main()
