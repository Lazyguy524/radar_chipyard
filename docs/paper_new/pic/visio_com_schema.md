# Visio COM JSON Schema

Windows 下的 GPT/脚本可以读取 `*.visio.json` 自动生成 Visio 图。JSON 不追求通用图论格式，而追求足够稳定、直观、易映射到 Visio shapes。

## 顶层字段

```json
{
  "title": "图标题",
  "language": "zh-CN",
  "page": {"width_in": 13.33, "height_in": 7.5, "orientation": "landscape"},
  "style": {"font": "Microsoft YaHei", "line_color": "#334155"},
  "groups": [],
  "nodes": [],
  "edges": [],
  "notes": []
}
```

## group

```json
{
  "id": "control_plane",
  "label": "控制面",
  "x": 0.4,
  "y": 0.4,
  "w": 12.4,
  "h": 2.0,
  "fill": "#dbeafe"
}
```

## node

```json
{
  "id": "rocket",
  "label": "Rocket Core",
  "subtitle": "bare-metal 控制与校验",
  "x": 0.8,
  "y": 1.0,
  "w": 1.8,
  "h": 0.8,
  "shape": "rounded_rect",
  "fill": "#e0f2fe",
  "tags": ["CPU", "control"]
}
```

## edge

```json
{
  "from": "rocket",
  "to": "dma_ctrl",
  "label": "MMIO 配置",
  "protocol": "AXI4/AXI4-Lite",
  "width": "32-bit regs",
  "style": "control",
  "arrow": "end"
}
```

## note

```json
{
  "id": "boundary",
  "text": "当前 RoCC 只实现 rqdot4；2.689x 是 QMLP kernel/profile，不是 full-chain e2e。",
  "x": 9.5,
  "y": 6.4,
  "w": 3.0,
  "h": 0.6
}
```

## 生成约定

- 坐标单位建议用 inch，方便 Visio PageSheet 设置。
- `shape` 第一版只需支持 `rect`、`rounded_rect`、`cylinder`、`document`、`note`。
- `style=control` 用虚线或蓝色线，`style=data` 用实线或绿色线，`style=instruction` 用紫色线。
- 所有 label 尽量中文；专有名词可保留英文。
