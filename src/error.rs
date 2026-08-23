//! 统一错误类型 → JSON 响应

use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;

/// API 错误
#[derive(Debug)]
pub enum ApiError {
    BadRequest(String),
    NotFound(String),
    Unauthorized(String),
    ServiceUnavailable(String),
    WorldState(String),
    Database(sqlx::Error),
}

impl From<sqlx::Error> for ApiError {
    fn from(e: sqlx::Error) -> Self {
        ApiError::Database(e)
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, msg) = match self {
            ApiError::BadRequest(m) => (StatusCode::BAD_REQUEST, m),
            ApiError::NotFound(m) => (StatusCode::NOT_FOUND, m),
            ApiError::Unauthorized(m) => (StatusCode::UNAUTHORIZED, m),
            ApiError::ServiceUnavailable(m) => (StatusCode::SERVICE_UNAVAILABLE, m),
            ApiError::WorldState(m) => (StatusCode::BAD_GATEWAY, m),
            ApiError::Database(e) => (StatusCode::INTERNAL_SERVER_ERROR, format!("database error: {e}")),
        };
        tracing::error!(status = %status, msg = %msg);
        (status, Json(json!({ "error": msg }))).into_response()
    }
}
