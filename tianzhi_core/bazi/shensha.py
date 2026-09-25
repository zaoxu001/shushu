"""神煞：按起例查出四柱上落了哪些名目。

**先说清楚这一块的地位。** 神煞在子平正统里是存疑的。《子平真诠·论星辰无关格局》讲得很直白：

    「八字格局，专以月令配四柱，至于星辰好歹，不可以议格局之高低。
     若因某星煞而议吉凶，则子平之法，反为星家所乱矣。」

即：格局高低只从月令与四柱的配合上论，星辰好歹不与焉。本包提供神煞，是为了完整性与展示——
命书里有它、用户想看它——**但取用神、定格局、算旺衰的逻辑绝不采信神煞**：
:mod:`tianzhi_core.bazi.score` 的权重表里没有任何一项来自本模块，
:mod:`tianzhi_core.bazi.hepan` 也不看神煞。要把它当断语用，是调用方自己的选择，不是本包的建议。

起例的出处：天乙贵人、文昌、禄神、驿马、桃花（咸池）、华盖、将星、劫煞、亡神
见《三命通会·论诸神煞》与《渊海子平》；天德月德见《协纪辨方书》；
羊刃直接用 :data:`tianzhi_core.core.ganzhi.YANGREN`，只给阳刃，不替使用者在阴干刃上选边。

同一个名目按不同的字起，结果可能不同（如天乙贵人有「日干起」与「年干起」两派）。
本模块两派都查，每条结果都带 ``base``（依哪个位置起）与 ``source``（依哪个字起），
不合并、不取舍，由调用方决定采信哪一派。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from ..core import ganzhi
from .interact import PILLARS, PillarKey, Quad, _check

# ── 起例表 ──────────────────────────────────────────────────────
#: 天乙贵人。《三命通会》：「甲戊庚牛羊，乙己鼠猴乡，丙丁猪鸡位，壬癸兔蛇藏，六辛逢马虎。」
TIAN_YI: dict[str, tuple[str, ...]] = {
    "甲": ("丑", "未"), "戊": ("丑", "未"), "庚": ("丑", "未"),
    "乙": ("子", "申"), "己": ("子", "申"),
    "丙": ("亥", "酉"), "丁": ("亥", "酉"),
    "辛": ("午", "寅"),
    "壬": ("卯", "巳"), "癸": ("卯", "巳"),
}
#: 文昌贵人。《古今图书集成·艺术典》星命部载：
#:   「甲乙巳午报君知，丙戊申宫丁己鸡；庚猪辛犬壬逢虎，癸人见兔入云梯。」
#: 其所以然：文昌是天干所生的地支人元——甲生丙在巳、乙生丁在午、丙生戊与戊生庚在申、
#: 丁生己与己生辛在酉、庚生壬在亥、壬生甲在寅、癸生乙在卯。
#: 独辛不按此法：原书曰「獨辛不以生，而以戌為文昌，戌在辛之方位，以其有從魁河魁夾之也」。
#: 辛原作子（机械照「食神临官位」推：辛食癸、癸禄子），与底本不合，2026-09 依原文改为戌。
WEN_CHANG: dict[str, tuple[str, ...]] = {
    "甲": ("巳",), "乙": ("午",), "丙": ("申",), "丁": ("酉",), "戊": ("申",),
    "己": ("酉",), "庚": ("亥",), "辛": ("戌",), "壬": ("寅",), "癸": ("卯",),
}
#: 禄神（建禄）：日干的临官位
LU_SHEN: dict[str, tuple[str, ...]] = {
    "甲": ("寅",), "乙": ("卯",), "丙": ("巳",), "丁": ("午",), "戊": ("巳",),
    "己": ("午",), "庚": ("申",), "辛": ("酉",), "壬": ("亥",), "癸": ("子",),
}

#: 三合局起例。一局四煞：将星为局中神，华盖为局末，驿马冲局首，
#: 桃花（咸池）为局首之沐浴，劫煞为局首之绝地，亡神为局中神之临官。
GROUP_RULES: tuple[dict[str, object], ...] = (
    {"group": ("申", "子", "辰"), "将星": "子", "华盖": "辰", "驿马": "寅",
     "桃花": "酉", "劫煞": "巳", "亡神": "亥"},
    {"group": ("寅", "午", "戌"), "将星": "午", "华盖": "戌", "驿马": "申",
     "桃花": "卯", "劫煞": "亥", "亡神": "巳"},
    {"group": ("巳", "酉", "丑"), "将星": "酉", "华盖": "丑", "驿马": "亥",
     "桃花": "午", "劫煞": "寅", "亡神": "申"},
    {"group": ("亥", "卯", "未"), "将星": "卯", "华盖": "未", "驿马": "巳",
     "桃花": "子", "劫煞": "申", "亡神": "寅"},
)
GROUP_NAMES: tuple[str, ...] = ("驿马", "桃花", "华盖", "将星", "劫煞", "亡神")

#: 月德贵人：月支所属三合局的阳干。《协纪辨方书》「寅午戌月在丙，申子辰月在壬……」
YUE_DE: dict[str, str] = {
    "寅": "丙", "午": "丙", "戌": "丙", "申": "壬", "子": "壬", "辰": "壬",
    "亥": "甲", "卯": "甲", "未": "甲", "巳": "庚", "酉": "庚", "丑": "庚",
}
#: 天德贵人：随月令而定，落处有时是天干、有时是地支。《协纪辨方书》
TIAN_DE: dict[str, str] = {
    "寅": "丁", "卯": "申", "辰": "壬", "巳": "辛", "午": "亥", "未": "甲",
    "申": "癸", "酉": "寅", "戌": "丙", "亥": "乙", "子": "巳", "丑": "庚",
}

#: 输出的固定名次，保证同一输入同一顺序
NAME_ORDER: tuple[str, ...] = (
    "天乙贵人", "天德贵人", "月德贵人", "文昌贵人", "禄神", "羊刃",
    "驿马", "桃花", "华盖", "将星", "劫煞", "亡神", "空亡",
)
#: 起例位置的采信次序，用于同名同位时的去重
BASE_ORDER: tuple[str, ...] = ("日干", "年干", "年支", "日支", "月支", "日柱")


@dataclass(frozen=True, slots=True)
class ShenSha:
    """一条神煞。"""

    name: str
    #: 落在哪一柱
    pillar: PillarKey
    #: 落在该柱的天干上还是地支上
    position: Literal["gan", "zhi"]
    #: 落处的那个字
    char: str
    #: 依哪个位置起例（日干 / 年干 / 年支 / 日支 / 月支 / 日柱）
    base: str
    #: 依哪个字起例
    source: str

    @property
    def zhi(self) -> str:
        """落在地支上时的地支，落在天干上时为空串。"""
        return self.char if self.position == "zhi" else ""

    @property
    def gan(self) -> str:
        """落在天干上时的天干，落在地支上时为空串。"""
        return self.char if self.position == "gan" else ""


def _hits_zhi(quad: dict[str, tuple[str, str]], targets: Sequence[str]) -> list[tuple[PillarKey, str]]:
    return [(k, quad[k][1]) for k in PILLARS  # type: ignore[misc]
            if k in quad and quad[k][1] and quad[k][1] in targets]


def _hits_gan(quad: dict[str, tuple[str, str]], target: str) -> list[tuple[PillarKey, str]]:
    return [(k, quad[k][0]) for k in PILLARS  # type: ignore[misc]
            if k in quad and quad[k][0] and quad[k][0] == target]


def xun_kong(day_gan: str, day_zhi: str) -> tuple[str, str]:
    """日柱所在旬的旬空（空亡）二支。甲子旬空戌亥，余仿此。"""
    gi, zi = ganzhi.GAN.index(day_gan), ganzhi.ZHI.index(day_zhi)
    start = (zi - gi) % 12  # 本旬旬首（甲）所落的地支
    return ganzhi.ZHI[(start + 10) % 12], ganzhi.ZHI[(start + 11) % 12]


def _group_of(zhi: str) -> dict[str, object] | None:
    for rule in GROUP_RULES:
        if zhi in rule["group"]:  # type: ignore[operator]
            return rule
    return None


def shensha(quad: Quad, *, include_kong: bool = True) -> list[ShenSha]:
    """四柱上能查出的神煞，按固定名次与柱序返回。

    同名同位但起例不同的，只保留 :data:`BASE_ORDER` 里靠前的那一派，避免重复计数。
    结果只是「查到了」，不含任何吉凶取向——本包的取用逻辑一概不看它。
    """
    q = _check(quad)
    year_gan, year_zhi = q.get("year", ("", ""))
    day_gan, day_zhi = q.get("day", ("", ""))
    month_zhi = q.get("month", ("", ""))[1]

    found: list[ShenSha] = []

    def add(name: str, pillar: PillarKey, position: Literal["gan", "zhi"],
            char: str, base: str, source: str) -> None:
        found.append(ShenSha(name, pillar, position, char, base, source))

    # 一、以天干起、查四柱地支
    for base, gan in (("日干", day_gan), ("年干", year_gan)):
        if not gan:
            continue
        for pillar, zhi in _hits_zhi(q, TIAN_YI.get(gan, ())):
            add("天乙贵人", pillar, "zhi", zhi, base, gan)
        for pillar, zhi in _hits_zhi(q, WEN_CHANG.get(gan, ())):
            add("文昌贵人", pillar, "zhi", zhi, base, gan)
    if day_gan:
        for pillar, zhi in _hits_zhi(q, LU_SHEN.get(day_gan, ())):
            add("禄神", pillar, "zhi", zhi, "日干", day_gan)
        ren = ganzhi.YANGREN.get(day_gan)  # 只有阳干有刃，阴干不给
        if ren:
            for pillar, zhi in _hits_zhi(q, (ren,)):
                add("羊刃", pillar, "zhi", zhi, "日干", day_gan)

    # 二、以年支、日支的三合局起、查四柱地支
    for base, zhi in (("年支", year_zhi), ("日支", day_zhi)):
        rule = _group_of(zhi) if zhi else None
        if not rule:
            continue
        for name in GROUP_NAMES:
            target = str(rule[name])
            for pillar, hit in _hits_zhi(q, (target,)):
                add(name, pillar, "zhi", hit, base, zhi)

    # 三、以月令起，落处可能是天干也可能是地支
    if month_zhi:
        yd = YUE_DE.get(month_zhi)
        if yd:
            for pillar, gan in _hits_gan(q, yd):
                add("月德贵人", pillar, "gan", gan, "月支", month_zhi)
        td = TIAN_DE.get(month_zhi)
        if td in ganzhi.GAN:
            for pillar, gan in _hits_gan(q, str(td)):
                add("天德贵人", pillar, "gan", gan, "月支", month_zhi)
        elif td in ganzhi.ZHI:
            for pillar, zhi in _hits_zhi(q, (str(td),)):
                add("天德贵人", pillar, "zhi", zhi, "月支", month_zhi)

    # 四、旬空。日柱自身不论空。
    if include_kong and day_gan and day_zhi:
        kong = xun_kong(day_gan, day_zhi)
        for pillar, zhi in _hits_zhi(q, kong):
            if pillar == "day":
                continue
            add("空亡", pillar, "zhi", zhi, "日柱", day_gan + day_zhi)

    # 去重：同名同位只留起例次序靠前的一派
    seen: dict[tuple[str, str, str], ShenSha] = {}
    for item in found:
        key = (item.name, item.pillar, item.char)
        old = seen.get(key)
        if old is None or BASE_ORDER.index(item.base) < BASE_ORDER.index(old.base):
            seen[key] = item

    def rank(item: ShenSha) -> tuple[int, int, int]:
        name_rank = NAME_ORDER.index(item.name) if item.name in NAME_ORDER else len(NAME_ORDER)
        return name_rank, PILLARS.index(item.pillar), BASE_ORDER.index(item.base)

    return sorted(seen.values(), key=rank)


__all__: Sequence[str] = (
    "TIAN_YI", "WEN_CHANG", "LU_SHEN", "GROUP_RULES", "GROUP_NAMES",
    "YUE_DE", "TIAN_DE", "NAME_ORDER", "BASE_ORDER",
    "ShenSha", "shensha", "xun_kong",
)
