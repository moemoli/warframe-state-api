//! warframe.market 集成端点
//! - GET /api/wfm/items               物品列表
//! - GET /api/wfm/items/{slug}        物品详情 + 实时价格
//! - GET /api/wfm/rivens              紫卡武器列表
//! - GET /api/wfm/rivens/attributes   紫卡词条列表
//! - GET /api/wfm/rivens/{slug}       紫卡武器详情 + 实时价格
//! - GET /api/wfm/liches              赤毒玄骸武器列表
//! - GET /api/wfm/liches/{slug}       赤毒玄骸武器详情 + 实时价格
//! - GET /api/wfm/sisters             帕尔沃斯姐妹武器列表
//! - GET /api/wfm/sisters/{slug}      姐妹武器详情 + 实时价格

use axum::extract::{Path, Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::error::ApiError;
use crate::state::AppState;

#[derive(Debug, Deserialize)]
pub struct WfmParams {
    lang: Option<String>,
    name: Option<String>,
    r#type: Option<String>,
    limit: Option<i64>,
    offset: Option<i64>,
}

fn lang_of<'a>(state: &'a AppState, p: &'a WfmParams) -> String {
    p.lang.clone().unwrap_or_else(|| state.config.default_lang.clone())
}

// ============================================================
// 通用查询宏（避免重复代码）
// ============================================================

macro_rules! wfm_list_endpoint {
    ($fn_name:ident, $table:ident, $i18n_table:ident, $extra_cols:expr, $extra_where:expr) => {
        pub async fn $fn_name(
            State(state): State<AppState>,
            Query(p): Query<WfmParams>,
        ) -> Result<Json<Value>, ApiError> {
            let lang = lang_of(&state, &p);
            let limit = p.limit.unwrap_or(20).clamp(1, 100);
            let offset = p.offset.unwrap_or(0).max(0);

            let sql = format!(
                "SELECT w.wfm_id, w.slug, w.game_ref, w.icon, w.thumb, i.item_name, {}
                 FROM {} w LEFT JOIN {} i ON i.wfm_id = w.wfm_id AND i.lang = $1
                 WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
                 {}
                 ORDER BY i.item_name NULLS LAST, w.slug LIMIT $3 OFFSET $4",
                $extra_cols, stringify!($table), stringify!($i18n_table), $extra_where
            );

            let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                           Option<String>,)> = sqlx::query_as(&sql)
                .bind(&lang).bind(p.name.as_deref()).bind(limit).bind(offset)
                .fetch_all(&state.pool).await?;

            let items: Vec<Value> = rows.iter().map(|r| json!({
                "wfm_id": r.0, "slug": r.1, "game_ref": r.2,
                "icon": r.3, "thumb": r.4, "item_name": r.5,
            })).collect();

            Ok(Json(json!({ "items": items, "total": items.len(), "limit": limit, "offset": offset })))
        }
    };
}

// ============================================================
// /api/wfm/items —— 可交易物品
// ============================================================

/// GET /api/wfm/items?name=adaptation&lang=zh
pub async fn list(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let limit = p.limit.unwrap_or(20).clamp(1, 100);
    let offset = p.offset.unwrap_or(0).max(0);

    let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                   Option<String>, Option<i32>, Option<i32>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.icon, w.thumb, i.item_name,
                w.ducats, w.trading_tax
         FROM wfm_items w
         LEFT JOIN wfm_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
         ORDER BY i.item_name NULLS LAST, w.slug LIMIT $3 OFFSET $4",
    ).bind(&lang).bind(p.name.as_deref()).bind(limit).bind(offset)
     .fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.iter().map(|r| json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2,
        "icon": r.3, "thumb": r.4, "item_name": r.5,
        "ducats": r.6, "trading_tax": r.7,
    })).collect();

    Ok(Json(json!({ "items": items, "total": items.len(), "limit": limit, "offset": offset })))
}

/// GET /api/wfm/items/{slug}?lang=zh
pub async fn detail(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let row: Option<(String, String, Option<String>, Vec<String>, bool, Option<String>,
                     Option<i32>, Option<i32>, Option<i32>, Option<i32>,
                     Option<String>, Option<String>,
                     Option<String>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.tags, w.tradable, w.rarity,
                w.mod_max_rank, w.mastery_level, w.ducats, w.trading_tax,
                w.icon, w.thumb, i.item_name, i.description, i.wiki_link
         FROM wfm_items w LEFT JOIN wfm_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE w.slug = $2"
    ).bind(&lang).bind(&slug).fetch_optional(&state.pool).await?;

    let Some(r) = row else { return Err(ApiError::NotFound(format!("未找到: {slug}"))); };
    let prices = fetch_wfm_top_orders("item", &slug).await.unwrap_or(json!(null));

    Ok(Json(json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2, "tags": r.3, "tradable": r.4,
        "rarity": r.5, "mod_max_rank": r.6, "mastery_level": r.7,
        "ducats": r.8, "trading_tax": r.9, "icon": r.10, "thumb": r.11,
        "item_name": r.12, "description": r.13, "wiki_link": r.14, "prices": prices,
    })))
}

