# GET /api/wfm/items —— warframe.market 物品列表

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

从本地数据库查询 warframe.market 物品数据（来源：[42bytes-team/wfm-items](https://github.com/42bytes-team/wfm-items)）。

| 参数 | 说明 |
|---|---|
| `lang` | 语言（zh/en/ru/ko/de/fr/pt 等） |
| `name` | 名称模糊搜索 |
| `tag` | 标签过滤（如 `mod`、`prime`、`relic`） |
| `tradable` | 可交易过滤（`true`/`false`） |
| `limit` / `offset` | 分页（默认 20/0，上限 100） |

```bash
curl "http://127.0.0.1:8099/api/wfm/items?name=adaptation&lang=zh"
```
```json
{ "items": [ {
    "wfm_id": "5bc1ab93b919f200c18c10ef",
    "slug": "adaptation",
    "game_ref": "/Lotus/Upgrades/Mods/Warframe/AvatarResistanceOnDamageMod",
    "tags": ["mod", "warframe", "rare"],
    "tradable": true,
    "rarity": "rare",
    "trading_tax": 8000,
    "item_name": "适应",
    "icon": "items/images/en/adaptation....png",
    "thumb": "items/images/en/thumbs/adaptation....128x128.png"
} ], "total": 1, "limit": 20, "offset": 0 }
```

---
