# Warframe API 调用文档

> 服务地址默认 `http://<host>:8099`（可用 `BIND_ADDR` 配置）。
> 数据来源：warframe-public-export-plus（实体数据）+ 官方 worldState API + browse.wf（仲裁）+ wiki.warframe.com（枚举翻译）。

---

## 0. 通用约定

| 约定 | 说明 |
|---|---|
| **语言** | 所有端点支持 `?lang=zh`（缺省取 `DEFAULT_LANG`，默认 `zh`）；当前仅导入 zh/en 字典 |
| **时间** | 所有时间字段统一 **UTC ISO 8601**：`2026-08-23T10:00:00Z` |
| **URL 编码** | 路径参数含 `/` 时必须 URL 编码，如 `/Lotus/Powersuits/Wisp/Wisp` → `%2FLotus%2FPowersuits%2FWisp%2FWisp` |
| **响应** | 一律 `application/json`；错误统一 `{"error": "<原因>"}` |
| **错误码** | 400 参数错误 / 401 鉴权失败 / 404 未找到 / 429 过于频繁 / 500 数据库错误 / 502 worldstate 上游失败 / 503 服务未配置 |
| **worldstate 头** | `GET /api/worldstate` 响应头携带 `X-WorldState-Age`（缓存秒数）、`X-WorldState-Stale`（0/1） |

### 枚举翻译体系

所有世界状态中的内部枚举标识符均通过 `worldstate_enums` 表翻译。数据来源分两类：

**导出来源**（`load.py` 从 warframe-public-export-plus 自动生成）：

| 分类 | 前缀 | 示例 | 翻译来源 |
|---|---|---|---|
| `mission_type` | `MT_` | `MT_SURVIVAL` → 生存 | ExportMissionTypes.json |
| `faction` | `FC_` | `FC_CORPUS` → Corpus | ExportFactions.json |

