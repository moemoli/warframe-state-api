# GET /api/wfm/trends/{slug} —— 价格趋势

> 分组：市场（warframe.market）　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

价格历史走势。双数据源自动切换：普通物品优先返回 **wfm 官方成交统计**（48 小时小时级 + 90 天日级的真实成交量与均价曲线）；紫卡/赤毒/姐妹回退到本地快照表（随每次询价自动积累）。

双数据源，自动选择：

1. **`source: wfm_statistics`**（优先）：代理 wfm 官方统计接口，返回**真实成交数据**
   （48h 小时级 + 90d 日级：均价/最低/最高/中位数/移动均值/成交量）。普通物品 slug 可用。
2. **`source: local_snapshots`**（兜底）：上游无该 slug（紫卡/赤毒/姐妹）或请求失败时，
   回退本地快照表——随详情询价与拍卖查询自动写入当日 sell_min/sell_avg/buy_max。

| 参数 | 说明 |
|---|---|
| `range` | `90d`（默认）/ `48h`，仅对 `wfm_statistics` 源生效 |
| `kind` | 本地兜底源使用：`item`（默认）/`riven`/`lich`/`sister` |
| `days` | 本地兜底源回溯天数（默认 30，上限 365） |

```bash
# 普通物品 → wfm 官方统计（推荐）
curl "http://127.0.0.1:8099/api/wfm/trends/adaptation?lang=zh"
```
```json
{ "slug": "adaptation", "source": "wfm_statistics",
  "data": {
    "90d": [ { "datetime": "2026-08-22T00:00:00Z", "avg": 6.5, "min": 3.0,
               "max": 10.0, "median": 5.0, "moving_avg": 7.5, "volume": 71 },
             "... 共178个日级点" ],
    "48h": [ { "datetime": "...", "avg": 5.0, "min": 5.0, "max": 5.0,
               "median": 5.0, "moving_avg": 4.7, "volume": 2 },
             "... 共78个小时级点" ]
  } }
```

```bash
# 紫卡 → 本地快照兜底
curl "http://127.0.0.1:8099/api/wfm/trends/rubico?kind=riven"
```
```json
{ "slug": "rubico", "kind": "riven", "source": "local_snapshots",
  "points": [ { "day": "2026-08-23", "sell_min": 1, "sell_avg": 993, "buy_max": null } ] }
```

> 快照表 `wfm_price_snapshots` 由 `/api/wfm/items|rivens|liches|sisters/{slug}` 详情询价
> 与拍卖查询成功时自动 UPSERT 当日记录；冷启动无历史属正常。
