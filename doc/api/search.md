# GET /api/search —— 统一搜索（推荐）

> 分组：资料查询　|　[← 返回索引](README.md)

## 🎮 这是什么游戏数据

跨库统一搜索入口。Warframe 社区存在大量昵称文化（Garuda 叫"血妈"、Forma 叫"福马"），本端点内置 116 条中文简称别名表，并同时搜索官方实体库与 warframe.market 商品库、紫卡武器库、赤毒/信条武器库，一次返回全部来源。

**一次查询同时覆盖 5 个数据源**：别名 → 官方库 → wfm 物品 → 紫卡武器 → 赤毒/姐妹武器。结果合并去重，每条自动关联 wfm 数据。

| 参数 | 说明 |
|---|---|
| `q` | 搜索关键词（必填，支持中文/英文/简称） |
| `lang` | 语言，默认 zh |
| `limit` | 最大返回条数，默认 20，上限 50 |
| `trade` | `true` 时仅返回有 wfm 数据的可交易结果（过滤 wfm=null） |
| `source` | 按来源筛选：逗号分隔 `alias,official,wfm,riven,lich,sister`（如 `source=wfm,riven`）；筛选后为空返回 404 |

```bash
curl "http://127.0.0.1:8099/api/search?q=血妈&lang=zh"              # 别名
curl "http://127.0.0.1:8099/api/search?q=rubico&lang=zh"            # 紫卡+wfm
curl "http://127.0.0.1:8099/api/search?q=kuva&lang=zh"              # 赤毒武器
curl "http://127.0.0.1:8099/api/search?q=信条&lang=zh&trade=true"   # 仅可交易
```

### 数据源

| source | 说明 | 数据量 |
|---|---|---|
| `alias` | 别名精确命中（116 条中文简称） | — |
| `official` | 官方实体库（战甲/武器/Mod/资源等） | 3w+ |
| `wfm` | warframe.market 可交易物品 | 3720 |
| `riven` | 紫卡武器（含倾向值） | 414 |
| `lich` | 赤毒玄骸武器 | 21 |
| `sister` | 帕尔沃斯姐妹武器 | 11 |

### 返回格式

```json
{
  "query": "kuva",
  "resolved_alias": null,
  "count": 10,
  "results": [
    {
      "source": "lich",
      "entity_type": "lich_weapon",
      "entity_id": "kuva_nukor",
      "name": "赤毒·努寇微波枪",
      "wfm": { "slug": "kuva_nukor", "mastery_level": 13, "item_name": "赤毒·努寇微波枪" }
    },
    {
      "source": "riven",
      "entity_type": "riven_weapon",
      "entity_id": "rubico",
      "name": "绝路",
      "wfm": { "slug": "rubico", "riven_type": "rifle", "disposition": 0.95 }
    }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `source` | 命中来源 |
| `entity_type` | 实体类型（warframes/weapons/wfm/riven_weapon/lich_weapon/sister_weapon） |
| `wfm` | warframe.market 关联数据（`null` = 不可交易或未关联） |
| `wfm.slug` | warframe.market URL 路径 |
| `wfm.disposition` | 紫卡倾向值（仅 riven_weapon） |
| `wfm.riven_type` | 紫卡类型：rifle/pistol/melee/shotgun（仅 riven_weapon） |
| `wfm.mastery_level` | 段位要求（仅 lich/sister_weapon） |
| `resolved_alias` | 别名命中时返回原始简称 |

---
