# Warframe API 实现文档（模块级）

> 依据 `doc/design.md` 细化到模块/函数/数据结构/SQL 级别，实现时按此文档逐模块落地。
> 全局约定：时间一律 UTC ISO 8601（`YYYY-MM-DDTHH:MM:SSZ`，毫秒级 `.sssZ`）；错误统一 `{ "error" }`。

---

## 0. 模块总览与依赖图

```
main.rs ── config.rs ── state.rs(AppState)
   │            └────── db.rs(PgPool)
   ├── routes/
   │   ├── worldstate.rs ── worldstate/{mod,fetch,types,resolve,parse}.rs
   │   ├── cycles.rs ────── worldstate/parse.rs(cycle 计算) + cycles 常量
   │   ├── nodes.rs ─────── db.rs + resolve.rs
   │   ├── items.rs ─────── aliases.rs + resolve.rs + db.rs
   │   ├── mods.rs ──────── db.rs + resolve.rs
   │   └── weapons.rs ───── db.rs + resolve.rs
   └── error.rs / models.rs / aliases.rs（被 routes 共用）
```

数据流（worldstate 请求）：
`HTTP → routes/worldstate.rs → worldstate::mod::get_cached() → (缓存未命中) fetch.rs 拉官方 → types.rs 反序列化 → parse.rs 各节解析（内部调用 resolve.rs 翻译/展开）→ models 输出`

---

## 1. config.rs —— 配置

```rust
#[derive(Debug, Clone)]
pub struct Config {
    pub database_url: String,      // DATABASE_URL    默认 postgres://warframe:warframe123@127.0.0.1:5432/warframe
    pub bind_addr: String,         // BIND_ADDR       默认 0.0.0.0:8080
    pub default_lang: String,      // DEFAULT_LANG    默认 zh
    pub worldstate_url: String,    // WORLDSTATE_URL  默认 https://api.warframe.com/cdn/worldState.php
    pub ws_cache_ttl: u64,         // WORLDSTATE_CACHE_TTL    默认 180（秒）
    pub ws_min_interval: u64,      // WORLDSTATE_MIN_INTERVAL 默认 30（秒）
    pub cycle_provider: String,    // CYCLE_PROVIDER  默认 local
    pub alias_api_key: Option<String>, // ALIAS_API_KEY 无默认（未配置则别名 POST 拒绝 503）
}
impl Config { pub fn from_env() -> Self { /* dotenvy + env::var + 默认值 */ } }
```

实现要点：`dotenvy::dotenv()` 忽略缺失；所有读取用 `env::var(...).unwrap_or(default)`。

---

## 2. state.rs / db.rs —— 共享状态与数据库

```rust
#[derive(Clone)]
pub struct AppState {
    pub pool: PgPool,
    pub config: Config,
    pub ws: Arc<WorldStateCache>,   // 见 §6
}
// db.rs
pub async fn create_pool(url: &str) -> Result<PgPool, sqlx::Error> { /* max 10, timeout 5s */ }
pub async fn ping(pool: &PgPool) -> Result<(), sqlx::Error> { /* SELECT 1 */ }
```

约定：所有 SQL 参数化绑定（`$n`）；`lang` 一律作为参数传给 `loc(tag, $lang)`。

---

## 3. error.rs —— 统一错误

```rust
pub enum ApiError {
    BadRequest(String),          // 400
    NotFound(String),            // 404
    Unauthorized(String),        // 401（别名 API key）
    ServiceUnavailable(String),  // 503（别名接口未配置 key；worldstate 无缓存且上游失败）
    WorldState(String),          // 502（上游失败且无缓存）
    Database(sqlx::Error),       // 500
}
impl IntoResponse for ApiError { /* Json({ "error": msg }) + tracing::error! */ }
```

---

## 4. models.rs —— 共享响应结构（serde::Serialize）

