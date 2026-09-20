"""调候：《穷通宝鉴》调候用神表、《金不换》喜忌表，以及按盘面剔除后的调候需求。

两张表都只由「日干 × 生月」两个条件决定，与盘里其余的字无关——这正是它们能做成
静态表的原因，也是「凡春月都取火土」这类按季节一刀切在方法上不成立的原因：
同样生在辰月，甲木要庚丁壬，乙木要癸丙戊。

- 《穷通宝鉴》（又名《栏江网》）十天干 × 十二月令，共 120 格，给「该取什么」。
- 《金不换大运》同样 120 格，除喜神外明确给出忌神天干，并附大运地支的顺逆，
  补上了调候表不说的「不该碰什么」。

数据见 shushu/data/tiaohou.json 与 shushu/data/jinbuhuan.json，原书为公版古籍。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from ..core import ganzhi
from . import strength as _st
from .strength import Quad

__all__ = [
    "ClimateGods", "AdverseGods", "ClimateNeed",
    "climate_gods", "adverse_gods", "climate_need",
]


@lru_cache(maxsize=1)
def _tiaohou_table() -> dict[str, dict[str, list[str]]]:
    with resources.files("shushu.data").joinpath("tiaohou.json").open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _jinbuhuan_table() -> dict[str, dict[str, dict]]:
    with resources.files("shushu.data").joinpath("jinbuhuan.json").open(encoding="utf-8") as f:
        return json.load(f)


def _elements(gans: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """天干折五行，保序去重。"""
    out: list[str] = []
    for g in gans:
        w = ganzhi.GAN_WUXING.get(g)
        if w and w not in out:
            out.append(w)
    return tuple(out)


@dataclass(frozen=True)
class ClimateGods:
    """《穷通宝鉴》某一格的调候用神。gans 按优先级排列，首位为首用神。"""

    day_gan: str
    month_zhi: str
    gans: tuple[str, ...]
    primary: str
    elements: tuple[str, ...]
    source: str = "穷通宝鉴"


@dataclass(frozen=True)
class AdverseGods:
    """《金不换》某一格的喜忌天干与大运顺逆地支。"""

    day_gan: str
    month_zhi: str
    xi_gans: tuple[str, ...]
    ji_gans: tuple[str, ...]
    xi_elements: tuple[str, ...]
    ji_elements: tuple[str, ...]
    dayun_xi: tuple[str, ...]
    dayun_ji: tuple[str, ...]
    note: str
    source: str = "金不换大运"


@dataclass(frozen=True)
class ClimateNeed:
    """查表之后按盘面剔除的调候需求。

    kept 是剔除后仍成立的调候五行，dropped 是被剔除的，bing 是全盘最旺的那一行。
    """

    gods: ClimateGods
    kept: tuple[str, ...]
    dropped: tuple[str, ...]
    bing: str
    fallback: bool          #: True 表示全被剔除、保留首用神兜底


def climate_gods(day_gan: str, month_zhi: str) -> ClimateGods | None:
    """查《穷通宝鉴》。查不到返回 None。"""
    gans = (_tiaohou_table().get(day_gan) or {}).get(month_zhi)
    if not gans:
        return None
    return ClimateGods(day_gan, month_zhi, tuple(gans), gans[0], _elements(gans))


def adverse_gods(day_gan: str, month_zhi: str) -> AdverseGods | None:
    """查《金不换》。查不到返回 None。"""
    cell = (_jinbuhuan_table().get(day_gan) or {}).get(month_zhi)
    if not cell:
        return None
    xi = tuple(cell.get("xi") or ())
    ji = tuple(cell.get("ji") or ())
    return AdverseGods(
        day_gan=day_gan, month_zhi=month_zhi,
        xi_gans=xi, ji_gans=ji,
        xi_elements=_elements(xi), ji_elements=_elements(ji),
        dayun_xi=tuple(cell.get("dayun_xi") or ()),
        dayun_ji=tuple(cell.get("dayun_ji") or ()),
        note=str(cell.get("note") or ""),
    )


def climate_need(quad: Quad) -> ClimateNeed | None:
    """查调候表，再按盘面剔除。查不到返回 None。

    剔除的依据是病药法（《神峰通考·病药说》「有病方为贵，无伤不是奇」）：
    古表给的是这个日干生在这个月**通常**缺什么，它不知道这张盘的字。
    全盘最旺的那一行是病；古表点名的用神若正好是这个病，说明这张盘不缺反而多，
    取之只会加重偏枯，予以剔除。全被剔除时保留首用神兜底（fallback=True），
    以免调候整条失效。
    """
    _st.validate_quad(quad)
    gods = climate_gods(quad["day"][0], quad["month"][1])
    if gods is None:
        return None
    mass = _st.element_power(quad)
    bing = max(mass, key=lambda k: mass[k]) if mass else ""
    kept = tuple(w for w in gods.elements if w != bing)
    dropped = tuple(w for w in gods.elements if w == bing)
    fallback = not kept
    if fallback:
        kept = gods.elements[:1]
    return ClimateNeed(gods=gods, kept=kept, dropped=dropped, bing=bing, fallback=fallback)
