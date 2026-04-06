# 输入收敛版本备份说明

## 1. 本目录用途

本目录用于备份当前推荐的 student 版本，避免后续继续修改代码或清理 `logs/` 后丢失关键结果。

当前冻结版本为：

> 多帧融合 `k=3` + `rcs21` 输入 + `21 -> 64 -> 32 -> 2` INT8 QMLP

---

## 2. 本目录包含内容

- `student_k3_rcs21_20260406.pt`
  - 当前推荐 student checkpoint
- `k3_rcs21.yaml`
  - 该模型对应训练配置
- `radar_mlp_binary_k3_rcs21_params.h`
  - C / bare-metal 参数头文件
- `radar_mlp_binary_k3_rcs21_params.json`
  - 参数摘要与 shape 说明
- `Radar_mlp_binary_k3_rcs21Params.scala`
  - Scala / Chisel 侧参数文件
- `hardware_golden/`
  - 硬件最小对拍包
  - 包含一组真实输入、golden logits 和每层中间结果

---

## 3. 当前版本为什么值得备份

这轮输入收敛实验比较了：

- `baseline18`
- `compact14`
- `rcs21`

并分别在：

- 单帧 full
- 多帧 `k=3`

上做了对比。

最终结论是：

- 单帧下：`baseline18` 最稳
- 多帧 `k=3` 下：`rcs21` 最优

当前推荐结果：

- `accuracy = 0.9279`
- `macro_f1 = 0.9178`

对应指标文件在：

- `logs/input_convergence_2026-04-06/train/k3_rcs21/student_metrics.json`

---

## 4. 使用建议

### 4.1 论文主线

如果 thesis 允许在 PC 端完成预处理后再把输入送板子，建议优先采用这一版本。

### 4.2 硬件主线

如果硬件侧希望先稳定形成闭环，可以直接基于本目录里的导出参数实现 accelerator。

当前最建议硬件优先对接的文件是：

- `radar_mlp_binary_k3_rcs21_params.h`
- `radar_mlp_binary_k3_rcs21_params.json`
- `hardware_golden/golden_input.h`
- `hardware_golden/golden_logits.h`
- `hardware_golden/golden_intermediate.json`

### 4.3 保守备选

如果以后发现真实系统里 RCS 不稳定，可退回：

- 单帧或多帧 `k=3` 的 `baseline18`

---

## 5. 恢复方式

如果需要回到这个版本：

1. 使用本目录的 `k3_rcs21.yaml`
2. 加载 `student_k3_rcs21_20260406.pt`
3. 或直接把导出参数交给硬件侧使用

如果需要做 FPGA 单样本对拍，直接使用：

- `hardware_golden/golden_input.bin`
- `hardware_golden/golden_logits.bin`
- `hardware_golden/golden_intermediate.json`