```rust
// 通用"引用解析"结果（Resolver 输出，见 §9）
#[derive(Serialize)]
pub struct Resolved {
    pub code: String,            // 原始值（loc tag 的末段 / 枚举码 / node / 路径）
    pub name: Option<String>,    // 译文（zh）
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detail: Option<Value>,   // node 详情 / 物品实体信息（可选）
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub translated: bool,
}

// 节点（worldstate 内联形态）
#[derive(Serialize)]
pub struct NodeRef { pub r#type: String, pub name: String }

// 奖励条目（§3.2 统一元素）
#[derive(Serialize)]
pub struct RewardItem {
    pub r#type: String,
    pub item_count: i64,
    pub item_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")] pub probability: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")] pub rarity: Option<String>,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")] pub translated: bool,
}

// 时间辅助
pub fn to_iso(ms: i64) -> String;   // epoch 毫秒 → "2026-08-22T16:06:12Z"（chrono::Utc）
pub fn to_iso_sec(s: i64) -> String;
pub fn human_remaining(secs: i64) -> String;  // "1h 20m"
```

---

## 5. aliases.rs —— 物品简写

```rust
pub async fn resolve_alias(pool: &PgPool, alias: &str, lang: &str)
    -> Result<Vec<AliasHit>, ApiError>;
// AliasHit { entity_type, entity_id, name, description }
// SQL:
//   SELECT a.entity_type, a.entity_id, loc(l.name_loc, $2) AS name, ...
//   FROM aliases a JOIN <按 entity_type 动态映射名称列> ...
//   简化实现：先查 aliases 得 (entity_type, entity_id)，
//   再按类型查对应实体表取 name_loc 译文（同 §9 物品解析逻辑复用）
```

匹配流程（`GET /api/items/{name}`）：
1. `SELECT * FROM aliases WHERE alias = $1`（精确，大小写不敏感 `lower(alias)=lower($1)`）→ 有则直接返回命中实体
2. 无别名命中 → `v_localized` 名称模糊：`SELECT entity_type, entity_id, value FROM v_localized WHERE lang=$1 AND value ILIKE '%'||$2||'%' AND field='name' ORDER BY entity_type LIMIT $3`
3. 返回 `{ query, resolved_alias, results[] }`

`POST /api/aliases`（§13 routes/items.rs）：携带 `X-API-Key`；校验 `ALIAS_API_KEY`；未配置→503、不匹配→401；批量 upsert。

---

## 6. worldstate/mod.rs —— 拉取 + 缓存 + 解析入口

```rust
pub struct WorldStateCache {
    inner: RwLock<Option<CacheEntry>>,        // CacheEntry { fetched_at: Instant, data: Arc<ParsedWorldState> }
    inflight: Mutex<Option<oneshot::Sender<Result<Arc<ParsedWorldState>, String>>>>,
    cfg: CacheCfg,                             // ttl, min_interval, url
    last_fetch: AtomicU64,                     // unix 秒，min_interval 兜底
}

pub async fn get(&self, pool, lang) -> Result<(Arc<ParsedWorldState>, FetchMeta), ApiError>;
// FetchMeta { fetched_at: String(ISO), stale: bool, age_secs: u64 }
```

`get()` 流程：
1. `inner` 有缓存且 `now - fetched_at < ttl` → 直接返回（`age_secs` = 差值，`stale=false`）
2. 无缓存/过期：
   - `inflight` 已有在途请求 → 等待其 oneshot 结果（singleflight）
   - 否则置 inflight → `fetch_and_parse(pool, lang)` → 成功：写缓存、发结果；失败：若有旧缓存 → 返回旧缓存（`stale=true`），否则 → 502
3. `last_fetch` 距上次 < min_interval 且本次为强制刷新 → 拒绝（429/503）

`fetch_and_parse`：`fetch.rs` 拉原始 JSON → `types.rs` 反序列化 → `parse.rs` 解析（含 cycles）→ `Arc::new`。

---

## 7. worldstate/fetch.rs —— 官方源拉取

