//! warframe.market 集成端点
//! - GET /api/wfm/items               物品列表
//! - GET /api/wfm/items/{slug}        物品详情 + 实时价格
//! - GET /api/wfm/rivens              紫卡武器列表
//! - GET /api/wfm/rivens/attributes   紫卡词条列表
//! - GET /api/wfm/rivens/{slug}       紫卡武器详情 + 实时价格
//! - GET /api/wfm/liches              赤毒玄骸武器列表
//! - GET /api/wfm/liches/{slug}       赤毒玄骸武器详情 + 实时价格
//! - GET /api/wfm/sisters             帕尔沃斯姐妹武器列表
//! - GET /api/wfm/sisters/{slug}      姐妹武器详情 + 实时价格

use axum::extract::{Path, Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::error::ApiError;
use crate::state::AppState;

#[derive(Debug, Deserialize)]
pub struct WfmParams {
    lang: Option<String>,
    name: Option<String>,
    r#type: Option<String>,
    kind: Option<String>,
    /// 趋势端点专用：48h | 90d（默认 90d）
    range: Option<String>,
    limit: Option<i64>,
    offset: Option<i64>,
    // ---- 列表端点通用数值筛选（rivens/liches/sisters 等）----
    /// 精通段位要求下限
    mastery_min: Option<i32>,
    /// 精通段位要求上限
    mastery_max: Option<i32>,
    /// 倾向值下限（仅 rivens 有 disposition 字段）
    disp_min: Option<f64>,
    /// 倾向值上限（仅 rivens）
    disp_max: Option<f64>,
}

fn lang_of<'a>(state: &'a AppState, p: &'a WfmParams) -> String {
    p.lang.clone().unwrap_or_else(|| state.config.default_lang.clone())
}

fn lang_of_opt(state: &AppState, lang: &Option<String>) -> String {
    lang.clone().unwrap_or_else(|| state.config.default_lang.clone())
}

/// 校验成对数值参数（min/max 均可缺省），非法范围返回 400
fn check_range(name: &str, min: Option<i64>, max: Option<i64>) -> Result<(), ApiError> {
    if let (Some(a), Some(b)) = (min, max) {
        if a > b {
            return Err(ApiError::BadRequest(format!(
                "{name} 范围非法：min({a}) > max({b})"
            )));
        }
    }
    Ok(())
}

fn check_range_i32(name: &str, min: Option<i32>, max: Option<i32>) -> Result<(), ApiError> {
    if let (Some(a), Some(b)) = (min, max) {
        if a > b {
            return Err(ApiError::BadRequest(format!(
                "{name} 范围非法：min({a}) > max({b})"
            )));
        }
    }
    Ok(())
}

fn check_range_f64(name: &str, min: Option<f64>, max: Option<f64>) -> Result<(), ApiError> {
    if let (Some(a), Some(b)) = (min, max) {
        if a > b {
            return Err(ApiError::BadRequest(format!(
                "{name} 范围非法：min({a}) > max({b})"
            )));
        }
    }
    Ok(())
}

// ============================================================
// /api/wfm/items —— 可交易物品
// ============================================================

/// GET /api/wfm/auctions 与 /api/wfm/spread 的筛选参数
///
/// 全部可选，多个条件取交集（AND）。词条用逗号分隔（与 wfm_riven_attributes.slug
/// 一致，如 `critical_chance,critical_damage`）。
#[derive(Debug, Deserialize)]
pub struct AuctionParams {
    lang: Option<String>,
    limit: Option<i64>,
    /// 洗练次数下限（零洗 = rerolls_min=0&rerolls_max=0）
    rerolls_min: Option<i64>,
    /// 洗练次数上限（如 5洗 = rerolls_max=5）
    rerolls_max: Option<i64>,
    /// mod 等级下限（0..8）
    rank_min: Option<i64>,
    /// mod 等级上限
    rank_max: Option<i64>,
    /// 精通段位要求下限
    mastery_min: Option<i64>,
    /// 精通段位要求上限
    mastery_max: Option<i64>,
    /// 有效价格（买断价优先，无则起拍价）下限
    price_min: Option<i64>,
    /// 有效价格上限（如 1000p = price_max=1000）
    price_max: Option<i64>,
    /// 正面词条数下限（如 2+ = pos_min=2）
    pos_min: Option<i64>,
    /// 正面词条数上限
    pos_max: Option<i64>,
    /// 负面词条数下限（带负 = neg_min=1）
    neg_min: Option<i64>,
    /// 负面词条数上限（无负 = neg_max=0）
    neg_max: Option<i64>,
    /// 必须包含的正面词条 slug，逗号分隔，可重复段；全部须命中
    attr_pos: Option<String>,
    /// 必须包含的负面词条 slug，逗号分隔；全部须命中
    attr_neg: Option<String>,
    /// 极性：madurai | naramon | vazarin | zenurik
    polarity: Option<String>,
    /// 卖家状态：ingame | online | offline | any（默认 any）
    status: Option<String>,
}

/// 归一化后的拍卖筛选条件（用于匹配与 filters 回显）
#[derive(Debug, Default, Clone)]
struct AuctionFilter {
    rerolls: (Option<i64>, Option<i64>),
    rank: (Option<i64>, Option<i64>),
    mastery: (Option<i64>, Option<i64>),
    price: (Option<i64>, Option<i64>),
    pos: (Option<i64>, Option<i64>),
    neg: (Option<i64>, Option<i64>),
    attr_pos: Vec<String>,
    attr_neg: Vec<String>,
    polarity: Option<String>,
    status: Option<String>,
}

impl AuctionFilter {
    fn is_empty(&self) -> bool {
        self.rerolls == (None, None)
            && self.rank == (None, None)
            && self.mastery == (None, None)
            && self.price == (None, None)
            && self.pos == (None, None)
            && self.neg == (None, None)
            && self.attr_pos.is_empty()
            && self.attr_neg.is_empty()
            && self.polarity.is_none()
            && self.status.is_none()
    }

