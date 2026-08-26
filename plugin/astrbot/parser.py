"""通用附加参数解析（-en/-1/-t/-cn/-N/平台）与翻页 LRU 缓存。"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

_FLAG_RE = re.compile(r"^-([a-z]+|\d+)$", re.I)
_PLATFORMS = {"pc", "ps", "ps4", "ps5", "xb", "xbox", "sw", "switch"}
_PAGE_MAX = 99


@dataclass
class Flags:
    lang_en: bool = False        # -en
    plain_text: bool = False     # -1 / -w
    force_image: bool = False    # -t
    page: int = 1                # -N
    cn: bool = False             # -cn → 直接终止
    platform: str | None = None  # -pc/-ps/-xb/-sw（接受但忽略）

    # 运行期回填
    lang: str = "zh"

    def merge_lang(self, default: str):
        self.lang = "en" if self.lang_en else (default or "zh")


def parse(text: str) -> tuple[str, Flags]:
    """从行首剥离 flag token，返回 (content, flags)。未知 -xxx 保留在 content。"""
    flags = Flags()
    rest: list[str] = []
    for token in text.split():
        m = _FLAG_RE.match(token)
        if not m:
            rest.append(token)
            continue
        v = m.group(1).lower()
        if v == "en":
            flags.lang_en = True
        elif v in ("1", "w"):
            flags.plain_text = True
        elif v == "t":
            flags.force_image = True
        elif v == "cn":
            flags.cn = True
        elif v in _PLATFORMS:
            flags.platform = v
        elif v.isdigit():
            n = int(v)
            if 1 <= n <= _PAGE_MAX:
                flags.page = n
        else:
            rest.append(token)
    return " ".join(rest).strip(), flags


class PageCache:
    """(session_id, cmd_key) → 分页 view-model 列表。容量/时间双限。"""

    MAX_ENTRIES = 128
    TTL = 300.0

    def __init__(self):
        self._data: dict[tuple[str, str], tuple[float, list[dict]]] = {}

    @staticmethod
    def key(session_id: str, cmd_key: str) -> tuple[str, str]:
        return (session_id, cmd_key)

    def set(self, session_id: str, cmd_key: str, pages: list[dict]):
        self._evict()
        self._data[self.key(session_id, cmd_key)] = (time.time(), pages)

    def get(self, session_id: str, cmd_key: str, page: int) -> dict | None:
        rec = self._data.get(self.key(session_id, cmd_key))
        if not rec:
            return None
        ts, pages = rec
        if time.time() - ts > self.TTL or not (1 <= page <= len(pages)):
            return None
        vm = dict(pages[page - 1])
        vm["page"] = page
        vm["page_total"] = len(pages)
        return vm

    def _evict(self):
        now = time.time()
        expired = [k for k, (ts, _) in self._data.items() if now - ts > self.TTL]
        for k in expired:
            self._data.pop(k, None)
        while len(self._data) >= self.MAX_ENTRIES:
            oldest = min(self._data.items(), key=lambda kv: kv[1][0])[0]
            self._data.pop(oldest)


def paginate(items: list, size: int) -> list[dict]:
    """把 items 切成 size 大小的若干页，返回 [{...vm字段..., items: 本页}, ...] 的骨架。"""
    if not items:
        return [{"items": [], "total": 0}]
    return [
        {"items": items[i:i + size], "total": len(items)}
        for i in range(0, len(items), size)
    ]
