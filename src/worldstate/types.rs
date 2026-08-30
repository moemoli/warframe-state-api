//! 官方 worldstate JSON 原始结构（serde，按 2026 版实测键）

use std::collections::HashMap;

use serde::Deserialize;
use serde_json::Value;

/// 顶层：官方键均为 PascalCase（Alerts/ActiveMissions/...）
#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "PascalCase")]
pub struct RawWorldState {
    #[serde(default)]
    pub time: Option<i64>,
    #[serde(default)]
    pub alerts: Vec<RawAlert>,
    #[serde(default)]
    pub events: Vec<RawEvent>,
    #[serde(default)]
    pub goals: Vec<RawGoal>,
    #[serde(default)]
    pub sorties: Vec<RawSortie>,
    #[serde(default)]
    pub active_missions: Vec<RawActiveMission>,
    #[serde(default)]
    pub void_storms: Vec<RawVoidStorm>,
    #[serde(default)]
    pub invasions: Vec<RawInvasion>,
    #[serde(default)]
    pub void_traders: Vec<RawVoidTrader>,
    #[serde(default)]
    pub daily_deals: Vec<RawDailyDeal>,
    #[serde(default)]
    pub syndicate_missions: Vec<RawSyndicateMission>,
    #[serde(default)]
    pub nightwave: Option<RawNightwave>,
    #[serde(default)]
    pub descents: Vec<RawDescent>,
    #[serde(default)]
    pub persistent_enemies: Vec<RawPersistentEnemy>,
    #[serde(default)]
    pub news: Vec<Value>,
    #[serde(default)]
    pub flash_sales: Vec<Value>,
    #[serde(default)]
    pub global_upgrades: Vec<Value>,
    #[serde(default)]
    pub conquests: Vec<RawConquest>,
    /// 未建模节原样保留
    #[serde(flatten)]
    pub extra: HashMap<String, Value>,
}

// ---- MongoDB 风格包装 ----
#[derive(Debug, Deserialize)]
pub struct RawDate {
    #[serde(rename = "$date")]
    pub date: RawNumberLong,
}
#[derive(Debug, Deserialize)]
pub struct RawNumberLong {
    #[serde(rename = "$numberLong")]
    pub value: String,
}
#[derive(Debug, Deserialize)]
pub struct RawId {
    #[serde(rename = "$oid")]
    pub oid: Option<String>,
}

impl RawDate {
    /// epoch 毫秒
    pub fn millis(&self) -> Option<i64> {
        self.date.value.parse::<i64>().ok()
    }
}

// ---- 奖励 ----
#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct RawReward {
    #[serde(default)]
    pub items: Vec<String>,
    #[serde(default)]
    pub counted_items: Vec<RawCountedItem>,
    #[serde(default)]
    pub credits: Option<i64>,
    #[serde(default)]
    pub xp: Option<i64>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawCountedItem {
    pub item_type: String,
    pub item_count: i64,
}

// ---- 任务信息（Alerts/Sortie.Missions/Events 共用） ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RawMissionInfo {
    pub location: String,
    pub mission_type: String,
    pub faction: String,
    #[serde(default)]
    pub mission_reward: Option<RawReward>,
    #[serde(default)]
    pub min_enemy_level: Option<i64>,
    #[serde(default)]
    pub max_enemy_level: Option<i64>,
    #[serde(default)]
    pub desc_text: Option<String>,
    #[serde(flatten)]
    pub extra: HashMap<String, Value>,
}

// ---- Alerts ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawAlert {
    #[serde(rename = "_id")]
    #[serde(default)]
    pub id: Option<RawId>,
    pub activation: Option<RawDate>,
    pub expiry: Option<RawDate>,
    pub mission_info: RawMissionInfo,
    #[serde(default)]
    pub tag: Option<String>,
}

// ---- Fissures（ActiveMissions 节） / VoidStorms ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawActiveMission {
    pub node: String,
    pub mission_type: String,
    #[serde(default)]
    pub modifier: Option<String>,
    #[serde(default)]
    pub hard: Option<bool>,
    pub activation: Option<RawDate>,
    pub expiry: Option<RawDate>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawVoidStorm {
    pub node: String,
    #[serde(default)]
    pub mission_type: Option<String>,
    #[serde(default)]
    pub active_mission_tier: Option<String>,
    pub activation: Option<RawDate>,
    pub expiry: Option<RawDate>,
}

// ---- Sortie ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawSortie {
    #[serde(default)]
    pub reward: Option<String>,
    #[serde(default)]
    pub boss: Option<String>,
    #[serde(default)]
    pub variants: Vec<RawSortieVariant>,
    #[serde(default)]
    pub missions: Vec<RawMissionInfo>,
    pub activation: Option<RawDate>,
    pub expiry: Option<RawDate>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RawSortieVariant {
    pub mission_type: String,
    #[serde(default)]
    pub modifier_type: Option<String>,
    pub node: String,
}

// ---- Invasion ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawInvasion {
    pub node: String,
    #[serde(default)]
    pub loc_tag: Option<String>,
    #[serde(default)]
    pub faction: Option<String>,
    #[serde(default)]
    pub defender_faction: Option<String>,
    #[serde(default)]
    pub attacker_mission_info: Option<RawFactionInfo>,
    #[serde(default)]
    pub defender_mission_info: Option<RawFactionInfo>,
    #[serde(default)]
    pub attacker_reward: Option<RawReward>,
    #[serde(default)]
    pub defender_reward: Option<RawReward>,
    #[serde(default)]
    pub count: Option<i64>,
    #[serde(default)]
    pub goal: Option<i64>,
    #[serde(default)]
    pub completed: Option<bool>,
    pub activation: Option<RawDate>,
}
#[derive(Debug, Deserialize)]
pub struct RawFactionInfo {
    pub faction: String,
}

