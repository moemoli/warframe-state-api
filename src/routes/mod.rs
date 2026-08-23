//! 路由装配

pub mod arbitrations;
pub mod cycles;
pub mod health;
pub mod items;
pub mod mods;
pub mod nodes;
pub mod weapons;
pub mod worldstate;

use axum::Router;
use tower_http::cors::CorsLayer;
use tower_http::trace::TraceLayer;

use crate::AppState;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/health", axum::routing::get(health::health))
        .route("/api/worldstate", axum::routing::get(worldstate::get))
        .route("/api/worldstate/rewards", axum::routing::get(worldstate::rewards))
        .route("/api/worldstate/_refresh", axum::routing::post(worldstate::refresh))
        .route("/api/arbitrations", axum::routing::get(arbitrations::get))
        .route("/api/cycles", axum::routing::get(cycles::list))
        .route("/api/nodes/{node_type}", axum::routing::get(nodes::detail))
        .route("/api/items/{name}", axum::routing::get(items::search))
        .route("/api/items/{name}/drops", axum::routing::get(items::drops))
        .route("/api/aliases", axum::routing::post(items::post_aliases))
        .route("/api/mods", axum::routing::get(mods::list))
        .route("/api/mods/{unique_name}", axum::routing::get(mods::detail))
        .route("/api/weapons", axum::routing::get(weapons::list))
        .route("/api/weapons/{name}", axum::routing::get(weapons::detail))
        .route("/api/weapons/{name}/riven", axum::routing::get(weapons::riven))
        .layer(CorsLayer::permissive())
        .layer(TraceLayer::new_for_http())
}
