//! GET /api/nodes/{node_type} —— 节点详情（type 直接传 SolNodexxx 精确查询）

use axum::extract::{Path, Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::FromRow;

use crate::error::ApiError;
use crate::worldstate::resolve::Resolver;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct NodeParams {
    lang: Option<String>,
    expand: Option<i8>,
}

#[derive(FromRow)]
struct NodeRow {
    unique_name: String,
    name_loc: Option<String>,
    system_index: Option<i32>,
    system_name_loc: Option<String>,
    mission_name_loc: Option<String>,
    faction_name_loc: Option<String>,
    min_enemy_level: Option<i32>,
    max_enemy_level: Option<i32>,
    mastery_req: Option<i32>,
    node_type: Option<i32>,
}

pub async fn detail(
    State(state): State<AppState>,
    Path(node_type): Path<String>,
    Query(p): Query<NodeParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = p.lang.unwrap_or_else(|| state.config.default_lang.clone());
    let expand = p.expand.unwrap_or(1) != 0;

    let row: Option<NodeRow> = sqlx::query_as(
        "SELECT unique_name, name_loc, system_index, system_name_loc, mission_name_loc,
                faction_name_loc, min_enemy_level, max_enemy_level, mastery_req, node_type
         FROM regions WHERE unique_name = $1",
    )
    .bind(&node_type)
    .fetch_optional(&state.pool)
    .await?;
    let Some(row) = row else {
        return Err(ApiError::NotFound(format!("未找到节点: {node_type}")));
    };

    let mut res = Resolver::new(&state.pool, lang.clone());

    let name = if let Some(t) = row.name_loc.as_deref() { res.loc(t).await } else { None };
    let system = if let Some(t) = row.system_name_loc.as_deref() { res.loc(t).await } else { None };
    let mission_name = if let Some(t) = row.mission_name_loc.as_deref() { res.loc(t).await } else { None };
    let faction_name = if let Some(t) = row.faction_name_loc.as_deref() { res.loc(t).await } else { None };

    // 奖励表（reward_manifests）
    let manifests: Vec<String> = sqlx::query_scalar(
        "SELECT manifest FROM region_reward_manifests WHERE region_unique_name = $1 ORDER BY slot",
    )
    .bind(&node_type)
    .fetch_all(&state.pool)
    .await?;

    let mut rewards: Vec<Value> = vec![];
    for deck in &manifests {
        let tiers = res.expand_deck(deck).await?;
        let deck_name = deck.rsplit('/').next().unwrap_or(deck).to_string();
        let mut obj = json!({ "deck": deck, "deck_name": deck_name });
        if expand {
            obj["tiers"] = match tiers {
                Some(t) => json!(t),
                None => json!([]),
            };
        }
        rewards.push(obj);
    }

    let code_of = |tag: &Option<String>| -> Option<String> {
        tag.as_deref().map(|t| t.rsplit('/').next().unwrap_or(t).to_string())
    };

    Ok(Json(json!({
        "type": row.unique_name,
        "name": name,
        "system": { "index": row.system_index, "name": system },
        "mission_type": {
            "code": code_of(&row.mission_name_loc),
            "name": mission_name,
        },
        "faction": {
            "code": code_of(&row.faction_name_loc),
            "name": faction_name,
        },
        "enemy_levels": { "min": row.min_enemy_level, "max": row.max_enemy_level },
        "mastery_req": row.mastery_req,
        "node_type": row.node_type,
        "reward_manifests": manifests,
        "rewards": rewards,
    })))
}
