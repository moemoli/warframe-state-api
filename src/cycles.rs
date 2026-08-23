//! 世界循环本地计算（design §2.2 / §11）
//! 时长/锚点来源：Fandom Wiki 与 warframe-worldstate-parser 实现核对，可调。

use chrono::{DateTime, TimeZone, Utc};

use crate::models::{human_remaining, to_iso_sec, CycleInfo};

/// 循环定义
struct CycleDef {
    name: &'static str,
    zh: &'static str,
    /// 锚点（unix 秒）
    anchor: i64,
    /// 状态分段（顺序循环）
    segments: &'static [(&'static str, i64)],
}

/// 状态中文映射
fn state_zh(name: &str, state: &str) -> String {
    let zh = match (name, state) {
        (_, "day") => "白天",
        (_, "night") => "夜晚",
        (_, "warm") => "温暖",
        (_, "cold") => "寒冷",
        (_, "fass") => "Fass",
        (_, "vome") => "Vome",
        (_, "corpus") => "Corpus",
        (_, "grineer") => "Grineer",
        (_, "sorrow") => "悲伤",
        (_, "fear") => "恐惧",
        (_, "joy") => "喜悦",
        (_, "anger") => "愤怒",
        (_, "envy") => "嫉妒",
        _ => state,
    };
    zh.to_string()
}

/// 计算某循环当前状态 → (state, activation_sec, expiry_sec)
fn segment_at<'a>(now: i64, anchor: i64, segments: &'a [(&'a str, i64)]) -> (&'a str, i64, i64) {
    let total: i64 = segments.iter().map(|(_, s)| s).sum();
    let elapsed = (now - anchor).rem_euclid(total);
    let mut acc = 0i64;
    for (st, len) in segments {
        if elapsed < acc + len {
            let start = now - (elapsed - acc);
            return (st, start, start + len);
        }
        acc += len;
    }
    let (st, len) = segments[0];
    let start = now - elapsed;
    (st, start, start + len)
}

fn cycle_info(name: &str, zh: &str, state: &str, act: i64, exp: i64, now: i64) -> CycleInfo {
    CycleInfo {
        name: name.to_string(),
        name_zh: zh.to_string(),
        state: state.to_string(),
        state_name: state_zh(name, state),
        activation: to_iso_sec(act),
        expiry: to_iso_sec(exp),
        remaining_seconds: (exp - now).max(0),
        remaining: human_remaining(exp - now),
    }
}

/// 当前全部世界循环（UTC）
pub fn compute_cycles(now: DateTime<Utc>) -> Vec<CycleInfo> {
    let now_sec = now.timestamp();

    // cetus（夜灵平原）：day 6000s / night 3000s，总 9000s
    let cetus = CycleDef { name: "cetus", zh: "夜灵平原", anchor: 1_704_067_200, segments: &[("day", 6000), ("night", 3000)] };
    let (cs, ca, ce) = segment_at(now_sec, cetus.anchor, cetus.segments);

    // earth（地球星图昼夜）：day 4h / night 4h，总 8h（对齐 epoch）
    let earth = CycleDef { name: "earth", zh: "地球", anchor: 0, segments: &[("day", 14400), ("night", 14400)] };
    let (es, ea, ee) = segment_at(now_sec, earth.anchor, earth.segments);

    // cambion：与 cetus 同步（cetus 白天=fass / 夜晚=vome）
    let cambion_state = if cs == "day" { "fass" } else { "vome" };

    // vallis：warm 400s / cold 1200s，总 1600s，锚点 2026-02-04T19:46:48Z
    let vallis = CycleDef { name: "vallis", zh: "奥布山谷", anchor: 1_769_790_408, segments: &[("warm", 400), ("cold", 1200)] };
    let (vs, va, ve) = segment_at(now_sec, vallis.anchor, vallis.segments);

    // zariman：corpus 9000s / grineer 9000s，总 18000s，锚点 2022-06-14T05:00:00Z
    let zariman = CycleDef { name: "zariman", zh: "扎里曼", anchor: 1_655_182_800, segments: &[("corpus", 9000), ("grineer", 9000)] };
    let (zs, za, ze) = segment_at(now_sec, zariman.anchor, zariman.segments);

    // duviri：sorrow/fear/joy/anger/envy 各 7200s，总 36000s
    let duviri = CycleDef { name: "duviri", zh: "双衍王境", anchor: 52, segments: &[("sorrow", 7200), ("fear", 7200), ("joy", 7200), ("anger", 7200), ("envy", 7200)] };
    let (ds, da, de) = segment_at(now_sec, duviri.anchor, duviri.segments);

    // midrath：day 1920s / night 960s，总 2880s，锚点 2025-08-07T16:05:29Z
    let midrath = CycleDef { name: "midrath", zh: "Midrath", anchor: 1_754_068_208, segments: &[("day", 1920), ("night", 960)] };
    let (ms, ma, me) = segment_at(now_sec, midrath.anchor, midrath.segments);

    vec![
        cycle_info("cetus", cetus.zh, cs, ca, ce, now_sec),
        cycle_info("earth", earth.zh, es, ea, ee, now_sec),
        cycle_info("cambion", "火卫二", cambion_state, ca, ce, now_sec),
        cycle_info("vallis", vallis.zh, vs, va, ve, now_sec),
        cycle_info("zariman", zariman.zh, zs, za, ze, now_sec),
        cycle_info("duviri", duviri.zh, ds, da, de, now_sec),
        cycle_info("midrath", midrath.zh, ms, ma, me, now_sec),
    ]
}

/// 单个循环查询
pub fn cycle_by_name(now: DateTime<Utc>, name: &str) -> Option<CycleInfo> {
    compute_cycles(now).into_iter().find(|c| c.name == name)
}

/// 供测试：给定 unix 秒计算
pub fn compute_cycles_at(unix_sec: i64) -> Vec<CycleInfo> {
    compute_cycles(Utc.timestamp_opt(unix_sec, 0).single().unwrap_or_else(Utc::now))
}
