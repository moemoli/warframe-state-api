# GET /api/wfm/rankings —— 查询热度排行

> 分组：系统　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

本站自身的查询热度排行榜（搜索首命中与详情访问自增计数），可用于发现当前玩家关注焦点。冷启动为空属正常。

| 参数 | 说明 |
|---|---|
| `type` | 实体类型：`warframes`/`weapons`/`mods` 等（默认 warframes） |
| `lang` / `limit` | 常规（默认 Top10） |

数据来源为本服务自身的查询热度统计（搜索首个命中 + 武器/Mod 详情自增）。
**冷启动阶段返回空数组属正常**，随使用量增长。

```bash
curl "http://127.0.0.1:8099/api/wfm/rankings?type=warframes&lang=zh"
```
```json
{ "type": "warframes", "items": [
  { "rank": 1, "entity_type": "warframes",
    "entity_id": "/Lotus/Powersuits/Garuda/Garuda",
    "name": "Garuda", "hits": 2 }
] }
```

---
