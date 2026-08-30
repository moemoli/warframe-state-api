"""JSON → view-model 裁剪 / 相对时间 / 纯文本降级排版。

约定：每个 vm_xxx 返回
{
  "title": str,
  "lines": [str, ...],          # 纯文本降级用（已排好序的完整行）
  "items": [...],               # 分页用条目（可缺省）
  **模板需要的结构化字段**
}
"""

from __future__ import annotations

from datetime import datetime, timezone

import aiohttp  # noqa: F401  (保持依赖提示)

# ---------------------------------------------------------------------------
# 时间工具
# ---------------------------------------------------------------------------

def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def rel_time(iso: str | None, now: datetime | None = None) -> str:
    dt = _parse_iso(iso)
    if not dt:
        return "—"
    now = now or datetime.now(timezone.utc)
    delta = (dt - now).total_seconds()
    future = delta >= 0
    m = abs(int(delta)) // 60
    if m < 1:
        return f"{abs(int(delta))}秒后" if future else "刚刚结束"
    if m < 60:
        return f"{m}分钟后" if future else f"{m}分钟前结束"
    h = m // 60
    if h < 24:
        return f"{h}小时{m % 60}分后" if future else f"{h}小时前结束"
    d = h // 24
    return f"{d}天后" if future else f"{d}天前结束"


def remain_between(act: str | None, exp: str | None) -> str:
    exp_dt = _parse_iso(exp)
    act_dt = _parse_iso(act) or datetime.now(timezone.utc)
    if not exp_dt:
        return "—"
    now = datetime.now(timezone.utc)
    if act_dt and now < act_dt:
        return f"{rel_time(act)}开始"
    return rel_time(exp)


# ---------------------------------------------------------------------------
# 内部小工具
# ---------------------------------------------------------------------------

def _name(obj) -> str:
    """resolved_json {code,name} 或 {type,name} → 显示名。"""
    if not isinstance(obj, dict):
        return obj if isinstance(obj, str) else "—"
    for k in ("name",):
        v = obj.get(k)
        if v:
            return str(v)
    t = obj.get("type")
    return str(t) if t else "—"


def _reward_line(reward) -> str:
    if not reward or not isinstance(reward, list):
        return "—"
    parts = []
    for r in reward[:4]:
        n = r.get("item_name") or r.get("type") or "?"
        cnt = r.get("item_count")
        parts.append(f"{n}×{cnt}" if isinstance(cnt, int) and cnt > 1 else str(n))
    extra = len(reward) - 4
    line = "、".join(parts)
    return f"{line}（+{extra}）" if extra > 0 else line


def _vm(title: str, items: list | None = None, lines: list[str] | None = None, **extra):
    vm = {"title": title, "lines": lines or [], **extra}
    if items is not None:
        vm["items"] = items
    return vm


def _finish(title: str, rows: list[tuple[str, ...]], header: tuple[str, ...] | None = None,
            items: list | None = None, notes: list[str] | None = None):
    lines = []
    if header:
        lines.append(" | ".join(header))
    for row in rows:
        lines.append(" | ".join(str(c) for c in row))
    for n in notes or []:
        lines.append(n)
    return _vm(title, items=items, lines=lines)


# ---------------------------------------------------------------------------
# 世界状态各节
# ---------------------------------------------------------------------------

def vm_alerts(data) -> dict:
    alerts = data.get("alerts") or []
    rows, items = [], []
    for a in alerts:
        m = a.get("mission") or {}
        node = _name(m.get("node"))
        mt = _name(m.get("mission_type"))
        fac = _name(m.get("faction"))
        lvl = m.get("enemy_levels") or {}
        lv = f"{lvl.get('min','?')}-{lvl.get('max','?')}"
        rw = _reward_line(m.get("reward"))
        left = remain_between(a.get("activation"), a.get("expiry"))
        rows.append((node, mt, fac, lv, rw, left))
        items.append({"node": node, "mission_type": mt, "faction": fac,
                      "levels": lv, "reward": rw, "left": left})
    return _finish(f"警报 · {len(alerts)} 条", rows,
                   ("节点", "类型", "派系", "等级", "奖励", "剩余"), items)


