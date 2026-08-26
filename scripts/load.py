#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
load.py — 拉取 warframe-public-export-plus 最新数据，生成数据导入 SQL（import.sql）

工作流：
  1) 从 GitHub（calamity-inc/warframe-public-export-plus，走 ghproxy 代理）拉取
     最新 Export*.json / dict.<lang>.json / languages.csv 到 temp/export-data/
  2) 解析并生成根目录 import.sql：
     - 先 TRUNCATE 清空全部 91 张表（每次导入都清理所有数据）
     - 再用 COPY / INSERT..SELECT 全量写入（含 localizations 指定语言字典）
  3) 把 import.sql 上传到目标服务器，执行:
       psql -U <user> -d <db> -f import.sql
     （服务器只需 psql，无需 Python/网络）

用法:
  python3 load.py --fetch --langs zh            # 拉最新数据并生成 import.sql（推荐）
  python3 load.py --langs zh                    # 用本地 temp/export-data/ 已有文件生成
  python3 load.py --fetch --langs zh,en --keep-data --out /path/import.sql

选项:
  --langs        要导入的字典语言，逗号分隔（默认 zh）
  --fetch        先从 GitHub 拉取缺失的数据文件
  --force-fetch  强制重新下载全部数据文件
  --mirror       GitHub 代理前缀（默认 ghproxy，置空走直连）
  --keep-data    保留下载的临时数据文件（默认导入后删除）
  --out          输出 SQL 路径（默认 ./import.sql）
  --no-clean     不在 SQL 中清空数据（默认 TRUNCATE 全部表再插入）
