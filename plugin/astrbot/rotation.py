"""钢铁双衍 / 普通双衍 周轮换数据与计算。

轮换周期：
- 普通双衍：12 周循环，每周 3 个战甲 + 强化 Mod
- 钢铁双衍：10 周循环，每周 5 个灵化之源

锚点：2026-01-05（UTC 周一）为第一周。
Warframe 每周 UTC 周一 00:00 重置。
"""

from __future__ import annotations
from datetime import datetime, timezone

# ── 锚点 ─────────────────────────────────────────────────────
# 每周 UTC 周一 00:00 重置
_ANCHOR_Y, _ANCHOR_M, _ANCHOR_D = 2026, 6, 29  # 第一周的周一

# ── 普通双衍：12 周轮换 ────────────────────────────────────
# 每周 3 个战甲，每个带一个强化 Mod
NORMAL_ROTATION: list[list[dict]] = [
    # 第 1 周
    [
        {"warframe": "Excalibur", "mod": "狂怒标枪"},
        {"warframe": "Trinity", "mod": "汲能榨取"},
        {"warframe": "Ember", "mod": "释能放热"},
    ],
    # 第 2 周
    [
        {"warframe": "Loki", "mod": "静谧无踪"},
        {"warframe": "Mag", "mod": "高压粉碎"},
        {"warframe": "Rhino", "mod": "铁甲冲锋"},
    ],
    # 第 3 周
    [
        {"warframe": "Ash", "mod": "削甲手里剑"},
        {"warframe": "Frost", "mod": "冰封护罩"},
        {"warframe": "Nyx", "mod": "同化"},
    ],
    # 第 4 周
    [
        {"warframe": "Saryn", "mod": "猛毒附加"},
        {"warframe": "Vauban", "mod": "永续力场"},
        {"warframe": "Nova", "mod": "分子裂变"},
    ],
    # 第 5 周
    [
        {"warframe": "Nekros", "mod": "幽影之护"},
        {"warframe": "Valkyr", "mod": "永恒战意"},
        {"warframe": "Oberon", "mod": "凤凰新生"},
    ],
    # 第 6 周
    [
        {"warframe": "Hydroid", "mod": "病毒风暴"},
        {"warframe": "Mirage", "mod": "全蚀"},
        {"warframe": "Limbo", "mod": "裂隙避难所"},
    ],
    # 第 7 周
    [
        {"warframe": "Mesa", "mod": "Mesa的华尔兹"},
        {"warframe": "Chroma", "mod": "永恒之护"},
        {"warframe": "Atlas", "mod": "碎石堆叠"},
    ],
    # 第 8 周
    [
        {"warframe": "Ivara", "mod": "渗透"},
        {"warframe": "Inaros", "mod": "不绝护甲"},
        {"warframe": "Titania", "mod": "刀翼闪击"},
    ],
    # 第 9 周
    [
        {"warframe": "Nidus", "mod": "不竭贪婪"},
        {"warframe": "Octavia", "mod": "指挥家"},
        {"warframe": "Harrow", "mod": "持久圣约"},
    ],
    # 第 10 周
    [
        {"warframe": "Gara", "mod": "光谱虹吸"},
        {"warframe": "Khora", "mod": "蓄积长鞭"},
        {"warframe": "Revenant", "mod": "奴仆契约"},
    ],
    # 第 11 周
    [
        {"warframe": "Garuda", "mod": "混沌利爪"},
        {"warframe": "Baruuk", "mod": "响应风暴"},
        {"warframe": "Hildryn", "mod": "炽燃劫掠"},
    ],
    # 第 12 周
    [
        {"warframe": "Wisp", "mod": "储备物流"},
        {"warframe": "Gauss", "mod": "加速"},
        {"warframe": "Protea", "mod": "弹药供给"},
    ],
]

# ── 钢铁双衍：10 周轮换 ────────────────────────────────────
# 每周 5 个灵化之源
STEEL_ROTATION: list[list[str]] = [
    # 第 1 周
    ["布莱顿灵化之源", "拉托灵化之源", "空刃灵化之源", "帕里斯灵化之源", "苦无灵化之源"],
    # 第 2 周
    ["野猪灵化之源", "咖玛腕甲枪灵化之源", "安格斯壮灵化之源", "蛇发女妖灵化之源", "夺魂死神灵化之源"],
    # 第 3 周
    ["玻之武杖灵化之源", "拉特昂灵化之源", "盗贼灵化之源", "弗拉克斯灵化之源", "斯特朗灵化之源"],
    # 第 4 周
    ["雷克斯灵化之源", "执法者灵化之源", "螺钉步枪灵化之源", "野马灵化之源", "陶瓷匕首灵化之源"],
    # 第 5 周
    ["托里德灵化之源", "毒囊双枪灵化之源", "恶脓双斧灵化之源", "米特尔灵化之源", "原子矿融炮灵化之源"],
    # 第 6 周
    ["认知&冲击灵化之源", "月神灵化之源", "瓦斯托灵化之源", "海波单剑灵化之源", "伯斯顿灵化之源"],
    # 第 7 周
    ["席尔火枪灵化之源", "西伯利亚冰锤灵化之源", "恐惧灵化之源", "绝望灵化之源", "憎恨灵化之源"],
    # 第 8 周
    ["德拉灵化之源", "席芭莉丝灵化之源", "锡斯特灵化之源", "暗杀者灵化之源", "翁灵化之源"],
    # 第 9 周
    ["守望者灵化之源", "史特克灵化之源", "布里斯提卡灵化之源", "技巧之剑灵化之源", "奥比克斯灵化之源"],
    # 第 10 周
    ["蛇刃灵化之源", "双子蝰蛇灵化之源", "飞驰电容灵化之源", "暗影利爪灵化之源", "格拉姆灵化之源"],
]


def _weeks_since_anchor() -> int:
    """返回自锚点以来的完整周数。"""
    from datetime import date
    anchor = date(_ANCHOR_Y, _ANCHOR_M, _ANCHOR_D)
    today = datetime.now(timezone.utc).date()
    return max(0, (today - anchor).days // 7)


def current_rotation() -> dict:
    """返回本周的普通双衍和钢铁双衍轮换数据。

    Returns:
        {
            "normal_week": 1-12,
            "normal": [{"warframe": "...", "mod": "..."}, ...],
            "steel_week": 1-10,
            "steel": ["xxx灵化之源", ...],
            "total_normal": 12,
            "total_steel": 10,
        }
    """
    weeks = _weeks_since_anchor()
    nw = weeks % len(NORMAL_ROTATION)
    sw = weeks % len(STEEL_ROTATION)
    return {
        "normal_week": nw + 1,
        "normal": NORMAL_ROTATION[nw],
        "steel_week": sw + 1,
        "steel": STEEL_ROTATION[sw],
        "total_normal": len(NORMAL_ROTATION),
        "total_steel": len(STEEL_ROTATION),
    }
