# GET /api/worldstate —— 官方 WorldState（解析+翻译）

> 分组：世界状态　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

整个《星际战甲》在线世界的实时状态快照，等价于游戏内星图界面左下角的"世界状态窗口"。包含：**警报**（限时小任务）、**虚空裂缝**（带遗物开箱的 fissure 任务）、**入侵**（Grineer/Corpus 争夺节点）、**突击**（每日 3 段高难度任务）、**午夜电波**（赛季挑战）、**虚空商人 Baro**（双周出现的限定商人）、**Descendia 沉沦之地**（暗折射每周爬塔）等。数据来自 DE 官方 `worldState.php`，本服务解析并翻译为中文。

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
