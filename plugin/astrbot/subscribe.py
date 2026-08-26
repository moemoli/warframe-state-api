"""蹲/订阅：简称词典、条件解析、后台轮询、命中推送。

存储：插件目录下 subs.json（简单可靠；后续可迁移 AstrBot 存储 API）。
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

from astrbot.api import logger

STORE_FILE = Path(__file__).parent / "subs.json"

# ---------------------------------------------------------------------------
# 简称词典：词 → (维度, 值)
# 维度: kind / system / mission / tier / hard / cycle / state
# ---------------------------------------------------------------------------

ALIAS_DIM: dict[str, list[tuple[str, Any]]] = {
    # —— 裂缝组合简称 ——
    "钢月":   [("kind", "fissure"), ("hard", True), ("system", "月球"), ("mission", "生存")],
    "钢镜":   [("kind", "fissure"), ("hard", True), ("system", "火星"), ("mission", "镜像防御")],
    "赛中":   [("kind", "fissure"), ("system", "赛德娜"), ("mission", "中断")],
    "赛防":   [("kind", "fissure"), ("system", "赛德娜"), ("mission", "防御")],
    "三傻":   [("kind", "cycle"), ("cycle", "cetus"), ("state", "night")],
    "夜灵":   [("kind", "cycle"), ("cycle", "cetus"), ("state", "night")],
    "奸商":   [("kind", "void_trader")],
    # —— 通用维度词 ——
    "钢铁":   [("hard", True)],
    "普通":   [],
    "虚空":   [("system", "虚空")],
    "夜灵平野": [("cycle", "cetus")],
    "地球":   [("system", "地球")],
    "火星":   [("system", "火星")],
    "月球":   [("system", "月球")],
    "赛德娜": [("system", "赛德娜")],
    "海王星": [("system", "海王星")],
    "冥王星": [("system", "冥王星")],
    "火卫二": [("system", "火卫二")],
    "金星":   [("system", "金星")],
    "阋神星": [("system", "阋神星")],
    "捕获":   [("mission", "捕获")],
    "歼灭":   [("mission", "歼灭")],
    "生存":   [("mission", "生存")],
    "防御":   [("mission", "防御")],
    "挖掘":   [("mission", "挖掘")],
    "中断":   [("mission", "中断")],
    "劫持":   [("mission", "劫持")],
    "救援":   [("mission", "救援")],
    "间谍":   [("mission", "间谍")],
    "破坏":   [("mission", "破坏")],
    "黑夜":   [("state", "night")],
    "白天":   [("state", "day")],
}

_KIND_DEFAULT = {
    "fissure": {"kind": "fissure"},
    "cycle": {"kind": "cycle"},
    "void_trader": {"kind": "void_trader"},
}


class ParseError(Exception):
    pass


def parse_subscribe(text: str, duration_s: int | None) -> dict:
    """解析『蹲』参数 → 订阅记录（不含会话字段）。"""
    text = text.strip()
    if not text:
        raise ParseError("缺少订阅条件，例：蹲钢月 / 蹲赛中 / 蹲 钢铁 虚空 生存")
    conds: dict[str, Any] = {}
    matched_any_alias = False
    for token in re.split(r"[，,\s]+", text):
        if not token:
            continue
        entries = ALIAS_DIM.get(token)
        if entries is None:
            low = token.lower()
            for k, v in ALIAS_DIM.items():
                if k.lower() == low:
                    entries = v
                    break
        if entries is None:
            raise ParseError(f"无法识别『{token}』。可用示例：钢月/赛中/三傻/奸商/星球名/任务名/钢铁")
        matched_any_alias = matched_any_alias or any(d == "kind" for d, _ in entries)
        for dim, val in entries:
            if dim == "kind" or dim in _KIND_DEFAULT.get(conds.get("kind", ""), {}):
                pass
            conds[dim] = val
    if not conds.get("kind"):
        conds["kind"] = "fissure"
        matched_any_alias = True
    now = int(time.time())
    return {
        "kind": conds["kind"],
        "cond": {k: v for k, v in conds.items() if k != "kind"},
        "duration_s": duration_s,
        "expire_at": (now + duration_s) if duration_s else None,
        "created_at": now,
        "last_hit_key": None,
        "_alias_matched": matched_any_alias,
    }


DURATION_RE = re.compile(r"^(\d+)\s*([hdwm]|小时|天|周|月)$")


def parse_duration(token: str | None) -> int | None:
    """时长 → 秒。None=命中一次即取消；'长期/永久'=None 且 permanent=True。"""
    if not token:
        return None
    t = token.strip().lower()
    if t in ("长期", "永久"):
        return -1          # 永久约定为 -1
    m = DURATION_RE.match(t)
    if not m:
        raise ParseError(f"无法识别时长『{token}』")
    n = int(m.group(1))
    unit = m.group(2)
    mult = {"h": 3600, "d": 86400, "w": 604800, "mo": 2592000}.get(unit)
    if unit == "小时":
        mult = 3600
    elif unit == "天":
        mult = 86400
    elif unit == "周":
        mult = 604800
    elif unit == "月":
        mult = 2592000
    return n * (mult or 3600)


# ---------------------------------------------------------------------------
# 存储
# ---------------------------------------------------------------------------

class SubStore:
    def __init__(self):
        self._data: dict[str, list[dict]] = {"subs": [], "seen": []}
        self._load()

    def _load(self):
        if STORE_FILE.is_file():
            try:
                self._data = json.loads(STORE_FILE.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"[wf-sub] 存储读取失败，重置: {e}")

    def save(self):
        try:
            STORE_FILE.write_text(
                json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            logger.error(f"[wf-sub] 存储写入失败: {e}")

    # ---- subs ----
    def add(self, session: str, sub: dict,
            at_id: str | None = None, at_name: str | None = None) -> int:
        sid = int(time.time() * 1000) % 10**9
        self._data["subs"].append({
            "id": sid,
            "session": session,
            "at": {"id": at_id, "name": at_name} if at_id else None,
            **sub,
        })
        self.save()
        return sid

    def list_session(self, session: str) -> list[dict]:
        return [s for s in self._data["subs"] if s["session"] == session]

    def remove(self, session: str, sub_id: int | None = None) -> int:
        before = len(self._data["subs"])
        keep = []
        for s in self._data["subs"]:
            if s["session"] != session:
                keep.append(s); continue
            if sub_id is not None and s["id"] != sub_id:
                keep.append(s)
        self._data["subs"] = keep
        removed = before - len(keep)
        if removed:
            self.save()
        return removed

    def all_active(self) -> list[dict]:
        now = int(time.time())
        alive = [s for s in self._data["subs"]
                 if s.get("expire_at") is None or s["expire_at"] in (-1,) or s["expire_at"] > now]
        if len(alive) != len(self._data["subs"]):
            self._data["subs"] = alive
            self.save()
        return alive

    def mark_done(self, sub: dict):
        """一次性订阅命中后删除。"""
        if sub.get("expire_at") is None:
            self._data["subs"] = [s for s in self._data["subs"] if s is not sub]

    # ---- seen ----
    def seen_has(self, key: str) -> bool:
        return key in self._data["seen"]

    def seen_add(self, key: str):
        self._data["seen"].append(key)
        self._data["seen"] = self._data["seen"][-5000:]
        self.save()


# ---------------------------------------------------------------------------
# 匹配器
# ---------------------------------------------------------------------------

def match_fissure(cond: dict, entry: dict) -> bool:
    if cond.get("system") and cond["system"] not in str((entry.get("node") or {}).get("name") or ""):
        # node name 形如 “Copernicus”，星球在 system 字段缺失时用节点匹配退化
        sysm = str((entry.get("node") or {}).get("system_name") or "")
        if cond["system"] not in sysm and cond["system"] not in str(entry.get("node")):
            return False
    mt = cond.get("mission")
    if mt and mt not in str((entry.get("mission_type") or {}).get("name") or ""):
        return False
    if "hard" in cond and bool(entry.get("hard")) != bool(cond["hard"]):
        return False
    return True


def match_cycle(cond: dict, cyc: dict) -> bool:
    if cond.get("cycle") and cond["cycle"] != cyc.get("name"):
        return False
    if cond.get("state") and cond["state"] != cyc.get("state"):
        return False
    return True


def hit_key_fissure(entry: dict) -> str:
    return f"f:{entry.get('id') or entry.get('activation')}"


def hit_key_cycle(cyc: dict) -> str:
    return f"c:{cyc.get('name')}:{cyc.get('expiry')}"


def hit_key_vt(vt: dict) -> str:
    return f"v:{vt.get('activation')}"


class Poller:
    """按 kind 分组轮询 worldstate/cycles，命中即回调 emit。"""

    def __init__(self, client, emit_fn, store: SubStore, interval_base: float = 30.0):
        self.client = client
        # async emit(session:str, title:str, lines:list[str], at_id=None, at_name=None) -> None
        self.emit = emit_fn
        self.store = store
        self.base = interval_base
        self._task: asyncio.Task | None = None
        self._last_tick: dict[str, float] = {}

    async def start(self):
        if not (self._task and not self._task.done()):
            self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        logger.info("[wf-sub] 轮询任务启动")
        while True:
            try:
                await self.tick_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[wf-sub] tick 异常: {e}")
            await asyncio.sleep(self.base)

    async def tick_once(self):
        subs = self.store.all_active()
        if not subs:
            return
        now = time.time()

        need_kinds = {s["kind"] for s in subs}
        fissures = cycles = vt = None

        if "fissure" in need_kinds and now - self._last_tick.get("fissure", 0) >= 60:
            data = await self.client.get("/api/worldstate", sections="fissures")
            fissures = data.get("fissures") or []
            self._last_tick["fissure"] = now
        if "cycle" in need_kinds and now - self._last_tick.get("cycle", 0) >= 30:
            data = await self.client.get("/api/cycles")
            cycles = data.get("cycles") or []
            self._last_tick["cycle"] = now
        if "void_trader" in need_kinds and now - self._last_tick.get("vt", 0) >= 300:
            data = await self.client.get("/api/worldstate", sections="void_trader")
            vt = (data.get("void_trader") or [{}])[0] if isinstance(data.get("void_trader"), list) \
                else data.get("void_trader")
            self._last_tick["vt"] = now

        for sub in subs:
            kind = sub["kind"]
            cond = sub.get("cond") or {}
            if kind == "fissure" and fissures is not None:
                for entry in fissures:
                    k = hit_key_fissure(entry)
                    if match_fissure(cond, entry) and not self.store.seen_has(k):
                        self.store.seen_add(k)
                        await self._emit_hit(sub, [
                            f"{('钢铁·' if entry.get('hard') else '')}"
                            f"{(entry.get('modifier') or {}).get('name','')}",
                            f"{(entry.get('node') or {}).get('name','?')} · "
                            f"{(entry.get('mission_type') or {}).get('name','?')}",
                        ], k)
            elif kind == "cycle" and cycles is not None:
                for cyc in cycles:
                    if match_cycle(cond, cyc):
                        k = hit_key_cycle(cyc)
                        if sub.get("last_hit_key") != k and not self.store.seen_has(k):
                            self.store.seen_add(k)
                            sub["last_hit_key"] = k
                            self.store.save()
                            await self._emit_hit(sub, [
                                f"{cyc.get('name_zh') or cyc.get('name','')} → {cyc.get('state_name','')}",
                                f"剩余 {cyc.get('remaining','?')}",
                            ], k)
            elif kind == "void_trader" and vt:
                k = hit_key_vt(vt)
                act = vt.get("activation") or ""
                from datetime import datetime, timezone
                try:
                    arrived = datetime.fromisoformat(act.replace("Z", "+00:00")).replace(
                        tzinfo=None) <= datetime.utcnow()
                except Exception:
                    arrived = False
                if arrived and not self.store.seen_has(k):
                    self.store.seen_add(k)
                    await self._emit_hit(sub, [
                        f"{vt.get('character','Baro')} 已到达 {((vt.get('node') or {}).get('name')) or '?'}",
                    ], k)

    async def _emit_hit(self, sub: dict, lines: list[str], key: str):
        title = "🔔 订阅命中"
        at = sub.get("at") or {}
        try:
            await self.emit(sub["session"], title,
                            lines + ["（发送『蹲 取消』可清空）"],
                            at_id=at.get("id"), at_name=at.get("name"))
        except Exception as e:
            logger.warning(f"[wf-sub] 推送失败: {e}")
            return
        if sub.get("expire_at") == -1:
            pass  # 永久
        elif sub.get("expire_at") is None:
            self.store.mark_done(sub)     # 命中一次即删
        self.store.save()
