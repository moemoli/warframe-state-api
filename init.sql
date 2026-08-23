-- ============================================================================
-- warframe 数据库 · 初始化 SQL（工作区根目录）
-- 建表 + 索引 + loc() 函数 + v_localized 视图 + languages 种子数据
-- 由 pg_dump 从 warframe 库（91 表 / 1 视图）重新生成，幂等可重复执行
--
-- 用法（在目标库执行，建库见 init.sh）:
--   psql -U <user> -d <db> -v ON_ERROR_STOP=1 -f init.sql
--   psql -h <host> -U <user> -d <db> -f init.sql
--
-- 说明:
--   * pg_trgm 扩展需要超级用户权限；无权限时删除对应 CREATE EXTENSION 语句
--   * 建表完成后用 load.py 导入数据:  python3 load.py --fetch --langs zh
-- ============================================================================

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.weapon_damage_per_shot DROP CONSTRAINT IF EXISTS weapon_damage_per_shot_weapon_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.weapon_compatibility_tags DROP CONSTRAINT IF EXISTS weapon_compatibility_tags_weapon_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.weapon_behaviours DROP CONSTRAINT IF EXISTS weapon_behaviours_weapon_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.weapon_behaviour_damage DROP CONSTRAINT IF EXISTS weapon_behaviour_damage_behaviour_id_fkey;
ALTER TABLE IF EXISTS ONLY public.warframe_exalted DROP CONSTRAINT IF EXISTS warframe_exalted_warframe_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.warframe_abilities DROP CONSTRAINT IF EXISTS warframe_abilities_warframe_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.warframe_abilities DROP CONSTRAINT IF EXISTS warframe_abilities_ability_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_mod_set_values DROP CONSTRAINT IF EXISTS upgrade_mod_set_values_upgrade_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_entry_values DROP CONSTRAINT IF EXISTS upgrade_entry_values_entry_id_fkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_entries DROP CONSTRAINT IF EXISTS upgrade_entries_upgrade_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_compatibility_tags DROP CONSTRAINT IF EXISTS upgrade_compatibility_tags_upgrade_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_challenge_complications DROP CONSTRAINT IF EXISTS upgrade_challenge_complications_challenge_id_fkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_available_challenges DROP CONSTRAINT IF EXISTS upgrade_available_challenges_upgrade_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.syndicate_titles DROP CONSTRAINT IF EXISTS syndicate_titles_syndicate_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.syndicate_medallions DROP CONSTRAINT IF EXISTS syndicate_medallions_syndicate_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.syndicate_alignments DROP CONSTRAINT IF EXISTS syndicate_alignments_syndicate_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.sentinel_default_upgrades DROP CONSTRAINT IF EXISTS sentinel_default_upgrades_sentinel_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.resource_sockets DROP CONSTRAINT IF EXISTS resource_sockets_resource_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.resource_dissection_parts DROP CONSTRAINT IF EXISTS resource_dissection_parts_resource_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.region_reward_manifests DROP CONSTRAINT IF EXISTS region_reward_manifests_region_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.region_dark_sector_data DROP CONSTRAINT IF EXISTS region_dark_sector_data_region_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.recipe_secret_ingredients DROP CONSTRAINT IF EXISTS recipe_secret_ingredients_recipe_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.recipe_ingredients DROP CONSTRAINT IF EXISTS recipe_ingredients_recipe_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.railjack_weapon_damage_per_shot DROP CONSTRAINT IF EXISTS railjack_weapon_damage_per_shot_weapon_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.railjack_weapon_compatibility_tags DROP CONSTRAINT IF EXISTS railjack_weapon_compatibility_tags_weapon_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.railjack_weapon_behaviours DROP CONSTRAINT IF EXISTS railjack_weapon_behaviours_weapon_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.railjack_weapon_behaviour_damage DROP CONSTRAINT IF EXISTS railjack_weapon_behaviour_damage_behaviour_id_fkey;
ALTER TABLE IF EXISTS ONLY public.mod_set_level_stats DROP CONSTRAINT IF EXISTS mod_set_level_stats_mod_set_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.mission_reward_tiers DROP CONSTRAINT IF EXISTS mission_reward_tiers_deck_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.mission_reward_items DROP CONSTRAINT IF EXISTS mission_reward_items_tier_id_fkey;
ALTER TABLE IF EXISTS ONLY public.localizations DROP CONSTRAINT IF EXISTS localizations_lang_fkey;
ALTER TABLE IF EXISTS ONLY public.key_rewards DROP CONSTRAINT IF EXISTS key_rewards_key_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.key_chain_stages DROP CONSTRAINT IF EXISTS key_chain_stages_key_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.key_chain_stage_items DROP CONSTRAINT IF EXISTS key_chain_stage_items_stage_id_fkey;
ALTER TABLE IF EXISTS ONLY public.intrinsic_ranks DROP CONSTRAINT IF EXISTS intrinsic_ranks_intrinsic_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.focus_upgrade_level_stats DROP CONSTRAINT IF EXISTS focus_upgrade_level_stats_focus_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.flavour_colours DROP CONSTRAINT IF EXISTS flavour_colours_flavour_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.enemy_droptable_pools DROP CONSTRAINT IF EXISTS enemy_droptable_pools_droptable_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.enemy_droptable_items DROP CONSTRAINT IF EXISTS enemy_droptable_items_pool_id_fkey;
ALTER TABLE IF EXISTS ONLY public.enemy_damage_controller_procs DROP CONSTRAINT IF EXISTS enemy_damage_controller_procs_controller_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.enemy_damage_controller_hit_proxies DROP CONSTRAINT IF EXISTS enemy_damage_controller_hit_proxies_controller_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.enemy_ai_weapon_behaviours DROP CONSTRAINT IF EXISTS enemy_ai_weapon_behaviours_ai_weapon_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.enemy_ai_weapon_behaviour_damage DROP CONSTRAINT IF EXISTS enemy_ai_weapon_behaviour_damage_behaviour_id_fkey;
ALTER TABLE IF EXISTS ONLY public.enemy_agent_items DROP CONSTRAINT IF EXISTS enemy_agent_items_agent_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.drone_capacity_multipliers DROP CONSTRAINT IF EXISTS drone_capacity_multipliers_drone_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.bundle_components DROP CONSTRAINT IF EXISTS bundle_components_bundle_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.booster_pack_rarity_weights DROP CONSTRAINT IF EXISTS booster_pack_rarity_weights_pack_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.booster_pack_components DROP CONSTRAINT IF EXISTS booster_pack_components_pack_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.achievement_children DROP CONSTRAINT IF EXISTS achievement_children_child_unique_name_fkey;
ALTER TABLE IF EXISTS ONLY public.achievement_children DROP CONSTRAINT IF EXISTS achievement_children_achievement_unique_name_fkey;
DROP INDEX IF EXISTS public.idx_weapon_behaviours_weapon;
DROP INDEX IF EXISTS public.idx_warframe_abilities_ability;
DROP INDEX IF EXISTS public.idx_upgrade_entries_upgrade;
DROP INDEX IF EXISTS public.idx_upgrade_available_challenges_upgrade;
DROP INDEX IF EXISTS public.idx_railjack_weapon_behaviours_weapon;
DROP INDEX IF EXISTS public.idx_mission_reward_tiers_deck;
DROP INDEX IF EXISTS public.idx_localizations_value_trgm;
DROP INDEX IF EXISTS public.idx_localizations_value_hash;
DROP INDEX IF EXISTS public.idx_localizations_loc_tag_trgm;
DROP INDEX IF EXISTS public.idx_localizations_lang;
DROP INDEX IF EXISTS public.idx_key_chain_stages_key;
DROP INDEX IF EXISTS public.idx_enemy_droptable_pools_droptable;
DROP INDEX IF EXISTS public.idx_enemy_ai_weapon_behaviours_weapon;
DROP INDEX IF EXISTS public.idx_achievement_children_child;
ALTER TABLE IF EXISTS ONLY public.weapons DROP CONSTRAINT IF EXISTS weapons_pkey;
ALTER TABLE IF EXISTS ONLY public.weapon_damage_per_shot DROP CONSTRAINT IF EXISTS weapon_damage_per_shot_pkey;
ALTER TABLE IF EXISTS ONLY public.weapon_compatibility_tags DROP CONSTRAINT IF EXISTS weapon_compatibility_tags_pkey;
ALTER TABLE IF EXISTS ONLY public.weapon_behaviours DROP CONSTRAINT IF EXISTS weapon_behaviours_weapon_unique_name_slot_key;
ALTER TABLE IF EXISTS ONLY public.weapon_behaviours DROP CONSTRAINT IF EXISTS weapon_behaviours_pkey;
ALTER TABLE IF EXISTS ONLY public.weapon_behaviour_damage DROP CONSTRAINT IF EXISTS weapon_behaviour_damage_pkey;
ALTER TABLE IF EXISTS ONLY public.warframes DROP CONSTRAINT IF EXISTS warframes_pkey;
ALTER TABLE IF EXISTS ONLY public.warframe_exalted DROP CONSTRAINT IF EXISTS warframe_exalted_pkey;
ALTER TABLE IF EXISTS ONLY public.warframe_abilities DROP CONSTRAINT IF EXISTS warframe_abilities_pkey;
ALTER TABLE IF EXISTS ONLY public.virtuals DROP CONSTRAINT IF EXISTS virtuals_pkey;
ALTER TABLE IF EXISTS ONLY public.upgrades DROP CONSTRAINT IF EXISTS upgrades_pkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_mod_set_values DROP CONSTRAINT IF EXISTS upgrade_mod_set_values_pkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_entry_values DROP CONSTRAINT IF EXISTS upgrade_entry_values_pkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_entries DROP CONSTRAINT IF EXISTS upgrade_entries_upgrade_unique_name_slot_key;
ALTER TABLE IF EXISTS ONLY public.upgrade_entries DROP CONSTRAINT IF EXISTS upgrade_entries_pkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_compatibility_tags DROP CONSTRAINT IF EXISTS upgrade_compatibility_tags_pkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_challenge_complications DROP CONSTRAINT IF EXISTS upgrade_challenge_complications_pkey;
ALTER TABLE IF EXISTS ONLY public.upgrade_challenge_complications DROP CONSTRAINT IF EXISTS upgrade_challenge_complications_challenge_id_slot_key;
ALTER TABLE IF EXISTS ONLY public.upgrade_available_challenges DROP CONSTRAINT IF EXISTS upgrade_available_challenges_upgrade_unique_name_slot_key;
ALTER TABLE IF EXISTS ONLY public.upgrade_available_challenges DROP CONSTRAINT IF EXISTS upgrade_available_challenges_pkey;
ALTER TABLE IF EXISTS ONLY public.text_icons DROP CONSTRAINT IF EXISTS text_icons_pkey;
ALTER TABLE IF EXISTS ONLY public.syndicates DROP CONSTRAINT IF EXISTS syndicates_pkey;
ALTER TABLE IF EXISTS ONLY public.syndicate_titles DROP CONSTRAINT IF EXISTS syndicate_titles_pkey;
ALTER TABLE IF EXISTS ONLY public.syndicate_medallions DROP CONSTRAINT IF EXISTS syndicate_medallions_pkey;
ALTER TABLE IF EXISTS ONLY public.syndicate_alignments DROP CONSTRAINT IF EXISTS syndicate_alignments_pkey;
ALTER TABLE IF EXISTS ONLY public.sentinels DROP CONSTRAINT IF EXISTS sentinels_pkey;
ALTER TABLE IF EXISTS ONLY public.sentinel_default_upgrades DROP CONSTRAINT IF EXISTS sentinel_default_upgrades_pkey;
ALTER TABLE IF EXISTS ONLY public.resources DROP CONSTRAINT IF EXISTS resources_pkey;
ALTER TABLE IF EXISTS ONLY public.resource_sockets DROP CONSTRAINT IF EXISTS resource_sockets_pkey;
ALTER TABLE IF EXISTS ONLY public.resource_dissection_parts DROP CONSTRAINT IF EXISTS resource_dissection_parts_pkey;
ALTER TABLE IF EXISTS ONLY public.relics DROP CONSTRAINT IF EXISTS relics_pkey;
ALTER TABLE IF EXISTS ONLY public.regions DROP CONSTRAINT IF EXISTS regions_pkey;
ALTER TABLE IF EXISTS ONLY public.region_reward_manifests DROP CONSTRAINT IF EXISTS region_reward_manifests_pkey;
ALTER TABLE IF EXISTS ONLY public.region_dark_sector_data DROP CONSTRAINT IF EXISTS region_dark_sector_data_pkey;
ALTER TABLE IF EXISTS ONLY public.recipes DROP CONSTRAINT IF EXISTS recipes_pkey;
ALTER TABLE IF EXISTS ONLY public.recipe_secret_ingredients DROP CONSTRAINT IF EXISTS recipe_secret_ingredients_pkey;
ALTER TABLE IF EXISTS ONLY public.recipe_ingredients DROP CONSTRAINT IF EXISTS recipe_ingredients_pkey;
ALTER TABLE IF EXISTS ONLY public.railjack_weapons DROP CONSTRAINT IF EXISTS railjack_weapons_pkey;
ALTER TABLE IF EXISTS ONLY public.railjack_weapon_damage_per_shot DROP CONSTRAINT IF EXISTS railjack_weapon_damage_per_shot_pkey;
ALTER TABLE IF EXISTS ONLY public.railjack_weapon_compatibility_tags DROP CONSTRAINT IF EXISTS railjack_weapon_compatibility_tags_pkey;
ALTER TABLE IF EXISTS ONLY public.railjack_weapon_behaviours DROP CONSTRAINT IF EXISTS railjack_weapon_behaviours_weapon_unique_name_slot_key;
ALTER TABLE IF EXISTS ONLY public.railjack_weapon_behaviours DROP CONSTRAINT IF EXISTS railjack_weapon_behaviours_pkey;
ALTER TABLE IF EXISTS ONLY public.railjack_weapon_behaviour_damage DROP CONSTRAINT IF EXISTS railjack_weapon_behaviour_damage_pkey;
ALTER TABLE IF EXISTS ONLY public.nightwave_rewards DROP CONSTRAINT IF EXISTS nightwave_rewards_pkey;
ALTER TABLE IF EXISTS ONLY public.nightwave DROP CONSTRAINT IF EXISTS nightwave_pkey;
ALTER TABLE IF EXISTS ONLY public.nightwave_challenges DROP CONSTRAINT IF EXISTS nightwave_challenges_pkey;
ALTER TABLE IF EXISTS ONLY public.mod_sets DROP CONSTRAINT IF EXISTS mod_sets_pkey;
ALTER TABLE IF EXISTS ONLY public.mod_set_level_stats DROP CONSTRAINT IF EXISTS mod_set_level_stats_pkey;
ALTER TABLE IF EXISTS ONLY public.mission_reward_tiers DROP CONSTRAINT IF EXISTS mission_reward_tiers_pkey;
ALTER TABLE IF EXISTS ONLY public.mission_reward_tiers DROP CONSTRAINT IF EXISTS mission_reward_tiers_deck_unique_name_tier_index_key;
ALTER TABLE IF EXISTS ONLY public.mission_reward_items DROP CONSTRAINT IF EXISTS mission_reward_items_pkey;
ALTER TABLE IF EXISTS ONLY public.mission_reward_decks DROP CONSTRAINT IF EXISTS mission_reward_decks_pkey;
ALTER TABLE IF EXISTS ONLY public.misc_unique_level_caps DROP CONSTRAINT IF EXISTS misc_unique_level_caps_pkey;
ALTER TABLE IF EXISTS ONLY public.misc DROP CONSTRAINT IF EXISTS misc_pkey;
ALTER TABLE IF EXISTS ONLY public.misc_booster_durations DROP CONSTRAINT IF EXISTS misc_booster_durations_pkey;
ALTER TABLE IF EXISTS ONLY public.localizations DROP CONSTRAINT IF EXISTS localizations_pkey;
ALTER TABLE IF EXISTS ONLY public.languages DROP CONSTRAINT IF EXISTS languages_pkey;
ALTER TABLE IF EXISTS ONLY public.keys DROP CONSTRAINT IF EXISTS keys_pkey;
ALTER TABLE IF EXISTS ONLY public.key_rewards DROP CONSTRAINT IF EXISTS key_rewards_pkey;
ALTER TABLE IF EXISTS ONLY public.key_chain_stages DROP CONSTRAINT IF EXISTS key_chain_stages_pkey;
ALTER TABLE IF EXISTS ONLY public.key_chain_stages DROP CONSTRAINT IF EXISTS key_chain_stages_key_unique_name_stage_index_key;
ALTER TABLE IF EXISTS ONLY public.key_chain_stage_items DROP CONSTRAINT IF EXISTS key_chain_stage_items_pkey;
ALTER TABLE IF EXISTS ONLY public.intrinsics DROP CONSTRAINT IF EXISTS intrinsics_pkey;
ALTER TABLE IF EXISTS ONLY public.intrinsic_ranks DROP CONSTRAINT IF EXISTS intrinsic_ranks_pkey;
ALTER TABLE IF EXISTS ONLY public.images DROP CONSTRAINT IF EXISTS images_pkey;
ALTER TABLE IF EXISTS ONLY public.gear DROP CONSTRAINT IF EXISTS gear_pkey;
ALTER TABLE IF EXISTS ONLY public.fusion_bundles DROP CONSTRAINT IF EXISTS fusion_bundles_pkey;
ALTER TABLE IF EXISTS ONLY public.focus_upgrades DROP CONSTRAINT IF EXISTS focus_upgrades_pkey;
ALTER TABLE IF EXISTS ONLY public.focus_upgrade_level_stats DROP CONSTRAINT IF EXISTS focus_upgrade_level_stats_pkey;
ALTER TABLE IF EXISTS ONLY public.flavour_items DROP CONSTRAINT IF EXISTS flavour_items_pkey;
ALTER TABLE IF EXISTS ONLY public.flavour_colours DROP CONSTRAINT IF EXISTS flavour_colours_pkey;
ALTER TABLE IF EXISTS ONLY public.export_sources DROP CONSTRAINT IF EXISTS export_sources_pkey;
ALTER TABLE IF EXISTS ONLY public.export_sources DROP CONSTRAINT IF EXISTS export_sources_file_name_key;
ALTER TABLE IF EXISTS ONLY public.enemy_hit_proxies DROP CONSTRAINT IF EXISTS enemy_hit_proxies_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_droptables DROP CONSTRAINT IF EXISTS enemy_droptables_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_droptable_pools DROP CONSTRAINT IF EXISTS enemy_droptable_pools_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_droptable_pools DROP CONSTRAINT IF EXISTS enemy_droptable_pools_droptable_unique_name_pool_index_key;
ALTER TABLE IF EXISTS ONLY public.enemy_droptable_items DROP CONSTRAINT IF EXISTS enemy_droptable_items_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_damage_controllers DROP CONSTRAINT IF EXISTS enemy_damage_controllers_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_damage_controller_procs DROP CONSTRAINT IF EXISTS enemy_damage_controller_procs_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_damage_controller_hit_proxies DROP CONSTRAINT IF EXISTS enemy_damage_controller_hit_proxies_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_avatars DROP CONSTRAINT IF EXISTS enemy_avatars_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_ai_weapons DROP CONSTRAINT IF EXISTS enemy_ai_weapons_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_ai_weapon_behaviours DROP CONSTRAINT IF EXISTS enemy_ai_weapon_behaviours_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_ai_weapon_behaviours DROP CONSTRAINT IF EXISTS enemy_ai_weapon_behaviours_ai_weapon_unique_name_slot_key;
ALTER TABLE IF EXISTS ONLY public.enemy_ai_weapon_behaviour_damage DROP CONSTRAINT IF EXISTS enemy_ai_weapon_behaviour_damage_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_agents DROP CONSTRAINT IF EXISTS enemy_agents_pkey;
ALTER TABLE IF EXISTS ONLY public.enemy_agent_items DROP CONSTRAINT IF EXISTS enemy_agent_items_pkey;
ALTER TABLE IF EXISTS ONLY public.drones DROP CONSTRAINT IF EXISTS drones_pkey;
ALTER TABLE IF EXISTS ONLY public.drone_capacity_multipliers DROP CONSTRAINT IF EXISTS drone_capacity_multipliers_pkey;
ALTER TABLE IF EXISTS ONLY public.customs DROP CONSTRAINT IF EXISTS customs_pkey;
ALTER TABLE IF EXISTS ONLY public.bundles DROP CONSTRAINT IF EXISTS bundles_pkey;
ALTER TABLE IF EXISTS ONLY public.bundle_components DROP CONSTRAINT IF EXISTS bundle_components_pkey;
ALTER TABLE IF EXISTS ONLY public.booster_packs DROP CONSTRAINT IF EXISTS booster_packs_pkey;
ALTER TABLE IF EXISTS ONLY public.booster_pack_rarity_weights DROP CONSTRAINT IF EXISTS booster_pack_rarity_weights_pkey;
ALTER TABLE IF EXISTS ONLY public.booster_pack_components DROP CONSTRAINT IF EXISTS booster_pack_components_pkey;
ALTER TABLE IF EXISTS ONLY public.avionics DROP CONSTRAINT IF EXISTS avionics_pkey;
ALTER TABLE IF EXISTS ONLY public.arcanes DROP CONSTRAINT IF EXISTS arcanes_pkey;
ALTER TABLE IF EXISTS ONLY public.achievements DROP CONSTRAINT IF EXISTS achievements_pkey;
ALTER TABLE IF EXISTS ONLY public.achievement_children DROP CONSTRAINT IF EXISTS achievement_children_pkey;
ALTER TABLE IF EXISTS ONLY public.abilities DROP CONSTRAINT IF EXISTS abilities_pkey;
ALTER TABLE IF EXISTS public.weapon_behaviours ALTER COLUMN behaviour_id DROP DEFAULT;
ALTER TABLE IF EXISTS public.upgrade_entries ALTER COLUMN entry_id DROP DEFAULT;
ALTER TABLE IF EXISTS public.upgrade_challenge_complications ALTER COLUMN complication_id DROP DEFAULT;
ALTER TABLE IF EXISTS public.upgrade_available_challenges ALTER COLUMN challenge_id DROP DEFAULT;
ALTER TABLE IF EXISTS public.railjack_weapon_behaviours ALTER COLUMN behaviour_id DROP DEFAULT;
ALTER TABLE IF EXISTS public.mission_reward_tiers ALTER COLUMN tier_id DROP DEFAULT;
ALTER TABLE IF EXISTS public.key_chain_stages ALTER COLUMN stage_id DROP DEFAULT;
ALTER TABLE IF EXISTS public.export_sources ALTER COLUMN source_id DROP DEFAULT;
ALTER TABLE IF EXISTS public.enemy_droptable_pools ALTER COLUMN pool_id DROP DEFAULT;
ALTER TABLE IF EXISTS public.enemy_ai_weapon_behaviours ALTER COLUMN behaviour_id DROP DEFAULT;
DROP TABLE IF EXISTS public.weapon_damage_per_shot;
DROP TABLE IF EXISTS public.weapon_compatibility_tags;
DROP SEQUENCE IF EXISTS public.weapon_behaviours_behaviour_id_seq;
DROP TABLE IF EXISTS public.weapon_behaviour_damage;
DROP TABLE IF EXISTS public.warframe_exalted;
DROP TABLE IF EXISTS public.warframe_abilities;
DROP VIEW IF EXISTS public.v_localized;
DROP TABLE IF EXISTS public.weapons;
DROP TABLE IF EXISTS public.weapon_behaviours;
DROP TABLE IF EXISTS public.warframes;
DROP TABLE IF EXISTS public.virtuals;
DROP TABLE IF EXISTS public.upgrades;
DROP TABLE IF EXISTS public.upgrade_mod_set_values;
DROP TABLE IF EXISTS public.upgrade_entry_values;
DROP SEQUENCE IF EXISTS public.upgrade_entries_entry_id_seq;
DROP TABLE IF EXISTS public.upgrade_entries;
DROP TABLE IF EXISTS public.upgrade_compatibility_tags;
DROP SEQUENCE IF EXISTS public.upgrade_challenge_complications_complication_id_seq;
DROP TABLE IF EXISTS public.upgrade_challenge_complications;
DROP SEQUENCE IF EXISTS public.upgrade_available_challenges_challenge_id_seq;
DROP TABLE IF EXISTS public.upgrade_available_challenges;
DROP TABLE IF EXISTS public.text_icons;
DROP TABLE IF EXISTS public.syndicates;
DROP TABLE IF EXISTS public.syndicate_titles;
DROP TABLE IF EXISTS public.syndicate_medallions;
DROP TABLE IF EXISTS public.syndicate_alignments;
DROP TABLE IF EXISTS public.sentinels;
DROP TABLE IF EXISTS public.sentinel_default_upgrades;
DROP TABLE IF EXISTS public.resources;
DROP TABLE IF EXISTS public.resource_sockets;
DROP TABLE IF EXISTS public.resource_dissection_parts;
DROP TABLE IF EXISTS public.relics;
DROP TABLE IF EXISTS public.regions;
DROP TABLE IF EXISTS public.region_reward_manifests;
DROP TABLE IF EXISTS public.region_dark_sector_data;
DROP TABLE IF EXISTS public.recipes;
DROP TABLE IF EXISTS public.recipe_secret_ingredients;
DROP TABLE IF EXISTS public.recipe_ingredients;
DROP TABLE IF EXISTS public.railjack_weapons;
DROP TABLE IF EXISTS public.railjack_weapon_damage_per_shot;
DROP TABLE IF EXISTS public.railjack_weapon_compatibility_tags;
DROP SEQUENCE IF EXISTS public.railjack_weapon_behaviours_behaviour_id_seq;
DROP TABLE IF EXISTS public.railjack_weapon_behaviours;
DROP TABLE IF EXISTS public.railjack_weapon_behaviour_damage;
DROP TABLE IF EXISTS public.nightwave_rewards;
DROP TABLE IF EXISTS public.nightwave_challenges;
DROP TABLE IF EXISTS public.nightwave;
DROP TABLE IF EXISTS public.mod_sets;
DROP TABLE IF EXISTS public.mod_set_level_stats;
DROP SEQUENCE IF EXISTS public.mission_reward_tiers_tier_id_seq;
DROP TABLE IF EXISTS public.mission_reward_tiers;
DROP TABLE IF EXISTS public.mission_reward_items;
DROP TABLE IF EXISTS public.mission_reward_decks;
DROP TABLE IF EXISTS public.misc_unique_level_caps;
DROP TABLE IF EXISTS public.misc_booster_durations;
DROP TABLE IF EXISTS public.misc;
DROP TABLE IF EXISTS public.localizations;
DROP TABLE IF EXISTS public.languages;
DROP TABLE IF EXISTS public.keys;
DROP TABLE IF EXISTS public.key_rewards;
DROP SEQUENCE IF EXISTS public.key_chain_stages_stage_id_seq;
DROP TABLE IF EXISTS public.key_chain_stages;
DROP TABLE IF EXISTS public.key_chain_stage_items;
DROP TABLE IF EXISTS public.intrinsics;
DROP TABLE IF EXISTS public.intrinsic_ranks;
DROP TABLE IF EXISTS public.images;
DROP TABLE IF EXISTS public.gear;
DROP TABLE IF EXISTS public.fusion_bundles;
DROP TABLE IF EXISTS public.focus_upgrades;
DROP TABLE IF EXISTS public.focus_upgrade_level_stats;
DROP TABLE IF EXISTS public.flavour_items;
DROP TABLE IF EXISTS public.flavour_colours;
DROP SEQUENCE IF EXISTS public.export_sources_source_id_seq;
DROP TABLE IF EXISTS public.export_sources;
DROP TABLE IF EXISTS public.enemy_hit_proxies;
DROP TABLE IF EXISTS public.enemy_droptables;
DROP SEQUENCE IF EXISTS public.enemy_droptable_pools_pool_id_seq;
DROP TABLE IF EXISTS public.enemy_droptable_pools;
DROP TABLE IF EXISTS public.enemy_droptable_items;
DROP TABLE IF EXISTS public.enemy_damage_controllers;
DROP TABLE IF EXISTS public.enemy_damage_controller_procs;
DROP TABLE IF EXISTS public.enemy_damage_controller_hit_proxies;
DROP TABLE IF EXISTS public.enemy_avatars;
DROP TABLE IF EXISTS public.enemy_ai_weapons;
DROP SEQUENCE IF EXISTS public.enemy_ai_weapon_behaviours_behaviour_id_seq;
DROP TABLE IF EXISTS public.enemy_ai_weapon_behaviours;
DROP TABLE IF EXISTS public.enemy_ai_weapon_behaviour_damage;
DROP TABLE IF EXISTS public.enemy_agents;
DROP TABLE IF EXISTS public.enemy_agent_items;
DROP TABLE IF EXISTS public.drones;
DROP TABLE IF EXISTS public.drone_capacity_multipliers;
DROP TABLE IF EXISTS public.customs;
DROP TABLE IF EXISTS public.bundles;
DROP TABLE IF EXISTS public.bundle_components;
DROP TABLE IF EXISTS public.booster_packs;
DROP TABLE IF EXISTS public.booster_pack_rarity_weights;
DROP TABLE IF EXISTS public.booster_pack_components;
DROP TABLE IF EXISTS public.avionics;
DROP TABLE IF EXISTS public.arcanes;
DROP TABLE IF EXISTS public.achievements;
DROP TABLE IF EXISTS public.achievement_children;
DROP TABLE IF EXISTS public.abilities;
DROP FUNCTION IF EXISTS public.loc(p_tag text, p_lang text);
DROP EXTENSION IF EXISTS pg_trgm;
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


