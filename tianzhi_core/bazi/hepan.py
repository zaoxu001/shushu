"""合盘：两张命盘之间的结构化指标。

只给指标，不给文案。四组数：

1. 两个日主的五行生克与互看的十神；
2. 日支（夫妻宫）、年支、月支、时支之间的合冲刑害，判定全部走 :mod:`tianzhi_core.core.ganzhi`；
3. 五行互补：一方欠的，另一方有没有；
4. 一个 0 到 100 的相对分与一个档位标签。

分数是相对的，用来排序与比较，不是缘分断语。对称的指标（分数、档位、互补总数、
各柱的关系种类）与调用顺序无关：``relation_card(a, b)`` 与 ``relation_card(b, a)``
在这些字段上必然一致；带方向的字段（十神互看、各自的互补项）才随顺序改变。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..core import ganzhi, wuxing
from .interact import PILLARS, Quad, QuadError, element_weights, ten_god, _check

# ── 权重表（全部为本包取值，可调）────────────────────────────────
BASE: float = 50.0
FLOOR: float = 0.0
CEILING: float = 100.0

#: 两个日主天干五合，古称「天干相合」，视为投缘
DAY_GAN_HE: float = 15.0
#: 两个日主天干相冲
DAY_GAN_CHONG: float = -10.0

#: 日主五行之间的关系分。生与被生同分，同分才保证正反调用对称。
GAN_WX_DELTA: dict[str, float] = {"生": 15.0, "同": 5.0, "克": -10.0, "无": 0.0}

#: 日支（夫妻宫）之间每种关系的分值
DAY_ZHI_DELTA: dict[str, float] = {"合": 20.0, "冲": -20.0, "刑": -10.0, "自刑": -6.0, "害": -10.0}
#: 年支之间，主两家长辈与大环境，权轻
YEAR_ZHI_DELTA: dict[str, float] = {"合": 5.0, "冲": -5.0, "刑": -3.0, "自刑": -2.0, "害": -3.0}
#: 月支之间，主各自最用力的那些年
MONTH_ZHI_DELTA: dict[str, float] = {"合": 4.0, "冲": -6.0, "刑": -3.0, "自刑": -2.0, "害": -3.0}

#: 每命中一项互补加多少，以及互补项的封顶
COMPLEMENT_UNIT: float = 10.0
COMPLEMENT_CAP: float = 20.0

#: 一方某一行的占比低于这个数算「欠」
SHORT_SHARE: float = 0.15
#: 另一方某一行的占比高于这个数算「有余」
STRONG_SHARE: float = 0.20

#: 档位标签。只是分段标签，不是断语。
GRADE_BANDS: tuple[tuple[float, str], ...] = ((75.0, "相契"), (55.0, "相合"), (40.0, "平"), (0.0, "相冲"))


@dataclass(frozen=True, slots=True)
class PairRelation:
    """两张盘同名柱位之间的关系。"""

    pillar: str
    a_zhi: str
    b_zhi: str
    #: 该对地支上成立的全部关系标签，按 ganzhi 的判定原样给出
    kinds: tuple[str, ...]
    #: 六合的化神
    into: str | None = None


@dataclass(frozen=True, slots=True)
class Synastry:
    """两张盘的关系指标。"""

    a_day_gan: str
    b_day_gan: str
    a_day_wuxing: str
    b_day_wuxing: str

    #: b 的日主对 a 来说是什么（比劫/印/食伤/财/官杀），以及反向
    b_to_a: str
    a_to_b: str
    #: 日主互看的十神
    ten_god_b_to_a: str
    ten_god_a_to_b: str
    #: b 的四个天干对 a 日主的十神，以及反向
    ten_gods_b_to_a: dict[str, str]
    ten_gods_a_to_b: dict[str, str]

    #: 两个日主之间的天干关系：合 / 冲 / None
    day_gan_kind: str | None
    #: 五行关系的对称标签：生 / 同 / 克 / 无
    day_gan_axis: str

    #: 同名柱位之间的地支关系
    pillar_relations: tuple[PairRelation, ...]

    #: 各自的五行占比
    a_ratio: dict[str, float]
    b_ratio: dict[str, float]
    #: a 欠而 b 有余的那几行（b 补 a），以及反向
    complement_to_a: tuple[str, ...]
    complement_to_b: tuple[str, ...]
    #: 互补总数，对称
    complement_count: int

    score: float
    grade: str
    breakdown: dict[str, float]


def _axis(wa: str, wb: str) -> str:
    """两行之间的对称关系标签：同 / 生 / 克 / 无。方向另由 b_to_a、a_to_b 给出。"""
    if wa == wb:
        return "同"
    if wuxing.SHENG[wa] == wb or wuxing.SHENG[wb] == wa:
        return "生"
    if wuxing.KE[wa] == wb or wuxing.KE[wb] == wa:
        return "克"
    return "无"


def _short_and_strong(ratio: dict[str, float]) -> tuple[set[str], set[str]]:
    short = {w for w in wuxing.ORDER if ratio.get(w, 0.0) < SHORT_SHARE}
    strong = {w for w in wuxing.ORDER if ratio.get(w, 0.0) > STRONG_SHARE}
    return short, strong


def relation_card(a_quad: Quad, b_quad: Quad, *,
                  a_favorable: Sequence[str] | None = None,
                  b_favorable: Sequence[str] | None = None) -> Synastry:
    """两张盘的关系卡：结构化指标与一个相对分，不含任何叙述文字。

    ``a_favorable`` / ``b_favorable`` 给了就用它判互补（一方的喜用，另一方盘里旺不旺）；
    不给则退回按占比判「欠」与「有余」，阈值见 :data:`SHORT_SHARE` 与 :data:`STRONG_SHARE`。
    本模块自己不取用神。
    """
    a = _check(a_quad)
    b = _check(b_quad)
    ga = a.get("day", ("", ""))[0]
    gb = b.get("day", ("", ""))[0]
    if not ga or not gb:
        raise QuadError("两张盘都必须有日干")

    wa, wb = ganzhi.GAN_WUXING[ga], ganzhi.GAN_WUXING[gb]
    axis = _axis(wa, wb)
    gan_rel = ganzhi.gan_relation(ga, gb)
    gan_kind = gan_rel.kind if gan_rel else None

    ten_gods_b_to_a = {k: ten_god(b[k][0], ga) for k in PILLARS if k in b and b[k][0]}
    ten_gods_a_to_b = {k: ten_god(a[k][0], gb) for k in PILLARS if k in a and a[k][0]}

    rels: list[PairRelation] = []
    for key in PILLARS:
        za = a.get(key, ("", ""))[1]
        zb = b.get(key, ("", ""))[1]
        if not za or not zb:
            continue
        found = ganzhi.zhi_relation(za, zb)
        if not found:
            continue
        into = next((r.into for r in found if r.into), None)
        rels.append(PairRelation(pillar=key, a_zhi=za, b_zhi=zb,
                                 kinds=tuple(r.kind for r in found), into=into))

    a_ratio = wuxing.counts_to_ratio(element_weights(a))
    b_ratio = wuxing.counts_to_ratio(element_weights(b))
    a_short, a_strong = _short_and_strong(a_ratio)
    b_short, b_strong = _short_and_strong(b_ratio)
    want_a = set(a_favorable) if a_favorable else a_short
    want_b = set(b_favorable) if b_favorable else b_short
    comp_a = tuple(w for w in wuxing.ORDER if w in want_a and w in b_strong)
    comp_b = tuple(w for w in wuxing.ORDER if w in want_b and w in a_strong)

    breakdown: dict[str, float] = {"base": BASE}
    if gan_kind == "合":
        breakdown[f"日干{ga}{gb}合"] = DAY_GAN_HE
    elif gan_kind == "冲":
        breakdown[f"日干{ga}{gb}冲"] = DAY_GAN_CHONG
    if GAN_WX_DELTA.get(axis):
        breakdown[f"日主五行{axis}"] = GAN_WX_DELTA[axis]

    table = {"day": DAY_ZHI_DELTA, "year": YEAR_ZHI_DELTA, "month": MONTH_ZHI_DELTA}
    for rel in rels:
        deltas = table.get(rel.pillar)
        if not deltas:
            continue  # 时支之间不入分：两人的时柱各主自己的晚年与子女，交涉最弱
        for kind in rel.kinds:
            if deltas.get(kind):
                breakdown[f"{rel.pillar}支{rel.a_zhi}{kind}{rel.b_zhi}"] = deltas[kind]

    n = len(comp_a) + len(comp_b)
    if n:
        breakdown[f"五行互补×{n}"] = min(COMPLEMENT_CAP, COMPLEMENT_UNIT * n)

    score = max(FLOOR, min(CEILING, sum(breakdown.values())))
    grade = next(g for t, g in GRADE_BANDS if score >= t)

    return Synastry(
        a_day_gan=ga, b_day_gan=gb, a_day_wuxing=wa, b_day_wuxing=wb,
        b_to_a=wuxing.relation(wb, wa), a_to_b=wuxing.relation(wa, wb),
        ten_god_b_to_a=ten_god(gb, ga), ten_god_a_to_b=ten_god(ga, gb),
        ten_gods_b_to_a=ten_gods_b_to_a, ten_gods_a_to_b=ten_gods_a_to_b,
        day_gan_kind=gan_kind, day_gan_axis=axis,
        pillar_relations=tuple(rels),
        a_ratio={k: round(v, 4) for k, v in a_ratio.items()},
        b_ratio={k: round(v, 4) for k, v in b_ratio.items()},
        complement_to_a=comp_a, complement_to_b=comp_b, complement_count=n,
        score=round(score, 1), grade=grade,
        breakdown={k: round(v, 2) for k, v in breakdown.items()},
    )


__all__: Sequence[str] = (
    "BASE", "DAY_GAN_HE", "DAY_GAN_CHONG", "GAN_WX_DELTA", "DAY_ZHI_DELTA",
    "YEAR_ZHI_DELTA", "MONTH_ZHI_DELTA", "COMPLEMENT_UNIT", "COMPLEMENT_CAP",
    "SHORT_SHARE", "STRONG_SHARE", "GRADE_BANDS",
    "PairRelation", "Synastry", "relation_card",
)
