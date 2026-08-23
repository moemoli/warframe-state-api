# GET /api/cycles —— 世界循环（本地计算）

> 分组：世界状态　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**开放世界环境循环**：地球夜灵平原的昼/夜（夜晚出没夜灵 Eidolon）、金星奥布山谷的温/冷（影响鱼类与矿点）、火卫二魔胎之境的 Fass/Vome、扎里曼的 Corpus/Grineer 势力时段、双衍王境的五种心绪（决定支线与奖励）。这些循环由固定周期公式驱动，本服务**本地计算**，不依赖官方接口、无缓存延迟。

本地计算，不依赖官方 API。支持 7 个循环：

| 循环 | 名称 | 周期 |
|---|---|---|
| `cetus` | 夜灵平原 | 白天 100m / 夜晚 50m |
| `earth` | 地球 | 白天 4h / 夜晚 4h |
| `vallis` | 金星平原 | 温暖 6m40s / 寒冷 20m |
| `cambion` | 火卫二 | Fass/Vome 与 cetus 同步 |
| `zariman` | 扎里曼 | Corpus 150m / Grineer 150m |
| `duviri` | 双衍王境 | 5 种心绪各 120m |
| `midrath` | Midrath | 白天 32m / 夜晚 16m |

| 参数 | 说明 |
|---|---|
| `name` | 单查：`cetus/earth/cambion/vallis/zariman/duviri/midrath` |

```bash
curl "http://127.0.0.1:8099/api/cycles?name=cetus"
```
```json
{ "cycles": [ {
  "name": "cetus", "name_zh": "夜灵平原",
  "state": "day", "state_name": "白天",
  "activation": "2026-08-23T07:30:00Z",
  "expiry": "2026-08-23T09:10:00Z",
  "remaining_seconds": 3427, "remaining": "57m"
} ] }
```

---
