# 硬件对接模型说明

## 1. 文档目的

这份文档不是论文说明，而是给硬件侧直接对接用的实现规格。

目标是回答四个问题：

1. 当前是否已经可以开始做 accelerator
2. 最推荐交付给硬件侧的模型到底是哪一个
3. 输入、权重、输出的数据格式是什么
4. 第一版在当前 `Chipyard + Rocket + AXI DMA + AXIS` 平台上应当怎么落地

---

## 2. 先给结论

### 2.1 可以开始做硬件，不需要继续等待更多软件微调

当前 student 主线已经收敛到一个适合冻结的版本：

> 多帧融合 `k=3` + `rcs21` 输入 + `21 -> 64 -> 32 -> 2` INT8 QMLP

当前 best 指标为：

- `accuracy = 0.9279`
- `macro_f1 = 0.9178`

对应指标文件：

- [student_metrics.json](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/logs/input_convergence_2026-04-06/train/k3_rcs21/student_metrics.json)

### 2.2 当前最推荐的硬件实现对象

当前建议硬件化的对象不是 teacher，也不是多帧融合预处理，而是：

> **最终部署 student：一个三层全连接 INT8 量化 MLP**

也就是说，硬件第一版只需要解决：

- 定长向量输入
- 三层 Linear
- 两层 ReLU
- INT8/INT32 定点推理

### 2.3 当前推荐主版本与保守备选

推荐主版本：

- `k=3 + rcs21`
- 输入维度：`21`
- 模型：`21 -> 64 -> 32 -> 2`

保守备选：

- `k=3 + baseline18`
- 输入维度：`18`
- 模型：`18 -> 64 -> 32 -> 2`

这两者对硬件主结构没有本质区别，只是第一层输入维度不同。

---

## 3. 当前平台约束与设计假设

根据当前硬件平台信息，本文档默认以下实现前提：

- 平台：`Chipyard/Rocket` on `Nexys Video`
- FPGA：`Artix-7`
- 外部存储：`MIG DDR`
- 稳定主频：`50 MHz`
- 已验证通路：
  - `DDR -> MM2S -> AXIS -> S2MM -> DDR`
  - DMA 中间插入 `RadarAXISPreprocessor` 已可工作

因此，当前建议保持既有主数据路径：

> `CPU/SD -> DDR -> MM2S -> NN accelerator -> S2MM -> DDR -> CPU`

不建议第一版重新发明一套访存体系。

---

## 4. 软件端与硬件端分工

### 4.1 软件端负责

软件端或 PC 端负责：

- 基于 `RadarScenes` 做数据预处理
- 按 `k=3` 做多帧融合
- 从点簇提取 21 维统计特征
- 输入量化
- 准备 DDR 中的输入向量
- 配置 accelerator CSR
- 启动 DMA
- 读取回写结果并做 `argmax`

### 4.2 硬件端负责

accelerator 只负责：

- 读取量化输入向量
- 执行三层 FC 推理
- 输出 2 维 logits

### 4.3 当前不建议硬件化的部分

第一版不建议优先硬件化：

- teacher 模型
- 多帧融合
- 聚类
- 统计特征提取
- 复杂后处理

这些部分当前更适合保留在 PC 或 Rocket 软件侧。

---

## 5. 当前推荐 student 模型规格

### 5.1 模型类型

- 类型：量化 MLP
- 任务：二分类
- 类别：
  - `pedestrian`
  - `vehicle`

### 5.2 输入与输出

- 输入：`int8[21]`
- 输出：建议硬件直接输出 `int32[2] logits`

CPU 侧最终只需做：

- 比较两个 logits
- 取 `argmax`

### 5.3 网络结构

当前推荐模型固定为：

1. `Linear(21 -> 64)` + `ReLU`
2. `Linear(64 -> 32)` + `ReLU`
3. `Linear(32 -> 2)`

可记为：

> `21 -> 64 -> 32 -> 2`

### 5.4 量化格式

- 权重：`INT8`
- 激活：`INT8`
- 偏置：`INT32`
- 累加：`INT32`
- 导出文件中提供每层 scale