def vm_fissures(data, steel_only=False) -> dict:
    fis = data.get("fissures") or []
    if steel_only:
        fis = [f for f in fis if f.get("hard")]
    rows, items = [], []
    for f in fis:
        tier = _name(f.get("modifier")) if f.get("modifier") else "?"
        node = _name(f.get("node"))
        mt = _name(f.get("mission_type"))
        hard = "钢铁" if f.get("hard") else ""
        left = remain_between(f.get("activation"), f.get("expiry"))
        rows.append((tier + hard, node, mt, left))
        items.append({"tier": tier, "node": node, "mission_type": mt,
                      "hard": bool(f.get("hard")), "left": left})
    title = f"钢铁裂缝 · {len(fis)} 条" if steel_only else f"虚空裂缝 · {len(fis)} 条"
    return _finish(title, rows, ("纪元", "节点", "类型", "剩余"), items)


def vm_sortie(data) -> dict:
    s = data if isinstance(data, dict) else {}
    boss = _name(s.get("boss"))
    variants = s.get("variants") or []
    rows, items = [], []
    for i, v in enumerate(variants, 1):
        node = _name(v.get("node"))
        mt = _name(v.get("mission_type"))
        mod = v.get("modifier_type")
        mod = mod if isinstance(mod, str) else _name(mod)
        rows.append((f"{i}", node, mt, mod))
        items.append({"idx": i, "node": node, "mission_type": mt, "modifier": mod})
    reward = s.get("reward") or {}
    rw = reward.get("deck_name", "")
    vm = _finish(f"突击 · {boss}", rows, ("#", "节点", "类型", "修正"),
                   items, notes=[f"奖励池：{rw}" if rw else "",
                                 f"结束：{rel_time(s.get('expiry'))}"])
    vm["boss"] = boss
    vm["expiry_rel"] = rel_time(s.get("expiry"))
    return vm


def vm_lite(data) -> dict:
    """LiteSorties（执刑官猎杀）透传节。"""
    arr = data if isinstance(data, list) else (data or {}).get("liteSorties") or []
    rows, items = [], []
    for ls in arr[:2]:
        boss = _name(ls.get("boss")) if isinstance(ls.get("boss"), dict) else (ls.get("boss") or "?")
        for i, m in enumerate(ls.get("missions") or [], 1):
            node = _name(m.get("node"))
            mt = _name(m.get("mission_type"))
            rows.append((boss, node, mt))
            items.append({"boss": boss, "node": node, "mission_type": mt})
    return _finish("执刑官猎杀", rows, ("Boss", "节点", "类型"), items)


def vm_invasions(data) -> dict:
    invs = [i for i in (data.get("invasions") or []) if not i.get("completed")]
    rows, items = [], []
    for inv in invs:
        node = _name(inv.get("node"))
        atk, dfn = inv.get("attacker") or {}, inv.get("defender") or {}
        afac, dfac = _name(atk.get("faction")), _name(dfn.get("faction"))
        arw, drw = _reward_line(atk.get("reward")), _reward_line(dfn.get("reward"))
        goal = inv.get("goal") or 1
        pct = int(max(0, min(100, 50 + 50 * (inv.get("count") or 0) / goal)))
        left = remain_between(inv.get("activation"), None)
        rows.append((node, f"{afac} vs {dfac}", f"{pct}%", drw, arw))
        items.append({"node": node, "matchup": f"{afac} vs {dfac}",
                      "progress": pct, "defender_reward": drw, "attacker_reward": arw})
    return _finish(f"入侵 · {len(invs)} 场", rows,
                   ("节点", "对阵", "进度", "守方奖励", "攻方奖励"), items)


