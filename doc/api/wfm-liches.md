# GET /api/wfm/liches —— 赤毒玄骸武器列表

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

| 参数 | 说明 |
|---|---|
| `lang` | 语言 |
| `name` | 名称模糊搜索 |
| `mastery_min` / `mastery_max` | 精通段位要求范围 |
| `limit` / `offset` | 分页 |

`total` 为命中总数（分页前）。响应含 `filters` 回显。

```bash
# 段位要求 ≥8 的赤毒武器
curl "http://127.0.0.1:8099/api/wfm/liches?mastery_min=8&lang=zh"
```
```json
{
  "lang": "zh",
  "filters": { "name": null, "mastery": { "min": 8, "max": null } },
  "items": [ {
    "slug": "kuva_bramma",
    "item_name": "赤毒·布拉玛",
    "mastery_level": 15
  } ],
  "total": 21,
  "limit": 20, "offset": 0
}
```
