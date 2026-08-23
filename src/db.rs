//! 数据库：PostgreSQL 连接池

use sqlx::postgres::{PgPool, PgPoolOptions};

/// 创建连接池（默认最大 10 个连接）
pub async fn create_pool(database_url: &str) -> Result<PgPool, sqlx::Error> {
    PgPoolOptions::new()
        .max_connections(10)
        .acquire_timeout(std::time::Duration::from_secs(5))
        .connect(database_url)
        .await
}

/// 健康检查：SELECT 1
pub async fn ping(pool: &PgPool) -> Result<(), sqlx::Error> {
    sqlx::query("SELECT 1").execute(pool).await.map(|_| ())
}
