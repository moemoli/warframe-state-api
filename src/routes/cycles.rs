//! GET /api/cycles —— 世界循环

use axum::extract::{Query, State};
use axum::Json;
use chrono::Utc;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::cycles::{cycle_by_name, compute_cycles};
use crate::error::ApiError;
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct CycleParams {
    name: Option<String>,
}

pub async fn list(State(_state): State<AppState>, Query(p): Query<CycleParams>) -> Result<Json<Value>, ApiError> {
    let now = Utc::now();
    match p.name {
        Some(n) => match cycle_by_name(now, &n) {
            Some(c) => Ok(Json(json!({ "cycles": [c] }))),
            None => Err(ApiError::NotFound(format!("未知循环: {n}"))),
        },
        None => Ok(Json(json!({ "cycles": compute_cycles(now) }))),
    }
}
