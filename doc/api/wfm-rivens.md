# GET /api/wfm/rivens —— 紫卡武器列表

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

| 参数 | 说明 |
|---|---|
| `lang` | 语言 |
| `name` | 名称模糊搜索 |
| `type` | 紫卡类型过滤：`rifle`/`pistol`/`melee`/`shotgun` |
| `mastery_min` / `mastery_max` | 精通段位要求范围 |
| `disp_min` / `disp_max` | 倾向值范围 |
| `limit` / `offset` | 分页 |

`total` 为命中总数（分页前）。响应含 `filters` 回显。

```bash
# 段位要求 ≥8 且倾向 ≥1.0 的步枪紫卡
curl "http://127.0.0.1:8099/api/wfm/rivens?type=rifle&mastery_min=8&disp_min=1.0&lang=zh"
```
```json
{
  "lang": "zh",
  "filters": {
    "name": null, "type": "rifle",
    "mastery": { "min": 8, "max": null },
    "disposition": { "min": 1.0, "max": null }
  },
  "items": [ {
    "wfm_id": "5c5ca81696e8d2003834fd90",
    "slug": "rubico",
    "game_ref": "/Lotus/Weapons/Tenno/LongGuns/FiveShotSniper/FiveShotSniper",
    "riven_type": "rifle",
    "group": "primary",
    "disposition": 0.95,
    "mastery_level": 6
  } ],
  "total": 1,
  "limit": 20, "offset": 0
}
```
