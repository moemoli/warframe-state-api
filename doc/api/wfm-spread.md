# GET /api/wfm/spread/{slug} —— 紫卡词条价差

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**词条价差分析**：对同一武器的紫卡拍卖聚合统计，回答"这把枪洗出哪个词条最值钱"。仅统计正面词条且样本 ≥2，输出按均价降序。

## 与 /api/wfm/auctions 共用筛选

支持与 `/api/wfm/auctions/{slug}` **完全相同**的筛选参数（`rerolls_min/max`、
`rank_min/max`、`mastery_min/max`、`price_min/max`、`pos_min/max`、`neg_min/max`、
`attr_pos`、`attr_neg`、`polarity`、`status`）：**先过滤拍卖样本，再对命中样本聚合**，
因此可回答"零洗/2+ 双暴/无负这类单子里，哪个词条最值钱"。响应带 `filters` 回显，
`samples` 为**命中拍卖数**。

```bash
# 零洗 + 2 正面无负的挂单中，各正面词条均价
curl "http://127.0.0.1:8099/api/wfm/spread/rubico?rerolls_max=0&pos_min=2&neg_max=0&lang=zh"
```
```json
{
  "slug": "rubico", "lang": "zh",
  "filters": {
    "rerolls": { "min": null, "max": 0 }, "rank": { "min": null, "max": null },
    "mastery": { "min": null, "max": null }, "price": { "min": null, "max": null },
    "pos": { "min": 2, "max": null }, "neg": { "min": null, "max": 0 },
    "attr_pos": [], "attr_neg": [], "polarity": null, "status": "any"
  },
  "samples": 47,
  "attributes": [
    { "attribute": "critical_damage", "attribute_zh": "暴击伤害", "avg_price": 2599, "samples": 22 },
    { "attribute": "critical_chance", "attribute_zh": "暴击率",    "avg_price": 1978, "samples": 28 }
  ]
}
```

> 无筛选时 `samples` 为全部挂单数，聚合行为与旧版一致（仅补上 `filters` 回显与词条中文名）。
