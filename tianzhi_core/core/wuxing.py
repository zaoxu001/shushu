"""五行：相生、相克，以及某一行相对于另一行的关系。

这是全包最底下的一层，八字、六壬、奇门都用同一套。任何模块要判断「甲对乙是什么」，
都应该落到这里，不要各自再写一份生克表。
"""
from __future__ import annotations

from typing import Literal

WuXing = Literal["木", "火", "土", "金", "水"]

#: 五行的固定次序，按相生排列
ORDER: tuple[str, ...] = ("木", "火", "土", "金", "水")

#: x 生 SHENG[x]
SHENG: dict[str, str] = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}

#: x 克 KE[x]
KE: dict[str, str] = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

#: 生 x 的那一行
SHENG_ME: dict[str, str] = {v: k for k, v in SHENG.items()}

#: 克 x 的那一行
KE_ME: dict[str, str] = {v: k for k, v in KE.items()}

#: 五行对应的方位、季节、颜色。这些是文化常识，供调用方展示用，本包自身不依赖。
DIRECTION: dict[str, str] = {"木": "东", "火": "南", "土": "中", "金": "西", "水": "北"}
SEASON: dict[str, str] = {"木": "春", "火": "夏", "土": "四季", "金": "秋", "水": "冬"}
COLOR: dict[str, str] = {"木": "青", "火": "赤", "土": "黄", "金": "白", "水": "黑"}

#: 相对关系的五种取值。以「我」为基准：
#: 同我=比劫，生我=印，我生=食伤，我克=财，克我=官杀。
Relation = Literal["比劫", "印", "食伤", "财", "官杀"]

#: 帮身的两类
SUPPORT: frozenset[str] = frozenset({"比劫", "印"})
#: 耗身的三类
DRAIN: frozenset[str] = frozenset({"食伤", "财", "官杀"})


def relation(target: str, me: str) -> Relation:
    """target 这一行，对 me 来说是什么关系。

    >>> relation("水", "木")
    '印'
    >>> relation("土", "木")
    '财'
    """
    if target == me:
        return "比劫"
    if SHENG[target] == me:
        return "印"
    if SHENG[me] == target:
        return "食伤"
    if KE[me] == target:
        return "财"
    if KE[target] == me:
        return "官杀"
    raise ValueError(f"不是五行：{target!r} 或 {me!r}")


def is_support(target: str, me: str) -> bool:
    """target 对 me 是帮身还是耗身。帮身为真。"""
    return relation(target, me) in SUPPORT


def counts_to_ratio(counts: dict[str, float]) -> dict[str, float]:
    """把五行的绝对分量折成占比，总和为 1。全零时返回全零，不抛错。"""
    total = sum(counts.get(w, 0.0) for w in ORDER)
    if total <= 0:
        return {w: 0.0 for w in ORDER}
    return {w: counts.get(w, 0.0) / total for w in ORDER}
