"""逐年评分：把一年的引动折成一个可比较的数，并交代这个数是怎么来的。

**这个分数是相对的。** 它用来看一生起伏的形状——哪几年顺、哪几年费劲、
拐点落在哪一步大运上——不是吉凶断语，也不能跨盘比较（两张盘的 60 分不是同一个 60 分）。
50 分表示这一年在这张盘上不偏顺也不偏逆。

打分只看四件在命理上说得清、在代码里算得出的事：

1. 流年与大运的干支，五行落在喜用上还是忌神上（喜忌由 yongshen 层给出，本模块不自己取用）；
2. 流年地支与四柱的冲刑害合，冲月令与冲日支最贴身，扣得最多；
3. 流年天干对日主的十神性质，财官印食偏顺，伤官七杀劫财偏折腾；
4. 岁运之间的并临与相冲。

所有权重都是模块级常量，标注为「本包取值，可调」。要换一套口径，改常量即可，不必动函数。
神煞一概不入分——理由见 :mod:`tianzhi_core.bazi.shensha` 的模块说明。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, NamedTuple, Sequence

from ..core import ganzhi
from . import interact
from .interact import Quad, QuadError

# ── 权重表（全部为本包取值，可调）────────────────────────────────
#: 不偏顺也不偏逆的基准分
BASE: float = 50.0
#: 分数的上下限
FLOOR: float = 0.0
CEILING: float = 100.0

#: 一个字落在喜用上加多少、落在忌神上扣多少（再乘各自的位置系数）
WX_HIT: float = 8.0

#: 位置系数：地支管一年的底，比天干重；大运是十年的底色，单年里减半计。
SLOT_WEIGHT: dict[str, float] = {
    "year_gan": 1.0,
    "year_zhi": 1.2,
    "dayun_gan": 0.5,
    "dayun_zhi": 0.6,
}

#: 十神本身的偏向。财官印食偏顺，伤官七杀劫财偏折腾，比肩偏印居中。
#: 这是对十神常见取向的工程近似，不是吉凶定论——忌神得地时正官也未必顺。
GOD_BIAS: dict[str, float] = {
    "正财": 6.0, "偏财": 5.0, "正官": 6.0, "正印": 5.0, "食神": 5.0,
    "偏印": 1.0, "比肩": 0.0, "劫财": -4.0, "伤官": -4.0, "七杀": -5.0,
}
GOD_WEIGHT: float = 0.8

#: 流年地支与四柱之间每种关系的分值。合为小幅加分：牵而不发，慢但不散。
REL_DELTA: dict[str, float] = {"冲": -9.0, "刑": -5.0, "自刑": -4.0, "害": -3.0, "合": 2.0}

#: 冲到哪一柱，轻重不同。月令为提纲、日支为自身，最贴身。
PILLAR_WEIGHT: dict[str, float] = {"month": 1.4, "day": 1.3, "year": 0.8, "hour": 0.8}

#: 流年天干直接冲日主 / 合日主。合是羁绊，只微扣。
DAY_GAN_CHONG: float = -5.0
DAY_GAN_HE: float = -1.0

#: 岁运并临（流年干支与大运干支相同）。《三命通会》有「岁运并临」之目，
#: 传统视为大动之年。本包只按「动得大」计一个负权重，不作灾祥之断。
SUIYUN_BINGLIN: float = -6.0
#: 岁运相冲：十年的底子与当年的势对着来
SUIYUN_CHONG: float = -6.0

#: 流年与原局四支凑成三合或三会，化神落喜用 / 忌神各加减多少
GROUP_DELTA: float = 5.0

#: 曲线里没有大运（起运之前）时，大运项一律缺省，不补分


class ScoreTerm(NamedTuple):
    """分数里的一项：从哪来、依据哪几个字、加减多少。"""

    source: str
    detail: str
    delta: float


@dataclass(frozen=True, slots=True)
class YearScore:
    """一年的评分。``score`` 是相对分，``breakdown`` 交代每一分是怎么来的。"""

    ganzhi: str
    score: float
    #: 每个加减项的来源与分值。键是结构化标签，值是分差。
    breakdown: dict[str, float]
    #: 与 breakdown 同一批数据，带完整字段，便于调用方自己排版
    terms: tuple[ScoreTerm, ...] = ()
    #: 这一年落在哪步大运上
    dayun: str | None = None
    #: 流年天干对日主的十神
    ten_god: str | None = None
    #: 喜忌态势标签：顺 / 偏顺 / 平 / 混 / 偏逆 / 逆
    stance: str = "平"


@dataclass(frozen=True, slots=True)
class YearPoint:
    """曲线上的一个点。"""

    year: int
    ganzhi: str
    dayun: str
    score: float
    ten_god: str | None = None
    stance: str = "平"
    breakdown: dict[str, float] = field(default_factory=dict)


class Cycle(NamedTuple):
    """一步大运，连同它覆盖的那些流年。``ganzhi`` 为空串表示起运之前的小运。"""

    ganzhi: str
    #: (公历年, 该年干支) 的序列
    years: tuple[tuple[int, str], ...]


def _wx_delta(wx: str, favorable: Sequence[str], unfavorable: Sequence[str]) -> tuple[float, str]:
    """一个五行落在喜用还是忌神上。返回 (系数前的分值, 标签)。"""
    if wx in favorable:
        return WX_HIT, "喜用"
    if wx in unfavorable:
        return -WX_HIT, "忌神"
    return 0.0, "闲神"


def _stance(gan_wx: str, zhi_wx: str, favorable: Sequence[str],
            unfavorable: Sequence[str]) -> str:
    """这一年的喜忌态势。只给标签，不给说法。"""
    hits = [w for w in (gan_wx, zhi_wx) if w in favorable]
    miss = [w for w in (gan_wx, zhi_wx) if w in unfavorable]
    if len(hits) == 2:
        return "顺"
    if len(miss) == 2:
        return "逆"
    if hits and miss:
        return "混"
    if hits:
        return "偏顺"
    if miss:
        return "偏逆"
    return "平"


def score_year(quad: Quad, year_gz: str, *, dayun_gz: str | None = None,
               favorable: Sequence[str] | None = None,
               unfavorable: Sequence[str] | None = None) -> YearScore:
    """给一年打一个 0 到 100 的相对分，并列出每一项的来源。

    ``favorable`` / ``unfavorable`` 是喜用与忌神的五行，由调用方从 yongshen 层取来；
    不给则只按引动关系与十神打分，五行项一律计 0。
    """
    fav = tuple(favorable or ())
    unf = tuple(unfavorable or ())
    y = interact._split(year_gz)
    if y is None:
        raise QuadError(f"流年干支不合法：{year_gz!r}")
    y_gan, y_zhi = y
    d = interact._split(dayun_gz)

    inter = interact.combine(quad, year_gz=year_gz, dayun_gz=dayun_gz)
    day_gan = inter.day_gan

    terms: list[ScoreTerm] = [ScoreTerm("base", "基准", BASE)]

    # 1) 五行喜忌
    gan_wx = ganzhi.GAN_WUXING[y_gan]
    zhi_wx = ganzhi.ZHI_WUXING[y_zhi]
    for slot, char, wx in (("year_gan", y_gan, gan_wx), ("year_zhi", y_zhi, zhi_wx)):
        raw, tag = _wx_delta(wx, fav, unf)
        if raw:
            terms.append(ScoreTerm(slot, f"{char}({wx}){tag}", raw * SLOT_WEIGHT[slot]))
    if d:
        for slot, char, wx in (("dayun_gan", d[0], ganzhi.GAN_WUXING[d[0]]),
                               ("dayun_zhi", d[1], ganzhi.ZHI_WUXING[d[1]])):
            raw, tag = _wx_delta(wx, fav, unf)
            if raw:
                terms.append(ScoreTerm(slot, f"{char}({wx}){tag}", raw * SLOT_WEIGHT[slot]))

    # 2) 十神性质
    tg = inter.year_ten_god
    if tg and GOD_BIAS.get(tg):
        terms.append(ScoreTerm("ten_god", f"{y_gan}对{day_gan}为{tg}", GOD_BIAS[tg] * GOD_WEIGHT))

    # 3) 流年地支与四柱的冲刑害合
    for rel in inter.year_zhi_relations:
        delta = REL_DELTA.get(rel.kind, 0.0) * PILLAR_WEIGHT.get(rel.pillar, 1.0)
        if delta:
            terms.append(ScoreTerm(f"zhi.{rel.kind}.{rel.pillar}",
                                   f"{rel.target}{rel.kind}{rel.pillar}支{rel.zhi}", delta))

    # 4) 流年天干与日主
    for rel in inter.year_gan_relations:
        if rel.pillar != "day":
            continue
        if rel.kind == "冲":
            terms.append(ScoreTerm("gan.冲.day", f"{y_gan}冲日主{day_gan}", DAY_GAN_CHONG))
        elif rel.kind == "合":
            terms.append(ScoreTerm("gan.合.day", f"{y_gan}合日主{day_gan}", DAY_GAN_HE))

    # 5) 岁运之间
    if inter.suiyun_binglin:
        terms.append(ScoreTerm("suiyun.并临", f"流年与大运同为{year_gz}", SUIYUN_BINGLIN))
    if inter.suiyun_chong:
        terms.append(ScoreTerm("suiyun.冲", f"{y_zhi}冲大运支{d[1] if d else ''}", SUIYUN_CHONG))

    # 6) 流年引来的三合三会
    for kind, trio, into in inter.groups:
        raw, tag = _wx_delta(into, fav, unf)
        if raw:
            sign = 1.0 if raw > 0 else -1.0
            terms.append(ScoreTerm(f"group.{kind}", f"{trio}{kind}{into}局({tag})",
                                   GROUP_DELTA * sign))

    total = sum(t.delta for t in terms)
    total = max(FLOOR, min(CEILING, total))

    breakdown: dict[str, float] = {}
    for t in terms:
        key = t.source if t.source == "base" else f"{t.source}|{t.detail}"
        while key in breakdown:  # 兜底去重，正常不会撞
            key += "'"
        breakdown[key] = round(t.delta, 2)

    return YearScore(
        ganzhi=year_gz,
        score=round(total, 1),
        breakdown=breakdown,
        terms=tuple(ScoreTerm(t.source, t.detail, round(t.delta, 2)) for t in terms),
        dayun=dayun_gz or None,
        ten_god=tg,
        stance=_stance(gan_wx, zhi_wx, fav, unf),
    )


def _as_cycle(item: Cycle | Mapping[str, object] | Sequence[object]) -> Cycle:
    """把大运输入规范成 Cycle。接受 Cycle、{'ganzhi':..,'years':[..]} 或 (干支, 年表)。"""
    if isinstance(item, Cycle):
        return item
    if isinstance(item, Mapping):
        gz = str(item.get("ganzhi") or "")
        years = item.get("years") or ()
    else:
        gz = str(item[0] or "")
        years = item[1] or ()  # type: ignore[index]
    norm = tuple((int(y), str(g)) for y, g in years)  # type: ignore[union-attr]
    return Cycle(gz, norm)


def curve(quad: Quad, cycles: Iterable[Cycle | Mapping[str, object] | Sequence[object]], *,
          favorable: Sequence[str] | None = None,
          unfavorable: Sequence[str] | None = None) -> list[YearPoint]:
    """整条人生曲线，每个流年一个点，按公历年升序。

    ``cycles`` 是逐步大运，每步带上它覆盖的流年。大运干支为空串（起运前的小运）时，
    该年只按流年与原局打分，不计大运项。分数的意义见模块说明：相对的形状，不是断语。
    """
    points: list[YearPoint] = []
    for raw in cycles:
        cyc = _as_cycle(raw)
        for year, gz in cyc.years:
            ys = score_year(quad, gz, dayun_gz=cyc.ganzhi or None,
                            favorable=favorable, unfavorable=unfavorable)
            points.append(YearPoint(year=year, ganzhi=gz, dayun=cyc.ganzhi,
                                    score=ys.score, ten_god=ys.ten_god,
                                    stance=ys.stance, breakdown=dict(ys.breakdown)))
    points.sort(key=lambda p: p.year)
    return points


__all__: Sequence[str] = (
    "BASE", "WX_HIT", "SLOT_WEIGHT", "GOD_BIAS", "GOD_WEIGHT", "REL_DELTA",
    "PILLAR_WEIGHT", "DAY_GAN_CHONG", "DAY_GAN_HE", "SUIYUN_BINGLIN", "SUIYUN_CHONG",
    "GROUP_DELTA", "ScoreTerm", "YearScore", "YearPoint", "Cycle",
    "score_year", "curve",
)

# 供调用方一次取到全部权重，做参数扫描或写文档用
WEIGHT_TABLE: dict[str, object] = {
    "BASE": BASE, "WX_HIT": WX_HIT, "SLOT_WEIGHT": SLOT_WEIGHT,
    "GOD_BIAS": GOD_BIAS, "GOD_WEIGHT": GOD_WEIGHT, "REL_DELTA": REL_DELTA,
    "PILLAR_WEIGHT": PILLAR_WEIGHT, "DAY_GAN_CHONG": DAY_GAN_CHONG,
    "DAY_GAN_HE": DAY_GAN_HE, "SUIYUN_BINGLIN": SUIYUN_BINGLIN,
    "SUIYUN_CHONG": SUIYUN_CHONG, "GROUP_DELTA": GROUP_DELTA,
}
