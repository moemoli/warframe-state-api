//! WorldState 拉取 + 缓存 + 解析入口（design §4 / §6）
//! 三态：无缓存→拉取并缓存；TTL 内→用缓存；超 TTL→重新拉取。
//! singleflight 并发去重 + stale-while-error + min_interval 兜底。

pub mod fetch;
pub mod parse;
pub mod resolve;
pub mod types;

use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::{Arc, RwLock};
use std::time::Instant;

use chrono::Utc;
use serde_json::{json, Value};
use sqlx::PgPool;
use tokio::sync::{Mutex, Notify, OwnedMutexGuard};

use crate::config::Config;
use crate::cycles::compute_cycles;
use crate::error::ApiError;
use crate::models::now_iso;

#[derive(Clone)]
pub struct CacheCfg {
    pub url: String,
    pub ttl: u64,
    pub min_interval: u64,
}

struct CacheEntry {
    fetched_at: Instant,
    data: Arc<Value>,
}

pub struct FetchMeta {
    pub fetched_at: String,
    pub stale: bool,
    pub age_secs: u64,
}

struct Inflight {
    result: Mutex<Option<Result<Arc<Value>, String>>>,
    notify: Notify,
}

pub struct WorldStateCache {
    inner: RwLock<Option<CacheEntry>>,
    inflight: Mutex<Option<Arc<Inflight>>>,
    cfg: CacheCfg,
    last_fetch: AtomicI64,
}

fn now_epoch() -> i64 {
    Utc::now().timestamp()
}

impl WorldStateCache {
    pub fn new(cfg: &Config) -> Self {
        Self {
            inner: RwLock::new(None),
            inflight: Mutex::new(None),
            cfg: CacheCfg {
                url: cfg.worldstate_url.clone(),
                ttl: cfg.ws_cache_ttl,
                min_interval: cfg.ws_min_interval,
            },
            last_fetch: AtomicI64::new(0),
        }
    }

    /// 获取 worldstate（解析后 JSON）。`force=true` 强制刷新（受 min_interval 保护）。
    pub async fn get(
        &self, pool: &PgPool, lang: &str, force: bool,
    ) -> Result<(Arc<Value>, FetchMeta), ApiError> {
        let now = Instant::now();

        // 1) TTL 内命中缓存
        if !force {
            if let Some(e) = self.inner.read().unwrap().as_ref() {
                let age = now.duration_since(e.fetched_at).as_secs();
                if age < self.cfg.ttl {
                    return Ok((
                        e.data.clone(),
                        FetchMeta { fetched_at: now_iso(), stale: false, age_secs: age },
                    ));
                }
                // 2) min_interval 兜底：距上次拉取过近 → 沿用缓存（stale）
                let last = self.last_fetch.load(Ordering::Relaxed);
                if last > 0 && now_epoch() - last < self.cfg.min_interval as i64 {
                    return Ok((
                        e.data.clone(),
                        FetchMeta { fetched_at: now_iso(), stale: true, age_secs: age },
                    ));
                }
            }
        }

        // 3) singleflight：只允许一个在途拉取
        let (shared, is_leader) = {
            let mut g = self.inflight.lock().await;
            match g.as_ref() {
                Some(s) => (s.clone(), false),
                None => {
                    let s = Arc::new(Inflight { result: Mutex::new(None), notify: Notify::new() });
                    *g = Some(s.clone());
                    (s, true)
                }
            }
        };

        if is_leader {
            let res = fetch_and_parse(pool, lang, &self.cfg.url).await;
            *shared.result.lock().await = Some(res);
            shared.notify.notify_waiters();
            self.last_fetch.store(now_epoch(), Ordering::Relaxed);
            // 清理 in-flight 标记（仅当仍指向自己）
            let mut g = self.inflight.lock().await;
            let same = g.as_ref().map(|c| Arc::ptr_eq(c, &shared)).unwrap_or(false);
            if same {
                *g = None;
            }
        } else {
            shared.notify.notified().await;
        }

        let outcome = shared.result.lock().await.clone();
        match outcome {
            Some(Ok(data)) => {
                *self.inner.write().unwrap() = Some(CacheEntry { fetched_at: Instant::now(), data: data.clone() });
                Ok((data, FetchMeta { fetched_at: now_iso(), stale: false, age_secs: 0 }))
            }
            Some(Err(e)) => {
                // stale-while-error
                if let Some(entry) = self.inner.read().unwrap().as_ref() {
                    let age = now.duration_since(entry.fetched_at).as_secs();
                    return Ok((
                        entry.data.clone(),
                        FetchMeta { fetched_at: now_iso(), stale: true, age_secs: age },
                    ));
                }
                Err(ApiError::WorldState(format!("worldstate 上游失败: {e}")))
            }
            None => Err(ApiError::WorldState("worldstate 拉取中".into())),
        }
    }
}

async fn fetch_and_parse(pool: &PgPool, lang: &str, url: &str) -> Result<Arc<Value>, String> {
    let raw = fetch::fetch_raw(url).await?;
    match serde_json::from_value::<types::RawWorldState>(raw.clone()) {
        Ok(parsed) => {
            let value = parse::parse_all(pool, lang, parsed, &now_iso())
                .await
                .map_err(|e| format!("{e:?}"))?;
            Ok(Arc::new(value))
        }
        // 解析失败降级：透传原始 JSON + 附加 cycles/meta
        Err(_) => {
            let mut v = raw;
            v["cycles"] = compute_cycles(Utc::now()).iter().map(|c| json!(c)).collect::<Vec<_>>().into();
            v["meta"] = json!({ "fetched_at": now_iso(), "stale": false, "passthrough": true });
            Ok(Arc::new(v))
        }
    }
}

// 辅助：拿到锁的 guard 仅用于确保 Mutex 类型被使用（避免未使用警告场景）
#[allow(dead_code)]
fn _keep(_g: OwnedMutexGuard<()>) {}
