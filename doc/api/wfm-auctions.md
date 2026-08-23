# GET /api/wfm/auctions/{slug} —— 紫卡拍卖（实时）

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

代理 warframe.market v1 拍卖接口。**slug 为紫卡武器命名空间**（`rubico`，非 `rubico_prime`），可经 `/api/wfm/rivens` 解析。

| 参数 | 说明 |
|---|---|
| `limit` | 返回条数（默认 20，上限 50；内部按价格升序排列后截取） |

```bash
curl "http://127.0.0.1:8099/api/wfm/auctions/rubico?lang=zh"
```
```json
{ "slug": "rubico", "total": 499, "auctions": [ {
    "price": 3000, "buyout": false, "top_bid": 3000,
    "rank": 8, "rerolls": 9, "mastery_level": 16,
    "polarity": "madurai", "riven_name": "crita-visitis",
    "user": "...", "status": "offline",
    "attributes": [
      { "name": "critical_damage", "value": 97.5, "negative": false },
      { "name": "zoom", "value": -40.0, "negative": true }
    ]
} ] }
```

> 成功响应会自动写入 `wfm_price_snapshots(kind=riven)` 当日快照。
