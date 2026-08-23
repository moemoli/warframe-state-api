# Warframe API 项目设计文档

> 版本: v0.1（待审核）　项目: Rust (Axum) + PostgreSQL，数据库即 `init.sql` 所建 warframe 库
> 本文档描述：官方 WorldState 拉取/缓存/解析与翻译、世界循环、物品（含简写）查询、
> Mod / 武器 / 紫卡倾向 / 掉落查询。**审核通过后按本文档实现。**

---

## 1. 项目目标

对外提供一组 REST API，能力清单：

| # | 能力 | 说明 |
|---|---|---|
| 1 | WorldState 解析 | 拉取官方 worldState.php，把其中 `/Lotus/...` 路径、`MT_*`/`FC_*` 任务/派系枚举、`SolNode*` 星图节点统一解析为**指定语言译文**（默认 zh） |
| 2 | Rewards 展开 | worldstate 与奖励相关的节（警报/入侵/活动/突击等）把奖励引用展开为 **JSON array**，每个条目含 `type`(物品路径) + `item_count` + 翻译后的 `item_name` |
| 3 | 节点查询 | 节点以 `type`(如 `SolNode94`) + `name`(译文) 输出；支持按 type 查询节点详情（任务类型、派系、敌人等级、奖励表等） |
| 4 | 世界循环 | 提供各开放世界/循环状态与起止时间（Cetus/Vallis/Cambion/Earth/Zariman/Duviri/Midrath） |
| 5 | WorldState 缓存 | 官方接口做进程内 TTL 缓存 + 并发去重 + 失败回退，避免频繁请求触发风控 |
| 6 | 物品查询（简写） | 按名称/中文简写查物品，如 `血妈` → Garuda；支持模糊匹配 |
| 7 | Mod 查询 | Mod 列表/详情（类型、极性、稀有度、属性词条） |
| 8 | 武器详细 | 武器全字段 + 伤害分量 + 行为伤害表 |
| 9 | 紫卡倾向 | 武器 Riven 倾向（omega_attenuation / prime_omega_attenuation） |
| 10 | 物品掉落 | 反查某物品的全部掉落来源（任务奖励表、敌人掉落表、合成配方等） |

---

## 2. 数据来源与依赖

### 2.1 官方 WorldState

- 主端点：`https://api.warframe.com/cdn/worldState.php`（gzip 压缩 JSON；`content.warframe.com` 旧地址已 404，代码中可配置 `WORLDSTATE_URL`）
- 响应节（2026 版本实测）：`Events, Goals, Alerts, Sorties, LiteSorties, SyndicateMissions, ActiveMissions, GlobalUpgrades, FlashSales, Invasions, VoidTraders, VoidStorms, DailyDeals, PersistentEnemies, Descents, WeeklyVaultBonusRewards, News(...)` 等
- 关键键形态（实测）：
  - 节点：`Node: "SolNode94"`、`"PlutoHUB"`、`"CrewBattleNode512"`
  - 任务/派系：`missionType: "MT_TERRITORY"`、`faction: "FC_CORPUS"`（**枚举短码，非 loc tag**）
  - 描述：`descText/LocTag/Desc/ToolTip/ScoreLocTag` 为 loc tag（`/Lotus/Language/...`）
  - 奖励：`missionReward{items[], countedItems[{ItemType,ItemCount}], credits}`、`AttackerReward/DefenderReward`、`Reward.items[]`；物品路径带 `/Lotus/StoreItems/` 前缀
  - 突击：`Sorties[].Boss("SORTIE_BOSS_RUK")`、`Variants[{missionType, modifierType, node}]`、`Reward`(奖励 deck 路径)
  - 集团任务：`SyndicateMissions[].Tag("EntratiSyndicate")`、`Jobs[{jobType, rewards(deck), ...}]`
  - 虚空风暴：`VoidStorms[].Node, ActiveMissionTier("VoidT1")`
  - 特惠/商人：`DailyDeals[].StoreItem`、`VoidTraders[].Manifest[{ItemType, PrimePrice, RegularPrice}]`

### 2.2 周期（世界循环）数据源 —— 本地计算

实测 2026 版 worldState.php **不含** `CetusCycle/EarthCycle/...` 节，因此**周期全部由本地按游戏时间公式计算**，不依赖外部端点（避免额外请求与风控）。