// ============================================================
// /api/wfm/rivens —— 紫卡武器
// ============================================================

/// GET /api/wfm/rivens?name=rubico&type=rifle&lang=zh
pub async fn riven_list(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let limit = p.limit.unwrap_or(20).clamp(1, 100);
    let offset = p.offset.unwrap_or(0).max(0);

    let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                   Option<String>, Option<String>, Option<f32>, Option<i32>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.riven_type, w.\"group\",
                w.icon, w.thumb, w.disposition, w.mastery_level
         FROM wfm_riven_items w
         LEFT JOIN wfm_riven_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
           AND ($3::text IS NULL OR w.riven_type = $3)
         ORDER BY i.item_name NULLS LAST, w.slug LIMIT $4 OFFSET $5",
    ).bind(&lang).bind(p.name.as_deref()).bind(p.r#type.as_deref())
     .bind(limit).bind(offset).fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.iter().map(|r| json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2, "riven_type": r.3, "group": r.4,
        "icon": r.5, "thumb": r.6, "disposition": r.7, "mastery_level": r.8,
    })).collect();

    Ok(Json(json!({ "items": items, "total": items.len(), "limit": limit, "offset": offset })))
}

/// GET /api/wfm/rivens/attributes?lang=zh
pub async fn riven_attr_list(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                   Option<String>, Vec<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.prefix, w.suffix, w.units, w.\"group\",
                w.exclusive_to, i.effect
         FROM wfm_riven_attributes w
         LEFT JOIN wfm_riven_attr_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         ORDER BY i.effect NULLS LAST, w.slug",
    ).bind(&lang).fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.iter().map(|r| json!({
        "wfm_id": r.0, "slug": r.1, "prefix": r.2, "suffix": r.3,
        "units": r.4, "group": r.5, "exclusive_to": r.6, "effect": r.7,
    })).collect();

    Ok(Json(json!({ "attributes": items, "total": items.len() })))
}

/// GET /api/wfm/rivens/{slug}?lang=zh
pub async fn riven_detail(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let row: Option<(String, String, Option<String>, Option<String>, Option<String>,
                     Option<f32>, Option<i32>, Option<String>, Option<String>,
                     Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.riven_type, w.\"group\",
                w.disposition, w.mastery_level, w.icon, w.thumb,
                i.item_name, i.wiki_link
         FROM wfm_riven_items w LEFT JOIN wfm_riven_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE w.slug = $2"
    ).bind(&lang).bind(&slug).fetch_optional(&state.pool).await?;

    let Some(r) = row else { return Err(ApiError::NotFound(format!("未找到紫卡武器: {slug}"))); };
    let prices = fetch_wfm_top_orders("riven/weapon", &slug).await.unwrap_or(json!(null));

    Ok(Json(json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2, "riven_type": r.3, "group": r.4,
        "disposition": r.5, "mastery_level": r.6, "icon": r.7, "thumb": r.8,
        "item_name": r.9, "wiki_link": r.10, "prices": prices,
    })))
}

// ============================================================
// /api/wfm/liches —— 赤毒玄骸武器
// ============================================================

/// GET /api/wfm/liches?name=kuva&lang=zh
pub async fn lich_list(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let limit = p.limit.unwrap_or(20).clamp(1, 100);
    let offset = p.offset.unwrap_or(0).max(0);

    let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                   Option<String>, Option<i32>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.icon, w.thumb, i.item_name, w.mastery_level
         FROM wfm_lich_weapons w
         LEFT JOIN wfm_lich_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
         ORDER BY i.item_name NULLS LAST, w.slug LIMIT $3 OFFSET $4",
    ).bind(&lang).bind(p.name.as_deref()).bind(limit).bind(offset)
     .fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.iter().map(|r| json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2,
        "icon": r.3, "thumb": r.4, "item_name": r.5, "mastery_level": r.6,
    })).collect();

    Ok(Json(json!({ "items": items, "total": items.len(), "limit": limit, "offset": offset })))
}

