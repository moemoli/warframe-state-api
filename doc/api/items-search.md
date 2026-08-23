# GET /api/items/{name} —— 物品查询（旧版，兼容保留）

> 分组：资料查询　|　[← 返回索引](README.md)

三级查询流程，每条结果自动关联 warframe.market 数据：

1. `aliases` 表精确匹配简写（如 `血妈` → Garuda）
2. `v_localized` 名称模糊匹配（官方数据库）
3. `wfm_items` + `wfm_item_i18n` 名称模糊匹配（warframe.market 数据库）

官方数据库命中的结果通过 `game_ref` 自动关联 wfm 数据（ducats/trading_tax/tags 等）。

```bash
curl "http://127.0.0.1:8099/api/items/绝路?lang=zh"
```
```json
{ "query": "绝路", "resolved_alias": null, "results": [
  { "entity_type": "resources",
    "entity_id": "/Lotus/Types/Recipes/Weapons/WeaponParts/RubicoPrimeBarrel",
    "name": "绝路 Prime 枪管",
    "wfm": {
      "wfm_id": "5baa8bbf4567de01ac283493",
      "slug": "rubico_prime_barrel",
      "tags": ["component", "weapon", "prime"],
      "tradable": true,
      "ducats": 25,
      "trading_tax": 2000,
      "item_name": "绝路 Prime 枪管",
      "description": "一个 Prime 武器的制作部件。"
    }
  }
] }
```

| 字段 | 说明 |
|---|---|
| `entity_type` | 来源表（warframes/weapons/upgrades/customs/bundles/wfm 等） |
| `entity_id` | 游戏内 unique_name |
| `name` | 物品名称（已翻译） |
| `wfm` | warframe.market 关联数据（`null` 表示无可交易版本或未关联） |
| `wfm.slug` | warframe.market URL 路径（可用于跳转或查价） |
| `wfm.ducats` | 杜卡特值 |
| `wfm.trading_tax` | 交易税 |
| `wfm.tags` | 标签（mod/prime/relic/component 等） |
