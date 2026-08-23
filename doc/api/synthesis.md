# GET /api/synthesis —— 结合仪式目标汇总

> 分组：资料查询　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**结合仪式（Synthesis）**：每日任务要求玩家在指定节点扫描指定敌人（Simaris 声望）。本端点整理了社区验证的每日六大任务地点、目标敌人清单与铭刻推荐，支持按目标名反查地点。

静态参考数据：每日结合任务地点 + 铭刻推荐表。

| 参数 | 说明 |
|---|---|
| `type` | `daily`=仅每日任务 / `imprints`=仅铭刻推荐 / 缺省=全部 |
| `target` | **按目标反查地点**（子串匹配，忽略大小写）。命中时额外输出 `by_target` 映射：`{目标名: [地点,...]}`（已去重）；无匹配返回 404 |

```bash
curl "http://127.0.0.1:8099/api/synthesis"                # 全部
curl "http://127.0.0.1:8099/api/synthesis?type=daily"     # 仅每日任务
curl "http://127.0.0.1:8099/api/synthesis?type=imprints"  # 仅铭刻
curl "http://127.0.0.1:8099/api/synthesis?target=火焰轰击者"
```
`?target=火焰轰击者` 响应：
```json
{ "by_target": { "火焰轰击者": ["CASSINI（土星捕获）"] }, "daily": [...], "imprints": [...] }
```
`?target=枪兵` 响应（子串匹配同时命中 枪兵/堕落枪兵/盾枪兵）：
```json
{ "by_target": {
    "枪兵":     ["LEX（谷神星捕获）"],
    "堕落枪兵": ["神后塔（虚空捕获）"],
    "盾枪兵":   ["CASSINI（土星捕获）"]
} }
```
```json
{
  "daily": [
    { "node": "LEX", "system": "谷神星", "mission": "捕获",
      "targets": ["枪兵", "恶徒", "禁卫军", "开膛者", "..."] }
  ],
  "imprints": [
    { "target": "枪兵", "location": "LEX（谷神星捕获）" }
  ],
  "notes": ["若星球节点正在被入侵……", "部分地点可能不出现目标"]
}
```

---
