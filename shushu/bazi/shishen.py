"""十神：以日干为「我」，给别的干贴标签。

十神不是十种独立的东西，而是两个维度的乘积：

* **五行关系**（五档）：同我=比劫、生我=印、我生=食伤、我克=财、克我=官杀。
  这一档直接用 `shushu.core.wuxing.relation`，不在这里重写。
* **阴阳**（两档）：与日干同阴阳为「偏」（比肩/偏印/食神/偏财/七杀），
  异阴阳为「正」（劫财/正印/伤官/正财/正官）。

「同性相斥、异性相吸」是这张表唯一的记忆点：同阴阳者作用直接而力大（七杀克身无情、
偏财来去无常），异阴阳者有情而受牵制（正官约束有礼、正财守成）。
注意比劫与食伤的命名与直觉相反：**同**阴阳是比肩、食神，**异**阴阳才是劫财、伤官。

本模块是纯查表的确定性函数，不判断吉凶、不看强弱、不看格局——那些要看整张盘，属于上层。
"""
from __future__ import annotations

from typing import Literal

from ..core import wuxing
from ..core.ganzhi import GAN, GAN_WUXING, GAN_YANG

__all__ = ["TenGod", "TEN_GODS", "ten_god", "ten_god_of_wuxing", "is_same_polarity"]

TenGod = Literal[
    "比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印",
]

#: 十神全集，按「比劫 食伤 财 官杀 印」的常用陈列次序
TEN_GODS: tuple[str, ...] = (
    "比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印",
)

#: (五行关系, 是否同阴阳) → 十神。同阴阳取「偏」侧，异阴阳取「正」侧。
_TABLE: dict[tuple[str, bool], str] = {
    ("比劫", True): "比肩", ("比劫", False): "劫财",
    ("食伤", True): "食神", ("食伤", False): "伤官",
    ("财", True): "偏财", ("财", False): "正财",
    ("官杀", True): "七杀", ("官杀", False): "正官",
    ("印", True): "偏印", ("印", False): "正印",
}


def is_same_polarity(a: str, b: str) -> bool:
    """两个天干是否同阴阳。"""
    _check(a)
    _check(b)
    return (a in GAN_YANG) == (b in GAN_YANG)


def _check(gan: str) -> None:
    if gan not in GAN:
        raise ValueError(f"不是天干：{gan!r}")


def ten_god(target_gan: str, day_gan: str) -> TenGod:
    """target_gan 对日干 day_gan 而言是哪一个十神。

    日干对自己是比肩（同五行同阴阳）。要标成「日主」是展示层的事，这里不做特例。

    >>> ten_god("癸", "乙")
    '偏印'
    >>> ten_god("壬", "乙")
    '正印'
    """
    _check(target_gan)
    _check(day_gan)
    rel = wuxing.relation(GAN_WUXING[target_gan], GAN_WUXING[day_gan])
    return _TABLE[(rel, is_same_polarity(target_gan, day_gan))]  # type: ignore[return-value]


def ten_god_of_wuxing(target_wx: str, day_gan: str) -> wuxing.Relation:
    """只到五档：比劫/印/食伤/财/官杀。

    用在只有五行、没有具体天干的场合——比如统计五行分数、判断喜忌方向时，
    正偏之分没有意义，硬要分反而会把量化口径搞乱。
    """
    _check(day_gan)
    if target_wx not in wuxing.ORDER:
        raise ValueError(f"不是五行：{target_wx!r}")
    return wuxing.relation(target_wx, GAN_WUXING[day_gan])