当前参数摘要文件：

- [radar_mlp_binary_k3_rcs21_params.json](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/artifacts/input_convergence_2026-04-06/k3_rcs21_export/radar_mlp_binary_k3_rcs21_params.json)

其中关键字段为：

- `input_dim = 21`
- `num_classes = 2`
- `shapes = [[64, 21], [32, 64], [2, 32]]`
- `num_bits = 8`

### 5.5 当前冻结版本的量化细节

当前软件参考和导出参数统一采用以下规则：

- 量化位宽：`8 bit`
- 激活 / 权重量化范围：`[-127, 127]`
- 不使用 `-128`
- rounding：`round-to-nearest, ties-to-even`
- clamp / saturation：固定到 `[-127, 127]`
- requant 方式：**浮点乘法缩放**
  - 不是移位近似
  - 公式见后文

这套规则与当前 Python / C 参考实现一致。

### 5.6 每层 scale

当前冻结模型对应的每层 scale 如下：

| 层 | input scale | weight scale | output scale |
|---|---:|---:|---:|
| L1 | `1.67398477e+00` | `1.20335594e-02` | `4.88404930e-01` |
| L2 | `4.88404930e-01` | `4.24808264e-03` | `3.40428680e-01` |
| L3 | `3.40428680e-01` | `1.65770040e-03` | `5.64328759e-04` |

说明：

- `L1/L2` 的 `output scale` 用于下一层 `INT8` 激活
- `L3` 不做 requant 回 `INT8`
- `L3 output scale` 只用于把最终 `int32 logits` 反量化回浮点近似值

### 5.7 中间层数值语义与固定计算顺序

为了与当前软件参考完全一致，硬件侧应按下面顺序执行：

#### L1

1. 输入：`x_q[int8, 21]`
2. 计算：
   - `acc1_int32 = x_q * W1_q^T + b1_q`
3. requant：
   - `scaled1 = acc1_int32 * (l1_input_scale * l1_weight_scale / l1_output_scale)`
4. 激活：
   - `relu1 = max(scaled1, 0)`
5. 量化输出：
   - `y1_q = clamp(round(relu1), -127, 127)`

#### L2

1. 输入：`y1_q[int8, 64]`
2. 计算：
   - `acc2_int32 = y1_q * W2_q^T + b2_q`
3. requant：
   - `scaled2 = acc2_int32 * (l2_input_scale * l2_weight_scale / l2_output_scale)`
4. 激活：
   - `relu2 = max(scaled2, 0)`
5. 量化输出：
   - `y2_q = clamp(round(relu2), -127, 127)`

#### L3

1. 输入：`y2_q[int8, 32]`
2. 计算：
   - `logits_int32 = y2_q * W3_q^T + b3_q`
3. 不做 ReLU
4. 不做 requant 回 `INT8`
5. 如需浮点近似：
   - `logits_float = logits_int32 * l3_output_scale`

---

## 6. 当前推荐 21 维输入特征顺序

硬件侧只需要吃定长向量，不需要知道这些特征是如何从点簇统计出来的，但为了 CPU/硬件接口一致，仍需固定顺序。

当前 `rcs21` 特征顺序如下：

1. `n_points`
2. `mean_x`
3. `mean_y`
4. `std_x`
5. `std_y`
6. `span_x`
7. `span_y`
8. `range_min`
9. `range_max`
10. `centroid_range`
11. `azimuth_span`
12. `eig_major`
13. `eig_minor`
14. `density_2d`
15. `doppler_mean`
16. `doppler_std`
17. `doppler_min`
18. `doppler_max`
19. `rcs_mean`
20. `rcs_std`
21. `rcs_max`

该顺序定义来源：

- [features.py](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/src/radar_cluster_rocc/features.py)

### 6.1 输入向量语义

当前 accelerator 不直接接收点云，而是接收**已经量化完成的 21 维特征向量**。

因此：

- 多帧融合在 CPU / PC 侧完成
- 聚类和特征提取在 CPU / PC 侧完成
- accelerator 只吃最终 `int8[21]`

这也是为什么单帧与多帧 `k=3` 版本对 accelerator 来说是同一类模型。

