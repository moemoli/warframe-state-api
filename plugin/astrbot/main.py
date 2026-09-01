"""astrbot_plugin_warframe_helper —— warframe-api 聊天前端。

指令总览见 doc/plugin_implementation.md §4；本文件只做注册与分发，
业务裁剪在 formatter.py，出图在 renderer.py，订阅在 subscribe.py。
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .api_client import ApiClient, ApiError
from .formatter import (
    to_text, vm_alerts, vm_arbitrations, vm_attrs, vm_auctions, vm_bounties,
    vm_conquests,
    vm_calendar, vm_components, vm_cycles, vm_daily_deals, vm_descents, vm_drops,
    vm_fissures, vm_goals, vm_invasions, vm_lite, vm_news, vm_nightwave,
    vm_nightwave_tasks, vm_persistent, vm_rankings, vm_rivens_list, vm_search,
    vm_sortie, vm_spread, vm_synthesis, vm_trends, vm_void_storms, vm_void_trader, vm_wiki,
    vm_wm_price,
)
from .parser import Flags, PageCache, parse, paginate
from .renderer import Renderer
from .rotation import current_rotation
from .subscribe import ParseError, Poller, SubStore, parse_duration, parse_subscribe

try:
    from astrbot.api.message_components import At, Plain
except Exception:                                     # pragma: no cover
    At = Plain = None

PLUGIN_DIR = Path(__file__).parent
TEMPLATE_DIR = PLUGIN_DIR / "templates"

# ---------------------------------------------------------------------------
# 常量表
# ---------------------------------------------------------------------------

_CN_CMDS = {"cm", "cr", "rm", "交易"}

_UNSUPPORTED = {
    "配卡", "伤害模拟", "签到", "打卡", "黄历", "组队", "我的配卡", "我的配色",
    "文字识别", "截图翻译", "批量查价", "核桃", "紫卡分析", "模拟开卡",
    "抽奖", "射爆", "三线琴", "和弦琴", "教程", "在线翻译", "中翻英", "英翻中",
    "浮印", "热门紫卡", "紫卡价格",
}

WS_SECTIONS = {
    "alerts":   ("警报",   vm_alerts,   "alerts.html"),
    "sortie":   ("突击",   vm_sortie,   "sortie.html"),
    "liteSorties": ("猎杀", vm_lite,     "lite_sorties.html"),
    "invasions":("入侵",   vm_invasions,"invasions.html"),
    "fissures": ("裂隙",   vm_fissures, "fissures.html"),
    "void_trader": ("奸商", vm_void_trader, "voidtrader.html"),
    "daily_deals": ("特惠", vm_daily_deals, "daily_deals.html"),
    "nightwave": ("电波",  vm_nightwave,"nightwave.html"),
    "events":   ("新闻",   vm_news,     "news.html"),
    "goals":    ("活动",   vm_goals,    "goals.html"),
    "descents": ("恶魔塔", vm_descents, "descents.html"),
    "persistent_enemies": ("小小黑", vm_persistent, "generic.html"),
    "conquests": ("科研", vm_conquests, "conquests.html"),
}

ALIAS_TO_SECTION = {
    "警报": "alerts", "突击": "sortie", "猎杀": "liteSorties", "执刑官": "liteSorties",
    "入侵": "invasions", "裂隙": "fissures", "裂缝": "fissures",
    "奸商": "void_trader", "特惠": "daily_deals", "每日特惠": "daily_deals",
    "电波": "nightwave", "新闻": "events", "最近新闻": "events",
    "活动": "goals", "恶魔塔": "descents", "沉沦之地": "descents",
    "小小黑": "persistent_enemies",
}

WR_ATTR_ALIAS = {
    "基伤": "base_damage_/_melee_damage", "近战伤害": "base_damage_/_melee_damage",
    "暴率": "critical_chance", "暴伤": "critical_damage",
    "多重": "multishot", "触发": "status_chance",
    "冰": "cold_damage", "火": "heat_damage", "电": "electricity_damage",
    "毒": "toxin_damage", "C伤": "damage_to_corpus", "G伤": "damage_to_grineer",
    "I伤": "damage_to_infested", "攻速": "attack_speed", "装填": "reload_speed",
}
WR_POLARITY = {"r槽": "madurai", "-槽": "naramon", "角槽": "vazarin", "=槽": "zenurik"}

DUR_TOKEN_RE = re.compile(r"^\d+\s*(h|d|w|m|小时|天|周|月)$", re.I)
PRICE_RE = re.compile(r"^(\d+)p$", re.I)


def _after(event: AstrMessageEvent, words: list[str]) -> str:
    s = event.message_str.strip()
    if s.startswith("/"):
        s = s[1:].strip()
    low = s.lower()
    for w in sorted(words, key=len, reverse=True):
        wl = w.lower()
        if low == wl:
            return ""
        if low.startswith(wl):
            return s[len(w):].strip()
    return s


def _match_price(tok: str) -> int | None:
    m = PRICE_RE.match(tok)
    return int(m.group(1)) if m else None


@register(
    "astrbot_plugin_warframe_helper",
    "warframe-api",
    "星际战甲查询助手：世界状态/突击/裂缝/仲裁/循环/物品搜索/WM 价格/紫卡/赤毒/订阅推送。",
    "0.2.0",
)
class WarframePlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context, config)
        self.config = config or {}
        self.client: ApiClient | None = None
        self.renderer: Renderer | None = None
        self.pages = PageCache()
        self.store = SubStore()
        self.poller: Poller | None = None
        self.page_size = 8
        self.max_lines = 40
        self.default_lang = "zh"
        self._attr_map_cache: tuple[float, dict] | None = None

    async def initialize(self):
        cfg = getattr(self, "config", None) or {}
        timeout = int(cfg.get("timeout") or 15)
        self.client = ApiClient(str(cfg.get("api_base") or "http://127.0.0.1:8080"), timeout)
        self.renderer = Renderer(TEMPLATE_DIR, str(cfg.get("render_mode") or "auto"),
                                  str(cfg.get("theme") or "dark"))
        self.page_size = max(3, int(cfg.get("page_size") or 8))
        self.max_lines = max(10, int(cfg.get("max_lines") or 40))
        self.default_lang = str(cfg.get("lang") or "zh")
        self.poller = Poller(self.client, self._push_text, self.store)
        await self.poller.start()
        logger.info("[wf] 插件初始化完成")

    async def terminate(self):
        if self.poller:
            await self.poller.stop()
        if self.client:
            await self.client.close()

    # ------------------------------------------------------------------
    # 通用管线
    # ------------------------------------------------------------------
    def _flags(self, event, words: list[str]) -> tuple[str, Flags]:
        content = _after(event, words)
        content, flags = parse(content)
        flags.merge_lang(self.default_lang)
        return content, flags

    async def _reply(self, event, vm: dict, flags: Flags, tpl: str):
        """渲染优先，失败/纯文本模式降级。"""
        if vm.get("page_total"):
            vm.setdefault("page_label", f"第 {vm['page']} / {vm['page_total']} 页")
        try:
            res = await self.renderer.render(self, self.context, event, tpl, vm, flags)
        except RuntimeError as e:
            yield event.plain_result(f"⚠ {e}")
            return
        if res is not None:
            yield res
            return
        yield event.plain_result(to_text(vm, self.max_lines, flags.plain_text))

    def _guard_cn(self, flags_or_content) -> str | None:
        if flags_or_content is True or flags_or_content == "cn":
            return "暂不支持国服查询"
        return None

    async def _fetch_section(self, section: str, lang: str):
        data = await self.client.get("/api/worldstate", sections=section, lang=lang)
        return data

    async def _ws_flow(self, event, section: str, paginated: bool):
        cn, vmf, tpl = WS_SECTIONS[section]
        content, flags = self._flags(event, [cn])
        if flags.cn:
            yield event.plain_result("暂不支持国服数据"); return
        sid = event.unified_msg_origin
        cmd_key = f"ws:{section}"
        try:
            data = await self._fetch_section(section, flags.lang)
            vm_full = vmf(data)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return

        if paginated and vm_full.get("items"):
            pages = paginate(vm_full["items"], self.page_size)
            base = {k: v for k, v in vm_full.items() if k != "items"}
            pages = [{**base, **p} for p in pages]
            self.pages.set(sid, cmd_key, pages)
            picked = self.pages.get(sid, cmd_key, flags.page)
            if picked is None:
                picked = {**vm_full, **pages[0]} if pages else vm_full
            vm = picked
        else:
            vm = vm_full
        async for m in self._reply(event, vm, flags, tpl):
            yield m

    # ------------------------------------------------------------------
    # 世界状态指令
    # ------------------------------------------------------------------
    async def _cycle_query(self, event, region: str | None):
        """循环查询通用逻辑。region=None 查全部。"""
        content, flags = self._flags(event, [])
        if flags.cn:
            yield event.plain_result("暂不支持国服数据"); return
        try:
            if region:
                data = await self.client.get("/api/cycles", name=region, lang=flags.lang)
            else:
                data = await self.client.get("/api/cycles", lang=flags.lang)
            vm = vm_cycles(data)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "cycles.html"):
            yield m

    @filter.command("夜灵", alias={"夜灵平原"})
    async def cycle_cetus(self, event):
        """夜灵平原昼夜循环"""
        async for m in self._cycle_query(event, "cetus"): yield m

    @filter.command("地球")
    async def cycle_earth(self, event):
        """地球昼夜循环"""
        async for m in self._cycle_query(event, "earth"): yield m

    @filter.command("金星", alias={"奥布山谷"})
    async def cycle_vallis(self, event):
        """金星奥布山谷温度循环"""
        async for m in self._cycle_query(event, "vallis"): yield m

    @filter.command("火卫二", alias={"火卫"})
    async def cycle_cambion(self, event):
        """火卫二 Fass/Vome 循环"""
        async for m in self._cycle_query(event, "cambion"): yield m

    @filter.command("扎里曼")
    async def cycle_zariman(self, event):
        """扎里曼 Corpus/Grineer 循环"""
        async for m in self._cycle_query(event, "zariman"): yield m

    @filter.command("双衍王境", alias={"双衍"})
    async def cycle_duviri(self, event):
        """双衍王境心绪循环"""
        async for m in self._cycle_query(event, "duviri"): yield m

    @filter.command("循环", alias={"平原时间"})
    async def cycles_all_cmd(self, event):
        """全部开放世界循环一览"""
        async for m in self._cycle_query(event, None): yield m

    @filter.command("警报")
    async def alerts_cmd(self, event):
        """当前世界状态·警报"""
        async for m in self._ws_flow(event, "alerts", False):
            yield m

    @filter.command("突击")
    async def sortie_cmd(self, event):
        """每日突击"""
        async for m in self._ws_flow(event, "sortie", False):
            yield m

    @filter.command("猎杀", alias={"执刑官"})
    async def lite_cmd(self, event):
        """每周执刑官猎杀"""
        async for m in self._ws_flow(event, "liteSorties", False):
            yield m

    @filter.command("入侵")
    async def invasions_cmd(self, event):
        """派系入侵（进度+双方奖励）"""
        async for m in self._ws_flow(event, "invasions", True):
            yield m

    @filter.command("裂隙", alias={"裂缝"})
    async def fissures_cmd(self, event):
        """虚空裂缝（仅普通裂缝，不含钢铁）"""
        content, flags = self._flags(event, ["裂隙", "裂缝"])
        if flags.cn:
            yield event.plain_result("暂不支持国服数据"); return
        sid = event.unified_msg_origin
        try:
            raw = await self._fetch_section("fissures", flags.lang)
            vm = vm_fissures(raw, normal_only=True)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        if vm.get("items"):
            pages = paginate(vm["items"], self.page_size)
            base = {k: v for k, v in vm.items() if k != "items"}
            pages = [{**base, **p} for p in pages]
            self.pages.set(sid, "ws:fissures", pages)
            picked = self.pages.get(sid, "ws:fissures", flags.page) or pages[0]
        else:
            picked = vm
        async for m in self._reply(event, picked, flags, "fissures.html"):
            yield m

    @filter.command("虚空风暴", alias={"九重天裂隙", "九重天裂缝"})
    async def void_storms_cmd(self, event):
        """虚空风暴（航道星舰九重天裂隙）"""
        content, flags = self._flags(event, ["虚空风暴", "九重天裂隙", "九重天裂缝"])
        if flags.cn:
            yield event.plain_result("暂不支持国服数据"); return
        sid = event.unified_msg_origin
        try:
            raw = await self._fetch_section("void_storms", flags.lang)
            vm = vm_void_storms(raw)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        if vm.get("items"):
            pages = paginate(vm["items"], self.page_size)
            base = {k: v for k, v in vm.items() if k != "items"}
            pages = [{**base, **p} for p in pages]
            self.pages.set(sid, "ws:voidstorms", pages)
            picked = self.pages.get(sid, "ws:voidstorms", flags.page) or pages[0]
        else:
            picked = vm
        async for m in self._reply(event, picked, flags, "void_storms.html"):
            yield m

    @filter.command("钢铁裂隙", alias={"钢铁裂缝"})
    async def steel_fissures_cmd(self, event):
        """钢铁裂缝（仅显示 hard=true 的虚空裂缝）"""
        content, flags = self._flags(event, ["钢铁裂隙", "钢铁裂缝"])
        if flags.cn:
            yield event.plain_result("暂不支持国服数据"); return
        sid = event.unified_msg_origin
        try:
            raw = await self._fetch_section("fissures", flags.lang)
            vm = vm_fissures(raw, steel_only=True)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        if vm.get("items"):
            pages = paginate(vm["items"], self.page_size)
            base = {k: v for k, v in vm.items() if k != "items"}
            pages = [{**base, **p} for p in pages]
            self.pages.set(sid, "ws:steelfissures", pages)
            picked = self.pages.get(sid, "ws:steelfissures", flags.page) or pages[0]
        else:
            picked = vm
        async for m in self._reply(event, picked, flags, "fissures.html"):
            yield m

    @filter.command("奸商")
    async def baro_cmd(self, event):
        """虚空商人 Baro Ki'Teer"""
        async for m in self._ws_flow(event, "void_trader", True):
            yield m

    @filter.command("特惠", alias={"每日特惠"})
    async def deals_cmd(self, event):
        """Darvo 每日特惠"""
        async for m in self._ws_flow(event, "daily_deals", False):
            yield m

    @filter.command("电波")
    async def nightwave_cmd(self, event):
        """午夜电波挑战"""
        async for m in self._ws_flow(event, "nightwave", True):
            yield m

    @filter.command("新闻", alias={"最近新闻"})
    async def news_cmd(self, event):
        """官方新闻（按语言筛选）"""
        async for m in self._ws_flow(event, "events", True):
            yield m

    @filter.command("活动")
    async def goals_cmd(self, event):
        """进行中的活动"""
        async for m in self._ws_flow(event, "goals", True):
            yield m

    @filter.command("恶魔塔", alias={"沉沦之地"})
    async def descents_cmd(self, event):
        """Descendia 沉沦之地 21 层挑战"""
        async for m in self._ws_flow(event, "descents", True):
            yield m

    @filter.command("日历", alias={"1999日历"})
    async def calendar_cmd(self, event):
        """1999 日历近期事件"""
        async for m in self._ws_flow(event, "knownCalendarSeasons", True):
            yield m

    @filter.command("小小黑")
    async def persistent_cmd(self, event):
        """追随者（Acolytes）位置与生命"""
        async for m in self._ws_flow(event, "persistent_enemies", False):
            yield m

    @filter.command("仲裁", alias={"仲裁表"})
    async def arb_cmd(self, event):
        """仲裁轮换表（当前+未来）"""
        content, flags = self._flags(event, ["仲裁", "仲裁表"])
        if flags.cn:
            yield event.plain_result("暂不支持国服数据"); return
        sid = event.unified_msg_origin
        try:
            data = await self.client.get("/api/arbitrations", lang=flags.lang)
            vm = vm_arbitrations(data)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        if vm.get("items"):
            pages = paginate(vm["items"], self.page_size)
            base = {k: v for k, v in vm.items() if k != "items"}
            pages = [{**base, **p} for p in pages]
            self.pages.set(sid, "arbitrations", pages)
            picked = self.pages.get(sid, "arbitrations", flags.page) or pages[0]
        else:
            picked = vm
        async for m in self._reply(event, picked, flags, "arbitrations.html"):
            yield m

    # ------------------------------------------------------------------
    # 资料 / 市场
    # ------------------------------------------------------------------
    async def _do_search(self, q: str, flags: Flags, extra: dict | None = None) -> dict:
        params = {"q": q, "lang": flags.lang}
        if extra:
            params.update(extra)
        data = await self.client.get("/api/search", **params)
        return {**data, "query": data.get("query", q)}

    @filter.command("查", alias={"物品"})
    async def search_cmd(self, event):
        """统一搜索（支持简称，可加 trade=true source=wfm,riven）"""
        content, flags = self._flags(event, ["查", "物品"])
        if not content:
            yield event.plain_result("用法：查 <关键词> [trade=true] [source=wfm,riven]"); return
        if flags.cn:
            yield event.plain_result("暂不支持国服查询"); return
        extra: dict = {}
        for tok in list(content.split()):
            tl = tok.lower()
            if tl.startswith("trade=") or tl.startswith("source="):
                k, v = tl.split("=", 1)
                extra[k] = v
                content = content.replace(tok, "").strip()
        try:
            vm = vm_search(await self._do_search(content, flags, extra))
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        self._bump_stats(vm)
        async for m in self._reply(event, vm, flags, "search.html"):
            yield m

    def _bump_stats(self, vm: dict):
        first = (vm.get("items") or [None])[0]
        pass  # 热度由 API 服务端统计；此处保留扩展点

    @filter.command("wiki")
    async def wiki_cmd(self, event):
        """返回首个含 Wiki 链接的搜索结果"""
        content, flags = self._flags(event, ["wiki"])
        if not content:
            yield event.plain_result("用法：wiki <关键词>"); return
        try:
            vm = vm_wiki(await self._do_search(content, flags))
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "search.html"):
            yield m

    @filter.command("掉落", alias={"合成", "铸造"})
    async def drops_cmd(self, event):
        """物品获取途径反查"""
        content, flags = self._flags(event, ["掉落", "合成", "铸造"])
        if not content:
            yield event.plain_result("用法：掉落 <物品名>"); return
        try:
            vm = vm_drops(await self.client.get(
                f"/api/items/{content}/drops", lang=flags.lang))
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "drops.html"):
            yield m

    @filter.command("wm")
    async def wm_cmd(self, event):
        """WM 物品实时价格"""
        content, flags = self._flags(event, ["wm"])
        logger.info(f"[wf] wm_cmd content={content!r} lang={flags.lang}")
        if not content:
            yield event.plain_result("用法：wm <物品名>"); return
        if flags.cn:
            yield event.plain_result("暂不支持国服查询"); return
        try:
            sv = await self._do_search(content, flags, {"trade": "true", "source": "wfm"})
            logger.info(f"[wf] wm search ok, slug candidates={[(r.get('name'), (r.get('wfm') or {}).get('slug')) for r in sv.get('results', [])]}")
            slug = next((w.get("slug")
                         for r in sv.get("results", [])
                         for w in [r.get("wfm") or {}] if w.get("slug")), None)
            if not slug:
                yield event.plain_result(f"WM 未收录：{content}（无匹配可交易商品）"); return
            vm = vm_wm_price(await self.client.get(
                f"/api/wfm/items/{slug}", lang=flags.lang))
        except ApiError as e:
            logger.info(f"[wf] wm ERR: {e.message}")
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "wfm_price.html"):
            yield m

    # ---- wr 全语法（§5.2.1）----
    def _parse_wr_filters(self, tokens: list[str]) -> tuple[dict, list[str]]:
        filters: dict = {}
        rest: list[str] = []
        pol_keys = list(WR_POLARITY.keys())
        for t in tokens:
            low = t.lower()
            matched = False
            if t in WR_POLARITY:
                filters["polarity"] = WR_POLARITY[t]; matched = True
            else:
                for pk in pol_keys:
                    if t.endswith(pk) and len(t) > len(pk):
                        filters["polarity"] = WR_POLARITY[pk]; matched = True; break
            if matched:
                continue
            p = _match_price(t)
            if p is not None:
                filters["price_max"] = p; continue
            if t == "零洗":
                filters["rerolls_zero"] = True; continue
            if t.endswith("洗") and t[:-1].isdigit():
                filters["rerolls_max"] = int(t[:-1]); continue
            m2 = re.match(r"^(\d)\+$", t)
            if m2:
                filters["pos_min"] = int(m2.group(1)); continue
            m21 = re.match(r"^(\d)\+(\d)$", t)
            if m21:
                filters["pos_min"] = int(m21.group(1))
                filters["neg_min"] = int(m21.group(2)); continue
            zh = WR_ATTR_ALIAS.get(t)
            if zh:
                filters.setdefault("attrs", []).append(zh); continue
            rest.append(t)
        return filters, rest

    def _match_wr(self, a: dict, f: dict) -> bool:
        price = a.get("price") or 0
        if "price_max" in f and price > f["price_max"]:
            return False
        rr = a.get("rerolls") or 0
        if "rerolls_zero" in f and rr != 0:
            return False
        if "rerolls_max" in f and rr > f["rerolls_max"]:
            return False
        if "polarity" in f and (a.get("polarity") or "") != f["polarity"]:
            return False
        pos = neg = 0
        names: set[str] = set()
        for x in a.get("attributes") or []:
            if x.get("negative"):
                neg += 1
            else:
                pos += 1
                if x.get("name"):
                    names.add(x["name"])
        if "pos_min" in f and pos < f["pos_min"]:
            return False
        if "neg_min" in f and neg < f["neg_min"]:
            return False
        for want in f.get("attrs") or []:
            if want not in names:
                return False
        return True

    async def _attr_zh_map(self) -> dict[str, str]:
        now = time.time()
        if self._attr_map_cache and now - self._attr_map_cache[0] < 600:
            return self._attr_map_cache[1]
        mapping: dict[str, str] = {}
        try:
            data = await self.client.get("/api/wfm/rivens/attributes",
                                         lang=self.default_lang)
            for a in data.get("attributes") or []:
                eff = a.get("effect")
                if eff:
                    mapping[a.get("slug")] = eff
        except Exception as e:
            logger.warning(f"[wf] 词条词典拉取失败: {e}")
        self._attr_map_cache = (now, mapping)
        return mapping

    @filter.command("wr", alias={"wmr", "wk"})
    async def wr_cmd(self, event):
        """紫卡拍卖筛选（全语法见实现文档 §5.2.1）"""
        content, flags = self._flags(event, ["wr", "wmr", "wk"])
        if not content:
            yield event.plain_result("用法：wr <武器名> [2+|3+1|词条|零洗|1000p|r槽]"); return
        toks = content.split()
        weapon_word = toks[0] if toks else ""
        try:
            rl = await self.client.get("/api/wfm/rivens",
                                       name=weapon_word, lang=flags.lang)
            its = rl.get("items") or []
            if not its:
                yield event.plain_result(f"未找到紫卡武器：{weapon_word}"); return
            slug = its[0]["slug"]
            au = await self.client.get(f"/api/wfm/auctions/{slug}", lang=flags.lang)
            vm = vm_auctions(au)
            filters, extra_kw = self._parse_wr_filters(toks[1:])
            # 中文词条 → slug（复用 attributes i18n）
            if extra_kw:
                zhm = await self._attr_zh_map()
                rev = {zh: sl for sl, zh in zhm.items()}
                for kw in extra_kw:
                    if kw in rev:
                        filters.setdefault("attrs", []).append(rev[kw])
                    elif kw not in filters.get("keywords", []):
                        filters.setdefault("keywords", []).append(kw)
            if filters:
                keep = [a for a in vm.get("items") or [] if self._match_wr(a, filters)]
                vm["items"] = keep
                vm["title"] += f" · 符合 {len(keep)} 单"
                vm["lines"] = [f"{len(keep)} 单符合筛选"]
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "auctions.html"):
            yield m

    @filter.command("词条")
    async def attrs_cmd(self, event):
        """紫卡词条全集（32 种）"""
        content, flags = self._flags(event, ["词条"])
        try:
            vm = vm_attrs(await self.client.get("/api/wfm/rivens/attributes",
                                                lang=flags.lang))
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "attributes.html"):
            yield m

    @filter.command("玄骸")
    async def lich_cmd(self, event):
        """赤毒玄骸武器库"""
        content, flags = self._flags(event, ["玄骸"])
        try:
            data = await self.client.get("/api/wfm/liches",
                                         name=content or None, lang=flags.lang)
            vm = vm_rivens_list({"items": [
                {"item_name": w.get("item_name"), "slug": w.get("slug"),
                 "mastery_level": w.get("mastery_level")}
                for w in data.get("items") or []]})
            vm["title"] = "赤毒玄骸武器 · " + vm["title"].split("· ")[-1]
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "lich_sister.html"):
            yield m

    @filter.command("信条")
    async def sister_cmd(self, event):
        """帕尔沃斯姐妹武器库"""
        content, flags = self._flags(event, ["信条"])
        try:
            data = await self.client.get("/api/wfm/sisters",
                                         name=content or None, lang=flags.lang)
            vm = vm_rivens_list({"items": [
                {"item_name": w.get("item_name"), "slug": w.get("slug"),
                 "mastery_level": w.get("mastery_level")}
                for w in data.get("items") or []]})
            vm["title"] = "信条武器 · " + vm["title"].split("· ")[-1]
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "lich_sister.html"):
            yield m

    @filter.command("倾向")
    async def disp_cmd(self, event):
        """官方紫卡倾向 omega_attenuation"""
        content, flags = self._flags(event, ["倾向"])
        if not content:
            yield event.plain_result("用法：倾向 <武器名>"); return
        try:
            row = await self.client.get(f"/api/weapons/{content}/riven", lang=flags.lang)
            vm = {"title": f"紫卡倾向 · {row.get('name')}",
                  "lines": [f"omega_attenuation = {row.get('omega_attenuation')}"],
                  "disp": row.get("omega_attenuation"), "rtype": "", "mastery": "",
                  "wiki": None}
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "riven.html"):
            yield m

    @filter.command("结合目标", alias={"结合"})
    async def synthesis_cmd(self, event):
        """结合仪式目标：可带 每日/铭刻 或 目标名"""
        content, flags = self._flags(event, ["结合目标", "结合"])
        params: dict = {}
        toks = content.split() if content else []
        for t in list(toks):
            if t == "每日":
                params["type"] = "daily"; toks.remove(t)
            elif t == "铭刻":
                params["type"] = "imprints"; toks.remove(t)
        if toks:
            params["target"] = " ".join(toks)
        try:
            data = await self.client.get("/api/synthesis", lang=flags.lang, **params)
            vm = vm_synthesis(data)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "synthesis.html"):
            yield m

    @filter.command("wm趋势")
    async def trend_cmd(self, event):
        """物品价格趋势（WM 官方统计）"""
        content, flags = self._flags(event, ["wm趋势"])
        if not content:
            yield event.plain_result("用法：wm趋势 <物品名>"); return
        async for m in self._trend_flow(event, content, "item", flags):
            yield m

    @filter.command("紫卡趋势")
    async def rtrend_cmd(self, event):
        """紫卡价格趋势（本地快照）"""
        content, flags = self._flags(event, ["紫卡趋势"])
        if not content:
            yield event.plain_result("用法：紫卡趋势 <武器名>"); return
        async for m in self._trend_flow(event, content, "riven", flags):
            yield m

    async def _trend_flow(self, event, name: str, kind: str, flags: Flags):
        try:
            if kind == "riven":
                rl = await self.client.get("/api/wfm/rivens",
                                           name=name.split()[0], lang=flags.lang)
                its = rl.get("items") or []
                if not its:
                    yield event.plain_result(f"未找到紫卡武器：{name}"); return
                slug = its[0]["slug"]
            else:
                sv = await self._do_search(name, flags, {"trade": "true", "source": "wfm"})
                slug = next((w.get("slug")
                             for r in sv.get("results", [])
                             for w in [r.get("wfm") or {}] if w.get("slug")), None)
                if not slug:
                    yield event.plain_result(f"WM 未收录：{name}"); return
            data = await self.client.get(f"/api/wfm/trends/{slug}",
                                         kind=kind, days=30)
            vm = vm_trends(data)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "trends.html"):
            yield m

    @filter.command("词条价差")
    async def spread_cmd(self, event):
        """同武器各正面词条均价排行"""
        content, flags = self._flags(event, ["词条价差"])
        if not content:
            yield event.plain_result("用法：词条价差 <紫卡武器名或slug>"); return
        try:
            rl = await self.client.get("/api/wfm/rivens",
                                       name=content.split()[0], lang=flags.lang)
            its = rl.get("items") or []
            slug = (its[0]["slug"] if its else content)
            data = await self.client.get(f"/api/wfm/spread/{slug}", lang=flags.lang)
            vm = vm_spread(data)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "spread.html"):
            yield m

    @filter.command("部件")
    async def comp_cmd(self, event):
        """Prime 部件杜卡德分档筛选"""
        s = event.message_str
        tier = "gold" if "金" in s else "silver" if "银" in s else \
            "bronze" if "铜" in s else None
        content, flags = self._flags(event, ["部件"])
        try:
            vm = vm_components(await self.client.get(
                "/api/wfm/components", tier=tier, lang=flags.lang, limit=20))
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "components.html"):
            yield m

    @filter.command("垃圾", alias={"金垃圾", "银垃圾", "铜垃圾"})
    async def trash_cmd(self, event):
        """Prime 部件杜卡德价格（金银铜垃圾）"""
        content, flags = self._flags(event, ["垃圾", "金垃圾", "银垃圾", "铜垃圾"])
        tier_map = {"金垃圾": "gold", "银垃圾": "silver", "铜垃圾": "bronze"}
        q = content.strip()
        tier = tier_map.get(q)
        try:
            if tier:
                data = await self.client.get(f"/api/wfm/components?tier={tier}&lang=flags.lang")
                vm = vm_components(data)
            else:
                # 不带参数：展示三档摘要
                all_items = []
                for t in ["gold", "silver", "bronze"]:
                    d = await self.client.get(f"/api/wfm/components?tier={t}&lang={flags.lang}")
                    for it in (d.get("items") or [])[:5]:
                        all_items.append({"name": it.get("item_name","?"), "ducats": it.get("ducats",0), "tax": it.get("trading_tax",0)})
                vm = {"title": "Prime 垃圾 · 金银铜", "items": all_items, "lines": []}
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "components.html"):
            yield m

    @filter.command("排行", alias={"甲排行", "卡排行", "Mod排行", "武排行"})
    async def rank_cmd(self, event):
        """本站查询热度排行"""
        s = event.message_str
        etype = ("mods" if "卡" in s else
                 "weapons" if ("武" in s or "枪" in s) else
                 "warframes")
        content, flags = self._flags(event, ["排行", "甲排行", "卡排行", "Mod排行", "武排行"])
        try:
            vm = vm_rankings(await self.client.get(
                "/api/wfm/rankings", type=etype, lang=flags.lang, limit=10))
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        async for m in self._reply(event, vm, flags, "generic.html"):
            yield m

    # ------------------------------------------------------------------
    # 蹲 / 订阅
    # ------------------------------------------------------------------
    @filter.command("蹲")
    async def sub_cmd(self, event):
        """条件订阅：蹲钢月 / 蹲赛中 / 蹲三傻 / 蹲奸商 / 蹲 列表 / 蹲 取消"""
        session = event.unified_msg_origin
        content, flags = self._flags(event, ["蹲"])
        toks = content.split() if content else []

        if not toks or toks[0] in ("帮助", "?", "？"):
            yield event.plain_result(
                "用法：蹲 <简称> [时长]\n例：蹲钢月 / 蹲赛中 / 蹲三傻 / 蹲奸商\n"
                "　　蹲钢铁赛中（钢铁+赛德娜+中断裂缝）\n"
                "　　蹲九重天生存（虚空风暴生存）／蹲虚空风暴\n"
                "　　蹲仲裁 [星球] [任务]（如：蹲仲裁 欧罗巴 拦截）\n"
                "　　蹲夜灵平原 白天／蹲地球 白天／蹲金星 寒冷／蹲火卫二 Vome\n"
                "　　蹲扎里曼 Corpus／蹲双衍 愤怒／蹲midrath\n"
                "　　蹲 钢铁 虚空 生存\n时长：7天 两周 长期 永久 数字+h/d/w/m"
                "（缺省命中一次即删）\n管理：蹲 列表 / 蹲 取消 / 蹲 <序号> 取消")
            return
        if toks[0] == "列表":
            subs = self.store.list_session(session)
            if not subs:
                yield event.plain_result("当前会话没有订阅"); return
            lines = [f"#{s['id']} [{s['kind']}] "
                     f"{json.dumps(s.get('cond', {}), ensure_ascii=False)}"
                     for s in subs]
            yield event.plain_result("\n".join(lines)); return
        if toks[0] == "取消":
            n = self.store.remove(session,
                                  int(toks[1]) if len(toks) > 1 and toks[1].isdigit() else None)
            yield event.plain_result(f"已取消 {n} 条订阅"); return

        duration_token = None
        if len(toks) > 1 and (DUR_TOKEN_RE.match(toks[-1]) or toks[-1] in ("长期", "永久")):
            duration_token = toks.pop()
        try:
            dur = parse_duration(duration_token) if duration_token else None
            sub = parse_subscribe(" ".join(toks), dur)
        except ParseError as e:
            yield event.plain_result(f"❌ {e}"); return
        at_id = str(event.get_sender_id() or "") or None
        at_name = event.get_sender_name() or None
        sid = self.store.add(session, sub, at_id=at_id, at_name=at_name)
        cond_str = json.dumps(sub.get("cond", {}), ensure_ascii=False)
        exp = sub.get("expire_at")
        dur_str = ("永久" if exp == -1 else
                   "命中一次即取消" if exp is None else
                   time.strftime("%m-%d %H:%M", time.localtime(exp)) + " 前")
        yield event.plain_result(
            f"✅ 已订阅 #{sid}（命中时将 @ 你）\n"
            f"类型 {sub['kind']}\n条件 {cond_str}\n到期 {dur_str}")

    # ------------------------------------------------------------------
    # /wf 总入口、帮助、不支持表
    # ------------------------------------------------------------------
    WF_ROUTE = {
        "警报": "alerts_cmd", "突击": "sortie_cmd", "猎杀": "lite_cmd",
        "执刑官": "lite_cmd", "入侵": "invasions_cmd", "裂隙": "fissures_cmd",
        "裂缝": "fissures_cmd", "钢铁裂隙": "steel_fissures_cmd",
        "钢铁裂缝": "steel_fissures_cmd", "虚空风暴": "void_storms_cmd",
        "九重天裂隙": "void_storms_cmd", "九重天裂缝": "void_storms_cmd",
        "奸商": "baro_cmd", "特惠": "deals_cmd",
        "每日特惠": "deals_cmd", "电波": "nightwave_cmd", "新闻": "news_cmd",
        "最近新闻": "news_cmd", "活动": "goals_cmd", "恶魔塔": "descents_cmd",
        "沉沦之地": "descents_cmd", "日历": "calendar_cmd",
        "1999日历": "calendar_cmd", "小小黑": "persistent_cmd",
        "仲裁": "arb_cmd", "仲裁表": "arb_cmd", "夜灵": "cycles_cmd",
        "循环": "cycles_cmd", "平原时间": "cycles_cmd", "查": "search_cmd",
        "物品": "search_cmd", "wiki": "wiki_cmd", "掉落": "drops_cmd",
        "合成": "drops_cmd", "铸造": "drops_cmd", "wm": "wm_cmd",
        "wr": "wr_cmd", "wmr": "wr_cmd", "wk": "wr_cmd", "词条": "attrs_cmd",
        "玄骸": "lich_cmd", "信条": "sister_cmd", "倾向": "disp_cmd",
        "结合目标": "synthesis_cmd", "结合": "synthesis_cmd",
        "wm趋势": "trend_cmd", "紫卡趋势": "rtrend_cmd",
        "词条价差": "spread_cmd", "部件": "comp_cmd", "金垃圾": "comp_cmd",
        "银垃圾": "comp_cmd", "铜垃圾": "comp_cmd", "排行": "rank_cmd",
        "甲排行": "rank_cmd", "卡排行": "rank_cmd", "帮助": "help_cmd",
    }

    @filter.command("wf")
    async def wf_cmd(self, event):
        """/wf <中文子指令> —— 与直接发中文指令等价"""
        content = _after(event, ["wf"]).strip()
        first = content.split()[0] if content else ""
        if first in _UNSUPPORTED:
            yield event.plain_result("该功能暂不支持，可用指令见『帮助』"); return
        if first in _CN_CMDS:
            yield event.plain_result("暂不支持国服查询"); return
        method_name = self.WF_ROUTE.get(first)
        if method_name is None:
            yield event.plain_result("未知子指令，发送『帮助』查看全部指令"); return
        orig = event.message_str
        try:
            event.message_str = content          # 保留子指令词供目标解析
            handler = getattr(self, method_name)
            async for m in handler(event):
                yield m
        finally:
            event.message_str = orig

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("wfa", alias={"别名"})
    async def alias_cmd(self, event: AstrMessageEvent):
        """管理员：别称管理。用法：wfa <简称> <物品名> / wfa 删 <简称>"""
        content, flags = self._flags(event, ["wfa", "别名"])
        toks = content.split()
        if not toks:
            yield event.plain_result(
                "用法：wfa <简称> <物品名或entity_id>\n"
                "删除：wfa 删 <简称>\n"
                "示例：wfa 猴 Wukong")
            return
        api_key = (getattr(self, "config", None) or {}).get("alias_api_key") or ""
        if not api_key:
            yield event.plain_result("⚠ 服务端未配置 alias_api_key，请联系部署者"); return

        # wfa 删 <简称>
        if toks[0] in ("删", "delete", "del", "rm"):
            if len(toks) < 2:
                yield event.plain_result("用法：wfa 删 <简称>"); return
            alias = toks[1]
            try:
                resp = await self.client.delete("/api/aliases",
                                              json={"alias": alias},
                                              headers={"X-API-Key": api_key})
                n = resp.get("deleted", 0) if isinstance(resp, dict) else 0
                if n > 0:
                    yield event.plain_result(f"✅ 已删除别称：{alias}")
                else:
                    yield event.plain_result(f"未找到别称：{alias}")
            except ApiError as e:
                yield event.plain_result(f"❌ {e.message}")
            return

        # wfa <简称> <物品名/entity_id>
        if len(toks) < 2:
            yield event.plain_result(
                "用法：wfa <简称> <物品名或entity_id>\n"
                "示例：wfa 猴 Wukong\n"
                "示例：wfa 猴 /Lotus/Powersuits/MonkeyKing/MonkeyKing")
            return
        short = toks[0]
        rest = " ".join(toks[1:])
        try:
            # 直接传 entity_id（以 /Lotus 开头）
            if rest.startswith("/Lotus"):
                entity_id = rest
                entity_type = "warframes"
                entity_name = entity_id.split("/")[-1]
            else:
                # 搜索模式
                sv = await self._do_search(rest, flags)
                results = [r for r in sv.get("results", []) if r.get("entity_id", "").startswith("/Lotus")]
                if not results:
                    yield event.plain_result(f"未找到可绑定的官方条目：{rest}"); return
                r0 = results[0]
                entity_id = r0.get("entity_id")
                entity_type = r0.get("entity_type")
                entity_name = r0.get("name")

            await self.client.post("/api/aliases",
                                   json={"aliases": [{"alias": short,
                                                      "entity_type": entity_type,
                                                      "entity_id": entity_id}]},
                                   headers={"X-API-Key": api_key})
            yield event.plain_result(f"✅ 已绑定：{short} → {entity_name}（{entity_id}）")
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}")
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return

    @filter.command("本周轮换", alias={"钢铁轮换", "双衍轮换"})
    async def rotation_cmd(self, event):
        """本周钢铁/普通双衍轮换物品"""
        content, flags = self._flags(event, ["本周轮换", "钢铁轮换", "双衍轮换"])
        rot = current_rotation()
        vm = {
            "title": f"本周轮换",
            "steel_week": rot["steel_week"],
            "steel": rot["steel"],
            "total_steel": rot["total_steel"],
            "normal_week": rot["normal_week"],
            "normal": rot["normal"],
            "total_normal": rot["total_normal"],
        }
        async for m in self._reply(event, vm, flags, "rotation.html"):
            yield m

    @filter.command("赏金", alias={"bounty"})
    async def bounty_cmd(self, event: AstrMessageEvent):
        """赏金任务查询。用法：赏金 <组织名>"""
        content, flags = self._flags(event, ["赏金", "bounty"])
        org = content.strip() if content.strip() else None
        if not org:
            yield event.plain_result(
                "用法：赏金 <组织名>\n"
                "开放世界：夜灵、金星、火卫二、坚守者、六人组\n"
                "关联集团：夜羽、殁世械灵、卡尔、科维兽、通风小子、索拉里斯之声\n"
                "六人集团：均衡仲裁者、中枢苏达、新世间、佩兰数列、血色面纱、钢铁前线")
            return
        try:
            data = await self._fetch_section("syndicate_missions", flags.lang)
            vm = vm_bounties(data, org)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        if not vm.get("items"):
            yield event.plain_result(
                f"未找到「{org}」的赏金任务\n"
                "发送「赏金」查看全部可用组织")
            return
        async for m in self._reply(event, vm, flags, "bounties.html"):
            yield m

    @filter.command("科研", alias={"深层科研", "时光科研", "Archimedea"})
    async def conquests_cmd(self, event):
        """深层科研 & 时光科研任务"""
        content, flags = self._flags(event, ["科研", "深层科研", "时光科研", "Archimedea"])
        try:
            data = await self._fetch_section("conquests", flags.lang)
            # 根据指令关键词筛选
            cq_filter = None
            raw = event.message_str.strip().lstrip("/")
            if any(kw in raw for kw in ("深层", "lab", "LAB")):
                cq_filter = "CT_LAB"
            elif any(kw in raw for kw in ("时光", "hex", "Hex", "HEX")):
                cq_filter = "CT_HEX"
            vm = vm_conquests(data, filter_type=cq_filter)
        except ApiError as e:
            yield event.plain_result(f"❌ {e.message}"); return
        if not vm.get("groups"):
            yield event.plain_result("当前无科研任务数据"); return
        async for m in self._reply(event, vm, flags, "conquests.html"):
            yield m

    @filter.command("帮助")
    async def help_cmd(self, event):
        """全部指令列表（markdown 图片输出）"""
        content, flags = self._flags(event, ["帮助"])
        vm = {"title": "Warframe 助手 · 指令"}
        try:
            res = await self.renderer.render(self, self.context, event, "help.html", vm, flags)
        except RuntimeError as e:
            yield event.plain_result(f"⚠ {e}")
            return
        if res is not None:
            yield res
        else:
            # 文本降级
            lines = [
                "【Warframe 助手 · 指令】",
                "世界状态：警报 突击 猎杀 入侵 裂隙 奸商 特惠 电波 新闻 活动",
                "轮换：仲裁 / 仲裁表　循环：夜灵(平原时间)　恶魔塔",
                "资料：查 <关键词>　wiki <关键词>　掉落 <物品>",
                "市场：wm <物品>　wr/wmr/wk <武器>　词条　词条价差",
                "订阅：蹲钢月 / 蹲赛中 / 蹲三傻 / 蹲奸商 / 蹲钢铁赛中 / 蹲九重天生存 / 蹲仲裁",
                "别名：血妈→Garuda　咖喱→Excalibur　冰男→Frost",
            ]
            yield event.plain_result("\n".join(lines))

    # ------------------------------------------------------------------
    # LLM Tools
    # ------------------------------------------------------------------
    @filter.llm_tool(name="wf_search_item")
    async def tool_search(self, event: AstrMessageEvent, query: str) -> str:
        """搜索 Warframe 物品（战甲/武器/材料/Mod）。用户询问物品信息时调用。
        Args:
            query (str): 物品关键词，支持中文简称如 血妈
        Returns:
            JSON 数组字符串：[{name, type, tradable}]
        """
        try:
            data = await self.client.get("/api/search", q=query,
                                         lang=self.default_lang, limit=5)
            out = [{"name": r.get("name"), "source": r.get("source"),
                    "tradable": bool(r.get("wfm"))}
                   for r in data.get("results", [])[:5]]
            return json.dumps(out, ensure_ascii=False)
        except Exception as e:
            return f"error: {e}"

    @filter.llm_tool(name="wf_market_price")
    async def tool_price(self, event: AstrMessageEvent, slug: str) -> str:
        """查询物品在 warframe.market 的实时买卖价格。需先用 wf_search_item 获得 slug。
        Args:
            slug (str): 物品 URL 标识（如 adaptation）
        Returns:
            JSON：{sell_min, sell_avg, buy_max}
        """
        try:
            data = await self.client.get(f"/api/wfm/items/{slug}",
                                         lang=self.default_lang)
            p = data.get("prices") or {}
            return json.dumps({
                "item": data.get("item_name"),
                "sell_min": (p.get("sell") or {}).get("min"),
                "sell_avg": (p.get("sell") or {}).get("avg"),
                "buy_max": (p.get("buy") or {}).get("max"),
            }, ensure_ascii=False)
        except Exception as e:
            return f"error: {e}"

    @filter.llm_tool(name="wf_world_summary")
    async def tool_summary(self, event: AstrMessageEvent) -> str:
        """获取游戏世界状态摘要（各开放世界时段、今日突击 Boss、当前仲裁）。用户问现在该打什么/什么时段时调用。"""
        try:
            cyc = await self.client.get("/api/cycles")
            parts = [f"{c.get('name_zh')}:{c.get('state_name')}(剩{c.get('remaining')})"
                     for c in cyc.get("cycles", [])]
            ws = await self.client.get("/api/worldstate", sections="sortie")
            so = ws.get("sortie") or {}
            boss = so.get("boss")
            boss = boss.get("name") if isinstance(boss, dict) else boss
            parts.append(f"突击Boss:{boss or '?'}")
            return "；".join(parts)
        except Exception as e:
            return f"error: {e}"

    # ------------------------------------------------------------------
    # 无前缀快捷指令（regex 触发）
    # ------------------------------------------------------------------
    _NOPREFIX_RE = re.compile(
        r'^(查|物品|wm|wr|wmr|wk|wiki|掉落|合成|铸造|赤毒|紫卡|帮助|help|指令|wfa|别名|'
        r'夜灵|夜灵平原|地球|金星|奥布山谷|火卫二|火卫|扎里曼|双衍王境|双衍|循环|平原时间|'
        r'本周轮换|钢铁轮换|双衍轮换|钢铁裂隙|钢铁裂缝|虚空风暴|九重天裂隙|九重天裂缝|赏金|bounty|警报|突击|猎杀|执刑官|入侵|裂隙|裂缝|'
        r'奸商|特惠|每日特惠|电波|新闻|最近新闻|活动|恶魔塔|沉沦之地|日历|1999日历|'
        r'小小黑|仲裁|仲裁表|词条|玄骸|信条|倾向|结合目标|结合|wm趋势|紫卡趋势|'
        r'词条价差|部件|垃圾|金垃圾|银垃圾|铜垃圾|科研|深层科研|时光科研|Archimedea|排行|甲排行|卡排行|Mod排行|武排行|蹲|wf)'
        r'(?:\s+(.*))?$',
        re.IGNORECASE,
    )


    @filter.regex(_NOPREFIX_RE)
    async def noprefix_cmd(self, event: AstrMessageEvent):
        """无前缀快捷指令：查/wm/wr/wiki/掉落 等可省略 / 前缀"""
        logger.info(f"[wf] noprefix_cmd triggered! msg={event.message_str!r}")
        # 如果消息以 wake_prefix（/）开头，command handler 已处理，跳过
        if event.is_at_or_wake_command:
            return
        msg = event.message_str.strip()
        m = self._NOPREFIX_RE.match(msg)
        if not m:
            return
        kw = m.group(1).lower()
        rest = (m.group(2) or "").strip()

        # 构造一个等效的带前缀消息，复用已有逻辑
        fake_msg = f"/{kw} {rest}".strip()
        event.message_str = fake_msg

        # 路由到对应 handler
        handler_map = {
            "查": self.search_cmd, "物品": self.search_cmd,
            "wm": self.wm_cmd,
            "wr": self.wr_cmd, "wmr": self.wr_cmd, "wk": self.wr_cmd,
            "wiki": self.wiki_cmd,
            "掉落": self.drops_cmd, "合成": self.drops_cmd, "铸造": self.drops_cmd,
            "赤毒": self.lich_cmd, "紫卡": self.lich_cmd,
            "帮助": self.help_cmd, "help": self.help_cmd, "指令": self.help_cmd,
            "wfa": self.alias_cmd, "别名": self.alias_cmd,
            "夜灵": self.cycle_cetus, "夜灵平原": self.cycle_cetus,
            "地球": self.cycle_earth,
            "金星": self.cycle_vallis, "奥布山谷": self.cycle_vallis,
            "火卫二": self.cycle_cambion, "火卫": self.cycle_cambion,
            "扎里曼": self.cycle_zariman,
            "双衍王境": self.cycle_duviri, "双衍": self.cycle_duviri,
            "循环": self.cycles_all_cmd, "平原时间": self.cycles_all_cmd,
            "本周轮换": self.rotation_cmd, "钢铁轮换": self.rotation_cmd, "双衍轮换": self.rotation_cmd,
            "赏金": self.bounty_cmd, "bounty": self.bounty_cmd,
            "科研": self.conquests_cmd, "深层科研": self.conquests_cmd, "时光科研": self.conquests_cmd, "Archimedea": self.conquests_cmd,
            "警报": self.alerts_cmd,
            "突击": self.sortie_cmd,
            "猎杀": self.lite_cmd, "执刑官": self.lite_cmd,
            "入侵": self.invasions_cmd,
            "裂隙": self.fissures_cmd, "裂缝": self.fissures_cmd,
            "钢铁裂隙": self.steel_fissures_cmd, "钢铁裂缝": self.steel_fissures_cmd,
            "虚空风暴": self.void_storms_cmd,
            "九重天裂隙": self.void_storms_cmd, "九重天裂缝": self.void_storms_cmd,
            "奸商": self.baro_cmd,
            "特惠": self.deals_cmd, "每日特惠": self.deals_cmd,
            "电波": self.nightwave_cmd,
            "新闻": self.news_cmd, "最近新闻": self.news_cmd,
            "活动": self.goals_cmd,
            "恶魔塔": self.descents_cmd, "沉沦之地": self.descents_cmd,
            "日历": self.calendar_cmd, "1999日历": self.calendar_cmd,
            "小小黑": self.persistent_cmd,
            "仲裁": self.arb_cmd, "仲裁表": self.arb_cmd,
            "词条": self.attrs_cmd,
            "玄骸": self.lich_cmd,
            "信条": self.sister_cmd,
            "倾向": self.disp_cmd,
            "结合目标": self.synthesis_cmd, "结合": self.synthesis_cmd,
            "wm趋势": self.trend_cmd,
            "紫卡趋势": self.rtrend_cmd,
            "词条价差": self.spread_cmd,
            "部件": self.comp_cmd,
            "垃圾": self.trash_cmd, "金垃圾": self.trash_cmd, "银垃圾": self.trash_cmd, "铜垃圾": self.trash_cmd,
            "排行": self.rank_cmd, "甲排行": self.rank_cmd, "卡排行": self.rank_cmd, "Mod排行": self.rank_cmd, "武排行": self.rank_cmd,
            "蹲": self.sub_cmd,
            "wf": self.wf_cmd,
        }
        handler = handler_map.get(kw)
        if handler:
            async for m in handler(event):
                yield m

    async def _push_text(self, session: str, title: str, lines: list[str],
                         at_id: str | None = None, at_name: str | None = None):
        """订阅命中推送：固定纯文本 + @订阅者（不渲染图片）。"""
        text = f"【{title}】\n" + "\n".join(lines)
        if Plain is None:
            logger.info(f"[wf-sub] 推送(无通道回显): {session} {text}")
            return
        try:
            from astrbot.core.message.message_event_result import MessageChain
        except Exception as e:
            logger.warning(f"[wf-sub] MessageChain 导入失败: {e}")
            return

        chain_items = []
        if at_id and At is not None:
            try:
                chain_items.append(At(qq=str(at_id), name=at_name))
            except TypeError:
                chain_items.append(At(qq=str(at_id)))
            text = "\n" + text          # @ 后换行再接正文
        chain_items.append(Plain(text))

        try:
            await self.context.send_message(session, MessageChain(chain=chain_items))
        except Exception as e:
            # At 组件导致平台拒绝时退回纯文本
            logger.warning(f"[wf-sub] 带@推送失败({e})，退回纯文本")
            try:
                await self.context.send_message(session, MessageChain(chain=[Plain(text)]))
            except Exception as e2:
                logger.error(f"[wf-sub] 推送失败: {e2}")
