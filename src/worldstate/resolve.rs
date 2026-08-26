//! 翻译解析器：把 worldstate 中的各类键解析为译文/详情（design §9 / §3.1）

use std::collections::HashMap;

use serde_json::{json, Value};
use sqlx::PgPool;

use crate::error::ApiError;
use crate::models::{NodeRef, Resolved, RewardItem, TierRewards};

/// 实体探测表（有 name_loc 列、unique_name 主键的表）
const ENTITY_TABLES: &[&str] = &[
    "warframes", "weapons", "railjack_weapons", "upgrades", "arcanes", "avionics",
    "resources", "sentinels", "syndicates", "keys", "gear", "bundles", "booster_packs",
    "customs", "drones", "flavour_items", "focus_upgrades", "fusion_bundles", "intrinsics",
    "mod_sets", "virtuals", "abilities", "achievements", "enemy_avatars",
    "enemy_ai_weapons", "nightwave_rewards",
];

/// 前缀 → worldstate_enums.category 分派表
const ENUM_PREFIX_MAP: &[(&str, &str)] = &[
    ("MT_",                  "mission_type"),
    ("FC_",                  "faction"),
    ("SORTIE_BOSS_",         "sortie_boss"),
    ("SORTIE_MODIFIER_",     "sortie_modifier"),
    ("VoidT",                "relic_tier"),
    ("DT_",                  "descent_type"),
    ("NC_",                  "descent_challenge"),
    ("CT_",                  "archimedea_type"),
    ("CD_",                  "archimedea_difficulty"),
    ("CST_",                 "calendar_season"),
    ("CET_",                 "calendar_event_type"),
];

pub struct Resolver<'a> {
    pool: &'a PgPool,
    pub lang: String,
    tag_cache: HashMap<String, Option<String>>,
    enum_cache: HashMap<String, Option<String>>,
}

/// 奖励表展开行
#[derive(sqlx::FromRow)]
struct DeckItemRow {
    tier_index: i32,
    slot: i32,
    item_type: String,
    item_count: i32,
    probability: Option<f64>,
    rarity: Option<String>,
}

impl<'a> Resolver<'a> {
    pub fn new(pool: &'a PgPool, lang: String) -> Self {
        Self { pool, lang, tag_cache: HashMap::new(), enum_cache: HashMap::new() }
    }

    /// loc tag → 译文（带缓存）
    pub async fn loc(&mut self, tag: &str) -> Option<String> {
        if let Some(v) = self.tag_cache.get(tag) {
            return v.clone();
        }
        let row: Option<(Option<String>,)> =
            sqlx::query_as("SELECT value FROM localizations WHERE loc_tag = $1 AND lang = $2")
                .bind(tag).bind(&self.lang).fetch_optional(self.pool).await.ok().flatten();
        let v = row.and_then(|r| r.0);
        self.tag_cache.insert(tag.to_string(), v.clone());
        v
    }

    /// 枚举（worldstate_enums）→ loc tag → 译文
    pub async fn enum_name(&mut self, category: &str, code: &str) -> Option<String> {
        let key = format!("{category}|{code}");
        if let Some(v) = self.enum_cache.get(&key) {
            return v.clone();
        }
        let tag: Option<(Option<String>,)> = sqlx::query_as(
            "SELECT name_loc FROM worldstate_enums WHERE category = $1 AND enum_code = $2")
            .bind(category).bind(code).fetch_optional(self.pool).await.ok().flatten();
        let v = match tag.and_then(|t| t.0) {
            Some(t) => self.loc(&t).await,
            None => None,
        };
        self.enum_cache.insert(key, v.clone());
        v
    }

