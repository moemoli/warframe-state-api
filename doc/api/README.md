# Warframe API 文档索引

> 服务地址默认 `http://<host>:8099`（`BIND_ADDR` 配置）。
> 每个端点独立文档，含**游戏数据背景说明**、请求参数、调用示例与完整返回结构。

---

## 📖 文档目录

### 系统

| 文档 | 端点 | 说明 |
|---|---|---|
| [health](health.md) | `GET /health` | 健康检查（含数据库连通性） |
| [worldstate-refresh](worldstate-refresh.md) | `POST /api/worldstate/_refresh` | 强制刷新世界状态缓存 |

### 世界状态（实时）

| 文档 | 端点 | 游戏内容 |
|---|---|---|
| [worldstate](worldstate-get.md) | `GET /api/worldstate` | 全量世界状态：警报/裂缝/入侵/突击/电波/商人… |
| [rewards](worldstate-rewards.md) | `GET /api/worldstate/rewards` | 当前可领取奖励聚合 |
| [arbitrations](arbitrations.md) | `GET /api/arbitrations` | 仲裁轮换表（每小时一换的高难任务） |
| [cycles](cycles.md) | `GET /api/cycles` | 平原昼夜/温度/心绪循环（本地计算） |

### 资料查询

| 文档 | 端点 | 游戏内容 |
|---|---|---|
| [search](search.md) ⭐ | `GET /api/search` | 统一搜索：中文简称 + 官方 + WM + 紫卡 + 玄骸 |
| [items-search](items-search.md) | `GET /api/items/{name}` | 官方库物品检索（旧版兼容） |
| [items-drops](items-drops.md) | `GET /api/items/{name}/drops` | 物品掉落/获取途径反查 |
| [nodes](nodes.md) | `GET /api/nodes/{nodeId}` | 星图节点详情与奖励表 |
| [mods-list](mods-list.md) / [mods-detail](mods-detail.md) | `GET /api/mods...` | MOD 卡库查询 |
| [weapons-list](weapons-list.md) / [weapons-detail](weapons-detail.md) / [weapons-riven](weapons-riven.md) | `GET /api/weapons...` | 武器库/深度面板/紫卡倾向 |
| [synthesis](synthesis.md) | `GET /api/synthesis` | 结合仪式每日目标地点速查 |

### 市场（warframe.market）

| 文档 | 端点 | 游戏内容 |
|---|---|---|
| [wfm-items](wfm-items.md) / [detail](wfm-items-detail.md) | `GET /api/wfm/items...` | 可交易物品列表 / 详情+实时价格 |
| [wfm-rivens](wfm-rivens.md) / [attributes](wfm-riven-attributes.md) / [detail](wfm-rivens-detail.md) | `GET /api/wfm/rivens...` | 紫卡武器库（段位/倾向筛选）/ 词条全集 / 详情 |
| [wfm-auctions](wfm-auctions.md) | `GET /api/wfm/auctions/{slug}` | 紫卡拍卖实时挂单 + 服务端筛选（洗练/等级/段位/词条/极性/价格/状态），命中项逐条标注条件 |
| [wfm-spread](wfm-spread.md) | `GET /api/wfm/spread/{slug}` | 词条价差：哪个词条最值钱（支持 auctions 同款筛选） |
| [wfm-trends](wfm-trends.md) | `GET /api/wfm/trends/{slug}` | 价格走势（48h/90d 真实成交） |
| [wfm-components](wfm-components.md) | `GET /api/wfm/components` | 杜卡德垃圾分档筛选 |
| [wfm-liches](wfm-liches.md) / [detail](wfm-liches-detail.md) | `GET /api/wfm/liches...` | 赤毒玄骸武器 |
| [wfm-sisters](wfm-sisters.md) / [detail](wfm-sisters-detail.md) | `GET /api/wfm/sisters...` | 帕尔沃斯姐妹武器 |
| [wfm-rankings](wfm-rankings.md) | `GET /api/wfm/rankings` | 本站查询热度排行 |

### 其他

| 文档 | 端点 | 说明 |
|---|---|---|
| [aliases-post](aliases-post.md) | `POST /api/aliases` | 别名提交（API Key 保护） |

---

## 0. 通用约定

| 约定 | 说明 |
|---|---|
| **语言** | 所有端点支持 `?lang=zh`（缺省取 `DEFAULT_LANG`，默认 `zh`）；当前导入 zh/en 字典 |
| **时间** | 所有时间字段统一 **UTC ISO 8601**：`2026-08-23T10:00:00Z` |
| **URL 编码** | 路径参数含 `/` 时必须 URL 编码，如 `/Lotus/Powersuits/Wisp/Wisp` → `%2FLotus%2FPowersuits%2FWisp%2FWisp` |
| **响应** | 一律 `application/json`；错误统一 `{"error": "<原因>"}` |
| **错误码** | 400 参数错误 / 401 鉴权失败 / 404 未找到 / 429 过于频繁 / 500 数据库错误 / 502 worldstate 上游失败 / 503 服务未配置 |
| **worldstate 头** | `GET /api/worldstate` 响应头携带 `X-WorldState-Age`（缓存秒数）、`X-WorldState-Stale`（0/1） |
| **翻译失败** | 引用字段译文缺失时返回原值并附 `"translated": false` |

