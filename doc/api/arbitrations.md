# GET /api/arbitrations —— 仲裁（Arbitrations）

> 分组：世界状态　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**仲裁（Arbitrations）**是通关全部星图后解锁的高难度轮换任务：敌人等级大幅提升、携带特殊修正，奖励为稀有赋能与内融核心。每 **1 小时**轮换一个节点，本端点基于 browse.wf 的公开排期表返回当前进行中的一轮与后续排程。

从 `browse.wf/arbys.txt` 实时拉取仲裁轮次数据，解析节点信息并格式化。

| 参数 | 说明 |
|---|---|
| `lang` | 译文语言，默认 zh |
| `limit` | 返回未来任务条数，默认 10 |

```bash
curl "http://127.0.0.1:8099/api/arbitrations?lang=zh&limit=5"
```

### 返回格式

```json
{
  "latest": {
    "activation": "2026-08-23T10:00:00Z",
    "expiry": "2026-08-23T11:00:00Z",
    "node": {
      "id": "SolNode118",
      "name": "Laomedeia",
      "system": { "index": 7, "name": "海王星" }
    },
    "mission_type": "中断",
    "faction": "Corpus",
    "enemy_levels": { "min": 25, "max": 30 }
  },
  "schedule": {
    "count": 5,
    "entries": [
      {
        "activation": "2026-08-23T11:00:00Z",
        "expiry": "2026-08-23T12:00:00Z",
        "node": {
          "id": "SolNode118",
          "name": "Laomedeia",
          "system": { "index": 7, "name": "海王星" }
        },
        "mission_type": "中断",
        "faction": "Corpus",
        "enemy_levels": { "min": 25, "max": 30 }
      }
    ]
  }
}
```

| 字段 | 说明 |
|---|---|
| `latest` | 当前正在进行的仲裁（`null` 表示轮换间隙） |
| `schedule.count` | 未来任务数 |
| `schedule.entries` | 未来任务列表，每条含完整节点/任务/派系/等级信息 |
| `node.id` | 节点内部标识（如 `SolNode118`） |
| `node.name` | 节点显示名（已翻译） |
| `node.system.index` | 星系编号 |
| `node.system.name` | 星系名（已翻译，如「海王星」） |
| `mission_type` | 任务类型（已翻译） |
| `faction` | 派系（已翻译） |
| `enemy_levels` | 基础敌人等级（regions 表数据） |

> 注：`enemy_levels` 为节点基础等级，实际仲裁等级会随轮次递增（60-80 起步，每轮 +15~20）。

---