---

## 7. 计算规模与硬件意义

### 7.1 权重规模

三层权重数量：

- 第一层：`21 x 64 = 1344`
- 第二层：`64 x 32 = 2048`
- 第三层：`32 x 2 = 64`

总权重数：

- `3456`

若按 `INT8` 存储：

- 权重总大小约 `3456 Byte`

### 7.2 偏置规模

偏置数量：

- `64 + 32 + 2 = 98`

若按 `INT32` 存储：

- 总大小约 `392 Byte`

### 7.3 单样本 MAC 数量

总 MAC 数量：

- `1344 + 2048 + 64 = 3456 MAC`

这说明：

- 模型极小
- 第一版没有必要做复杂层调度
- 甚至可以优先把权重常驻片上 BRAM/ROM，而不是每次都从 DDR 拉取

### 7.4 对当前平台的含义

在 `50 MHz` 主频下，真正的瓶颈更可能来自：

- DMA 启停与软件开销
- 输入/输出缓存组织
- AXIS 包装

而不是模型算力本身。

因此，v1 设计重点应该是：

- 跑通通路
- 固定接口
- 结果和软件一致

而不是一开始就追求极端算力优化。

### 7.5 权重与偏置的内存组织格式

当前导出文件里的权重布局已经固定：

- 权重 layout：`row-major[out][in]`
- 也就是：
  - `Linear(21 -> 64)` 在文件里是 `[64][21]`
  - 一行对应一个输出神经元
- bias layout：单独数组 `int32[out]`
- bias **不**紧跟在 weight 后拼接成一个连续 blob

在 C 参考实现中，访问方式固定为：

- `weight[o * input_dim + i]`

因此硬件若直接从导出的 `*.h` / `*.json` 初始化 BRAM，应按：

- `out-major`
- `row-major[out][in]`

理解。

### 7.6 对齐建议

当前导出数组本身没有强制加 `32B/64B` 对齐修饰。

因此建议：

- 片上 BRAM 初始化：
  - 直接按导出顺序放置即可
- DDR 输入输出 buffer：
  - 建议 CPU 侧按 `32 Byte` 对齐
- v1 不建议把 `weight + bias` 再人为重新打包成复杂格式

先保证可验证性，再做布局优化。

---

## 8. 当前建议交付硬件侧的文件

### 8.1 推荐主版本

当前推荐交付目录：

- [input_convergence_k3_rcs21_20260406](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406)

其中包含：

- [student_k3_rcs21_20260406.pt](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/student_k3_rcs21_20260406.pt)
- [k3_rcs21.yaml](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/k3_rcs21.yaml)
- [radar_mlp_binary_k3_rcs21_params.h](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/radar_mlp_binary_k3_rcs21_params.h)
- [radar_mlp_binary_k3_rcs21_params.json](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/radar_mlp_binary_k3_rcs21_params.json)
- [Radar_mlp_binary_k3_rcs21Params.scala](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/Radar_mlp_binary_k3_rcs21Params.scala)

### 8.1.1 导出元数据说明

当前参数摘要文件已经包含以下硬件关键信息：

- `weight_layout = row_major[out][in]`
- `bias_layout = separate_int32[out]`
- `requant_mode = float_mul_scale_then_round`
- `rounding = round_to_nearest_ties_to_even`
- `clamp_range = [-127, 127]`
- 每层 `input_scale / weight_scale / output_scale`

文件位置：

- [radar_mlp_binary_k3_rcs21_params.json](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/radar_mlp_binary_k3_rcs21_params.json)

### 8.2 硬件侧最关心的文件

如果硬件侧只先接最关键内容，优先看：

1. `radar_mlp_binary_k3_rcs21_params.h`
2. `radar_mlp_binary_k3_rcs21_params.json`
3. `Radar_mlp_binary_k3_rcs21Params.scala`

### 8.3 最小回归包

为了避免硬件侧后续反复追问，我已经额外生成了一个最小 golden 对拍包：

- [hardware_golden](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden)

其中包含：

