# 冻结模型单样本推理时延对比说明（CPU / GPU / FPGA）

## 1. 目的

本文档用于汇总冻结部署模型在软件侧与硬件侧的单样本推理时延，便于后续与硬件同学对齐 accelerator 的 kernel latency 口径。

当前冻结模型为：

- 模型结构：`21 -> 64 -> 32 -> 2`
- 模型类型：`INT8 QMLP`
- 输入：单样本 `21` 维特征
- 输出：`2` 维 logits
- 冻结版本目录：[input_convergence_k3_rcs21_20260406](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406)

## 2. 测试环境

### CPU 基准

- 机器 CPU：`Intel(R) Xeon(R) Gold 6258R CPU @ 2.70GHz`
- 单线程：是
- CPU 亲和性：绑定 `CPU0`
- 结果文件：[benchmark_results.json](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/logs/kernel_latency_benchmark_2026-04-09/benchmark_results.json)

### GPU 基准

- Python：`3.10.20`
- PyTorch：`2.10.0+cu128`
- GPU：`NVIDIA GeForce RTX 3090`
- Driver：`535.247.01`
- 显存：`24576 MiB`
- 单线程环境变量：`OMP_NUM_THREADS=1` 等已固定
- 结果文件：[benchmark_results_gpu_forward_only.json](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/logs/kernel_latency_benchmark_2026-04-09_gpu/benchmark_results_gpu_forward_only.json)

### 硬件参考

- `hw_cycles_avg = 1301`
- `clock = 50 MHz`
- `kernel latency = 26.02 us`

## 3. 口径说明

### 纯 forward 时间

只统计模型计算本体：

- 不包含文件读取
- 不包含模型加载
- 不包含一次性初始化
- 不包含数据集读取
- 不包含打印与日志
- 不包含多帧融合、特征提取、聚类
- 不包含 DMA / MMIO / DDR 搬运

### 端到端单样本时间

在纯 forward 基础上，额外允许包含最小的完整函数调用开销。

对于 CPU 参考实现，这一项包含：

- `float[21] -> int8[21]` 的输入量化
- 完整函数调用

对于 GPU 本轮测试，这一项实际仍然只是在 GPU 上对同一个已驻留输入做完整 `model(x)` 调用，并在主机侧计时后 `synchronize`，因此它不包含：

- 主机到显存的数据拷贝
- 模型文件加载
- 一次性初始化

## 4. 测试次数

本轮 CPU / GPU 基准均采用：

- warmup：`2000` 次
- 正式测量：`20000` 次

满足“至少 1000 次单样本 forward”的要求。

## 5. 结果汇总

### 5.1 CPU 结果

#### Python / NumPy 量化参考

- 纯 forward：
  - avg：`61.32465675 us`
  - median：`61.187 us`
  - min：`60.053 us`
  - max：`1221.892 us`
- 端到端：
  - avg：`62.42260465 us`
  - median：`60.513 us`
  - min：`56.379 us`
  - max：`1216.342 us`

#### C 参考实现（`-O3 -march=native`）

- 纯 forward：
  - avg：`0.6531 us`
  - median：`0.642 us`
  - min：`0.585 us`
  - max：`21.045 us`
- 端到端：
  - avg：`0.753696 us`
  - median：`0.745 us`
  - min：`0.686 us`
  - max：`36.196 us`

### 5.2 GPU 结果

本轮 GPU 测的是“冻结模型在 CUDA 上的 PyTorch forward”，也就是直接执行：

```python
model(input_float_cuda)
```

#### PyTorch CUDA forward

- 纯 forward：
  - avg：`963.6710408 us`
  - median：`965.6320214 us`
  - min：`857.1199775 us`
  - max：`2515.9680843 us`
- 端到端：
  - avg：`955.06389375 us`
  - median：`956.343 us`
  - min：`890.378 us`
  - max：`2509.212 us`