-- Name: loc(text, text); Type: FUNCTION; Schema: public; Owner: -

CREATE FUNCTION public.loc(p_tag text, p_lang text DEFAULT 'en'::text) RETURNS text
    LANGUAGE sql STABLE PARALLEL SAFE
    AS $$
    SELECT value
    FROM localizations
    WHERE loc_tag = p_tag AND lang = p_lang
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

-- Name: abilities; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.abilities (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text,
    energy_required_to_activate integer,
    energy_consumption_over_time double precision
);


-- Name: achievement_children; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.achievement_children (
    achievement_unique_name text NOT NULL,
    child_unique_name text NOT NULL
);


-- Name: achievements; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.achievements (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text,
    required_count integer,
    progress_indicator_freq integer,
    hidden boolean
);


-- Name: arcanes; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.arcanes (
    unique_name text NOT NULL,
    name_loc text,
    icon text,
    codex_secret boolean,
    exclude_from_codex boolean,
    rarity text,
    fusion_limit integer,
    distill_point_value integer,
    is_frivolous boolean
);


-- Name: avionics; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.avionics (
    unique_name text NOT NULL,
    name_loc text,
    polarity text,
    rarity text,
    codex_secret boolean,
    base_drain integer,
    fusion_limit integer,
    exclude_from_codex boolean
);


