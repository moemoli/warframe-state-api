//! 路由装配

pub mod arbitrations;
pub mod cycles;
pub mod health;
pub mod items;
pub mod mods;
pub mod nodes;
pub mod search;
pub mod synthesis;
pub mod weapons;
pub mod wfm;
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
        .route("/api/search", axum::routing::get(search::search))
        .route("/api/items/{name}", axum::routing::get(items::search))
        .route("/api/items/{name}/drops", axum::routing::get(items::drops))
        .route("/api/aliases", axum::routing::post(items::post_aliases))
        .route("/api/synthesis", axum::routing::get(synthesis::get))
        .route("/api/mods", axum::routing::get(mods::list))
        .route("/api/mods/{unique_name}", axum::routing::get(mods::detail))
        .route("/api/weapons", axum::routing::get(weapons::list))
        .route("/api/weapons/{name}", axum::routing::get(weapons::detail))
        .route("/api/weapons/{name}/riven", axum::routing::get(weapons::riven))
        .route("/api/wfm/items", axum::routing::get(wfm::list))
        .route("/api/wfm/items/{slug}", axum::routing::get(wfm::detail))
        .route("/api/wfm/rivens", axum::routing::get(wfm::riven_list))
        .route("/api/wfm/rivens/attributes", axum::routing::get(wfm::riven_attr_list))
        .route("/api/wfm/rivens/{slug}", axum::routing::get(wfm::riven_detail))
        .route("/api/wfm/auctions/{slug}", axum::routing::get(wfm::auctions))
        .route("/api/wfm/spread/{slug}", axum::routing::get(wfm::spread))
        .route("/api/wfm/trends/{slug}", axum::routing::get(wfm::trends))
        .route("/api/wfm/components", axum::routing::get(wfm::components))
        .route("/api/wfm/rankings", axum::routing::get(wfm::rankings))
        .route("/api/wfm/liches", axum::routing::get(wfm::lich_list))
        .route("/api/wfm/liches/{slug}", axum::routing::get(wfm::lich_detail))
        .route("/api/wfm/sisters", axum::routing::get(wfm::sister_list))
        .route("/api/wfm/sisters/{slug}", axum::routing::get(wfm::sister_detail))
        .layer(CorsLayer::permissive())
        .layer(TraceLayer::new_for_http())
}