def vm_void_trader(data) -> dict:
    vt = (data.get("void_trader") or {}) or {}
    char = _name(vt.get("character")) or "Baro Ki'Teer"
    loc = _name(vt.get("node"))
    act, exp = vt.get("activation"), vt.get("expiry")
    manifest = vt.get("manifest") or []
    status = vt.get("status") or ("absent" if not act else "present")
    arrival_dt = _parse_iso(act)

    if not act:
        vm = _finish(f"{char}", [], notes=["当前无 Baro 数据，稍后查询"])
        vm["arrival"] = ""
        vm["leave"] = ""
        return vm

    arrived = arrival_dt and arrival_dt.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)
    arrival_txt = "已到达" if arrived else f"{rel_time(act)}到达"

    if not manifest or status == "absent":
        msg = f"虚空商人 {char} 将在 {rel_time(act)}到达 {loc}"
        vm = _finish(f"{char}", [], notes=[msg])
        vm["arrival"] = arrival_txt
        vm["leave"] = rel_time(exp)
        return vm

    rows, items = [], []
    for it in manifest:
        nm = it.get("item_name") or it.get("name") or "?"
        pp, rp = it.get("prime_price"), it.get("regular_price")
        rows.append((nm, f"{pp}杜+{rp}星币" if rp is not None else f"{pp}杜"))
        items.append({"name": nm, "ducats": pp, "credits": rp})
    vm = _finish(f"{char} · {loc}",
                   rows, ("物品", "价格"),
                   items,
                   notes=[f"{arrival_txt}，{rel_time(exp)}离开"])
    vm["arrival"] = arrival_txt
    vm["leave"] = rel_time(exp)
    return vm


def vm_daily_deals(data) -> dict:
    deals = data.get("daily_deals") or []
    rows, items = [], []
    for d in deals:
        nm = d.get("item_name") or "?"
        disc = d.get("discount", 0)
        sp, op = d.get("sale_price"), d.get("original_price")
        total, sold = d.get("amount_total"), d.get("amount_sold")
        rows.append((nm, f"-{disc}%", f"{sp}p(原{op})", f"{sold}/{total}"))
        items.append({"name": nm, "discount": disc, "sale_price": sp,
                      "original_price": op, "sold": sold, "total": total})
    return _finish(f"Darvo 特惠 · {len(deals)} 条", rows,
                   ("物品", "折扣", "现价", "库存"), items)



_CONQUEST_TITLE = {
    "CT_LAB": "深层科研",
    "CT_HEX": "时光科研",
}

def vm_conquests(data, filter_type: str | None = None) -> dict:
    """科研任务。filter_type: CT_LAB/CT_HEX，None=全部。"""
    cqs = data.get("conquests") or []
    groups = []
    for cq in cqs:
        cq_type = cq.get("type", "")
        if filter_type and cq_type != filter_type:
            continue
        type_zh = _CONQUEST_TITLE.get(cq_type, cq.get("type_zh") or cq_type)
        rows = []
        for m in cq.get("missions", []):
            mt = m.get("mission_type_zh") or m.get("mission_type", "?")
            fac = m.get("faction_zh") or m.get("faction", "?")
            normal = next((d for d in m.get("difficulties", []) if d.get("type") == "CD_NORMAL"), None)
            hard = next((d for d in m.get("difficulties", []) if d.get("type") == "CD_HARD"), None)
            dev_zh = (normal or {}).get("deviation_zh") or (normal or {}).get("deviation", "")
            dev_desc = (normal or {}).get("deviation_desc") or ""
            risks_zh = (normal or {}).get("risks_zh") or []
            # risks_zh 现在是 [{name, desc}] 对象列表
            risks_with_desc = [{"zh": r.get("name", r) if isinstance(r, dict) else r,
                                "desc": r.get("desc", "") if isinstance(r, dict) else ""} for r in risks_zh]
            hard_risks_zh = (hard or {}).get("risks_zh") or []
            hard_risk_names = {(r.get("name") if isinstance(r, dict) else r) for r in hard_risks_zh}
            normal_risk_names = {(r.get("name") if isinstance(r, dict) else r) for r in risks_zh}
            extra = [r for r in hard_risks_zh if (r.get("name") if isinstance(r, dict) else r) not in normal_risk_names]
            extra_with_desc = [{"zh": r.get("name", r) if isinstance(r, dict) else r,
                                "desc": r.get("desc", "") if isinstance(r, dict) else ""} for r in extra]
            rows.append({
                "mission": mt, "faction": fac,
                "deviation": dev_zh, "dev_desc": dev_desc,
                "risks": risks_with_desc,
                "elite_extra": extra_with_desc,
            })
        variables = cq.get("variables") or []
        groups.append({"type_zh": type_zh, "rows": rows, "variables": variables})
    title = " · ".join(g["type_zh"] for g in groups) if groups else "科研任务"
    return {"title": title, "groups": groups, "lines": [], "items": []}