-- Name: booster_pack_components; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.booster_pack_components (
    pack_unique_name text NOT NULL,
    slot integer NOT NULL,
    item text NOT NULL,
    rarity text
);


-- Name: booster_pack_rarity_weights; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.booster_pack_rarity_weights (
    pack_unique_name text NOT NULL,
    roll_index integer NOT NULL,
    rarity text NOT NULL,
    weight double precision NOT NULL
);


-- Name: booster_packs; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.booster_packs (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text
);


-- Name: bundle_components; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.bundle_components (
    bundle_unique_name text NOT NULL,
    slot integer NOT NULL,
    type_name text NOT NULL,
    purchase_quantity integer NOT NULL,
    durability text,
    give_max_rank boolean
);


-- Name: bundles; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.bundles (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text,
    exclude_from_codex boolean,
    premium_price integer
);


-- Name: customs; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.customs (
    unique_name text NOT NULL,
    name_loc text,
    codex_secret boolean,
    description_loc text,
    icon text,
    exclude_from_codex boolean
);


-- Name: drone_capacity_multipliers; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.drone_capacity_multipliers (
    drone_unique_name text NOT NULL,
    slot integer NOT NULL,
    value double precision NOT NULL
);


-- Name: drones; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.drones (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text,
    bin_count integer,
    bin_capacity integer,
    fill_rate double precision,
    durability double precision,
    repair_rate double precision,
    codex_secret boolean
);


-- Name: enemy_agent_items; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_agent_items (
    agent_unique_name text NOT NULL,
    slot integer NOT NULL,
    type text NOT NULL
);


-- Name: enemy_agents; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_agents (
    unique_name text NOT NULL,
    base_level integer,
    avatar_standard text,
    avatar_eximus text,
    avatar_rare text
);


-- Name: enemy_ai_weapon_behaviour_damage; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_ai_weapon_behaviour_damage (
    behaviour_id bigint NOT NULL,
    path text NOT NULL,
    damage_type text NOT NULL,
    value double precision NOT NULL
);


-- Name: enemy_ai_weapon_behaviours; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_ai_weapon_behaviours (
    behaviour_id bigint NOT NULL,
    ai_weapon_unique_name text NOT NULL,
    slot integer NOT NULL,
    state_name_loc text
);


-- Name: enemy_ai_weapon_behaviours_behaviour_id_seq; Type: SEQUENCE; Schema: public; Owner: -

CREATE SEQUENCE public.enemy_ai_weapon_behaviours_behaviour_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


-- Name: enemy_ai_weapon_behaviours_behaviour_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -

ALTER SEQUENCE public.enemy_ai_weapon_behaviours_behaviour_id_seq OWNED BY public.enemy_ai_weapon_behaviours.behaviour_id;


-- Name: enemy_ai_weapons; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_ai_weapons (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text
);


-- Name: enemy_avatars; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_avatars (
    unique_name text NOT NULL,
    name_loc text,
    icon text,
    description_loc text,
    faction text,
    damage_controller text,
    health integer,
    kill_xp_reward integer,
    faction_resistance_keyword text,
    droptable text,
    is_frivolous boolean
);


-- Name: enemy_damage_controller_hit_proxies; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_damage_controller_hit_proxies (
    controller_unique_name text CONSTRAINT enemy_damage_controller_hit_pro_controller_unique_name_not_null NOT NULL,
    slot integer NOT NULL,
    bone text,
    type text
);


-- Name: enemy_damage_controller_procs; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_damage_controller_procs (
    controller_unique_name text NOT NULL,
    slot integer NOT NULL,
    proc_type text NOT NULL
);


-- Name: enemy_damage_controllers; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_damage_controllers (
    unique_name text NOT NULL,
    armor double precision,
    shield double precision
);


-- Name: enemy_droptable_items; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_droptable_items (
    pool_id bigint NOT NULL,
    slot integer NOT NULL,
    type text NOT NULL,
    probability double precision NOT NULL
);


-- Name: enemy_droptable_pools; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_droptable_pools (
    pool_id bigint NOT NULL,
    droptable_unique_name text NOT NULL,
    pool_index integer NOT NULL,
    chance double precision NOT NULL
);


-- Name: enemy_droptable_pools_pool_id_seq; Type: SEQUENCE; Schema: public; Owner: -

CREATE SEQUENCE public.enemy_droptable_pools_pool_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


-- Name: enemy_droptable_pools_pool_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -

ALTER SEQUENCE public.enemy_droptable_pools_pool_id_seq OWNED BY public.enemy_droptable_pools.pool_id;


-- Name: enemy_droptables; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_droptables (
    unique_name text NOT NULL
);


-- Name: enemy_hit_proxies; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.enemy_hit_proxies (
    unique_name text NOT NULL,
    damage_atten double precision,
    critical_chance double precision,
    critical_multiplier double precision
);


