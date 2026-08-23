# GET /api/nodes/{nodeId} —— 星图节点详情

> 分组：资料查询　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**星图节点**即玩家执行任务的每一个具体地图点（如火星·Arval）。本端点返回该节点的所属星球、任务类型、占据派系、敌人等级区间、段位需求，以及关联的任务奖励表（掉落哪些遗物/Mod）——查"这张图值不值得打"。

| 参数 | 说明 |
|---|---|
| `lang` | 译文语言 |
| `expand` | `1`（默认）展开奖励表 / `0` 仅 deck 引用 |

```bash
curl "http://127.0.0.1:8099/api/nodes/SolNode94?lang=zh"
```
```json
{
  "type": "SolNode94",
  "name": "Apollodorus",
  "system": { "index": 0, "name": "水星" },
  "mission_type": { "code": "MissionName_Survival", "name": "生存" },
  "faction": { "code": "Faction_InfestationUC", "name": "Infestation" },
  "enemy_levels": { "min": 6, "max": 11 },
  "mastery_req": 0,
  "node_type": 0,
  "reward_manifests": ["/Lotus/Types/Game/MissionDecks/..."],
  "rewards": [ { "deck": "...", "deck_name": "...", "tiers": [ { "tier": 0, "items": [...] } ] } ]
}
```

| 字段 | 说明 |
|---|---|
| `type` | 节点内部标识 |
| `name` | 节点显示名（翻译） |
| `system.index` | 星系编号（0=水星, 1=金星, 2=地球, ...） |
| `system.name` | 星系名称（翻译） |
| `mission_type.code` | 任务类型标识 |
| `mission_type.name` | 任务类型名（翻译） |
| `faction.code` | 派系标识 |
| `faction.name` | 派系名（翻译） |
| `enemy_levels` | 敌人等级范围 |
| `mastery_req` | 段位要求 |
| `node_type` | 节点类型（0=普通, 1=枢纽, ...） |
| `rewards` | 奖励表展开（expand=1 时含 tier/items） |

---