def vm_nightwave(data) -> dict:
    nw = data.get("nightwave") or {}
    chals = nw.get("challenges") or []
    rows, items = [], []
    for c in chals:
        nm = c.get("name") or "?"
        st = c.get("standing", "")
        rows.append((nm, str(st)))
        items.append({"name": nm, "standing": st, "description": c.get("description")})
    title = _name(nw.get("affiliation_tag")) or "午夜电波"
    return _finish(f"{title} 挑战 · {len(chals)} 条", rows, ("挑战", "声望"), items)



def vm_nightwave_tasks(data) -> dict:
    """午夜电波任务（按日/周/精英分类）。"""
    nw = data.get("nightwave") or {}
    chals = nw.get("challenges") or []
    tag = _name(nw.get("affiliation_tag")) or "午夜电波"

    daily, weekly, elite = [], [], []
    for c in chals:
        st = c.get("standing", 0) or 0
        item = {"name": c.get("name") or "?", "standing": st,
                "description": c.get("description") or "",
                "required": bool(c.get("required"))}
        if st <= 2500:
            daily.append(item)
        elif st <= 4500:
            weekly.append(item)
        else:
            elite.append(item)

    return {"title": f"{tag}", "season": tag,
            "daily": daily, "weekly": weekly, "elite": elite,
            "lines": [], "items": []}



def vm_news(data) -> dict:
    news = data.get("events") or data.get("news") or []
    rows, items = [], []
    for n in news[:15]:
        nm = _name(n) if isinstance(n, str) else (
            (n.get("messages") or [{}])[0].get("message") or n.get("name") or "?")
        when = rel_time(n.get("date") or n.get("activation"))
        rows.append((when, nm))
        items.append({"title": nm, "when": when})
    return _finish(f"新闻 · {min(len(news),15)} 条", rows, ("时间", "标题"), items)


def vm_goals(data) -> dict:
    goals = data.get("goals") or []
    rows, items = [], []
    for g in goals:
        nm = g.get("name") or "?"
        desc = (g.get("tooltip") or g.get("description") or "")[:60]
        rows.append((nm, desc, remain_between(g.get("activation"), g.get("expiry"))))
        items.append({"name": nm, "desc": desc})
    return _finish(f"活动 · {len(goals)} 个", rows, ("活动", "说明", "时间"), items)


def vm_descents(data) -> dict:
    ds = data.get("descents") or []
    items = []
    idx = 0
    for d in ds:
        for c in (d.get("challenges") or []):
            idx += 1
            floor = c.get("index") or idx
            tn = c.get("type_name") or c.get("type") or "?"
            td = c.get("type_desc") or ""
            cn = c.get("challenge_name") or c.get("challenge") or ""
            cd = c.get("challenge_desc") or ""
            auras = "、".join(a.get("name") or "" for a in (c.get("auras") or []) if isinstance(a, dict))
            items.append({"index": floor, "type_name": tn, "type_desc": td,
                          "challenge_name": cn, "challenge_desc": cd, "auras": auras})
    return {"title": f"沉沦之地 · {idx} 层", "items": items, "lines": []}


def vm_calendar(data) -> dict:
    seasons = data.get("knownCalendarSeasons") or (data.get("known_calendar_seasons") or [])
    out_notes, items = [], []
    for s in seasons[:1]:
        days = s.get("days") or []
        for day in days[:7]:
            evs = day.get("events") or []
            for e in evs:
                et = e.get("type") or ""
                nm = _name(e.get("challenge") or e.get("reward") or e.get("upgrade") or e.get("day"))
                out_notes.append(f"{et}: {nm}")
                items.append({"type": et, "name": nm})
    return _finish("1999 日历（近期）", [], items=items, notes=out_notes[:20])


def vm_cycles(data) -> dict:
    cyc = data.get("cycles") or []
    rows, items = [], []
    for c in cyc:
        nm = c.get("name_zh") or c.get("name") or "?"
        state = c.get("state_name") or c.get("state") or "?"
        rem = c.get("remaining") or ""
        rows.append((nm, state, rem))
        items.append({"name": nm, "state": state, "remaining": rem,
                      "expiry_iso": c.get("expiry")})
    return _finish("世界循环", rows, ("地区", "状态", "剩余"), items)


