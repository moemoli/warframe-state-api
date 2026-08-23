# POST /api/worldstate/_refresh —— 强制刷新

> 分组：系统　|　[← 返回索引](README.md)

受最小间隔保护（`WORLDSTATE_MIN_INTERVAL`，默认 30s），过早触发返回 429。

```bash
curl -X POST "http://127.0.0.1:8099/api/worldstate/_refresh"
```

---
