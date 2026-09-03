# GET /api/wfm/sisters —— 帕尔沃斯姐妹武器列表

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

| 参数 | 说明 |
|---|---|
| `lang` | 语言 |
| `name` | 名称模糊搜索 |
| `mastery_min` / `mastery_max` | 精通段位要求范围 |
| `limit` / `offset` | 分页 |

`total` 为命中总数（分页前）。响应含 `filters` 回显。

```bash
# 段位要求 8..14 的信条武器
curl "http://127.0.0.1:8099/api/wfm/sisters?mastery_min=8&mastery_max=14&lang=zh"
```
```json
{
  "lang": "zh",
  "filters": { "name": null, "mastery": { "min": 8, "max": 14 } },
  "items": [ {
    "slug": "tenet_envoy",
    "item_name": "信条·典客",
    "mastery_level": 14
  } ],
  "total": 11,
  "limit": 20, "offset": 0
}
```