    fn to_json(&self, lang: &str) -> Value {
        let rng = |r: (Option<i64>, Option<i64>)| json!({ "min": r.0, "max": r.1 });
        json!({
            "lang": lang,
            "rerolls": rng(self.rerolls),
            "rank": rng(self.rank),
            "mastery": rng(self.mastery),
            "price": rng(self.price),
            "pos": rng(self.pos),
            "neg": rng(self.neg),
            "attr_pos": self.attr_pos,
            "attr_neg": self.attr_neg,
            "polarity": self.polarity,
            "status": self.status.clone().unwrap_or_else(|| "any".into()),
        })
    }
}

fn split_slugs(s: &str) -> Vec<String> {
    s.split(',').map(|x| x.trim().to_string()).filter(|x| !x.is_empty()).collect()
}

/// 校验词条 slug 是否存在于词条表；未知值返回 400（表本身为空时跳过校验）
async fn validate_attr_slugs(pool: &PgPool, slugs: &[String]) -> Result<(), ApiError> {
    if slugs.is_empty() { return Ok(()); }
    let total: i64 = sqlx::query_scalar("SELECT count(*) FROM wfm_riven_attributes")
        .fetch_one(pool).await?;
    if total == 0 {
        // 词条表尚未导入数据时不做强校验，避免误伤
        return Ok(());
    }
    let known: Vec<String> = sqlx::query_scalar(
        "SELECT slug FROM wfm_riven_attributes WHERE slug = ANY($1)")
        .bind(slugs).fetch_all(pool).await?;
    let unknown: Vec<&String> = slugs.iter().filter(|s| !known.contains(s)).collect();
    if !unknown.is_empty() {
        return Err(ApiError::BadRequest(format!(
            "未知词条 slug: {}（可用 /api/wfm/rivens/attributes 查询）",
            unknown.iter().map(|s| s.as_str()).collect::<Vec<_>>().join(", ")
        )));
    }
    Ok(())
}

/// 校验并构建拍卖筛选条件（数值范围 / 极性 / 卖家状态）
fn parse_auction_filter(p: &AuctionParams) -> Result<AuctionFilter, ApiError> {
    check_range("rerolls", p.rerolls_min, p.rerolls_max)?;
    check_range("rank", p.rank_min, p.rank_max)?;
    check_range("mastery", p.mastery_min, p.mastery_max)?;
    check_range("price", p.price_min, p.price_max)?;
    check_range("pos", p.pos_min, p.pos_max)?;
    check_range("neg", p.neg_min, p.neg_max)?;

    let polarity = match p.polarity.as_deref() {
        None => None,
        Some(v @ ("madurai" | "naramon" | "vazarin" | "zenurik")) => Some(v.to_string()),
        Some(v) => {
            return Err(ApiError::BadRequest(format!(
                "polarity 非法：{v}（可选 madurai/naramon/vazarin/zenurik）"
            )))
        }
    };
    let status = match p.status.as_deref() {
        None => None,
        Some(v @ ("ingame" | "online" | "offline" | "any")) => Some(v.to_string()),
        Some(v) => {
            return Err(ApiError::BadRequest(format!(
                "status 非法：{v}（可选 ingame/online/offline/any）"
            )))
        }
    };

    Ok(AuctionFilter {
        rerolls: (p.rerolls_min, p.rerolls_max),
        rank: (p.rank_min, p.rank_max),
        mastery: (p.mastery_min, p.mastery_max),
        price: (p.price_min, p.price_max),
        pos: (p.pos_min, p.pos_max),
        neg: (p.neg_min, p.neg_max),
        attr_pos: p.attr_pos.as_deref().map(split_slugs).unwrap_or_default(),
        attr_neg: p.attr_neg.as_deref().map(split_slugs).unwrap_or_default(),
        polarity,
        status,
    })
}

fn in_range(v: Option<i64>, r: (Option<i64>, Option<i64>)) -> bool {
    match (r.0, r.1) {
        (None, None) => true,
        (Some(a), None) => v.map_or(false, |x| x >= a),
        (None, Some(b)) => v.map_or(false, |x| x <= b),
        (Some(a), Some(b)) => v.map_or(false, |x| x >= a && x <= b),
    }
}

/// 简化拍卖条目是否满足全部条件（AND）
fn auction_matches(a: &Value, f: &AuctionFilter) -> bool {
    let i64_at = |k: &str| a.get(k).and_then(|v| v.as_i64());
    if !in_range(i64_at("rerolls"), f.rerolls) { return false; }
    if !in_range(i64_at("rank"), f.rank) { return false; }
    if !in_range(i64_at("mastery_level"), f.mastery) { return false; }
    if !in_range(i64_at("price"), f.price) { return false; }

    if let Some(pol) = &f.polarity {
        if a.get("polarity").and_then(|v| v.as_str()) != Some(pol.as_str()) { return false; }
    }
    if let Some(st) = &f.status {
        let s = a.get("status").and_then(|v| v.as_str()).unwrap_or("offline");
        let ok = match st.as_str() {
            "any" => true,
            "ingame" => s == "ingame",
            "online" => s == "ingame" || s == "online",
            "offline" => s == "offline",
            _ => true,
        };
        if !ok { return false; }
    }

    let attrs = a.get("attributes").and_then(|v| v.as_array());
    let (mut pos, mut neg) = (0i64, 0i64);
    let (mut pos_hit, mut neg_hit) = (vec![false; f.attr_pos.len()], vec![false; f.attr_neg.len()]);
    if let Some(list) = attrs {
        for at in list {
            let negative = at.get("negative").and_then(|v| v.as_bool()).unwrap_or(false);
            if negative { neg += 1; } else { pos += 1; }
            if let Some(name) = at.get("name").and_then(|v| v.as_str()) {
                if !negative {
                    for (i, w) in f.attr_pos.iter().enumerate() {
                        if w == name { pos_hit[i] = true; }
                    }
                } else {
                    for (i, w) in f.attr_neg.iter().enumerate() {
                        if w == name { neg_hit[i] = true; }
                    }
                }
            }
        }
    }
    if !in_range(Some(pos), f.pos) { return false; }
    if !in_range(Some(neg), f.neg) { return false; }
    pos_hit.iter().all(|h| *h) && neg_hit.iter().all(|h| *h)
}