```rust
pub async fn fetch_raw(cfg: &CacheCfg) -> Result<serde_json::Value, String>;
```

- `reqwest::Client`（单例，`gzip(true)`，`user_agent("warframe-api/0.1")`，timeout 30s）
- `cfg.worldstate_url` GET → bytes → gzip 解码（reqwest gzip 特性自动）→ `serde_json::from_slice`
- 非 200 / 解析失败 → `Err(msg)`
- 重试 1 次（网络抖动），间隔 1s

---

## 8. worldstate/types.rs —— 官方 JSON 原始结构（serde）

按 2026 版实测键（PascalCase）定义只读结构，`#[serde(rename_all = "PascalCase")]`，多余字段 `#[serde(flatten)] extra: HashMap<String, Value>` 保留（透传未解析节）。

```rust
#[derive(Deserialize)]
pub struct RawWorldState {
    #[serde(default)] pub time: Option<i64>,            // epoch 秒
    #[serde(default)] pub alerts: Vec<RawAlert>,
    #[serde(default)] pub events: Vec<RawEvent>,        // WorldEvent 形状
    #[serde(default)] pub goals: Vec<RawGoal>,
    #[serde(default)] pub sorties: Vec<RawSortie>,
    #[serde(default)] pub active_missions: Vec<RawActiveMission>,  // fissures 同形
    #[serde(default)] pub void_storms: Vec<RawVoidStorm>,
    #[serde(default)] pub invasions: Vec<RawInvasion>,
    #[serde(default)] pub void_traders: Vec<RawVoidTrader>,
    #[serde(default)] pub daily_deals: Vec<RawDailyDeal>,
    #[serde(default)] pub syndicate_missions: Vec<RawSyndicateMission>,
    #[serde(default)] pub nightwave: Option<RawNightwave>,
    #[serde(default)] pub descents: Vec<RawDescent>,
    #[serde(default)] pub persistent_enemies: Vec<RawPersistentEnemy>,
    #[serde(default)] pub flash_sales: Vec<RawFlashSale>,
    #[serde(default)] pub global_upgrades: Vec<RawGlobalUpgrade>,
    #[serde(flatten)] pub extra: HashMap<String, Value>,
}

// 通用时间包装（MongoDB 风格）
#[derive(Deserialize)]
pub struct RawDate { #[serde(rename = "$date")] pub date: RawNumberLong }
#[derive(Deserialize)]
pub struct RawNumberLong { #[serde(rename = "$numberLong")] pub value: String }  // 毫秒字符串

// 奖励
#[derive(Deserialize)]
pub struct RawReward {
    #[serde(default)] pub items: Vec<String>,
    #[serde(default)] pub counted_items: Vec<RawCountedItem>,
    #[serde(default)] pub credits: Option<i64>,
    #[serde(default)] pub xp: Option<i64>,
}
pub struct RawCountedItem { pub item_type: String, pub item_count: i64 }

// 各节（示例，字段以实测为准，多余字段 flatten）
pub struct RawAlert { #[serde(rename = "_id")] pub id: RawId,
    pub activation: RawDate, pub expiry: RawDate,
    pub mission_info: RawMissionInfo, pub tag: Option<String> }
pub struct RawMissionInfo {
    pub location: String,                // SolNode25
    pub mission_type: String,            // MT_TERRITORY
    pub faction: String,                 // FC_CORPUS
    pub mission_reward: RawReward,
    pub min_enemy_level: i64, pub max_enemy_level: i64,
    pub desc_text: Option<String>,       // loc tag
    #[serde(flatten)] pub extra: HashMap<String, Value>,
}
pub struct RawActiveMission { pub node: String, pub mission_type: String,
    pub modifier: Option<String>, pub hard: Option<bool>, pub activation: RawDate, pub expiry: RawDate }
pub struct RawVoidStorm { pub node: String, pub active_mission_tier: Option<String>, /* VoidT1 */ ... }
pub struct RawSortie { pub reward: String, pub boss: Option<String>,
    pub variants: Vec<RawSortieVariant>, pub missions: Vec<RawMissionInfo>, pub activation: RawDate, pub expiry: RawDate }
pub struct RawSortieVariant { pub mission_type: String, pub modifier_type: Option<String>, pub node: String }
pub struct RawInvasion { pub node: String, pub loc_tag: Option<String>,
    pub attacker_mission_info: RawFactionInfo, pub defender_mission_info: RawFactionInfo,
    pub attacker_reward: Option<RawReward>, pub defender_reward: Option<RawReward>,
    pub count: i64, pub goal: i64, pub completed: bool, pub activation: RawDate }
pub struct RawFactionInfo { pub faction: String }          // FC_*
pub struct RawVoidTrader { pub character: Option<String>, pub node: String,
    pub manifest: Vec<RawVoidTraderItem>, pub activation: RawDate, pub expiry: RawDate }
pub struct RawVoidTraderItem { pub item_type: String, pub prime_price: Option<i64>, pub regular_price: Option<i64> }
pub struct RawDailyDeal { pub store_item: String, pub discount: i64,
    pub original_price: i64, pub sale_price: i64, pub activation: RawDate, pub expiry: RawDate }
pub struct RawSyndicateMission { pub tag: String, #[serde(default)] pub nodes: Vec<String>,
    pub jobs: Vec<RawSyndicateJob> }
pub struct RawSyndicateJob { pub job_type: Option<String>, pub rewards: String,   // deck 路径
    pub min_enemy_level: i64, pub max_enemy_level: i64, #[serde(default)] pub xp_amounts: Vec<i64> }
pub struct RawNightwave { pub affiliation_tag: Option<String>,
    pub challenges: HashMap<String, RawNightwaveChallenge>, /* key=挑战路径 */
    #[serde(default)] pub rewards: Vec<RawNightwaveReward> }
pub struct RawNightwaveChallenge { pub name: Option<String>, pub description: Option<String>,
    pub standing: Option<i64>, pub required: Option<i64>, pub icon: Option<String>,
    pub tip: Option<String>, pub tip_icon: Option<String> }
pub struct RawNightwaveReward { pub unique_name: String, pub name: Option<String>,
    pub description: Option<String>, pub icon: Option<String>, pub item_count: Option<i64> }
pub struct RawEvent { pub desc: Option<String>, pub tool_tip: Option<String>,
    pub node: Option<String>, pub faction: Option<String>, pub score_loc_tag: Option<String>,
    pub reward: Option<RawReward>, pub tag: Option<String>, pub activation: RawDate, pub expiry: RawDate,
    pub jobs: Vec<RawSyndicateJob>, #[serde(flatten)] pub extra: HashMap<String, Value> }
pub struct RawGoal { pub node: Option<String>, pub score_loc_tag: Option<String>,
    pub desc: Option<String>, pub tool_tip: Option<String>, pub reward: Option<RawReward>, ... }
pub struct RawDescent { pub challenges: Vec<RawDescentChallenge>, pub activation: RawDate, pub expiry: RawDate }
pub struct RawDescentChallenge { pub r#type: Option<String>, pub challenge: Option<String>,
    pub level: Option<String>, /* /Lotus/Levels/... */ ... }
pub struct RawPersistentEnemy { pub agent_type: Option<String>, pub loc_tag: Option<String>,
    pub last_discovered_location: Option<String>, pub rank: Option<i64>, ... }
pub struct RawId { #[serde(rename = "$oid")] pub oid: Option<String> }
```

