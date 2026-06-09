# 架构图资料入口

本目录保存论文/答辩图的文字描述、Visio COM 对接 JSON 和可预览 Mermaid 图。

## 文件

| 文件 | 用途 |
| --- | --- |
| [architecture_diagrams.md](architecture_diagrams.md) | 中文图纸说明和画图要求 |
| [visio_com_schema.md](visio_com_schema.md) | Windows GPT/Visio COM 脚本应读取的 JSON 字段约定 |
| [system_overview.visio.json](system_overview.visio.json) | SoC 总体架构图 |
| [dataflow.visio.json](dataflow.visio.json) | 数据从点集到 logits 的流程图 |
| [rocc_path.visio.json](rocc_path.visio.json) | `rqdot4` RoCC 指令路径图 |
| [system_overview.mmd](system_overview.mmd) | Mermaid 预览 |
| [dataflow.mmd](dataflow.mmd) | Mermaid 预览 |

## 命名规则

- 图中中文优先，专有名词保留英文。
- 节点必须包含模块名、功能、协议或数据类型。
- 连线必须包含方向、协议、位宽或数据 shape。
- Visio JSON 是后续 Windows 自动画图的主格式；Mermaid 只用于快速预览。
