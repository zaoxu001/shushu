"""天干地支：属性、阴阳、藏干，以及两两之间的合冲刑害。

这一层只做「给我两个字，告诉我它们什么关系」，不看整张盘，也不知道谁是日主。
需要上下文的判断（合化得成不成、冲开的是喜还是忌）属于上层，不在这里。
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Literal, NamedTuple

from . import wuxing

GAN: str = "甲乙丙丁戊己庚辛壬癸"
ZHI: str = "子丑寅卯辰巳午未申酉戌亥"

#: 六十甲子，索引 0 为甲子
JIAZI: tuple[str, ...] = tuple(GAN[i % 10] + ZHI[i % 12] for i in range(60))

GAN_WUXING: dict[str, str] = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}
ZHI_WUXING: dict[str, str] = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

#: 阳干阳支为真
GAN_YANG: frozenset[str] = frozenset("甲丙戊庚壬")
ZHI_YANG: frozenset[str] = frozenset("子寅辰午申戌")

#: 地支藏干，按本气、中气、余气排列
HIDDEN: dict[str, tuple[tuple[str, str], ...]] = {
    "子": (("癸", "本"),),
    "丑": (("己", "本"), ("癸", "中"), ("辛", "余")),
    "寅": (("甲", "本"), ("丙", "中"), ("戊", "余")),
    "卯": (("乙", "本"),),
    "辰": (("戊", "本"), ("乙", "中"), ("癸", "余")),
    "巳": (("丙", "本"), ("庚", "中"), ("戊", "余")),
    "午": (("丁", "本"), ("己", "中")),
    "未": (("己", "本"), ("丁", "中"), ("乙", "余")),
    "申": (("庚", "本"), ("壬", "中"), ("戊", "余")),
    "酉": (("辛", "本"),),
    "戌": (("戊", "本"), ("辛", "中"), ("丁", "余")),
    "亥": (("壬", "本"), ("甲", "中")),
}

#: 子、卯、酉只藏一个字，气最纯。量化时给它们更高的权重有出处，
#: 见 china-testing/bazi 的 zhi5：纯气支按 8 计，杂气支本气按 5 计。
PURE_ZHI: frozenset[str] = frozenset("子卯酉")

# ── 天干之间 ──────────────────────────────────────────────────
#: 天干五合，合化的那一行按「甲己合化土」的次第
GAN_HE: dict[frozenset[str], str] = {
    frozenset({"甲", "己"}): "土",
    frozenset({"乙", "庚"}): "金",
    frozenset({"丙", "辛"}): "水",
    frozenset({"丁", "壬"}): "木",
    frozenset({"戊", "癸"}): "火",
}
#: 天干相冲，隔七位相冲，同阴阳
GAN_CHONG: frozenset[frozenset[str]] = frozenset({
    frozenset({"甲", "庚"}), frozenset({"乙", "辛"}),
    frozenset({"丙", "壬"}), frozenset({"丁", "癸"}),
})

# ── 地支之间 ──────────────────────────────────────────────────
#: 地支六合
ZHI_LIUHE: dict[frozenset[str], str] = {
    frozenset({"子", "丑"}): "土", frozenset({"寅", "亥"}): "木",
    frozenset({"卯", "戌"}): "火", frozenset({"辰", "酉"}): "金",
    frozenset({"巳", "申"}): "水", frozenset({"午", "未"}): "土",
}
#: 三合局，三字聚齐才成局
ZHI_SANHE: dict[tuple[str, str, str], str] = {
    ("申", "子", "辰"): "水", ("亥", "卯", "未"): "木",
    ("寅", "午", "戌"): "火", ("巳", "酉", "丑"): "金",
}
#: 三会方，同一方位的三个字
ZHI_SANHUI: dict[tuple[str, str, str], str] = {
    ("寅", "卯", "辰"): "木", ("巳", "午", "未"): "火",
    ("申", "酉", "戌"): "金", ("亥", "子", "丑"): "水",
}
#: 六冲，对宫相冲
ZHI_CHONG: dict[str, str] = {
    "子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
    "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳",
}
#: 六害
ZHI_HAI: dict[str, str] = {
    "子": "未", "未": "子", "丑": "午", "午": "丑", "寅": "巳", "巳": "寅",
    "卯": "辰", "辰": "卯", "申": "亥", "亥": "申", "酉": "戌", "戌": "酉",
}
#: 相刑。三刑各自成组，另有两字互刑与自刑。
ZHI_XING_GROUPS: tuple[tuple[str, ...], ...] = (
    ("寅", "巳", "申"),   # 无恩之刑
    ("丑", "戌", "未"),   # 恃势之刑
)
ZHI_XING_PAIR: frozenset[frozenset[str]] = frozenset({frozenset({"子", "卯"})})  # 无礼之刑
ZHI_ZIXING: frozenset[str] = frozenset({"辰", "午", "酉", "亥"})                 # 自刑

#: 十二长生的次第
CHANGSHENG: tuple[str, ...] = (
    "长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养",
)
#: 五阳干的长生位；阴干逆行，由 dishi() 处理
_CS_START: dict[str, str] = {"甲": "亥", "丙": "寅", "戊": "寅", "庚": "巳", "壬": "申"}
#: 阴干的长生位（阴生阳死，逆行）
_CS_START_YIN: dict[str, str] = {"乙": "午", "丁": "酉", "己": "酉", "辛": "子", "癸": "卯"}

#: 五阳干的阳刃。阴干是否有刃各家分歧，本包只给阳刃，不替使用者选边。
YANGREN: dict[str, str] = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}

#: 旺相休囚死：某一行在某个季节的状态
WANGXIANG: tuple[str, ...] = ("旺", "相", "休", "囚", "死")


class Relation(NamedTuple):
    """两个字之间的一条关系。"""

    kind: Literal["合", "冲", "刑", "自刑", "害", "会"]
    a: str
    b: str
    #: 合与会才有化神，其余为 None
    into: str | None = None


def _pair(a: str, b: str) -> frozenset[str]:
    return frozenset({a, b})


def gan_relation(a: str, b: str) -> Relation | None:
    """两个天干之间的关系。没有关系返回 None。"""
    if a == b:
        return None
    p = _pair(a, b)
    if p in GAN_HE:
        return Relation("合", a, b, GAN_HE[p])
    if p in GAN_CHONG:
        return Relation("冲", a, b)
    return None


def zhi_relation(a: str, b: str) -> list[Relation]:
    """两个地支之间的全部关系。同一对字可能既合又刑，所以返回列表。

    自刑要求两字相同且在自刑之列；相同但不自刑的（如两个子）不算任何关系。
    """
    out: list[Relation] = []
    if a == b:
        if a in ZHI_ZIXING:
            out.append(Relation("自刑", a, b))
        return out
    p = _pair(a, b)
    if p in ZHI_LIUHE:
        out.append(Relation("合", a, b, ZHI_LIUHE[p]))
    if ZHI_CHONG.get(a) == b:
        out.append(Relation("冲", a, b))
    if ZHI_HAI.get(a) == b:
        out.append(Relation("害", a, b))
    if p in ZHI_XING_PAIR or any(a in g and b in g for g in ZHI_XING_GROUPS):
        out.append(Relation("刑", a, b))
    return out


def zhi_groups(zhis: list[str]) -> list[Relation]:
    """一组地支里成立的三合与三会。要三个字全在才算，缺一不成局。"""
    have = set(zhis)
    out: list[Relation] = []
    for trio, into in ZHI_SANHE.items():
        if have.issuperset(trio):
            out.append(Relation("合", "".join(trio), "", into))
    for trio, into in ZHI_SANHUI.items():
        if have.issuperset(trio):
            out.append(Relation("会", "".join(trio), "", into))
    return out


def dishi(gan: str, zhi: str) -> str:
    """天干在某个地支上的十二长生状态。阳干顺行，阴干逆行。"""
    if gan in _CS_START:
        start, step = _CS_START[gan], 1
    elif gan in _CS_START_YIN:
        start, step = _CS_START_YIN[gan], -1
    else:
        raise ValueError(f"不是天干：{gan!r}")
    d = (ZHI.index(zhi) - ZHI.index(start)) * step % 12
    return CHANGSHENG[d]


def wangxiang(target: str, month_zhi: str) -> str:
    """某一行生在某个月令，处于旺相休囚死的哪一档。

    当令者旺，我生者相，生我者休，克我者囚，我克者死。四季土另按月令本气论。
    """
    ruler = ZHI_WUXING[month_zhi]
    if target == ruler:
        return "旺"
    if wuxing.SHENG[ruler] == target:
        return "相"
    if wuxing.SHENG[target] == ruler:
        return "休"
    if wuxing.KE[target] == ruler:
        return "囚"
    return "死"


def jiazi_index(ganzhi: str) -> int:
    """六十甲子里的序号，0 为甲子。不是有效干支时抛 ValueError。"""
    try:
        return JIAZI.index(ganzhi)
    except ValueError:
        raise ValueError(f"不是六十甲子之一：{ganzhi!r}") from None


@lru_cache(maxsize=1)
def siling_table() -> dict[str, list[dict]]:
    """人元司令分日：每个月令里，藏干各自当令多少天。

    出处为通行的司令分日表，用于按出生日距节气的天数决定该月藏干的权重，
    比固定的本中余三档更贴近古法。
    """
    with resources.files("tianzhi_core.data").joinpath("siling.json").open(encoding="utf-8") as f:
        return json.load(f)


def siling_gan(month_zhi: str, days_after_jieqi: float) -> str:
    """生在节气后第几天，当令的是哪个藏干。超出全月天数时返回最后一位。"""
    acc = 0.0
    table = siling_table().get(month_zhi) or []
    for item in table:
        acc += item["days"]
        if days_after_jieqi < acc:
            return item["gan"]
    return table[-1]["gan"] if table else HIDDEN[month_zhi][0][0]
