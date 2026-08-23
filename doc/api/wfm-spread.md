# GET /api/wfm/spread/{slug} —— 紫卡词条价差

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**词条价差分析**：对同一武器的全部紫卡拍卖聚合统计，回答"这把枪洗出哪个词条最值钱"。仅统计正面词条且样本 ≥2，输出按均价降序。

基于同一拍卖数据聚合：各**正面**词条在挂单中的平均价格排行（≥2 样本才计入）。

```bash
curl "http://127.0.0.1:8099/api/wfm/spread/rubico"
```
```json
{ "slug": "rubico", "samples": 499, "attributes": [
  { "attribute": "multishot",       "avg_price": 4136, "samples": 270 },
  { "attribute": "critical_chance", "avg_price": 3645, "samples": 309 },
  { "attribute": "critical_damage", "avg_price": 3243, "samples": 333 }
] }
```