-- Name: export_sources; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.export_sources (
    source_id integer NOT NULL,
    file_name text NOT NULL,
    record_count integer DEFAULT 0 NOT NULL,
    source_commit text,
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


-- Name: export_sources_source_id_seq; Type: SEQUENCE; Schema: public; Owner: -

CREATE SEQUENCE public.export_sources_source_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


-- Name: export_sources_source_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -

ALTER SEQUENCE public.export_sources_source_id_seq OWNED BY public.export_sources.source_id;


-- Name: flavour_colours; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.flavour_colours (
    flavour_unique_name text NOT NULL,
    kind text NOT NULL,
    slot integer NOT NULL,
    value text NOT NULL
);


-- Name: flavour_items; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.flavour_items (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text,
    base text,
    codex_secret boolean,
    exclude_from_codex boolean
);


-- Name: focus_upgrade_level_stats; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.focus_upgrade_level_stats (
    focus_unique_name text NOT NULL,
    level integer NOT NULL,
    stat_key text NOT NULL,
    stat_value text NOT NULL
);


-- Name: focus_upgrades; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.focus_upgrades (
    unique_name text NOT NULL,
    name_loc text,
    icon text,
    polarity text,
    rarity text,
    codex_secret boolean,
    base_drain integer,
    fusion_limit integer,
    exclude_from_codex boolean,
    description_loc text,
    base_focus_point_cost integer
);


-- Name: fusion_bundles; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.fusion_bundles (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text,
    codex_secret boolean,
    fusion_points integer
);


-- Name: gear; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.gear (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text,
    codex_secret boolean,
    parent_name text,
    purchase_quantity integer
);


-- Name: images; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.images (
    unique_name text NOT NULL,
    content_hash text
);


-- Name: intrinsic_ranks; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.intrinsic_ranks (
    intrinsic_unique_name text NOT NULL,
    rank_index integer NOT NULL,
    name_loc text,
    description_loc text
);


-- Name: intrinsics; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.intrinsics (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text
);


-- Name: key_chain_stage_items; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.key_chain_stage_items (
    stage_id bigint NOT NULL,
    slot integer NOT NULL,
    item_type text NOT NULL
);


-- Name: key_chain_stages; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.key_chain_stages (
    stage_id bigint NOT NULL,
    key_unique_name text NOT NULL,
    stage_index integer NOT NULL,
    key text,
    message_sender_loc text,
    message_title_loc text,
    message_body_loc text
);


-- Name: key_chain_stages_stage_id_seq; Type: SEQUENCE; Schema: public; Owner: -

CREATE SEQUENCE public.key_chain_stages_stage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


-- Name: key_chain_stages_stage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -

ALTER SEQUENCE public.key_chain_stages_stage_id_seq OWNED BY public.key_chain_stages.stage_id;


-- Name: key_rewards; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.key_rewards (
    key_unique_name text NOT NULL,
    slot integer NOT NULL,
    reward_type text NOT NULL,
    item_type text,
    amount integer
);


-- Name: keys; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.keys (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text,
    parent_name text,
    codex_secret boolean,
    exclude_from_codex boolean
);


-- Name: languages; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.languages (
    code text NOT NULL,
    native_name text NOT NULL,
    english_name text NOT NULL
);


-- Name: localizations; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.localizations (
    loc_tag text NOT NULL,
    lang text NOT NULL,
    value text NOT NULL
);


-- Name: misc; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.misc (
    id integer DEFAULT 1 NOT NULL,
    npc_kill_reward_multiplier double precision,
    CONSTRAINT misc_id_check CHECK ((id = 1))
);


-- Name: misc_booster_durations; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.misc_booster_durations (
    rarity text NOT NULL,
    value double precision NOT NULL
);


-- Name: misc_unique_level_caps; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.misc_unique_level_caps (
    level_cap_key text NOT NULL,
    value integer NOT NULL
);


-- Name: mission_reward_decks; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.mission_reward_decks (
    unique_name text NOT NULL
);


-- Name: mission_reward_items; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.mission_reward_items (
    tier_id bigint NOT NULL,
    slot integer NOT NULL,
    type text NOT NULL,
    item_count integer NOT NULL,
    probability double precision,
    rarity text
);


-- Name: mission_reward_tiers; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.mission_reward_tiers (
    tier_id bigint NOT NULL,
    deck_unique_name text NOT NULL,
    tier_index integer NOT NULL
);


-- Name: mission_reward_tiers_tier_id_seq; Type: SEQUENCE; Schema: public; Owner: -

CREATE SEQUENCE public.mission_reward_tiers_tier_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


-- Name: mission_reward_tiers_tier_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -

ALTER SEQUENCE public.mission_reward_tiers_tier_id_seq OWNED BY public.mission_reward_tiers.tier_id;


-- Name: mod_set_level_stats; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.mod_set_level_stats (
    mod_set_unique_name text NOT NULL,
    level integer NOT NULL,
    stat_key text NOT NULL,
    stat_value text NOT NULL
);


-- Name: mod_sets; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.mod_sets (
    unique_name text NOT NULL,
    description_loc text,
    icon text,
    num_upgrades_in_set integer,
    buff_set boolean
);


-- Name: nightwave; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.nightwave (
    id integer DEFAULT 1 NOT NULL,
    affiliation_tag text,
    CONSTRAINT nightwave_id_check CHECK ((id = 1))
);


-- Name: nightwave_challenges; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.nightwave_challenges (
    challenge_key text NOT NULL,
    name_loc text,
    description_loc text,
    standing integer,
    required integer,
    icon text,
    tip_loc text,
    tip_icon text
);


-- Name: nightwave_rewards; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.nightwave_rewards (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text,
    item_count integer
);


-- Name: railjack_weapon_behaviour_damage; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.railjack_weapon_behaviour_damage (
    behaviour_id bigint NOT NULL,
    path text NOT NULL,
    damage_type text NOT NULL,
    value double precision NOT NULL
);


-- Name: railjack_weapon_behaviours; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.railjack_weapon_behaviours (
    behaviour_id bigint NOT NULL,
    weapon_unique_name text NOT NULL,
    slot integer NOT NULL,
    state_name_loc text
);


-- Name: railjack_weapon_behaviours_behaviour_id_seq; Type: SEQUENCE; Schema: public; Owner: -

CREATE SEQUENCE public.railjack_weapon_behaviours_behaviour_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


-- Name: railjack_weapon_behaviours_behaviour_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -

ALTER SEQUENCE public.railjack_weapon_behaviours_behaviour_id_seq OWNED BY public.railjack_weapon_behaviours.behaviour_id;


-- Name: railjack_weapon_compatibility_tags; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.railjack_weapon_compatibility_tags (
    weapon_unique_name text NOT NULL,
    tag text NOT NULL
);


-- Name: railjack_weapon_damage_per_shot; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.railjack_weapon_damage_per_shot (
    weapon_unique_name text NOT NULL,
    slot integer NOT NULL,
    value double precision NOT NULL
);


-- Name: railjack_weapons; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.railjack_weapons (
    unique_name text NOT NULL,
    name_loc text,
    parent_name text,
    icon text,
    codex_secret boolean,
    total_damage double precision,
    description_loc text,
    critical_chance double precision,
    critical_multiplier double precision,
    proc_chance double precision,
    fire_rate double precision,
    mastery_req integer,
    product_category text,
    exclude_from_codex boolean,
    slot integer,
    accuracy double precision,
    omega_attenuation double precision,
    noise text,
    trigger text,
    magazine_size integer,
    reload_time double precision,
    multishot double precision
);


-- Name: recipe_ingredients; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.recipe_ingredients (
    recipe_unique_name text NOT NULL,
    slot integer NOT NULL,
    item_type text NOT NULL,
    item_count integer NOT NULL
);


-- Name: recipe_secret_ingredients; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.recipe_secret_ingredients (
    recipe_unique_name text NOT NULL,
    slot integer NOT NULL,
    item_type text NOT NULL,
    item_count integer NOT NULL
);


-- Name: recipes; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.recipes (
    unique_name text NOT NULL,
    result_type text,
    build_price integer,
    build_time integer,
    skip_build_time_price integer,
    consume_on_use boolean,
    num integer,
    codex_secret boolean,
    exclude_from_codex boolean,
    always_available boolean,
    hidden boolean,
    prime_selling_price integer,
    secret_ingredient_action text
);


-- Name: region_dark_sector_data; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.region_dark_sector_data (
    region_unique_name text NOT NULL,
    resource_bonus double precision,
    xp_bonus double precision,
    weapon_xp_bonus_for text,
    weapon_xp_bonus_val double precision
);


-- Name: region_reward_manifests; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.region_reward_manifests (
    region_unique_name text NOT NULL,
    slot integer NOT NULL,
    manifest text NOT NULL
);


-- Name: regions; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.regions (
    unique_name text NOT NULL,
    name_loc text,
    system_index integer,
    system_name_loc text,
    node_type integer,
    mastery_req integer,
    mission_index integer,
    mission_name_loc text,
    faction_index integer,
    faction_name_loc text,
    secondary_faction_index integer,
    secondary_faction_name_loc text,
    min_enemy_level integer,
    max_enemy_level integer,
    mastery_exp integer,
    cache_reward_manifest text,
    quest_req text,
    hidden boolean
);


-- Name: relics; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.relics (
    unique_name text NOT NULL,
    category text,
    era text,
    icon text,
    codex_secret boolean,
    description_loc text,
    quality text,
    reward_manifest text
);


-- Name: resource_dissection_parts; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.resource_dissection_parts (
    resource_unique_name text NOT NULL,
    slot integer NOT NULL,
    item_type text NOT NULL,
    item_count integer NOT NULL
);


-- Name: resource_sockets; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.resource_sockets (
    resource_unique_name text NOT NULL,
    slot integer NOT NULL,
    socket text NOT NULL
);


-- Name: resources; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.resources (
    unique_name text NOT NULL,
    name_loc text,
    description_loc text,
    icon text,
    codex_secret boolean,
    parent_name text,
    product_category text,
    exclude_from_codex boolean,
    show_in_inventory boolean,
    long_description text,
    prime_selling_price integer
);


-- Name: sentinel_default_upgrades; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.sentinel_default_upgrades (
    sentinel_unique_name text NOT NULL,
    slot integer NOT NULL,
    item_type text NOT NULL,
    slot_num integer
);


-- Name: sentinels; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.sentinels (
    unique_name text NOT NULL,
    name_loc text,
    icon text,
    health integer,
    shield integer,
    armor integer,
    stamina integer,
    power integer,
    codex_secret boolean,
    exclude_from_codex boolean,
    description_loc text,
    product_category text,
    default_weapon text
);


-- Name: syndicate_alignments; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.syndicate_alignments (
    syndicate_unique_name text NOT NULL,
    aligned_syndicate text NOT NULL,
    value double precision NOT NULL
);


-- Name: syndicate_medallions; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.syndicate_medallions (
    syndicate_unique_name text NOT NULL,
    item_type text NOT NULL,
    standing integer NOT NULL
);


-- Name: syndicate_titles; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.syndicate_titles (
    syndicate_unique_name text NOT NULL,
    level integer NOT NULL,
    name_loc text,
    icon text,
    description_loc text
);


-- Name: syndicates; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.syndicates (
    unique_name text NOT NULL,
    name_loc text,
    icon text,
    colour text,
    background_colour text,
    description_loc text,
    medallions_capped_by_daily_limit boolean
);


-- Name: text_icons; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.text_icons (
    unique_name text NOT NULL,
    dit_ps4 text,
    dit_xbone text,
    dit_steam text,
    dit_agnostic text,
    dit_switch text,
    dit_pc text,
    dit_ps5 text,
    dit_ios text,
    dit_auto text
);


-- Name: upgrade_available_challenges; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.upgrade_available_challenges (
    challenge_id bigint NOT NULL,
    upgrade_unique_name text NOT NULL,
    slot integer NOT NULL,
    full_name text,
    description_loc text,
    count_range_min integer,
    count_range_max integer
);


-- Name: upgrade_available_challenges_challenge_id_seq; Type: SEQUENCE; Schema: public; Owner: -

CREATE SEQUENCE public.upgrade_available_challenges_challenge_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


-- Name: upgrade_available_challenges_challenge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -

ALTER SEQUENCE public.upgrade_available_challenges_challenge_id_seq OWNED BY public.upgrade_available_challenges.challenge_id;


-- Name: upgrade_challenge_complications; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.upgrade_challenge_complications (
    complication_id bigint NOT NULL,
    challenge_id bigint NOT NULL,
    slot integer NOT NULL,
    full_name text,
    description_loc text,
    override_tag_loc text
);


-- Name: upgrade_challenge_complications_complication_id_seq; Type: SEQUENCE; Schema: public; Owner: -

CREATE SEQUENCE public.upgrade_challenge_complications_complication_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


-- Name: upgrade_challenge_complications_complication_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -

ALTER SEQUENCE public.upgrade_challenge_complications_complication_id_seq OWNED BY public.upgrade_challenge_complications.complication_id;


-- Name: upgrade_compatibility_tags; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.upgrade_compatibility_tags (
    upgrade_unique_name text NOT NULL,
    tag text NOT NULL
);


-- Name: upgrade_entries; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.upgrade_entries (
    entry_id bigint NOT NULL,
    upgrade_unique_name text NOT NULL,
    slot integer NOT NULL,
    tag text,
    prefix_tag_loc text,
    suffix_tag_loc text
);


-- Name: upgrade_entries_entry_id_seq; Type: SEQUENCE; Schema: public; Owner: -

CREATE SEQUENCE public.upgrade_entries_entry_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


-- Name: upgrade_entries_entry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -

ALTER SEQUENCE public.upgrade_entries_entry_id_seq OWNED BY public.upgrade_entries.entry_id;


-- Name: upgrade_entry_values; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.upgrade_entry_values (
    entry_id bigint NOT NULL,
    slot integer NOT NULL,
    value double precision NOT NULL,
    loc_tag text,
    reverse_value_symbol boolean
);


-- Name: upgrade_mod_set_values; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.upgrade_mod_set_values (
    upgrade_unique_name text NOT NULL,
    slot integer NOT NULL,
    value double precision NOT NULL
);


-- Name: upgrades; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.upgrades (
    unique_name text NOT NULL,
    name_loc text,
    icon text,
    polarity text,
    rarity text,
    codex_secret boolean,
    base_drain integer,
    fusion_limit integer,
    compat text,
    compat_name text,
    type text,
    description_loc text,
    is_utility boolean,
    mod_set text,
    subtype text,
    exclude_from_codex boolean,
    is_starter boolean,
    is_frivolous boolean
);


-- Name: virtuals; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.virtuals (
    unique_name text NOT NULL,
    parent_name text,
    name_loc text
);


-- Name: warframes; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.warframes (
    unique_name text NOT NULL,
    name_loc text,
    parent_name text,
    description_loc text,
    icon text,
    health integer,
    shield integer,
    armor integer,
    stamina integer,
    power integer,
    codex_secret boolean,
    mastery_req integer,
    sprint_speed double precision,
    passive_description_loc text,
    product_category text,
    long_description_loc text
);


-- Name: weapon_behaviours; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.weapon_behaviours (
    behaviour_id bigint NOT NULL,
    weapon_unique_name text NOT NULL,
    slot integer NOT NULL,
    state_name_loc text
);


-- Name: weapons; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.weapons (
    unique_name text NOT NULL,
    name_loc text,
    parent_name text,
    icon text,
    codex_secret boolean,
    total_damage double precision,
    description_loc text,
    critical_chance double precision,
    critical_multiplier double precision,
    proc_chance double precision,
    fire_rate double precision,
    mastery_req integer,
    product_category text,
    holster_category text,
    slot integer,
    accuracy double precision,
    omega_attenuation double precision,
    noise text,
    trigger text,
    magazine_size integer,
    reload_time double precision,
    multishot double precision,
    blocking_angle integer,
    combo_duration integer,
    follow_through double precision,
    range double precision,
    slam_attack integer,
    slam_radial_damage integer,
    slam_radius integer,
    slide_attack integer,
    heavy_attack_damage integer,
    heavy_slam_attack integer,
    heavy_slam_radial_damage integer,
    heavy_slam_radius integer,
    wind_up double precision,
    max_level_cap integer,
    sentinel boolean,
    exclude_from_codex boolean,
    prime_omega_attenuation double precision
);


-- Name: v_localized; Type: VIEW; Schema: public; Owner: -

CREATE VIEW public.v_localized AS
 SELECT 'abilities'::text AS entity_type,
    abilities.unique_name AS entity_id,
    'name'::text AS field,
    abilities.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.abilities
     JOIN public.localizations l ON ((l.loc_tag = abilities.name_loc)))
UNION ALL
 SELECT 'abilities'::text AS entity_type,
    abilities.unique_name AS entity_id,
    'description'::text AS field,
    abilities.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.abilities
     JOIN public.localizations l ON ((l.loc_tag = abilities.description_loc)))
UNION ALL
 SELECT 'warframes'::text AS entity_type,
    warframes.unique_name AS entity_id,
    'name'::text AS field,
    warframes.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.warframes
     JOIN public.localizations l ON ((l.loc_tag = warframes.name_loc)))
UNION ALL
 SELECT 'warframes'::text AS entity_type,
    warframes.unique_name AS entity_id,
    'description'::text AS field,
    warframes.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.warframes
     JOIN public.localizations l ON ((l.loc_tag = warframes.description_loc)))
UNION ALL
 SELECT 'warframes'::text AS entity_type,
    warframes.unique_name AS entity_id,
    'passive_description'::text AS field,
    warframes.passive_description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.warframes
     JOIN public.localizations l ON ((l.loc_tag = warframes.passive_description_loc)))
UNION ALL
 SELECT 'warframes'::text AS entity_type,
    warframes.unique_name AS entity_id,
    'long_description'::text AS field,
    warframes.long_description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.warframes
     JOIN public.localizations l ON ((l.loc_tag = warframes.long_description_loc)))
UNION ALL
 SELECT 'weapons'::text AS entity_type,
    weapons.unique_name AS entity_id,
    'name'::text AS field,
    weapons.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.weapons
     JOIN public.localizations l ON ((l.loc_tag = weapons.name_loc)))
UNION ALL
 SELECT 'weapons'::text AS entity_type,
    weapons.unique_name AS entity_id,
    'description'::text AS field,
    weapons.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.weapons
     JOIN public.localizations l ON ((l.loc_tag = weapons.description_loc)))
UNION ALL
 SELECT 'railjack_weapons'::text AS entity_type,
    railjack_weapons.unique_name AS entity_id,
    'name'::text AS field,
    railjack_weapons.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.railjack_weapons
     JOIN public.localizations l ON ((l.loc_tag = railjack_weapons.name_loc)))
UNION ALL
 SELECT 'railjack_weapons'::text AS entity_type,
    railjack_weapons.unique_name AS entity_id,
    'description'::text AS field,
    railjack_weapons.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.railjack_weapons
     JOIN public.localizations l ON ((l.loc_tag = railjack_weapons.description_loc)))
UNION ALL
 SELECT 'upgrades'::text AS entity_type,
    upgrades.unique_name AS entity_id,
    'name'::text AS field,
    upgrades.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.upgrades
     JOIN public.localizations l ON ((l.loc_tag = upgrades.name_loc)))
UNION ALL
 SELECT 'upgrades'::text AS entity_type,
    upgrades.unique_name AS entity_id,
    'description'::text AS field,
    upgrades.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.upgrades
     JOIN public.localizations l ON ((l.loc_tag = upgrades.description_loc)))
UNION ALL
 SELECT 'arcanes'::text AS entity_type,
    arcanes.unique_name AS entity_id,
    'name'::text AS field,
    arcanes.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.arcanes
     JOIN public.localizations l ON ((l.loc_tag = arcanes.name_loc)))
UNION ALL
 SELECT 'avionics'::text AS entity_type,
    avionics.unique_name AS entity_id,
    'name'::text AS field,
    avionics.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.avionics
     JOIN public.localizations l ON ((l.loc_tag = avionics.name_loc)))
UNION ALL
 SELECT 'relics'::text AS entity_type,
    relics.unique_name AS entity_id,
    'description'::text AS field,
    relics.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.relics
     JOIN public.localizations l ON ((l.loc_tag = relics.description_loc)))
UNION ALL
 SELECT 'resources'::text AS entity_type,
    resources.unique_name AS entity_id,
    'name'::text AS field,
    resources.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.resources
     JOIN public.localizations l ON ((l.loc_tag = resources.name_loc)))
UNION ALL
 SELECT 'resources'::text AS entity_type,
    resources.unique_name AS entity_id,
    'description'::text AS field,
    resources.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.resources
     JOIN public.localizations l ON ((l.loc_tag = resources.description_loc)))
UNION ALL
 SELECT 'sentinels'::text AS entity_type,
    sentinels.unique_name AS entity_id,
    'name'::text AS field,
    sentinels.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.sentinels
     JOIN public.localizations l ON ((l.loc_tag = sentinels.name_loc)))
UNION ALL
 SELECT 'sentinels'::text AS entity_type,
    sentinels.unique_name AS entity_id,
    'description'::text AS field,
    sentinels.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.sentinels
     JOIN public.localizations l ON ((l.loc_tag = sentinels.description_loc)))
