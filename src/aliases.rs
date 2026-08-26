//! 物品简写（别名）查询与管理

use serde::{Deserialize, Serialize};
use sqlx::PgPool;

use crate::error::ApiError;

#[derive(Debug, Serialize)]
pub struct AliasHit {
    pub entity_type: String,
    pub entity_id: String,
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct AliasBody {
    pub aliases: Vec<AliasEntry>,
}

#[derive(Debug, Deserialize)]
pub struct AliasEntry {
    pub alias: String,
    pub entity_type: String,
    pub entity_id: String,
}

/// 别名精确查询（大小写不敏感）。返回别名命中的实体 id。
pub async fn find_alias(pool: &PgPool, alias: &str) -> Result<Vec<(String, String)>, ApiError> {
    let rows = sqlx::query_as::<_, (String, String)>(
        "SELECT entity_type, entity_id FROM aliases WHERE lower(alias) = lower($1)",
    )
    .bind(alias)
    .fetch_all(pool)
    .await?;
    Ok(rows)
}

/// 批量 upsert 别名（POST /api/aliases 使用）
pub async fn upsert_aliases(pool: &PgPool, entries: Vec<AliasEntry>) -> Result<usize, ApiError> {
    let mut tx = pool.begin().await?;
    let mut n = 0usize;
    for e in entries {
        let alias = e.alias.trim();
        let entity_type = e.entity_type.trim();
        let entity_id = e.entity_id.trim();
        if alias.is_empty() || entity_type.is_empty() || entity_id.is_empty() {
            continue;
        }
        let res = sqlx::query(
            "INSERT INTO aliases (alias, entity_type, entity_id) VALUES ($1,$2,$3)
             ON CONFLICT (alias, entity_type, entity_id) DO UPDATE SET entity_id = EXCLUDED.entity_id",
        )
        .bind(alias)
        .bind(entity_type)
        .bind(entity_id)
        .execute(&mut *tx)
        .await?;
        n += res.rows_affected() as usize;
    }
    tx.commit().await?;
    Ok(n)
}

/// 删除别名（DELETE /api/aliases 使用）
pub async fn delete_alias(pool: &PgPool, alias: &str) -> Result<usize, ApiError> {
    let alias = alias.trim();
    if alias.is_empty() {
        return Err(ApiError::BadRequest("alias 不能为空".into()));
    }
    let res = sqlx::query("DELETE FROM aliases WHERE lower(alias) = lower($1)")
        .bind(alias)
        .execute(pool)
        .await?;
    Ok(res.rows_affected() as usize)
}
