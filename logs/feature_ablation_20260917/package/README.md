# 特征消融软件参考包

全部四组、三个种子保留。分析对照与当前主方案 A/B 区分见评价结论。每个子目录含原始槽位映射、尺度、模型、C 源码及单簇示例。

```bash
cd dedup20_seed7
gcc -O2 -std=c99 candidate.c -o candidate
./candidate example.int16le
```

输出对照 example.json。历史关联属于上游，不包含检测/跟踪或板测。