UNION ALL
 SELECT 'syndicates'::text AS entity_type,
    syndicates.unique_name AS entity_id,
    'name'::text AS field,
    syndicates.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.syndicates
     JOIN public.localizations l ON ((l.loc_tag = syndicates.name_loc)))
UNION ALL
 SELECT 'syndicates'::text AS entity_type,
    syndicates.unique_name AS entity_id,
    'description'::text AS field,
    syndicates.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.syndicates
     JOIN public.localizations l ON ((l.loc_tag = syndicates.description_loc)))
UNION ALL
 SELECT 'regions'::text AS entity_type,
    regions.unique_name AS entity_id,
    'name'::text AS field,
    regions.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.regions
     JOIN public.localizations l ON ((l.loc_tag = regions.name_loc)))
UNION ALL
 SELECT 'regions'::text AS entity_type,
    regions.unique_name AS entity_id,
    'system_name'::text AS field,
    regions.system_name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.regions
     JOIN public.localizations l ON ((l.loc_tag = regions.system_name_loc)))
UNION ALL
 SELECT 'regions'::text AS entity_type,
    regions.unique_name AS entity_id,
    'mission_name'::text AS field,
    regions.mission_name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.regions
     JOIN public.localizations l ON ((l.loc_tag = regions.mission_name_loc)))
UNION ALL
 SELECT 'regions'::text AS entity_type,
    regions.unique_name AS entity_id,
    'faction_name'::text AS field,
    regions.faction_name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.regions
     JOIN public.localizations l ON ((l.loc_tag = regions.faction_name_loc)))
UNION ALL
 SELECT 'regions'::text AS entity_type,
    regions.unique_name AS entity_id,
    'secondary_faction_name'::text AS field,
    regions.secondary_faction_name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.regions
     JOIN public.localizations l ON ((l.loc_tag = regions.secondary_faction_name_loc)))
UNION ALL
 SELECT 'keys'::text AS entity_type,
    keys.unique_name AS entity_id,
    'name'::text AS field,
    keys.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.keys
     JOIN public.localizations l ON ((l.loc_tag = keys.name_loc)))
UNION ALL
 SELECT 'keys'::text AS entity_type,
    keys.unique_name AS entity_id,
    'description'::text AS field,
    keys.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.keys
     JOIN public.localizations l ON ((l.loc_tag = keys.description_loc)))
UNION ALL
 SELECT 'gear'::text AS entity_type,
    gear.unique_name AS entity_id,
    'name'::text AS field,
    gear.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.gear
     JOIN public.localizations l ON ((l.loc_tag = gear.name_loc)))
UNION ALL
 SELECT 'gear'::text AS entity_type,
    gear.unique_name AS entity_id,
    'description'::text AS field,
    gear.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.gear
     JOIN public.localizations l ON ((l.loc_tag = gear.description_loc)))
UNION ALL
 SELECT 'bundles'::text AS entity_type,
    bundles.unique_name AS entity_id,
    'name'::text AS field,
    bundles.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.bundles
     JOIN public.localizations l ON ((l.loc_tag = bundles.name_loc)))
UNION ALL
 SELECT 'bundles'::text AS entity_type,
    bundles.unique_name AS entity_id,
    'description'::text AS field,
    bundles.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.bundles
     JOIN public.localizations l ON ((l.loc_tag = bundles.description_loc)))
UNION ALL
 SELECT 'booster_packs'::text AS entity_type,
    booster_packs.unique_name AS entity_id,
    'name'::text AS field,
    booster_packs.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.booster_packs
     JOIN public.localizations l ON ((l.loc_tag = booster_packs.name_loc)))
UNION ALL
 SELECT 'booster_packs'::text AS entity_type,
    booster_packs.unique_name AS entity_id,
    'description'::text AS field,
    booster_packs.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.booster_packs
     JOIN public.localizations l ON ((l.loc_tag = booster_packs.description_loc)))
UNION ALL
 SELECT 'customs'::text AS entity_type,
    customs.unique_name AS entity_id,
    'name'::text AS field,
    customs.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.customs
     JOIN public.localizations l ON ((l.loc_tag = customs.name_loc)))
UNION ALL
 SELECT 'customs'::text AS entity_type,
    customs.unique_name AS entity_id,
    'description'::text AS field,
    customs.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.customs
     JOIN public.localizations l ON ((l.loc_tag = customs.description_loc)))
UNION ALL
 SELECT 'drones'::text AS entity_type,
    drones.unique_name AS entity_id,
    'name'::text AS field,
    drones.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.drones
     JOIN public.localizations l ON ((l.loc_tag = drones.name_loc)))
UNION ALL
 SELECT 'drones'::text AS entity_type,
    drones.unique_name AS entity_id,
    'description'::text AS field,
    drones.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.drones
     JOIN public.localizations l ON ((l.loc_tag = drones.description_loc)))
UNION ALL
 SELECT 'flavour_items'::text AS entity_type,
    flavour_items.unique_name AS entity_id,
    'name'::text AS field,
    flavour_items.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.flavour_items
     JOIN public.localizations l ON ((l.loc_tag = flavour_items.name_loc)))
UNION ALL
 SELECT 'flavour_items'::text AS entity_type,
    flavour_items.unique_name AS entity_id,
    'description'::text AS field,
    flavour_items.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.flavour_items
     JOIN public.localizations l ON ((l.loc_tag = flavour_items.description_loc)))
UNION ALL
 SELECT 'focus_upgrades'::text AS entity_type,
    focus_upgrades.unique_name AS entity_id,
    'name'::text AS field,
    focus_upgrades.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.focus_upgrades
     JOIN public.localizations l ON ((l.loc_tag = focus_upgrades.name_loc)))
UNION ALL
 SELECT 'focus_upgrades'::text AS entity_type,
    focus_upgrades.unique_name AS entity_id,
    'description'::text AS field,
    focus_upgrades.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.focus_upgrades
     JOIN public.localizations l ON ((l.loc_tag = focus_upgrades.description_loc)))
UNION ALL
 SELECT 'fusion_bundles'::text AS entity_type,
    fusion_bundles.unique_name AS entity_id,
    'name'::text AS field,
    fusion_bundles.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.fusion_bundles
     JOIN public.localizations l ON ((l.loc_tag = fusion_bundles.name_loc)))
UNION ALL
 SELECT 'fusion_bundles'::text AS entity_type,
    fusion_bundles.unique_name AS entity_id,
    'description'::text AS field,
    fusion_bundles.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.fusion_bundles
     JOIN public.localizations l ON ((l.loc_tag = fusion_bundles.description_loc)))
UNION ALL
 SELECT 'intrinsics'::text AS entity_type,
    intrinsics.unique_name AS entity_id,
    'name'::text AS field,
    intrinsics.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.intrinsics
     JOIN public.localizations l ON ((l.loc_tag = intrinsics.name_loc)))
UNION ALL
 SELECT 'intrinsics'::text AS entity_type,
    intrinsics.unique_name AS entity_id,
    'description'::text AS field,
    intrinsics.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.intrinsics
     JOIN public.localizations l ON ((l.loc_tag = intrinsics.description_loc)))
UNION ALL
 SELECT 'mod_sets'::text AS entity_type,
    mod_sets.unique_name AS entity_id,
    'description'::text AS field,
    mod_sets.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.mod_sets
     JOIN public.localizations l ON ((l.loc_tag = mod_sets.description_loc)))
UNION ALL
 SELECT 'virtuals'::text AS entity_type,
    virtuals.unique_name AS entity_id,
    'name'::text AS field,
    virtuals.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.virtuals
     JOIN public.localizations l ON ((l.loc_tag = virtuals.name_loc)))
UNION ALL
 SELECT 'enemy_avatars'::text AS entity_type,
    enemy_avatars.unique_name AS entity_id,
    'name'::text AS field,
    enemy_avatars.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.enemy_avatars
     JOIN public.localizations l ON ((l.loc_tag = enemy_avatars.name_loc)))
UNION ALL
 SELECT 'enemy_avatars'::text AS entity_type,
    enemy_avatars.unique_name AS entity_id,
    'description'::text AS field,
    enemy_avatars.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.enemy_avatars
     JOIN public.localizations l ON ((l.loc_tag = enemy_avatars.description_loc)))
UNION ALL
 SELECT 'enemy_ai_weapons'::text AS entity_type,
    enemy_ai_weapons.unique_name AS entity_id,
    'name'::text AS field,
    enemy_ai_weapons.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.enemy_ai_weapons
     JOIN public.localizations l ON ((l.loc_tag = enemy_ai_weapons.name_loc)))
UNION ALL
 SELECT 'enemy_ai_weapons'::text AS entity_type,
    enemy_ai_weapons.unique_name AS entity_id,
    'description'::text AS field,
    enemy_ai_weapons.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.enemy_ai_weapons
     JOIN public.localizations l ON ((l.loc_tag = enemy_ai_weapons.description_loc)))
UNION ALL
 SELECT 'achievements'::text AS entity_type,
    achievements.unique_name AS entity_id,
    'name'::text AS field,
    achievements.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.achievements
     JOIN public.localizations l ON ((l.loc_tag = achievements.name_loc)))
UNION ALL
 SELECT 'achievements'::text AS entity_type,
    achievements.unique_name AS entity_id,
    'description'::text AS field,
    achievements.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.achievements
     JOIN public.localizations l ON ((l.loc_tag = achievements.description_loc)))
UNION ALL
 SELECT 'nightwave_challenges'::text AS entity_type,
    nightwave_challenges.challenge_key AS entity_id,
    'name'::text AS field,
    nightwave_challenges.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.nightwave_challenges
     JOIN public.localizations l ON ((l.loc_tag = nightwave_challenges.name_loc)))
UNION ALL
 SELECT 'nightwave_challenges'::text AS entity_type,
    nightwave_challenges.challenge_key AS entity_id,
    'description'::text AS field,
    nightwave_challenges.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.nightwave_challenges
     JOIN public.localizations l ON ((l.loc_tag = nightwave_challenges.description_loc)))
UNION ALL
 SELECT 'nightwave_challenges'::text AS entity_type,
    nightwave_challenges.challenge_key AS entity_id,
    'tip'::text AS field,
    nightwave_challenges.tip_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.nightwave_challenges
     JOIN public.localizations l ON ((l.loc_tag = nightwave_challenges.tip_loc)))
UNION ALL
 SELECT 'nightwave_rewards'::text AS entity_type,
    nightwave_rewards.unique_name AS entity_id,
    'name'::text AS field,
    nightwave_rewards.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.nightwave_rewards
     JOIN public.localizations l ON ((l.loc_tag = nightwave_rewards.name_loc)))
UNION ALL
 SELECT 'nightwave_rewards'::text AS entity_type,
    nightwave_rewards.unique_name AS entity_id,
    'description'::text AS field,
    nightwave_rewards.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.nightwave_rewards
     JOIN public.localizations l ON ((l.loc_tag = nightwave_rewards.description_loc)))
UNION ALL
 SELECT 'weapon_behaviours'::text AS entity_type,
    weapon_behaviours.weapon_unique_name AS entity_id,
    'state_name'::text AS field,
    weapon_behaviours.state_name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.weapon_behaviours
     JOIN public.localizations l ON ((l.loc_tag = weapon_behaviours.state_name_loc)))
UNION ALL
 SELECT 'railjack_weapon_behaviours'::text AS entity_type,
    railjack_weapon_behaviours.weapon_unique_name AS entity_id,
    'state_name'::text AS field,
    railjack_weapon_behaviours.state_name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.railjack_weapon_behaviours
     JOIN public.localizations l ON ((l.loc_tag = railjack_weapon_behaviours.state_name_loc)))
UNION ALL
 SELECT 'enemy_ai_weapon_behaviours'::text AS entity_type,
    enemy_ai_weapon_behaviours.ai_weapon_unique_name AS entity_id,
    'state_name'::text AS field,
    enemy_ai_weapon_behaviours.state_name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.enemy_ai_weapon_behaviours
     JOIN public.localizations l ON ((l.loc_tag = enemy_ai_weapon_behaviours.state_name_loc)))
UNION ALL
 SELECT 'upgrade_entries'::text AS entity_type,
    upgrade_entries.upgrade_unique_name AS entity_id,
    'prefix_tag'::text AS field,
    upgrade_entries.prefix_tag_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.upgrade_entries
     JOIN public.localizations l ON ((l.loc_tag = upgrade_entries.prefix_tag_loc)))
UNION ALL
 SELECT 'upgrade_entries'::text AS entity_type,
    upgrade_entries.upgrade_unique_name AS entity_id,
    'suffix_tag'::text AS field,
    upgrade_entries.suffix_tag_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.upgrade_entries
     JOIN public.localizations l ON ((l.loc_tag = upgrade_entries.suffix_tag_loc)))
UNION ALL
 SELECT 'upgrade_entry_values'::text AS entity_type,
    (upgrade_entry_values.entry_id)::text AS entity_id,
    'value_loc_tag'::text AS field,
    upgrade_entry_values.loc_tag,
    l.lang,
    l.value
   FROM (public.upgrade_entry_values
     JOIN public.localizations l ON ((l.loc_tag = upgrade_entry_values.loc_tag)))
UNION ALL
 SELECT 'upgrade_available_challenges'::text AS entity_type,
    upgrade_available_challenges.upgrade_unique_name AS entity_id,
    'description'::text AS field,
    upgrade_available_challenges.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.upgrade_available_challenges
     JOIN public.localizations l ON ((l.loc_tag = upgrade_available_challenges.description_loc)))
UNION ALL
 SELECT 'upgrade_challenge_complications'::text AS entity_type,
    (upgrade_challenge_complications.challenge_id)::text AS entity_id,
    'description'::text AS field,
    upgrade_challenge_complications.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.upgrade_challenge_complications
     JOIN public.localizations l ON ((l.loc_tag = upgrade_challenge_complications.description_loc)))
UNION ALL
 SELECT 'upgrade_challenge_complications'::text AS entity_type,
    (upgrade_challenge_complications.challenge_id)::text AS entity_id,
    'override_tag'::text AS field,
    upgrade_challenge_complications.override_tag_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.upgrade_challenge_complications
     JOIN public.localizations l ON ((l.loc_tag = upgrade_challenge_complications.override_tag_loc)))
UNION ALL
 SELECT 'key_chain_stages'::text AS entity_type,
    key_chain_stages.key_unique_name AS entity_id,
    'message_sender'::text AS field,
    key_chain_stages.message_sender_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.key_chain_stages
     JOIN public.localizations l ON ((l.loc_tag = key_chain_stages.message_sender_loc)))
