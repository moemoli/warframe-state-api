//! GET /api/search —— 统一搜索（别名 + 官方库 + warframe.market）

use axum::extract::{Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::aliases;
use crate::error::ApiError;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct SearchParams {
    q: Option<String>,
    lang: Option<String>,
    limit: Option<i64>,
    trade: Option<bool>,
    /// 按来源筛选：逗号分隔 alias/official/wfm/riven/lich/sister（如 source=wfm,riven）
    source: Option<String>,
}

/// GET /api/search?q=血妈&lang=zh&limit=20
///
/// 搜索流程（并行合并，去重）：
///   1. aliases 表 → 精确别名命中
///   2. v_localized → 官方库名称模糊
///   3. wfm_item_i18n + wfm_items → wfm 库名称模糊
///   4. game_ref 关联 → 官方结果补全 wfm 信息
pub async fn search(
    State(state): State<AppState>,
    Query(p): Query<SearchParams>,
) -> Result<Json<Value>, ApiError> {
    let q = p.q.unwrap_or_default();
    let q = q.trim().to_string();
    if q.is_empty() {
        return Err(ApiError::BadRequest("q 不能为空".into()));
    }
    let lang = p.lang.clone().unwrap_or_else(|| state.config.default_lang.clone());
    let limit = p.limit.unwrap_or(20).clamp(1, 50);
    let pool = &state.pool;

    // 1) 别名精确命中
    let alias_hits = aliases::find_alias(pool, &q).await?;
    let mut resolved_alias: Option<String> = None;
    let mut results: Vec<Value> = Vec::new();
    let mut seen = std::collections::HashSet::new();

    if !alias_hits.is_empty() {
        resolved_alias = Some(q.clone());
        for (entity_type, entity_id) in &alias_hits {
            let name = resolve_entity_name(pool, entity_id, &lang).await;
            let wfm = wfm_by_game_ref(pool, entity_id, &lang).await;
            seen.insert(format!("{}:{}", entity_type, entity_id));
            results.push(json!({
                "source": "alias",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "name": name,
                "wfm": wfm,
            }));
        }
    }

    // 2+3) 官方库 + wfm 普通物品 + 紫卡武器 + 赤毒武器 + 姐妹武器 联合搜索
    //      始终执行（别名命中也聚合其余来源），按 source+type+id 去重
    {
        let rows: Vec<(String, String, String, Option<String>, String)> = sqlx::query_as(
            "SELECT source, entity_type, entity_id, wfm_id, name FROM (
                -- 官方库
                SELECT 'official' AS source, entity_type, entity_id,
                       NULL::text AS wfm_id, value AS name
                FROM v_localized
                WHERE lang = $1 AND field = 'name' AND value ILIKE '%' || $2 || '%'
                UNION ALL
                -- wfm 普通物品（名称/别名关联 + 别名基础名→slug 匹配）
                SELECT 'wfm', 'wfm', COALESCE(w.game_ref, ''), w.wfm_id, i.item_name
                FROM wfm_items w
                JOIN wfm_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
                WHERE i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%'
                   OR w.game_ref IN (SELECT entity_id FROM aliases WHERE lower(alias) = lower($2))
                   OR EXISTS (
                       SELECT 1 FROM aliases a
                       WHERE lower(a.alias) = lower($2)
                         AND (
                             -- 战甲目录匹配：/Lotus/Powersuits/<Warframe>/... 取第4段
                             (split_part(a.entity_id, '/', 3) = 'Powersuits'
                              AND split_part(a.entity_id, '/', 4) <> ''
                              AND lower(w.game_ref) LIKE '%/powersuits/' || lower(split_part(a.entity_id, '/', 4)) || '/%')
                             OR
                             -- 路径末段 → slug 匹配（兜底）
                             (lower(split_part(a.entity_id, '/', -1)) <> ''
                              AND w.slug LIKE '%' || lower(split_part(a.entity_id, '/', -1)) || '%')
                         )
                   )
                UNION ALL
                -- 紫卡武器
                SELECT 'riven', 'riven_weapon', w.slug, w.wfm_id, i.item_name
                FROM wfm_riven_items w
                JOIN wfm_riven_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
                WHERE i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%'
                UNION ALL
                -- 赤毒玄骸武器
                SELECT 'lich', 'lich_weapon', w.slug, w.wfm_id, i.item_name
                FROM wfm_lich_weapons w
                JOIN wfm_lich_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
                WHERE i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%'
                UNION ALL
                -- 帕尔沃斯姐妹武器
                SELECT 'sister', 'sister_weapon', w.slug, w.wfm_id, i.item_name
                FROM wfm_sister_weapons w
                JOIN wfm_sister_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
                WHERE i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%'
             ) sub
             ORDER BY name NULLS LAST
             LIMIT $3",
        )
        .bind(&lang)
        .bind(&q)
        .bind(limit)
        .fetch_all(pool)
        .await?;

        for (source, entity_type, entity_id, wfm_id, name) in rows {
            let key = format!("{source}:{entity_type}:{entity_id}");
            if !seen.insert(key) {
                continue;
            }
            let wfm = match source.as_str() {
                "riven" => {
                    if let Some(ref wid) = wfm_id {
                        riven_detail_by_id(pool, wid, &lang).await
                    } else { Value::Null }
                }
                "lich" => {
                    if let Some(ref wid) = wfm_id {
                        lich_detail_by_id(pool, wid, &lang).await
                    } else { Value::Null }
                }
                "sister" => {
                    if let Some(ref wid) = wfm_id {
                        sister_detail_by_id(pool, wid, &lang).await
                    } else { Value::Null }
                }
                "wfm" => {
                    if let Some(ref wid) = wfm_id {
                        wfm_by_wfm_id(pool, wid, &lang).await
                    } else { Value::Null }
                }
                _ => wfm_by_game_ref(pool, &entity_id, &lang).await,
            };
            results.push(json!({
                "source": source,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "name": name,
                "wfm": wfm,
            }));
        }
    }

    // 热度统计：首个含游戏内路径的结果计一次（排行数据源）
    if let Some(first) = results.first() {
        if let Some(eid) = first.get("entity_id").and_then(|v| v.as_str()) {
            if eid.starts_with("/Lotus") {
                let etype = first.get("entity_type").and_then(|v| v.as_str()).unwrap_or("other");
                let _ = sqlx::query(
                    "INSERT INTO api_query_stats (entity_type, entity_id, hits) VALUES ($1,$2,1)
                     ON CONFLICT (entity_type, entity_id) DO UPDATE SET hits = api_query_stats.hits + 1, last_at = now()")
                    .bind(etype).bind(eid).execute(pool).await;
            }
        }
    }

    // source= 筛选：仅保留指定来源（逗号分隔多值）
    if let Some(src) = p.source.as_deref() {
        let allow: Vec<&str> = src.split(',').map(|x| x.trim()).filter(|x| !x.is_empty()).collect();
        if !allow.is_empty() {
            results.retain(|r| {
                r.get("source").and_then(|v| v.as_str())
                    .map(|s| allow.contains(&s))
                    .unwrap_or(false)
            });
        }
    }

    // trade=true 时过滤掉无 wfm 数据的结果
    if p.trade.unwrap_or(false) {
        results.retain(|r| {
            r.get("wfm").map_or(false, |w| !w.is_null())
        });
    }

    if results.is_empty() {
        return Err(ApiError::NotFound(format!("未找到: {q}")));
    }

    Ok(Json(json!({
        "query": q,
        "resolved_alias": resolved_alias,
        "count": results.len(),
        "results": results,
    })))
}

/// 通过 game_ref 查 wfm 数据
async fn wfm_by_game_ref(pool: &PgPool, game_ref: &str, lang: &str) -> Value {
    let row: Option<(String, String, Vec<String>, bool, Option<String>,
                     Option<i32>, Option<i32>, Option<String>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.tags, w.tradable, w.rarity,
                w.ducats, w.trading_tax, i.item_name, i.description, i.wiki_link
         FROM wfm_items w
         LEFT JOIN wfm_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $2
         WHERE w.game_ref = $1 LIMIT 1",
    )
    .bind(game_ref)
    .bind(lang)
    .fetch_optional(pool)
    .await.ok().flatten();

    match row {
        Some((id, slug, tags, tradable, rarity, ducats, tax, name, desc, wiki)) => json!({
            "wfm_id": id, "slug": slug, "tags": tags, "tradable": tradable,
            "rarity": rarity, "ducats": ducats, "trading_tax": tax,
            "item_name": name, "description": desc, "wiki_link": wiki,
        }),
        None => Value::Null,
    }
}

/// 通过 wfm_id 查 wfm 数据
async fn wfm_by_wfm_id(pool: &PgPool, wfm_id: &str, lang: &str) -> Value {
    let row: Option<(String, String, Option<String>, Vec<String>, bool,
                     Option<String>, Option<i32>, Option<i32>,
                     Option<String>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.tags, w.tradable, w.rarity,
                w.ducats, w.trading_tax, i.item_name, i.description, i.wiki_link
         FROM wfm_items w
         LEFT JOIN wfm_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $2
         WHERE w.wfm_id = $1 LIMIT 1",
    )
    .bind(wfm_id)
    .bind(lang)
    .fetch_optional(pool)
    .await.ok().flatten();

    match row {
        Some((id, slug, game_ref, tags, tradable, rarity, ducats, tax, name, desc, wiki)) => json!({
            "wfm_id": id, "slug": slug, "game_ref": game_ref,
            "tags": tags, "tradable": tradable, "rarity": rarity,
            "ducats": ducats, "trading_tax": tax,
            "item_name": name, "description": desc, "wiki_link": wiki,
        }),
        None => Value::Null,
    }
}

/// 解析实体名称（通过 entity_id 在各实体表中查找 name_loc）
async fn resolve_entity_name(pool: &PgPool, entity_id: &str, lang: &str) -> Option<String> {
    let row: Option<(String,)> = sqlx::query_as(
        "SELECT value FROM v_localized WHERE entity_id = $1 AND lang = $2 AND field = 'name' LIMIT 1",
    )
    .bind(entity_id)
    .bind(lang)
    .fetch_optional(pool)
    .await.ok().flatten();
    row.map(|(v,)| v)
}

/// 紫卡武器详情
async fn riven_detail_by_id(pool: &PgPool, wfm_id: &str, lang: &str) -> Value {
    let row: Option<(String, String, Option<String>, Option<String>, Option<f32>,
                     Option<i32>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.riven_type, w.\"group\", w.disposition,
                w.mastery_level, i.item_name, i.wiki_link
         FROM wfm_riven_items w
         LEFT JOIN wfm_riven_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $2
         WHERE w.wfm_id = $1 LIMIT 1",
    ).bind(wfm_id).bind(lang).fetch_optional(pool).await.ok().flatten();

    match row {
        Some((id, slug, riven_type, group, disp, mastery, name, wiki)) => json!({
            "wfm_id": id, "slug": slug, "riven_type": riven_type, "group": group,
            "disposition": disp, "mastery_level": mastery, "item_name": name,
            "wiki_link": wiki,
        }),
        None => Value::Null,
    }
}

/// 赤毒武器详情
async fn lich_detail_by_id(pool: &PgPool, wfm_id: &str, lang: &str) -> Value {
    let row: Option<(String, String, Option<i32>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.mastery_level, i.item_name, i.wiki_link
         FROM wfm_lich_weapons w
         LEFT JOIN wfm_lich_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $2
         WHERE w.wfm_id = $1 LIMIT 1",
    ).bind(wfm_id).bind(lang).fetch_optional(pool).await.ok().flatten();

    match row {
        Some((id, slug, mastery, name, wiki)) => json!({
            "wfm_id": id, "slug": slug, "mastery_level": mastery, "item_name": name,
            "wiki_link": wiki,
        }),
        None => Value::Null,
    }
}

/// 姐妹武器详情
async fn sister_detail_by_id(pool: &PgPool, wfm_id: &str, lang: &str) -> Value {
    let row: Option<(String, String, Option<i32>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.mastery_level, i.item_name, i.wiki_link
         FROM wfm_sister_weapons w
         LEFT JOIN wfm_sister_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $2
         WHERE w.wfm_id = $1 LIMIT 1",
    ).bind(wfm_id).bind(lang).fetch_optional(pool).await.ok().flatten();

    match row {
        Some((id, slug, mastery, name, wiki)) => json!({
            "wfm_id": id, "slug": slug, "mastery_level": mastery, "item_name": name,
            "wiki_link": wiki,
        }),
        None => Value::Null,
    }
}