> 反序列化策略：`serde_json::from_value::<RawWorldState>(value)` 失败时降级为 `extra` 全量透传（`ParsedWorldState::Passthrough(Value)`），保证接口不因新键崩溃。

---

## 9. worldstate/resolve.rs —— 翻译解析器（核心）

```rust
pub struct Resolver<'c> { cur: &'c mut PgPool, lang: String,
    tag_cache: HashMap<String, Option<String>>,     // loc_tag -> 译文（本次解析周期内复用）
    enum_cache: HashMap<String, Option<String>>,    // "category|code" -> name_loc
}
impl Resolver<'_> {
    pub async fn loc(&mut self, tag: &str) -> Option<String>;          // 命中 tag_cache
    pub async fn resolve(&mut self, value: &str) -> Resolved;          // §3.1 全规则
    pub async fn node(&mut self, id: &str) -> Option<NodeRef>;         // regions 查询
    pub async fn item(&mut self, path: &str) -> Option<(String, String, Option<String>)>; // (entity_type, name, desc)
    pub async fn expand_deck(&mut self, deck: &str) -> Option<Vec<TierRewards>>;  // §10 rewards
}
```

`resolve(value)` 分派：
1. `value` 以 `/Lotus/Language/` 或 `/EE/Language/` 开头 → `loc()`；`code` = 末段
2. `MT_*` / `FC_*` → `SELECT name_loc FROM worldstate_enums WHERE category=$1 AND enum_code=$2` → `loc(name_loc)`
3. `SolNode\d+|CrewBattleNode\d+|\w+HUB` → `node()`：`regions` 查 name_loc 译文；`Resolved{ code=id, name, detail=null, translated }`
4. `/Lotus/...` → `item()`：路径变体（去 `/Lotus/StoreItems`、`/Lotus/Types/StoreItems`→`/Lotus/StoreItems`）→ 实体表探测（`upgrades→weapons→resources→warframes→arcanes→relics→sentinels→mod_sets→...`），取 `name_loc` 译文；`code` = 原路径
5. `SORTIE_BOSS_*` → 后缀词（末段）`enemy_avatars ILIKE '%词%'` 取 name_loc 译文
6. `SORTIE_MODIFIER_*` → 内置常量表（英文名）
7. `VoidT1..5` → 常量映射 era（Lith/Meso/Neo/Axi/Requiem）
8. 其他 → `Resolved{ code=value, name=None, translated=false }`

