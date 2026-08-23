//! GET /api/worldstate / rewards / _refresh

use axum::extract::{Query, State};
use axum::http::header::HeaderMap;
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::error::ApiError;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct WsParams {
    lang: Option<String>,
    /// 分类筛选：逗号分隔节名，空/缺省=全部；cycles/meta 恒附带
    sections: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct LangOnly {
    lang: Option<String>,
}

fn lang_of<'a>(state: &'a AppState, p: &'a LangOnly) -> String {
    p.lang.clone().unwrap_or_else(|| state.config.default_lang.clone())
}

/// GET /api/worldstate
pub async fn get(
    State(state): State<AppState>,
    Query(p): Query<WsParams>,
) -> Result<(HeaderMap, Json<Value>), ApiError> {
    let lang = p.lang.unwrap_or_else(|| state.config.default_lang.clone());
    let (data, meta) = state.ws.get(&state.pool, &lang, false).await?;

    let mut out = json!({});
    match p.sections {
        Some(s) if !s.trim().is_empty() => {
            for sec in s.split(',').map(|x| x.trim()).filter(|x| !x.is_empty()) {
                match data.get(sec) {
                    Some(v) => { out[sec] = v.clone(); }
                    None => return Err(ApiError::BadRequest(format!("未知节: {sec}"))),
                }
            }
            // cycles/meta 恒附带
            if let Some(c) = data.get("cycles") { out["cycles"] = c.clone(); }
            if let Some(m) = data.get("meta") { out["meta"] = m.clone(); }
        }
        _ => { out = (*data).clone(); }
    }

    let mut headers = HeaderMap::new();
    headers.insert("x-worldstate-age", meta.age_secs.to_string().parse().unwrap());
    headers.insert("x-worldstate-stale", (meta.stale as u8).to_string().parse().unwrap());
    Ok((headers, Json(out)))
}

/// GET /api/worldstate/rewards —— 全部奖励聚合
pub async fn rewards(
    State(state): State<AppState>,
    Query(p): Query<LangOnly>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let (data, _) = state.ws.get(&state.pool, &lang, false).await?;
    let mut out: Vec<Value> = vec![];

    if let Some(alerts) = data.get("alerts").and_then(|v| v.as_array()) {
        for (i, a) in alerts.iter().enumerate() {
            if let Some(r) = a.pointer("/mission/reward") {
                out.push(json!({ "source": format!("alert:{i}"), "rewards": r }));
            }
        }
    }
    if let Some(invs) = data.get("invasions").and_then(|v| v.as_array()) {
        for (i, inv) in invs.iter().enumerate() {
            if let Some(r) = inv.pointer("/attacker/reward") {
                out.push(json!({ "source": format!("invasion:{i}:attacker"), "rewards": r }));
            }
            if let Some(r) = inv.pointer("/defender/reward") {
                out.push(json!({ "source": format!("invasion:{i}:defender"), "rewards": r }));
            }
        }
    }
    if let Some(events) = data.get("events").and_then(|v| v.as_array()) {
        for (i, e) in events.iter().enumerate() {
            if let Some(r) = e.get("reward") {
                out.push(json!({ "source": format!("event:{i}"), "rewards": r }));
            }
        }
    }
    if let Some(goals) = data.get("goals").and_then(|v| v.as_array()) {
        for (i, g) in goals.iter().enumerate() {
            if let Some(r) = g.get("reward") {
                out.push(json!({ "source": format!("goal:{i}"), "rewards": r }));
            }
        }
    }
    if let Some(s) = data.get("sortie") {
        if let Some(r) = s.get("reward") {
            out.push(json!({ "source": "sortie", "rewards": r }));
        }
    }
    Ok(Json(json!({ "rewards": out })))
}

/// POST /api/worldstate/_refresh —— 强制刷新（受 min_interval 保护）
pub async fn refresh(
    State(state): State<AppState>,
    Query(p): Query<LangOnly>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let (data, meta) = state.ws.get(&state.pool, &lang, true).await?;
    Ok(Json(json!({
        "data": *data,
        "meta": { "fetched_at": meta.fetched_at, "stale": meta.stale },
    })))
}
