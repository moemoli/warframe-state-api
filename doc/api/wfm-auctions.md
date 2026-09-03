# GET /api/wfm/auctions/{slug} —— 紫卡拍卖（实时 + 服务端筛选）

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

代理 warframe.market v1 拍卖接口。**slug 为紫卡武器命名空间**（`rubico`，非 `rubico_prime`），可经 `/api/wfm/rivens` 解析。

服务端按条件筛选（**AND 语义**）：先过滤再排序，返回**仅命中**的拍卖、命中总数 `total`、
归一化 `filters` 回显，且每条命中项标注其满足的筛选点 `matched_conditions`。

## 筛选参数（wr 全语法维度，全部可选）

| 参数 | 含义 | 备注 |
|---|---|---|
| `limit` | 返回条数（默认 20，上限 50；命中后按价格升序截取） | 无筛选时与旧版等价 |
| `rerolls_min` / `rerolls_max` | 洗练次数范围 | 零洗=`0,0`；`5洗`→max=5 |
| `rank_min` / `rank_max` | mod 等级范围（0..8） | — |
| `mastery_min` / `mastery_max` | 精通段位要求范围 | — |
| `price_min` / `price_max` | 有效价格范围（买断价优先，无则起拍价） | `1000p`→max=1000 |
| `pos_min` / `pos_max` | 正面词条数量范围 | `2+`→min=2 |
| `neg_min` / `neg_max` | 负面词条数量范围 | `带负`→min=1；`无负`→max=0 |
| `attr_pos` | 必须包含的**正面**词条 slug，逗号分隔 | 与 `wfm_riven_attributes.slug` 一致 |
| `attr_neg` | 必须包含的**负面**词条 slug，逗号分隔 | 同上 |
| `polarity` | 极性：`madurai`/`naramon`/`vazarin`/`zenurik` | — |
| `status` | 卖家状态：`ingame`/`online`/`offline`/`any`（默认 any） | `online`=ingame+online |
| `lang` | 语言（默认 zh） | 词条 `name_zh` 与条件文案随语言 |

> 数值范围 `min>max`、非法 `polarity`/`status` → `400`。
> `limit` 仅约束返回条数；`total` 为**筛选命中总数**（截断前）。

```bash
# 零洗 + 至少 2 正面 + 无负面 + 双暴，买断价从低到高
curl "http://127.0.0.1:8099/api/wfm/auctions/rubico?lang=zh&rerolls_min=0&rerolls_max=0&pos_min=2&neg_max=0&attr_pos=critical_chance,critical_damage"
# mod 等级 8 + 段位 ≤15 + 价格 ≤500
curl "http://127.0.0.1:8099/api/wfm/auctions/rubico?rank_min=8&rank_max=8&mastery_max=15&price_max=500"
```
```json
{
  "slug": "rubico", "lang": "zh",
  "filters": {
    "rerolls": { "min": 0, "max": 0 }, "rank": { "min": null, "max": null },
    "mastery": { "min": null, "max": null }, "price": { "min": null, "max": 500 },
    "pos": { "min": 2, "max": null }, "neg": { "min": null, "max": 0 },
    "attr_pos": ["critical_chance", "critical_damage"], "attr_neg": [],
    "polarity": null, "status": "any"
  },
  "total": 3, "limit": 20,
  "auctions": [ {
    "price": 300, "buyout": true, "top_bid": null,
    "rank": 8, "rerolls": 0, "mastery_level": 16,
    "polarity": "madurai", "riven_name": "crita-visitis",
    "user": "...", "status": "online",
    "attributes": [
      { "name": "critical_chance", "name_zh": "暴击率", "value": 87.5, "negative": false },
      { "name": "critical_damage", "name_zh": "暴击伤害", "value": 97.5, "negative": false },
      { "name": "zoom", "name_zh": null, "value": -40.0, "negative": true }
    ],
    "matched_conditions": ["洗练=0", "正面词条数≥2", "负面词条数≤0",
                           "正面含「暴击率」", "正面含「暴击伤害」", "价格≤500"]
  } ]
}
```

> 无筛选时 `matched_conditions` 为空数组、`filters` 各字段为 null/空，行为与旧版兼容。
> 命中单会写入 `wfm_price_snapshots(kind=riven)` 当日快照（按命中集最低价/均价）。
