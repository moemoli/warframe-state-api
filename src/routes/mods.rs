//! GET /api/mods —— Mod 查询

use axum::extract::{Path, Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::FromRow;

use crate::error::ApiError;
use crate::worldstate::resolve::Resolver;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct ModParams {
    lang: Option<String>,
    r#type: Option<String>,
    name: Option<String>,
    polarity: Option<String>,
    rarity: Option<String>,
    limit: Option<i64>,
    offset: Option<i64>,
}

#[derive(FromRow)]
struct ModRow {
    unique_name: String,
    name: Option<String>,
    #[sqlx(rename = "type")]
    mod_type: Option<String>,
    polarity: Option<String>,
    rarity: Option<String>,
    base_drain: Option<i32>,
    fusion_limit: Option<i32>,
}

pub async fn list(
    State(state): State<AppState>,
    Query(p): Query<ModParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = p.lang.clone().unwrap_or_else(|| state.config.default_lang.clone());
    let limit = p.limit.unwrap_or(20).clamp(1, 100);
    let offset = p.offset.unwrap_or(0).max(0);

    let rows: Vec<ModRow> = sqlx::query_as(
        "SELECT unique_name, loc(name_loc, $1) AS name, type, polarity, rarity,
                base_drain, fusion_limit
         FROM upgrades
         WHERE ($2::text IS NULL OR type = $2)
           AND ($3::text IS NULL OR polarity = $3)
           AND ($4::text IS NULL OR rarity = $4)
           AND ($5::text IS NULL OR loc(name_loc, $1) ILIKE '%' || $5 || '%')
         ORDER BY name NULLS LAST, unique_name
         LIMIT $6 OFFSET $7",
    )
    .bind(&lang)
    .bind(p.r#type)
    .bind(p.polarity)
    .bind(p.rarity)
    .bind(p.name)
    .bind(limit)
    .bind(offset)
    .fetch_all(&state.pool)
    .await?;

    let items: Vec<Value> = rows
        .into_iter()
        .map(|r| {
            json!({
                "unique_name": r.unique_name,
                "name": r.name,
                "type": r.mod_type,
                "polarity": r.polarity,
                "rarity": r.rarity,
                "base_drain": r.base_drain,
                "fusion_limit": r.fusion_limit,
            })
        })
        .collect();
    Ok(Json(json!({ "mods": items, "total": items.len(), "limit": limit, "offset": offset })))
}

pub async fn detail(
    State(state): State<AppState>,
    Path(unique_name): Path<String>,
    Query(p): Query<ModParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = p.lang.clone().unwrap_or_else(|| state.config.default_lang.clone());
    let row: Option<ModRow> = sqlx::query_as(
        "SELECT unique_name, loc(name_loc, $1) AS name, type, polarity, rarity,
                base_drain, fusion_limit
         FROM upgrades WHERE unique_name = $2",
    )
    .bind(&lang)
    .bind(&unique_name)
    .fetch_optional(&state.pool)
    .await?;
    let Some(row) = row else {
        return Err(ApiError::NotFound(format!("未找到 Mod: {unique_name}")));
    };

    let mut res = Resolver::new(&state.pool, lang.clone());

    let tags: Vec<String> = sqlx::query_scalar(
        "SELECT tag FROM upgrade_compatibility_tags WHERE upgrade_unique_name = $1 ORDER BY tag",
    )
    .bind(&unique_name)
    .fetch_all(&state.pool)
    .await?;

    // 词条
    #[derive(FromRow)]
    struct EntryRow {
        slot: i32,
        tag: Option<String>,
        prefix_tag_loc: Option<String>,
        suffix_tag_loc: Option<String>,
    }
    let entries: Vec<EntryRow> = sqlx::query_as(
        "SELECT slot, tag, prefix_tag_loc, suffix_tag_loc
         FROM upgrade_entries WHERE upgrade_unique_name = $1 ORDER BY slot",
    )
    .bind(&unique_name)
    .fetch_all(&state.pool)
    .await?;
    let mut entry_out = vec![];
    for e in entries {
        let prefix = if let Some(t) = e.prefix_tag_loc.as_deref() { res.loc(t).await } else { None };
        let suffix = if let Some(t) = e.suffix_tag_loc.as_deref() { res.loc(t).await } else { None };
        let values: Vec<(i32, f64, Option<String>, Option<bool>)> = sqlx::query_as(
            "SELECT slot, value, loc_tag, reverse_value_symbol
             FROM upgrade_entry_values WHERE entry_id IN
               (SELECT entry_id FROM upgrade_entries WHERE upgrade_unique_name = $1 AND slot = $2)
             ORDER BY slot",
        )
        .bind(&unique_name)
        .bind(e.slot)
        .fetch_all(&state.pool)
        .await?;
        let mut v_out = vec![];
        for (slot, value, loc_tag, reverse) in values {
            let vname = if let Some(t) = loc_tag.as_deref() { res.loc(t).await } else { None };
            v_out.push(json!({ "slot": slot, "value": value, "name": vname, "reverse": reverse }));
        }
        entry_out.push(json!({
            "slot": e.slot, "tag": e.tag, "prefix": prefix, "suffix": suffix, "values": v_out,
        }));
    }

    Ok(Json(json!({
        "unique_name": row.unique_name,
        "name": row.name,
        "type": row.mod_type,
        "polarity": row.polarity,
        "rarity": row.rarity,
        "base_drain": row.base_drain,
        "fusion_limit": row.fusion_limit,
        "compatibility_tags": tags,
        "upgrade_entries": entry_out,
    })))
}