批量缓存：`tag_cache` 用 `SELECT loc_tag, value FROM localizations WHERE lang=$1 AND loc_tag = ANY($2)` 批量预热（解析开始时收集本次会遇到的 tags 一次性查询）；enum 同理。

---

## 10. worldstate/parse.rs —— 各节解析 + rewards 展开

```rust
pub async fn parse_all(raw: RawWorldState, res: &mut Resolver<'_>, expand: bool, sections: &[Section])
    -> ParsedWorldState;
// ParsedWorldState = serde_json::Value（按 §5.1 结构组装的 JSON）
// Section enum: alerts/events/fissures(invasions 同源)/sortie/void_trader/daily_deals/
//               syndicate_missions/nightwave/cycles/persistent_enemies/descents/goals/news/...
```

每个节一个 `parse_xxx(raw, res, expand) -> Value` 函数，输出结构遵循 design.md §5.1 示例（camelCase 键）。

**rewards 展开（形态 A/B，design §3.2）**：

```rust
// 形态 A：直接列表
async fn expand_direct(&mut self, r: &RawReward) -> Vec<RewardItem> {
    // items[] + countedItems[] + credits/xp → RewardItem 数组（credits→type="credits", item_name="星币"）
}
// 形态 B：deck 引用
async fn expand_deck(&mut self, deck: &str) -> Vec<TierRewards> {   // expand=true 时
    // SELECT t.tier_index, i.slot, i.type, i.item_count, i.probability, i.rarity
    // FROM mission_reward_decks d JOIN mission_reward_tiers t ... JOIN mission_reward_items i ...
    // WHERE d.unique_name = $1 ORDER BY t.tier_index, i.slot
    // 每 item：item_name = self.item(&i.type).name（去 StoreItems 前缀反查，§9 复用）
    // 返回 [{ tier, items: [RewardItem] }]
}
// expand=false 时：返回 [{ deck, deck_name: Option<String> }]（deck_name 尽力翻译，失败回退原文）
```