/// GET /api/wfm/liches/{slug}?lang=zh
pub async fn lich_detail(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let row: Option<(String, String, Option<String>, Option<i32>,
                     Option<String>, Option<String>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.mastery_level,
                w.icon, w.thumb, i.item_name, i.wiki_link
         FROM wfm_lich_weapons w LEFT JOIN wfm_lich_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE w.slug = $2"
    ).bind(&lang).bind(&slug).fetch_optional(&state.pool).await?;

    let Some(r) = row else { return Err(ApiError::NotFound(format!("未找到赤毒武器: {slug}"))); };
    let prices = fetch_wfm_top_orders("lich/weapon", &slug).await.unwrap_or(json!(null));

    Ok(Json(json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2, "mastery_level": r.3,
        "icon": r.4, "thumb": r.5, "item_name": r.6, "wiki_link": r.7, "prices": prices,
    })))
}

// ============================================================
// /api/wfm/sisters —— 帕尔沃斯姐妹武器
// ============================================================

/// GET /api/wfm/sisters?name=tenet&lang=zh
pub async fn sister_list(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let limit = p.limit.unwrap_or(20).clamp(1, 100);
    let offset = p.offset.unwrap_or(0).max(0);

    let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                   Option<String>, Option<i32>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.icon, w.thumb, i.item_name, w.mastery_level
         FROM wfm_sister_weapons w
         LEFT JOIN wfm_sister_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
         ORDER BY i.item_name NULLS LAST, w.slug LIMIT $3 OFFSET $4",
    ).bind(&lang).bind(p.name.as_deref()).bind(limit).bind(offset)
     .fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.iter().map(|r| json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2,
        "icon": r.3, "thumb": r.4, "item_name": r.5, "mastery_level": r.6,
    })).collect();

    Ok(Json(json!({ "items": items, "total": items.len(), "limit": limit, "offset": offset })))
}

/// GET /api/wfm/sisters/{slug}?lang=zh
pub async fn sister_detail(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let row: Option<(String, String, Option<String>, Option<i32>,
                     Option<String>, Option<String>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.mastery_level,
                w.icon, w.thumb, i.item_name, i.wiki_link
         FROM wfm_sister_weapons w LEFT JOIN wfm_sister_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE w.slug = $2"
    ).bind(&lang).bind(&slug).fetch_optional(&state.pool).await?;

    let Some(r) = row else { return Err(ApiError::NotFound(format!("未找到姐妹武器: {slug}"))); };
    let prices = fetch_wfm_top_orders("sister/weapon", &slug).await.unwrap_or(json!(null));

    Ok(Json(json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2, "mastery_level": r.3,
        "icon": r.4, "thumb": r.5, "item_name": r.6, "wiki_link": r.7, "prices": prices,
    })))
}

// ============================================================
// 通用：从 warframe.market API 获取最优买卖订单
// ============================================================

async fn fetch_wfm_top_orders(endpoint: &str, slug: &str) -> Result<Value, Box<dyn std::error::Error>> {
    let client = reqwest::Client::builder()
        .user_agent("warframe-api/1.0")
        .timeout(std::time::Duration::from_secs(10))
        .build()?;

    let url = format!("https://api.warframe.market/v2/{}/{}/top", endpoint, slug);
    let resp = client.get(&url)
        .header("Platform", "pc")
        .header("Language", "zh-hans")
        .send().await?;

    if !resp.status().is_success() { return Ok(json!(null)); }

    let body: Value = resp.json().await?;
    let data = body.get("data").cloned().unwrap_or(Value::Null);

    let simplify = |o: &Value| -> Value {
        json!({
            "platinum": o.get("platinum").and_then(|v| v.as_i64()),
            "quantity": o.get("quantity").and_then(|v| v.as_i64()),
            "user": o.get("user").and_then(|u| u.get("ingameName")).and_then(|v| v.as_str()),
            "status": o.get("user").and_then(|u| u.get("status")).and_then(|v| v.as_str()),
        })
    };

    let sell: Vec<Value> = data.get("sell").and_then(|v| v.as_array())
        .map(|a| a.iter().map(simplify).collect()).unwrap_or_default();
    let buy: Vec<Value> = data.get("buy").and_then(|v| v.as_array())
        .map(|a| a.iter().map(simplify).collect()).unwrap_or_default();

    let sell_min = sell.iter().filter_map(|o| o.get("platinum").and_then(|v| v.as_i64())).min();
    let sell_avg = if !sell.is_empty() {
        Some(sell.iter().filter_map(|o| o.get("platinum").and_then(|v| v.as_i64())).sum::<i64>() / sell.len() as i64)
    } else { None };
    let buy_max = buy.iter().filter_map(|o| o.get("platinum").and_then(|v| v.as_i64())).max();

    Ok(json!({
        "sell": { "min": sell_min, "avg": sell_avg, "orders": sell },
        "buy": { "max": buy_max, "orders": buy },
    }))
}
