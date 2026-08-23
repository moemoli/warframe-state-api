//! GET /health — 健康检查（含数据库连通性）

use axum::extract::State;
use axum::Json;
use serde_json::{json, Value};

use crate::db;
use crate::AppState;

pub async fn health(State(state): State<AppState>) -> Json<Value> {
    match db::ping(&state.pool).await {
        Ok(()) => Json(json!({ "status": "ok", "database": "ok" })),
        Err(e) => Json(json!({ "status": "degraded", "database": format!("{e}") })),
    }
}