- [golden_input.bin](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_input.bin)
- [golden_input.h](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_input.h)
- [golden_logits.bin](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_logits.bin)
- [golden_logits.h](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_logits.h)
- [golden_intermediate.json](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_intermediate.json)
- [golden_manifest.json](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_manifest.json)

当前这组 golden 样本对应：

- `split = test`
- `sample_index = 0`
- ground truth：`pedestrian`
- prediction：`pedestrian`

### 8.4 当前 golden 样本的关键数值

当前 `golden_input.int8` 为：

`[6, 20, -25, 0, 0, 1, 1, 32, 33, 32, 0, 0, 0, 35, -2, 1, -4, -2, 0, 0, 0]`

当前最终 `logits_int32` 为：

`[855, -10706]`

对应浮点近似 logits 为：

`[0.2399662584, -3.0047705173]`

硬件侧最简单的单样本对拍方式是：

1. 直接喂 `golden_input.bin`
2. 检查输出是否为 `golden_logits.bin`
3. 如果不一致，再对照 `golden_intermediate.json` 检查每层中间结果

---

## 9. 第一版 accelerator 的推荐实现方式

### 9.1 推荐实现原则

第一版建议做成一个**固定结构**的三层 FC accelerator，而不是通用大矩阵引擎。

原因：

- 当前模型非常小
- 结构已经固定
- 论文目标是形成系统闭环，不是做通用 DNN 编译器

### 9.2 推荐 v1 结构

建议 v1 结构如下：

- 输入 buffer：缓存 `21` 个 `int8`
- 权重存储：片上 BRAM/ROM
- 中间激活 buffer：
  - `64`
  - `32`
- 输出 buffer：`2` 个 `int32`
- 运算流程：
  - L1 GEMV + bias + requant + ReLU
  - L2 GEMV + bias + requant + ReLU
  - L3 GEMV + bias

### 9.3 中间层输出的类型

v1 建议明确固定为：

- `L1 accum`：`int32[64]`
- `L1 output`：`int8[64]`
- `L2 accum`：`int32[32]`
- `L2 output`：`int8[32]`
- `L3 output`：`int32[2]`

这样可以和当前 golden 中间结果一一对应。

### 9.4 为什么不建议 v1 直接做 DDR 权重流

当前总权重只有：

- `3456 Byte`

这个规模非常适合片上常驻。

所以 v1 更推荐：

- 权重固化到 BRAM/ROM
- DDR 只搬输入和输出

这样可以减少：

- DMA 复杂度
- DDR 权重访存开销
- 控制面复杂度

### 9.4 后续扩展空间

如果以后需要支持更多模型版本，再演进到：

- DDR 权重加载
- 参数热切换
- 通用 PE 阵列

但这些不建议作为第一步。

---

## 10. 推荐的数据流与内存组织

### 10.1 推荐数据流

保持当前已板测通过的路线：

> `CPU/PC -> DDR -> MM2S -> accelerator -> S2MM -> DDR -> CPU`

### 10.2 建议输入布局

单样本输入：

- `21` 个 `int8`

建议对齐到至少 `32 Byte` 边界，便于 DMA 处理。

示例：

- 有效输入：`21 Byte`
- padding：补到 `32 Byte`

### 10.3 建议输出布局

单样本输出：

- `2` 个 `int32 logits`

输出大小：

- `8 Byte`

建议也做固定对齐，例如：

- 有效输出：`8 Byte`
- padding：补到 `16 Byte` 或 `32 Byte`

### 10.4 批处理建议

第一版建议固定成：

| 项目 | 建议语义 |
|---|---|
| `num_samples` | 一次 DMA 事务中连续处理的样本数 |
| 输入 layout | contiguous，每个样本一段 |
| 输入 stride | 推荐 `32 Byte` |
| 输出 layout | contiguous，每个样本一段 |
| 输出 stride | 推荐 `16 Byte` 或 `32 Byte` |
| 样本处理方式 | 逐样本串行，通过同一个 accelerator 重复消费 |

也就是说，v1 推荐的 batch 语义是：

> `N` 个样本顺序排布在 DDR 中，accelerator 在一次启动后逐样本串行处理。

