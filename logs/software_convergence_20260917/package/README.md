# 冻结的软件参考包

主方案及备选均保留 seed 7、17、37，不挑选最佳种子。每个子目录的 contract.json 定义表示、尺度、标签和历史边界。

编译并运行示例：

```bash
cd main_seed7
gcc -O2 -std=c99 candidate.c -o candidate
./candidate example.int16le
```

输出应与 example.json 一致。输入为上游已关联的一个点簇，不包含检测、关联或原始雷达信号处理。全部训练与评价脚本位于 docs/paper_new/software_convergence_2026-09-17。
