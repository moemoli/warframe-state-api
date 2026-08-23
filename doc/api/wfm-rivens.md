# GET /api/wfm/rivens —— 紫卡武器列表

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

| 参数 | 说明 |
|---|---|
| `lang` | 语言 |
| `name` | 名称模糊搜索 |
| `type` | 紫卡类型过滤：`rifle`/`pistol`/`melee`/`shotgun` |
| `limit` / `offset` | 分页 |

```bash
curl "http://127.0.0.1:8099/api/wfm/rivens?name=rubico&lang=zh"
```
```json
{ "items": [ {
    "wfm_id": "5c5ca81696e8d2003834fd90",
    "slug": "rubico",
    "game_ref": "/Lotus/Weapons/Tenno/LongGuns/FiveShotSniper/FiveShotSniper",
    "riven_type": "rifle",
    "group": "primary",
    "disposition": 0.95,
    "mastery_level": 6
} ], "total": 1 }
```