UNION ALL
 SELECT 'key_chain_stages'::text AS entity_type,
    key_chain_stages.key_unique_name AS entity_id,
    'message_title'::text AS field,
    key_chain_stages.message_title_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.key_chain_stages
     JOIN public.localizations l ON ((l.loc_tag = key_chain_stages.message_title_loc)))
UNION ALL
 SELECT 'key_chain_stages'::text AS entity_type,
    key_chain_stages.key_unique_name AS entity_id,
    'message_body'::text AS field,
    key_chain_stages.message_body_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.key_chain_stages
     JOIN public.localizations l ON ((l.loc_tag = key_chain_stages.message_body_loc)))
UNION ALL
 SELECT 'syndicate_titles'::text AS entity_type,
    syndicate_titles.syndicate_unique_name AS entity_id,
    'name'::text AS field,
    syndicate_titles.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.syndicate_titles
     JOIN public.localizations l ON ((l.loc_tag = syndicate_titles.name_loc)))
UNION ALL
 SELECT 'syndicate_titles'::text AS entity_type,
    syndicate_titles.syndicate_unique_name AS entity_id,
    'description'::text AS field,
    syndicate_titles.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.syndicate_titles
     JOIN public.localizations l ON ((l.loc_tag = syndicate_titles.description_loc)))
UNION ALL
 SELECT 'intrinsic_ranks'::text AS entity_type,
    intrinsic_ranks.intrinsic_unique_name AS entity_id,
    'name'::text AS field,
    intrinsic_ranks.name_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.intrinsic_ranks
     JOIN public.localizations l ON ((l.loc_tag = intrinsic_ranks.name_loc)))
UNION ALL
 SELECT 'intrinsic_ranks'::text AS entity_type,
    intrinsic_ranks.intrinsic_unique_name AS entity_id,
    'description'::text AS field,
    intrinsic_ranks.description_loc AS loc_tag,
    l.lang,
    l.value
   FROM (public.intrinsic_ranks
     JOIN public.localizations l ON ((l.loc_tag = intrinsic_ranks.description_loc)));


-- Name: warframe_abilities; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.warframe_abilities (
    warframe_unique_name text NOT NULL,
    ability_unique_name text NOT NULL,
    slot integer NOT NULL
);


-- Name: warframe_exalted; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.warframe_exalted (
    warframe_unique_name text NOT NULL,
    slot integer NOT NULL,
    exalted_unique_name text NOT NULL
);


-- Name: weapon_behaviour_damage; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.weapon_behaviour_damage (
    behaviour_id bigint NOT NULL,
    path text NOT NULL,
    damage_type text NOT NULL,
    value double precision NOT NULL
);


-- Name: weapon_behaviours_behaviour_id_seq; Type: SEQUENCE; Schema: public; Owner: -

CREATE SEQUENCE public.weapon_behaviours_behaviour_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


-- Name: weapon_behaviours_behaviour_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -

ALTER SEQUENCE public.weapon_behaviours_behaviour_id_seq OWNED BY public.weapon_behaviours.behaviour_id;


-- Name: weapon_compatibility_tags; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.weapon_compatibility_tags (
    weapon_unique_name text NOT NULL,
    tag text NOT NULL
);


-- Name: weapon_damage_per_shot; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.weapon_damage_per_shot (
    weapon_unique_name text NOT NULL,
    slot integer NOT NULL,
    value double precision NOT NULL
);


-- Name: enemy_ai_weapon_behaviours behaviour_id; Type: DEFAULT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_ai_weapon_behaviours ALTER COLUMN behaviour_id SET DEFAULT nextval('public.enemy_ai_weapon_behaviours_behaviour_id_seq'::regclass);


-- Name: enemy_droptable_pools pool_id; Type: DEFAULT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_droptable_pools ALTER COLUMN pool_id SET DEFAULT nextval('public.enemy_droptable_pools_pool_id_seq'::regclass);


-- Name: export_sources source_id; Type: DEFAULT; Schema: public; Owner: -

ALTER TABLE ONLY public.export_sources ALTER COLUMN source_id SET DEFAULT nextval('public.export_sources_source_id_seq'::regclass);


-- Name: key_chain_stages stage_id; Type: DEFAULT; Schema: public; Owner: -

ALTER TABLE ONLY public.key_chain_stages ALTER COLUMN stage_id SET DEFAULT nextval('public.key_chain_stages_stage_id_seq'::regclass);


-- Name: mission_reward_tiers tier_id; Type: DEFAULT; Schema: public; Owner: -

ALTER TABLE ONLY public.mission_reward_tiers ALTER COLUMN tier_id SET DEFAULT nextval('public.mission_reward_tiers_tier_id_seq'::regclass);


-- Name: railjack_weapon_behaviours behaviour_id; Type: DEFAULT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapon_behaviours ALTER COLUMN behaviour_id SET DEFAULT nextval('public.railjack_weapon_behaviours_behaviour_id_seq'::regclass);


-- Name: upgrade_available_challenges challenge_id; Type: DEFAULT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_available_challenges ALTER COLUMN challenge_id SET DEFAULT nextval('public.upgrade_available_challenges_challenge_id_seq'::regclass);


-- Name: upgrade_challenge_complications complication_id; Type: DEFAULT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_challenge_complications ALTER COLUMN complication_id SET DEFAULT nextval('public.upgrade_challenge_complications_complication_id_seq'::regclass);


-- Name: upgrade_entries entry_id; Type: DEFAULT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_entries ALTER COLUMN entry_id SET DEFAULT nextval('public.upgrade_entries_entry_id_seq'::regclass);


-- Name: weapon_behaviours behaviour_id; Type: DEFAULT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapon_behaviours ALTER COLUMN behaviour_id SET DEFAULT nextval('public.weapon_behaviours_behaviour_id_seq'::regclass);


-- Name: abilities abilities_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.abilities
    ADD CONSTRAINT abilities_pkey PRIMARY KEY (unique_name);


-- Name: achievement_children achievement_children_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.achievement_children
    ADD CONSTRAINT achievement_children_pkey PRIMARY KEY (achievement_unique_name, child_unique_name);


-- Name: achievements achievements_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.achievements
    ADD CONSTRAINT achievements_pkey PRIMARY KEY (unique_name);


-- Name: arcanes arcanes_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.arcanes
    ADD CONSTRAINT arcanes_pkey PRIMARY KEY (unique_name);


-- Name: avionics avionics_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.avionics
    ADD CONSTRAINT avionics_pkey PRIMARY KEY (unique_name);


-- Name: booster_pack_components booster_pack_components_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.booster_pack_components
    ADD CONSTRAINT booster_pack_components_pkey PRIMARY KEY (pack_unique_name, slot);


-- Name: booster_pack_rarity_weights booster_pack_rarity_weights_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.booster_pack_rarity_weights
    ADD CONSTRAINT booster_pack_rarity_weights_pkey PRIMARY KEY (pack_unique_name, roll_index, rarity);


-- Name: booster_packs booster_packs_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.booster_packs
    ADD CONSTRAINT booster_packs_pkey PRIMARY KEY (unique_name);


-- Name: bundle_components bundle_components_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.bundle_components
    ADD CONSTRAINT bundle_components_pkey PRIMARY KEY (bundle_unique_name, slot);


-- Name: bundles bundles_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.bundles
    ADD CONSTRAINT bundles_pkey PRIMARY KEY (unique_name);


-- Name: customs customs_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.customs
    ADD CONSTRAINT customs_pkey PRIMARY KEY (unique_name);


-- Name: drone_capacity_multipliers drone_capacity_multipliers_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.drone_capacity_multipliers
    ADD CONSTRAINT drone_capacity_multipliers_pkey PRIMARY KEY (drone_unique_name, slot);


-- Name: drones drones_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.drones
    ADD CONSTRAINT drones_pkey PRIMARY KEY (unique_name);


-- Name: enemy_agent_items enemy_agent_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_agent_items
    ADD CONSTRAINT enemy_agent_items_pkey PRIMARY KEY (agent_unique_name, slot);


-- Name: enemy_agents enemy_agents_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_agents
    ADD CONSTRAINT enemy_agents_pkey PRIMARY KEY (unique_name);


-- Name: enemy_ai_weapon_behaviour_damage enemy_ai_weapon_behaviour_damage_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_ai_weapon_behaviour_damage
    ADD CONSTRAINT enemy_ai_weapon_behaviour_damage_pkey PRIMARY KEY (behaviour_id, path, damage_type);


-- Name: enemy_ai_weapon_behaviours enemy_ai_weapon_behaviours_ai_weapon_unique_name_slot_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_ai_weapon_behaviours
    ADD CONSTRAINT enemy_ai_weapon_behaviours_ai_weapon_unique_name_slot_key UNIQUE (ai_weapon_unique_name, slot);


-- Name: enemy_ai_weapon_behaviours enemy_ai_weapon_behaviours_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_ai_weapon_behaviours
    ADD CONSTRAINT enemy_ai_weapon_behaviours_pkey PRIMARY KEY (behaviour_id);


-- Name: enemy_ai_weapons enemy_ai_weapons_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_ai_weapons
    ADD CONSTRAINT enemy_ai_weapons_pkey PRIMARY KEY (unique_name);


-- Name: enemy_avatars enemy_avatars_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_avatars
    ADD CONSTRAINT enemy_avatars_pkey PRIMARY KEY (unique_name);


-- Name: enemy_damage_controller_hit_proxies enemy_damage_controller_hit_proxies_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_damage_controller_hit_proxies
    ADD CONSTRAINT enemy_damage_controller_hit_proxies_pkey PRIMARY KEY (controller_unique_name, slot);


-- Name: enemy_damage_controller_procs enemy_damage_controller_procs_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_damage_controller_procs
    ADD CONSTRAINT enemy_damage_controller_procs_pkey PRIMARY KEY (controller_unique_name, slot);


-- Name: enemy_damage_controllers enemy_damage_controllers_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_damage_controllers
    ADD CONSTRAINT enemy_damage_controllers_pkey PRIMARY KEY (unique_name);


-- Name: enemy_droptable_items enemy_droptable_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_droptable_items
    ADD CONSTRAINT enemy_droptable_items_pkey PRIMARY KEY (pool_id, slot);


-- Name: enemy_droptable_pools enemy_droptable_pools_droptable_unique_name_pool_index_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_droptable_pools
    ADD CONSTRAINT enemy_droptable_pools_droptable_unique_name_pool_index_key UNIQUE (droptable_unique_name, pool_index);


-- Name: enemy_droptable_pools enemy_droptable_pools_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_droptable_pools
    ADD CONSTRAINT enemy_droptable_pools_pkey PRIMARY KEY (pool_id);


-- Name: enemy_droptables enemy_droptables_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_droptables
    ADD CONSTRAINT enemy_droptables_pkey PRIMARY KEY (unique_name);


-- Name: enemy_hit_proxies enemy_hit_proxies_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_hit_proxies
    ADD CONSTRAINT enemy_hit_proxies_pkey PRIMARY KEY (unique_name);


-- Name: export_sources export_sources_file_name_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.export_sources
    ADD CONSTRAINT export_sources_file_name_key UNIQUE (file_name);


-- Name: export_sources export_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.export_sources
    ADD CONSTRAINT export_sources_pkey PRIMARY KEY (source_id);


-- Name: flavour_colours flavour_colours_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.flavour_colours
    ADD CONSTRAINT flavour_colours_pkey PRIMARY KEY (flavour_unique_name, kind, slot);


-- Name: flavour_items flavour_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.flavour_items
    ADD CONSTRAINT flavour_items_pkey PRIMARY KEY (unique_name);


-- Name: focus_upgrade_level_stats focus_upgrade_level_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.focus_upgrade_level_stats
    ADD CONSTRAINT focus_upgrade_level_stats_pkey PRIMARY KEY (focus_unique_name, level, stat_key);


-- Name: focus_upgrades focus_upgrades_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.focus_upgrades
    ADD CONSTRAINT focus_upgrades_pkey PRIMARY KEY (unique_name);


-- Name: fusion_bundles fusion_bundles_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.fusion_bundles
    ADD CONSTRAINT fusion_bundles_pkey PRIMARY KEY (unique_name);


-- Name: gear gear_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.gear
    ADD CONSTRAINT gear_pkey PRIMARY KEY (unique_name);


-- Name: images images_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (unique_name);


-- Name: intrinsic_ranks intrinsic_ranks_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.intrinsic_ranks
    ADD CONSTRAINT intrinsic_ranks_pkey PRIMARY KEY (intrinsic_unique_name, rank_index);


-- Name: intrinsics intrinsics_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.intrinsics
    ADD CONSTRAINT intrinsics_pkey PRIMARY KEY (unique_name);


-- Name: key_chain_stage_items key_chain_stage_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.key_chain_stage_items
    ADD CONSTRAINT key_chain_stage_items_pkey PRIMARY KEY (stage_id, slot);


-- Name: key_chain_stages key_chain_stages_key_unique_name_stage_index_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.key_chain_stages
    ADD CONSTRAINT key_chain_stages_key_unique_name_stage_index_key UNIQUE (key_unique_name, stage_index);


-- Name: key_chain_stages key_chain_stages_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.key_chain_stages
    ADD CONSTRAINT key_chain_stages_pkey PRIMARY KEY (stage_id);


-- Name: key_rewards key_rewards_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.key_rewards
    ADD CONSTRAINT key_rewards_pkey PRIMARY KEY (key_unique_name, slot);


-- Name: keys keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.keys
    ADD CONSTRAINT keys_pkey PRIMARY KEY (unique_name);


-- Name: languages languages_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.languages
    ADD CONSTRAINT languages_pkey PRIMARY KEY (code);


-- Name: localizations localizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.localizations
    ADD CONSTRAINT localizations_pkey PRIMARY KEY (loc_tag, lang);


-- Name: misc_booster_durations misc_booster_durations_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.misc_booster_durations
    ADD CONSTRAINT misc_booster_durations_pkey PRIMARY KEY (rarity);


-- Name: misc misc_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.misc
    ADD CONSTRAINT misc_pkey PRIMARY KEY (id);


-- Name: misc_unique_level_caps misc_unique_level_caps_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.misc_unique_level_caps
    ADD CONSTRAINT misc_unique_level_caps_pkey PRIMARY KEY (level_cap_key);


