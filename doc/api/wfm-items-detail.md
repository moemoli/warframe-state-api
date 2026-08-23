# GET /api/wfm/items/{slug} —— 物品详情 + 实时价格

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

warframe.market（国际服玩家交易平台）单品实时行情：最低卖单/平均卖价/最高收单与最优订单列表。Warframe 内交易以白金(Pt)结算，WM 是事实上的交易所。

查本地数据库获取物品信息，同时实时请求 [warframe.market API v2](https://api.warframe.market/v2/) 获取最优买卖订单。

| 参数 | 说明 |
|---|---|
| `lang` | 语言 |

```bash
curl "http://127.0.0.1:8099/api/wfm/items/adaptation?lang=zh"
```
```json
{
  "wfm_id": "5bc1ab93b919f200c18c10ef",
  "slug": "adaptation",
  "game_ref": "/Lotus/Upgrades/Mods/Warframe/AvatarResistanceOnDamageMod",
  "item_name": "适应",
  "description": "受伤后：+10% 对该种伤害类型的抗性...",
  "wiki_link": "https://wiki.warframe.com/w/Adaptation",
  "tags": ["mod", "warframe", "rare"],
  "tradable": true,
  "rarity": "rare",
  "trading_tax": 8000,
  "ducats": null,
  "prices": {
    "sell": {
      "min": 4,
      "avg": 4,
      "orders": [
        { "platinum": 4, "quantity": 9, "user": "DaJiBaZHENXIANG", "status": "ingame" }
      ]
    },
    "buy": {
      "max": 41,
      "orders": [
        { "platinum": 41, "quantity": 6, "user": "SpaceXero", "status": "ingame" }
      ]
    }
  }
}
```

| prices 字段 | 说明 |
|---|---|
| `sell.min` | 最低卖价（白金） |
| `sell.avg` | 平均卖价 |
| `buy.max` | 最高买价（白金） |
| `sell/buy.orders` | 最优 5 条订单（含玩家名、数量、在线状态） |

> 注：价格数据实时从 warframe.market 获取，受其 3 req/s 限流。`prices` 获取失败时返回 `null`。

---