"""
import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录
DEFAULT_DATA_DIR = os.path.join(HERE, "temp", "export-data")
DEFAULT_OUT = os.path.join(HERE, "sql", "import.sql")

LANG_CODES = ["en", "de", "es", "fr", "it", "ja", "ko", "pl", "pt", "ru", "tc", "th", "tr", "uk", "zh"]
GITHUB_BASE = "https://raw.githubusercontent.com/calamity-inc/warframe-public-export-plus/master/"


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def _g(d, *keys):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def _s(v):
    return None if v is None else str(v)


def _n(v):
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def load_json(data_dir, name):
    with open(os.path.join(data_dir, name), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 从 GitHub 拉取数据
# ---------------------------------------------------------------------------
def fetch_data(data_dir, langs, mirror, force, timeout=90):
    import urllib.request

    url_prefix = (mirror or "") + GITHUB_BASE
    files = [fname for fname, _ in LOADERS] \
        + ["ExportFactions.json", "ExportMissionTypes.json"] \
        + [f"dict.{l}.json" for l in langs] \
        + ["supplementals/languages.csv"]
    os.makedirs(data_dir, exist_ok=True)
    fetched, skipped = [], []
    for f in files:
        local = os.path.join(data_dir, os.path.basename(f))
        if os.path.exists(local) and not force:
            skipped.append(f)
            continue
        url = url_prefix + f
        ok = False
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=timeout) as r:
                    content = r.read()
                head = content[:300].lstrip().lower()
                if head.startswith(b"<!doctype") or head.startswith(b"404"):
                    raise ValueError("非 JSON 内容（404/HTML）")
                with open(local, "wb") as fp:
                    fp.write(content)
                ok = True
                break
            except Exception as e:
                if attempt == 2:
                    # 上游可能已移除该文件（如 ExportMisc.json），跳过并警告
                    print(f"[fetch] 跳过（下载失败）{f}: {e}")
                else:
                    print(f"[fetch] 重试 {attempt + 1}/3 {f}: {e}")
        if ok:
            fetched.append(f)
    return fetched, skipped


# ---------------------------------------------------------------------------
# SQL 生成器
# ---------------------------------------------------------------------------
def _copy_escape(v):
    if v is None:
        return "\\N"
    if isinstance(v, (list, tuple)):
        # PostgreSQL 数组格式：{val1,val2,...}
        inner = ",".join(_pg_array_elem(x) for x in v)
        return "{" + inner + "}"
    s = str(v)
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def _pg_array_elem(v):
    """单个数组元素（COPY 格式）。"""
    if v is None:
        return "NULL"
    s = str(v)
    # 含逗号/引号/反斜杠/大括号的元素需要加引号
    if any(c in s for c in ',\\"{}'):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return s


def _sql_literal(v):
    """VALUES 字面量（INSERT..SELECT 用）。"""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _values_clause(rows):
    return ",\n    ".join("(" + ", ".join(_sql_literal(v) for v in r) + ")" for r in rows)


class SQLWriter:
    """收集数据并写出 COPY / INSERT..SELECT 语句。"""

    def __init__(self, out):
        self.out = out
        self.counts = {}

    def copy(self, table, columns, rows):
        """COPY FROM stdin 块（用于无自增外键依赖的表）。"""
        if not rows:
            return
        self.out.write(f"COPY public.{table} ({columns}) FROM stdin;\n")
        for r in rows:
            self.out.write("\t".join(_copy_escape(v) for v in r) + "\n")
        self.out.write("\\.\n")
        self.counts[table] = self.counts.get(table, 0) + len(rows)

    def insert_select(self, sql_tail, rows):
        """INSERT ... SELECT ... FROM (VALUES ...) 模式（用于依赖自增 id 的子表）。"""
        if not rows:
            return
        self.out.write(sql_tail.format(values=_values_clause(rows)) + "\n")

    def upsert(self, table, columns, rows, conflict_cols, update_col=None):
        """INSERT ... ON CONFLICT DO UPDATE/NOTHING（用于 wiki 枚举等手动数据）。"""
        if not rows:
            return
        cols = columns
        conflict = ", ".join(conflict_cols)
        if update_col:
            on_conflict = f"ON CONFLICT ({conflict}) DO UPDATE SET {update_col} = EXCLUDED.{update_col}"
        else:
            on_conflict = f"ON CONFLICT ({conflict}) DO NOTHING"
        for r in rows:
            vals = ", ".join(_upsert_val(v) for v in r)
            self.out.write(f"INSERT INTO public.{table} ({cols}) VALUES ({vals}) {on_conflict};\n")
        self.counts[table] = self.counts.get(table, 0) + len(rows)


def _upsert_val(v):
    """INSERT VALUES 转义。"""
    if v is None:
        return "NULL"
    s = str(v).replace("'", "''")
    return f"'{s}'"


# ---------------------------------------------------------------------------
# 各 Export 文件加载器（收集模式：data -> SQLWriter）
# ---------------------------------------------------------------------------
def load_abilities(data, w):
    for un, a in data.items():
        _add_ability((un, a.get("name"), a.get("description"), a.get("icon"),
                      a.get("energyRequiredToActivate"), _n(a.get("energyConsumptionOverTime"))))


def load_achievements(data, w):
    key_to_un = {k: (a.get("uniqueName") or k) for k, a in data.items()}
    loaded = set(key_to_un.values())
    rows, child_rows = [], []
    for _k, a in data.items():
        un = a.get("uniqueName") or _k
        rows.append((un, a.get("name"), a.get("description"), a.get("icon"),
                     a.get("requiredCount"), a.get("progressIndicatorFreq"), a.get("hidden")))
        seen = set()
        for c in a.get("children") or []:
            target = key_to_un.get(c, c)
            if target in loaded and (un, target) not in seen:
                child_rows.append((un, target))
                seen.add((un, target))
    w.copy("achievements", "unique_name, name_loc, description_loc, icon, "
                           "required_count, progress_indicator_freq, hidden", rows)
    w.copy("achievement_children", "achievement_unique_name, child_unique_name", child_rows)


def load_arcanes(data, w):
    w.copy("arcanes", "unique_name, name_loc, icon, codex_secret, exclude_from_codex, "
                      "rarity, fusion_limit, distill_point_value, is_frivolous",
           [(un, a.get("name"), a.get("icon"), a.get("codexSecret"), a.get("excludeFromCodex"),
             a.get("rarity"), a.get("fusionLimit"), a.get("distillPointValue"), a.get("isFrivolous"))
            for un, a in data.items()])


def load_avionics(data, w):
    w.copy("avionics", "unique_name, name_loc, polarity, rarity, codex_secret, "
                       "base_drain, fusion_limit, exclude_from_codex",
           [(un, a.get("name"), a.get("polarity"), a.get("rarity"), a.get("codexSecret"),
             a.get("baseDrain"), a.get("fusionLimit"), a.get("excludeFromCodex"))
            for un, a in data.items()])


def load_booster_packs(data, w):
    rows, comp_rows, weight_rows = [], [], []
    for un, b in data.items():
        rows.append((un, b.get("name"), b.get("description"), b.get("icon")))
        for i, c in enumerate(b.get("components") or []):
            comp_rows.append((un, i, c.get("Item"), c.get("Rarity")))
        for ri, weights in enumerate(b.get("rarityWeightsPerRoll") or []):
            for rarity in ("COMMON", "UNCOMMON", "RARE", "LEGENDARY"):
                if rarity in weights:
                    weight_rows.append((un, ri, rarity, _n(weights[rarity])))
    w.copy("booster_packs", "unique_name, name_loc, description_loc, icon", rows)
    w.copy("booster_pack_components", "pack_unique_name, slot, item, rarity", comp_rows)
    w.copy("booster_pack_rarity_weights", "pack_unique_name, roll_index, rarity, weight", weight_rows)


def load_bundles(data, w):
    rows, comp_rows = [], []
    for un, b in data.items():
        rows.append((un, b.get("name"), b.get("description"), b.get("icon"),
                     b.get("excludeFromCodex"), b.get("premiumPrice")))
        for i, c in enumerate(b.get("components") or []):
            comp_rows.append((un, i, c.get("typeName"), c.get("purchaseQuantity"),
                              c.get("durability"), c.get("giveMaxRank")))
    w.copy("bundles", "unique_name, name_loc, description_loc, icon, "
                      "exclude_from_codex, premium_price", rows)
    w.copy("bundle_components", "bundle_unique_name, slot, type_name, "
                                "purchase_quantity, durability, give_max_rank", comp_rows)


def load_customs(data, w):
    w.copy("customs", "unique_name, name_loc, codex_secret, description_loc, "
                      "icon, exclude_from_codex",
           [(un, c.get("name"), c.get("codexSecret"), c.get("description"),
             c.get("icon"), c.get("excludeFromCodex"))
            for un, c in data.items()])


def load_drones(data, w):
    rows, cap_rows = [], []
    for un, d in data.items():
        rows.append((un, d.get("name"), d.get("description"), d.get("icon"),
                     d.get("binCount"), d.get("binCapacity"), _n(d.get("fillRate")),
                     _n(d.get("durability")), _n(d.get("repairRate")), d.get("codexSecret")))
        for i, v in enumerate(d.get("capacityMultiplier") or []):
            cap_rows.append((un, i, _n(v)))
    w.copy("drones", "unique_name, name_loc, description_loc, icon, bin_count, bin_capacity, "
                     "fill_rate, durability, repair_rate, codex_secret", rows)
    w.copy("drone_capacity_multipliers", "drone_unique_name, slot, value", cap_rows)


def load_flavour(data, w):
    rows, colour_rows = [], []
    for un, f_ in data.items():
        rows.append((un, f_.get("name"), f_.get("description"), f_.get("icon"),
                     f_.get("base"), f_.get("codexSecret"), f_.get("excludeFromCodex")))
        for kind in ("hexColours", "legacyColours"):
            for i, c in enumerate(f_.get(kind) or []):
                colour_rows.append((un, "hex" if kind == "hexColours" else "legacy", i, c.get("value")))
    w.copy("flavour_items", "unique_name, name_loc, description_loc, icon, base, "
                            "codex_secret, exclude_from_codex", rows)
    w.copy("flavour_colours", "flavour_unique_name, kind, slot, value", colour_rows)


def load_focus_upgrades(data, w):
    rows, stat_rows = [], []
    for un, f_ in data.items():
        rows.append((un, f_.get("name"), f_.get("icon"), f_.get("polarity"), f_.get("rarity"),
                     f_.get("codexSecret"), f_.get("baseDrain"), f_.get("fusionLimit"),
                     f_.get("excludeFromCodex"), f_.get("description"), f_.get("baseFocusPointCost")))
        for level, entry in enumerate(f_.get("levelStats") or []):
            for k, v in entry.items():
                stat_rows.append((un, level, k, _s(v)))
    w.copy("focus_upgrades", "unique_name, name_loc, icon, polarity, rarity, codex_secret, "
                             "base_drain, fusion_limit, exclude_from_codex, description_loc, "
                             "base_focus_point_cost", rows)
    w.copy("focus_upgrade_level_stats", "focus_unique_name, level, stat_key, stat_value", stat_rows)


def load_fusion_bundles(data, w):
    w.copy("fusion_bundles", "unique_name, name_loc, description_loc, icon, "
                             "codex_secret, fusion_points",
           [(un, f_.get("name"), f_.get("description"), f_.get("icon"),
             f_.get("codexSecret"), f_.get("fusionPoints"))
            for un, f_ in data.items()])


def load_gear(data, w):
    w.copy("gear", "unique_name, name_loc, description_loc, icon, codex_secret, "
                   "parent_name, purchase_quantity",
           [(un, g.get("name"), g.get("description"), g.get("icon"), g.get("codexSecret"),
             g.get("parentName"), g.get("purchaseQuantity"))
            for un, g in data.items()])


def load_images(data, w):
    w.copy("images", "unique_name, content_hash",
           [(un, i.get("contentHash")) for un, i in data.items()])


def load_intrinsics(data, w):
    rows, rank_rows = [], []
    for un, i in data.items():
        rows.append((un, i.get("name"), i.get("description"), i.get("icon")))
        for ri, r in enumerate(i.get("ranks") or []):
            rank_rows.append((un, ri, r.get("name"), r.get("description")))
    w.copy("intrinsics", "unique_name, name_loc, description_loc, icon", rows)
    w.copy("intrinsic_ranks", "intrinsic_unique_name, rank_index, name_loc, description_loc", rank_rows)


def load_keys(data, w):
    rows, stage_rows, stage_item_rows, reward_rows = [], [], [], []
    for un, k in data.items():
        rows.append((un, k.get("name"), k.get("description"), k.get("icon"),
                     k.get("parentName"), k.get("codexSecret"), k.get("excludeFromCodex")))
        for si, s in enumerate(k.get("chainStages") or []):
            msg = s.get("messageToSendWhenTriggered") or {}
            stage_rows.append((un, si, s.get("key"),
                               msg.get("sender"), msg.get("title"), msg.get("body")))
            for ii, it in enumerate(s.get("itemsToGiveWhenTriggered") or []):
                stage_item_rows.append((un, si, ii, it))
        for ri, r in enumerate(k.get("rewards") or []):
            reward_rows.append((un, ri, r.get("rewardType"), r.get("itemType"), r.get("amount")))
    w.copy("keys", "unique_name, name_loc, description_loc, icon, parent_name, "
                   "codex_secret, exclude_from_codex", rows)
    w.copy("key_chain_stages", "key_unique_name, stage_index, key, message_sender_loc, "
                               "message_title_loc, message_body_loc", stage_rows)
    w.insert_select("""
        INSERT INTO public.key_chain_stage_items (stage_id, slot, item_type)
        SELECT ks.stage_id, v.slot, v.item_type
        FROM (VALUES {values}) AS v(key_unique_name, stage_index, slot, item_type)
        JOIN public.key_chain_stages ks
          ON ks.key_unique_name = v.key_unique_name AND ks.stage_index = v.stage_index;""",
        stage_item_rows)
    w.copy("key_rewards", "key_unique_name, slot, reward_type, item_type, amount", reward_rows)


def load_misc(data, w):
    w.copy("misc", "id, npc_kill_reward_multiplier", [(1, _n(data.get("npcKillRewardMultiplier")))])
    w.copy("misc_unique_level_caps", "level_cap_key, value",
           [(k, v) for k, v in (data.get("uniqueLevelCaps") or {}).items()])
    w.copy("misc_booster_durations", "rarity, value",
           [(k, _n(v)) for k, v in (data.get("boosterDurations") or {}).items()])


def load_mod_sets(data, w):
    rows, stat_rows = [], []
    for un, m in data.items():
        rows.append((un, m.get("description"), m.get("icon"), m.get("numUpgradesInSet"), m.get("buffSet")))
        for level, entry in enumerate(m.get("levelStats") or []):
            for k, v in entry.items():
                stat_rows.append((un, level, k, _s(v)))
    w.copy("mod_sets", "unique_name, description_loc, icon, num_upgrades_in_set, buff_set", rows)
    w.copy("mod_set_level_stats", "mod_set_unique_name, level, stat_key, stat_value", stat_rows)


def load_nightwave(data, w):
    w.copy("nightwave", "id, affiliation_tag", [(1, data.get("affiliationTag"))])
    challenge_rows = []
    for ck, c in (data.get("challenges") or {}).items():
        challenge_rows.append((ck, c.get("name"), c.get("description"), c.get("standing"),
                               c.get("required"), c.get("icon"), c.get("tip"), c.get("tipIcon")))
    w.copy("nightwave_challenges", "challenge_key, name_loc, description_loc, standing, "
                                   "required, icon, tip_loc, tip_icon", challenge_rows)
    # rewards 列表可能含重复 uniqueName，去重后再写入
    seen = set()
    reward_rows = []
    for r in data.get("rewards") or []:
        un = r.get("uniqueName")
        if un in seen:
            continue
        seen.add(un)
        reward_rows.append((un, r.get("name"), r.get("description"),
                            r.get("icon"), r.get("itemCount")))
    w.copy("nightwave_rewards", "unique_name, name_loc, description_loc, icon, item_count",
           reward_rows)


def _collect_behaviours(data):
    bh_rows, dmg_rows = [], []
    for un, b in data.items():
        for bi, bh in enumerate(b.get("behaviours") or []):
            bh_rows.append((un, bi, bh.get("stateName")))
            _collect_damage(dmg_rows, un, bi, bh)
    return bh_rows, dmg_rows


def _collect_damage(dmg_rows, un, bi, bh):
    def walk(path, table):
        if isinstance(table, dict):
            for dt, v in table.items():
                dmg_rows.append((un, bi, path, dt, _n(v)))
    walk("impact", bh.get("impact"))
    proj = bh.get("projectile") or {}
    cproj = bh.get("chargedProjectile") or {}
    walk("projectile.attack", proj.get("attack"))
    walk("projectile.explosiveAttack", proj.get("explosiveAttack"))
    walk("projectile.embedDeathAttack", proj.get("embedDeathAttack"))
    walk("chargedProjectile.attack", cproj.get("attack"))
    walk("chargedProjectile.explosiveAttack", cproj.get("explosiveAttack"))
    walk("chargedProjectile.embedDeathAttack", cproj.get("embedDeathAttack"))


def _emit_behaviours(w, bh_table, dmg_table, data, fk_col="weapon_unique_name"):
    bh_rows, dmg_rows = _collect_behaviours(data)
    w.copy(bh_table, f"{fk_col}, slot, state_name_loc", bh_rows)
    w.insert_select(f"""
        INSERT INTO public.{dmg_table} (behaviour_id, path, damage_type, value)
        SELECT b.behaviour_id, v.path, v.damage_type, v.value::double precision
        FROM (VALUES {{values}}) AS v({fk_col}, slot, path, damage_type, value)
        JOIN public.{bh_table} b
          ON b.{fk_col} = v.{fk_col} AND b.slot = v.slot;""",
        dmg_rows)


def load_railjack_weapons(data, w):
    rows, dps_rows, tag_rows = [], [], []
    for un, wd in data.items():
        rows.append((un, wd.get("name"), wd.get("parentName"), wd.get("icon"), wd.get("codexSecret"),
                     _n(wd.get("totalDamage")), wd.get("description"), _n(wd.get("criticalChance")),
                     _n(wd.get("criticalMultiplier")), _n(wd.get("procChance")), _n(wd.get("fireRate")),
                     wd.get("masteryReq"), wd.get("productCategory"), wd.get("excludeFromCodex"),
                     wd.get("slot"), _n(wd.get("accuracy")), _n(wd.get("omegaAttenuation")),
                     wd.get("noise"), wd.get("trigger"), wd.get("magazineSize"),
                     _n(wd.get("reloadTime")), _n(wd.get("multishot"))))
        for i, v in enumerate(wd.get("damagePerShot") or []):
            dps_rows.append((un, i, _n(v)))
        for t in wd.get("compatibilityTags") or []:
            tag_rows.append((un, t))
    w.copy("railjack_weapons", "unique_name, name_loc, parent_name, icon, codex_secret, "
                "total_damage, description_loc, critical_chance, critical_multiplier, proc_chance, "
                "fire_rate, mastery_req, product_category, exclude_from_codex, slot, accuracy, "
                "omega_attenuation, noise, trigger, magazine_size, reload_time, multishot", rows)
    w.copy("railjack_weapon_damage_per_shot", "weapon_unique_name, slot, value", dps_rows)
    w.copy("railjack_weapon_compatibility_tags", "weapon_unique_name, tag", tag_rows)
    _emit_behaviours(w, "railjack_weapon_behaviours", "railjack_weapon_behaviour_damage", data)


def load_recipes(data, w):
    rows, ing_rows, sec_rows = [], [], []
    for un, r in data.items():
        rows.append((un, r.get("resultType"), r.get("buildPrice"), r.get("buildTime"),
                     r.get("skipBuildTimePrice"), r.get("consumeOnUse"), r.get("num"),
                     r.get("codexSecret"), r.get("excludeFromCodex"), r.get("alwaysAvailable"),
                     r.get("hidden"), r.get("primeSellingPrice"), r.get("secretIngredientAction")))
        for i, ing in enumerate(r.get("ingredients") or []):
            ing_rows.append((un, i, ing.get("ItemType"), ing.get("ItemCount")))
        for i, ing in enumerate(r.get("secretIngredients") or []):
            sec_rows.append((un, i, ing.get("ItemType"), ing.get("ItemCount")))
    w.copy("recipes", "unique_name, result_type, build_price, build_time, "
                "skip_build_time_price, consume_on_use, num, codex_secret, exclude_from_codex, "
                "always_available, hidden, prime_selling_price, secret_ingredient_action", rows)
    w.copy("recipe_ingredients", "recipe_unique_name, slot, item_type, item_count", ing_rows)
    w.copy("recipe_secret_ingredients", "recipe_unique_name, slot, item_type, item_count", sec_rows)


# 新版 ExportRegions 的 faction 为 FC_* 枚举，用 ExportFactions 映射补全 loc tag
_FACTION_TAGS = {}
_MISSION_TAGS = {}

# 全局能力收集（ExportAbilities + 战甲内嵌技能，按 unique_name 去重）
_ABILITY_ROWS = []
_ABILITY_SEEN = set()
_WARFRAME_ABILITY_ROWS = []


def _add_ability(row):
    if row and row[0] and row[0] not in _ABILITY_SEEN:
        _ABILITY_SEEN.add(row[0])
        _ABILITY_ROWS.append(row)


def load_regions(data, w):
    rows, mani_rows, ds_rows = [], [], []
    for un, r in data.items():
        ds = r.get("darkSectorData")
        faction_name_loc = _FACTION_TAGS.get(r.get("faction")) or r.get("factionName")
        rows.append((un, r.get("name"), r.get("systemIndex"), r.get("systemName"), r.get("nodeType"),
                     r.get("masteryReq"), r.get("missionIndex"), r.get("missionName"),
                     r.get("factionIndex"), faction_name_loc, r.get("secondaryFactionIndex"),
                     r.get("secondaryFactionName"), r.get("minEnemyLevel"), r.get("maxEnemyLevel"),
                     r.get("masteryExp"), r.get("cacheRewardManifest"), r.get("questReq"), r.get("hidden")))
        for i, m in enumerate(r.get("rewardManifests") or []):
            mani_rows.append((un, i, m))
        if ds:
            ds_rows.append((un, _n(ds.get("resourceBonus")), _n(ds.get("xpBonus")),
                            ds.get("weaponXpBonusFor"), _n(ds.get("weaponXpBonusVal"))))
    w.copy("regions", "unique_name, name_loc, system_index, system_name_loc, node_type, "
                "mastery_req, mission_index, mission_name_loc, faction_index, faction_name_loc, "
                "secondary_faction_index, secondary_faction_name_loc, min_enemy_level, "
                "max_enemy_level, mastery_exp, cache_reward_manifest, quest_req, hidden", rows)
    w.copy("region_reward_manifests", "region_unique_name, slot, manifest", mani_rows)
    w.copy("region_dark_sector_data", "region_unique_name, resource_bonus, xp_bonus, "
                                      "weapon_xp_bonus_for, weapon_xp_bonus_val", ds_rows)


def load_relics(data, w):
    w.copy("relics", "unique_name, category, era, icon, codex_secret, description_loc, "
                     "quality, reward_manifest",
           [(un, r.get("category"), r.get("era"), r.get("icon"), r.get("codexSecret"),
             r.get("description"), r.get("quality"), r.get("rewardManifest"))
            for un, r in data.items()])


def load_resources(data, w):
    rows, sock_rows, part_rows = [], [], []
    for un, r in data.items():
        rows.append((un, r.get("name"), r.get("description"), r.get("icon"), r.get("codexSecret"),
                     r.get("parentName"), r.get("productCategory"), r.get("excludeFromCodex"),
                     r.get("showInInventory"), r.get("longDescription"), r.get("primeSellingPrice")))
        for i, s in enumerate(r.get("sockets") or []):
            sock_rows.append((un, i, s))
        for i, p in enumerate(r.get("dissectionParts") or []):
            part_rows.append((un, i, p.get("ItemType"), p.get("ItemCount")))
    w.copy("resources", "unique_name, name_loc, description_loc, icon, codex_secret, "
                "parent_name, product_category, exclude_from_codex, show_in_inventory, "
                "long_description, prime_selling_price", rows)
    w.copy("resource_sockets", "resource_unique_name, slot, socket", sock_rows)
    w.copy("resource_dissection_parts", "resource_unique_name, slot, item_type, item_count", part_rows)


def load_rewards(data, w):
    w.copy("mission_reward_decks", "unique_name", [(un,) for un in data])
    tier_rows, item_rows = [], []
    for un, tiers in data.items():
        for ti, tier in enumerate(tiers):
            tier_rows.append((un, ti))
            for ii, item in enumerate(tier):
                item_rows.append((un, ti, ii, item.get("type"), item.get("itemCount"),
                                  _n(item.get("probability")), item.get("rarity")))
    w.copy("mission_reward_tiers", "deck_unique_name, tier_index", tier_rows)
    w.insert_select("""
        INSERT INTO public.mission_reward_items (tier_id, slot, type, item_count, probability, rarity)
        SELECT t.tier_id, v.slot, v.type, v.item_count, v.probability::double precision, v.rarity
        FROM (VALUES {values}) AS v(deck_unique_name, tier_index, slot, type, item_count, probability, rarity)
        JOIN public.mission_reward_tiers t
          ON t.deck_unique_name = v.deck_unique_name AND t.tier_index = v.tier_index;""",
        item_rows)


def load_sentinels(data, w):
    rows, upg_rows = [], []
    for un, s in data.items():
        rows.append((un, s.get("name"), s.get("icon"), s.get("health"), s.get("shield"),
                     s.get("armor"), s.get("stamina"), s.get("power"), s.get("codexSecret"),
                     s.get("excludeFromCodex"), s.get("description"), s.get("productCategory"),
                     s.get("defaultWeapon")))
        for i, u in enumerate(s.get("defaultUpgrades") or []):
            upg_rows.append((un, i, u.get("ItemType"), u.get("Slot")))
    w.copy("sentinels", "unique_name, name_loc, icon, health, shield, armor, stamina, "
                "power, codex_secret, exclude_from_codex, description_loc, product_category, "
                "default_weapon", rows)
    w.copy("sentinel_default_upgrades", "sentinel_unique_name, slot, item_type, slot_num", upg_rows)


def load_syndicates(data, w):
    rows, align_rows, title_rows, medal_rows = [], [], [], []
    for un, s in data.items():
        un = s.get("uniqueName") or un
        rows.append((un, s.get("name"), s.get("icon"),
                     _g(s, "colour", "value"), _g(s, "backgroundColour", "value"),
                     s.get("description"), s.get("medallionsCappedByDailyLimit")))
        for name, val in (s.get("alignments") or {}).items():
            align_rows.append((un, name, _n(val)))
        for t in s.get("titles") or []:
            title_rows.append((un, t.get("level"), t.get("name"), t.get("icon"), t.get("description")))
        for m in s.get("medallions") or []:
            medal_rows.append((un, m.get("itemType"), m.get("standing")))
    w.copy("syndicates", "unique_name, name_loc, icon, colour, background_colour, "
                         "description_loc, medallions_capped_by_daily_limit", rows)
    w.copy("syndicate_alignments", "syndicate_unique_name, aligned_syndicate, value", align_rows)
    w.copy("syndicate_titles", "syndicate_unique_name, level, name_loc, icon, description_loc", title_rows)
    w.copy("syndicate_medallions", "syndicate_unique_name, item_type, standing", medal_rows)


def load_text_icons(data, w):
    cols = ("dit_ps4", "dit_xbone", "dit_steam", "dit_agnostic", "dit_switch",
            "dit_pc", "dit_ps5", "dit_ios", "dit_auto")
    src = ("DIT_PS4", "DIT_XBONE", "DIT_STEAM", "DIT_AGNOSTIC", "DIT_SWITCH",
           "DIT_PC", "DIT_PS5", "DIT_IOS", "DIT_AUTO")
    w.copy("text_icons", "unique_name, " + ", ".join(cols),
           [(un,) + tuple(t.get(s) for s in src) for un, t in data.items()])


def load_upgrades(data, w):
    rows, tag_rows, msval_rows, entry_rows, entryval_rows, chall_rows, comp_rows = [], [], [], [], [], [], []
    for un, u in data.items():
        rows.append((un, u.get("name"), u.get("icon"), u.get("polarity"), u.get("rarity"),
                     u.get("codexSecret"), u.get("baseDrain"), u.get("fusionLimit"), u.get("compat"),
                     u.get("compatName"), u.get("type"), u.get("description"), u.get("isUtility"),
                     u.get("modSet"), u.get("subtype"), u.get("excludeFromCodex"),
                     u.get("isStarter"), u.get("isFrivolous")))
        for t in u.get("compatibilityTags") or []:
            tag_rows.append((un, t))
        for i, v in enumerate(u.get("modSetValues") or []):
            msval_rows.append((un, i, _n(v)))
        for ei, e in enumerate(u.get("upgradeEntries") or []):
            entry_rows.append((un, ei, e.get("tag"), e.get("prefixTag"), e.get("suffixTag")))
            for vi, uv in enumerate(e.get("upgradeValues") or []):
                entryval_rows.append((un, ei, vi, _n(uv.get("value")), uv.get("locTag"),
                                      uv.get("reverseValueSymbol")))
        for ci, c in enumerate(u.get("availableChallenges") or []):
            rng = c.get("countRange") or [None, None]
            chall_rows.append((un, ci, c.get("fullName"), c.get("description"), rng[0], rng[1]))
            for xi, x in enumerate(c.get("complications") or []):
                comp_rows.append((un, ci, xi, x.get("fullName"), x.get("description"), x.get("overrideTag")))
    w.copy("upgrades", "unique_name, name_loc, icon, polarity, rarity, codex_secret, "
                "base_drain, fusion_limit, compat, compat_name, type, description_loc, is_utility, "
                "mod_set, subtype, exclude_from_codex, is_starter, is_frivolous", rows)
    w.copy("upgrade_compatibility_tags", "upgrade_unique_name, tag", tag_rows)
    w.copy("upgrade_mod_set_values", "upgrade_unique_name, slot, value", msval_rows)
    w.copy("upgrade_entries", "upgrade_unique_name, slot, tag, prefix_tag_loc, suffix_tag_loc", entry_rows)
    w.insert_select("""
        INSERT INTO public.upgrade_entry_values (entry_id, slot, value, loc_tag, reverse_value_symbol)
        SELECT e.entry_id, v.slot, v.value::double precision, v.loc_tag, v.reverse_value_symbol
        FROM (VALUES {values}) AS v(upgrade_unique_name, entry_slot, slot, value, loc_tag, reverse_value_symbol)
        JOIN public.upgrade_entries e
          ON e.upgrade_unique_name = v.upgrade_unique_name AND e.slot = v.entry_slot;""",
        entryval_rows)
    w.copy("upgrade_available_challenges", "upgrade_unique_name, slot, full_name, description_loc, "
                                           "count_range_min, count_range_max", chall_rows)
    w.insert_select("""
        INSERT INTO public.upgrade_challenge_complications (challenge_id, slot, full_name,
                                                             description_loc, override_tag_loc)
        SELECT c.challenge_id, v.slot, v.full_name, v.description_loc, v.override_tag_loc
        FROM (VALUES {values}) AS v(upgrade_unique_name, challenge_slot, slot, full_name, description_loc, override_tag_loc)
        JOIN public.upgrade_available_challenges c
          ON c.upgrade_unique_name = v.upgrade_unique_name AND c.slot = v.challenge_slot;""",
        comp_rows)


def load_virtuals(data, w):
    w.copy("virtuals", "unique_name, parent_name, name_loc",
           [(un, v.get("parentName"), v.get("name")) for un, v in data.items()])


def load_warframes(data, w):
    rows, abil_rows, link_rows, exalt_rows = [], [], [], []
    for un, wf in data.items():
        rows.append((un, wf.get("name"), wf.get("parentName"), wf.get("description"), wf.get("icon"),
                     wf.get("health"), wf.get("shield"), wf.get("armor"), wf.get("stamina"),
                     wf.get("power"), wf.get("codexSecret"), wf.get("masteryReq"),
                     _n(wf.get("sprintSpeed")), wf.get("passiveDescription"),
                     wf.get("productCategory"), wf.get("longDescription")))
        for slot, a in enumerate(wf.get("abilities") or []):
            abil_rows.append((a.get("uniqueName"), a.get("name"), a.get("description"),
                              a.get("icon"), a.get("energyRequiredToActivate"),
                              _n(a.get("energyConsumptionOverTime"))))
            _WARFRAME_ABILITY_ROWS.append((un, a.get("uniqueName"), slot))
        for i, e in enumerate(wf.get("exalted") or []):
            exalt_rows.append((un, i, e))
    w.copy("warframes", "unique_name, name_loc, parent_name, description_loc, icon, "
                "health, shield, armor, stamina, power, codex_secret, mastery_req, sprint_speed, "
                "passive_description_loc, product_category, long_description_loc", rows)
    for row in abil_rows:
        _add_ability(row)
    w.copy("warframe_exalted", "warframe_unique_name, slot, exalted_unique_name", exalt_rows)


def load_weapons(data, w):
    rows, dps_rows, tag_rows = [], [], []
    for un, wd in data.items():
        rows.append((un, wd.get("name"), wd.get("parentName"), wd.get("icon"), wd.get("codexSecret"),
                     _n(wd.get("totalDamage")), wd.get("description"), _n(wd.get("criticalChance")),
                     _n(wd.get("criticalMultiplier")), _n(wd.get("procChance")), _n(wd.get("fireRate")),
                     wd.get("masteryReq"), wd.get("productCategory"), wd.get("holsterCategory"),
                     wd.get("slot"), _n(wd.get("accuracy")), _n(wd.get("omegaAttenuation")),
                     wd.get("noise"), wd.get("trigger"), wd.get("magazineSize"), _n(wd.get("reloadTime")),
                     _n(wd.get("multishot")), wd.get("blockingAngle"), wd.get("comboDuration"),
                     _n(wd.get("followThrough")), _n(wd.get("range")), wd.get("slamAttack"),
                     wd.get("slamRadialDamage"), wd.get("slamRadius"), wd.get("slideAttack"),
                     wd.get("heavyAttackDamage"), wd.get("heavySlamAttack"),
                     wd.get("heavySlamRadialDamage"), wd.get("heavySlamRadius"), _n(wd.get("windUp")),
                     wd.get("maxLevelCap"), wd.get("sentinel"), wd.get("excludeFromCodex"),
                     _n(wd.get("primeOmegaAttenuation"))))
        for i, v in enumerate(wd.get("damagePerShot") or []):
            dps_rows.append((un, i, _n(v)))
        for t in wd.get("compatibilityTags") or []:
            tag_rows.append((un, t))
    w.copy("weapons", "unique_name, name_loc, parent_name, icon, codex_secret, "
                "total_damage, description_loc, critical_chance, critical_multiplier, proc_chance, "
                "fire_rate, mastery_req, product_category, holster_category, slot, accuracy, "
                "omega_attenuation, noise, trigger, magazine_size, reload_time, multishot, "
                "blocking_angle, combo_duration, follow_through, range, slam_attack, "
                "slam_radial_damage, slam_radius, slide_attack, heavy_attack_damage, "
                "heavy_slam_attack, heavy_slam_radial_damage, heavy_slam_radius, wind_up, "
                "max_level_cap, sentinel, exclude_from_codex, prime_omega_attenuation", rows)
    w.copy("weapon_damage_per_shot", "weapon_unique_name, slot, value", dps_rows)
    w.copy("weapon_compatibility_tags", "weapon_unique_name, tag", tag_rows)
    _emit_behaviours(w, "weapon_behaviours", "weapon_behaviour_damage", data)


def load_enemies(data, w):
    agents, avatars, controllers, droptables, hit_proxies, ai_weapons = (
        data["agents"], data["avatars"], data["damageControllers"],
        data["droptables"], data["hitProxies"], data["aiWeapons"])

    agent_rows, agent_item_rows = [], []
    for un, a in agents.items():
        at = a.get("avatarTypes") or {}
        agent_rows.append((un, a.get("baseLevel"), at.get("STANDARD"), at.get("EXIMUS"), at.get("RARE")))
        for i, it in enumerate(a.get("items") or []):
            agent_item_rows.append((un, i, it.get("type")))
    w.copy("enemy_agents", "unique_name, base_level, avatar_standard, avatar_eximus, avatar_rare", agent_rows)
    w.copy("enemy_agent_items", "agent_unique_name, slot, type", agent_item_rows)

    avatar_rows = []
    for un, a in avatars.items():
        avatar_rows.append((un, a.get("name"), a.get("icon"), a.get("description"),
                            a.get("faction"), a.get("damageController"), a.get("health"),
                            a.get("killXPReward"), a.get("factionResistanceKeyword"),
                            a.get("droptable"), a.get("isFrivolous")))
    w.copy("enemy_avatars", "unique_name, name_loc, icon, description_loc, faction, "
                            "damage_controller, health, kill_xp_reward, "
                            "faction_resistance_keyword, droptable, is_frivolous", avatar_rows)

    ctrl_rows, proc_rows, hp_rows = [], [], []
    for un, c in controllers.items():
        ctrl_rows.append((un, _n(c.get("armor")), _n(c.get("shield"))))
        for i, p in enumerate(c.get("unhandledProcTypes") or []):
            proc_rows.append((un, i, p))
        for i, h in enumerate(c.get("hitProxies") or []):
            hp_rows.append((un, i, h.get("bone"), h.get("type")))
    w.copy("enemy_damage_controllers", "unique_name, armor, shield", ctrl_rows)
    w.copy("enemy_damage_controller_procs", "controller_unique_name, slot, proc_type", proc_rows)
    w.copy("enemy_damage_controller_hit_proxies", "controller_unique_name, slot, bone, type", hp_rows)

    w.copy("enemy_droptables", "unique_name", [(un,) for un in droptables])
    pool_rows, item_rows = [], []
    for un, pools in droptables.items():
        for pi, pool in enumerate(pools):
            pool_rows.append((un, pi, _n(pool.get("chance"))))
            for ii, it in enumerate(pool.get("items") or []):
                item_rows.append((un, pi, ii, it.get("type"), _n(it.get("probability"))))
    w.copy("enemy_droptable_pools", "droptable_unique_name, pool_index, chance", pool_rows)
    w.insert_select("""
        INSERT INTO public.enemy_droptable_items (pool_id, slot, type, probability)
        SELECT p.pool_id, v.slot, v.type, v.probability::double precision
        FROM (VALUES {values}) AS v(droptable_unique_name, pool_index, slot, type, probability)
        JOIN public.enemy_droptable_pools p
          ON p.droptable_unique_name = v.droptable_unique_name AND p.pool_index = v.pool_index;""",
        item_rows)

    w.copy("enemy_hit_proxies", "unique_name, damage_atten, critical_chance, critical_multiplier",
           [(un, _n(h.get("damageAtten")), _n(h.get("criticalChance")), _n(h.get("criticalMultiplier")))
            for un, h in hit_proxies.items()])

    w.copy("enemy_ai_weapons", "unique_name, name_loc, description_loc, icon",
           [(un, wd.get("name"), wd.get("description"), wd.get("icon"))
            for un, wd in ai_weapons.items()])
    _emit_behaviours(w, "enemy_ai_weapon_behaviours", "enemy_ai_weapon_behaviour_damage",
                     ai_weapons, fk_col="ai_weapon_unique_name")


def load_worldstate_enums(data_f, data_mt, w):
    """ExportFactions / ExportMissionTypes → worldstate_enums（FC_*/MT_* → loc tag）。"""
    rows = [("faction", code, v.get("name")) for code, v in data_f.items()] \
        + [("mission_type", code, v.get("name")) for code, v in data_mt.items()]
    w.copy("worldstate_enums", "category, enum_code, name_loc", rows)

    # ----- Wiki 手动维护枚举（来源：wiki.warframe.com/w/World_State） -----
    # 格式：category → { code: (zh, en) }
    WIKI_ENUMS = {
        # --- Descendia 任务类型（来源：doroprime + wiki） ---
        "descent_type": {
            "DT_ALCHEMY":          ("元素转换", "Alchemy"),
            "DT_BOSS":             ("刺杀", "Assassination"),
            "DT_BREAK_TARGETS":    ("摧毁全息球", "Destroy Hologlobes"),
            "DT_CAPTURE":          ("传承种捕获", "Capture"),
            "DT_COLLECTION":       ("收集", "Collection"),
            "DT_DEFENSE":          ("防御", "Defense"),
            "DT_EXCAVATION":       ("挖掘", "Excavation"),
            "DT_EXTERMINATE":      ("歼灭", "Exterminate"),
            "DT_INFESTED_SALVAGE": ("净化", "Infested Salvage"),
            "DT_INTERCEPTION":     ("移动拦截", "Mobile Interception"),
            "DT_LOOT":             ("掠夺", "Loot"),
            "DT_LOOT_CREATURES":   ("贪屯断肢劫掠", "Gruzzling Plunder"),
            "DT_MIMICS":           ("掠夺轮盘", "Plunder Roulette"),
            "DT_NETRACELLS":       ("消灭目标", "Targeted Elimination"),
            "DT_PRESURE_GAUGE":    ("压力锅", "Volatile"),
            "DT_PROTOFRAME":       ("保护所", "Protoframe Room"),
            "DT_RACE":             ("时间试炼", "Race"),
            "DT_SABOTAGE_DEFENSE": ("防御", "Defense"),
            "DT_SABOTAGE_HIVE":    ("清巢", "Hive"),
            "DT_SHRINE_DEFENSE":   ("祈运坛防御", "Shrine Defense"),
            "DT_UNIQUE":           ("绝灵骥战斗", "Kaithe Combat"),
        },
        # --- Descendia Challenge / Penance（来源：doroprime + wiki） ---
        "descent_challenge": {
            "ArbitersNightmareLawyer": ("帕尔沃斯的姐妹", "Parvos' Sisters"),
            "ArbitrationDrones":       ("仲裁无人机", "Arbitration Drones"),
            "ArchonAmar":              ("执刑官欺谋狼主", "Archon Amar"),
            "BallonParty":             ("先驱者前哨", "Outrider Post"),
            "BasicBreakTargets":       ("摧毁目标", "Destroy Targets"),
            "BasicLoot":               ("搜寻资源", "Search Resources"),
            "BasicLootCreatures":      ("贪屯断肢劫掠", "Gruzzling Plunder"),
            "BasicMimics":             ("掠夺轮盘", "Plunder Roulette"),
            "BasicRace":               ("时间试炼", "Race"),
            "BlitzLeech":              ("突袭吸血卓越者军团", "Blitz Leech Eximus"),
            "CollectionBasic":         ("收集", "Collection"),
            "CorruptedVor":            ("堕落的Vor", "Corrupted Vor"),
            "Darkness":                ("放逐之阳", "Sol Banished"),
            "Devil":                   ("罗瑟的遗忘", "Roathe's Oblivion"),
            "Escapist":                ("秘密撤离", "Sneaky Retreats"),
            "FieryTrail":              ("防火道", "Fire Trail"),
            "FieryTrailRollers":       ("火球滚轮", "Fireball Rollers"),
            "FireAndIce":              ("冰火卓越者军团", "Fire & Ice Eximus"),
            "FireChain":               ("烈焰枷锁", "Flame Shackles"),
            "FreezeInShoot":           ("冰封之光卓越者军团", "Freeze Beam Eximus"),
            "GiantRealm":              ("巨人症", "Gigantism"),
            "GlassMaker":              ("玻璃匠中枢人", "Glassmaker Cephalites"),
            "GrenadesOnly":            ("易受元素瓶攻击的敌人", "Grenades Only"),
            "Harrow":                  ("里昂的圣所", "Lyon's Sanctuary"),
            "HardShell":               ("冰封卓越者军团", "Frost Eximus"),
            "HeadShotsOnly":           ("只有弱点才会受到伤害", "Headshots Only"),
            "HeavyWeaponsOnly":        ("易受曲翼枪械攻击的敌人", "Heavy Weapons Only"),
            "HordeWeakpoints":         ("弱点敌群", "Weakpoint Horde"),
            "HorseCombatOnly":         ("绝灵骥战斗", "Kaithe Combat Only"),
            "HyenaPack":               ("鬣狗群", "Hyena Pack"),
            "InfestedBoyband":         ("科技细胞终幕者", "Techrot Finale"),
            "InfestedLichDuo":         ("科技细胞终幕者二重对决", "Techrot Lich Duo"),
            "JadeGuardian":            ("翠玉卓越者军团", "Jade Eximus"),
            "Juggernauts":             ("烈焰巨兽", "Juggernauts"),
            "JumpSmash":               ("跺头者", "Head Stompers"),
            "Kullervo":                ("未训之罪", "Untamed Sin"),
            "Manics":                  ("躁狂症", "Manic Mania"),
            "MechCombatOnly":          ("维尔科的复仇", "Veliko's Revenge"),
            "MineField":               ("雷区", "Minefield"),
            "NarmerPhobia":            ("合一众执事", "Narmer Deacons"),
            "NecroMechNormal":         ("殁世机甲", "Necramech"),
            "NecroMechWeakpoints":     ("只有弱点才会受到伤害（机甲）", "Weakpoints Only (Mech)"),
            "NullifierOnly":           ("全面无效", "Nullifier Only"),
            "Octopede":                ("接肢至尊", "The Fragmented"),
            "Oraxia":                  ("Oraxia", "Oraxia"),
            "PoisonGas":               ("化学战", "Chemical Warfare"),
            "PowerHouse":              ("力量贪婪卓越者军团", "Power Draining Eximus"),
            "RaceHorse":               ("绝灵骥战斗", "Kaithe Combat"),
            "RangedArcadiaOnly":       ("泡泡枪", "Bubble Gun"),
            "Raptor2":                 ("猛禽", "Raptor"),
            "RocketsOnly":             ("易受火箭炮攻击的敌人", "Rockets Only"),
            "SecuritySpin":            ("激光炼狱", "Laser Spin"),
            "Sentients":               ("Tau的复仇", "Tau's Revenge"),
            "ShockingLeech":           ("电击吸血卓越者军团", "Shock Leech Eximus"),
            "SlipAndSlide":            ("无摩擦", "Frictionless"),
            "SpicyKnife":              ("拆弹", "Bomb Defusal"),
            "SpikeCeiling":            ("坠落的碎片", "Falling Debris"),
            "Sunlight":                ("太阳神之怒", "Sol's Wrath"),
            "99TankP1":                ("艾弗旺坦克", "Efervon Tank"),
            "99TankP2":                ("科腐者坦克", "Techrot Tank"),
            "ToxicFire":               ("毒焰卓越者军团", "Toxic Fire Eximus"),
            "UnseenFoes":              ("潜在威胁", "Hidden Threats"),
            "VeryToxic":               ("毒蛭吸血卓越者军团", "Toxic Leech Eximus"),
            "VoidAberration":          ("吸血界影", "Vampyric Liminus"),
            "Wisp":                    ("玛丽的圣所", "Marie's Sanctuary"),
        },
        # --- Descendia Level → 地图名 ---
        "descent_level": {
            "ArenaCherry":           ("樱桃竞技场", "Arena Cherry"),
            "ArenaCoconut":          ("椰子竞技场", "Arena Coconut"),
            "ArenaAvocado":          ("牛油果竞技场", "Arena Avocado"),
            "ArenaMelon":            ("甜瓜竞技场", "Arena Melon"),
            "ArenaPeach":            ("蜜桃竞技场", "Arena Peach"),
            "ArenaGrape":            ("葡萄竞技场", "Arena Grape"),
            "ArenaEggplant":         ("茄子竞技场", "Arena Eggplant"),
            "ArenaWaffle":           ("华夫竞技场", "Arena Waffle"),
            "BossArenaSmall":        ("小型Boss竞技场", "Boss Arena Small"),
            "BossArenaUriel":        ("Uriel王座室", "Roathe's Throne Room"),
            "ProtoframeRoomWisp":    ("Marie圣所", "Marie's Sanctuary"),
            "ProtoframeRoomHarrow":  ("Lyon圣所", "Lyon's Sanctuary"),
        },
        # --- Descendia Specs → 敌人种类 ---
        "descent_specs": {
            "CoHCorpusExterminateMixed":         ("Corpus", "Corpus"),
            "VaniaExterminateTechrotSpec":       ("Techrot", "Techrot"),
            "DuviriExterminateHardmodeA":        ("Duviri", "Duviri"),
            "CoHInfestedMicroplanet":            ("灰毒株", "Grey Strain"),
            "CoHForestGrineerFairy":             ("前线Grineer", "Frontier Grineer"),
            "EntratiSwarmSpec":                  ("低语之物", "The Murmur"),
            "CoHCorpusZarimanExterminateSpec":   ("Juno Corpus", "Juno Corpus"),
            "CoHGrineerExterminateFire":         ("Grineer", "Grineer"),
            "DuviriSurvivalSpecA":               ("堕落+Duviri+Thrax", "Corrupted, Duviri & Thrax"),
            "VaniaExterminateScaldraNoBalloonSpec": ("Scaldra", "Scaldra"),
            "PNWNarmerForestGrineerExterminate": ("全阵营", "All Factions"),
            "CoHManicSpec":                      ("全部狂化", "All Manics"),
            "Tau12MinWarDaxSpec":                ("叛军", "Anarchs"),
        },
        # --- Descendia Auras → Penance 效果 ---
        "descent_aura": {
            "CoHSlipAndSlideAura":       ("无摩擦", "Frictionless"),
            "CoHMineFieldAura":          ("雷区", "Minefield"),
            "CoHEscapistAura":           ("潜行撤退", "Sneaky Retreats"),
            "DarknessAura":              ("太阳放逐", "Sol Banished"),
            "CoHVoidAberrationAura":     ("吸血利米努斯", "Vampyric Liminus"),
            "FireAndIceEnhancementAura": ("精英集团：火与冰", "Eximus Cabal: Fire & Ice"),
            "PoisonGasAura":             ("化学战", "Chemical Warfare"),
            "GlassMakerAura":            ("玻璃制造者", "Glassmaker Cephalites"),
            "SpicyKnifeAura":            ("拆弹", "Bomb Defusal"),
            "JumpSmashAura":             ("踩头者", "Head Stompers"),
            "GiantRealmAura":            ("巨大化", "Gigantism"),
        },
        # --- Archimedea 类型 ---
        "archimedea_type": {
            "CT_LAB":  ("深层Archimedea", "Deep Archimedea"),
            "CT_HEX":  ("时序Archimedea", "Temporal Archimedea"),
        },
        # --- Archimedea 难度 ---
        "archimedea_difficulty": {
            "CD_NORMAL": ("普通", "Normal"),
            "CD_HARD":   ("精英Archimedea", "Elite Archimedea"),
        },
        # --- Archimedea Deviation（偏差修正）---
        "archimedea_deviation": {
            "ChemicalNoise":          ("噪音抑制", "Noise Suppression"),
            "ContaminationZone":      ("屏息", "Hold Your Breath"),
            "DisruptiveSounds":       ("吸血摇滚", "Vamp Rock"),
            "DoubleTroubleLegacyte":  ("有丝分裂", "Mitosis"),
            "EscalateImmediately":    ("缓存崩溃", "Cache Crash"),
            "ExplosiveEnergy":        ("毒蛾混合", "Miasmite Mash"),
            "FortifiedFoes":          ("密封装甲", "Sealed Armor"),
            "GestatingTumors":        ("孢子生成", "Sporogenesis"),
            "HighScalingLegacyte":    ("生长激素", "Growth Hormones"),
            "HostileSecurity":        ("干扰之声", "Disruptive Sounds"),
            "MutatedEnemies":         ("平行进化", "Parallel Evolution"),
            "TankReinforcements":     ("增援", "Reinforcements"),
            "TankStrongArmor":        ("热力装甲", "Thermian Plating"),
            "TankSuperToxic":         ("毒坦克", "Toxic Tank"),
            "TechrotConjunction":     ("合力攻击", "Pile-On"),
            "AlchemicalShields":      ("炼金免疫", "Alchemical Invulnerability"),
            "DoubleTrouble":          ("双拆除者", "Double Demolishers"),
            "DuoAssassination":       ("碎片双子", "The Fragmented Two"),
            "EnemyLink":              ("伤害链接", "Damage Link"),
            "EnvironmentalSystem":    ("危险区域", "Hazardous Areas"),
            "EximusGrenadiers":       ("精英安瓿", "Eximus Amphors"),
            "FragileNodes":           ("统一目标", "Unified Purpose"),
            "GrowingIncursion":       ("裂缝级联", "Fissure Cascade"),
            "HarshWords":             ("尖刺铭文", "Barbed Glyphs"),
            "HungryPillars":          ("放射性分解", "Radioactive Breakdown"),
            "InfiniteTide":           ("无情潮汐", "Relentless Tide"),
            "LostInTranslation":      ("铭文膨胀", "Glyph Inflation"),
            "MisguidedInstructions":  ("铭文陷阱", "Glyph Trap"),
            "NecramechActivation":    ("亡骸机甲涌入", "Necramech Influx"),
            "NecramechLockout":       ("敌方支援", "Hostile Support"),
            "Reinforcements":         ("协调前线", "Coordinated Front"),
            "SameTeam":               ("天使同伴", "Angelic Cohort"),
            "StickyFingers":          ("贪噬膨胀", "Engorged Gruzzlings"),
            "UnpoweredCapsules":      ("寄生之塔", "Parasitic Towers"),
            "VolatileGrenades":       ("危险品", "Hazardous Goods"),
        },
        # --- Archimedea Risk Variables（风险变量）---
        "archimedea_risk": {
            "AcceleratedEnemies":       ("大胆投机", "Bold Venture"),
            "AntiMaterialWeapons":      ("指挥炮艇", "Commanding Culverins"),
            "ArcadeAutomata":           ("街机自动机", "Arcade Automata"),
            "ArtilleryBeacons":         ("炮兵信标", "Artillery Beacons"),
            "BalloonFest":              ("气球节", "Balloonfest"),
            "CompetitionSpillover":     ("竞争倾向", "Competitive Streak"),
            "Deflectors":               ("强化敌人", "Fortified Foes"),
            "DrainingResiduals":        ("魔鬼交易", "Devil's Bargain"),
            "EfervonFog":               ("浓雾", "Dense Fog"),
            "EmpoweredEnemies":         ("比例抗性", "Proportional Resistance"),
            "EnemyElementalEnhancement":("元素效力", "Elemental Potency"),
            "ExplosiveCrawlers":        ("爆炸潜力", "Explosive Potential"),
            "ExplosiveSummer":          ("过度爆炸", "Excessive Explosives"),
            "Scaldra":                  ("Scaldra速通", "Scaldra Speed Run"),
            "Techrot":                  ("Techrot速通", "Techrot Speed Run"),
            "FallFog":                  ("雾秋", "Foggy Fall"),
            "HeavyWarfare":             ("重装作战", "Heavy Warfare"),
            "HostileOvergrowth":        ("活性化", "It's Alive"),
            "InfectedTechrot":          ("腐化之躯", "Corrupted Flesh"),
            "JadeSpring":               ("翡翠之灵", "Jade Spirits"),
            "MagneticHounds":           ("诱人蛛形虫", "Alluring Arcocanids"),
            "MeleeOnlyEnemies":         ("近战交锋", "Close Quarters"),
            "MiasmiteHive":             ("毒蛾群", "Miasmite Swarm"),
            "MurmurIncursion":          ("越墙", "Beyond The Wall"),
            "PointBlank":               ("近视弹药", "Myopic Munitions"),
            "Quicksand":                ("纠缠", "Entanglement"),
            "RangedOnlyEnemies":        ("远程交战", "Ranged Engagements"),
            "RegeneratingEnemies":      ("敌方再生", "Hostile Regeneration"),
            "RestrictedConsumables":    ("延迟补给", "Delayed Supply"),
            "RestrictedRespawns":       ("终局", "Finality"),
            "SentientAdaptation":       ("适应畸变", "Adaptive Aberrations"),
            "ShieldedFoes":             ("强化好战者", "Bolstered Belligerents"),
            "Vanquisher":               ("精英增援", "Eximus Reinforcements"),
            "VoidAberration":           ("吸血利米努斯", "Vampyric Liminus"),
            "Voidburst":                ("死后涌动", "Postmortal Surges"),
            "WinterFrost":              ("厚冰", "Thick Ice"),
        },
        # --- Archimedea Personal Modifiers（个人修正）---
        "archimedea_personal": {
            "AbilityLockout":      ("无力", "Powerless"),
            "AntiGuard":           ("守卫下降", "Dropped Guard"),
            "Armorless":           ("碎甲", "Fractured Armor"),
            "ComboCountChance":    ("钝刃", "Dull Blades"),
            "Conductive":          ("导电", "Conductive"),
            "ContactDamage":       ("副武器创伤", "Secondary Wounds"),
            "DamageMomentum":      ("终端速度", "Terminal Velocity"),
            "DecayingFlesh":       ("永久创伤", "Permanent Injury"),
            "EnergyStarved":       ("束缚", "Constricted"),
            "Exhaustion":          ("能量枯竭", "Energy Exhaustion"),
            "ExposureCurse":       ("暴露诅咒", "Exposure Curse"),
            "Framecurse":          ("战甲综合症", "Framecurse Syndrome"),
            "Gearless":            ("装备禁令", "Gear Embargo"),
            "Knifestep":           ("刀刃综合症", "Knifestep Syndrome"),
            "MaxAmmo":             ("补给不足", "Undersupplied"),
            "OperatorLockout":     ("传送扭曲", "Transference Distortion"),
            "OverSensitive":       ("过敏", "Hypersensitive"),
            "Sanguine":            ("嗜血综合症", "Sanguine Syndrome"),
            "ScarcityCurse":       ("弹药匮乏", "Ammo Scarcity"),
            "ShieldDelay":         ("迟钝护盾", "Lethargic Shields"),
            "Starvation":          ("弹药赤字", "Ammo Deficit"),
            "TimeDilation":        ("能力缩减", "Abbreviated Abilities"),
            "Vampyri":             ("吸血综合症", "Vampyric Syndrome"),
            "VitalEnergy":         ("震荡消耗", "Concussive Drain"),
            "VoidEnergyOverload":  ("能力过载", "Ability Overload"),
            "Withering":           ("不可治愈", "Untreatable"),
        },
        # --- VoidT* 虚空遗物等级 ---
        "relic_tier": {
            "VoidT1": ("古纪", "Lith"),
            "VoidT2": ("前纪", "Meso"),
            "VoidT3": ("中纪", "Neo"),
            "VoidT4": ("后纪", "Axi"),
            "VoidT5": ("安魂", "Requiem"),
            "VoidT6": ("全能", "Omnia"),
        },
        # --- SORTIE_BOSS_* 突击/猎杀Boss ---
        "sortie_boss": {
            "SORTIE_BOSS_ALAD":           ("Alad V", "Alad V"),
            "SORTIE_BOSS_AMAR":           ("猎杀者Amar", "Archon Amar"),
            "SORTIE_BOSS_AMBULAS":        ("Ambulas", "Ambulas"),
            "SORTIE_BOSS_BOREAL":         ("猎杀者Boreal", "Archon Boreal"),
            "SORTIE_BOSS_CORRUPTED_VOR":  ("堕落Vor", "Corrupted Vor"),
            "SORTIE_BOSS_NEF":            ("Nef Anyo", "Nef Anyo"),
            "SORTIE_BOSS_HEK":            ("Vay Hek议员", "Councilor Vay Hek"),
            "SORTIE_BOSS_HYENA":          ("鬣狗群", "Hyena Pack"),
            "SORTIE_BOSS_INFALAD":        ("异变Alad V", "Mutalist Alad V"),
            "SORTIE_BOSS_JACKAL":         ("豺狼", "Jackal"),
            "SORTIE_BOSS_KELA":           ("Kela De Thaym", "Kela De Thaym"),
            "SORTIE_BOSS_KRIL":           ("Lech Kril中尉", "Lieutenant Lech Kril"),
            "SORTIE_BOSS_LEPHANTIS":      ("Lephantis", "Lephantis"),
            "SORTIE_BOSS_NIRA":           ("猎杀者Nira", "Archon Nira"),
            "SORTIE_BOSS_PHORID":         ("Phorid", "Phorid"),
            "SORTIE_BOSS_RAPTOR":         ("猛禽", "Raptors"),
            "SORTIE_BOSS_RUK":            ("Sargas Ruk将军", "General Sargas Ruk"),
            "SORTIE_BOSS_TYL":            ("Tyl Regor", "Tyl Regor"),
            "SORTIE_BOSS_VOR":            ("Vor船长", "Captain Vor"),
        },
        # --- SORTIE_MODIFIER_* 突击修正 ---
        "sortie_modifier": {
            "SORTIE_MODIFIER_LOW_ENERGY":      ("能量削减", "Energy Reduction"),
            "SORTIE_MODIFIER_IMPACT":          ("冲击增强", "Enemy Physical Enhancement: Impact"),
            "SORTIE_MODIFIER_SLASH":           ("切割增强", "Enemy Physical Enhancement: Slash"),
            "SORTIE_MODIFIER_PUNCTURE":        ("穿刺增强", "Enemy Physical Enhancement: Puncture"),
            "SORTIE_MODIFIER_EXIMUS":          ("精英要塞", "Eximus Stronghold"),
            "SORTIE_MODIFIER_MAGNETIC":        ("磁力增强", "Enemy Elemental Enhancement: Magnetic"),
            "SORTIE_MODIFIER_CORROSIVE":       ("腐蚀增强", "Enemy Elemental Enhancement: Corrosive"),
            "SORTIE_MODIFIER_VIRAL":           ("病毒增强", "Enemy Elemental Enhancement: Viral"),
            "SORTIE_MODIFIER_ELECTRICITY":     ("电击增强", "Enemy Elemental Enhancement: Electricity"),
            "SORTIE_MODIFIER_RADIATION":       ("辐射增强", "Enemy Elemental Enhancement: Radiation"),
            "SORTIE_MODIFIER_FIRE":            ("火焰增强", "Enemy Elemental Enhancement: Heat"),
            "SORTIE_MODIFIER_EXPLOSION":       ("爆炸增强", "Enemy Elemental Enhancement: Blast"),
            "SORTIE_MODIFIER_FREEZE":          ("冰冻增强", "Enemy Elemental Enhancement: Cold"),
            "SORTIE_MODIFIER_POISON":          ("毒素增强", "Enemy Elemental Enhancement: Toxin"),
            "SORTIE_MODIFIER_HAZARD_RADIATION": ("辐射区", "Environmental Hazard: Radiation Pockets"),
            "SORTIE_MODIFIER_HAZARD_MAGNETIC":  ("电磁异常", "Environmental Hazard: Electromagnetic Anomalies"),
            "SORTIE_MODIFIER_HAZARD_FOG":       ("浓雾", "Environmental Hazard: Dense Fog"),
            "SORTIE_MODIFIER_HAZARD_FIRE":      ("火焰", "Environmental Hazard: Fire"),
            "SORTIE_MODIFIER_HAZARD_ICE":       ("低温泄漏", "Environmental Effect: Cryogenic Leakage"),
            "SORTIE_MODIFIER_HAZARD_COLD":      ("极寒", "Environmental Effect: Extreme Cold"),
            "SORTIE_MODIFIER_ARMOR":           ("增强护甲", "Augmented Enemy Armor"),
            "SORTIE_MODIFIER_SHIELDS":         ("增强护盾", "Enhanced Enemy Shields"),
            "SORTIE_MODIFIER_SECONDARY_ONLY":  ("仅限手枪", "Weapon Restriction: Pistol Only"),
            "SORTIE_MODIFIER_SHOTGUN_ONLY":    ("仅限霰弹枪", "Weapon Restriction: Shotgun Only"),
            "SORTIE_MODIFIER_SNIPER_ONLY":     ("仅限狙击枪", "Weapon Restriction: Sniper Only"),
            "SORTIE_MODIFIER_RIFLE_ONLY":      ("仅限步枪", "Weapon Restriction: Assault Rifle Only"),
            "SORTIE_MODIFIER_MELEE_ONLY":      ("仅限近战", "Weapon Restriction: Melee Only"),
            "SORTIE_MODIFIER_BOW_ONLY":        ("仅限弓箭", "Weapon Restriction: Bow Only"),
        },
        # --- GlobalUpgrades 全局增益类型 ---
        "upgrade_type": {
            "GAMEPLAY_KILL_XP_AMOUNT":       ("经验加成", "Affinity Booster"),
            "GAMEPLAY_MONEY_REWARD_AMOUNT":  ("星币加成", "Credit Booster"),
            "GAMEPLAY_PICKUP_AMOUNT":        ("资源加成", "Resource Booster"),
        },
        # --- KnownCalendarSeasons 季节 ---
        "calendar_season": {
            "CST_WINTER": ("冬季", "Winter"),
            "CST_SPRING": ("春季", "Spring"),
            "CST_SUMMER": ("夏季", "Summer"),
            "CST_AUTUMN": ("秋季", "Autumn"),
        },
        # --- Calendar Event Type ---
        "calendar_event_type": {
            "CET_CHALLENGE": ("挑战", "Challenge"),
            "CET_REWARD":    ("奖励", "Reward"),
            "CET_UPGRADE":   ("覆写", "Override"),
        },
        # --- Goals 事件内部名 ---
        "goal_tag": {
            "CorpusRazorbackProject": ("利刃叛军", "Razorback Armada"),
            "Fomorian":               ("福米尼安破坏", "Fomorian Sabotage"),
            "HeatFissure":            ("热美亚裂缝", "Thermia Fractures"),
            "GhoulEmergence":         ("食尸鬼清扫", "Ghoul Purge"),
        },
    }

    # 统一写入 worldstate_enums + localizations（upsert，不覆盖已有）
    enum_rows = []
    loc_rows = []

    # 枚举描述（description 列）
    WIKI_DESCRIPTIONS = {
        # 深层/时光科研 — 偏差
        "archimedea_deviation": {
            "VolatileGrenades": "携带元素瓶时会受到对应元素伤害",
            "UnpoweredCapsules": "维生装置塔需击杀20敌人才激活",
            "LostInTranslation": "浮印膨胀：需双倍荧音浮印激活安全系统",
            "EscalateImmediately": "每轮产生两个传承种，需双倍捕获次数",
            "DoubleTroubleLegacyte": "每轮产生两个传承种，需双倍捕获次数",
            "DisruptiveSounds": "无人机向弗莱尔喷射艾弗旺气体",
            "AlchemicalShields": "10%敌人装备不可穿透元素屏障",
            "ChemicalNoise": "高危物资：携带元素瓶受对应元素伤害",
            "ContaminationZone": "整个区域随停留时间造成毒素伤害",
            "Deflectors": "非弱点命中伤害降低90%",
            "DrainingResiduals": "维生塔附近击杀20敌人才激活",
            "FortifiedFoes": "敌人装备不可穿透元素屏障",
            "GestatingTumors": "维生塔附近出现科腐者肿瘤加速衰减",
            "GrowingIncursion": "科腐者敌人攻击净化器，接触引爆",
            "HostileSecurity": "卓越者敌人支援断肢潮和接肢怪",
            "InfiniteTide": "断肢潮不会停止攻击",
            "MutatedEnemies": "敌人受元素伤害时产生抗性",
            "NecramechActivation": "可能出现守护者卓越者敌人",
            "NecramechLockout": "敌人距离15米内才受伤害",
            "Reinforcements": "战斗中有敌方援军抵达",
            "SameTeam": "伤害链接：10米内敌人伤害均摊",
            "StickyFingers": "浮印附传送门陷阱",
            "TankReinforcements": "只有热熔火箭炮能伤害坦克",
            "TankStrongArmor": "只有热熔火箭炮能伤害坦克",
            "TankSuperToxic": "坦克拥有毒素光环和毒素尾迹",
            "TechrotConjunction": "科腐者自爆虫从阴影中蜂拥而出",
            "ExplosiveEnergy": "敌人死亡时掉落自爆虫立即冲向弗莱尔",
            "HungryPillars": "浮印被收集时造成火焰伤害",
            "EnvironmentalSystem": "激活维生塔清除危险区域",
            "DoubleTrouble": "每个导管受两台爆破型殁世机甲攻击",
        },
        # 深层/时光科研 — 风险
        "archimedea_risk": {
            "RegeneratingEnemies": "敌人生命值缓慢恢复",
            "DrainingResiduals": "不死界影吸取友军生命和能量",
            "VoidAberration": "不死界影吸取友军生命和能量",
            "AcceleratedEnemies": "敌人移动/攻击/射速+15%",
            "AntiMaterialWeapons": "暴戾重型炮兵对超宏防护造成5倍伤害",
            "ArcadeAutomata": "敌人枪械发射巨大缓慢球体",
            "ArtilleryBeacons": "炽蛇军被击杀时掉落光能炮信标",
            "BalloonFest": "炽蛇军前哨气球更多更快",
            "CompetitionSpillover": "阿米尔和碧对战产生随机负面惩罚",
            "Deflectors": "可能出现守护者卓越者敌人",
            "EfervonFog": "艾弗旺气体覆盖整个关卡",
            "EmpoweredEnemies": "部署额外的卓越者敌人",
            "EnemyElementalEnhancement": "敌人+100%元素伤害+85%元素抗性",
            "ExplosiveCrawlers": "爆裂断肢取代蹒跚断肢",
            "ExplosiveSummer": "所有补给箱被炸药桶取代",
            "FallFog": "迷雾限制整个任务区视野",
            "HeavyWarfare": "非重型武器伤害减少90%",
            "HostileOvergrowth": "敌人被注入艾弗旺，击杀后爆炸",
            "InfectedTechrot": "所有敌人被科腐者取代且移动更快",
            "JadeSpring": "翠玉之灵徘徊并转变为翠玉光束",
            "MagneticHounds": "暴戾弧犬攻击时将战甲拉向自己",
            "MeleeOnlyEnemies": "只出现近战攻击的敌人",
            "MiasmiteHive": "地下停止移动时敌方增生物发起攻击",
            "MurmurIncursion": "低语者敌人加入炽蛇军和科腐者",
            "PointBlank": "距离敌人15米内才受伤害",
            "Quicksand": "被击杀敌人4米内移动和跑酷速度降低",
            "RangedOnlyEnemies": "只出现远程攻击的敌人",
            "RestrictedConsumables": "被击杀敌人4米内牺牲50%弹药效率换+25%射速",
            "RestrictedRespawns": "被击杀敌人爆发出虚空能量",
            "Scaldra": "所有敌人被炽蛇军取代且移动更快",
            "SentientAdaptation": "敌人受元素伤害时产生相应抗性",
            "ShieldedFoes": "所有敌人获得50%最大生命值的超宏防护",
            "Techrot": "科腐者敌人被注入艾弗旺，击杀后爆炸",
            "Vanquisher": "敌人造成-15%伤害，受+15%伤害，速度+15%",
            "Voidburst": "被击杀敌人爆发虚空能量",
            "WinterFrost": "极寒卓越者护罩耐久度10倍",
        },
        # 沉沦之地 — 任务类型
        "descent_type": {
            "DT_ALCHEMY": "使用敌人掉落的两种元素安瓿填充坩埚，完成转化流程",
            "DT_EXTERMINATE": "击杀指定数量的敌人",
            "DT_LOOT_CREATURES": "击杀贪囤断肢以获取热火核和怒火核",
            "DT_INFESTED_SALVAGE": "使用抗血清为汽化器供能，净化3个感染节点",
            "DT_COLLECTION": "收集指定数量的修复凝液",
            "DT_EXCAVATION": "保护挖掘机，用能量电池为其供能",
            "DT_BREAK_TARGETS": "击杀指定数量的标记敌人",
            "DT_RACE": "在时间限制内依序穿过多个闸门，每通过一个增加5秒",
            "DT_LOOT": "玩家有30秒时间搜刮储物容器",
            "DT_MIMICS": "玩家有30秒搜刮储物柜，部分可能是拟态者",
            "DT_DEFENSE": "抵御单波敌人，保护玛丽、里昂或冷冻舱",
            "DT_SABOTAGE_HIVE": "摧毁感染肿瘤以消灭其虫巢",
            "DT_PRESURE_GAUGE": "填充转化进度条，指针在白色括号内时进度更快",
            "DT_INTERCEPTION": "跟随移动的星盘以填充解码进度条",
            "DT_BOSS": "击败头目以继续前进",
            "DT_NETRACELLS": "保护Kalymos以生成传承种，不会生成信息素且不逃跑",
            "DT_SABOTAGE_DEFENSE": "在位置生成供品，阻止敌人进入，两供品送抵后召唤感染恶鬼",
            "DT_UNIQUE": "特殊挑战（Kullervo/堕落的沃尔/H-09坦克/Oraxia/罗瑟等）",
            "DT_PROTOFRAME": "骑乘绝灵骥摧毁指定数量目标",
            "DT_SHRINE_DEFENSE": "在位置生成供品，阻止敌人进入，两供品送抵后召唤感染恶鬼",
            "DT_CAPTURE": "击败头目以继续前进",
        },
        # 沉沦之地 — 赎罪
        "descent_challenge": {
            "ArbitrationDrones": "敌人受到仲裁护盾无人机的保护",
            "Escapist": "敌人生命值降至一半时短暂无敌并传送离开",
            "SpicyKnife": "玩家会散发热量，15秒后爆炸造成巨额伤害；击杀敌人可延缓",
            "FreezeInShoot": "敌方投射物被替换为缓慢移动的大型能量球",
            "FireChain": "敌人之间由燃烧光束相连，接触会灼烧玩家",
            "PoisonGas": "竞技场弥漫毒气，敌人掉落安全区域以规避伤害",
            "BallonParty": "敌人生成卓越者单位概率大幅提高",
            "SpikeCeiling": "天花板不断掉落残骸，击中的单位受到伤害",
            "FieryTrail": "敌人留下燃烧轨迹，灼烧玩家",
            "FieryTrailRollers": "所有敌人均为滚轮单位，留下火焰轨迹",
            "RangedArcadiaOnly": "只能使用曲翼枪械",
            "NullifierOnly": "敌人对除安瓿外的伤害具有极高抗性",
            "RocketsOnly": "敌人对除火箭外的伤害具有极高抗性",
            "SlipAndSlide": "玩家摩擦力大幅降低",
            "GiantRealm": "敌人体型更大、行动更慢",
            "GlassMaker": "虚空裂隙将敌人变成玻璃，玻璃碎片被破坏前不死",
            "JumpSmash": "敌人体型更小，被踩踏时受到巨额伤害",
            "UnseenFoes": "敌人在首次攻击前处于隐形状态",
            "SecuritySpin": "周期性生成激光防护网并围绕基座旋转",
            "Manics": "所有敌人均为狂人",
            "Octopede": "出现合一众执事，其视野会减速玩家",
            "HeadShotsOnly": "敌人弱点以外受到的伤害大幅削减",
            "Darkness": "该炼狱关闭照明，环境变得黑暗",
            "Sunlight": "敌人散发伤害性光环，进入范围的玩家受到伤害",
            "Sentients": "所有敌人均为Sentient",
            "HordeWeakpoints": "弱点以外伤害大幅降低，敌人更倾向近战蜂拥",
            "Harrow": "击败Kullervo",
            "CorruptedVor": "击败堕落的沃尔",
            "Oraxia": "击败Oraxia（只有两条生命值）",
            "VoidAberration": "击败堕落的沃尔",
            "Kullervo": "击败Kullervo",
            "99TankP1": "击败H-09艾弗旺坦克",
            "99TankP2": "击败科技细胞终幕者",
            "Devil": "击败最终头目罗瑟",
            "Wisp": "骑乘绝灵骥摧毁目标",
            "BasicRace": "在时间限制内穿过闸门",
            "BasicLoot": "30秒搜刮储物容器",
            "BasicMimics": "30秒搜刮储物柜，部分可能是拟态者",
            "BasicBreakTargets": "击杀标记敌人",
            "CollectionBasic": "收集修复凝液",
            "InfestedBoyband": "击败执刑官混沌蛇主",
            "InfestedLichDuo": "击败科技细胞终幕者",
            "BasicLootCreatures": "击杀贪囤断肢获取热火核和怒火核",
            "BlitzLeech": "被击杀敌人4米内牺牲弹药效率换射速",
            "FireAndIce": "极寒、纵火或冲锋卓越者",
            "GrenadesOnly": "只能使用曲翼枪械",
            "HardShell": "敌人装备不可穿透元素屏障",
            "HeavyWeaponsOnly": "只能使用重型武器",
            "HorseCombatOnly": "骑乘绝灵骥摧毁目标",
            "JadeGuardian": "翠玉之灵徘徊并转变为翠玉光束",
            "MineField": "天花板不断掉落残骸",
            "NarmerPhobia": "敌人散发伤害性光环",
            "NecroMechWeakpoints": "只能使用殁世机甲攻击",
            "PowerHouse": "被击杀敌人爆发出虚空能量",
            "ShockingLeech": "不死界影吸取友军生命和能量",
            "ToxicFire": "纵火、电击或剧毒卓越者",
            "VeryToxic": "竞技场弥漫毒气",
            "ArbitersNightmareLich": "卓越者敌人支援断肢潮和接肢怪",
            "ArchonBoreal": "击败执政官Boreal",
            "JohnProdman": "击败John Prodman",
            "MechCombatOnly": "只能使用殁世机甲",
        },
    }

    for category, entries in WIKI_ENUMS.items():
        for code, (zh, en) in entries.items():
            loc_tag = f"/_ws/{category}/{code}"
            enum_rows.append((category, code, loc_tag))
            loc_rows.append((loc_tag, "zh", zh))
            loc_rows.append((loc_tag, "en", en))
    w.upsert("worldstate_enums", "category, enum_code, name_loc",
             enum_rows, conflict_cols=["category", "enum_code"], update_col="name_loc")
    w.upsert("localizations", "loc_tag, lang, value",
             loc_rows, conflict_cols=["loc_tag", "lang"], update_col="value")
    # 写入 description 列
    desc_rows = []
    for category, entries in WIKI_DESCRIPTIONS.items():
        for code, desc in entries.items():
            desc_rows.append((category, code, desc))
    w.upsert("worldstate_enums", "category, enum_code, description",
             desc_rows, conflict_cols=["category", "enum_code"], update_col="description")


# ---------------------------------------------------------------------------
# warframe.market 物品数据加载（来源：42bytes-team/wfm-items）
# ---------------------------------------------------------------------------
WFM_ITEMS_REPO = "https://github.com/42bytes-team/wfm-items.git"
WFM_ITEMS_DIR = os.path.join(HERE, "temp", "wfm-items")

def load_wfm_items(w, langs=None):
    """从 wfm-items 仓库拉取物品数据并写入 wfm_items + wfm_item_i18n。"""
    import subprocess
    if langs is None:
        langs = ["zh"]

    # 拉取/更新仓库
    if os.path.exists(WFM_ITEMS_DIR):
        subprocess.run(["git", "-C", WFM_ITEMS_DIR, "pull", "--ff-only"],
                       capture_output=True, timeout=30)
    else:
        subprocess.run(["git", "clone", "--depth", "1", WFM_ITEMS_REPO, WFM_ITEMS_DIR],
                       capture_output=True, timeout=60)

    items_dir = os.path.join(WFM_ITEMS_DIR, "tracked", "items")
    if not os.path.isdir(items_dir):
        print(f"[warn] wfm-items 目录不存在: {items_dir}")
        return

    item_rows = []
    i18n_rows = []
    # wfm 语言代码 → 我们的语言代码
    lang_map = {"zh-hans": "zh", "zh-hant": "tc"}

    for fname in os.listdir(items_dir):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(items_dir, fname), encoding="utf-8") as fp:
            d = json.load(fp)

        wfm_id = d.get("_id", "")
        slug = d.get("url_name", "")
        game_ref_obj = d.get("game_ref") or {}
        game_ref = game_ref_obj.get("uniq_name") if isinstance(game_ref_obj, dict) else None
        tags = d.get("tags") or []
        icon = d.get("icon")
        thumb = d.get("thumb")

        def _int(v):
            if v is None:
                return None
            return int(float(v))

        item_rows.append((
            wfm_id, slug, game_ref, tags, d.get("tradable", True),
            d.get("rarity"), _int(d.get("mod_max_rank")), _int(d.get("mastery_level")),
            _int(d.get("ducats")), _int(d.get("trading_tax")),
            icon, thumb,
        ))

        # i18n
        for wfm_lang, data in (d.get("i18n") or {}).items():
            our_lang = lang_map.get(wfm_lang, wfm_lang)
            if our_lang not in langs and our_lang != "en":
                continue
            i18n_rows.append((
                wfm_id, our_lang,
                data.get("item_name"), data.get("description"), data.get("wiki_link"),
            ))

    w.copy("wfm_items",
           "wfm_id, slug, game_ref, tags, tradable, rarity, mod_max_rank, "
           "mastery_level, ducats, trading_tax, icon, thumb", item_rows)
    w.copy("wfm_item_i18n",
           "wfm_id, lang, item_name, description, wiki_link", i18n_rows)
    print(f"[ok] wfm-items: {len(item_rows)} 物品, {len(i18n_rows)} 翻译条目")

    # ---- 紫卡武器 ----
    _load_wfm_subdir(w, WFM_ITEMS_DIR, "tracked/rivens/items", "wfm_riven_items",
                     cols="wfm_id, slug, game_ref, riven_type, \"group\", disposition, "
                          "mastery_level, icon, thumb",
                     extract=lambda d: (
                         d["_id"], d["url_name"],
                         (d.get("game_ref") or {}).get("uniq_name"),
                         d.get("riven_type"), d.get("group"),
                         d.get("disposition"), _int(d.get("mastery_level")),
                         d.get("icon"), d.get("thumb"),
                     ),
                     i18n_table="wfm_riven_item_i18n",
                     i18n_cols="wfm_id, lang, item_name, wiki_link",
                     i18n_extract=lambda wid, _lang, data: (wid, _lang, data.get("item_name"), data.get("wiki_link")),
                     label="riven-items")

    # ---- 紫卡词条 ----
    _load_wfm_subdir(w, WFM_ITEMS_DIR, "tracked/rivens/attributes", "wfm_riven_attributes",
                     cols="wfm_id, slug, \"group\", prefix, suffix, positive_is_negative, "
                          "negative_only, positive_only, exclusive_to, units, search_only, "
                          "game_ref, icon, thumb",
                     extract=lambda d: (
                         d["_id"], d["url_name"], d.get("group"),
                         d.get("prefix"), d.get("suffix"),
                         d.get("positive_is_negative"), d.get("negative_only"),
                         d.get("positive_only"), d.get("exclusive_to") or [],
                         d.get("units"), d.get("search_only"),
                         (d.get("game_ref") or {}).get("uniq_name"),
                         d.get("icon"), d.get("thumb"),
                     ),
                     i18n_table="wfm_riven_attr_i18n",
                     i18n_cols="wfm_id, lang, effect",
                     i18n_extract=lambda wid, _lang, data: (wid, _lang, data.get("effect")),
                     label="riven-attrs")

    # ---- 赤毒玄骸武器 ----
    _load_wfm_subdir(w, WFM_ITEMS_DIR, "tracked/liches/weapons", "wfm_lich_weapons",
                     cols="wfm_id, slug, game_ref, icon_format, mastery_level, icon, thumb",
                     extract=lambda d: (
                         d["_id"], d["url_name"],
                         (d.get("game_ref") or {}).get("uniq_name"),
                         d.get("icon_format"), _int(d.get("mastery_level")),
                         d.get("icon"), d.get("thumb"),
                     ),
                     i18n_table="wfm_lich_weapon_i18n",
                     i18n_cols="wfm_id, lang, item_name, wiki_link",
                     i18n_extract=lambda wid, _lang, data: (wid, _lang, data.get("item_name"), data.get("wiki_link")),
                     label="lich-weapons")

    # ---- 赤毒玄骸幻纹 ----
    _load_wfm_subdir(w, WFM_ITEMS_DIR, "tracked/liches/ephemeras", "wfm_lich_ephemeras",
                     cols="wfm_id, slug, game_ref, animation, element, icon, thumb",
                     extract=lambda d: (
                         d["_id"], d["url_name"],
                         (d.get("game_ref") or {}).get("uniq_name"),
                         d.get("animation"), d.get("element"),
                         d.get("icon"), d.get("thumb"),
                     ),
                     i18n_table="wfm_lich_ephemera_i18n",
                     i18n_cols="wfm_id, lang, item_name, wiki_link",
                     i18n_extract=lambda wid, _lang, data: (wid, _lang, data.get("item_name"), data.get("wiki_link")),
                     label="lich-ephemeras")

    # ---- 帕尔沃斯姐妹武器 ----
    _load_wfm_subdir(w, WFM_ITEMS_DIR, "tracked/sisters/weapons", "wfm_sister_weapons",
                     cols="wfm_id, slug, game_ref, icon_format, mastery_level, icon, thumb",
                     extract=lambda d: (
                         d["_id"], d["url_name"],
                         (d.get("game_ref") or {}).get("uniq_name"),
                         d.get("icon_format"), _int(d.get("mastery_level")),
                         d.get("icon"), d.get("thumb"),
                     ),
                     i18n_table="wfm_sister_weapon_i18n",
                     i18n_cols="wfm_id, lang, item_name, wiki_link",
                     i18n_extract=lambda wid, _lang, data: (wid, _lang, data.get("item_name"), data.get("wiki_link")),
                     label="sister-weapons")

    # ---- 帕尔沃斯姐妹幻纹 ----
    _load_wfm_subdir(w, WFM_ITEMS_DIR, "tracked/sisters/ephemeras", "wfm_sister_ephemeras",
                     cols="wfm_id, slug, game_ref, animation, element, icon, thumb",
                     extract=lambda d: (
                         d["_id"], d["url_name"],
                         (d.get("game_ref") or {}).get("uniq_name"),
                         d.get("animation"), d.get("element"),
                         d.get("icon"), d.get("thumb"),
                     ),
                     i18n_table="wfm_sister_ephemera_i18n",
                     i18n_cols="wfm_id, lang, item_name, wiki_link",
                     i18n_extract=lambda wid, _lang, data: (wid, _lang, data.get("item_name"), data.get("wiki_link")),
                     label="sister-ephemeras")


def _load_wfm_subdir(w, repo_dir, subdir, table, cols, extract, i18n_table, i18n_cols, i18n_extract, label):
    """通用 wfm-items 子目录加载器。"""
    dir_path = os.path.join(repo_dir, subdir)
    if not os.path.isdir(dir_path):
        print(f"[skip] wfm {label}: {dir_path} 不存在")
        return

    rows = []
    i18n_rows = []
    lang_map = {"zh-hans": "zh", "zh-hant": "tc"}

    for fname in os.listdir(dir_path):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(dir_path, fname), encoding="utf-8") as fp:
            d = json.load(fp)
        rows.append(extract(d))
        wfm_id = d["_id"]
        for wfm_lang, data in (d.get("i18n") or {}).items():
            our_lang = lang_map.get(wfm_lang, wfm_lang)
            i18n_rows.append(i18n_extract(wfm_id, our_lang, data))

    w.copy(table, cols, rows)
    w.copy(i18n_table, i18n_cols, i18n_rows)
    print(f"[ok] wfm {label}: {len(rows)} 条目, {len(i18n_rows)} 翻译")


# ---------------------------------------------------------------------------
# 常用别名（中文玩家社区常用简称）
# 来源：灰机wiki 术语表 + 社区调研
# 格式：(alias, entity_type, entity_id)
# ---------------------------------------------------------------------------
DEFAULT_ALIASES = [
    # ---- 战甲（warframes） ----
    ("阿屎", "warframes", "/Lotus/Powersuits/Ninja/Ninja"),
    ("轮椅", "warframes", "/Lotus/Powersuits/Ninja/Ninja"),
    ("土甲", "warframes", "/Lotus/Powersuits/Brawler/Brawler"),
    ("一拳超人", "warframes", "/Lotus/Powersuits/Brawler/Brawler"),
    ("武僧", "warframes", "/Lotus/Powersuits/Pacifist/Pacifist"),
    ("和尚", "warframes", "/Lotus/Powersuits/Pacifist/Pacifist"),
    ("音妈", "warframes", "/Lotus/Powersuits/Banshee/Banshee"),
    ("龙甲", "warframes", "/Lotus/Powersuits/Dragon/Dragon"),
    ("龙", "warframes", "/Lotus/Powersuits/Dragon/Dragon"),
    ("咖喱棒", "warframes", "/Lotus/Powersuits/Excalibur/Excalibur"),
    ("咖喱", "warframes", "/Lotus/Powersuits/Excalibur/Excalibur"),
    ("黑咖喱", "warframes", "/Lotus/Powersuits/Excalibur/ExcaliburUmbra"),
    ("扶她", "warframes", "/Lotus/Powersuits/YinYang/YinYang"),
    ("阴阳甲", "warframes", "/Lotus/Powersuits/YinYang/YinYang"),
    ("火鸡", "warframes", "/Lotus/Powersuits/Ember/Ember"),
    ("火女", "warframes", "/Lotus/Powersuits/Ember/Ember"),
    ("冰男", "warframes", "/Lotus/Powersuits/Frost/Frost"),
    ("玻璃甲", "warframes", "/Lotus/Powersuits/Glass/Glass"),
    ("血妈", "warframes", "/Lotus/Powersuits/Garuda/Garuda"),
    ("血甲", "warframes", "/Lotus/Powersuits/Garuda/Garuda"),
    ("高斯", "warframes", "/Lotus/Powersuits/Runner/Runner"),
    ("快男", "warframes", "/Lotus/Powersuits/Runner/Runner"),
    ("跑男", "warframes", "/Lotus/Powersuits/Runner/Runner"),
    ("肥宅", "warframes", "/Lotus/Powersuits/Devourer/Devourer"),
    ("胖子", "warframes", "/Lotus/Powersuits/Devourer/Devourer"),
    ("主教", "warframes", "/Lotus/Powersuits/Priest/Priest"),
    ("水男", "warframes", "/Lotus/Powersuits/Pirate/Pirate"),
    ("母牛", "warframes", "/Lotus/Powersuits/IronFrame/IronFrame"),
    ("牛妹", "warframes", "/Lotus/Powersuits/IronFrame/IronFrame"),
    ("沙甲", "warframes", "/Lotus/Powersuits/Sandman/Sandman"),
    ("弓妹", "warframes", "/Lotus/Powersuits/Ranger/Ranger"),
    ("猫甲", "warframes", "/Lotus/Powersuits/Khora/Khora"),
    ("蜘蛛甲", "warframes", "/Lotus/Powersuits/Khora/Khora"),
    ("小明", "warframes", "/Lotus/Powersuits/Magician/Magician"),
    ("李明博", "warframes", "/Lotus/Powersuits/Magician/Magician"),
    ("磁妹", "warframes", "/Lotus/Powersuits/Mag/Mag"),
    ("马哥", "warframes", "/Lotus/Powersuits/Mag/Mag"),
    ("女枪", "warframes", "/Lotus/Powersuits/Cowgirl/Cowgirl"),
    ("小丑", "warframes", "/Lotus/Powersuits/Harlequin/Harlequin"),
    ("摸尸", "warframes", "/Lotus/Powersuits/Necro/Necro"),
    ("血摸", "warframes", "/Lotus/Powersuits/Necro/Necro"),
    ("蓝摸", "warframes", "/Lotus/Powersuits/Necro/Necro"),
    ("哪吒", "warframes", "/Lotus/Powersuits/Nezha/Nezha"),
    ("感染甲", "warframes", "/Lotus/Powersuits/Infestation/Infestation"),
    ("蛆甲", "warframes", "/Lotus/Powersuits/Infestation/Infestation"),
    ("蛆爹", "warframes", "/Lotus/Powersuits/Infestation/Infestation"),
    ("诺娃", "warframes", "/Lotus/Powersuits/AntiMatter/Anti"),
    ("加速娃", "warframes", "/Lotus/Powersuits/AntiMatter/Anti"),
    ("减速娃", "warframes", "/Lotus/Powersuits/AntiMatter/Anti"),
    ("脑溢血", "warframes", "/Lotus/Powersuits/Jade/Jade"),
    ("奶爸", "warframes", "/Lotus/Powersuits/Paladin/Paladin"),
    ("音乐甲", "warframes", "/Lotus/Powersuits/Bard/Bard"),
    ("DJ", "warframes", "/Lotus/Powersuits/Bard/Bard"),
    ("DJ甲", "warframes", "/Lotus/Powersuits/Bard/Bard"),
    ("犀牛", "warframes", "/Lotus/Powersuits/Rhino/Rhino"),
    ("牛甲", "warframes", "/Lotus/Powersuits/Rhino/Rhino"),
    ("踩牛", "warframes", "/Lotus/Powersuits/Rhino/Rhino"),
    ("吼牛", "warframes", "/Lotus/Powersuits/Rhino/Rhino"),
    ("夜灵甲", "warframes", "/Lotus/Powersuits/Revenant/Revenant"),
    ("毒妈", "warframes", "/Lotus/Powersuits/Saryn/Saryn"),
    ("奶妈", "warframes", "/Lotus/Powersuits/Trinity/Trinity"),
    ("蝶甲", "warframes", "/Lotus/Powersuits/Fairy/Fairy"),
    ("蝶妹", "warframes", "/Lotus/Powersuits/Fairy/Fairy"),
    ("瓦喵", "warframes", "/Lotus/Powersuits/Berserker/Berserker"),
    ("女汉子", "warframes", "/Lotus/Powersuits/Berserker/Berserker"),
    ("女武神", "warframes", "/Lotus/Powersuits/Berserker/Berserker"),
    ("工程甲", "warframes", "/Lotus/Powersuits/Trapper/Trapper"),
    ("工程", "warframes", "/Lotus/Powersuits/Trapper/Trapper"),
    ("电男", "warframes", "/Lotus/Powersuits/Volt/Volt"),
    ("伏特", "warframes", "/Lotus/Powersuits/Volt/Volt"),
    ("猴子", "warframes", "/Lotus/Powersuits/MonkeyKing/MonkeyKing"),
    ("悟空", "warframes", "/Lotus/Powersuits/MonkeyKing/MonkeyKing"),
    ("幽浮", "warframes", "/Lotus/Powersuits/Wisp/Wisp"),
    ("鬼妹", "warframes", "/Lotus/Powersuits/Wisp/Wisp"),
    ("花甲", "warframes", "/Lotus/Powersuits/Wisp/Wisp"),
    ("花妈", "warframes", "/Lotus/Powersuits/Wisp/Wisp"),
    ("鸟姐", "warframes", "/Lotus/Powersuits/Tengu/Tengu"),
    # ---- 新战甲（术语表补充） ----
    ("茶妹", "warframes", "/Lotus/Powersuits/Railjack/Railjack"),   # Protea
    ("刀哥", "warframes", "/Lotus/Powersuits/Kullervo/Kullervo"),    # Kullervo
    ("但丁", "warframes", "/Lotus/Powersuits/Dante/Dante"),           # Dante
    ("扣妹", "warframes", "/Lotus/Powersuits/Koumei/Koumei"),         # Koumei
    ("骰妹", "warframes", "/Lotus/Powersuits/Koumei/Koumei"),
    ("狼妹", "warframes", "/Lotus/Powersuits/Voruna/Voruna"),         # Voruna
    ("狼甲", "warframes", "/Lotus/Powersuits/Voruna/Voruna"),
    ("马娘", "warframes", "/Lotus/Powersuits/Dagath/Dagath"),         # Dagath
    ("鬼甲", "warframes", "/Lotus/Powersuits/Sevagoth/Sevagoth"),     # Sevagoth
    ("死鬼", "warframes", "/Lotus/Powersuits/Sevagoth/Sevagoth"),
    ("鲨鱼辣椒", "warframes", "/Lotus/Powersuits/Sevagoth/Sevagoth"),
    ("水晶甲", "warframes", "/Lotus/Powersuits/Citrine/Citrine"),     # Citrine
    ("斯巴达", "warframes", "/Lotus/Powersuits/Styanax/Styanax"),     # Styanax
    ("电妹", "warframes", "/Lotus/Powersuits/Gyre/Gyre"),             # Gyre
    ("药水哥", "warframes", "/Lotus/Powersuits/Railjack/Railjack"),   # Lavos
    ("蛇甲", "warframes", "/Lotus/Powersuits/Railjack/Railjack"),
    ("老九", "warframes", "/Lotus/Powersuits/Cyte09/Cyte09"),         # Cyte-09
    ("水妹", "warframes", "/Lotus/Powersuits/Yareli/Yareli"),         # Yareli
    ("鸭梨", "warframes", "/Lotus/Powersuits/Yareli/Yareli"),
    # ---- 常用术语/物品 ----
    ("土豆", "resources", "/Lotus/Types/Items/MiscItems/OrokinReactor"),
    ("金土豆", "resources", "/Lotus/Types/Items/MiscItems/OrokinReactor"),
    ("银土豆", "resources", "/Lotus/Types/Items/MiscItems/OrokinCatalyst"),
    ("福马", "resources", "/Lotus/Types/Items/MiscItems/Forma"),
    ("核桃", "resources", "/Lotus/Types/Game/Projections/T1VoidProjectionA"),  # 泛指遗物
    ("紫卡", "upgrades", "/Lotus/Upgrades/Mods/Randomized/"),  # 泛指裂罅
    ("BP", "recipes", "/Lotus/Types/Recipes/"),  # 泛指蓝图
    ("豆子", "resources", "/Lotus/Types/Items/MiscItems/FocusLensGreater"),
    ("传核", "resources", "/Lotus/Types/Items/MiscItems/LegendaryCore"),
    ("夜明珠", "resources", "/Lotus/Types/Items/MiscItems/LegendaryCore"),
    # ---- 赤毒/帕尔沃斯玄骸 ----
    ("AV男", "enemies", "/Lotus/Types/Enemies/Corpus/Leaders/AladV"),
    ("C系玄骸", "enemies", "/Lotus/Types/Enemies/Corpus/SistersOfParvos/"),  # 泛指
    ("大黑", "enemies", "/Lotus/Types/Enemies/Stalker/StalkerShadow"),
    ("小黑", "enemies", "/Lotus/Types/Enemies/Stalker/Stalker"),
    ("快递员", "enemies", "/Lotus/Types/Enemies/Stalker/Stalker"),
    # ---- 头目 ----
    ("火将军", "enemies", "/Lotus/Types/Enemies/Grineer/GrineerBosses/SargasRuk"),
    ("大鱼鹰", "enemies", "/Lotus/Types/Enemies/Corpus/CorpusBosses/Raptor"),
    ("骚话王", "enemies", "/Lotus/Types/Enemies/Grineer/GrineerBosses/TylRegor"),
    # ---- 集团 ----
    ("大黄脸", "syndicates", "/Lotus/Types/Syndicates/Library/SimarisSyndicate"),
    # ---- 虚空商人 ----
    ("奸商", "syndicates", "/Lotus/Types/Syndicates/VoidTrader/VoidTraderSyndicate"),
]

def load_default_aliases(w):
    """写入常用别名（幂等 upsert）。"""
    rows = [(a, t, eid) for a, t, eid in DEFAULT_ALIASES]
    w.upsert("aliases", "alias, entity_type, entity_id", rows,
             conflict_cols=["alias", "entity_type", "entity_id"])
    print(f"[ok] aliases: {len(rows)} 条常用别名")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
LOADERS = [
    ("ExportAbilities.json", load_abilities),
    ("ExportAchievements.json", load_achievements),
    ("ExportArcanes.json", load_arcanes),
    ("ExportAvionics.json", load_avionics),
    ("ExportBoosterPacks.json", load_booster_packs),
    ("ExportBundles.json", load_bundles),
    ("ExportCustoms.json", load_customs),
    ("ExportDrones.json", load_drones),
    ("ExportEnemies.json", load_enemies),
    ("ExportFlavour.json", load_flavour),
    ("ExportFocusUpgrades.json", load_focus_upgrades),
    ("ExportFusionBundles.json", load_fusion_bundles),
    ("ExportGear.json", load_gear),
    ("ExportImages.json", load_images),
    ("ExportIntrinsics.json", load_intrinsics),
    ("ExportKeys.json", load_keys),
    ("ExportMisc.json", load_misc),
    ("ExportModSet.json", load_mod_sets),
    ("ExportNightwave.json", load_nightwave),
    ("ExportRailjackWeapons.json", load_railjack_weapons),
    ("ExportRecipes.json", load_recipes),
    ("ExportRegions.json", load_regions),
    ("ExportRelics.json", load_relics),
    ("ExportResources.json", load_resources),
    ("ExportRewards.json", load_rewards),
    ("ExportSentinels.json", load_sentinels),
    ("ExportSyndicates.json", load_syndicates),
    ("ExportTextIcons.json", load_text_icons),
    ("ExportUpgrades.json", load_upgrades),
    ("ExportVirtuals.json", load_virtuals),
    ("ExportWarframes.json", load_warframes),
    ("ExportWeapons.json", load_weapons),
]


def extract_tables():
    """从 sql/init.sql 提取全部表名（保证与 schema 一致）。"""
    init_path = os.path.join(HERE, "sql", "init.sql")
    if not os.path.exists(init_path):
        raise SystemExit("[error] 未找到 sql/init.sql")
    tables = re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?public\.(\w+)", open(init_path, encoding="utf-8").read())
    if not tables:
        raise SystemExit("[error] init.sql 中未找到 CREATE TABLE")
    return tables


def main():
    ap = argparse.ArgumentParser(description="拉取 warframe 数据并生成数据导入 SQL（import.sql）")
    ap.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="数据文件目录（默认 temp/export-data/）")
    ap.add_argument("--langs", default="zh", help="要导入的字典语言，逗号分隔（默认 zh）")
    ap.add_argument("--fetch", action="store_true", help="先从 GitHub 拉取最新数据文件")
    ap.add_argument("--force-fetch", action="store_true", help="--fetch 时强制重新下载全部文件")
    ap.add_argument("--mirror", default=os.environ.get("GH_MIRROR", "https://v6.gh-proxy.org/"),
                    help="GitHub 代理前缀（默认 ghproxy，置空走直连）")
    ap.add_argument("--keep-data", action="store_true", help="保留下载的临时数据文件（默认删除）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出 SQL 路径（默认 ./import.sql）")
    ap.add_argument("--no-clean", action="store_true",
                    help="不在 SQL 中清空数据（默认每次导入先 TRUNCATE 全部表）")
    args = ap.parse_args()

    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    bad = [l for l in langs if l not in LANG_CODES]
    if bad:
        ap.error(f"不支持的语言代码: {bad}（支持: {','.join(LANG_CODES)}）")

    fetched = []
    if args.fetch:
        fetched, skipped = fetch_data(args.data_dir, langs, args.mirror, args.force_fetch)
        print(f"[fetch] 新下载 {len(fetched)} 个文件，跳过已有 {len(skipped)} 个")

    tables = extract_tables()
    with open(args.out, "w", encoding="utf-8") as f:
        w = SQLWriter(f)
        f.write("-- ============================================================================\n"
                "-- warframe 数据导入 SQL（由 load.py 生成）\n"
                f"-- 语言: {','.join(langs)}    生成时间: "
                f"{__import__('datetime').datetime.now().isoformat(timespec='seconds')}\n"
                "-- 用法: psql -U <user> -d <db> -f import.sql\n"
                "-- ============================================================================\n\n"
                "BEGIN;\n"
                "SET client_encoding = 'UTF8';\n"
                "SET standard_conforming_strings = on;\n\n")

        if not args.no_clean:
            f.write("-- 1) 清理所有数据（每次导入先清空全部表）\n"
                    "TRUNCATE TABLE " + ", ".join(f"public.{t}" for t in tables)
                    + " RESTART IDENTITY CASCADE;\n\n")

        import csv as _csv
        csv_path = os.path.join(args.data_dir, "languages.csv")
        lang_rows = []
        if os.path.exists(csv_path):
            with open(csv_path, encoding="utf-8") as cf:
                for r in _csv.DictReader(cf):
                    lang_rows.append((r["code"], r["native name"], r["english name"]))
        else:
            lang_rows = [("en", "English", "English"), ("de", "Deutsch", "German"),
                         ("es", "Español", "Spanish"), ("fr", "Français", "French"),
                         ("it", "Italiano", "Italian"), ("ja", "日本語", "Japanese"),
                         ("ko", "한국어", "Korean"), ("pl", "Polski", "Polish"),
                         ("pt", "Português", "Portuguese"), ("ru", "Русский", "Russian"),
                         ("tr", "Türkçe", "Turkish"), ("uk", "Українська", "Ukrainian"),
                         ("zh", "简体中文", "Simplified Chinese"), ("tc", "繁體中文", "Traditional Chinese"),
                         ("th", "แบบไทย", "Thai")]
        f.write("-- 2) 语言参考表\n")
        w.copy("languages", "code, native_name, english_name", lang_rows)
        f.write("\n")

        f.write(f"-- 3) 本地化字典（langs={','.join(langs)}）\n")
        for lang in langs:
            rows = [(tag, lang, val) for tag, val in load_json(args.data_dir, f"dict.{lang}.json").items()]
            w.copy("localizations", "loc_tag, lang, value", rows)
        f.write("\n")

        f.write("-- 4) 实体数据（33 个 Export 文件）\n")
        summary = []

        # 4.0) 枚举映射：ExportFactions/ExportMissionTypes → worldstate_enums，
        #      并用于补全 ExportRegions 的 faction_name_loc（FC_* → loc tag）
        f_data = m_data = None
        for fname in ("ExportFactions.json", "ExportMissionTypes.json"):
            path = os.path.join(args.data_dir, fname)
            if not os.path.exists(path):
                print(f"[skip] 缺少 {fname}")
                continue
            d = load_json(args.data_dir, fname)
            if fname == "ExportFactions.json":
                f_data = d
                _FACTION_TAGS.update({code: v.get("name") for code, v in d.items()})
            else:
                m_data = d
                _MISSION_TAGS.update({code: v.get("name") for code, v in d.items()})
            print(f"[ok] {fname}")
        if f_data is not None or m_data is not None:
            load_worldstate_enums(f_data or {}, m_data or {}, w)
            summary.append(("ExportFactions/MissionTypes", (len(f_data or {}) + len(m_data or {}))))

        for fname, fn in LOADERS:
            path = os.path.join(args.data_dir, fname)
            if not os.path.exists(path):
                print(f"[skip] 缺少 {fname}")
                continue
            data = load_json(args.data_dir, fname)
            before = dict(w.counts)
            fn(data, w)
            n = sum(w.counts.get(t, 0) - before.get(t, 0) for t in w.counts)
            summary.append((fname, n))
            print(f"[ok] {fname}")
        f.write("\n")

        # 4.9) abilities 汇总写库（ExportAbilities + 战甲内嵌技能，按 unique_name 去重）
        w.copy("abilities", "unique_name, name_loc, description_loc, icon, "
                            "energy_required_to_activate, energy_consumption_over_time",
               _ABILITY_ROWS)
        w.copy("warframe_abilities", "warframe_unique_name, ability_unique_name, slot",
               _WARFRAME_ABILITY_ROWS)
        f.write("\n")

        # 4.95) warframe.market 物品数据
        f.write("-- 6) warframe.market 物品数据\n")
        load_wfm_items(w, langs)
        f.write("\n")

        # 4.96) 常用别名
        f.write("-- 7) 常用别名\n")
        load_default_aliases(w)
        f.write("\n")

        f.write("-- 8) 导入来源元信息\n")
        w.copy("export_sources", "file_name, record_count, source_commit",
               [(fname, n, "github-master") for fname, n in summary])

        f.write("\nCOMMIT;\n")

    print(f"\n完成: {args.out}（{os.path.getsize(args.out) / 1024 / 1024:.1f} MB）")
    for fname, n in summary:
        print(f"  {fname}: {n} 行")

    if fetched and not args.keep_data:
        removed = 0
        for fn in fetched:
            local = os.path.join(args.data_dir, os.path.basename(fn))
            try:
                os.remove(local)
                removed += 1
            except OSError:
                pass
        print(f"[cleanup] 已删除 {removed} 个下载的临时数据文件（--keep-data 可保留）")
        if removed == len(fetched) and os.path.isdir(args.data_dir) and not os.listdir(args.data_dir):
            os.rmdir(args.data_dir)


if __name__ == "__main__":
    main()