**cycles 本地计算**（§11 常量表）：

```rust
pub struct CycleInfo { pub name: String, pub state: String, pub state_name: String,
    pub activation: String, pub expiry: String,   // ISO
    pub remaining_seconds: i64, pub remaining: String }
pub fn compute_cycles(now: DateTime<Utc>) -> Vec<CycleInfo>;
```

---

## 11. cycles.rs —— 世界循环本地计算（常量表）

```rust
// 每个循环一条：{ anchor: DateTime<Utc>, segments: Vec<(state, secs)>, cycle: i64 }
// 状态顺序循环；state → state_name 中文映射常量
const CYCLE_DEFS: &[CycleDef] = &[
    // 名称    状态序列(秒)                周期秒   锚点
    // cetus   day=6000, night=3000       9000     (对齐：day 起算锚点可配置)
    // earth   day=14400, night=14400     28800
    // vallis  warm=400, cold=1200        1600     2026-02-04T19:46:48Z
    // cambion 与 cetus 同步：cetus 白天=fass / 夜晚=vome（不单独锚点）
    // zariman corpus=9000, grineer=9000  18000    2022-06-14T05:00:00Z
    // duviri  sorrow/fear/joy/anger/envy 各 7200   36000
    // midrath day=1920, night=960        2880     2025-08-07T16:05:29Z
];
fn current(now: DateTime<Utc>, def: &CycleDef) -> CycleInfo {
    let elapsed = (now - def.anchor).num_seconds().rem_euclid(def.cycle);
    // 按 segments 累减定位当前段 → state/activation/expiry/remaining
}
// 状态中文：day=白天 night=夜晚 warm=温暖 cold=寒冷 fass=Fass vome=Vome
//          corpus=Corpus grineer=Grineer sorrow=悲伤 fear=恐惧 joy=喜悦 anger=愤怒 envy=嫉妒
```

> 时长/锚点来源：Fandom Wiki 与 warframe-worldstate-parser 实现核对（design §2.2），常量可调。

---

## 12. routes/mod.rs —— 路由表

```rust
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/health", get(health::health))
        .route("/api/worldstate", get(worldstate::get))
        .route("/api/worldstate/rewards", get(worldstate::rewards))
        .route("/api/worldstate/_refresh", post(worldstate::refresh))
        .route("/api/cycles", get(cycles::list))
        .route("/api/nodes/{node_type}", get(nodes::detail))
        .route("/api/items/{name}", get(items::search))
        .route("/api/items/{name}/drops", get(items::drops))
        .route("/api/aliases", post(items::post_aliases))
        .route("/api/mods", get(mods::list))
        .route("/api/mods/{unique_name}", get(mods::detail))
        .route("/api/weapons", get(weapons::list))
        .route("/api/weapons/{name}", get(weapons::detail))
        .route("/api/weapons/{name}/riven", get(weapons::riven))
        .layer(CorsLayer::permissive())
        .layer(TraceLayer::new_for_http())
}
```

---

## 13. routes/worldstate.rs / cycles.rs

**GET /api/worldstate**（`?lang=&sections=&expand=`）：
1. `ws.get(&pool, lang)` → `(data, meta)`
2. `sections` 解析（逗号分隔，空=全部；无效节名→400）；`cycles`/`meta` 恒附带
3. 按 `sections` 从 `data`（已解析的 Value）提取子对象组装
4. 响应头：`X-WorldState-Age`（秒）、`X-WorldState-Stale`（0/1）
5. 返回 `{ ...sections..., "meta": { source, fetched_at(ISO), stale } }`

**GET /api/worldstate/rewards**：遍历 alerts/events/invasions/sortie 等节的奖励，聚合为
`[{ "source": "alert:<id>", "rewards": [...], "deck": "..."|null }, ...]`（复用 §10 展开）

**POST /api/worldstate/_refresh**：强制刷新（受 min_interval 保护，过早→429）；成功返回新数据