def vm_arbitrations(data) -> dict:
    latest = data.get("latest")
    sched = ((data.get("schedule") or {}).get("entries")) or []
    rows, items = [], []
    def one(e, tag):
        node = (e.get("node") or {})
        nm = node.get("name", "?")
        sysm = (node.get("system") or {}).get("name", "")
        mt = e.get("mission_type", "")
        lv = e.get("enemy_levels") or {}
        return {"node": nm, "system": sysm, "mission_type": mt,
                "levels": f"{lv.get('min','?')}-{lv.get('max','?')}"},
    if latest:
        vm, _x = one(latest, 0)
        items.append(vm); rows.append(("当前", vm["node"], vm["system"], vm["mission_type"], vm["levels"]))
    for e in sched:
        vm, _x = one(e, 0)
        items.append(vm)
        rows.append((e.get("activation", "")[11:16], vm["node"], vm["system"], vm["mission_type"], vm["levels"]))
    return _finish("仲裁轮换", rows, ("", "节点", "星球", "类型", "等级"), items)


def vm_persistent(data) -> dict:
    pes = data.get("persistent_enemies") or []
    rows, items = [], []
    for p in pes:
        agent = _name(p.get("agent_type")) if isinstance(p.get("agent_type"), dict) else (p.get("agent_type") or "?")
        loc = p.get("last_discovered_location") or "?"
        hp = p.get("health_percent", "?")
        rows.append((agent, loc, f"{hp}%"))
        items.append({"agent": agent, "location": loc, "hp": hp})
    return _finish(f"追随者 · {len(pes)} 个", rows, ("目标", "最后出现", "生命"), items)


# ---------------------------------------------------------------------------
# 资料/市场
# ---------------------------------------------------------------------------

def _source_badge(src: str) -> str:
    return {"alias": "别名", "official": "官方", "wfm": "WM",
            "riven": "紫卡", "lich": "赤毒", "sister": "信条"}.get(src, src or "?")


def vm_search(data) -> dict:
    results = data.get("results") or []
    rows, items = [], []
    for r in results:
        wfm = r.get("wfm") or {}
        slug = wfm.get("slug") if isinstance(wfm, dict) else None
        wiki = wfm.get("wiki_link") if isinstance(wfm, dict) else None
        rows.append((_source_badge(r.get("source")), r.get("entity_type", ""),
                     r.get("name", ""), slug or ""))
        items.append({"source": r.get("source"), "badge": _source_badge(r.get("source")),
                      "entity_type": r.get("entity_type"), "name": r.get("name"),
                      "slug": slug, "wiki": wiki, "tradable": bool(wfm)})
    return _finish(f"搜索「{data.get('query','')}」· {len(results)} 条",
                   rows, ("来源", "类型", "名称", "slug"), items)


def vm_wiki(data) -> dict:
    results = data.get("results") or []
    for r in results:
        wfm = r.get("wfm") or {}
        wiki = wfm.get("wiki_link") if isinstance(wfm, dict) else None
        if wiki:
            return _finish(f"Wiki · {r.get('name')}", [],
                           items=[{"name": r.get("name"), "wiki": wiki}],
                           notes=[wiki])
    return _finish("Wiki", [], notes=["未找到含 Wiki 链接的结果"])


def vm_drops(data) -> dict:
    drops = data.get("drops") or []
    groups: dict[str, list] = {}
    for d in drops:
        groups.setdefault(d.get("source_type", "other"), []).append(
            (d.get("source") or d.get("source_name") or "?",
             d.get("chance"), d.get("item_count")))
    names = {"mission_reward": "任务奖励表", "enemy_droptable": "敌人掉落",
             "recipe_ingredient": "作为配方原料", "recipe_result": "作为配方产物",
             "bundle": "组合包"}
    lines, items = [], []
    for st, lst in groups.items():
        lines.append(f"— {names.get(st, st)} —")
        for src, chance, cnt in lst[:6]:
            c = f" {chance*100:.2f}%" if isinstance(chance, (int, float)) else ""
            lines.append(f"  {src}{c}")
            items.append({"source_type": st, "source": src, "chance": chance})
    item = data.get("item") or {}
    return _finish(f"掉落 · {item.get('name','?')}", [], items=items, notes=lines)


