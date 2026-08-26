//! worldstate 各节解析（design §5.1 / §3.2）
//! 注意：所有对 Resolver 的借用都在单个语句内完成并立即 await，
//! 避免闭包同时捕获 &mut Resolver 造成借用冲突。

use chrono::Utc;
use serde_json::{json, Value};
use sqlx::PgPool;

use crate::cycles::compute_cycles;
use crate::error::ApiError;
use crate::models::{to_iso, RewardItem, TierRewards};
use crate::worldstate::resolve::{resolved_json, Resolver};
use crate::worldstate::types::*;

/// 解析完整 worldstate → JSON（全部引用字段已翻译/展开）
pub async fn parse_all(
    pool: &PgPool, lang: &str, raw: RawWorldState, fetched_at: &str,
) -> Result<Value, ApiError> {
    let mut res = Resolver::new(pool, lang.to_string());
    let expand = true; // 默认完全展开

    let mut root = json!({});
    root["alerts"] = parse_alerts(&mut res, &raw.alerts).await;
    root["fissures"] = parse_fissures(&mut res, &raw.active_missions).await;
    root["void_storms"] = parse_void_storms(&mut res, &raw.void_storms).await;
    root["invasions"] = parse_invasions(&mut res, &raw.invasions).await;
    root["sortie"] = parse_sortie(&mut res, raw.sorties.first(), expand).await;
    root["void_trader"] = parse_void_trader(&mut res, raw.void_traders.first()).await;
    root["daily_deals"] = parse_daily_deals(&mut res, &raw.daily_deals).await;
    root["syndicate_missions"] = parse_syndicate_missions(&mut res, &raw.syndicate_missions, expand).await;
    root["nightwave"] = parse_nightwave(&mut res, raw.nightwave.as_ref()).await;
    root["events"] = parse_events(&mut res, &raw.events, expand).await;
    root["goals"] = parse_goals(&mut res, &raw.goals, expand).await;
    root["descents"] = parse_descents(&mut res, &raw.descents).await;
    root["persistent_enemies"] = parse_persistent_enemies(&mut res, &raw.persistent_enemies).await;
    root["conquests"] = parse_conquests(&mut res, &raw.conquests).await;
    root["cycles"] = json!(compute_cycles(Utc::now()).iter().map(|c| json!(c)).collect::<Vec<_>>());
    root["meta"] = json!({
        "source": "api.warframe.com/cdn/worldState.php",
        "fetched_at": fetched_at,
        "stale": false,
    });

    // 原样建模的透传节（news/flash_sales/global_upgrades）—— 深度翻译后输出
    for (key, val) in [
        ("news", &raw.news),
        ("flash_sales", &raw.flash_sales),
        ("global_upgrades", &raw.global_upgrades),
    ] {
        if !root.get(key).is_some() {
            let mut v = json!(val);
            translate_passthrough(&mut res, &mut v).await;
            root[key] = v;
        }
    }

    // 透传未建模节（深度翻译：枚举/物品/节点/loc tag）
    for (k, v) in &raw.extra {
        if !root.get(k).is_some() {
            let mut val = v.clone();
            translate_passthrough(&mut res, &mut val).await;
            root[k] = val;
        }
    }

    // 统一时间格式：响应内所有 Activation/Expiry（含透传节）转 UTC ISO
    normalize_times(&mut root);
    // 清理 _id 数据 + 字段名统一全小写
    lowercase_keys(&mut root);
    Ok(root)
}

/// 删除 `_id`（MongoDB ObjectId）及无用字段，并将对象键名转为全小写（递归）。
fn lowercase_keys(v: &mut Value) {
    match v {
        Value::Object(map) => {
            map.remove("_id");
            map.remove("AllianceId");
            map.remove("allianceid");
            let keys: Vec<String> = map.keys().cloned().collect();
            for k in keys {
                let lower = k.to_lowercase();
                if lower != k {
                    if let Some(val) = map.remove(&k) {
                        map.insert(lower, val);
                    }
                }
            }
            for (_, val) in map.iter_mut() {
                lowercase_keys(val);
            }
        }
        Value::Array(arr) => {
            for item in arr.iter_mut() {
                lowercase_keys(item);
            }
        }
        _ => {}
    }
}