**GET /api/cycles**（`?name=` 可选）：`compute_cycles(now)` 全量或单查（未知 name→404）；ISO 时间输出

---

## 14. routes/nodes.rs —— 节点详情

`GET /api/nodes/{node_type}?lang=&expand=`：
1. `node_type` 精确查 `regions`（`unique_name = $1`）；未命中→404
2. 组装：`type`/`name`/`system{index,name}`/`mission_type{code:mission_name_loc 末段?, name}`/`faction{...}`/`enemy_levels`/`mastery_req`/`node_type`/`reward_manifests[]`
   - mission_type：新版 regions 无 MT 枚举列，用 `mission_name_loc` 译文 + 末段作 code（或补查 `worldstate_enums` 反查 MT 码，命中则输出）
   - faction：`faction_name_loc`（load.py 已用 FC_* 映射补全）
3. `expand=true`（默认）→ 对每个 `reward_manifests[]` 调 `expand_deck` 输出 `rewards: [ {deck, deck_name, tiers:[...]} ]`；`expand=false` → 仅 deck 引用
4. SQL 见 design §5.4

---

## 15. routes/items.rs —— 物品查询 / 别名管理 / 掉落

**GET /api/items/{name}?lang=**：§5 流程（别名精确 → v_localized 模糊），结果 `{query, resolved_alias, results[]}`
- 无任何命中 → 404 `{error:"未找到物品"}`
- `name` 为空 → 400

**POST /api/aliases**（`X-API-Key`）：
1. `config.alias_api_key` 为 None → 503
2. 头缺失/不匹配 → 401
3. body `{aliases:[{alias, entity_type, entity_id}]}` 校验字段非空（非法→400）
4. `INSERT INTO aliases ... ON CONFLICT (alias, entity_type, entity_id) DO UPDATE` 批量
5. 返回 `{inserted: n}`

**GET /api/items/{name}/drops?lang=**：反查聚合（design §5.9）：
```sql
-- mission_reward_items（归一化 type 后匹配）
SELECT 'mission_reward' AS source_type, d.unique_name AS source,
       i.item_count, i.probability, i.rarity
FROM mission_reward_items i JOIN mission_reward_tiers t ON t.tier_id=i.tier_id
JOIN mission_reward_decks d ON d.unique_name=t.deck_unique_name
WHERE regexp_replace(i.type, '^/Lotus/StoreItems', '/Lotus') = $1
-- enemy_droptable_items
SELECT 'enemy_droptable' AS source_type, p.droptable_unique_name AS source,
       i.probability FROM enemy_droptable_items i
JOIN enemy_droptable_pools p ON p.pool_id=i.pool_id
WHERE regexp_replace(i.type, '^/Lotus/StoreItems', '/Lotus') = $1
-- recipe（原料/产物）
SELECT 'recipe_ingredient' AS source_type, recipe_unique_name AS source, item_count
FROM recipe_ingredients WHERE item_type = $1
UNION ALL
SELECT 'recipe_result' AS source_type, unique_name AS source, NULL FROM recipes WHERE result_type = $1
-- bundle_components
SELECT 'bundle' AS source_type, bundle_unique_name AS source, purchase_quantity
FROM bundle_components WHERE type_name = $1
```
`source_name` 翻译：deck 用 `v_localized(entity_id=source, field='name')` 尽力解析，失败回退原文；响应含 `{item:{type,name}, drops:[{source_type, source, source_name, chance, rarity, item_count}]}`

---

## 16. routes/mods.rs —— Mod 查询

**GET /api/mods?lang=&type=&name=&polarity=&rarity=&limit=&offset=**：
```sql
SELECT unique_name, loc(name_loc, $1) AS name, type, polarity, rarity,
       base_drain, fusion_limit
FROM upgrades
WHERE ($2::text IS NULL OR type = $2)
  AND ($3::text IS NULL OR polarity = $3)
  AND ($4::text IS NULL OR rarity = $4)
  AND ($5::text IS NULL OR loc(name_loc, $1) ILIKE '%'||$5||'%')
ORDER BY name NULLS LAST, unique_name
LIMIT $6 OFFSET $7
```
（无效 `type`/`polarity`/`rarity` 值→400；limit clamp 1..100）