换算成秒：

- GPU 纯 forward avg：`0.000963671 s`
- GPU 端到端 avg：`0.000955064 s`

### 5.3 FPGA 硬件参考

- 平均周期：`1301 cycles`
- 时钟：`50 MHz`
- kernel latency：`26.02 us`
- 换算成秒：`0.00002602 s`

## 6. 结果对比

| 平台 | 实现 | 纯 forward avg |
|---|---|---:|
| CPU | Python / NumPy 量化参考 | `61.325 us` |
| CPU | C 参考实现 | `0.653 us` |
| GPU | PyTorch CUDA forward | `963.671 us` |
| FPGA | 硬件 kernel | `26.02 us` |

## 7. 如何理解这些数字

### 7.1 为什么 GPU 反而更慢

这是正常现象，不说明 GPU 不行，而是说明：

- 当前模型非常小：`21 -> 64 -> 32 -> 2`
- 单样本 batch = 1
- 计算量总共只有 `3456 MAC`
- 对 GPU 来说，这种规模远小于它擅长的并行吞吐场景
- CUDA kernel launch、框架调度、同步开销会占主导

所以：

> 对这种极小 MLP 的单样本推理，GPU 往往不会比高优化 CPU 或定制 FPGA kernel 更占优。

### 7.2 为什么 C 参考实现比 FPGA 还快

这也不矛盾，因为：

- C 参考运行在 `2.7 GHz` Xeon 上
- 数据和权重大概率在 cache 友好环境中
- 它不包含 DDR / DMA / MMIO / 控制面开销
- 只是“纯算子核”的主机侧参考

所以它只能说明：

> 这个算子本体非常小，软件纯核在高频 CPU 上可以很快。

它不能说明 FPGA 没价值。FPGA 的价值在于：

- 与板级 SoC 闭环集成
- 固定低频下的确定性延迟
- 可与 AXI DMA / DDR / accelerator 数据路径直接耦合

### 7.3 哪些结果最适合和硬件 `26.02 us` 比较

如果只谈“计算边界是否接近”，最接近硬件 kernel 口径的是：

- CPU `C 参考实现` 的 pure forward

但这仍然不是完全公平的同平台比较，因为：

- CPU 与 FPGA 主频完全不同
- 微架构不同
- 访存层级不同

GPU 这次的结果更适合回答：

> 如果把当前冻结模型直接放在 CUDA 上做单样本 forward，大概需要多久？

答案是：

> 大约 `0.96 ms`。

## 8. 当前可用于汇报的结论

可以直接使用下面这段总结：

> 针对冻结部署模型 `21 -> 64 -> 32 -> 2 INT8 QMLP`，本文在软件侧和硬件侧分别测试了单样本推理时延。结果表明：在 Xeon CPU 上，C 参考实现的纯 kernel 时间约为 `0.653 us`；在 RTX 3090 上，PyTorch CUDA 单样本 forward 时间约为 `0.964 ms`；在 Nexys Video FPGA SoC 上，当前硬件 kernel latency 为 `26.02 us`。由于该模型规模较小、单样本计算量有限，GPU 端主要受 kernel launch 与框架调度开销影响，未体现出吞吐优势；而 FPGA kernel 运行在 `50 MHz` 下，仍能获得稳定且确定性的板级推理时延，因此更适合作为当前 SoC 闭环中的部署目标。

## 9. 备注

本轮 GPU 测试没有实现与硬件完全同口径的 `INT8/INT32` CUDA 量化 kernel，对比对象是：

- 冻结后的同一组权重
- 同一个输入样本
- 在 CUDA 上执行的 PyTorch forward

原因是 PyTorch CUDA 当前不直接支持这里所需的 `int32 addmm` 路径。  
因此，GPU 数据可作为“模型在 CUDA 上的实际单样本 forward 时间”参考，但不应被解读为与硬件 kernel 的严格等价性能对拍。
