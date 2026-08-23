//! 共享应用状态

use std::sync::Arc;

use sqlx::PgPool;

use crate::config::Config;
use crate::worldstate::WorldStateCache;

#[derive(Clone)]
pub struct AppState {
    pub pool: PgPool,
    pub config: Config,
    pub ws: Arc<WorldStateCache>,
}