**GET /api/mods/{unique_name}?lang=**：+ 词条（`upgrade_entries`+`upgrade_entry_values`，loc_tag 译文）、
`compatibility_tags`、`available_challenges`（description_loc 译文）；未命中→404

---

## 17. routes/weapons.rs —— 武器 / 紫卡倾向

**GET /api/weapons?lang=&category=&name=**：`weapons` 列表（`product_category`/名称过滤，同 mods 模式）

**GET /api/weapons/{name}?lang=**：详情，含：
- 基础/面板字段全量（design §5.7）
- 伤害分量：`weapon_damage_per_shot`（slot/value 数组）
- 行为伤害：`weapon_behaviours`+`weapon_behaviour_damage` 按 `(slot, path)` 分组 → `{state_name(译文), impact:{DT_IMPACT:..}, projectile:{attack:{...}}}` 形状
- 兼容标签：`weapon_compatibility_tags`
- 匹配：`unique_name=$1` 或 `loc(name_loc,$2)=$1`（名称精确）；未命中→404

**GET /api/weapons/{name}/riven?lang=**：
```sql
SELECT unique_name, loc(name_loc, $2) AS name, omega_attenuation, prime_omega_attenuation
FROM weapons WHERE unique_name = $1 OR loc(name_loc, $2) = $1
```
响应 `{weapon, name, omega_attenuation, prime_omega_attenuation, disposition_rank?}`（rank 为可选常量映射，默认不输出）

---

## 18. main.rs —— 启动

```rust
#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    tracing_subscriber::fmt().with_env_filter(EnvFilter::from_default_env()).init();
    let cfg = Config::from_env();
    let pool = db::create_pool(&cfg.database_url).await?;
    let ws = Arc::new(WorldStateCache::new(cfg.clone()));
    let state = AppState { pool, config: cfg.clone(), ws };
    let listener = tokio::net::TcpListener::bind(&cfg.bind_addr).await?;
    tracing::info!("listening on {}", cfg.bind_addr);
    axum::serve(listener, routes::router().with_state(state)).await?;
    Ok(())
}
```

---

## 19. 边界情况与健壮性清单

| 场景 | 处理 |
|---|---|
| 官方 worldstate 返回未知新键/新节 | `extra` flatten 透传；解析失败降级 Passthrough，不 500 |
| 官方拉取失败 | 有缓存→stale 返回；无缓存→502 |
| loc tag 字典未收录（新 tag） | 回退原文 + `translated:false`，tracing WARN |
| deck 路径不在 mission_reward_decks | expand_deck 返回空 tiers，不报错 |
| 节点不存在 | /api/nodes 404；worldstate 内联 node 回退 `name=type` |
| 简写命中多实体 / 名称模糊多结果 | 全部返回 results[] 让客户端选择 |
| 并发缓存过期 | singleflight 只放行一个上游请求 |
| 无 ALIAS_API_KEY | POST /api/aliases → 503 |
| 超大 sections / 非法节名 | 400 |
| 时间戳缺失 | 输出 null（字段 Option） |

## 20. 测试要点

- 单元：`cycles` 公式（锚点±偏移断言 state/起止 ISO）、`resolve` 分派、`to_iso`/`human_remaining`、rewards 展开（构造 fixture）
- 集成（`tower::ServiceExt`）：/api/worldstate 首次拉取+二次命中缓存（mock 上游或本地 fixture 文件）、/api/nodes/SolNode94、/api/items/血妈、POST /api/aliases 401/503 分支
- SQL 直测：nodes/mods/weapons/drops 查询在 warframe 库执行验证

---

*本文档与 `doc/design.md` 配套；实现过程中若与设计冲突，以本文档为最终实现依据并回更设计。*