不建议一开始就做复杂变长点簇流接口，因为当前板上部署对象本来就是**已经统计好的定长特征向量**。

---

## 11. 推荐 CSR / 控制接口草案

如果 accelerator 继续挂在当前 AXI DMA 流水中，建议 MMIO/CSR 至少包含：

1. `src_addr`
   - 输入向量在 DDR 中的起始地址
2. `dst_addr`
   - 输出 logits 在 DDR 中的起始地址
3. `num_samples`
   - 本次需要处理的样本数
4. `start`
   - 启动位
5. `done`
   - 完成位
6. `status`
   - 忙/空闲/错误
7. `irq_enable`
   - 可选
8. `model_id`
   - 可选，后续支持 `18` 维或 `21` 维版本时有帮助

如果 v1 权重固化，CSR 不需要管理权重地址。

### 11.1 CPU 与 accelerator 的边界再明确一次

为了避免后续边界反复漂移，当前建议固定为：

- `argmax`：留在 CPU
- 权重管理：
  - v1 固化在 accelerator 片上
  - v2 再考虑热切换
- Rocket 端职责：
  - 准备输入
  - 配置 CSR
  - 启动 DMA
  - 读取输出
  - 做最终分类判决
- Rocket **不参与任何逐层数值计算**

---

## 12. 软件与硬件对齐的验证建议

硬件侧完成后，建议按以下顺序回归：

### 12.1 单样本对齐

对同一个输入向量，同时跑：

- Python 量化参考
- C 参考实现
- FPGA accelerator

检查：

- 每层中间结果是否一致
- 最终 logits 是否一致

这里建议直接使用：

- [golden_input.h](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_input.h)
- [golden_logits.h](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_logits.h)
- [golden_intermediate.json](/home/student/CaiWeijie/project/radar_cluster_rocc_exp/releases/input_convergence_k3_rcs21_20260406/hardware_golden/golden_intermediate.json)

### 12.2 小批量回归

随机抽取若干样本，例如：

- `100`
- `1000`

比较：

- logits 一致性
- `argmax` 一致率

### 12.3 全链路验证

验证：

- DDR 输入写入
- MM2S
- accelerator
- S2MM
- CPU 读取输出

这一步应尽量复用你们已经跑通的 DMA 流水框架。

---

## 13. 当前是否还要继续做软件侧大调整

我的建议是：

- **不再做大范围 student 结构搜索**
- 以当前 `k=3 + rcs21` 为主版本开始做硬件

因为现在再继续改，最可能变化的是：

- 权重
- 轻微 loss
- 轻微特征统计

而不是 accelerator 主结构。

### 13.1 允许保留的软件侧工作

软件侧后续仍可以做的小范围工作有：

- 生成固定输入向量文件
- 生成硬件回归样本
- 对 `baseline18` 做保守备份

### 13.2 不建议现在继续拖延的原因

如果继续等待“绝对最优”模型，硬件侧会一直缺一个冻结目标。

而当前这个模型已经满足：

- 结果稳定
- 结构简单
- 参数小
- 可量化
- 已有完整导出文件

这已经足够作为第一版 accelerator 的冻结对象。

---

## 14. 最终建议

### 14.1 当前冻结的主版本

建议硬件侧优先按下面这个版本实现：

> **`k=3 + rcs21 + 21 -> 64 -> 32 -> 2` INT8 QMLP**

### 14.2 当前保留的 fallback

如果后续 RCS 路线需要回退，保留：

> **`k=3 + baseline18 + 18 -> 64 -> 32 -> 2`**

### 14.3 实施优先级

当前最推荐的推进顺序是：

1. 硬件侧按固定三层 FC accelerator 开始实现
2. 软件侧准备定长输入向量与 golden 输出
3. 完成 Python/C/FPGA 三方一致性验证
4. 再考虑更复杂的参数热切换或更通用阵列

一句话概括：

> 现在已经可以把模型冻结给硬件侧，第一版 accelerator 不需要承担多帧融合和特征提取，只需要稳定完成 `21 -> 64 -> 32 -> 2` 的 INT8 MLP 推理即可。
