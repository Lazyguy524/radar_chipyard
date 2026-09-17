# 双向维度实验软件参考包

全部11组新方案、三个种子保留；旧16/23的六个完整软件包逐文件SHA复制到frozen_references目录，来源见reused_references.json。分析对照与当前主方案 A/B 区分见评价结论。每个子目录含原始槽位映射、尺度、模型、C 源码及单簇示例。

```bash
cd full36_seed7
gcc -O2 -std=c99 candidate.c -o candidate
./candidate example.int16le
```

输出对照 example.json。历史关联属于上游，不包含检测/跟踪或板测。