/// 生成该条命中项满足的筛选条件文案（用于逐条标注）
fn matched_conditions(a: &Value, f: &AuctionFilter) -> Vec<Value> {
    if f.is_empty() { return vec![]; }
    let mut out: Vec<String> = Vec::new();
    let rng_desc = |label: &str, r: (Option<i64>, Option<i64>)| -> Option<String> {
        match (r.0, r.1) {
            (Some(a0), Some(b0)) if a0 == b0 => Some(format!("{label}={a0}")),
            (Some(a0), None) => Some(format!("{label}≥{a0}")),
            (None, Some(b0)) => Some(format!("{label}≤{b0}")),
            (Some(a0), Some(b0)) => Some(format!("{a0}≤{label}≤{b0}")),
            (None, None) => None,
        }
    };
    if let Some(s) = rng_desc("洗练", f.rerolls) { out.push(s); }
    if let Some(s) = rng_desc("等级", f.rank) { out.push(s); }
    if let Some(s) = rng_desc("段位", f.mastery) { out.push(s); }
    if let Some(s) = rng_desc("价格", f.price) { out.push(s); }
    if let Some(s) = rng_desc("正面词条数", f.pos) { out.push(s); }
    if let Some(s) = rng_desc("负面词条数", f.neg) { out.push(s); }
    // 命中词条（带中文名对照优先）
    if let Some(list) = a.get("attributes").and_then(|v| v.as_array()) {
        for at in list {
            let negative = at.get("negative").and_then(|v| v.as_bool()).unwrap_or(false);
            if let Some(name) = at.get("name").and_then(|v| v.as_str()) {
                let disp = at.get("name_zh").and_then(|v| v.as_str())
                    .unwrap_or(name);
                let wanted = if negative { &f.attr_neg } else { &f.attr_pos };
                if wanted.iter().any(|w| w == name) {
                    out.push(format!("{}含「{}」", if negative { "负面" } else { "正面" }, disp));
                }
            }
        }
    }
    if let Some(pol) = &f.polarity {
        out.push(format!("极性={pol}"));
    }
    out.into_iter().map(Value::String).collect()
}

/// GET /api/wfm/items?name=adaptation&lang=zh
pub async fn list(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let limit = p.limit.unwrap_or(20).clamp(1, 100);
    let offset = p.offset.unwrap_or(0).max(0);

    let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                   Option<String>, Option<i32>, Option<i32>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.icon, w.thumb, i.item_name,
                w.ducats, w.trading_tax
         FROM wfm_items w
         LEFT JOIN wfm_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
         ORDER BY i.item_name NULLS LAST, w.slug LIMIT $3 OFFSET $4",
    ).bind(&lang).bind(p.name.as_deref()).bind(limit).bind(offset)
     .fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.iter().map(|r| json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2,
        "icon": r.3, "thumb": r.4, "item_name": r.5,
        "ducats": r.6, "trading_tax": r.7,
    })).collect();

    Ok(Json(json!({ "items": items, "total": items.len(), "limit": limit, "offset": offset })))
}

/// GET /api/wfm/items/{slug}?lang=zh
pub async fn detail(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let row: Option<(String, String, Option<String>, Vec<String>, bool, Option<String>,
                     Option<i32>, Option<i32>, Option<i32>, Option<i32>,
                     Option<String>, Option<String>,
                     Option<String>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.tags, w.tradable, w.rarity,
                w.mod_max_rank, w.mastery_level, w.ducats, w.trading_tax,
                w.icon, w.thumb, i.item_name, i.description, i.wiki_link
         FROM wfm_items w LEFT JOIN wfm_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE w.slug = $2"
    ).bind(&lang).bind(&slug).fetch_optional(&state.pool).await?;

    let Some(r) = row else { return Err(ApiError::NotFound(format!("未找到: {slug}"))); };
    let prices = fetch_wfm_top_orders(&state.pool, "item", "item", &slug).await;

    Ok(Json(json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2, "tags": r.3, "tradable": r.4,
        "rarity": r.5, "mod_max_rank": r.6, "mastery_level": r.7,
        "ducats": r.8, "trading_tax": r.9, "icon": r.10, "thumb": r.11,
        "item_name": r.12, "description": r.13, "wiki_link": r.14, "prices": prices,
    })))
}

// ============================================================
// /api/wfm/rivens —— 紫卡武器
// ============================================================

/// GET /api/wfm/rivens?name=rubico&type=rifle&lang=zh
/// 支持 mastery_min/max（段位要求）、disp_min/max（倾向值）范围筛选。
pub async fn riven_list(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let limit = p.limit.unwrap_or(20).clamp(1, 100);
    let offset = p.offset.unwrap_or(0).max(0);
    check_range_i32("mastery", p.mastery_min, p.mastery_max)?;
    check_range_f64("disp", p.disp_min, p.disp_max)?;

    let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                   Option<String>, Option<String>, Option<f32>, Option<i32>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.riven_type, w.\"group\",
                w.icon, w.thumb, w.disposition, w.mastery_level
         FROM wfm_riven_items w
         LEFT JOIN wfm_riven_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
           AND ($3::text IS NULL OR w.riven_type = $3)
           AND ($4::int IS NULL OR w.mastery_level >= $4)
           AND ($5::int IS NULL OR w.mastery_level <= $5)
           AND ($6::float8 IS NULL OR w.disposition >= $6)
           AND ($7::float8 IS NULL OR w.disposition <= $7)
         ORDER BY i.item_name NULLS LAST, w.slug LIMIT $8 OFFSET $9",
    ).bind(&lang).bind(p.name.as_deref()).bind(p.r#type.as_deref())
     .bind(p.mastery_min).bind(p.mastery_max).bind(p.disp_min).bind(p.disp_max)
     .bind(limit).bind(offset).fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.iter().map(|r| json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2, "riven_type": r.3, "group": r.4,
        "icon": r.5, "thumb": r.6, "disposition": r.7, "mastery_level": r.8,
    })).collect();

    // 真实命中总数（分页前）
    let total: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM wfm_riven_items w
         LEFT JOIN wfm_riven_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
           AND ($3::text IS NULL OR w.riven_type = $3)
           AND ($4::int IS NULL OR w.mastery_level >= $4)
           AND ($5::int IS NULL OR w.mastery_level <= $5)
           AND ($6::float8 IS NULL OR w.disposition >= $6)
           AND ($7::float8 IS NULL OR w.disposition <= $7)")
        .bind(&lang).bind(p.name.as_deref()).bind(p.r#type.as_deref())
        .bind(p.mastery_min).bind(p.mastery_max).bind(p.disp_min).bind(p.disp_max)
        .fetch_one(&state.pool).await?;

    Ok(Json(json!({
        "lang": lang,
        "filters": {
            "name": p.name, "type": p.r#type,
            "mastery": { "min": p.mastery_min, "max": p.mastery_max },
            "disposition": { "min": p.disp_min, "max": p.disp_max },
        },
        "items": items, "total": total, "limit": limit, "offset": offset,
    })))
}

