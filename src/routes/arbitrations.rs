//! 仲裁（Arbitrations）端点：从 browse.wf/arbys.txt 拉取数据，解析节点并格式化。

use axum::Json;
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::error::ApiError;
use crate::models::to_iso;
use crate::state::AppState;

/// GET /api/arbitrations?lang=zh
pub async fn get(
    axum::extract::State(state): axum::extract::State<AppState>,
    axum::extract::Query(params): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Result<Json<Value>, ApiError> {
    let lang = params.get("lang").map(|s| s.as_str()).unwrap_or("zh");
    let limit: usize = params.get("limit")
        .and_then(|s| s.parse().ok())
        .unwrap_or(10);

    // 1) 拉取 browse.wf/arbys.txt
    let client = reqwest::Client::builder()
        .user_agent("warframe-api/1.0")
        .gzip(true)
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|e| ApiError::WorldState(e.to_string()))?;

    let text = client.get("https://browse.wf/arbys.txt")
        .send().await
        .map_err(|e| ApiError::WorldState(e.to_string()))?
        .error_for_status()
        .map_err(|e| ApiError::WorldState(e.to_string()))?
        .text().await
        .map_err(|e| ApiError::WorldState(e.to_string()))?;

    // 2) 解析 CSV: timestamp,nodeId
    let mut entries: Vec<(i64, String)> = Vec::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() { continue; }
        let mut parts = line.splitn(2, ',');
        let ts: i64 = parts.next().unwrap_or("0").parse().unwrap_or(0);
        let node = parts.next().unwrap_or("").to_string();
        if ts > 0 && !node.is_empty() {
            entries.push((ts, node));
        }
    }

    // 3) 批量查询所有涉及节点的信息
    let pool: &PgPool = &state.pool;
    let node_ids: Vec<&str> = entries.iter().map(|(_, n)| n.as_str()).collect();

    // 收集所有唯一节点 ID
    let mut unique_nodes: Vec<String> = node_ids.iter().map(|s| s.to_string()).collect();
    unique_nodes.sort();
    unique_nodes.dedup();

    // 批量查 regions 表
    #[derive(sqlx::FromRow)]
    struct NodeRow {
        unique_name: String,
        name_loc: Option<String>,
        system_index: Option<i32>,
        system_name_loc: Option<String>,
        mission_name_loc: Option<String>,
        faction_name_loc: Option<String>,
        min_enemy_level: Option<i32>,
        max_enemy_level: Option<i32>,
    }

    let rows: Vec<NodeRow> = sqlx::query_as(
        "SELECT unique_name, name_loc, system_index, system_name_loc,
                mission_name_loc, faction_name_loc, min_enemy_level, max_enemy_level
         FROM regions WHERE unique_name = ANY($1)"
    ).bind(&unique_nodes).fetch_all(pool).await.unwrap_or_default();

    // 构建查找 map
    let mut node_map = std::collections::HashMap::new();
    for r in rows {
        node_map.insert(r.unique_name.clone(), r);
    }

    // 批量查 localizations
    let loc_tags: Vec<String> = node_map.values()
        .flat_map(|r| {
            let mut tags = Vec::new();
            if let Some(ref t) = r.name_loc { tags.push(t.clone()); }
            if let Some(ref t) = r.system_name_loc { tags.push(t.clone()); }
            if let Some(ref t) = r.mission_name_loc { tags.push(t.clone()); }
            if let Some(ref t) = r.faction_name_loc { tags.push(t.clone()); }
            tags
        })
        .collect();

    let mut unique_tags: Vec<String> = loc_tags;
    unique_tags.sort();
    unique_tags.dedup();

    #[derive(sqlx::FromRow)]
    struct LocRow {
        loc_tag: String,
        value: Option<String>,
    }

    let loc_rows: Vec<LocRow> = sqlx::query_as(
        "SELECT loc_tag, value FROM localizations WHERE loc_tag = ANY($1) AND lang = $2"
    ).bind(&unique_tags).bind(lang).fetch_all(pool).await.unwrap_or_default();

    let mut loc_map = std::collections::HashMap::new();
    for r in loc_rows {
        loc_map.insert(r.loc_tag, r.value.unwrap_or_default());
    }

    // 4) 组装输出，分离 latest（当前进行中）与 schedule（未来）
    let now = chrono::Utc::now().timestamp();
    let mut latest: Option<Value> = None;
    let mut schedule: Vec<Value> = Vec::new();

    for (ts, node_id) in &entries {
        let nr = node_map.get(node_id);
        let node_name = nr
            .and_then(|r| r.name_loc.as_ref())
            .and_then(|t| loc_map.get(t).cloned())
            .unwrap_or_else(|| node_id.clone());
        let system_name = nr
            .and_then(|r| r.system_name_loc.as_ref())
            .and_then(|t| loc_map.get(t).cloned());
        let mission_type = nr
            .and_then(|r| r.mission_name_loc.as_ref())
            .and_then(|t| loc_map.get(t).cloned());
        let faction = nr
            .and_then(|r| r.faction_name_loc.as_ref())
            .and_then(|t| loc_map.get(t).cloned());
        let min_level = nr.and_then(|r| r.min_enemy_level);
        let max_level = nr.and_then(|r| r.max_enemy_level);
        let system_index = nr.and_then(|r| r.system_index);

        let expiry = ts + 3600;
        let is_active = *ts <= now && now < expiry;
        let is_future = *ts > now;

        if !is_active && !is_future { continue; }

        let mut node_obj = json!({
            "id": node_id,
            "name": node_name,
        });
        if let Some(idx) = system_index {
            node_obj["system"] = json!({ "index": idx });
            if let Some(ref sn) = system_name {
                node_obj["system"]["name"] = json!(sn);
            }
        }

        let mut entry = json!({
            "activation": to_iso(*ts * 1000),
            "expiry": to_iso(expiry * 1000),
            "node": node_obj,
        });
        if let Some(mt) = mission_type { entry["mission_type"] = json!(mt); }
        if let Some(f) = faction { entry["faction"] = json!(f); }
        if min_level.is_some() || max_level.is_some() {
            entry["enemy_levels"] = json!({ "min": min_level, "max": max_level });
        }

        if is_active && latest.is_none() {
            latest = Some(entry);
        } else if is_future && schedule.len() < limit {
            schedule.push(entry);
        }
    }

    Ok(Json(json!({
        "latest": latest,
        "schedule": {
            "count": schedule.len(),
            "entries": schedule,
        }
    })))
}