/// 深度翻译透传节：MT_*/FC_*/SORTIE_*/VoidT* 枚举、物品路径、节点、loc tag 替换为译文/对象。
async fn translate_passthrough(res: &mut Resolver<'_>, v: &mut Value) {
    match v {
        Value::Object(map) => {
            let keys: Vec<String> = map.keys().cloned().collect();
            for k in keys {
                let val = map.get_mut(&k).expect("key exists");
                if let Some(s) = val.as_str() {
                    // 枚举（MT_/FC_/SORTIE_/VoidT）→ {code, name, translated}
                    if s.starts_with("MT_") || s.starts_with("FC_")
                        || s.starts_with("SORTIE_") || s.starts_with("VoidT")
                    {
                        let r = res.resolve(s).await;
                        *val = resolved_json(&r);
                        continue;
                    }
                    // loc tag → 译文字符串
                    if s.starts_with("/Lotus/Language/") || s.starts_with("/EE/Language/") {
                        if let Some(name) = res.loc(s).await {
                            *val = json!(name);
                            continue;
                        }
                    }
                    // 节点 ID（node 键）→ {type, name}
                    if k.eq_ignore_ascii_case("node") && is_node_id(s) {
                        if let Some(n) = res.node(s).await {
                            *val = json!({ "type": n.r#type, "name": n.name });
                            continue;
                        }
                    }
                    // 物品路径（物品类键）→ {type, name, translated}
                    if is_item_key(&k) && (s.starts_with("/Lotus/") || s.starts_with("/EE/")) {
                        if let Some((_t, name)) = res.item(s).await {
                            *val = json!({ "type": s, "name": name, "translated": name.is_some() });
                            continue;
                        }
                    }
                }
                Box::pin(translate_passthrough(res, val)).await;
            }
        }
        Value::Array(arr) => {
            for item in arr.iter_mut() {
                Box::pin(translate_passthrough(res, item)).await;
            }
        }
        _ => {}
    }
}

fn is_node_id(v: &str) -> bool {
    v.starts_with("SolNode") || v.starts_with("CrewBattleNode")
        || v.starts_with("ClanNode") || v.ends_with("HUB")
}

/// 物品类键名（其值若是 /Lotus/... 路径则翻译）
fn is_item_key(k: &str) -> bool {
    matches!(
        k,
        "Item" | "Items" | "ItemType" | "itemType" | "StoreItem" | "StoreItems"
            | "type" | "typeName" | "TypeName" | "item" | "items"
            | "Reward" | "rewards" | "UpgradeType" | "reward"
    )
}

/// 递归把 `{"$date":{"$numberLong":"..."}}` 及 `Activation/Expiry` 键转为 UTC ISO 字符串。
/// 已解析节（已是 ISO 字符串）不受影响。
fn normalize_times(v: &mut Value) {
    match v {
        Value::Object(map) => {
            // Mongo `$date` 包装 → ISO
            if let Some(d) = map.get("$date") {
                if let Some(ms) = d
                    .get("$numberLong")
                    .and_then(|n| n.as_str())
                    .and_then(|s| s.parse::<i64>().ok())
                {
                    *v = Value::String(to_iso(ms));
                    return;
                }
            }
            let keys: Vec<String> = map.keys().cloned().collect();
            for k in keys {
                let is_time_key = matches!(
                    k.as_str(),
                    "Activation" | "Expiry" | "activation" | "expiry"
                        | "Date" | "EventStartDate" | "EventEndDate" | "LastDiscoveredTime"
                );
                let val = map.get_mut(&k).expect("key exists");
                if is_time_key {
                    // epoch 毫秒/秒 → ISO（已是字符串则跳过）
                    if let Some(ms) = val.as_i64() {
                        *val = Value::String(to_iso(ms));
                        continue;
                    }
                    normalize_times(val);
                } else {
                    normalize_times(val);
                }
            }
        }
        Value::Array(arr) => {
            for item in arr.iter_mut() {
                normalize_times(item);
            }
        }
        _ => {}
    }
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------
async fn parse_alerts(res: &mut Resolver<'_>, alerts: &[RawAlert]) -> Value {
    let mut out = vec![];
    for a in alerts {
        let m = &a.mission_info;
        let node = if m.location.starts_with("SolNode")
            || m.location.starts_with("CrewBattleNode")
            || m.location.ends_with("HUB")
        {
            res.node(&m.location).await
        } else {
            None
        };
        let node = node.map(|n| json!({ "type": n.r#type, "name": n.name }));
        let mission_type = res.resolve(&m.mission_type).await;
        let faction = res.resolve(&m.faction).await;
        let reward = expand_direct(res, &m.mission_reward).await;
        let description = if let Some(t) = m.desc_text.as_deref() {
            res.loc(t).await
        } else {
            None
        };
        out.push(json!({
            "id": a.id.as_ref().and_then(|i| i.oid.clone()),
            "activation": a.activation.as_ref().and_then(|d| d.millis()).map(to_iso),
            "expiry": a.expiry.as_ref().and_then(|d| d.millis()).map(to_iso),
            "mission": {
                "node": node,
                "mission_type": resolved_json(&mission_type),
                "faction": resolved_json(&faction),
                "enemy_levels": { "min": m.min_enemy_level, "max": m.max_enemy_level },
                "reward": reward,
                "description": description,
            },
            "tag": a.tag,
        }));
    }
    json!(out)
}

// ---------------------------------------------------------------------------
// Fissures（ActiveMissions 节）/ VoidStorms
// ---------------------------------------------------------------------------
async fn parse_fissures(res: &mut Resolver<'_>, list: &[RawActiveMission]) -> Value {
    let mut out = vec![];
    for f in list {
        let node = res.node(&f.node).await;
        let mt = res.resolve(&f.mission_type).await;
        let modifier = if let Some(m) = f.modifier.as_deref() {
            let r = res.resolve(m).await;
            resolved_json(&r)
        } else {
            Value::Null
        };
        out.push(json!({
            "node": node.map(|n| json!({"type": n.r#type, "name": n.name})),
            "mission_type": resolved_json(&mt),
            "modifier": modifier,
            "hard": f.hard,
            "activation": f.activation.as_ref().and_then(|d| d.millis()).map(to_iso),
            "expiry": f.expiry.as_ref().and_then(|d| d.millis()).map(to_iso),
        }));
    }
    json!(out)
}

async fn parse_void_storms(res: &mut Resolver<'_>, list: &[RawVoidStorm]) -> Value {
    let mut out = vec![];
    for s in list {
        let node = res.node(&s.node).await;
        let tier = if let Some(t) = s.active_mission_tier.as_deref() {
            let r = res.resolve(t).await;
            resolved_json(&r)
        } else {
            Value::Null
        };
        out.push(json!({
            "node": node.map(|n| json!({"type": n.r#type, "name": n.name})),
            "tier": tier,
            "activation": s.activation.as_ref().and_then(|d| d.millis()).map(to_iso),
            "expiry": s.expiry.as_ref().and_then(|d| d.millis()).map(to_iso),
        }));
    }
    json!(out)
}

// ---------------------------------------------------------------------------
// Invasions
// ---------------------------------------------------------------------------
async fn parse_invasions(res: &mut Resolver<'_>, list: &[RawInvasion]) -> Value {
    let mut out = vec![];
    for inv in list {
        let node = res.node(&inv.node).await;
        let desc = if let Some(t) = inv.loc_tag.as_deref() { res.loc(t).await } else { None };
        let attacker_faction = if let Some(f) = inv.attacker_mission_info.as_ref() {
            let r = res.resolve(&f.faction).await;
            resolved_json(&r)
        } else {
            Value::Null
        };
        let defender_faction = if let Some(f) = inv.defender_mission_info.as_ref() {
            let r = res.resolve(&f.faction).await;
            resolved_json(&r)
        } else {
            Value::Null
        };
        let attacker_reward = expand_direct(res, &inv.attacker_reward).await;
        let defender_reward = expand_direct(res, &inv.defender_reward).await;
        out.push(json!({
            "node": node.map(|n| json!({"type": n.r#type, "name": n.name})),
            "description": desc,
            "attacker": { "faction": attacker_faction, "reward": attacker_reward },
            "defender": { "faction": defender_faction, "reward": defender_reward },
            "count": inv.count,
            "goal": inv.goal,
            "completed": inv.completed,
            "activation": inv.activation.as_ref().and_then(|d| d.millis()).map(to_iso),
        }));
    }
    json!(out)
}

// ---------------------------------------------------------------------------
// Sortie
// ---------------------------------------------------------------------------
async fn parse_sortie(res: &mut Resolver<'_>, s: Option<&RawSortie>, expand: bool) -> Value {
    let Some(s) = s else { return Value::Null };
    let boss = if let Some(b) = s.boss.as_deref() {
        let r = res.resolve(b).await;
        resolved_json(&r)
    } else {
        Value::Null
    };
    let reward = expand_deck_ref(res, s.reward.as_deref(), expand).await;
    let mut variants = vec![];
    for v in &s.variants {
        let node = res.node(&v.node).await;
        let mt = res.resolve(&v.mission_type).await;
        let modf = if let Some(m) = v.modifier_type.as_deref() {
            let r = res.resolve(m).await;
            resolved_json(&r)
        } else {
            Value::Null
        };
        variants.push(json!({
            "node": node.map(|n| json!({"type": n.r#type, "name": n.name})),
            "mission_type": resolved_json(&mt),
            "modifier_type": modf,
        }));
    }
    json!({
        "boss": boss,
        "reward": reward,
        "variants": variants,
        "activation": s.activation.as_ref().and_then(|d| d.millis()).map(to_iso),
        "expiry": s.expiry.as_ref().and_then(|d| d.millis()).map(to_iso),
    })
}

// ---------------------------------------------------------------------------
// VoidTrader / DailyDeals
// ---------------------------------------------------------------------------
async fn parse_void_trader(res: &mut Resolver<'_>, vt: Option<&RawVoidTrader>) -> Value {
    let Some(vt) = vt else {
        return json!({
            "character": "Baro Ki'Teer", "status": "absent",
            "node": null, "manifest": [],
            "activation": null, "expiry": null,
        });
    };
    let node = res.node(&vt.node).await;
    let mut manifest = vec![];
    for it in &vt.manifest {
        let name = res.resolve_item_name(&it.item_type).await;
        manifest.push(json!({
            "type": it.item_type,
            "item_name": name,
            "prime_price": it.prime_price,
            "regular_price": it.regular_price,
        }));
    }
    json!({
        "character": vt.character,
        "node": node.map(|n| json!({"type": n.r#type, "name": n.name})),
        "manifest": manifest,
        "activation": vt.activation.as_ref().and_then(|d| d.millis()).map(to_iso),
        "expiry": vt.expiry.as_ref().and_then(|d| d.millis()).map(to_iso),
    })
}

async fn parse_daily_deals(res: &mut Resolver<'_>, list: &[RawDailyDeal]) -> Value {
    let mut out = vec![];
    for d in list {
        let item_name = res.resolve_item_name(&d.store_item).await;
        out.push(json!({
            "store_item": d.store_item,
            "item_name": item_name,
            "discount": d.discount,
            "original_price": d.original_price,
            "sale_price": d.sale_price,
            "activation": d.activation.as_ref().and_then(|x| x.millis()).map(to_iso),
            "expiry": d.expiry.as_ref().and_then(|x| x.millis()).map(to_iso),
        }));
    }
    json!(out)
}

// ---------------------------------------------------------------------------
// SyndicateMissions
// ---------------------------------------------------------------------------
async fn parse_syndicate_missions(res: &mut Resolver<'_>, list: &[RawSyndicateMission], expand: bool) -> Value {
    let mut out = vec![];
    for sm in list {
        let mut nodes = vec![];
        for n in &sm.nodes {
            if let Some(nn) = res.node(n).await {
                nodes.push(json!({ "type": nn.r#type, "name": nn.name }));
            }
        }
        let mut jobs = vec![];
        for j in &sm.jobs {
            jobs.push(json!({
                "job_type": j.job_type,
                "rewards": expand_deck_ref(res, j.rewards.as_deref(), expand).await,
                "min_enemy_level": j.min_enemy_level,
                "max_enemy_level": j.max_enemy_level,
                "xp_amounts": j.xp_amounts,
            }));
        }
        out.push(json!({ "tag": sm.tag, "nodes": nodes, "jobs": jobs }));
    }
    json!(out)
}

// ---------------------------------------------------------------------------
// Nightwave
// ---------------------------------------------------------------------------
async fn parse_nightwave(res: &mut Resolver<'_>, nw: Option<&RawNightwave>) -> Value {
    let Some(nw) = nw else { return Value::Null };
    let mut challenges = vec![];
    for (key, c) in &nw.challenges {
        let name = if let Some(t) = c.name.as_deref() { res.loc(t).await } else { None };
        let description = if let Some(t) = c.description.as_deref() { res.loc(t).await } else { None };
        let tip = if let Some(t) = c.tip.as_deref() { res.loc(t).await } else { None };
        challenges.push(json!({
            "key": key,
            "name": name,
            "description": description,
            "standing": c.standing,
            "required": c.required,
            "icon": c.icon,
            "tip": tip,
            "tip_icon": c.tip_icon,
        }));
    }
    let mut rewards = vec![];
    for r in &nw.rewards {
        rewards.push(json!({
            "unique_name": r.unique_name,
            "name": r.name,
            "description": r.description,
            "icon": r.icon,
            "item_count": r.item_count,
        }));
    }
    json!({ "affiliation_tag": nw.affiliation_tag, "challenges": challenges, "rewards": rewards })
}

// ---------------------------------------------------------------------------
// Events / Goals / Descents / PersistentEnemy
// ---------------------------------------------------------------------------
async fn parse_events(res: &mut Resolver<'_>, list: &[RawEvent], expand: bool) -> Value {
    // 真实 worldstate 的 Events 节是 News（Messages/Icon 等，无 desc/reward）；
    // 含活动特征（desc/reward/jobs/tool_tip）时才按活动解析。
    let is_news = list.iter().all(|e| {
        e.desc.is_none() && e.reward.is_none() && e.tool_tip.is_none() && e.jobs.is_empty()
    });
    if is_news {
        let lang = res.lang.clone();
        let mut out = vec![];
        for e in list {
            let mut obj = json!(e.extra);
            // 筛选 messages 数组，只保留 languagecode 匹配当前语言的条目
            if obj.get("Messages").is_some() || obj.get("messages").is_some() {
                let key = if obj.get("Messages").is_some() { "Messages" } else { "messages" };
                if let Some(msgs) = obj.get_mut(key).unwrap().as_array_mut() {
                    msgs.retain(|m| {
                        m.get("LanguageCode")
                            .or_else(|| m.get("languagecode"))
                            .and_then(|v| v.as_str())
                            .map(|c| c.eq_ignore_ascii_case(&lang))
                            .unwrap_or(false)
                    });
                }
            }
            translate_passthrough(res, &mut obj).await;
            out.push(obj);
        }
        return json!(out);
    }
    let mut out = vec![];
    for e in list {
        let node = if let Some(n) = e.node.as_deref() {
            res.node(n).await.map(|n| json!({ "type": n.r#type, "name": n.name }))
        } else {
            None
        };
        let desc = if let Some(t) = e.desc.as_deref() { res.loc(t).await } else { None };
        let tooltip = if let Some(t) = e.tool_tip.as_deref() { res.loc(t).await } else { None };
        let faction = if let Some(f) = e.faction.as_deref() {
            let r = res.resolve(f).await;
            resolved_json(&r)
        } else {
            Value::Null
        };
        let mut jobs = vec![];
        for j in &e.jobs {
            jobs.push(json!({
                "job_type": j.job_type,
                "rewards": expand_deck_ref(res, j.rewards.as_deref(), expand).await,
            }));
        }
        out.push(json!({
            "description": desc,
            "tooltip": tooltip,
            "node": node,
            "faction": faction,
            "score_loc_tag": e.score_loc_tag,
            "reward": expand_direct(res, &e.reward).await,
            "tag": e.tag,
            "jobs": jobs,
            "activation": e.activation.as_ref().and_then(|d| d.millis()).map(to_iso),
            "expiry": e.expiry.as_ref().and_then(|d| d.millis()).map(to_iso),
        }));
    }
    json!(out)
}

async fn parse_goals(res: &mut Resolver<'_>, list: &[RawGoal], _expand: bool) -> Value {
    let mut out = vec![];
    for g in list {
        let node = if let Some(n) = g.node.as_deref() {
            res.node(n).await.map(|n| json!({ "type": n.r#type, "name": n.name }))
        } else {
            None
        };
        let desc = if let Some(t) = g.desc.as_deref() { res.loc(t).await } else { None };
        let tooltip = if let Some(t) = g.tool_tip.as_deref() { res.loc(t).await } else { None };
        out.push(json!({
            "description": desc,
            "tooltip": tooltip,
            "node": node,
            "score_loc_tag": g.score_loc_tag,
            "reward": expand_direct(res, &g.reward).await,
            "tag": g.tag,
            "activation": g.activation.as_ref().and_then(|d| d.millis()).map(to_iso),
            "expiry": g.expiry.as_ref().and_then(|d| d.millis()).map(to_iso),
        }));
    }
    json!(out)
}

/// Descents（Descendia）挑战翻译。
/// 翻译来源：worldstate_enums 表（descent_type / descent_challenge / descent_level / descent_specs / descent_aura）。
async fn parse_descents(res: &mut Resolver<'_>, list: &[RawDescent]) -> Value {
    let mut out = vec![];
    for d in list {
        let mut challenges = Vec::new();
        for c in &d.challenges {
            let level_short = c.level.as_ref().map(|l| {
                let short = l.rsplit('/').next().unwrap_or(l);
                short.strip_suffix(".level").unwrap_or(short).to_string()
            });
            // level_short → descent_level 翻译
            let level_name = if let Some(ref short) = level_short {
                res.enum_name("descent_level", short).await
            } else {
                None
            };
            let type_name = if let Some(ref code) = c.r#type {
                res.enum_name("descent_type", code).await
            } else {
                None
            };
            let type_desc = if let Some(ref code) = c.r#type {
                res.enum_desc("descent_type", code).await.unwrap_or_default()
            } else {
                String::new()
            };
            let challenge_name = if let Some(ref code) = c.challenge {
                res.enum_name("descent_challenge", code).await
            } else {
                None
            };
            let challenge_desc = if let Some(ref code) = c.challenge {
                res.enum_desc("descent_challenge", code).await.unwrap_or_default()
            } else {
                String::new()
            };
            // Specs：EnemySpec 路径末段 → descent_specs 翻译
            let mut specs_out = Vec::new();
            for spec in &c.specs {
                let key = spec.rsplit('/').next().unwrap_or(spec);
                let name = res.enum_name("descent_specs", key).await;
                specs_out.push(json!({ "type": spec, "name": name }));
            }
            // Auras：Complications 路径末段 → descent_aura 翻译
            let mut auras_out = Vec::new();
            for aura in &c.auras {
                let key = aura.rsplit('/').next().unwrap_or(aura);
                let name = res.enum_name("descent_aura", key).await;
                auras_out.push(json!({ "type": aura, "name": name }));
            }
            challenges.push(json!({
                "index": c.r#type.as_ref().map(|_| ()),  // placeholder, real index from JSON
                "type": c.r#type,
                "type_name": type_name,
                "type_desc": type_desc,
                "challenge": c.challenge,
                "challenge_name": challenge_name,
                "challenge_desc": challenge_desc,
                "specs": specs_out,
                "auras": auras_out,
            }));
        }
        out.push(json!({
            "challenges": challenges,
            "activation": d.activation.as_ref().and_then(|x| x.millis()).map(to_iso),
            "expiry": d.expiry.as_ref().and_then(|x| x.millis()).map(to_iso),
        }));
    }
    json!(out)
}

async fn parse_persistent_enemies(res: &mut Resolver<'_>, list: &[RawPersistentEnemy]) -> Value {
    let mut out = vec![];
    for p in list {
        let agent = if let Some(a) = p.agent_type.as_deref() {
            let r = res.resolve(a).await;
            resolved_json(&r)
        } else {
            Value::Null
        };
        let loc = if let Some(t) = p.loc_tag.as_deref() { res.loc(t).await } else { None };
        let last_node = if let Some(n) = p.last_discovered_location.as_deref() {
            res.node(n).await.map(|n| json!({ "type": n.r#type, "name": n.name }))
        } else {
            None
        };
        out.push(json!({
            "agent_type": agent,
            "location_tag": loc,
            "last_discovered_location": last_node,
            "rank": p.rank,
            "health_percent": p.health_percent,
            "activation": p.activation.as_ref().and_then(|d| d.millis()).map(to_iso),
            "expiry": p.expiry.as_ref().and_then(|d| d.millis()).map(to_iso),
        }));
    }
    json!(out)
}

// ---------------------------------------------------------------------------
// Rewards 展开（design §3.2）
// ---------------------------------------------------------------------------
/// 形态 A：直接奖励列表 → RewardItem[]
async fn expand_direct(res: &mut Resolver<'_>, reward: &Option<RawReward>) -> Vec<RewardItem> {
    let mut out = vec![];
    let Some(r) = reward else { return out };
    for it in &r.items {
        let name = res.resolve_item_name(it).await;
        out.push(RewardItem {
            r#type: it.clone(), item_count: 1, item_name: name,
            probability: None, rarity: None, translated: true,
        });
    }
    for c in &r.counted_items {
        let name = res.resolve_item_name(&c.item_type).await;
        out.push(RewardItem {
            r#type: c.item_type.clone(), item_count: c.item_count, item_name: name,
            probability: None, rarity: None, translated: true,
        });
    }
    if let Some(c) = r.credits {
        out.push(RewardItem {
            r#type: "credits".into(), item_count: c, item_name: Some("星币".into()),
            probability: None, rarity: None, translated: true,
        });
    }
    if let Some(x) = r.xp {
        out.push(RewardItem {
            r#type: "xp".into(), item_count: x, item_name: Some("经验".into()),
            probability: None, rarity: None, translated: true,
        });
    }
    out
}

/// 形态 B：deck 引用 → { deck, deck_name, tiers[] }（expand=false 时无 tiers）
async fn expand_deck_ref(res: &mut Resolver<'_>, deck: Option<&str>, expand: bool) -> Value {
    let Some(deck) = deck else { return Value::Null };
    let tiers: Option<Vec<TierRewards>> = match res.expand_deck(deck).await {
        Ok(t) => t,
        Err(_) => None,
    };
    let deck_name = deck.rsplit('/').next().unwrap_or(deck).to_string();
    let mut obj = json!({ "deck": deck, "deck_name": deck_name });
    if expand {
        obj["tiers"] = match tiers {
            Some(t) => json!(t),
            None => json!([]),
        };
    }
    obj
}

// ---------------------------------------------------------------------------
// Conquests (科研任务)
// ---------------------------------------------------------------------------
async fn parse_conquests(res: &mut Resolver<'_>, list: &[RawConquest]) -> Value {
    let mut out = vec![];
    for cq in list {
        let cq_type = cq.r#type.as_deref().unwrap_or("");
        let type_zh = res.enum_name("archimedea_type", cq_type).await;
        let mut missions = vec![];
        for m in &cq.missions {
            let fac = m.faction.as_deref().unwrap_or("");
            let mt = m.mission_type.as_deref().unwrap_or("");
            let fac_zh = res.enum_name("faction", fac).await;
            let mt_zh = res.enum_name("mission_type", mt).await;
            let mut diffs = vec![];
            for d in &m.difficulties {
                let dt = d.diff_type.as_deref().unwrap_or("");
                let dt_zh = res.enum_name("archimedea_difficulty", dt).await;
                let dev = d.deviation.as_deref().unwrap_or("");
                let dev_zh = res.enum_name("archimedea_deviation", dev).await;
                let dev_desc = res.enum_desc("archimedea_deviation", dev).await.unwrap_or_default();
                let mut risk_zh_list = vec![];
                for r in &d.risks {
                    let rzh = res.enum_name("archimedea_risk", r).await.unwrap_or_else(|| r.clone());
                    let rdesc = res.enum_desc("archimedea_risk", r).await.unwrap_or_default();
                    risk_zh_list.push(json!({"name": rzh, "desc": rdesc}));
                }
                diffs.push(json!({
                    "type": dt, "type_zh": dt_zh,
                    "deviation": dev, "deviation_zh": dev_zh, "deviation_desc": dev_desc,
                    "risks": d.risks, "risks_zh": risk_zh_list,
                }));
            }
            missions.push(json!({
                "faction": fac, "faction_zh": fac_zh,
                "mission_type": mt, "mission_type_zh": mt_zh,
                "difficulties": diffs,
            }));
        }
        out.push(json!({
            "type": cq_type, "type_zh": type_zh,
            "missions": missions,
            "variables": cq.variables,
        }));
    }
    json!(out)
}
