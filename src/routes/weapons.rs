//! GET /api/weapons —— 武器列表 / 详情 / 紫卡倾向

use axum::extract::{Path, Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::FromRow;

use crate::error::ApiError;
use crate::worldstate::resolve::Resolver;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct WeaponParams {
    lang: Option<String>,
    category: Option<String>,
    name: Option<String>,
    limit: Option<i64>,
    offset: Option<i64>,
}

#[derive(FromRow)]
struct WeaponRow {
    unique_name: String,
    name: Option<String>,
    description: Option<String>,
    product_category: Option<String>,
    holster_category: Option<String>,
    mastery_req: Option<i32>,
    slot: Option<i32>,
    trigger: Option<String>,
    noise: Option<String>,
    critical_chance: Option<f64>,
    critical_multiplier: Option<f64>,
    proc_chance: Option<f64>,
    fire_rate: Option<f64>,
    multishot: Option<f64>,
    magazine_size: Option<i32>,
    reload_time: Option<f64>,
    accuracy: Option<f64>,
    omega_attenuation: Option<f64>,
    prime_omega_attenuation: Option<f64>,
    total_damage: Option<f64>,
    range: Option<f64>,
    combo_duration: Option<i32>,
    follow_through: Option<f64>,
    blocking_angle: Option<i32>,
}

pub async fn list(
    State(state): State<AppState>,
    Query(p): Query<WeaponParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = p.lang.clone().unwrap_or_else(|| state.config.default_lang.clone());
    let limit = p.limit.unwrap_or(20).clamp(1, 100);
    let offset = p.offset.unwrap_or(0).max(0);

    let rows: Vec<WeaponRow> = sqlx::query_as(
        "SELECT unique_name, loc(name_loc, $1) AS name, loc(description_loc, $1) AS description,
                product_category, holster_category, mastery_req, slot, trigger, noise,
                critical_chance, critical_multiplier, proc_chance, fire_rate, multishot,
                magazine_size, reload_time, accuracy, omega_attenuation, prime_omega_attenuation,
                total_damage, range, combo_duration, follow_through, blocking_angle
         FROM weapons
         WHERE ($2::text IS NULL OR product_category = $2)
           AND ($3::text IS NULL OR loc(name_loc, $1) ILIKE '%' || $3 || '%')
         ORDER BY name NULLS LAST, unique_name
         LIMIT $4 OFFSET $5",
    )
    .bind(&lang)
    .bind(p.category)
    .bind(p.name)
    .bind(limit)
    .bind(offset)
    .fetch_all(&state.pool)
    .await?;

    let items: Vec<Value> = rows.into_iter().map(|r| weapon_basic_json(r)).collect();
    Ok(Json(json!({ "weapons": items, "total": items.len(), "limit": limit, "offset": offset })))
}

pub async fn detail(
    State(state): State<AppState>,
    Path(name): Path<String>,
    Query(p): Query<WeaponParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = p.lang.clone().unwrap_or_else(|| state.config.default_lang.clone());
    let row: Option<WeaponRow> = sqlx::query_as(
        "SELECT unique_name, loc(name_loc, $1) AS name, loc(description_loc, $1) AS description,
                product_category, holster_category, mastery_req, slot, trigger, noise,
                critical_chance, critical_multiplier, proc_chance, fire_rate, multishot,
                magazine_size, reload_time, accuracy, omega_attenuation, prime_omega_attenuation,
                total_damage, range, combo_duration, follow_through, blocking_angle
         FROM weapons
         WHERE unique_name = $2 OR loc(name_loc, $1) = $2",
    )
    .bind(&lang)
    .bind(&name)
    .fetch_optional(&state.pool)
    .await?;
    let Some(row) = row else {
        return Err(ApiError::NotFound(format!("未找到武器: {name}")));
    };
    let un = row.unique_name.clone();
    let _ = sqlx::query(
        "INSERT INTO api_query_stats (entity_type, entity_id, hits) VALUES ('weapons',$1,1)
         ON CONFLICT (entity_type, entity_id) DO UPDATE SET hits = api_query_stats.hits + 1, last_at = now()")
        .bind(&un).execute(&state.pool).await;
    let mut res = Resolver::new(&state.pool, lang.clone());

    // 伤害分量
    let damage_per_shot: Vec<(i32, f64)> =
        sqlx::query_as("SELECT slot, value FROM weapon_damage_per_shot WHERE weapon_unique_name = $1 ORDER BY slot")
            .bind(&un).fetch_all(&state.pool).await?;

    // 兼容标签
    let tags: Vec<String> = sqlx::query_scalar(
        "SELECT tag FROM weapon_compatibility_tags WHERE weapon_unique_name = $1 ORDER BY tag")
        .bind(&un).fetch_all(&state.pool).await?;

    // behaviours（slot, path, damage_type, value → 嵌套 JSON）
    let bh: Vec<(i32, Option<String>)> =
        sqlx::query_as("SELECT slot, state_name_loc FROM weapon_behaviours WHERE weapon_unique_name = $1 ORDER BY slot")
            .bind(&un).fetch_all(&state.pool).await?;
    let dmg: Vec<(i32, String, String, f64)> = sqlx::query_as(
        "SELECT b.slot, d.path, d.damage_type, d.value
         FROM weapon_behaviour_damage d
         JOIN weapon_behaviours b ON b.behaviour_id = d.behaviour_id
         WHERE b.weapon_unique_name = $1 ORDER BY b.slot",
    )
    .bind(&un).fetch_all(&state.pool).await?;

    let mut behaviours: Vec<Value> = vec![];
    for (slot, state_loc) in bh {
        let state_name = state_loc.as_deref().map(|t| res.loc(t));
        let state_name = match state_name { Some(f) => f.await, None => None };
        let mut tree: serde_json::Map<String, Value> = serde_json::Map::new();
        for (dslot, path, dtype, value) in &dmg {
            if *dslot != slot {
                continue;
            }
            insert_path(&mut tree, &path.split('.').collect::<Vec<_>>(), dtype, *value);
        }
        behaviours.push(json!({ "slot": slot, "state_name": state_name, "damage": tree }));
    }

    let mut out = weapon_basic_json(row);
    out["damage_per_shot"] = json!(damage_per_shot.into_iter().map(|(s, v)| json!({ "slot": s, "value": v })).collect::<Vec<_>>());
    out["compatibility_tags"] = json!(tags);
    out["behaviours"] = json!(behaviours);
    Ok(Json(out))
}

/// GET /api/weapons/{name}/riven —— 紫卡倾向
pub async fn riven(
    State(state): State<AppState>,
    Path(name): Path<String>,
    Query(p): Query<WeaponParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = p.lang.clone().unwrap_or_else(|| state.config.default_lang.clone());
    let row: Option<(String, Option<String>, Option<f64>, Option<f64>)> = sqlx::query_as(
        "SELECT unique_name, loc(name_loc, $1), omega_attenuation, prime_omega_attenuation
         FROM weapons WHERE unique_name = $2 OR loc(name_loc, $1) = $2",
    )
    .bind(&lang)
    .bind(&name)
    .fetch_optional(&state.pool)
    .await?;
    let Some((un, name_zh, omega, prime_omega)) = row else {
        return Err(ApiError::NotFound(format!("未找到武器: {name}")));
    };
    let _ = sqlx::query(
        "INSERT INTO api_query_stats (entity_type, entity_id, hits) VALUES ('weapons',$1,1)
         ON CONFLICT (entity_type, entity_id) DO UPDATE SET hits = api_query_stats.hits + 1, last_at = now()")
        .bind(&un).execute(&state.pool).await;

    Ok(Json(json!({
        "weapon": un,
        "name": name_zh,
        "omega_attenuation": omega,
        "prime_omega_attenuation": prime_omega,
    })))
}

fn weapon_basic_json(r: WeaponRow) -> Value {
    json!({
        "unique_name": r.unique_name,
        "name": r.name,
        "description": r.description,
        "product_category": r.product_category,
        "holster_category": r.holster_category,
        "mastery_req": r.mastery_req,
        "slot": r.slot,
        "trigger": r.trigger,
        "noise": r.noise,
        "critical_chance": r.critical_chance,
        "critical_multiplier": r.critical_multiplier,
        "proc_chance": r.proc_chance,
        "fire_rate": r.fire_rate,
        "multishot": r.multishot,
        "magazine_size": r.magazine_size,
        "reload_time": r.reload_time,
        "accuracy": r.accuracy,
        "omega_attenuation": r.omega_attenuation,
        "prime_omega_attenuation": r.prime_omega_attenuation,
        "total_damage": r.total_damage,
        "range": r.range,
        "combo_duration": r.combo_duration,
        "follow_through": r.follow_through,
        "blocking_angle": r.blocking_angle,
    })
}

/// 把 "projectile.attack" 这类 path 写入嵌套树（递归）
fn insert_path(tree: &mut serde_json::Map<String, Value>, parts: &[&str], damage_type: &str, value: f64) {
    if parts.is_empty() {
        return;
    }
    let (head, rest) = parts.split_first().expect("non-empty");
    let entry = tree.entry((*head).to_string()).or_insert_with(|| json!({}));
    if !entry.is_object() {
        *entry = json!({});
    }
    if rest.is_empty() {
        entry[damage_type] = json!(value);
    } else {
        insert_path(entry.as_object_mut().expect("object"), rest, damage_type, value);
    }
}
