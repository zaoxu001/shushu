"""岁运引动：一个外来的干支（流年、大运）落到原局上，动了哪几个字。

这一层只回答「动没动、动在哪、是什么关系」，不回答「这一年吉不吉」。
合冲刑害的判定一律下放到 :mod:`tianzhi_core.core.ganzhi`，本模块不自带任何一份冲合表——
盘上两个字的关系是底层的事，上层只负责把四柱逐一喂进去、把结果排好序。

合化是唯一一处需要上下文的判断。《滴天髓·化象》：「化得真者只论化，化神还有几般话。」
——化不化得真，要看化神有没有月令之气与盘中之根，不是见合就化。
本模块只给依据（月令帮不帮化神、化神在盘中占多少分量），
拿不准时 ``can_transform`` 返回 ``None``，不替使用者做主。两条阈值都是本包取值，可调。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

from ..core import ganzhi, wuxing
from .shishen import ten_god  # 十神一律走 shishen 层，本模块不重写一份

#: 四柱的固定次序。所有返回的列表都按这个次序做次级排序，保证同一输入同一输出。
PILLARS: tuple[str, ...] = ("year", "month", "day", "hour")

PillarKey = Literal["year", "month", "day", "hour"]
Quad = Mapping[str, tuple[str, str]]

#: 关系的轻重次第：冲 > 刑 > 自刑 > 害 > 合。
#: 本包取值，可调。依据是通行说法「冲为动之最急，刑次之，害又次之，合则牵而不发」。
KIND_ORDER: dict[str, int] = {"冲": 0, "刑": 1, "自刑": 2, "害": 3, "合": 4, "会": 5}

# ── 合化判断用的分量估算 ────────────────────────────────────────
# 真正的旺衰计算在 strength 层，这里只需要一个「化神在盘中有没有根」的粗判，
# 所以用最朴素的加权数数。以下三个系数是本包取值，可调。
GAN_WEIGHT: float = 1.0
#: 地支藏干按本、中、余三档折算
HIDDEN_WEIGHT: dict[str, float] = {"本": 1.0, "中": 0.4, "余": 0.2}

#: 化神占全盘分量到这个比例以上，且月令帮化神，才敢说化得成。本包取值，可调。
TRANSFORM_SHARE_YES: float = 0.28
#: 化神占比低到这个数以下，且月令不帮，才敢说化不成。本包取值，可调。
TRANSFORM_SHARE_NO: float = 0.10


class QuadError(ValueError):
    """四柱输入不合法。"""


def _check(quad: Quad) -> dict[str, tuple[str, str]]:
    """校验四柱字典，返回一份规范化的浅拷贝。缺柱允许，字不合法不允许。"""
    out: dict[str, tuple[str, str]] = {}
    for key in PILLARS:
        cell = quad.get(key)
        if cell is None:
            continue
        gan, zhi = cell[0], cell[1]
        if gan and gan not in ganzhi.GAN:
            raise QuadError(f"{key} 柱天干不合法：{gan!r}")
        if zhi and zhi not in ganzhi.ZHI:
            raise QuadError(f"{key} 柱地支不合法：{zhi!r}")
        out[key] = (gan, zhi)
    if not out:
        raise QuadError("四柱为空")
    return out


def _split(ganzhi_str: str | None) -> tuple[str, str] | None:
    """把 '辛丑' 拆成 ('辛', '丑')。空串或长度不足返回 None。"""
    if not ganzhi_str or len(ganzhi_str) < 2:
        return None
    gan, zhi = ganzhi_str[0], ganzhi_str[1]
    if gan not in ganzhi.GAN or zhi not in ganzhi.ZHI:
        raise QuadError(f"不是干支：{ganzhi_str!r}")
    return gan, zhi


# ── 分量估算 ────────────────────────────────────────────────────
def element_weights(quad: Quad) -> dict[str, float]:
    """四柱五行的粗略分量。天干各计 1，地支藏干按本中余折算。

    这不是旺衰，只是「盘上这一行有多少字」。真正的旺衰取用在 strength / yongshen 层。
    """
    q = _check(quad)
    out: dict[str, float] = {w: 0.0 for w in wuxing.ORDER}
    for gan, zhi in q.values():
        if gan:
            out[ganzhi.GAN_WUXING[gan]] += GAN_WEIGHT
        if zhi:
            for hid, tier in ganzhi.HIDDEN[zhi]:
                out[ganzhi.GAN_WUXING[hid]] += HIDDEN_WEIGHT[tier]
    return out


@dataclass(frozen=True, slots=True)
class Transform:
    """一次合化的判断依据。"""

    #: 合出来的那一行
    into: str
    #: 参与相合的两个字
    pair: tuple[str, str]
    #: 合发生在天干还是地支
    level: Literal["gan", "zhi"]
    #: 月令是否帮化神（月支本气与化神同行，或月支本气生化神）
    month_supports: bool
    #: 化神占全盘分量的比例
    share: float
    #: 化神是否被月令所克
    month_restrains: bool
    #: 化得成吗。拿不准给 None，不武断。
    can_transform: bool | None


def _transform_check(into: str, pair: tuple[str, str], level: Literal["gan", "zhi"],
                     quad: Quad) -> Transform:
    """化神在盘中够不够分量。依《滴天髓·化象》「化得真者只论化」之意，看月令与根气。"""
    q = _check(quad)
    month_zhi = q.get("month", ("", ""))[1]
    month_wx = ganzhi.ZHI_WUXING[month_zhi] if month_zhi else ""
    supports = bool(month_wx) and (month_wx == into or wuxing.SHENG[month_wx] == into)
    restrains = bool(month_wx) and wuxing.KE[month_wx] == into

    weights = element_weights(q)
    total = sum(weights.values())
    share = round(weights[into] / total, 4) if total > 0 else 0.0

    verdict: bool | None
    if supports and share >= TRANSFORM_SHARE_YES:
        verdict = True
    elif not supports and (restrains or share <= TRANSFORM_SHARE_NO):
        verdict = False
    else:
        verdict = None
    return Transform(into=into, pair=pair, level=level, month_supports=supports,
                     share=share, month_restrains=restrains, can_transform=verdict)


# ── 地支引动 ────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class PillarRelation:
    """一个外来地支与某一柱地支之间的一条关系。"""

    kind: Literal["冲", "刑", "自刑", "害", "合"]
    pillar: PillarKey
    #: 被动的那一柱的地支
    zhi: str
    #: 外来的那个地支
    target: str
    #: 六合才有化神，其余为 None
    into: str | None = None


def pillar_relations(target_zhi: str, quad: Quad) -> list[PillarRelation]:
    """一个外来地支跟四柱各支的全部关系，按 冲 > 刑 > 自刑 > 害 > 合 排序。

    同一对字可能同时成立多条（如丑未既冲又刑），逐条返回，不做取舍——
    判定全部来自 :func:`tianzhi_core.core.ganzhi.zhi_relation`，本函数只负责遍历与排序。
    """
    if target_zhi not in ganzhi.ZHI:
        raise QuadError(f"不是地支：{target_zhi!r}")
    q = _check(quad)
    out: list[PillarRelation] = []
    for key in PILLARS:
        zhi = q.get(key, ("", ""))[1]
        if not zhi:
            continue
        for rel in ganzhi.zhi_relation(target_zhi, zhi):
            out.append(PillarRelation(kind=rel.kind, pillar=key, zhi=zhi,  # type: ignore[arg-type]
                                      target=target_zhi, into=rel.into))
    out.sort(key=lambda r: (KIND_ORDER.get(r.kind, 9), PILLARS.index(r.pillar)))
    return out


# ── 天干引动 ────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class GanRelation:
    """一个外来天干与某一柱天干之间的关系。"""

    kind: Literal["合", "冲"]
    pillar: PillarKey
    gan: str
    target: str
    into: str | None = None


def gan_relations(target_gan: str, quad: Quad) -> list[GanRelation]:
    """一个外来天干跟四柱各干的合与冲，冲在前合在后。

    判定来自 :func:`tianzhi_core.core.ganzhi.gan_relation`。
    """
    if target_gan not in ganzhi.GAN:
        raise QuadError(f"不是天干：{target_gan!r}")
    q = _check(quad)
    out: list[GanRelation] = []
    for key in PILLARS:
        gan = q.get(key, ("", ""))[0]
        if not gan:
            continue
        rel = ganzhi.gan_relation(target_gan, gan)
        if rel is None:
            continue
        out.append(GanRelation(kind=rel.kind, pillar=key, gan=gan,  # type: ignore[arg-type]
                               target=target_gan, into=rel.into))
    out.sort(key=lambda r: (KIND_ORDER.get(r.kind, 9), PILLARS.index(r.pillar)))
    return out


# ── 岁运合看 ────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class Interaction:
    """流年与大运一起压到原局上的结构化结果。"""

    day_gan: str
    year_gz: str | None = None
    dayun_gz: str | None = None

    #: 流年天干对日主的十神。没有流年时为 None
    year_ten_god: str | None = None
    #: 大运天干对日主的十神
    dayun_ten_god: str | None = None

    year_zhi_relations: tuple[PillarRelation, ...] = ()
    year_gan_relations: tuple[GanRelation, ...] = ()
    dayun_zhi_relations: tuple[PillarRelation, ...] = ()
    dayun_gan_relations: tuple[GanRelation, ...] = ()

    #: 岁运并临：流年干支与大运干支完全相同
    suiyun_binglin: bool = False
    #: 岁运相冲：流年支冲大运支
    suiyun_chong: bool = False
    #: 岁运相合：流年支与大运支六合
    suiyun_he: bool = False
    #: 流年干与大运干的关系（合或冲），没有则为 None
    suiyun_gan_kind: str | None = None
    #: 流年地支与大运地支之间的全部关系标签
    suiyun_zhi_kinds: tuple[str, ...] = ()

    #: 被引动的柱位，按 year/month/day/hour 次序
    moved_pillars: tuple[PillarKey, ...] = ()
    #: 每一条相合的化神判断
    transforms: tuple[Transform, ...] = ()
    #: 流年干支连同原局四支，是否凑成三合或三会
    groups: tuple[tuple[str, str, str], ...] = field(default=())


def combine(quad: Quad, *, year_gz: str | None = None,
            dayun_gz: str | None = None) -> Interaction:
    """把流年与大运一起看，返回结构化的引动结果。

    两者都不给时，只回一个空壳（仍带日主），不抛错——调用方常常先建盘后填岁运。
    """
    q = _check(quad)
    day_gan = q.get("day", ("", ""))[0]
    if not day_gan:
        raise QuadError("缺日干，无法论十神")

    y = _split(year_gz)
    d = _split(dayun_gz)

    y_zhi_rel = tuple(pillar_relations(y[1], q)) if y else ()
    y_gan_rel = tuple(gan_relations(y[0], q)) if y else ()
    d_zhi_rel = tuple(pillar_relations(d[1], q)) if d else ()
    d_gan_rel = tuple(gan_relations(d[0], q)) if d else ()

    binglin = bool(y and d and year_gz == dayun_gz)
    zhi_kinds: tuple[str, ...] = ()
    gan_kind: str | None = None
    chong = he = False
    if y and d:
        rels = ganzhi.zhi_relation(y[1], d[1])
        zhi_kinds = tuple(r.kind for r in rels)
        chong = any(r.kind == "冲" for r in rels)
        he = any(r.kind == "合" for r in rels)
        g = ganzhi.gan_relation(y[0], d[0])
        gan_kind = g.kind if g else None

    moved = {r.pillar for r in (*y_zhi_rel, *d_zhi_rel)}
    moved |= {r.pillar for r in (*y_gan_rel, *d_gan_rel)}

    transforms: list[Transform] = []
    for zr in (*y_zhi_rel, *d_zhi_rel):
        if zr.kind == "合" and zr.into:
            transforms.append(_transform_check(zr.into, (zr.target, zr.zhi), "zhi", q))
    for gr in (*y_gan_rel, *d_gan_rel):
        if gr.kind == "合" and gr.into:
            transforms.append(_transform_check(gr.into, (gr.target, gr.gan), "gan", q))

    groups: list[tuple[str, str, str]] = []
    if y:
        base = [z for _, z in (q.get(k, ("", "")) for k in PILLARS) if z]
        before = {(r.kind, r.a) for r in ganzhi.zhi_groups(base)}
        for r in ganzhi.zhi_groups([*base, y[1]]):
            if (r.kind, r.a) not in before:
                groups.append((r.kind, r.a, r.into or ""))

    return Interaction(
        day_gan=day_gan,
        year_gz=year_gz or None,
        dayun_gz=dayun_gz or None,
        year_ten_god=ten_god(y[0], day_gan) if y else None,
        dayun_ten_god=ten_god(d[0], day_gan) if d else None,
        year_zhi_relations=y_zhi_rel,
        year_gan_relations=y_gan_rel,
        dayun_zhi_relations=d_zhi_rel,
        dayun_gan_relations=d_gan_rel,
        suiyun_binglin=binglin,
        suiyun_chong=chong,
        suiyun_he=he,
        suiyun_gan_kind=gan_kind,
        suiyun_zhi_kinds=zhi_kinds,
        moved_pillars=tuple(p for p in PILLARS if p in moved),  # type: ignore[misc]
        transforms=tuple(transforms),
        groups=tuple(groups),
    )


__all__: Sequence[str] = (
    "PILLARS", "KIND_ORDER", "QuadError",
    "PillarKey", "PillarRelation", "GanRelation", "Transform", "Interaction",
    "pillar_relations", "gan_relations", "combine", "ten_god", "element_weights",
)
