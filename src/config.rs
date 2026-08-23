//! 配置：环境变量加载（支持 .env 文件）

use std::env;

/// 应用配置
#[derive(Debug, Clone)]
pub struct Config {
    pub database_url: String,
    pub bind_addr: String,
    pub default_lang: String,
    pub worldstate_url: String,
    /// WorldState 缓存秒数（默认 180 = 3 分钟；超时重新拉取）
    pub ws_cache_ttl: u64,
    /// 两次上游请求最小间隔（秒）
    pub ws_min_interval: u64,
    pub cycle_provider: String,
    /// 别名提交接口鉴权密钥；None 时 POST /api/aliases 返回 503
    pub alias_api_key: Option<String>,
}

impl Config {
    pub fn from_env() -> Self {
        let _ = dotenvy::dotenv();
        Self {
            database_url: env::var("DATABASE_URL").unwrap_or_else(|_| {
                "postgres://warframe:warframe123@127.0.0.1:5432/warframe".to_string()
            }),
            bind_addr: env::var("BIND_ADDR").unwrap_or_else(|_| "0.0.0.0:8080".to_string()),
            default_lang: env::var("DEFAULT_LANG").unwrap_or_else(|_| "zh".to_string()),
            worldstate_url: env::var("WORLDSTATE_URL")
                .unwrap_or_else(|_| "https://api.warframe.com/cdn/worldState.php".to_string()),
            ws_cache_ttl: env::var("WORLDSTATE_CACHE_TTL")
                .ok().and_then(|v| v.parse().ok()).unwrap_or(180),
            ws_min_interval: env::var("WORLDSTATE_MIN_INTERVAL")
                .ok().and_then(|v| v.parse().ok()).unwrap_or(30),
            cycle_provider: env::var("CYCLE_PROVIDER").unwrap_or_else(|_| "local".to_string()),
            alias_api_key: env::var("ALIAS_API_KEY").ok().filter(|s| !s.is_empty()),
        }
    }
}