**Wiki 手动维护**（`load.py` 中 `WIKI_ENUMS` 字典，来源 [wiki.warframe.com/w/World_State](https://wiki.warframe.com/w/World_State) + [doroprime](https://github.com/Yawanaika/doroprime)）：

| 分类 | 前缀 | 示例 |
|---|---|---|
| `sortie_boss` | `SORTIE_BOSS_` | `SORTIE_BOSS_AMAR` → 猎杀者Amar |
| `sortie_modifier` | `SORTIE_MODIFIER_` | `SORTIE_MODIFIER_FIRE` → 火焰增强 |
| `relic_tier` | `VoidT` | `VoidT1` → 古纪、`VoidT4` → 后纪 |
| `descent_type` | `DT_` | `DT_SHRINE_DEFENSE` → 祈运坛防御 |
| `descent_challenge` | *(多种)* | `HeavyWeaponsOnly` → 易受曲翼枪械攻击的敌人 |
| `descent_level` | *(地图片段)* | `ArenaCherry` → 樱桃竞技场 |
| `descent_specs` | *(敌人规格)* | `CoHCorpusExterminateMixed` → Corpus |
| `descent_aura` | *(Penance)* | `PoisonGasAura` → 化学战 |
| `archimedea_type` | `CT_` | `CT_LAB` → 深层Archimedea |
| `archimedea_difficulty` | `CD_` | `CD_HARD` → 精英Archimedea |
| `archimedea_deviation` | *(多种)* | `FortifiedFoes` → 密封装甲 |
| `archimedea_risk` | *(多种)* | `AcceleratedEnemies` → 大胆投机 |
| `archimedea_personal` | *(多种)* | `AbilityLockout` → 无力 |
| `calendar_season` | `CST_` | `CST_SPRING` → 春季 |
| `calendar_event_type` | `CET_` | `CET_CHALLENGE` → 挑战 |
| `upgrade_type` | `GAMEPLAY_*` | `GAMEPLAY_MONEY_REWARD_AMOUNT` → 星币加成 |
| `goal_tag` | *(事件名)* | `HeatFissure` → 热美亚裂缝 |

所有分类均可通过 `?lang=` 切换语言（当前支持 zh/en）。

---

## 1. GET /health —— 健康检查

```bash
curl http://127.0.0.1:8099/health
```
```json
{ "status": "ok", "database": "ok" }
```

---

## 2. GET /api/worldstate —— 官方 WorldState（解析+翻译）

官方源：`https://api.warframe.com/cdn/worldState.php`（默认 180s 缓存，单飞行并发，stale-while-error）。

| 参数 | 说明 |
|---|---|
| `lang` | 译文语言，默认 zh |
| `sections` | 分类筛选，逗号分隔（如 `alerts,fissures`）；空/缺省=全部；`cycles`、`meta` 恒附带 |

```bash
curl "http://127.0.0.1:8099/api/worldstate?sections=alerts,fissures,cycles&lang=zh"
```

### 2.1 返回节列表

| 节名 | 说明 | 对应 Wiki 章节 |
|---|---|---|
| `alerts` | 当前警报 | Alerts |
| `fissures` | 虚空裂缝 | ActiveMissions |
| `void_storms` | 虚空风暴 | VoidStorms |
| `invasions` | 入侵 | Invasions |
| `sortie` | 突击 | Sorties |
| `void_trader` | 虚空商人 Baro | VoidTraders |
| `daily_deals` | Darvo 每日特惠 | DailyDeals |
| `syndicate_missions` | 集团任务 | SyndicateMissions |
| `nightwave` | 午夜电波 | SeasonInfo |
| `events` | 新闻（News） | Events |
| `goals` | 活动/事件 | Goals |
| `descents` | 深塑池 | Descents |
| `persistent_enemies` | 追随者（Acolytes） | PersistentEnemies |
| `cycles` | 世界循环（本地计算） | — |
| `meta` | 缓存元数据 | — |
| `liteSorties` | 执刑官猎杀 | LiteSorties |
| `conquests` | Archimedea | Conquests |
| `flash_sales` | 商城特卖 | FlashSales |
| `global_upgrades` | 全局增益 | GlobalUpgrades |
| `news` | 新闻消息 | Events |
| `known_calendar_seasons` | 1999日历 | KnownCalendarSeasons |

### 2.2 透传节统一处理

未单独建模的节（如 `conquests`、`flash_sales`、`global_upgrades`、`known_calendar_seasons` 等）原样输出，但经过以下处理：

- `_id`（MongoDB ObjectId）**一律删除**
- `AllianceId` **删除**
- **字段名统一全小写**（`Activation`→`activation`、`TypeName`→`typename`）
- `Activation`/`Expiry`/`Date`/`EventStartDate`/`EventEndDate` 等时间字段一律转 **UTC ISO**
- 深度翻译：`MT_*`→任务类型、`FC_*`→派系、`SORTIE_BOSS_*`→Boss名、`SORTIE_MODIFIER_*`→修正名、`VoidT*`→遗物等级、`DT_*`→Descendia任务类型、物品路径→物品名、loc tag→译文
- `Events` 节（新闻）按 `LanguageCode` 筛选当前 `lang` 对应的消息

### 2.3 各节详细格式

**alerts** — 警报：

```json
{
  "id": "611ab7e6dca89d12db0c527f",
  "activation": "2026-08-23T00:00:00Z",
  "expiry": "2026-08-25T00:00:00Z",
  "mission": {
    "node": { "type": "SolNode711", "name": "Terrorem" },
    "mission_type": { "code": "MT_SURVIVAL", "name": "生存", "translated": true },
    "faction": { "code": "FC_INFESTATION", "name": "Infestation", "translated": true },
    "enemy_levels": { "min": 20, "max": 30 },
    "reward": [
      { "type": "/Lotus/Types/Items/MiscItems/OrokinCatalyst", "item_count": 1,
        "item_name": "Orokin反应堆", "translated": true }
    ],
    "description": "Gift of the Lotus"
  },
  "tag": "LotusGift"
}
```

**fissures** — 虚空裂缝（Modifier 翻译为遗物等级）：

```json
{
  "node": { "type": "SolNode66", "name": "Unda" },
  "mission_type": { "code": "MT_INTEL", "name": "间谍", "translated": true },
  "modifier": { "code": "VoidT1", "name": "古纪", "translated": true },
  "hard": true,
  "activation": "...", "expiry": "..."
}
```

**sortie** — 突击（Boss/Modifier 均翻译）：

```json
{
  "boss": { "code": "SORTIE_BOSS_RUK", "name": "Sargas Ruk将军", "translated": true },
  "reward": { "deck": "/Lotus/Types/Game/MissionDecks/SortieRewards", "deck_name": "SortieRewards",
              "tiers": [ { "tier": 0, "items": [ ... ] } ] },
  "variants": [ {
    "node": { "type": "SolNode15", "name": "Pacific" },
    "mission_type": { "code": "MT_RESCUE", "name": "救援", "translated": true },
    "modifier_type": { "code": "SORTIE_MODIFIER_FIRE", "name": "火焰增强", "translated": true }
  } ],
  "activation": "...", "expiry": "..."
}
```

**descents** — Descendia 暗折射（完整翻译）：

```json
{
  "challenges": [ {
    "type": "DT_BREAK_TARGETS",
    "type_name": "摧毁全息球",
    "challenge": "HeavyWeaponsOnly",
    "challenge_name": "易受曲翼枪械攻击的敌人",
    "level": "/Lotus/Levels/DevilTower/ArenaCherry.level",
    "level_short": "ArenaCherry",
    "level_name": "樱桃竞技场",
    "specs": [ { "type": "/Lotus/Types/Game/EnemySpecs/Tau/CoHCorpusExterminateMixed", "name": "Corpus" } ],
    "auras": [ { "type": "/Lotus/Types/Scripts/Tau/CoH/Complications/PoisonGasAura", "name": "化学战" } ]
  } ],
  "activation": "...", "expiry": "..."
}
```

| 字段 | 说明 |
|---|---|
| `type` / `type_name` | DT_* 任务类型枚举 / 中文翻译 |
| `challenge` / `challenge_name` | Challenge 修正标识 / 中文翻译 |
| `level` / `level_short` / `level_name` | 关卡路径 / 路径末段 / 地图中文名 |
| `specs[]` | 敌人规格路径 → 名称翻译 |
| `auras[]` | Penance 效果路径 → 名称翻译 |

**void_trader** — 虚空商人：

```json
{
  "character": "Baro'Ki Teel",
  "node": { "type": "PlutoHUB", "name": "Orcus 中继站" },
  "manifest": [ {
    "type": "/Lotus/StoreItems/Upgrades/Mods/...",
    "item_name": "压制力量",
    "prime_price": 390, "regular_price": 210000
  } ],
  "activation": "...", "expiry": "..."
}
```

**conquests** — Archimedea（透传+深度翻译）：

字段内的 `faction`（FC_*）、`missionType`（MT_*）、`difficulties[].type`（CD_*）、`difficulties[].deviation`、`difficulties[].risks[]`、`Variables[]` 均自动翻译。

**events** — 新闻（按语言筛选）：

`Messages` 数组已按 `LanguageCode == lang` 筛选，只返回当前语言的消息。`Message` 中的 loc tag 自动翻译为译文。

**meta** — 缓存元数据：

```json
{ "source": "api.warframe.com/cdn/worldState.php",
  "fetched_at": "2026-08-23T08:13:59Z", "stale": false }
```

---

## 3. GET /api/worldstate/rewards —— 全部奖励聚合

聚合 alerts/invasions/events/goals/sortie 的所有奖励：

```bash
curl "http://127.0.0.1:8099/api/worldstate/rewards?lang=zh"
```
```json
{ "rewards": [
  { "source": "alert:0", "rewards": [ { "type": "...", "item_count": 175, "item_name": "娜卡珍珠" } ] },
  { "source": "invasion:2:attacker", "rewards": [...] }
] }
```

---

## 4. POST /api/worldstate/_refresh —— 强制刷新

受最小间隔保护（`WORLDSTATE_MIN_INTERVAL`，默认 30s），过早触发返回 429。

```bash
curl -X POST "http://127.0.0.1:8099/api/worldstate/_refresh"
```

---

## 5. GET /api/arbitrations —— 仲裁（Arbitrations）

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

## 6. GET /api/cycles —— 世界循环（本地计算）

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

## 7. GET /api/nodes/{nodeId} —— 星图节点详情

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

## 8. GET /api/items/{name} —— 物品查询（支持常用简写）

查询流程：① `aliases` 表精确匹配简写 → ② `v_localized` 名称模糊匹配。

```bash
curl "http://127.0.0.1:8099/api/items/血妈?lang=zh"     # 别名命中
curl "http://127.0.0.1:8099/api/items/Garuda?lang=zh"     # 名称模糊
```
```json
{ "query": "血妈", "resolved_alias": "血妈", "results": [
  { "entity_type": "warframes",
    "entity_id": "/Lotus/Powersuits/Garuda/Garuda",
    "name": "Garuda" }
] }
```

## 9. GET /api/items/{name}/drops —— 物品掉落/来源聚合

反查 4 类来源：任务奖励表、敌人掉落表、配方（原料/产物）、组合包。

```bash
curl "http://127.0.0.1:8099/api/items/Forma/drops?lang=zh"
```
```json
{ "item": { "type": "/Lotus/Types/Items/MiscItems/Forma", "name": "Forma" },
  "drops": [
    { "source_type": "mission_reward", "source": "...", "chance": 0.025, "item_count": 3 }
  ] }
```

---

## 10. POST /api/aliases —— 别名提交（受 API Key 保护）

- 请求头 `X-API-Key`（值 = 环境变量 `ALIAS_API_KEY`）；未携带/错误 → 401；未配置 → 503
- 批量 upsert（幂等）

```bash
curl -X POST "http://127.0.0.1:8099/api/aliases" \
  -H "X-API-Key: your-key" -H "Content-Type: application/json" \
  -d '{"aliases":[{"alias":"血妈","entity_type":"warframes","entity_id":"/Lotus/Powersuits/Garuda/Garuda"}]}'
```
```json
{ "inserted": 1 }
```

---

## 11. GET /api/mods —— Mod 查询

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

## 12. GET /api/mods/{unique_name} —— Mod 详情

含兼容标签、词条（前缀/后缀/每级数值与名称翻译）。

```bash
curl "http://127.0.0.1:8099/api/mods/%2FLotus%2FUpgrades%2FMods%2FRifle%2FWeaponDamageAmountMod?lang=zh"
```

---

## 13. GET /api/weapons —— 武器列表

| 参数 | 说明 |
|---|---|
| `lang` / `category`（product_category）/ `name`（模糊） | 过滤 |
| `limit` / `offset` | 分页 |

```bash
curl "http://127.0.0.1:8099/api/weapons?category=LongGuns&limit=3&lang=zh"
```

## 14. GET /api/weapons/{name} —— 武器详情

按 unique_name 或名称精确匹配；含面板数据/伤害分量/行为伤害表/兼容标签。

```bash
curl "http://127.0.0.1:8099/api/weapons/斯特朗?lang=zh"
```
```json
{
  "unique_name": "/Lotus/Weapons/Tenno/Shotgun/Shotgun",
  "name": "斯特朗", "total_damage": 25.0,
  "critical_chance": 0.11, "fire_rate": 2.9,
  "damage_per_shot": [ { "slot": 0, "value": 6.0 } ],
  "behaviours": [ { "slot": 0, "state_name": "...",
    "damage": { "impact": { "DT_IMPACT": 6.0 } } } ],
  "compatibility_tags": ["PROJECTILE", "SHOTGUN"]
}
```

## 15. GET /api/weapons/{name}/riven —— 紫卡倾向

```bash
curl "http://127.0.0.1:8099/api/weapons/斯特朗/riven?lang=zh"
```
```json
{ "weapon": "/Lotus/Weapons/Tenno/Shotgun/Shotgun",
  "name": "斯特朗",
  "omega_attenuation": 1.4,
  "prime_omega_attenuation": null }
```

---

## 16. 配置（环境变量 / .env）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgres://warframe:warframe123@127.0.0.1:5432/warframe` | PostgreSQL 连接串 |
| `BIND_ADDR` | `0.0.0.0:8099` | 监听地址 |
| `DEFAULT_LANG` | `zh` | 缺省语言 |
| `WORLDSTATE_URL` | `https://api.warframe.com/cdn/worldState.php` | 官方 worldState 端点 |
| `WORLDSTATE_CACHE_TTL` | `180` | 缓存秒数（3 分钟） |
| `WORLDSTATE_MIN_INTERVAL` | `30` | 强制刷新最小间隔（秒） |
| `ALIAS_API_KEY` | 无 | 别名提交鉴权密钥 |

---

## 17. 快速上手

```bash
# 启动
CARGO_TARGET_DIR=temp/target cargo build && \
ALIAS_API_KEY=testkey123 BIND_ADDR=127.0.0.1:8099 ./temp/target/debug/warframe-api

# 常用调用
curl localhost:8099/health
curl "localhost:8099/api/worldstate?sections=alerts,fissures,cycles&lang=zh"
curl "localhost:8099/api/arbitrations?lang=zh&limit=5"
curl "localhost:8099/api/cycles"
curl "localhost:8099/api/nodes/SolNode94?lang=zh"
curl "localhost:8099/api/items/血妈?lang=zh"
curl "localhost:8099/api/weapons/斯特朗/riven?lang=zh"
curl "localhost:8099/api/mods?type=PRIMARY&limit=10&lang=zh"
```

---

*Wiki 数据来源：[wiki.warframe.com/w/World_State](https://wiki.warframe.com/w/World_State) | [doroprime descent_type.dart](https://github.com/Yawanaika/doroprime) | 设计见 `doc/design.md`。*
