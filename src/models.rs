//! 共享响应模型

use chrono::{DateTime, Utc};
use serde::Serialize;
use serde_json::Value;

/// 通用"引用解析"结果（Resolver 输出）
#[derive(Debug, Serialize)]
pub struct Resolved {
    pub code: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detail: Option<Value>,
    #[serde(skip_serializing_if = "std::ops::Not::not")]
    pub translated: bool,
}

/// 节点内联形态（worldstate 中）
#[derive(Debug, Serialize)]
pub struct NodeRef {
    pub r#type: String,
    pub name: String,
}

/// 奖励条目（统一元素）
#[derive(Debug, Serialize)]
pub struct RewardItem {
    pub r#type: String,
    pub item_count: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub item_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub probability: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rarity: Option<String>,
    #[serde(skip_serializing_if = "std::ops::Not::not")]
    pub translated: bool,
}

/// 奖励表展开（形态 B，tier 分组）
#[derive(Debug, Serialize)]
pub struct TierRewards {
    pub tier: i64,
    pub items: Vec<RewardItem>,
}

/// 世界循环
#[derive(Debug, Serialize)]
pub struct CycleInfo {
    pub name: String,
    pub name_zh: String,
    pub state: String,
    pub state_name: String,
    pub activation: String,
    pub expiry: String,
    pub remaining_seconds: i64,
    pub remaining: String,
}

// ---------------------------------------------------------------------------
// 时间工具：统一 UTC ISO 8601（YYYY-MM-DDTHH:MM:SSZ / .sssZ）
// ---------------------------------------------------------------------------
pub fn to_iso(ms: i64) -> String {
    DateTime::<Utc>::from_timestamp_millis(ms)
        .map(|d| d.to_rfc3339_opts(chrono::SecondsFormat::Secs, true))
        .unwrap_or_default()
}

pub fn to_iso_sec(s: i64) -> String {
    DateTime::<Utc>::from_timestamp(s, 0)
        .map(|d| d.to_rfc3339_opts(chrono::SecondsFormat::Secs, true))
        .unwrap_or_default()
}

pub fn now_iso() -> String {
    Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true)
}

/// 秒 → "1h 20m" / "45m" / "30s"
pub fn human_remaining(secs: i64) -> String {
    let secs = secs.max(0);
    let h = secs / 3600;
    let m = (secs % 3600) / 60;
    let s = secs % 60;
    if h > 0 {
        format!("{h}h {m}m")
    } else if m > 0 {
        format!("{m}m")
    } else {
        format!("{s}s")
    }
}
