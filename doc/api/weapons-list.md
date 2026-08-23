# GET /api/weapons —— 武器列表

> 分组：资料查询　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

全量武器库（ExportWeapons/RailjackWeapons）：主武/副武/近战分类，含面板摘要，支持中文名模糊搜索。

| 参数 | 说明 |
|---|---|
| `lang` / `category`（product_category）/ `name`（模糊） | 过滤 |
| `limit` / `offset` | 分页 |

```bash
curl "http://127.0.0.1:8099/api/weapons?category=LongGuns&limit=3&lang=zh"
```