**计算模型**：每个循环 = 状态分段时长 + 锚点时间，按当前 UTC 时间推算当前状态与起止时刻。时长与锚点以 **Fandom Wiki 与 WFCD/warframe-worldstate-parser 实现双重核对**（下表"来源"列）：

| 循环 | 状态（时长） | 周期总长 | 锚点/说明 | 来源 |
|---|---|---|---|---|
| `cetus`（夜灵平原） | day 100min / night 50min | 150min | 与 `cambion` 同步 | [wiki](https://warframe.fandom.com/wiki/Plains_of_Eidolon)（"Daytime...100 minutes, nighttime...50"）+ parser `CetusCycle` |
| `earth`（地球昼夜） | day 4h / night 4h | 8h | 独立于 cetus（地球星图昼夜） | parser `EarthCycle`（`%28800s`，`<14400s` 为白天） |
| `vallis`（金星奥布山谷） | warm 6m40s / cold 20min | 26m40s | 锚点 `2026-02-04T19:46:48Z`（可配置） | [wiki](https://warframe.fandom.com/wiki/Orb_Vallis)（"6 minutes and 40 seconds of warm... 20 minutes of cold"）+ parser `VallisCycle` |
| `cambion`（火卫二） | fass 100min / vome 50min | 150min | **与 cetus 同步**：cetus 白天=fass，夜晚=vome | [wiki](https://warframe.fandom.com/wiki/Cambion_Drift)（"same cycle lengths as Plains"）+ parser `CambionCycle` |
| `zariman`（扎里曼） | corpus 150min / grineer 150min | 5h | 阵营轮换（非昼夜）；锚点 `2022-06-14` 可配置 | parser `ZarimanCycle`（`fullCycle=18e6ms`） |
| `duviri`（双衍王境） | 心绪各 120min：sorrow→fear→joy→anger→envy 轮换 | 10h | [wiki](https://warframe.fandom.com/wiki/Duviri)（"Each mood lasts for 120 minutes"）+ parser `DuviriCycle`（`stateTime=7200s`） |
| `midrath`（2025 新区域） | day 32min / night 16min | 48min | 锚点 `2025-08-07T16:05:29Z`（可配置） | parser `MidrathCycle`（`day=1920s/night=960s`） |

- 分段时长/锚点为**常量表**（`cycles.rs` 内配置，以上数值为 wiki/parser 权威值，按游戏更新可调）
- 循环中文名称：`cetus=夜灵平原 earth=地球 vallis=奥布山谷 cambion=火卫二 zariman=扎里曼 duviri=双衍王境 midrath=Midrath`
- 状态中文映射常量表（可配置）：`day=白天 night=夜晚 warm=温暖 cold=寒冷 fass=Fass vome=Vome`（**fass/vome 不翻译**，保持原文）`corpus=Corpus grineer=Grineer`（保留原文）`sorrow=悲伤 fear=恐惧 joy=喜悦 anger=愤怒 envy=嫉妒`
- 输出统一结构见 §5.3（含 ISO 起止时间，见"时间输出规范"）
- 配置项 `CYCLE_PROVIDER=local`（当前唯一实现，未来如需外部源可扩展）

### 2.3 数据库（已建，`init.sql`）

| 用途 | 表/视图 | 说明 |
|---|---|---|
| 译文 | `localizations(loc_tag, lang, value)`、`loc(tag,lang)` | 唯一译文源；当前只装 zh |
| 全库检索 | `v_localized(entity_type, entity_id, field, lang, value)` | 38+ 类实体所有本地化字段 |
| 节点 | `regions(unique_name=SolNode94, name_loc, mission_name_loc, faction_name_loc, min/max_enemy_level, reward_manifests...)` | 星图节点（354 条，含 HUB/航道星舰节点） |
| 枚举映射 | `worldstate_enums(category, enum_code, name_loc)` | `MT_*`/`FC_*` → loc tag（ExportFactions/MissionTypes） |
| 奖励表 | `mission_reward_decks → mission_reward_tiers → mission_reward_items` | rewards 展开来源 |
| 实体 | `warframes/weapons/upgrades/relics/resources/arcanes/...` | 物品翻译与详情 |
| 敌人掉落 | `enemy_droptables → enemy_droptable_pools → enemy_droptable_items` | 掉落查询 |
| 配方 | `recipes/recipe_ingredients` | 掉落/来源查询 |

---

## 3. WorldState 解析与翻译规则（核心）

解析分两层：**原文结构保留**（PascalCase 键原样解析成 Rust 结构）→ **翻译增强**（每个引用字段追加 `*_translated` 或统一走解析器）。

### 3.1 翻译解析器（`resolve` 模块，输入任意字符串 → 译文/详情）

统一函数 `Resolver::resolve(value: &str, lang: &str) -> Resolved`，按以下优先级：

| 值形态 | 判定 | 处理 | 数据库 |
|---|---|---|---|
| loc tag | 以 `/Lotus/Language/` 或 `/EE/Language/` 开头 | 直接查译文 | `localizations` |
| 任务类型枚举 | `MT_*` | 查枚举映射 → loc tag → 译文 | `worldstate_enums(category='mission_type')` + `localizations` |
| 派系枚举 | `FC_*` | 同上（category='faction'） | 同上 |
| 节点 ID | `SolNode\d+` / `CrewBattleNode\d+` / `\w+HUB` | 查节点 → 返回 `{type, name}` | `regions` |
| 物品路径 | `/Lotus/...` | 去 `/Lotus/StoreItems` 前缀 → 逐实体表探测 → 取 `name_loc` 译文 | 实体表 + `localizations` |
| 突击 Boss | `SORTIE_BOSS_*` | 后缀词匹配 `enemy_avatars`（如 RUK → "Sargas Ruk 将军"） | `enemy_avatars` |
| 突击修饰 | `SORTIE_MODIFIER_*` | 内置英文表（worldstate-data sortieData） | 常量表 |
| 遗物等级 | `VoidT1..5` | 映射遗物 era（Lith/Meso/Neo/Axi/Requiem） | 常量映射 + `relics.era` |
| 其他 | — | 原样返回 | — |

> 翻译失败（如 zh 字典未收录新 tag）时：返回原值 + `"translated": false` 标记，不报错。

### 3.2 奖励（Rewards）展开规则（含"展开深度"详解）

#### 3.2.1 worldstate 奖励的两种形态

worldstate 里的奖励字段存在两种完全不同的形态，理解这一点是"展开深度"的关键：

**形态 A：直接奖励列表（本身就是具体物品）**
警报、入侵、事件等节直接携带物品列表：

```jsonc
// Alerts[].MissionInfo.missionReward
{ "credits": 50000,
  "countedItems": [ { "ItemType": "/Lotus/Types/Items/MiscItems/WaterFightBucks",
                      "ItemCount": 175 } ] }

// Events[].Reward
{ "items": ["/Lotus/StoreItems/Weapons/Corpus/LongGuns/..."], "credits": 0 }
```

**形态 B：奖励表引用（只是一个 deck 路径，指向数据库里的奖励表）**
突击（Sortie）、集团任务（SyndicateMissions.Jobs）、以及 `regions.reward_manifests` 只有**一个 deck 路径**：

```jsonc
// Sorties[].Reward
"/Lotus/Types/Game/MissionDecks/SortieRewards"
// SyndicateMissions[].Jobs[].rewards
"/Lotus/Types/Game/MissionDecks/DeimosMissionRewards/TierATableCRewards"
```

这个 deck 在数据库里是 `mission_reward_decks → mission_reward_tiers → mission_reward_items`，
即**多轮（tier）× 每轮若干条目（item）** 的二维结构。

#### 3.2.2 "展开深度"的定义

深度只对**形态 B** 有意义（形态 A 本身就是列表，永远直接展开）：

| 深度 | 行为 | 响应示例（Sortie 奖励） |
|---|---|---|
| **depth=0（仅引用）** | 只返回 deck 路径 + deck 名称（翻译），**不查具体条目** | `{ "deck": "/Lotus/Types/Game/MissionDecks/SortieRewards", "deck_name": "突击奖励" }` |
| **depth=1（展开，默认）** | 查数据库把 deck 展开为**完整的奖励条目数组**（保留 tier 分组） | 见下方示例 |

**深度 1 展开后的响应结构**（每个 tier 一轮，条目含概率/稀有度 + 翻译后的物品名）：

```jsonc
{ "deck": "/Lotus/Types/Game/MissionDecks/SortieRewards",
  "deck_name": "突击奖励",
  "tiers": [
    { "tier": 0,
      "items": [
        { "type": "/Lotus/StoreItems/Upgrades/Mods/Randomized/RawRifleRandomMod",
          "item_count": 1, "probability": 0.0679, "rarity": null,
          "item_name": "随机步枪 Mod" },     // 物品路径 → 去 StoreItems 前缀 → 实体表 → 译文
        { "type": "/Lotus/StoreItems/Types/Items/FusionTreasures/OroFusexF",
          "item_count": 1, "probability": 0.28, "rarity": null,
          "item_name": "遗物银" },
        { "type": "/Lotus/StoreItems/Types/Items/MiscItems/Forma",
          "item_count": 3, "probability": 0.025, "rarity": null,
          "item_name": "Forma" }
      ] },
    { "tier": 1, "items": [ /* ... */ ] }
  ] }
```

- 悬赏类 deck（如 Deimos TierA/B/C）tier 对应轮次奖励（第 1/2/3 轮），概率与轮次相关
- 遗物类 deck 的条目用 `rarity`（COMMON/UNCOMMON/RARE）代替 `probability`，两者都输出、按实际字段填空
- 条目数量可能很大（一个 deck 几十到上百条），这是"展开"的代价；不需要时可请求 depth=0

#### 3.2.3 深度控制参数

所有含形态 B 奖励的端点（worldstate 各节、nodes 详情）支持：

| 参数 | 值 | 默认 | 说明 |
|---|---|---|---|
| `expand` | `1`（展开）/ `0`（仅引用） | `1` | 形态 B 的展开深度；形态 A 不受影响，始终展开 |

对应关系：`expand=1` = depth 1，`expand=0` = depth 0。

#### 3.2.4 统一输出约定（形态 A 与形态 B 一致的元素结构）

最终 JSON array 的**每个元素**统一为：

```jsonc
{ "type": "<物品路径 | credits | xp | 特殊键>",
  "item_count": <数量>,
  "item_name": "<翻译后的名称>",          // credits→"星币"、xp→"经验"（内置常量）；物品路径→§3.1 解析
  "probability": <0~1 | null>,           // 仅奖励表条目有
  "rarity": "COMMON|UNCOMMON|RARE|...|null" } // 遗物类条目有
```

翻译失败（zh 字典未收录）时 `item_name` 回退为路径末段（如 `Forma`），并附 `"translated": false`。

### 3.3 节点（Node）输出结构

worldstate 每个含节点的节，节点统一输出为：

```json
{ "type": "SolNode94", "name": "Apollodorus" }
```

- `type` = 原始节点 ID（`SolNode94`），**直接可用于查询**
- `name` = `regions.name_loc` 译文
- 若节点不在 `regions`（极少，如未知 HUB）：`name` 回退为 `type`，`"translated": false`

**按 type 查节点详情**：`GET /api/nodes/{type}` 返回 §5.4 的完整节点对象。

---

## 4. WorldState 缓存（防风控）

### 4.1 策略

- **进程内 TTL 缓存**（`tokio::sync::RwLock` + `Instant`，或 `dashmap`），TTL 由环境变量 `WORLDSTATE_CACHE_TTL` 控制，**默认 180 秒（3 分钟）**
- **行为语义（标准 TTL）**：
  1. 请求到来时若**无缓存**（进程启动后首次）→ 从官方源拉取并缓存，记录拉取时间
  2. 若距上次拉取**未超过 TTL** → 直接返回缓存（不访问官方）
  3. 若距上次拉取**已超过 TTL** → 重新从官方源拉取并刷新缓存
- **并发去重（singleflight）**：同一时刻多个请求同时触发"重新拉取"时，只发起一次上游请求，其余等待同一结果（`tokio::sync::OnceCell`/`oneshot` 队列），避免瞬时并发打爆上游
- **stale-while-error**：重新拉取失败时返回上次成功缓存（标记 `stale: true`），避免风控/抖动导致 API 不可用；仅当**完全没有缓存**且拉取失败时返回 502
- **User-Agent 与限速**：固定 UA；`WORLDSTATE_MIN_INTERVAL`（默认 30s）兜底防止两次拉取间隔过近（通常被 TTL 覆盖）
- 可选：`Accept-Encoding: gzip`，解码 gzip

### 4.2 状态

```rust
struct WorldStateCache {
    data: RwLock<Option<(Instant, Arc<WorldState>)>>,  // (拉取时间, 解析结果)
    inflight: Mutex<Option<oneshot::Sender<Result<Arc<WorldState>>>>>,
    cfg: CacheConfig,  // ttl, min_interval
}
```

### 4.3 端点行为

- `GET /api/worldstate` 永远返回缓存/最新数据，并在响应头附带 `X-WorldState-Age`（秒）、`X-WorldState-Stale`（0/1）
- 提供 `GET /api/worldstate/_refresh`（POST）强制刷新（仍受最小间隔保护），便于运维

---

## 5. API 端点设计

> 通用约定：`lang` 参数缺省 `DEFAULT_LANG`(zh)；所有 `name`/`unique_name` 路径参数 URL 编码；
> 错误统一 `{ "error": "..." }`（400/404/500）；分页 `limit/offset`（默认 20/0，上限 100）。

**时间输出规范（全局强制）**：
- 所有时间字段（`activation`/`expiry`/`fetched_at`/周期起止/`Time` 等）统一输出为 **UTC ISO 8601** 格式：`YYYY-MM-DDTHH:MM:SSZ`（精确到秒）；若源数据含毫秒则输出 `YYYY-MM-DDTHH:MM:SS.sssZ`
- 原始 worldstate 时间为 epoch 毫秒（`$date.$numberLong`）或 epoch 秒（`Time` 字段），解析层统一转为 UTC 后格式化输出，**不输出 epoch/本地时间/带时区偏移的 `+08:00` 形式**
- 时间差字段（如 `remaining`）输出 `remaining_seconds`(整数秒) + 人类可读字符串 `"1h 20m"`，**不单独输出时间戳**
- 所有 ISO 时间通过 `chrono::Utc` 生成，字符串统一大写 `Z` 后缀

### 5.1 GET /api/worldstate?lang=zh&sections=
解析后的完整 worldstate。

- **默认返回全部节**：`alerts, events, fissures, invasions, sortie, void_trader, daily_deals, syndicate_missions, nightwave, kuva, arbitration, persistent_enemies, descents, news, goals, cycles, meta`（含 flash_sales/global_upgrades 等未在列表的节原样透传）
- **分类筛选**：`?sections=alerts,fissures` 只返回指定节（逗号分隔，大小写不敏感；`cycles`/`meta` 始终附带，便于时间对齐）；`?sections=` 空值等同全部
- 每节内所有引用字段按 §3 翻译/展开；rewards 按 §3.2（`expand` 参数控制深度）

响应（节选）：

```json
{
  "time": "2026-08-22T16:06:12Z",
  "alerts": [{
    "id": "6a8716700000000000000000",
    "activation": "2026-08-22T15:00:00Z",
    "expiry": "2026-08-23T15:00:00Z",
    "mission": {
      "node": { "type": "SolNode25", "name": "Vesper 中继站" },
      "mission_type": { "code": "MT_TERRITORY", "name": "领土" },
      "faction":     { "code": "FC_CORPUS", "name": "Corpus" },
      "enemy_levels": { "min": 1, "max": 2 },
      "reward": [ { "type": "/Lotus/Types/Items/MiscItems/WaterFightBucks",
                    "item_count": 175, "item_name": "水上格斗币" } ],
      "description": "三伏天活动任务描述译文"
    },
    "tag": "WaterFight"
  }],
  "fissures": [...], "invasions": [...], "sortie": {...}, "void_trader": {...},
  "daily_deals": [...], "syndicate_missions": [...], "nightwave": {...},
  "events": [...], "descents": [...], "persistent_enemies": [...],
  "cycles": [ { "name": "cetus", "state": "night", "remaining": "1h 20m",
                "activation": "2026-08-22T10:00:00Z",
                "expiry": "2026-08-22T14:00:00Z" } ],
  "meta": { "source": "api.warframe.com/cdn/worldState.php",
            "fetched_at": "2026-08-22T16:06:12Z", "stale": false }
}
```

- 每节对应一个解析函数（`parse_alerts/parse_fissures/...`），全部复用 §3 的 Resolver
- rewards 字段全部按 §3.2 展开

### 5.2 GET /api/worldstate/rewards
只返回全部奖励聚合（警报+入侵双方+事件+突击奖励表展开），便于客户端直接消费：
`[{ "source": "alert:6a87...", "rewards": [ ... ] }, ...]`

### 5.3 GET /api/cycles
世界循环列表（来自 CycleProvider，见 §2.2）：

```json
{ "cycles": [
  { "name": "cetus",     "state": "night", "state_name": "夜晚",
    "activation": "2026-08-22T10:00:00Z", "expiry": "2026-08-22T14:00:00Z",
    "remaining_seconds": 4800, "remaining": "1h 20m" },
  { "name": "vallis",    "state": "warm", "state_name": "温暖",
    "activation": "2026-08-22T11:30:00Z", "expiry": "2026-08-22T13:30:00Z",
    "remaining_seconds": 3600, "remaining": "1h 0m" },
  { "name": "cambion",   "state": "fass", "state_name": "Fass",
    "activation": "2026-08-22T10:00:00Z", "expiry": "2026-08-22T11:40:00Z",
    "remaining_seconds": 6000, "remaining": "1h 40m" },
  { "name": "earth",     "state": "day",  ... },
  { "name": "zariman",   ... }, { "name": "duviri", ... }, { "name": "midrath", ... }
]}
```
支持 `?name=cetus` 单查；state 的中文映射为内置常量表（day=白天/night=夜晚/warm=温暖/cold=寒冷/fass=Fass/vome=Vome/corpus=Corpus/grineer=Grineer/心绪五态见 §2.2）。

### 5.4 GET /api/nodes/{type}?lang=zh&expand=
按节点 type 查询详情。**`type` 直接传节点 tag（`SolNode94` 这类完整 ID）精确查询**（不做裸数字/前缀匹配）：

```json
{
  "type": "SolNode94", "name": "Apollodorus",
  "system": { "index": 0, "name": "水星" },
  "mission_type": { "code": "MT_SURVIVAL", "name": "生存" },
  "faction": { "code": "FC_INFESTATION", "name": "Infestation" },
  "enemy_levels": { "min": 6, "max": 11 },
  "mastery_req": 0, "node_type": 0,
  "reward_manifests": [ "/Lotus/Types/Game/MissionDecks/SurvivalMissionRewards/SurvivalLowLevelRewards" ],
  "rewards": [ /* 展开的奖励 JSON array，§3.2；?expand=0 时只返回 deck 引用 */ ]
}
```

SQL 骨架：

```sql
SELECT unique_name, loc(name_loc, $2), loc(system_name_loc, $2),
       loc(mission_name_loc, $2), loc(faction_name_loc, $2),
       min_enemy_level, max_enemy_level, mastery_req, node_type
FROM regions WHERE unique_name = $1;
-- 奖励: JOIN mission_reward_decks/tiers/items 按 reward_manifests 展开（§3.2，expand 参数控制深度）
```

### 5.5 GET /api/items/{name}?lang=zh
物品查询，**支持常用简写**：

- 步骤 1 精确：`aliases` 表查简写（`血妈` → warframes.Garuda）
- 步骤 2 名称匹配：`v_localized` 按 `entity_id` 精确 / `value` ILIKE 模糊（如 `garuda`、`赤毒`）
- 返回候选列表（可能多条，客户端自选）：

```json
{ "query": "血妈", "resolved_alias": "Garuda", "results": [
  { "entity_type": "warframes",
    "entity_id": "/Lotus/Powersuits/Garuda/Garuda",
    "name": "Garuda", "description": "血之女神，以鲜血为食……" }
]}
```

#### 别名管理端点（POST /api/aliases，受 API Key 保护）

别名清单由你后续提供，服务端提供**提交接口**（也可直接 SQL 导入 `aliases` 表）：

```http
POST /api/aliases
X-API-Key: <环境变量 ALIAS_API_KEY 配置的密钥>
Content-Type: application/json

{ "aliases": [
    { "alias": "血妈", "entity_type": "warframes",
      "entity_id": "/Lotus/Powersuits/Garuda/Garuda" }
] }
```

- **未携带 `X-API-Key` 或与 `ALIAS_API_KEY` 不一致 → 拒绝（401）**
- 携带正确 key → 批量 upsert（`ON CONFLICT (alias, entity_type, entity_id) DO UPDATE`），返回 `{ "inserted": n }`
- 同一 alias 可对应多个实体（多义简写）；`entity_type` 取值与 §5.5 一致（warframes/weapons/...）

### 5.6 GET /api/mods?lang=zh&type=&name=&polarity=&rarity=
Mod 查询（`upgrades` 表）：

| 参数 | 说明 |
|---|---|
| `type` | STANCE/WARFRAME/PRIMARY/SECONDARY/MELEE/AURA/ARCH-GUN/...（`upgrades.type`） |
| `name` | 名称模糊（`loc(name_loc,lang) ILIKE`） |
| `polarity` / `rarity` | 极性/稀有度过滤 |
| `limit/offset` | 分页 |

响应每项：`unique_name, name(译文), type, polarity, rarity, base_drain, fusion_limit, compatibility_tags[]`；
支持 `GET /api/mods/{unique_name}?lang=` 详情（+`upgrade_entries/upgrade_entry_values` 词条、`available_challenges`）。

### 5.7 GET /api/weapons/{name}?lang=zh
武器详情（`weapons` 表全字段）：

- 基础：name(译文)/description(译文)/product_category/holster_category/mastery_req/slot/trigger/noise
- 面板：critical_chance/critical_multiplier/proc_chance/fire_rate/multishot/magazine_size/reload_time/accuracy
- 伤害：`damage_per_shot` 分量 + `weapon_behaviour_damage`（按 path 分组：impact/projectile.attack/...）
- 近战：range/slam_*/heavy_*/combo_duration/follow_through/blocking_angle
- 兼容标签：`weapon_compatibility_tags`

也支持 `?name=` 模糊 + `?category=`（Pistols/Melee/LongGuns/...）列表模式。

### 5.8 GET /api/weapons/{name}/riven?lang=zh
紫卡倾向：

```json
{ "weapon": "...", "name": "斯特朗",
  "omega_attenuation": 1.15,            // Riven 倾向
  "prime_omega_attenuation": null,      // Prime 版倾向（若有）
  "disposition_rank": "中等" }          // 可选：倾向档位常量映射
```
来自 `weapons.omega_attenuation / prime_omega_attenuation`。

### 5.9 GET /api/items/{name}/drops?lang=zh
物品掉落/来源聚合（反查）：

```json
{ "item": { "type": "/Lotus/Types/Items/MiscItems/Kuva", "name": "赤毒" },
  "drops": [
    { "source_type": "mission_reward", "source": "TierABountyRewards",
      "source_name": "甲级悬赏奖励", "chance": 0.1951, "rarity": null, "item_count": 20 },
    { "source_type": "enemy_droptable", "source": "/Lotus/Types/DropTables/...",
      "chance": 0.1667, ... },
    { "source_type": "recipe", "source": "...Blueprint", "as_ingredient": true, "item_count": 5 }
  ]}
```

反查 SQL：
- `mission_reward_items.type`（StoreItems 前缀变体，`regexp_replace` 归一后匹配）
- `enemy_droptable_items.type`
- `recipe_ingredients.item_type`（该物品作为配方原料）、`recipes.result_type`（该物品作为产物）
- `bundle_components.type_name`（组合包内含）
- 各来源 `source`/`source_name` 翻译（deck/enemy 名称尽力翻译，失败回退原文）

---

## 6. 代码结构（Rust）

```
src/
├── main.rs            # 入口：配置→连接池→缓存→路由→axum::serve
├── config.rs          # 环境变量（见 §8）
├── state.rs           # AppState { pool, cache, aliases, cfg }
├── db.rs              # 连接池
├── error.rs           # ApiError → {error}
├── aliases.rs         # 别名加载（DB）+ 匹配
├── worldstate/
│   ├── mod.rs         # 拉取+缓存+解析入口（fetch_or_cache）
│   ├── fetch.rs       # reqwest 拉取（gzip、UA、TTL、singleflight、stale 回退）
│   ├── types.rs       # worldstate 原始结构（serde）
│   ├── resolve.rs     # Resolver：§3.1 翻译/展开（sqlx 查询，批量缓存 tag→译文）
│   └── parse.rs       # 各节解析（alerts/fissures/.../rewards 展开/cycles）
├── routes/
│   ├── mod.rs
│   ├── worldstate.rs  # 5.1/5.2
│   ├── cycles.rs      # 5.3
│   ├── nodes.rs       # 5.4
│   ├── items.rs       # 5.5 / 5.9
│   ├── mods.rs        # 5.6
│   └── weapons.rs     # 5.7 / 5.8
└── models.rs          # 响应结构
```

依赖新增：`reqwest`(json/gzip)、`tokio`(sync)、`dashmap`(可选)、`chrono`(时间)、`tower-http`(压缩/缓存头)。

---

## 7. 数据库变更（在 `init.sql` 追加，随文档审核）

```sql
-- 物品别名（常用简写 → 实体；POST /api/aliases 或 SQL 导入维护）
CREATE TABLE public.aliases (
    alias          text NOT NULL,          -- 如 '血妈'
    entity_type    text NOT NULL,          -- warframes/weapons/...
    entity_id      text NOT NULL,          -- unique_name（去 StoreItems 前缀）
    PRIMARY KEY (alias, entity_type, entity_id)
);
CREATE INDEX idx_aliases_alias ON public.aliases (alias);
```

种子数据由你后续提供清单，通过 `POST /api/aliases`（携带 `X-API-Key`）或直接 SQL 导入；初始不内置。

---

## 8. 配置（环境变量 / .env）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgres://warframe:warframe123@127.0.0.1:5432/warframe` | 连接串 |
| `BIND_ADDR` | `0.0.0.0:8080` | 监听地址 |
| `DEFAULT_LANG` | `zh` | 缺省语言 |
| `WORLDSTATE_URL` | `https://api.warframe.com/cdn/worldState.php` | 官方端点 |
| `WORLDSTATE_CACHE_TTL` | `180` | 缓存秒数（默认 3 分钟；超时重新拉取） |
| `WORLDSTATE_MIN_INTERVAL` | `30` | 两次上游请求最小间隔（秒） |
| `CYCLE_PROVIDER` | `local` | 周期计算方式（当前仅本地公式实现） |
| `ALIAS_API_KEY` | （无默认） | `POST /api/aliases` 的鉴权密钥；**未配置则别名提交接口直接拒绝（503）** |

---

## 9. 错误处理与日志

- `ApiError`: BadRequest(400) / NotFound(404) / WorldState(502, 上游失败且无缓存) / Database(500)
- worldstate 拉取失败且无缓存：502 + `{error, stale:false}`；有缓存：200 + stale 标记
- tracing 日志：请求 trace（tower-http TraceLayer）、上游拉取/缓存命中/刷新事件、翻译失败告警（WARN）

---

## 10. 非目标（本期不做）

- 不建 worldstate 历史存储（只做当前态缓存）
- 不做用户系统/鉴权
- 上游新增的 11 个导出文件（Animals/Bounties/Challenges/Codex/...）对应新表不在本期（仅当 drops/items 需要时评估）
- OpenAPI 文档生成（utoipa）列为二期

---

## 11. 待确认（审核点）

1. ~~周期数据源/数值~~ → 已定：**本地公式计算**，时长与锚点已按 [Fandom Wiki](https://warframe.fandom.com/wiki/Plains_of_Eidolon) 与 [warframe-worldstate-parser](https://github.com/WFCD/warframe-worldstate-parser) 实现核对（§2.2 表格）
2. **别名清单**：由你后续提供；补充方式已定——`POST /api/aliases` 携带 `X-API-Key`（环境变量 `ALIAS_API_KEY`，未携带/错误 401，未配置 503），或直接 SQL 导入（§5.5/§7）
3. **rewards 展开深度**：已确认——**默认完全展开**（depth=1，tier 分组条目数组），`?expand=0` 只返回 deck 引用（§3.2）
4. **worldstate 返回节范围**：已定——**全部节** + `?sections=` 分类筛选（§5.1）
5. **/api/nodes 查询**：已定——`type` 直接传 `SolNodexxx` 完整 tag 精确查询（§5.4）
6. **缓存粒度**：已定——`WORLDSTATE_CACHE_TTL` 默认 **180s（3 分钟）**（§4.1）
7. 周期中文命名：已定——**fass/vome 不翻译**（保持原文 Fass/Vome），**zariman 游戏内称"扎里曼"**，corpus/grineer 保留原文（§2.2）

> 设计要点已全部确认，可进入实现阶段。
