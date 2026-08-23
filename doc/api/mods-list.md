# GET /api/mods —— Mod 查询

> 分组：资料查询　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

**MOD 卡**是 Warframe 的核心养成系统：插在战甲/武器上提供属性与技能强化的卡片。本端点按类型/极性/稀有度筛选全量 Mod 库（来源 ExportUpgrades）。

| 参数 | 说明 |
|---|---|
| `lang` / `type` / `name` / `polarity` / `rarity` | 过滤（name 为名称模糊） |
| `limit` / `offset` | 分页（默认 20/0，limit 上限 100） |

```bash
curl "http://127.0.0.1:8099/api/mods?type=PRIMARY&rarity=RARE&limit=5&lang=zh"
```
```json
{ "mods": [ { "unique_name": "/Lotus/Upgrades/Mods/...", "name": "...",
              "type": "PRIMARY", "polarity": "AP_V", "rarity": "RARE",
              "base_drain": 14, "fusion_limit": 5 } ],
  "total": 5, "limit": 5, "offset": 0 }
```