-- Name: mission_reward_decks mission_reward_decks_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.mission_reward_decks
    ADD CONSTRAINT mission_reward_decks_pkey PRIMARY KEY (unique_name);


-- Name: mission_reward_items mission_reward_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.mission_reward_items
    ADD CONSTRAINT mission_reward_items_pkey PRIMARY KEY (tier_id, slot);


-- Name: mission_reward_tiers mission_reward_tiers_deck_unique_name_tier_index_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.mission_reward_tiers
    ADD CONSTRAINT mission_reward_tiers_deck_unique_name_tier_index_key UNIQUE (deck_unique_name, tier_index);


-- Name: mission_reward_tiers mission_reward_tiers_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.mission_reward_tiers
    ADD CONSTRAINT mission_reward_tiers_pkey PRIMARY KEY (tier_id);


-- Name: mod_set_level_stats mod_set_level_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.mod_set_level_stats
    ADD CONSTRAINT mod_set_level_stats_pkey PRIMARY KEY (mod_set_unique_name, level, stat_key);


-- Name: mod_sets mod_sets_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.mod_sets
    ADD CONSTRAINT mod_sets_pkey PRIMARY KEY (unique_name);


-- Name: nightwave_challenges nightwave_challenges_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.nightwave_challenges
    ADD CONSTRAINT nightwave_challenges_pkey PRIMARY KEY (challenge_key);


-- Name: nightwave nightwave_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.nightwave
    ADD CONSTRAINT nightwave_pkey PRIMARY KEY (id);


-- Name: nightwave_rewards nightwave_rewards_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.nightwave_rewards
    ADD CONSTRAINT nightwave_rewards_pkey PRIMARY KEY (unique_name);


-- Name: railjack_weapon_behaviour_damage railjack_weapon_behaviour_damage_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapon_behaviour_damage
    ADD CONSTRAINT railjack_weapon_behaviour_damage_pkey PRIMARY KEY (behaviour_id, path, damage_type);


-- Name: railjack_weapon_behaviours railjack_weapon_behaviours_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapon_behaviours
    ADD CONSTRAINT railjack_weapon_behaviours_pkey PRIMARY KEY (behaviour_id);


-- Name: railjack_weapon_behaviours railjack_weapon_behaviours_weapon_unique_name_slot_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapon_behaviours
    ADD CONSTRAINT railjack_weapon_behaviours_weapon_unique_name_slot_key UNIQUE (weapon_unique_name, slot);


-- Name: railjack_weapon_compatibility_tags railjack_weapon_compatibility_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapon_compatibility_tags
    ADD CONSTRAINT railjack_weapon_compatibility_tags_pkey PRIMARY KEY (weapon_unique_name, tag);


-- Name: railjack_weapon_damage_per_shot railjack_weapon_damage_per_shot_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapon_damage_per_shot
    ADD CONSTRAINT railjack_weapon_damage_per_shot_pkey PRIMARY KEY (weapon_unique_name, slot);


-- Name: railjack_weapons railjack_weapons_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapons
    ADD CONSTRAINT railjack_weapons_pkey PRIMARY KEY (unique_name);


-- Name: recipe_ingredients recipe_ingredients_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.recipe_ingredients
    ADD CONSTRAINT recipe_ingredients_pkey PRIMARY KEY (recipe_unique_name, slot);


-- Name: recipe_secret_ingredients recipe_secret_ingredients_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.recipe_secret_ingredients
    ADD CONSTRAINT recipe_secret_ingredients_pkey PRIMARY KEY (recipe_unique_name, slot);


-- Name: recipes recipes_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.recipes
    ADD CONSTRAINT recipes_pkey PRIMARY KEY (unique_name);


-- Name: region_dark_sector_data region_dark_sector_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.region_dark_sector_data
    ADD CONSTRAINT region_dark_sector_data_pkey PRIMARY KEY (region_unique_name);


-- Name: region_reward_manifests region_reward_manifests_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.region_reward_manifests
    ADD CONSTRAINT region_reward_manifests_pkey PRIMARY KEY (region_unique_name, slot);


-- Name: regions regions_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.regions
    ADD CONSTRAINT regions_pkey PRIMARY KEY (unique_name);


-- Name: relics relics_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.relics
    ADD CONSTRAINT relics_pkey PRIMARY KEY (unique_name);


-- Name: resource_dissection_parts resource_dissection_parts_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.resource_dissection_parts
    ADD CONSTRAINT resource_dissection_parts_pkey PRIMARY KEY (resource_unique_name, slot);


-- Name: resource_sockets resource_sockets_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.resource_sockets
    ADD CONSTRAINT resource_sockets_pkey PRIMARY KEY (resource_unique_name, slot);


-- Name: resources resources_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.resources
    ADD CONSTRAINT resources_pkey PRIMARY KEY (unique_name);


-- Name: sentinel_default_upgrades sentinel_default_upgrades_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.sentinel_default_upgrades
    ADD CONSTRAINT sentinel_default_upgrades_pkey PRIMARY KEY (sentinel_unique_name, slot);


-- Name: sentinels sentinels_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.sentinels
    ADD CONSTRAINT sentinels_pkey PRIMARY KEY (unique_name);


-- Name: syndicate_alignments syndicate_alignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.syndicate_alignments
    ADD CONSTRAINT syndicate_alignments_pkey PRIMARY KEY (syndicate_unique_name, aligned_syndicate);


-- Name: syndicate_medallions syndicate_medallions_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.syndicate_medallions
    ADD CONSTRAINT syndicate_medallions_pkey PRIMARY KEY (syndicate_unique_name, item_type);


-- Name: syndicate_titles syndicate_titles_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.syndicate_titles
    ADD CONSTRAINT syndicate_titles_pkey PRIMARY KEY (syndicate_unique_name, level);


-- Name: syndicates syndicates_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.syndicates
    ADD CONSTRAINT syndicates_pkey PRIMARY KEY (unique_name);


-- Name: text_icons text_icons_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.text_icons
    ADD CONSTRAINT text_icons_pkey PRIMARY KEY (unique_name);


-- Name: upgrade_available_challenges upgrade_available_challenges_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_available_challenges
    ADD CONSTRAINT upgrade_available_challenges_pkey PRIMARY KEY (challenge_id);


-- Name: upgrade_available_challenges upgrade_available_challenges_upgrade_unique_name_slot_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_available_challenges
    ADD CONSTRAINT upgrade_available_challenges_upgrade_unique_name_slot_key UNIQUE (upgrade_unique_name, slot);


-- Name: upgrade_challenge_complications upgrade_challenge_complications_challenge_id_slot_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_challenge_complications
    ADD CONSTRAINT upgrade_challenge_complications_challenge_id_slot_key UNIQUE (challenge_id, slot);


-- Name: upgrade_challenge_complications upgrade_challenge_complications_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_challenge_complications
    ADD CONSTRAINT upgrade_challenge_complications_pkey PRIMARY KEY (complication_id);


-- Name: upgrade_compatibility_tags upgrade_compatibility_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_compatibility_tags
    ADD CONSTRAINT upgrade_compatibility_tags_pkey PRIMARY KEY (upgrade_unique_name, tag);


-- Name: upgrade_entries upgrade_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_entries
    ADD CONSTRAINT upgrade_entries_pkey PRIMARY KEY (entry_id);


-- Name: upgrade_entries upgrade_entries_upgrade_unique_name_slot_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_entries
    ADD CONSTRAINT upgrade_entries_upgrade_unique_name_slot_key UNIQUE (upgrade_unique_name, slot);


-- Name: upgrade_entry_values upgrade_entry_values_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_entry_values
    ADD CONSTRAINT upgrade_entry_values_pkey PRIMARY KEY (entry_id, slot);


-- Name: upgrade_mod_set_values upgrade_mod_set_values_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_mod_set_values
    ADD CONSTRAINT upgrade_mod_set_values_pkey PRIMARY KEY (upgrade_unique_name, slot);


-- Name: upgrades upgrades_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrades
    ADD CONSTRAINT upgrades_pkey PRIMARY KEY (unique_name);


-- Name: virtuals virtuals_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.virtuals
    ADD CONSTRAINT virtuals_pkey PRIMARY KEY (unique_name);


-- Name: warframe_abilities warframe_abilities_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.warframe_abilities
    ADD CONSTRAINT warframe_abilities_pkey PRIMARY KEY (warframe_unique_name, slot);


-- Name: warframe_exalted warframe_exalted_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.warframe_exalted
    ADD CONSTRAINT warframe_exalted_pkey PRIMARY KEY (warframe_unique_name, slot);


-- Name: warframes warframes_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.warframes
    ADD CONSTRAINT warframes_pkey PRIMARY KEY (unique_name);


-- Name: weapon_behaviour_damage weapon_behaviour_damage_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapon_behaviour_damage
    ADD CONSTRAINT weapon_behaviour_damage_pkey PRIMARY KEY (behaviour_id, path, damage_type);


-- Name: weapon_behaviours weapon_behaviours_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapon_behaviours
    ADD CONSTRAINT weapon_behaviours_pkey PRIMARY KEY (behaviour_id);


-- Name: weapon_behaviours weapon_behaviours_weapon_unique_name_slot_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapon_behaviours
    ADD CONSTRAINT weapon_behaviours_weapon_unique_name_slot_key UNIQUE (weapon_unique_name, slot);


-- Name: weapon_compatibility_tags weapon_compatibility_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapon_compatibility_tags
    ADD CONSTRAINT weapon_compatibility_tags_pkey PRIMARY KEY (weapon_unique_name, tag);


-- Name: weapon_damage_per_shot weapon_damage_per_shot_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapon_damage_per_shot
    ADD CONSTRAINT weapon_damage_per_shot_pkey PRIMARY KEY (weapon_unique_name, slot);


-- Name: weapons weapons_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapons
    ADD CONSTRAINT weapons_pkey PRIMARY KEY (unique_name);


-- Name: idx_achievement_children_child; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_achievement_children_child ON public.achievement_children USING btree (child_unique_name);


-- Name: idx_enemy_ai_weapon_behaviours_weapon; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_enemy_ai_weapon_behaviours_weapon ON public.enemy_ai_weapon_behaviours USING btree (ai_weapon_unique_name);


-- Name: idx_enemy_droptable_pools_droptable; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_enemy_droptable_pools_droptable ON public.enemy_droptable_pools USING btree (droptable_unique_name);


-- Name: idx_key_chain_stages_key; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_key_chain_stages_key ON public.key_chain_stages USING btree (key_unique_name);


-- Name: idx_localizations_lang; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_localizations_lang ON public.localizations USING btree (lang);


-- Name: idx_localizations_loc_tag_trgm; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_localizations_loc_tag_trgm ON public.localizations USING gin (loc_tag public.gin_trgm_ops);


-- Name: idx_localizations_value_hash; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_localizations_value_hash ON public.localizations USING hash (value);


-- Name: idx_localizations_value_trgm; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_localizations_value_trgm ON public.localizations USING gin (value public.gin_trgm_ops);


-- Name: idx_mission_reward_tiers_deck; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_mission_reward_tiers_deck ON public.mission_reward_tiers USING btree (deck_unique_name);


-- Name: idx_railjack_weapon_behaviours_weapon; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_railjack_weapon_behaviours_weapon ON public.railjack_weapon_behaviours USING btree (weapon_unique_name);


-- Name: idx_upgrade_available_challenges_upgrade; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_upgrade_available_challenges_upgrade ON public.upgrade_available_challenges USING btree (upgrade_unique_name);


-- Name: idx_upgrade_entries_upgrade; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_upgrade_entries_upgrade ON public.upgrade_entries USING btree (upgrade_unique_name);


-- Name: idx_warframe_abilities_ability; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_warframe_abilities_ability ON public.warframe_abilities USING btree (ability_unique_name);


-- Name: idx_weapon_behaviours_weapon; Type: INDEX; Schema: public; Owner: -

CREATE INDEX idx_weapon_behaviours_weapon ON public.weapon_behaviours USING btree (weapon_unique_name);


-- Name: achievement_children achievement_children_achievement_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.achievement_children
    ADD CONSTRAINT achievement_children_achievement_unique_name_fkey FOREIGN KEY (achievement_unique_name) REFERENCES public.achievements(unique_name) ON DELETE CASCADE;


-- Name: achievement_children achievement_children_child_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.achievement_children
    ADD CONSTRAINT achievement_children_child_unique_name_fkey FOREIGN KEY (child_unique_name) REFERENCES public.achievements(unique_name) ON DELETE CASCADE;


-- Name: booster_pack_components booster_pack_components_pack_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.booster_pack_components
    ADD CONSTRAINT booster_pack_components_pack_unique_name_fkey FOREIGN KEY (pack_unique_name) REFERENCES public.booster_packs(unique_name) ON DELETE CASCADE;


-- Name: booster_pack_rarity_weights booster_pack_rarity_weights_pack_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.booster_pack_rarity_weights
    ADD CONSTRAINT booster_pack_rarity_weights_pack_unique_name_fkey FOREIGN KEY (pack_unique_name) REFERENCES public.booster_packs(unique_name) ON DELETE CASCADE;


-- Name: bundle_components bundle_components_bundle_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.bundle_components
    ADD CONSTRAINT bundle_components_bundle_unique_name_fkey FOREIGN KEY (bundle_unique_name) REFERENCES public.bundles(unique_name) ON DELETE CASCADE;


-- Name: drone_capacity_multipliers drone_capacity_multipliers_drone_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.drone_capacity_multipliers
    ADD CONSTRAINT drone_capacity_multipliers_drone_unique_name_fkey FOREIGN KEY (drone_unique_name) REFERENCES public.drones(unique_name) ON DELETE CASCADE;


-- Name: enemy_agent_items enemy_agent_items_agent_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_agent_items
    ADD CONSTRAINT enemy_agent_items_agent_unique_name_fkey FOREIGN KEY (agent_unique_name) REFERENCES public.enemy_agents(unique_name) ON DELETE CASCADE;


-- Name: enemy_ai_weapon_behaviour_damage enemy_ai_weapon_behaviour_damage_behaviour_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_ai_weapon_behaviour_damage
    ADD CONSTRAINT enemy_ai_weapon_behaviour_damage_behaviour_id_fkey FOREIGN KEY (behaviour_id) REFERENCES public.enemy_ai_weapon_behaviours(behaviour_id) ON DELETE CASCADE;