/// GET /api/wfm/rivens/attributes?lang=zh
pub async fn riven_attr_list(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                   Option<String>, Vec<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.prefix, w.suffix, w.units, w.\"group\",
                w.exclusive_to, i.effect
         FROM wfm_riven_attributes w
         LEFT JOIN wfm_riven_attr_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         ORDER BY i.effect NULLS LAST, w.slug",
    ).bind(&lang).fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.iter().map(|r| json!({
        "wfm_id": r.0, "slug": r.1, "prefix": r.2, "suffix": r.3,
        "units": r.4, "group": r.5, "exclusive_to": r.6, "effect": r.7,
    })).collect();

    Ok(Json(json!({ "attributes": items, "total": items.len() })))
}

/// GET /api/wfm/rivens/{slug}?lang=zh
pub async fn riven_detail(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let row: Option<(String, String, Option<String>, Option<String>, Option<String>,
                     Option<f32>, Option<i32>, Option<String>, Option<String>,
                     Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.riven_type, w.\"group\",
                w.disposition, w.mastery_level, w.icon, w.thumb,
                i.item_name, i.wiki_link
         FROM wfm_riven_items w LEFT JOIN wfm_riven_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE w.slug = $2"
    ).bind(&lang).bind(&slug).fetch_optional(&state.pool).await?;

    let Some(r) = row else { return Err(ApiError::NotFound(format!("未找到紫卡武器: {slug}"))); };
    let prices = fetch_wfm_top_orders(&state.pool, "riven", "riven/weapon", &slug).await;

    Ok(Json(json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2, "riven_type": r.3, "group": r.4,
        "disposition": r.5, "mastery_level": r.6, "icon": r.7, "thumb": r.8,
        "item_name": r.9, "wiki_link": r.10, "prices": prices,
    })))
}

// ============================================================
// /api/wfm/liches —— 赤毒玄骸武器
// ============================================================

/// GET /api/wfm/liches?name=kuva&lang=zh
/// 支持 mastery_min/max（段位要求）范围筛选。
pub async fn lich_list(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let limit = p.limit.unwrap_or(20).clamp(1, 100);
    let offset = p.offset.unwrap_or(0).max(0);
    check_range_i32("mastery", p.mastery_min, p.mastery_max)?;

    let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                   Option<String>, Option<i32>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.icon, w.thumb, i.item_name, w.mastery_level
         FROM wfm_lich_weapons w
         LEFT JOIN wfm_lich_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
           AND ($3::int IS NULL OR w.mastery_level >= $3)
           AND ($4::int IS NULL OR w.mastery_level <= $4)
         ORDER BY i.item_name NULLS LAST, w.slug LIMIT $5 OFFSET $6",
    ).bind(&lang).bind(p.name.as_deref())
     .bind(p.mastery_min).bind(p.mastery_max).bind(limit).bind(offset)
     .fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.iter().map(|r| json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2,
        "icon": r.3, "thumb": r.4, "item_name": r.5, "mastery_level": r.6,
    })).collect();

    let total: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM wfm_lich_weapons w
         LEFT JOIN wfm_lich_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
           AND ($3::int IS NULL OR w.mastery_level >= $3)
           AND ($4::int IS NULL OR w.mastery_level <= $4)")
        .bind(&lang).bind(p.name.as_deref())
        .bind(p.mastery_min).bind(p.mastery_max)
        .fetch_one(&state.pool).await?;

    Ok(Json(json!({
        "lang": lang,
        "filters": {
            "name": p.name,
            "mastery": { "min": p.mastery_min, "max": p.mastery_max },
        },
        "items": items, "total": total, "limit": limit, "offset": offset,
    })))
}

/// GET /api/wfm/liches/{slug}?lang=zh
pub async fn lich_detail(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let row: Option<(String, String, Option<String>, Option<i32>,
                     Option<String>, Option<String>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.mastery_level,
                w.icon, w.thumb, i.item_name, i.wiki_link
         FROM wfm_lich_weapons w LEFT JOIN wfm_lich_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE w.slug = $2"
    ).bind(&lang).bind(&slug).fetch_optional(&state.pool).await?;

    let Some(r) = row else { return Err(ApiError::NotFound(format!("未找到赤毒武器: {slug}"))); };
    let prices = fetch_wfm_top_orders(&state.pool, "lich", "lich/weapon", &slug).await;

    Ok(Json(json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2, "mastery_level": r.3,
        "icon": r.4, "thumb": r.5, "item_name": r.6, "wiki_link": r.7, "prices": prices,
    })))
}

// ============================================================
// /api/wfm/sisters —— 帕尔沃斯姐妹武器
// ============================================================