def vm_wm_price(data) -> dict:
    prices = data.get("prices") or {}
    sell = (prices.get("sell") or {})
    buy = (prices.get("buy") or {})
    so, bo = sell.get("orders") or [], buy.get("orders") or []

    # 排序：在线优先 → 价格排序（卖低到高 / 买高到低）
    _status_rank = {"ingame": 0, "online": 1, "offline": 2}
    so = sorted(so, key=lambda o: (_status_rank.get(o.get("status", ""), 9), o.get("platinum", 9999)))
    bo = sorted(bo, key=lambda o: (_status_rank.get(o.get("status", ""), 9), -o.get("platinum", 0)))

    lines = [
        f"最低卖 {sell.get('min','-')}p · 均 {sell.get('avg','-')}p · 最高收 {buy.get('max','-')}p",
        "— 卖单 —",
    ]
    for o in so[:5]:
        st = {"ingame": "🟢", "online": "🟡"}.get(o.get("status"), "⚫")
        lines.append(f"  {st} {o.get('platinum')}p ×{o.get('quantity')} {o.get('user')}")
    lines.append("— 买单 —")
    for o in bo[:5]:
        st = {"ingame": "🟢", "online": "🟡"}.get(o.get("status"), "⚫")
        lines.append(f"  {st} {o.get('platinum')}p ×{o.get('quantity')} {o.get('user')}")
    items = [{"sell_min": sell.get("min"), "sell_avg": sell.get("avg"),
              "buy_max": buy.get("max"), "sell_orders": so, "buy_orders": bo}]
    vm = _finish(f"WM · {data.get('item_name') or data.get('slug','?')}",
                   [], items=items, notes=[data.get("description","")[:80]] + [""] + lines)
    # 提升到顶层供模板直接访问
    vm["desc"] = data.get("description", "")[:120]
    vm["sell_min"] = sell.get("min")
    vm["sell_avg"] = sell.get("avg")
    vm["buy_max"] = buy.get("max")
    vm["sell_orders"] = so
    vm["buy_orders"] = bo
    return vm


def vm_rivens_list(data) -> dict:
    items = data.get("items") or []
    rows = [(it.get("item_name") or it.get("slug"),
             it.get("riven_type"), it.get("disposition"), it.get("mastery_level"))
            for it in items]
    return _finish(f"紫卡武器 · {len(items)} 把",
                   rows, ("武器", "类型", "倾向", "段位"),
                   items=[{"name": r[0], "type": r[1], "disp": r[2], "mastery": r[3],
                           "slug": it.get("slug")} for r, it in zip(rows, items)])


def vm_attrs(data) -> dict:
    attrs = data.get("attributes") or []
    rows = [(a.get("effect") or a.get("slug"), f"{a.get('prefix') or ''}/{a.get('suffix') or ''}",
             a.get("group")) for a in attrs]
    return _finish(f"紫卡词条 · {len(attrs)} 种", rows, ("效果", "前缀/后缀", "类别"),
                   items=[{"effect": r[0], "affix": r[1], "group": r[2]} for r in rows])


def vm_auctions(data) -> dict:
    auctions = data.get("auctions") or []
    # 排序：在线优先 → 价格低到高
    _status_rank = {"ingame": 0, "online": 1, "offline": 2}
    auctions = sorted(auctions, key=lambda a: (
        _status_rank.get(a.get("status", ""), 9),
        a.get("price", 9999),
    ))
    rows, items = [], []
    for a in auctions[:15]:
        attrs = " ".join(
            ("负·" if x.get("negative") else "") + (x.get("name_zh") or x.get("name") or "?")
            for x in (a.get("attributes") or []))
        price = f"{a.get('price')}p" + ("" if a.get("buyout") else "(竞)")
        rows.append((price, f"R{a.get('rank')}", f"洗{a.get('rerolls')}", attrs[:40]))
        items.append({"price": a.get("price"), "buyout": a.get("buyout"),
                      "rank": a.get("rank"), "rerolls": a.get("rerolls"),
                      "status": a.get("status"), "owner": a.get("user"),
                      "attributes": a.get("attributes")})
    return _finish(f"紫卡拍卖 · {data.get('slug')} ({data.get('total')} 单)",
                   rows, ("价", "级", "洗", "词条"), items)


def vm_spread(data) -> dict:
    attrs = data.get("attributes") or []
    rows = [(a.get("attribute_zh") or a.get("attribute"), a.get("avg_price"), a.get("samples"))
            for a in attrs]
    return _finish(f"词条价差 · {data.get('slug')}（样本 {data.get('samples')}）",
                   rows, ("词条", "均价", "样本"),
                   items=[{"attr": r[0], "avg": r[1], "samples": r[2]} for r in rows])


