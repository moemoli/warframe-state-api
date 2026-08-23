//! GET /api/items/{name} / drops / POST /api/aliases

use axum::extract::{Path, Query, State};
use axum::http::HeaderMap;
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::aliases;
use crate::error::ApiError;
use crate::worldstate::resolve::Resolver;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct ItemParams {
    lang: Option<String>,
}

fn lang_of<'a>(state: &'a AppState, p: &'a ItemParams) -> String {
    p.lang.clone().unwrap_or_else(|| state.config.default_lang.clone())
}

/// GET /api/items/{name} —— 物品查询（支持简写）
pub async fn search(
    State(state): State<AppState>,
    Path(name): Path<String>,
    Query(p): Query<ItemParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let q = name.trim();
    if q.is_empty() {
        return Err(ApiError::BadRequest("name 不能为空".into()));
    }
    let mut results: Vec<Value> = vec![];
    let mut resolved_alias: Option<String> = None;

    // 1) 别名精确（大小写不敏感）
    let alias_hits = aliases::find_alias(&state.pool, q).await?;
    if !alias_hits.is_empty() {
        resolved_alias = Some(q.to_string());
        let mut res = Resolver::new(&state.pool, lang.clone());
        for (entity_type, entity_id) in alias_hits {
            let name = res.item(&entity_id).await.map(|(_, n)| n).flatten();
            results.push(json!({
                "entity_type": entity_type,
                "entity_id": entity_id,
                "name": name,
            }));
        }
    }

    // 2) 名称模糊（v_localized）
    if results.is_empty() {
        let rows: Vec<(String, String, String)> = sqlx::query_as(
            "SELECT entity_type, entity_id, value FROM v_localized
             WHERE lang = $1 AND field = 'name' AND value ILIKE '%' || $2 || '%'
             ORDER BY entity_type, entity_id LIMIT 20",
        )
        .bind(&lang)
        .bind(q)
        .fetch_all(&state.pool)
        .await?;
        for (t, id, n) in rows {
            results.push(json!({ "entity_type": t, "entity_id": id, "name": n }));
        }
    }

    if results.is_empty() {
        return Err(ApiError::NotFound(format!("未找到物品: {q}")));
    }
    Ok(Json(json!({ "query": q, "resolved_alias": resolved_alias, "results": results })))
}

/// GET /api/items/{name}/drops —— 物品掉落/来源聚合
pub async fn drops(
    State(state): State<AppState>,
    Path(name): Path<String>,
    Query(p): Query<ItemParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let mut item_path = name.trim().to_string();
    if item_path.is_empty() {
        return Err(ApiError::BadRequest("name 不能为空".into()));
    }
    let mut res = Resolver::new(&state.pool, lang.clone());

    // 非路径输入：按名称找 entity_id
    if !item_path.starts_with('/') {
        if let Some((id, _)) = sqlx::query_as::<_, (String, String)>(
            "SELECT entity_id, value FROM v_localized
             WHERE lang = $1 AND field = 'name' AND lower(value) = lower($2) LIMIT 1",
        )
        .bind(&lang)
        .bind(&item_path)
        .fetch_optional(&state.pool)
        .await?
        {
            item_path = id;
        }
    }
    let item_name = res.item(&item_path).await.map(|(_, n)| n).flatten();

    let mut drops: Vec<Value> = vec![];

    // 1) 任务奖励表
    let rows: Vec<(String, i32, Option<f64>, Option<String>)> = sqlx::query_as(
        "SELECT d.unique_name, i.item_count, i.probability, i.rarity
         FROM mission_reward_items i
         JOIN mission_reward_tiers t ON t.tier_id = i.tier_id
         JOIN mission_reward_decks d ON d.unique_name = t.deck_unique_name
         WHERE regexp_replace(i.type, '^/Lotus/StoreItems', '/Lotus') = $1",
    )
    .bind(&item_path)
    .fetch_all(&state.pool)
    .await?;
    for (deck, cnt, prob, rar) in rows {
        drops.push(json!({
            "source_type": "mission_reward", "source": deck, "source_name": deck,
            "chance": prob, "rarity": rar, "item_count": cnt,
        }));
    }

    // 2) 敌人掉落表
    let rows: Vec<(String, f64)> = sqlx::query_as(
        "SELECT p.droptable_unique_name, i.probability
         FROM enemy_droptable_items i
         JOIN enemy_droptable_pools p ON p.pool_id = i.pool_id
         WHERE regexp_replace(i.type, '^/Lotus/StoreItems', '/Lotus') = $1",
    )
    .bind(&item_path)
    .fetch_all(&state.pool)
    .await?;
    for (dt, prob) in rows {
        drops.push(json!({
            "source_type": "enemy_droptable", "source": dt, "source_name": dt,
            "chance": prob, "rarity": Value::Null, "item_count": Value::Null,
        }));
    }

    // 3) 配方（作为原料 / 作为产物）
    let rows: Vec<(String, i32)> = sqlx::query_as(
        "SELECT recipe_unique_name, item_count FROM recipe_ingredients WHERE item_type = $1",
    )
    .bind(&item_path)
    .fetch_all(&state.pool)
    .await?;
    for (recipe, cnt) in rows {
        drops.push(json!({
            "source_type": "recipe_ingredient", "source": recipe, "source_name": recipe,
            "chance": Value::Null, "rarity": Value::Null, "item_count": cnt,
        }));
    }
    let rows: Vec<String> = sqlx::query_scalar(
        "SELECT unique_name FROM recipes WHERE result_type = $1",
    )
    .bind(&item_path)
    .fetch_all(&state.pool)
    .await?;
    for recipe in rows {
        drops.push(json!({
            "source_type": "recipe_result", "source": recipe, "source_name": recipe,
            "chance": Value::Null, "rarity": Value::Null, "item_count": Value::Null,
        }));
    }

    // 4) 组合包
    let rows: Vec<(String, i32)> = sqlx::query_as(
        "SELECT bundle_unique_name, purchase_quantity FROM bundle_components WHERE type_name = $1",
    )
    .bind(&item_path)
    .fetch_all(&state.pool)
    .await?;
    for (bundle, cnt) in rows {
        drops.push(json!({
            "source_type": "bundle", "source": bundle, "source_name": bundle,
            "chance": Value::Null, "rarity": Value::Null, "item_count": cnt,
        }));
    }

    Ok(Json(json!({
        "item": { "type": item_path, "name": item_name },
        "drops": drops,
    })))
}

/// POST /api/aliases —— 别名提交（受 X-API-Key 保护）
pub async fn post_aliases(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<aliases::AliasBody>,
) -> Result<Json<Value>, ApiError> {
    let Some(key) = state.config.alias_api_key.clone() else {
        return Err(ApiError::ServiceUnavailable("ALIAS_API_KEY 未配置".into()));
    };
    let provided = headers.get("x-api-key").and_then(|v| v.to_str().ok());
    match provided {
        Some(k) if k == key => {}
        Some(_) => return Err(ApiError::Unauthorized("X-API-Key 错误".into())),
        None => return Err(ApiError::Unauthorized("缺少 X-API-Key".into())),
    }
    if body.aliases.is_empty() {
        return Err(ApiError::BadRequest("aliases 不能为空".into()));
    }
    let n = aliases::upsert_aliases(&state.pool, body.aliases).await?;
    Ok(Json(json!({ "inserted": n })))
}