/// GET /api/wfm/sisters?name=tenet&lang=zh
/// 支持 mastery_min/max（段位要求）范围筛选。
pub async fn sister_list(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let limit = p.limit.unwrap_or(20).clamp(1, 100);
    let offset = p.offset.unwrap_or(0).max(0);
    check_range_i32("mastery", p.mastery_min, p.mastery_max)?;

    let rows: Vec<(String, String, Option<String>, Option<String>, Option<String>,
                   Option<String>, Option<i32>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.icon, w.thumb, i.item_name, w.mastery_level
         FROM wfm_sister_weapons w
         LEFT JOIN wfm_sister_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
           AND ($3::int IS NULL OR w.mastery_level >= $3)
           AND ($4::int IS NULL OR w.mastery_level <= $4)
         ORDER BY i.item_name NULLS LAST, w.slug LIMIT $5 OFFSET $6",
    ).bind(&lang).bind(p.name.as_deref())
     .bind(p.mastery_min).bind(p.mastery_max).bind(limit).bind(offset)
     .fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.iter().map(|r| json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2,
        "icon": r.3, "thumb": r.4, "item_name": r.5, "mastery_level": r.6,
    })).collect();

    let total: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM wfm_sister_weapons w
         LEFT JOIN wfm_sister_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE ($2::text IS NULL OR i.item_name ILIKE '%' || $2 || '%' OR w.slug ILIKE '%' || $2 || '%')
           AND ($3::int IS NULL OR w.mastery_level >= $3)
           AND ($4::int IS NULL OR w.mastery_level <= $4)")
        .bind(&lang).bind(p.name.as_deref())
        .bind(p.mastery_min).bind(p.mastery_max)
        .fetch_one(&state.pool).await?;

    Ok(Json(json!({
        "lang": lang,
        "filters": {
            "name": p.name,
            "mastery": { "min": p.mastery_min, "max": p.mastery_max },
        },
        "items": items, "total": total, "limit": limit, "offset": offset,
    })))
}

/// GET /api/wfm/sisters/{slug}?lang=zh
pub async fn sister_detail(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let row: Option<(String, String, Option<String>, Option<i32>,
                     Option<String>, Option<String>, Option<String>, Option<String>)> = sqlx::query_as(
        "SELECT w.wfm_id, w.slug, w.game_ref, w.mastery_level,
                w.icon, w.thumb, i.item_name, i.wiki_link
         FROM wfm_sister_weapons w LEFT JOIN wfm_sister_weapon_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE w.slug = $2"
    ).bind(&lang).bind(&slug).fetch_optional(&state.pool).await?;

    let Some(r) = row else { return Err(ApiError::NotFound(format!("未找到姐妹武器: {slug}"))); };
    let prices = fetch_wfm_top_orders(&state.pool, "sister", "sister/weapon", &slug).await;

    Ok(Json(json!({
        "wfm_id": r.0, "slug": r.1, "game_ref": r.2, "mastery_level": r.3,
        "icon": r.4, "thumb": r.5, "item_name": r.6, "wiki_link": r.7, "prices": prices,
    })))
}

// ============================================================
// 通用：从 warframe.market API 获取最优买卖订单（成功时写入当日价格快照）
// ============================================================