def vm_trends(data) -> dict:
    src = data.get("source")
    lines = [f"数据源：{'WM官方统计' if src == 'wfm_statistics' else '本地快照'}"]
    items = []
    if src == "wfm_statistics":
        for rng in ("48h", "90d"):
            pts = ((data.get("data") or {}).get(rng)) or []
            if pts:
                last, first = pts[-1], pts[0]
                lines.append(f"[{rng}] 最新均价 {last.get('avg')}p（量 {last.get('volume')}），"
                             f"区间 {first.get('datetime','')[:10]} ~ {last.get('datetime','')[:10]}")
        items = (data.get("data") or {}).get("90d") or []
    else:
        for p in (data.get("points") or []):
            lines.append(f"{p['day']}: 卖低 {p.get('sell_min')}p / 均价 {p.get('sell_avg')}p / 收高 {p.get('buy_max')}p")
        items = data.get("points") or []
    return _finish(f"趋势 · {data.get('slug')}", [], items=items, notes=lines or ["暂无数据"])

# ── 赏金任务 ──

_BOUNTY_ZH = {
    # 开放世界赏金
    "CetusSyndicate":        ("夜灵平原", "希图斯", "cetus", "ostron"),
    "SolarisSyndicate":      ("金星", "福尔图娜", "solaris", "金星平原", "索拉里斯联盟"),
    "EntratiSyndicate":      ("火卫二", "火卫二平原", "deimos", "entrati", "英择谛"),
    "QuillsSyndicate":       ("夜羽", "quills"),
    "NecraloidSyndicate":    ("殁世械灵", "necraloid"),
    "KahlSyndicate":         ("卡尔", "卡尔营地", "kahl"),
    "ZarimanSyndicate":      ("坚守者", "扎里曼", "zariman"),
    "HexSyndicate":          ("六人组", "1999", "hex"),
    "EntratiLabSyndicate":   ("科维兽", "entrati_lab"),
    "VentKidsSyndicate":     ("通风小子", "ventkids"),
    "VoxSyndicate":          ("索拉里斯之声", "vox"),
    # 六人集团
    "ArbitersSyndicate":     ("均衡仲裁者", "仲裁者", "hexis"),
    "CephalonSudaSyndicate": ("中枢苏达", "苏达", "suda"),
    "NewLokaSyndicate":      ("新世间", "loka"),
    "PerrinSyndicate":       ("佩兰数列", "佩兰", "perrin"),
    "RedVeilSyndicate":      ("血色面纱", "redveil"),
    "SteelMeridianSyndicate": ("钢铁前线", "钢铁", "meridian"),
}
_BOUNTY_JOB_ZH = {
    "Sabotage": "破坏", "Assassinate": "暗杀", "Rescue": "救援",
    "Exterminate": "歼灭", "Capture": "捕获", "Survival": "生存",
    "Defense": "防御", "Excavation": "挖掘", "Spy": "间谍",
    "Attrition": "消耗战", "Cull": "清除", "Recovery": "回收",
    "Purify": "净化", "Gather": "采集", "KeyPieces": "钥匙碎片",
}


def _job_type_zh(jt: str) -> str:
    """从 job_type 路径提取中文任务类型。"""
    raw = jt.split('/')[-1]  # e.g. DeimosAssassinateBounty
    for eng, zh in _BOUNTY_JOB_ZH.items():
        if eng in raw:
            return zh
    return raw


