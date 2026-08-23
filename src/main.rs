//! warframe-api 入口

mod aliases;
mod config;
mod cycles;
mod db;
mod error;
mod models;
mod routes;
mod state;
mod worldstate;

use std::sync::Arc;

use tracing_subscriber::EnvFilter;

use crate::config::Config;
use crate::state::AppState;
use crate::worldstate::WorldStateCache;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    let cfg = Config::from_env();
    let pool = db::create_pool(&cfg.database_url).await?;
    let ws = Arc::new(WorldStateCache::new(&cfg));
    let state = AppState { pool, config: cfg.clone(), ws };

    let listener = tokio::net::TcpListener::bind(&cfg.bind_addr).await?;
    tracing::info!("warframe-api listening on {}", cfg.bind_addr);
    axum::serve(listener, routes::router().with_state(state)).await?;
    Ok(())
}