async fn fetch_wfm_top_orders(
    pool: &PgPool, kind: &str, endpoint: &str, slug: &str,
) -> Value {
    let client = match reqwest::Client::builder()
        .user_agent("warframe-api/1.0")
        .timeout(std::time::Duration::from_secs(10))
        .build()
    {
        Ok(c) => c,
        Err(_) => return json!(null),
    };

    let url = format!("https://api.warframe.market/v2/orders/item/{}", slug);
    let resp = match client.get(&url)
        .header("Platform", "pc")
        .header("Language", "zh-hans")
        .send().await
    {
        Ok(r) => r,
        Err(_) => return json!(null),
    };
    if !resp.status().is_success() { return json!(null); }

    let body: Value = match resp.json().await {
        Ok(b) => b,
        Err(_) => return json!(null),
    };
    // v2 API: data 是扁平数组，type 字段为 "sell"/"buy"
    let data = match body.get("data").and_then(|v| v.as_array()) {
        Some(arr) => arr,
        None => return json!(null),
    };

    let simplify = |o: &Value| -> Value {
        json!({
            "platinum": o.get("platinum").and_then(|v| v.as_i64()),
            "quantity": o.get("quantity").and_then(|v| v.as_i64()),
            "user": o.get("user").and_then(|u| u.get("ingameName")).and_then(|v| v.as_str()),
            "status": o.get("user").and_then(|u| u.get("status")).and_then(|v| v.as_str()),
        })
    };

    let sell: Vec<Value> = data.iter()
        .filter(|o| o.get("type").and_then(|v| v.as_str()) == Some("sell"))
        .map(simplify).collect();
    let buy: Vec<Value> = data.iter()
        .filter(|o| o.get("type").and_then(|v| v.as_str()) == Some("buy"))
        .map(simplify).collect();

    let sell_min = sell.iter().filter_map(|o| o.get("platinum").and_then(|v| v.as_i64())).min();
    let sell_avg = if !sell.is_empty() {
        Some(sell.iter().filter_map(|o| o.get("platinum").and_then(|v| v.as_i64())).sum::<i64>() / sell.len() as i64)
    } else { None };
    let buy_max = buy.iter().filter_map(|o| o.get("platinum").and_then(|v| v.as_i64())).max();

    // 写入当日快照（趋势数据源），失败不影响主流程
    let _ = sqlx::query(
        "INSERT INTO wfm_price_snapshots (slug, kind, day, sell_min, sell_avg, buy_max)
         VALUES ($1,$2,CURRENT_DATE,$3,$4,$5)
         ON CONFLICT (slug, kind, day) DO UPDATE
         SET sell_min = EXCLUDED.sell_min, sell_avg = EXCLUDED.sell_avg, buy_max = EXCLUDED.buy_max")
        .bind(slug).bind(kind)
        .bind(sell_min.map(|v| v as i32))
        .bind(sell_avg.map(|v| v as i32))
        .bind(buy_max.map(|v| v as i32))
        .execute(pool).await;

    json!({
        "sell": { "min": sell_min, "avg": sell_avg, "orders": sell },
        "buy": { "max": buy_max, "orders": buy },
    })
}

// ============================================================
// GET /api/wfm/auctions/{slug} —— 紫卡拍卖（wfm v1 拍卖接口）
// GET /api/wfm/spread/{slug}   —— 紫卡词条价差（同一数据聚合）
// ============================================================

async fn fetch_auctions(slug: &str) -> Result<Vec<Value>, Box<dyn std::error::Error>> {
    let client = reqwest::Client::builder()
        .user_agent("warframe-api/1.0")
        .timeout(std::time::Duration::from_secs(12))
        .build()?;

    // v1 拍卖搜索（按价格降序，在线卖家优先由 wfm 默认 in_game 过滤可选）
    let url = format!(
        "https://api.warframe.market/v1/auctions/search?type=riven&weapon_url_name={slug}&sort_by=price_desc"
    );
    let resp = client.get(&url)
        .header("Platform", "pc")
        .header("Language", "zh-hans")
        .send().await?;
    if !resp.status().is_success() { return Ok(vec![]); }

    let body: Value = resp.json().await?;
    let auctions = body.pointer("/payload/auctions")
        .and_then(|v| v.as_array()).cloned().unwrap_or_default();
    Ok(auctions)
}

fn simplify_auction(a: &Value) -> Value {
    // v1 拍卖结构：词条/等级/洗数都在 item 子对象里
    let item = a.get("item").cloned().unwrap_or(Value::Null);
    let attrs: Vec<Value> = item.get("attributes").and_then(|v| v.as_array())
        .map(|arr| arr.iter().map(|at| json!({
            "name": at.get("url_name").and_then(|x| x.as_str()),
            "value": at.get("value").and_then(|x| x.as_f64()),
            "negative": !at.get("positive").and_then(|x| x.as_bool()).unwrap_or(true),
        })).collect()).unwrap_or_default();
    let buyout = a.get("buyout_price").and_then(|v| v.as_i64());
    json!({
        "price": buyout.or_else(|| a.get("starting_price").and_then(|v| v.as_i64())),
        "buyout": buyout.is_some(),
        "top_bid": a.get("top_bid").and_then(|v| v.as_i64()),
        "rank": item.get("mod_rank").and_then(|v| v.as_i64()),
        "rerolls": item.get("re_rolls").and_then(|v| v.as_i64()),
        "mastery_level": item.get("mastery_level").and_then(|v| v.as_i64()),
        "polarity": item.get("polarity").and_then(|v| v.as_str()),
        "riven_name": item.get("name").and_then(|v| v.as_str()),
        "user": a.pointer("/owner/ingame_name").and_then(|v| v.as_str()),
        "status": a.pointer("/owner/status").and_then(|v| v.as_str()),
        "attributes": attrs,
    })
}

/// GET /api/wfm/auctions/{slug}?lang=zh&limit=20
/// 支持 wr 全语法筛选（AND）：rerolls/rank/mastery/price/pos/neg 范围、
/// attr_pos/attr_neg 词条、polarity、status。详见 doc/api/wfm-auctions.md。
pub async fn auctions(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<AuctionParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of_opt(&state, &p.lang);
    let limit = p.limit.unwrap_or(20).clamp(1, 50) as usize;
    let filter = parse_auction_filter(&p)?;
    // 校验词条 slug 合法性
    let mut chk: Vec<String> = filter.attr_pos.clone();
    chk.extend(filter.attr_neg.iter().cloned());
    chk.sort(); chk.dedup();
    validate_attr_slugs(&state.pool, &chk).await?;

    let list = fetch_auctions(&slug).await.map_err(|e| ApiError::WorldState(e.to_string()))?;

    // 1) 服务端过滤（AND）
    let mut items: Vec<Value> = list.iter()
        .map(simplify_auction)
        .filter(|a| auction_matches(a, &filter))
        .collect();
    let total = items.len();

    // 2) 排序：价格低到高（买断价优先字段为 price）
    items.sort_by_key(|a| a.get("price").and_then(|v| v.as_i64()).unwrap_or(i64::MAX));
    items.truncate(limit);

    // 3) 词条英文 slug → 中文对照
    let attr_map = attr_name_map(&state.pool, &items, &lang).await;
    for a in items.iter_mut() {
        translate_attr_names(a, &attr_map);
        // 逐条标注命中条件（须在词条翻译后，matched_conditions 需 name_zh）
        a["matched_conditions"] = Value::Array(matched_conditions(a, &filter));
    }

    // 4) 记录紫卡价格快照（kind=riven：以当前最低买断价为卖价参考）
    let prices: Vec<i64> = items.iter()
        .filter_map(|a| a.get("price").and_then(|v| v.as_i64())).collect();
    if !prices.is_empty() {
        let min = *prices.iter().min().unwrap();
        let avg = prices.iter().sum::<i64>() / prices.len() as i64;
        let _ = sqlx::query(
            "INSERT INTO wfm_price_snapshots (slug, kind, day, sell_min, sell_avg)
             VALUES ($1,'riven',CURRENT_DATE,$2,$3)
             ON CONFLICT (slug, kind, day) DO UPDATE
             SET sell_min = EXCLUDED.sell_min, sell_avg = EXCLUDED.sell_avg")
            .bind(&slug).bind(min as i32).bind(avg as i32)
            .execute(&state.pool).await;
    }

    Ok(Json(json!({
        "slug": slug, "lang": lang,
        "filters": filter.to_json(&lang),
        "total": total, "limit": limit,
        "auctions": items,
    })))
}

/// 批量查询词条 slug → 当前语言名称（复用 wfm_riven_attributes + i18n）
/// 兼容两种行结构：拍卖行（attributes 数组）与价差聚合行（顶层 attribute 键）。
async fn attr_name_map(pool: &PgPool, items: &[Value], lang: &str) -> std::collections::HashMap<String, String> {
    // 收集全部词条 slug
    let mut slugs: Vec<String> = Vec::new();
    for a in items {
        if let Some(attrs) = a.get("attributes").and_then(|v| v.as_array()) {
            for at in attrs {
                if let Some(n) = at.get("name").and_then(|v| v.as_str()) {
                    slugs.push(n.to_string());
                }
            }
        }
        if let Some(n) = a.get("attribute").and_then(|v| v.as_str()) {
            slugs.push(n.to_string());
        }
    }
    if slugs.is_empty() { return std::collections::HashMap::new(); }
    slugs.sort(); slugs.dedup();

    let rows: Vec<(String, Option<String>)> = sqlx::query_as(
        "SELECT w.slug, i.effect
         FROM wfm_riven_attributes w
         LEFT JOIN wfm_riven_attr_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $2
         WHERE w.slug = ANY($1)")
        .bind(&slugs).bind(lang)
        .fetch_all(pool).await.unwrap_or_default();

    rows.into_iter().filter_map(|(slug, eff)|
        eff.map(|e| (slug, e))).collect()
}

/// 就地给词条条目填充中文名（兼容 name / attribute 两种键；无对照时置 null）
fn translate_attr_names(a: &mut Value, map: &std::collections::HashMap<String, String>) {
    if let Some(attrs) = a.get_mut("attributes").and_then(|v| v.as_array_mut()) {
        for at in attrs.iter_mut() {
            let en = at.get("name").and_then(|v| v.as_str()).map(|s| s.to_string());
            if let Some(en) = en {
                at["name_zh"] = match map.get(&en) {
                    Some(zh) => json!(zh),
                    None => Value::Null,
                };
            }
        }
    }
    // 价差聚合行：顶层 attribute 键
    if let Some(en) = a.get("attribute").and_then(|v| v.as_str()).map(|s| s.to_string()) {
        a["attribute_zh"] = match map.get(&en) {
            Some(zh) => json!(zh),
            None => Value::Null,
        };
    }
}

/// GET /api/wfm/spread/{slug} —— 词条价差：各正面词条在挂单中的平均成交参考价
/// 支持与 /api/wfm/auctions 相同的筛选参数：先过滤拍卖样本，再对命中样本聚合。
pub async fn spread(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<AuctionParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of_opt(&state, &p.lang);
    let filter = parse_auction_filter(&p)?;
    // 校验词条 slug 合法性
    let mut chk: Vec<String> = filter.attr_pos.clone();
    chk.extend(filter.attr_neg.iter().cloned());
    chk.sort(); chk.dedup();
    validate_attr_slugs(&state.pool, &chk).await?;
    let list = fetch_auctions(&slug).await.map_err(|e| ApiError::WorldState(e.to_string()))?;
    if list.is_empty() {
        return Ok(Json(json!({
            "slug": slug, "lang": lang,
            "filters": filter.to_json(&lang),
            "samples": 0, "attributes": [],
        })));
    }

    // 1) 服务端过滤（与 auctions 同一套 AND 条件），再聚合命中样本
    let matched: Vec<Value> = list.iter()
        .map(simplify_auction)
        .filter(|a| auction_matches(a, &filter))
        .collect();

    // 2) 聚合：正面词条 → (价格和, 样本数)
    let mut agg: std::collections::HashMap<String, (i64, i64)> = std::collections::HashMap::new();
    for a in &matched {
        let price = a.get("price").and_then(|v| v.as_i64());
        let Some(price) = price else { continue };
        if let Some(attrs) = a.get("attributes").and_then(|v| v.as_array()) {
            for at in attrs {
                let negative = at.get("negative").and_then(|x| x.as_bool()).unwrap_or(false);
                if negative { continue; }
                if let Some(name) = at.get("name").and_then(|x| x.as_str()) {
                    let e = agg.entry(name.to_string()).or_insert((0, 0));
                    e.0 += price; e.1 += 1;
                }
            }
        }
    }

    let mut rows: Vec<Value> = agg.into_iter()
        .filter(|(_, (_, n))| *n >= 2)   // 至少 2 个样本才有参考意义
        .map(|(name, (sum, n))| json!({
            "attribute": name,
            "avg_price": sum / n,
            "samples": n,
        }))
        .collect();
    rows.sort_by_key(|r| -r.get("avg_price").and_then(|v| v.as_i64()).unwrap_or(0));

    // 词条英文 slug → 中文对照
    let attr_map = attr_name_map(&state.pool, &rows, &lang).await;
    for r in rows.iter_mut() {
        translate_attr_names(r, &attr_map);
    }

    Ok(Json(json!({
        "slug": slug, "lang": lang,
        "filters": filter.to_json(&lang),
        "samples": matched.len(), "attributes": rows,
    })))
}

// ============================================================
// GET /api/wfm/trends/{slug} —— 价格趋势
// 优先代理 wfm v1 官方统计（48h 小时级 + 90d 日级真实数据）；
// 上游无数据（如紫卡/赤毒/姐妹 slug）或失败时，回退本地快照表。
// ============================================================

/// 拉取 wfm 官方统计（普通物品 slug 有效；紫卡等返回 404 → None）
async fn fetch_wfm_statistics(slug: &str) -> Option<Value> {
    let client = reqwest::Client::builder()
        .user_agent("warframe-api/1.0")
        .timeout(std::time::Duration::from_secs(12))
        .build().ok()?;
    let url = format!("https://api.warframe.market/v1/items/{slug}/statistics");
    let resp = client.get(&url).header("Platform", "pc").send().await.ok()?;
    if !resp.status().is_success() { return None; }
    let body: Value = resp.json().await.ok()?;

    let simplify_row = |r: &Value| -> Value {
        json!({
            "datetime":   r.get("datetime").and_then(|v| v.as_str()),
            "avg":        r.get("avg_price").and_then(|v| v.as_f64()),
            "min":        r.get("min_price").and_then(|v| v.as_f64()),
            "max":        r.get("max_price").and_then(|v| v.as_f64()),
            "median":     r.get("median").and_then(|v| v.as_f64()),
            "moving_avg": r.get("moving_avg").and_then(|v| v.as_f64()),
            "volume":     r.get("volume").and_then(|v| v.as_i64()),
        })
    };

    let pick = |key: &str| -> Vec<Value> {
        body.pointer(&format!("/payload/statistics_closed/{key}"))
            .and_then(|v| v.as_array())
            .map(|a| a.iter().map(simplify_row).collect())
            .unwrap_or_default()
    };
    Some(json!({ "h48": pick("48hours"), "d90": pick("90days") }))
}

/// GET /api/wfm/trends/{slug}?range=90d&kind=item&lang=zh
///
/// - `source: wfm_statistics`：wfm 官方真实成交统计（48h 小时级 + 90d 日级，
///   含成交量/中位数/移动均值）。普通物品 slug 可用。
/// - `source: local_snapshots`：本地快照兜底（随详情询价/拍卖查询写入）。
///   紫卡（kind=riven）、赤毒（lich）、姐妹（sister）走此路径。
pub async fn trends(
    State(state): State<AppState>,
    Path(slug): Path<String>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    // 兼容 kind= 与 type= 两种写法
    let kind = p.r#type.as_deref().or(p.kind.as_deref()).unwrap_or("item");
    let days = p.limit.unwrap_or(30).clamp(1, 365);
    // range=48h|90d（仅上游统计源生效；kind 显式指定为非 item 时跳过上游）
    let want_48h = p.range.as_deref().map(|r| r == "48h").unwrap_or(false);

    // ---- 1) 上游官方统计（仅 item 类）----
    if kind == "item" {
        if let Some(stats) = fetch_wfm_statistics(&slug).await {
            let empty = stats.pointer("/h48").and_then(|v| v.as_array()).map_or(true, |a| a.is_empty())
                && stats.pointer("/d90").and_then(|v| v.as_array()).map_or(true, |a| a.is_empty());
            if !empty {
                let data = if want_48h {
                    json!({ "48h": stats["h48"] })
                } else {
                    json!({ "90d": stats["d90"], "48h": stats["h48"] })
                };
                return Ok(Json(json!({
                    "slug": slug,
                    "source": "wfm_statistics",
                    "data": data,
                })));
            }
        }
    }

    // ---- 2) 本地快照兜底 ----
    #[derive(sqlx::FromRow)]
    struct Row { day: String, sell_min: Option<i32>, sell_avg: Option<i32>, buy_max: Option<i32> }
    let rows: Vec<Row> = sqlx::query_as(
        "SELECT to_char(day, 'YYYY-MM-DD') AS day, sell_min, sell_avg, buy_max FROM wfm_price_snapshots
         WHERE slug = $1 AND kind = $2 AND day >= CURRENT_DATE - $3::int ORDER BY day")
        .bind(&slug).bind(kind).bind(days as i32)
        .fetch_all(&state.pool).await?;

    let points: Vec<Value> = rows.iter().map(|r| json!({
        "day": r.day,
        "sell_min": r.sell_min, "sell_avg": r.sell_avg, "buy_max": r.buy_max,
    })).collect();

    Ok(Json(json!({
        "slug": slug, "kind": kind, "days": days,
        "source": "local_snapshots",
        "points": points,
        "note": if rows.is_empty() {
            "暂无历史数据。本地快照随每次实时询价写入；普通物品建议直接用默认模式获取 wfm 官方 90 天统计。"
        } else { "" },
    })))
}

// ============================================================
// GET /api/wfm/components?tier=gold|silver|bronze —— 杜卡德部件筛选
// ============================================================

/// GET /api/wfm/components?tier=gold&lang=zh&limit=50&offset=0
pub async fn components(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let limit = p.limit.unwrap_or(50).clamp(1, 200);
    let offset = p.offset.unwrap_or(0).max(0);

    // 金垃圾=100 银垃圾=45 铜垃圾=15；不传 tier 列出全部部件
    let ducats: Option<i32> = match p.r#type.as_deref() {
        Some("gold") => Some(100),
        Some("silver") => Some(45),
        Some("bronze") => Some(15),
        _ => None,
    };

    #[derive(sqlx::FromRow)]
    struct Row { slug: String, item_name: Option<String>, ducats: Option<i32>, trading_tax: Option<i32> }
    let rows: Vec<Row> = sqlx::query_as(
        "SELECT w.slug, i.item_name, w.ducats, w.trading_tax
         FROM wfm_items w
         LEFT JOIN wfm_item_i18n i ON i.wfm_id = w.wfm_id AND i.lang = $1
         WHERE 'component' = ANY(w.tags)
           AND ($2::int IS NULL OR w.ducats = $2)
         ORDER BY w.ducats DESC NULLS LAST, w.slug LIMIT $3 OFFSET $4")
        .bind(&lang).bind(ducats).bind(limit).bind(offset)
        .fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.into_iter().map(|r| json!({
        "slug": r.slug, "item_name": r.item_name,
        "ducats": r.ducats, "trading_tax": r.trading_tax,
    })).collect();

    Ok(Json(json!({
        "tier": p.r#type.clone().unwrap_or_else(|| "all".into()),
        "items": items, "limit": limit, "offset": offset,
    })))
}

// ============================================================
// GET /api/wfm/rankings?type=warframes|weapons|mods —— 查询热度排行
// ============================================================

/// GET /api/wfm/rankings?type=warframes&lang=zh&limit=10
///
/// 数据来源为本服务自身的详情查询热度统计（api_query_stats），
/// 冷启动阶段数据为空属正常，随使用量增长。
pub async fn rankings(
    State(state): State<AppState>,
    Query(p): Query<WfmParams>,
) -> Result<Json<Value>, ApiError> {
    let lang = lang_of(&state, &p);
    let limit = p.limit.unwrap_or(10).clamp(1, 50);
    let entity_type = p.r#type.clone().unwrap_or_else(|| "warframes".into());

    #[derive(sqlx::FromRow)]
    struct Row { entity_id: String, hits: i64, name: Option<String> }
    let rows: Vec<Row> = sqlx::query_as(
        "SELECT s.entity_id, s.hits, v.value AS name
         FROM api_query_stats s
         LEFT JOIN v_localized v
           ON v.entity_id = s.entity_id AND v.lang = $1 AND v.field = 'name'
         WHERE s.entity_type = $2
         ORDER BY s.hits DESC LIMIT $3")
        .bind(&lang).bind(&entity_type).bind(limit)
        .fetch_all(&state.pool).await?;

    let items: Vec<Value> = rows.into_iter().enumerate()
        .map(|(i, r)| json!({
            "rank": i + 1,
            "entity_type": entity_type,
            "entity_id": r.entity_id,
            "name": r.name,
            "hits": r.hits,
        }))
        .collect();

    Ok(Json(json!({ "type": entity_type, "items": items })))
}