// ---- VoidTrader / DailyDeal ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawVoidTrader {
    #[serde(default)]
    pub character: Option<String>,
    pub node: String,
    #[serde(default)]
    pub manifest: Vec<RawVoidTraderItem>,
    pub activation: Option<RawDate>,
    pub expiry: Option<RawDate>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawVoidTraderItem {
    pub item_type: String,
    #[serde(default)]
    pub prime_price: Option<i64>,
    #[serde(default)]
    pub regular_price: Option<i64>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawDailyDeal {
    pub store_item: String,
    #[serde(default)]
    pub discount: Option<i64>,
    #[serde(default)]
    pub original_price: Option<i64>,
    #[serde(default)]
    pub sale_price: Option<i64>,
    pub activation: Option<RawDate>,
    pub expiry: Option<RawDate>,
}

// ---- SyndicateMission ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawSyndicateMission {
    pub tag: String,
    #[serde(default)]
    pub nodes: Vec<String>,
    #[serde(default)]
    pub jobs: Vec<RawSyndicateJob>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RawSyndicateJob {
    #[serde(default)]
    pub job_type: Option<String>,
    #[serde(default)]
    pub rewards: Option<String>,
    #[serde(default)]
    pub min_enemy_level: Option<i64>,
    #[serde(default)]
    pub max_enemy_level: Option<i64>,
    #[serde(default)]
    pub xp_amounts: Vec<i64>,
}

// ---- Nightwave ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RawNightwave {
    #[serde(default)]
    pub affiliation_tag: Option<String>,
    #[serde(default)]
    pub challenges: HashMap<String, RawNightwaveChallenge>,
    #[serde(default)]
    pub rewards: Vec<RawNightwaveReward>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RawNightwaveChallenge {
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub standing: Option<i64>,
    #[serde(default)]
    pub required: Option<i64>,
    #[serde(default)]
    pub icon: Option<String>,
    #[serde(default)]
    pub tip: Option<String>,
    #[serde(default)]
    pub tip_icon: Option<String>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RawNightwaveReward {
    pub unique_name: String,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub icon: Option<String>,
    #[serde(default)]
    pub item_count: Option<i64>,
}

// ---- Events / Goals ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawEvent {
    #[serde(default)]
    pub desc: Option<String>,
    #[serde(default)]
    pub tool_tip: Option<String>,
    #[serde(default)]
    pub node: Option<String>,
    #[serde(default)]
    pub faction: Option<String>,
    #[serde(default)]
    pub score_loc_tag: Option<String>,
    #[serde(default)]
    pub reward: Option<RawReward>,
    #[serde(default)]
    pub tag: Option<String>,
    #[serde(default)]
    pub jobs: Vec<RawSyndicateJob>,
    pub activation: Option<RawDate>,
    pub expiry: Option<RawDate>,
    #[serde(flatten)]
    pub extra: HashMap<String, Value>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawGoal {
    #[serde(default)]
    pub node: Option<String>,
    #[serde(default)]
    pub desc: Option<String>,
    #[serde(default)]
    pub tool_tip: Option<String>,
    #[serde(default)]
    pub score_loc_tag: Option<String>,
    #[serde(default)]
    pub reward: Option<RawReward>,
    #[serde(default)]
    pub tag: Option<String>,
    pub activation: Option<RawDate>,
    pub expiry: Option<RawDate>,
}

// ---- Descents / PersistentEnemy ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawDescent {
    #[serde(default)]
    pub challenges: Vec<RawDescentChallenge>,
    pub activation: Option<RawDate>,
    pub expiry: Option<RawDate>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawDescentChallenge {
    #[serde(default)]
    pub r#type: Option<String>,
    #[serde(default)]
    pub challenge: Option<String>,
    #[serde(default)]
    pub level: Option<String>,
    #[serde(default)]
    pub specs: Vec<String>,
    #[serde(default)]
    pub auras: Vec<String>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawPersistentEnemy {
    #[serde(default)]
    pub agent_type: Option<String>,
    #[serde(default)]
    pub loc_tag: Option<String>,
    #[serde(default)]
    pub last_discovered_location: Option<String>,
    #[serde(default)]
    pub rank: Option<i64>,
    #[serde(default)]
    pub health_percent: Option<String>,
    pub activation: Option<RawDate>,
    pub expiry: Option<RawDate>,
}

// ---- Conquests (科研任务) ----
#[derive(Debug, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct RawConquest {
    #[serde(default)]
    pub r#type: Option<String>,
    #[serde(default)]
    pub missions: Vec<RawConquestMission>,
    #[serde(default)]
    pub variables: Vec<String>,
    #[serde(default)]
    pub activation: Option<RawDate>,
    #[serde(default)]
    pub expiry: Option<RawDate>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RawConquestMission {
    #[serde(default)]
    pub faction: Option<String>,
    #[serde(default)]
    pub mission_type: Option<String>,
    #[serde(default)]
    pub difficulties: Vec<RawConquestDifficulty>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RawConquestDifficulty {
    #[serde(rename = "type")]
    #[serde(default)]
    pub diff_type: Option<String>,
    #[serde(default)]
    pub deviation: Option<String>,
    #[serde(default)]
    pub risks: Vec<String>,
}
