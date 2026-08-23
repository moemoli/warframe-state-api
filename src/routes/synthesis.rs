//! GET /api/synthesis —— 结合仪式目标地点汇总（每日任务 + 铭刻）
//!
//! 数据为社区整理的静态参考表：
//! - 若星球节点正在被入侵，敌人派系可能变化，导致不出现结合目标；
//! - 部分地点与特定地图板块有关，结合目标可能不出现。

use axum::extract::Query;
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::error::ApiError;

/// 每日结合任务（节点, 星球, 任务类型, 目标列表）
const DAILY: &[(&str, &str, &str, &[&str])] = &[
    ("LEX", "谷神星", "捕获", &[
        "枪兵", "恶徒", "禁卫军", "开膛者", "重型机枪手",
        "追踪者", "天蝎", "轰击者", "骑兵", "弩炮",
    ]),
    ("CASSINI", "土星", "捕获", &[
        "火焰轰击者", "怒焚者", "盾枪兵", "屠夫", "爪喀驯兽师",
    ]),
    ("SORATHR", "欧罗巴", "劫持", &[
        "逆进恐鸟", "德特昂船员",
    ]),
    ("TIKAL", "地球", "挖掘", &[
        "狂奔者", "病变虫母", "疾冲者", "奔跳者", "远古干扰者",
        "爬行者", "痛裂者", "异融胞群恐鸟",
    ]),
    ("神后塔", "虚空", "捕获", &[
        "远古堕落者", "堕落枪兵", "堕落屠夫", "堕落船员", "堕落重型机枪手",
    ]),
    ("母神塔", "虚空", "歼灭", &[
        "堕落轰击者", "堕落虚能者",
    ]),
];

/// 结合仪式铭刻（目标 → 推荐地点）
const IMPRINTS: &[(&str, &str)] = &[
    ("枪兵",       "LEX（谷神星捕获）"),
    ("逆进恐鸟",   "SORATHR（欧罗巴劫持）"),
    ("沙漠开膛者", "ARA（火星捕获）"),
    ("远古堕落者", "神后塔（虚空捕获）"),
    ("德特昂船员", "NESO（海王星歼灭）"),
    ("狂奔者",     "TIKAL（地球挖掘）"),
    ("禁卫军",     "LEX（谷神星捕获）"),
];

/// GET /api/synthesis?type=daily|imprints&target=火焰轰击者
#[derive(Debug, Deserialize)]
pub struct SynthesisParams {
    /// daily = 每日任务；imprints = 结合仪式铭刻；缺省返回全部
    r#type: Option<String>,
    /// 按目标名筛选（子串匹配，大小写不敏感）：反查该目标出现的地点。
    /// 命中时仅返回 daily/imprints 中匹配的条目，并在各条目附 matched 字段。
    target: Option<String>,
}

pub async fn get(
    Query(p): Query<SynthesisParams>,
) -> Result<Json<Value>, ApiError> {
    let want_daily = p.r#type.as_deref().map(|t| t != "imprints").unwrap_or(true);
    let want_imprints = p.r#type.as_deref().map(|t| t != "daily").unwrap_or(true);

    // 目标筛选（子串、忽略大小写）
    let filter = p.target.as_deref().map(|t| t.trim().to_lowercase()).filter(|t| !t.is_empty());
    let hit = |name: &str| -> bool {
        match &filter {
            Some(f) => name.to_lowercase().contains(f),
            None => true,
        }
    };

    let mut daily: Vec<Value> = if want_daily {
        DAILY.iter().filter_map(|(node, system, mission, targets)| {
            // 节点/星球/任务名也可作为筛选对象
            let node_hit = hit(node) || hit(system) || hit(mission);
            let matched: Vec<&str> = targets.iter().filter(|t| hit(t)).cloned().collect();
            if !node_hit && matched.is_empty() { return None; }
            let shown: Vec<&str> = if filter.is_some() && !matched.is_empty() { matched } else { targets.to_vec() };
            Some(json!({
                "node": node,
                "system": system,
                "mission": mission,
                "targets": shown,
                "matched": !filter.is_none(),
            }))
        }).collect()
    } else { vec![] };

    let imprints: Vec<Value> = if want_imprints {
        IMPRINTS.iter().filter_map(|(target, location)| {
            if !hit(target) && !hit(location) { return None; }
            Some(json!({ "target": target, "location": location }))
        }).collect()
    } else { vec![] };

    // 目标筛选时按"目标→地点"视图输出，更直观
    let by_target: Value = if filter.is_some() {
        let mut m: std::collections::BTreeMap<String, Vec<String>> = std::collections::BTreeMap::new();
        for (node, system, mission, targets) in DAILY {
            for t in *targets {
                if hit(t) {
                    m.entry(t.to_string()).or_default()
                        .push(format!("{node}（{system}{mission}）"));
                }
            }
        }
        for (target, location) in IMPRINTS {
            if hit(target) {
                m.entry(target.to_string()).or_default()
                    .push((*location).to_string());
            }
        }
        // 去重（同一目标可能在每日任务与铭刻中出现同一地点）
        for locs in m.values_mut() {
            locs.sort();
            locs.dedup();
        }
        json!(m)
    } else { Value::Null };

    if filter.is_some() && daily.is_empty() && imprints.is_empty() {
        return Err(ApiError::NotFound(format!(
            "未找到结合目标: {}（注意：名字需与游戏内一致）",
            p.target.as_deref().unwrap_or(""))));
    }

    Ok(Json(json!({
        "type": p.r#type.clone().unwrap_or_else(|| "all".into()),
        "target_query": p.target.clone(),
        "by_target": by_target,
        "daily": daily,
        "imprints": imprints,
        "notes": [
            "若星球对应节点正在被入侵，敌人派系和种类有可能改变，导致不出现结合仪式目标。",
            "部分地点与特定地图板块有关，结合仪式目标可能不出现。"
        ],
        "source": "社区整理静态数据，游戏内实际刷新以当日为准",
    })))
}