-- Name: enemy_ai_weapon_behaviours enemy_ai_weapon_behaviours_ai_weapon_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_ai_weapon_behaviours
    ADD CONSTRAINT enemy_ai_weapon_behaviours_ai_weapon_unique_name_fkey FOREIGN KEY (ai_weapon_unique_name) REFERENCES public.enemy_ai_weapons(unique_name) ON DELETE CASCADE;


-- Name: enemy_damage_controller_hit_proxies enemy_damage_controller_hit_proxies_controller_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_damage_controller_hit_proxies
    ADD CONSTRAINT enemy_damage_controller_hit_proxies_controller_unique_name_fkey FOREIGN KEY (controller_unique_name) REFERENCES public.enemy_damage_controllers(unique_name) ON DELETE CASCADE;


-- Name: enemy_damage_controller_procs enemy_damage_controller_procs_controller_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_damage_controller_procs
    ADD CONSTRAINT enemy_damage_controller_procs_controller_unique_name_fkey FOREIGN KEY (controller_unique_name) REFERENCES public.enemy_damage_controllers(unique_name) ON DELETE CASCADE;


-- Name: enemy_droptable_items enemy_droptable_items_pool_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_droptable_items
    ADD CONSTRAINT enemy_droptable_items_pool_id_fkey FOREIGN KEY (pool_id) REFERENCES public.enemy_droptable_pools(pool_id) ON DELETE CASCADE;


-- Name: enemy_droptable_pools enemy_droptable_pools_droptable_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.enemy_droptable_pools
    ADD CONSTRAINT enemy_droptable_pools_droptable_unique_name_fkey FOREIGN KEY (droptable_unique_name) REFERENCES public.enemy_droptables(unique_name) ON DELETE CASCADE;


-- Name: flavour_colours flavour_colours_flavour_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.flavour_colours
    ADD CONSTRAINT flavour_colours_flavour_unique_name_fkey FOREIGN KEY (flavour_unique_name) REFERENCES public.flavour_items(unique_name) ON DELETE CASCADE;


-- Name: focus_upgrade_level_stats focus_upgrade_level_stats_focus_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.focus_upgrade_level_stats
    ADD CONSTRAINT focus_upgrade_level_stats_focus_unique_name_fkey FOREIGN KEY (focus_unique_name) REFERENCES public.focus_upgrades(unique_name) ON DELETE CASCADE;


-- Name: intrinsic_ranks intrinsic_ranks_intrinsic_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.intrinsic_ranks
    ADD CONSTRAINT intrinsic_ranks_intrinsic_unique_name_fkey FOREIGN KEY (intrinsic_unique_name) REFERENCES public.intrinsics(unique_name) ON DELETE CASCADE;


-- Name: key_chain_stage_items key_chain_stage_items_stage_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.key_chain_stage_items
    ADD CONSTRAINT key_chain_stage_items_stage_id_fkey FOREIGN KEY (stage_id) REFERENCES public.key_chain_stages(stage_id) ON DELETE CASCADE;


-- Name: key_chain_stages key_chain_stages_key_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.key_chain_stages
    ADD CONSTRAINT key_chain_stages_key_unique_name_fkey FOREIGN KEY (key_unique_name) REFERENCES public.keys(unique_name) ON DELETE CASCADE;


-- Name: key_rewards key_rewards_key_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.key_rewards
    ADD CONSTRAINT key_rewards_key_unique_name_fkey FOREIGN KEY (key_unique_name) REFERENCES public.keys(unique_name) ON DELETE CASCADE;


-- Name: localizations localizations_lang_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.localizations
    ADD CONSTRAINT localizations_lang_fkey FOREIGN KEY (lang) REFERENCES public.languages(code);


-- Name: mission_reward_items mission_reward_items_tier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.mission_reward_items
    ADD CONSTRAINT mission_reward_items_tier_id_fkey FOREIGN KEY (tier_id) REFERENCES public.mission_reward_tiers(tier_id) ON DELETE CASCADE;


-- Name: mission_reward_tiers mission_reward_tiers_deck_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.mission_reward_tiers
    ADD CONSTRAINT mission_reward_tiers_deck_unique_name_fkey FOREIGN KEY (deck_unique_name) REFERENCES public.mission_reward_decks(unique_name) ON DELETE CASCADE;


-- Name: mod_set_level_stats mod_set_level_stats_mod_set_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.mod_set_level_stats
    ADD CONSTRAINT mod_set_level_stats_mod_set_unique_name_fkey FOREIGN KEY (mod_set_unique_name) REFERENCES public.mod_sets(unique_name) ON DELETE CASCADE;


-- Name: railjack_weapon_behaviour_damage railjack_weapon_behaviour_damage_behaviour_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapon_behaviour_damage
    ADD CONSTRAINT railjack_weapon_behaviour_damage_behaviour_id_fkey FOREIGN KEY (behaviour_id) REFERENCES public.railjack_weapon_behaviours(behaviour_id) ON DELETE CASCADE;


-- Name: railjack_weapon_behaviours railjack_weapon_behaviours_weapon_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapon_behaviours
    ADD CONSTRAINT railjack_weapon_behaviours_weapon_unique_name_fkey FOREIGN KEY (weapon_unique_name) REFERENCES public.railjack_weapons(unique_name) ON DELETE CASCADE;


-- Name: railjack_weapon_compatibility_tags railjack_weapon_compatibility_tags_weapon_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapon_compatibility_tags
    ADD CONSTRAINT railjack_weapon_compatibility_tags_weapon_unique_name_fkey FOREIGN KEY (weapon_unique_name) REFERENCES public.railjack_weapons(unique_name) ON DELETE CASCADE;


-- Name: railjack_weapon_damage_per_shot railjack_weapon_damage_per_shot_weapon_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.railjack_weapon_damage_per_shot
    ADD CONSTRAINT railjack_weapon_damage_per_shot_weapon_unique_name_fkey FOREIGN KEY (weapon_unique_name) REFERENCES public.railjack_weapons(unique_name) ON DELETE CASCADE;


-- Name: recipe_ingredients recipe_ingredients_recipe_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.recipe_ingredients
    ADD CONSTRAINT recipe_ingredients_recipe_unique_name_fkey FOREIGN KEY (recipe_unique_name) REFERENCES public.recipes(unique_name) ON DELETE CASCADE;


-- Name: recipe_secret_ingredients recipe_secret_ingredients_recipe_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.recipe_secret_ingredients
    ADD CONSTRAINT recipe_secret_ingredients_recipe_unique_name_fkey FOREIGN KEY (recipe_unique_name) REFERENCES public.recipes(unique_name) ON DELETE CASCADE;


-- Name: region_dark_sector_data region_dark_sector_data_region_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.region_dark_sector_data
    ADD CONSTRAINT region_dark_sector_data_region_unique_name_fkey FOREIGN KEY (region_unique_name) REFERENCES public.regions(unique_name) ON DELETE CASCADE;


-- Name: region_reward_manifests region_reward_manifests_region_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.region_reward_manifests
    ADD CONSTRAINT region_reward_manifests_region_unique_name_fkey FOREIGN KEY (region_unique_name) REFERENCES public.regions(unique_name) ON DELETE CASCADE;


-- Name: resource_dissection_parts resource_dissection_parts_resource_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.resource_dissection_parts
    ADD CONSTRAINT resource_dissection_parts_resource_unique_name_fkey FOREIGN KEY (resource_unique_name) REFERENCES public.resources(unique_name) ON DELETE CASCADE;


-- Name: resource_sockets resource_sockets_resource_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.resource_sockets
    ADD CONSTRAINT resource_sockets_resource_unique_name_fkey FOREIGN KEY (resource_unique_name) REFERENCES public.resources(unique_name) ON DELETE CASCADE;


-- Name: sentinel_default_upgrades sentinel_default_upgrades_sentinel_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.sentinel_default_upgrades
    ADD CONSTRAINT sentinel_default_upgrades_sentinel_unique_name_fkey FOREIGN KEY (sentinel_unique_name) REFERENCES public.sentinels(unique_name) ON DELETE CASCADE;


-- Name: syndicate_alignments syndicate_alignments_syndicate_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.syndicate_alignments
    ADD CONSTRAINT syndicate_alignments_syndicate_unique_name_fkey FOREIGN KEY (syndicate_unique_name) REFERENCES public.syndicates(unique_name) ON DELETE CASCADE;


-- Name: syndicate_medallions syndicate_medallions_syndicate_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.syndicate_medallions
    ADD CONSTRAINT syndicate_medallions_syndicate_unique_name_fkey FOREIGN KEY (syndicate_unique_name) REFERENCES public.syndicates(unique_name) ON DELETE CASCADE;


-- Name: syndicate_titles syndicate_titles_syndicate_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.syndicate_titles
    ADD CONSTRAINT syndicate_titles_syndicate_unique_name_fkey FOREIGN KEY (syndicate_unique_name) REFERENCES public.syndicates(unique_name) ON DELETE CASCADE;


-- Name: upgrade_available_challenges upgrade_available_challenges_upgrade_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_available_challenges
    ADD CONSTRAINT upgrade_available_challenges_upgrade_unique_name_fkey FOREIGN KEY (upgrade_unique_name) REFERENCES public.upgrades(unique_name) ON DELETE CASCADE;


-- Name: upgrade_challenge_complications upgrade_challenge_complications_challenge_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_challenge_complications
    ADD CONSTRAINT upgrade_challenge_complications_challenge_id_fkey FOREIGN KEY (challenge_id) REFERENCES public.upgrade_available_challenges(challenge_id) ON DELETE CASCADE;


-- Name: upgrade_compatibility_tags upgrade_compatibility_tags_upgrade_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_compatibility_tags
    ADD CONSTRAINT upgrade_compatibility_tags_upgrade_unique_name_fkey FOREIGN KEY (upgrade_unique_name) REFERENCES public.upgrades(unique_name) ON DELETE CASCADE;


-- Name: upgrade_entries upgrade_entries_upgrade_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_entries
    ADD CONSTRAINT upgrade_entries_upgrade_unique_name_fkey FOREIGN KEY (upgrade_unique_name) REFERENCES public.upgrades(unique_name) ON DELETE CASCADE;


-- Name: upgrade_entry_values upgrade_entry_values_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_entry_values
    ADD CONSTRAINT upgrade_entry_values_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES public.upgrade_entries(entry_id) ON DELETE CASCADE;


-- Name: upgrade_mod_set_values upgrade_mod_set_values_upgrade_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.upgrade_mod_set_values
    ADD CONSTRAINT upgrade_mod_set_values_upgrade_unique_name_fkey FOREIGN KEY (upgrade_unique_name) REFERENCES public.upgrades(unique_name) ON DELETE CASCADE;


-- Name: warframe_abilities warframe_abilities_ability_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.warframe_abilities
    ADD CONSTRAINT warframe_abilities_ability_unique_name_fkey FOREIGN KEY (ability_unique_name) REFERENCES public.abilities(unique_name) ON DELETE CASCADE;


-- Name: warframe_abilities warframe_abilities_warframe_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.warframe_abilities
    ADD CONSTRAINT warframe_abilities_warframe_unique_name_fkey FOREIGN KEY (warframe_unique_name) REFERENCES public.warframes(unique_name) ON DELETE CASCADE;


-- Name: warframe_exalted warframe_exalted_warframe_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.warframe_exalted
    ADD CONSTRAINT warframe_exalted_warframe_unique_name_fkey FOREIGN KEY (warframe_unique_name) REFERENCES public.warframes(unique_name) ON DELETE CASCADE;


-- Name: weapon_behaviour_damage weapon_behaviour_damage_behaviour_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapon_behaviour_damage
    ADD CONSTRAINT weapon_behaviour_damage_behaviour_id_fkey FOREIGN KEY (behaviour_id) REFERENCES public.weapon_behaviours(behaviour_id) ON DELETE CASCADE;


-- Name: weapon_behaviours weapon_behaviours_weapon_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapon_behaviours
    ADD CONSTRAINT weapon_behaviours_weapon_unique_name_fkey FOREIGN KEY (weapon_unique_name) REFERENCES public.weapons(unique_name) ON DELETE CASCADE;


-- Name: weapon_compatibility_tags weapon_compatibility_tags_weapon_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapon_compatibility_tags
    ADD CONSTRAINT weapon_compatibility_tags_weapon_unique_name_fkey FOREIGN KEY (weapon_unique_name) REFERENCES public.weapons(unique_name) ON DELETE CASCADE;


-- Name: weapon_damage_per_shot weapon_damage_per_shot_weapon_unique_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.weapon_damage_per_shot
    ADD CONSTRAINT weapon_damage_per_shot_weapon_unique_name_fkey FOREIGN KEY (weapon_unique_name) REFERENCES public.weapons(unique_name) ON DELETE CASCADE;


-- worldstate_enums：WorldState 枚举映射（FC_*/MT_* → loc tag）
-- 数据源: ExportFactions.json / ExportMissionTypes.json
CREATE TABLE public.worldstate_enums (
    category text NOT NULL,
    enum_code text NOT NULL,
    name_loc text,
    PRIMARY KEY (category, enum_code)
);

-- aliases：物品别名（常用简写 → 实体；POST /api/aliases 或 SQL 维护）
CREATE TABLE public.aliases (
    alias text NOT NULL,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    PRIMARY KEY (alias, entity_type, entity_id)
);
CREATE INDEX idx_aliases_alias ON public.aliases (alias);

-- languages 种子数据（15 种官方语言，幂等）
INSERT INTO public.languages (code, native_name, english_name) VALUES
    ('en', 'English',    'English'),
    ('de', 'Deutsch',    'German'),
    ('es', 'Español',    'Spanish'),
    ('fr', 'Français',   'French'),
    ('it', 'Italiano',   'Italian'),
    ('ja', '日本語',      'Japanese'),
    ('ko', '한국어',      'Korean'),
    ('pl', 'Polski',     'Polish'),
    ('pt', 'Português',  'Portuguese'),
    ('ru', 'Русский',    'Russian'),
    ('tr', 'Türkçe',     'Turkish'),
    ('uk', 'Українська', 'Ukrainian'),
    ('zh', '简体中文',     'Simplified Chinese'),
    ('tc', '繁體中文',     'Traditional Chinese'),
    ('th', 'แบบไทย',     'Thai')
ON CONFLICT (code) DO NOTHING;