---

## 枚举翻译体系

所有世界状态中的内部枚举标识符通过 `worldstate_enums` 表翻译，数据来源分两类。

**导出来源**（`load.py` 自动生成）：

| 分类 | 前缀 | 示例 |
|---|---|---|
| `mission_type` | `MT_` | `MT_SURVIVAL` → 生存 |
| `faction` | `FC_` | `FC_CORPUS` → Corpus |

**Wiki 手动维护**（来源 [wiki.warframe.com/w/World_State](https://wiki.warframe.com/w/World_State) + [doroprime](https://github.com/Yawanaika/doroprime)，共 17 类 290 条）：

| 分类 | 前缀/示例 | 示例翻译 |
|---|---|---|
| `sortie_boss` | `SORTIE_BOSS_AMAR` | 猎杀者Amar |
| `sortie_modifier` | `SORTIE_MODIFIER_FIRE` | 火焰增强 |
| `relic_tier` | `VoidT1`→古纪 … `VoidT6`→全能 | |
| `descent_type` | `DT_SHRINE_DEFENSE` | 祈运坛防御 |
| `descent_challenge` | `HeavyWeaponsOnly` 等 65 条 | 易受曲翼枪械攻击的敌人 |
| `descent_level` / `descent_specs` / `descent_aura` | 地图/敌人规格/Penance | |
| `archimedea_type/difficulty/deviation/risk/personal` | Archimedea 全套修正 | `CD_HARD`→精英Archimedea |
| `calendar_season` / `calendar_event_type` | `CST_SPRING`→春季、`CET_CHALLENGE`→挑战 | |
| `upgrade_type` / `goal_tag` | 全局增益 / 活动事件名 | |

均支持 `?lang=` 切换（zh/en）。

---

## 配置（环境变量 / .env）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgres://warframe:warframe123@127.0.0.1:5432/warframe` | PostgreSQL 连接串 |
| `BIND_ADDR` | `0.0.0.0:8099` | 监听地址 |
| `DEFAULT_LANG` | `zh` | 缺省语言 |
| `WORLDSTATE_URL` | `https://api.warframe.com/cdn/worldState.php` | 官方 worldState 端点 |
| `WORLDSTATE_CACHE_TTL` | `180` | 缓存秒数 |
| `WORLDSTATE_MIN_INTERVAL` | `30` | 强制刷新最小间隔（秒） |
| `ALIAS_API_KEY` | 无 | 别名提交鉴权密钥 |

---

## 快速上手

```bash
# 启动
CARGO_TARGET_DIR=temp/target cargo build && \
ALIAS_API_KEY=testkey123 BIND_ADDR=127.0.0.1:8099 ./temp/target/debug/warframe-api

# 数据库初始化 / 更新数据
python3 scripts/load.py --fetch --langs zh   # 生成 sql/import.sql
psql -d warframe -f sql/init.sql             # 首次建表
psql -d warframe -f sql/import.sql           # 导入数据
```

```bash
# 常用调用
curl localhost:8099/health
curl "localhost:8099/api/search?q=血妈&lang=zh"                     # 统一搜索
curl "localhost:8099/api/worldstate?sections=alerts,fissures,cycles&lang=zh"
curl "localhost:8099/api/arbitrations?lang=zh&limit=5"
curl "localhost:8099/api/cycles"
curl "localhost:8099/api/nodes/SolNode94?lang=zh"
curl "localhost:8099/api/weapons/斯特朗/riven?lang=zh"
curl "localhost:8099/api/wfm/items/adaptation?lang=zh"              # WM 实时价格
curl "localhost:8099/api/wfm/auctions/rubico?lang=zh"               # 紫卡拍卖
curl "localhost:8099/api/wfm/auctions/rubico?lang=zh&rerolls_max=0&pos_min=2&neg_max=0&attr_pos=critical_chance,critical_damage"  # 拍卖筛选
curl "localhost:8099/api/wfm/trends/adaptation"                     # 90 天价格趋势
curl "localhost:8099/api/synthesis?target=火焰轰击者"                # 结合目标反查
```

---

*数据来源：[warframe-public-export-plus](https://github.com/calamity-inc/warframe-public-export-plus) ·
[官方 worldState API](https://api.warframe.com/cdn/worldState.php) ·
[warframe.market v1/v2](https://docs.astrbot.app) ·
[browse.wf](https://browse.wf) ·
[wiki.warframe.com](https://wiki.warframe.com/w/World_State) ·
[doroprime](https://github.com/Yawanaika/doroprime)*