    /// 节点 ID → regions 查询
    /// 枚举描述查询（worldstate_enums.description）
    pub async fn enum_desc(&mut self, category: &str, code: &str) -> Option<String> {
        let row: Option<(Option<String>,)> = sqlx::query_as(
            "SELECT description FROM worldstate_enums WHERE category = $1 AND enum_code = $2")
            .bind(category).bind(code).fetch_optional(self.pool).await.ok().flatten();
        row.and_then(|r| r.0).filter(|s| !s.is_empty())
    }
    pub async fn node(&mut self, id: &str) -> Option<NodeRef> {
        let row: Option<(String,)> =
            sqlx::query_as("SELECT COALESCE(name_loc, '') FROM regions WHERE unique_name = $1")
                .bind(id).fetch_optional(self.pool).await.ok().flatten();
        match row {
            Some((tag,)) if !tag.is_empty() => {
                let name = self.loc(&tag).await.unwrap_or_else(|| id.to_string());
                Some(NodeRef { r#type: id.to_string(), name })
            }
            _ => Some(NodeRef { r#type: id.to_string(), name: id.to_string() }),
        }
    }

    /// 物品路径 → (entity_type, 名称)
    pub async fn item(&mut self, path: &str) -> Option<(String, Option<String>)> {
        for cand in path_variants(path) {
            for table in ENTITY_TABLES {
                let q = format!("SELECT name_loc FROM {table} WHERE unique_name = $1 LIMIT 1");
                let row: Option<(Option<String>,)> =
                    sqlx::query_as(&q).bind(&cand).fetch_optional(self.pool).await.ok().flatten();
                if let Some((Some(tag),)) = row {
                    let name = self.loc(&tag).await;
                    return Some(((*table).to_string(), name));
                }
            }
        }
        None
    }

    /// 统一解析入口：前缀匹配 → worldstate_enums 表查询
    pub async fn resolve(&mut self, value: &str) -> Resolved {
        let v = value.trim();
        if v.is_empty() {
            return Resolved { code: value.to_string(), name: None, detail: None, translated: false };
        }
        // 1) loc tag
        if v.starts_with("/Lotus/Language/") || v.starts_with("/EE/Language/") {
            let name = self.loc(v).await;
            let code = v.rsplit('/').next().unwrap_or(v).to_string();
            let translated = name.as_ref().is_some();
            return Resolved { code, name, detail: None, translated };
        }
        // 2) 枚举前缀 → worldstate_enums
        for (prefix, category) in ENUM_PREFIX_MAP {
            if v.starts_with(prefix) {
                let name = self.enum_name(category, v).await;
                let translated = name.as_ref().is_some();
                return Resolved { code: v.to_string(), name, detail: None, translated };
            }
        }
        // 3) 节点 ID
        if is_node_id(v) {
            if let Some(n) = self.node(v).await {
                return Resolved {
                    code: n.r#type.clone(), name: Some(n.name.clone()),
                    detail: Some(json!({ "type": n.r#type, "name": n.name })), translated: true,
                };
            }
        }
        // 4) 物品路径
        if v.starts_with("/Lotus/") {
            if let Some((_t, name)) = self.item(v).await {
                let translated = name.is_some();
                return Resolved {
                    code: v.to_string(), name, detail: None, translated,
                };
            }
            return Resolved { code: v.to_string(), name: None, detail: None, translated: false };
        }
        // 5) 其他：原样
        Resolved { code: v.to_string(), name: None, detail: None, translated: false }
    }

    /// 奖励表 deck 展开（形态 B）→ tier 分组条目
    pub async fn expand_deck(&mut self, deck: &str) -> Result<Option<Vec<TierRewards>>, ApiError> {
        let exists: Option<(i32,)> =
            sqlx::query_as("SELECT 1 FROM mission_reward_decks WHERE unique_name = $1")
                .bind(deck).fetch_optional(self.pool).await?;
        if exists.is_none() {
            return Ok(None);
        }
        let rows: Vec<DeckItemRow> = sqlx::query_as(
            "SELECT t.tier_index, i.slot, i.type AS item_type, i.item_count, i.probability, i.rarity
             FROM mission_reward_decks d
             JOIN mission_reward_tiers t ON t.deck_unique_name = d.unique_name
             JOIN mission_reward_items i ON i.tier_id = t.tier_id
             WHERE d.unique_name = $1 ORDER BY t.tier_index, i.slot")
            .bind(deck).fetch_all(self.pool).await?;

        let mut out: Vec<TierRewards> = Vec::new();
        for r in rows {
            let item_name = self.resolve_item_name(&r.item_type).await;
            if let Some(t) = out.last_mut() {
                if t.tier == r.tier_index as i64 {
                    t.items.push(RewardItem {
                        r#type: r.item_type, item_count: r.item_count as i64,
                        item_name, probability: r.probability, rarity: r.rarity,
                        translated: true,
                    });
                    continue;
                }
            }
            out.push(TierRewards {
                tier: r.tier_index as i64,
                items: vec![RewardItem {
                    r#type: r.item_type, item_count: r.item_count as i64, item_name,
                    probability: r.probability, rarity: r.rarity, translated: true,
                }],
            });
        }
        Ok(Some(out))
    }

    /// 奖励条目物品名（带 StoreItems 前缀归一）
    pub async fn resolve_item_name(&mut self, path: &str) -> Option<String> {
        self.item(path).await.and_then(|(_, name)| name)
    }
}

fn is_node_id(v: &str) -> bool {
    v.starts_with("SolNode") || v.starts_with("CrewBattleNode")
        || v.starts_with("ClanNode") || v.ends_with("HUB")
}

/// 物品路径变体（处理 /Lotus/StoreItems 前缀差异）
pub fn path_variants(p: &str) -> Vec<String> {
    let mut out = vec![p.to_string()];
    if let Some(rest) = p.strip_prefix("/Lotus/StoreItems/") {
        out.push(format!("/Lotus/{rest}"));
        out.push(format!("/{rest}"));
    } else if let Some(rest) = p.strip_prefix("/Lotus/Types/StoreItems/") {
        out.push(format!("/Lotus/StoreItems/{rest}"));
        out.push(format!("/Lotus/Types/{rest}"));
    }
    out
}

/// 供其他模块使用的物品名解析（独立 Resolver 便捷包装）
pub async fn item_name(pool: &PgPool, lang: &str, path: &str) -> Option<String> {
    let mut r = Resolver::new(pool, lang.to_string());
    r.item(path).await.and_then(|(_, n)| n)
}

// 供 routes 使用：把 Resolved 转为 json 值
pub fn resolved_json(r: &Resolved) -> Value {
    json!({
        "code": r.code,
        "name": r.name,
        "detail": r.detail,
        "translated": r.translated,
    })
}