def vm_bounties(data, org: str | None = None) -> dict:
    """赏金/集团任务数据。

    org: 可选，按组织筛选。
    返回 {title, items: [{tag, name, kind, jobs/nodes: [...]}]}
    """
    synd = data.get("syndicate_missions") or []

    # 按 tag 收集（去重：同一 tag 可能出现两次，取 jobs 多的那份）
    by_tag: dict[str, dict] = {}
    for s in synd:
        tag = s.get("tag", "")
        if not tag:
            continue
        jobs = s.get("jobs") or []
        nodes = s.get("nodes") or []
        existing = by_tag.get(tag)
        if not existing or len(jobs) > len(existing.get("jobs", [])):
            by_tag[tag] = {"tag": tag, "jobs": jobs, "nodes": nodes}

    # 筛选
    def match(tag: str) -> bool:
        if not org:
            return True
        q = org.lower()
        names = _BOUNTY_ZH.get(tag, ())
        return any(q in a.lower() for a in names) or q in tag.lower()

    items = []
    for tag, sdata in by_tag.items():
        if not match(tag):
            continue
        names = _BOUNTY_ZH.get(tag, (tag, tag))
        name_zh = names[0]
        jobs = sdata["jobs"]
        nodes = sdata["nodes"]

        if jobs:
            # 开放世界赏金
            job_items = []
            for j in jobs:
                jt = j.get("job_type", "").split("/")[-1]
                mn = j.get("min_enemy_level", 0)
                mx = j.get("max_enemy_level", 0)
                tiers = j.get("rewards", {}).get("tiers", [])
                rare_per_tier = []
                for t in tiers:
                    ti = t.get("tier", 0)
                    items_t = t.get("items") or []
                    rare = [i.get("item_name") or i.get("type", "").split("/")[-1]
                            for i in items_t
                            if i.get("probability", 0) < 0.2 and (i.get("item_name") or "").strip()]
                    if rare:
                        rare_per_tier.append({"tier": ti, "items": rare})
                job_items.append({
                    "type_zh": _job_type_zh(jt),
                    "type_raw": jt,
                    "lv": f"Lv{mn}-{mx}",
                    "rare": rare_per_tier,
                })
            items.append({"tag": tag, "name": name_zh, "kind": "bounty", "jobs": job_items, "nodes": []})
        elif nodes:
            # 集团日常任务（只有节点）
            items.append({"tag": tag, "name": name_zh, "kind": "daily", "jobs": [], "nodes": nodes})

    if org and not items:
        names_list = sorted(set(n[0] for n in _BOUNTY_ZH.values()))
        return {"title": f"未找到：{org}", "items": [],
                "lines": [f"可用组织：{'、'.join(names_list)}"]}

    title = "赏金任务" + (f" · {org}" if org else f" · {len(items)} 个组织")
    return {"title": title, "items": items, "lines": []}




def vm_components(data) -> dict:
    items = data.get("items") or []
    rows = [(it.get("item_name"), it.get("ducats"), it.get("trading_tax")) for it in items]
    return _finish(f"Prime 部件 · {data.get('tier','all')}",
                   rows, ("部件", "杜卡德", "税"),
                   items=[{"name": r[0], "ducats": r[1], "tax": r[2]} for r in rows])


def vm_rankings(data) -> dict:
    items = data.get("items") or []
    rows = [(f"#{x.get('rank')}", x.get("name") or x.get("entity_id"), x.get("hits")) for x in items]
    return _finish(f"热度排行 · {data.get('type')}", rows, ("名次", "名称", "查询次数"),
                   items=items)


def vm_synthesis(data) -> dict:
    by_target = data.get("by_target")
    if by_target:
        lines = [f"{k} → {'；'.join(v)}" for k, v in by_target.items()]
        items = [{"target": k, "locations": v} for k, v in by_target.items()]
        return _finish(f"结合目标 · {data.get('target_query')}", [], items=items, notes=lines)
    daily = data.get("daily") or []
    imprints = data.get("imprints") or []
    lines = []
    for d in daily:
        lines.append(f"{d['node']}（{d['system']}{d['mission']}）：{'、'.join(d['targets'])}")
    lines.append("")
    for i in imprints:
        lines.append(f"{i['target']} → {i['location']}")
    items = ([{"kind": "daily", **d} for d in daily] +
             [{"kind": "imprint", **i} for i in imprints])
    return _finish("结合仪式目标", [], items=items, notes=lines)


# ---------------------------------------------------------------------------
# 文本排版（降级输出）
# ---------------------------------------------------------------------------

def to_text(vm: dict, max_lines: int = 40, plain: bool = False) -> str:
    lines: list[str] = vm.get("lines") or []
    title = "" if plain else f"【{vm.get('title','')}】\n"
    body = "\n".join(lines)
    all_lines = body.split("\n")
    if len(all_lines) > max_lines:
        head = "\n".join(all_lines[:max_lines])
        total = vm.get("page_total") or len(all_lines)
        body = f"{head}\n……共 {total} 行，发送『-2』翻页"
    text = f"{title}{body}".strip() or "（空）"
    return text
