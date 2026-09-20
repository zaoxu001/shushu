"""盘面量化：五行力量、日主旺衰、十神力量、寒暖燥湿。

本模块只接收「四柱干支」这一最朴素的输入，不依赖排盘、不读时间、不做 IO，
同一输入永远得到同一输出。

═══ 量化模型 ═══
全盘拆成若干「成分」(Component)：四个天干各一个成分，四个地支按藏干各展开若干成分。
每个成分带一个力量权重，权重由下列因子相乘得到：

    基础分 × 根气系数 × 纯气加权 × 月令配重 × 司令加权 × 贴身加权 × 虚透折减

各因子的出处与取值见下方常量。上层（旺衰、十神力量、五行分布）共用这一套权重，
不再各自加权，避免三处口径打架。

═══ 相对参考实现 bazi_score.py 修掉的三个问题 ═══
(a) 原实现的「贴身 ×1.2」只在成分克泄日主时加、帮身时不加，等于系统性地把天平
    压向身弱。本包把贴身加权做成与生克无关的位置因子（月干、日支各 ×1.2），
    见 ATTACH_FACTOR，帮身耗身一视同仁。
(b) 原实现「日主根气分 +8」与「地支藏干里的比劫分」重复计一次同一个根。
    **本包二选一，保留「藏干比劫分」，取消额外的根气分**（DAY_ROOT_BONUS = 0.0）：
    藏干展开已经按本/中/余分级计过这个根，再加一次等于同一个字算两遍。
    根的有无另行以布尔闸 Strength.has_root 表达，不混进连续分。
(c) 原实现对所有地支本气一刀切。子卯酉只藏一个字、气最纯，本包给纯气支加权
    PURE_ZHI_COEF，见 shushu.core.ganzhi.PURE_ZHI 的注释。

另：原实现的「杂气湿燥土 ×0.65」同样只作用于耗身一侧，与 (a) 是同一类不对称，
本包不予实现。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from ..core import ganzhi, wuxing
from .shishen import TEN_GODS, ten_god  # 十神一律走 shishen 层，本模块不重写一份

__all__ = [
    "Quad", "POSITIONS", "TEN_GODS", "Component", "PowerItem", "Strength",
    "components", "element_power", "day_master_strength", "ten_god_power",
    "climate_index", "ten_god", "validate_quad",
]

#: 四柱输入：键为 year/month/day/hour，值为 (天干, 地支)。与 shushu.bazi.interact 同型。
Quad = Mapping[str, tuple[str, str]]

POSITIONS: tuple[str, ...] = ("year", "month", "day", "hour")

Category = Literal["strong", "slightly_strong", "balanced", "slightly_weak", "weak"]
Side = Literal["support", "drain"]

# ── 权重常量 ────────────────────────────────────────────────────
# 下列系数除注明出处者外，一律是**本包取值，可调**：古籍只说孰重孰轻，不给数字。

#: 天干基础分。本包取值，可调。
GAN_BASE: float = 10.0
#: 地支基础分。地支藏干、通根，故略重于天干。本包取值，可调。
ZHI_BASE: float = 12.0

#: 根气系数：本气、中气、余气。三档轻重的次第出自传统「人元」本中余之分，
#: 具体数值为本包取值，可调。
ROOT_COEF: dict[str, float] = {"本": 1.0, "中": 0.5, "余": 0.3}

#: 纯气支（子卯酉）本气加权。出处见 shushu.core.ganzhi.PURE_ZHI：
#: 纯气支按 8 计、杂气支本气按 5 计，8/5 = 1.6。本包取此比值，可调。
PURE_ZHI_COEF: float = 1.6

#: 月令配重。《子平真诠·论用神》「八字用神，专求月令」——月令为提纲，权重最重。
#: 倍数 2.0 为本包取值，可调。
MONTH_WEIGHT: float = 2.0

#: 人元司令加权：月令藏干中当令的那一个另加权。分日之说出自人元司令分日表
#: （见 shushu.data.siling）。倍数为本包取值，可调。
#:
#: 取 1.1 而不是更大，是因为司令只该**细化**月令藏干的粗细，不该把结论推翻：
#: 月令藏干本来就已吃了 MONTH_WEIGHT=2.0，再乘一个大倍数，足以把 ratio 推过分档线。
#: 实测（500 张随机盘 × 每张的各个月令藏干 = 1159 对「传 / 不传司令」）：
#: 倍数 1.5 时有 4.7% 的对子给出方向相克的用神，1.1 时降到 0.9%，
#: 且残余的几例都伴随旺衰档位本身的跨线。见 tests/test_yongshen.py 的司令稳定性测试。
SILING_BOOST: float = 1.1

#: 贴身加权：月干、日支贴近日主，力量传导最直接。**与生克无关**，帮身耗身同加。
#: 倍数为本包取值，可调。
ATTACH_FACTOR: float = 1.2
#: 受贴身加权的位置
ATTACH_GAN_POS: frozenset[str] = frozenset({"month"})
ATTACH_ZHI_POS: frozenset[str] = frozenset({"day"})

#: 虚透无根折减：天干在全盘地支无同五行之根则力薄。「有根」之说通行于子平诸家，
#: 折减倍数为本包取值，可调。
VIRTUAL_FLOAT_FACTOR: float = 0.5

#: 日主根气额外加分。见模块 docstring (b)：本包取 0.0，即不叠加。可调。
DAY_ROOT_BONUS: float = 0.0

#: 旺衰五档的分界（身弱/偏弱、偏弱/中和、中和/偏旺、偏旺/身旺），
#: 作用在归一化后的 ratio = 同党/(同党+异党) 上。
#: 参考实现用未归一的绝对净值 ±20/±50 分档，「身旺」只占 6.8%，分布明显偏斜。
#: 本包改为归一化后分档，阈值按 3000 张随机盘的 ratio 分位数标定（20/40/70/90 分位），
#: 五档各占约 20/20/30/20/10。注意分布的中位数在 0.39 而非 0.50：
#: 同党只占五种关系中的两种（比劫、印），异党占三种，本就不对称，
#: 所以门槛按实际分布定，不按 0.5 硬切。本包取值，可调。
RATIO_BANDS: tuple[float, float, float, float] = (0.26, 0.35, 0.48, 0.61)

#: 强根布尔闸：日主坐这三个十二长生位即算得强根。《三命通会》以长生、临官、帝旺
#: 为天干得地之位。本包取这三位，可调。
ROOT_DISHI: frozenset[str] = frozenset({"长生", "临官", "帝旺"})
#: 或：全盘藏干中与日主同五行者超过这个个数，也算有根。本包取值，可调。
ROOT_COUNT_TH: int = 2

# ── 寒暖燥湿 ────────────────────────────────────────────────────
# 调候之说出自《穷通宝鉴》（《栏江网》）：金水为寒、木火为暖，辰丑为湿土、未戌为燥土。
# 本包把它折成一个标量，各字的取值为**本包取值，可调**。
CLIMATE_ZHI: dict[str, float] = {
    "子": -1.0, "丑": -0.8, "寅": 0.3, "卯": 0.1, "辰": -0.4, "巳": 0.9,
    "午": 1.0, "未": 0.7, "申": -0.1, "酉": -0.3, "戌": 0.4, "亥": -0.9,
}
CLIMATE_GAN: dict[str, float] = {
    "甲": 0.2, "乙": 0.1, "丙": 1.0, "丁": 0.8, "戊": 0.3,
    "己": -0.2, "庚": -0.2, "辛": -0.3, "壬": -0.9, "癸": -0.8,
}
#: 月令定一年寒暖，权重最重；其余地支次之；天干最轻。本包取值，可调。
CLIMATE_W_MONTH_ZHI: float = 3.0
CLIMATE_W_ZHI: float = 1.5
CLIMATE_W_GAN: float = 1.0

# ── 输入校验 ────────────────────────────────────────────────────
def validate_quad(quad: Quad) -> None:
    """四柱输入合法性。不合法抛 ValueError。"""
    for pos in POSITIONS:
        cell = quad.get(pos)
        if not cell or len(cell) != 2:
            raise ValueError(f"缺少或不完整的柱：{pos!r}")
        gan, zhi = cell
        if gan not in ganzhi.GAN:
            raise ValueError(f"{pos} 柱天干不合法：{gan!r}")
        if zhi not in ganzhi.ZHI:
            raise ValueError(f"{pos} 柱地支不合法：{zhi!r}")


# ── 成分 ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Component:
    """全盘拆出的一个力量成分。"""

    pos: str                 #: year/month/day/hour
    kind: Literal["干", "支"]
    char: str                #: 该柱上这个字（天干或地支）
    gan: str                 #: 折算到的天干（地支取藏干）
    level: str               #: 天干为「透」，地支为 本/中/余
    weight: float
    tags: tuple[str, ...]    #: 加权理由的短标签


def _has_root(gan: str, quad: Quad) -> bool:
    """这个天干在全盘地支藏干里有没有同五行的根。"""
    wx = ganzhi.GAN_WUXING[gan]
    return any(
        ganzhi.GAN_WUXING[hg] == wx
        for pos in POSITIONS
        for hg, _ in ganzhi.HIDDEN[quad[pos][1]]
    )


def components(quad: Quad, *, month_siling: str | None = None,
               include_day_gan: bool = True) -> list[Component]:
    """把四柱拆成带权重的成分表。旺衰、五行分布、十神力量都建在这上面。

    month_siling 为月令司令的藏干（见 shushu.core.ganzhi.siling_gan）；
    不传则只按本中余三档，不另加司令权。
    """
    validate_quad(quad)
    out: list[Component] = []
    for pos in POSITIONS:
        gan, zhi = quad[pos]
        # 天干
        if pos != "day" or include_day_gan:
            w = GAN_BASE
            tags: list[str] = []
            if not _has_root(gan, quad):
                w *= VIRTUAL_FLOAT_FACTOR
                tags.append("虚透")
            if pos in ATTACH_GAN_POS:
                w *= ATTACH_FACTOR
                tags.append("贴身")
            out.append(Component(pos, "干", gan, gan, "透", w, tuple(tags)))
        # 地支藏干
        is_month = pos == "month"
        pure = zhi in ganzhi.PURE_ZHI
        for hg, level in ganzhi.HIDDEN[zhi]:
            w = ZHI_BASE * ROOT_COEF[level]
            tags = []
            if pure:
                w *= PURE_ZHI_COEF
                tags.append("纯气")
            if is_month:
                w *= MONTH_WEIGHT
                tags.append("月令")
                if month_siling and hg == month_siling:
                    w *= SILING_BOOST
                    tags.append("司令")
            if pos in ATTACH_ZHI_POS:
                w *= ATTACH_FACTOR
                tags.append("贴身")
            out.append(Component(pos, "支", zhi, hg, level, w, tuple(tags)))
    return out


# ── 五行分布 ────────────────────────────────────────────────────
def element_power(quad: Quad, *, month_siling: str | None = None) -> dict[str, float]:
    """全盘五行力量分布。含日主自身的天干，五个键恒在，缺者为 0.0。"""
    out = {w: 0.0 for w in wuxing.ORDER}
    for c in components(quad, month_siling=month_siling):
        out[ganzhi.GAN_WUXING[c.gan]] += c.weight
    return {k: round(v, 3) for k, v in out.items()}


# ── 日主旺衰 ────────────────────────────────────────────────────
@dataclass(frozen=True)
class PowerItem:
    """旺衰打分的一条明细。"""

    pos: str
    source: str            #: 如「月支辰藏戊」
    gan: str
    relation: str          #: 比劫/印/食伤/财/官杀
    side: Side
    score: float
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Strength:
    """日主旺衰。"""

    support: float         #: 同党（比劫 + 印）合计
    drain: float           #: 异党（食伤 + 财 + 官杀）合计
    net: float             #: support - drain，保留以便外部比较，分档不用它
    ratio: float           #: support / (support + drain)，分档用这个
    label: str             #: 身旺/偏旺/中和/偏弱/身弱
    category: Category
    has_root: bool         #: 强根布尔闸，与 ratio 并联，不参与连续分
    root_note: tuple[str, ...]
    items: tuple[PowerItem, ...]


def day_master_strength(quad: Quad, *, month_siling: str | None = None) -> Strength:
    """日主旺衰。

    同党 = 比劫 + 印，异党 = 食伤 + 财 + 官杀（《滴天髓》「体用」之分党）。
    分档作用在归一化的 ratio 上，不用未归一的净值，见模块 docstring。

    强根闸 has_root 与 ratio 并联、不相乘：日主在任一地支得长生/临官/帝旺，
    或全盘藏干中同五行者多于 ROOT_COUNT_TH 个，即为 True。
    从格、专旺是否成立要看这一闸，不能只看连续分。
    """
    validate_quad(quad)
    day_gan = quad["day"][0]
    day_wx = ganzhi.GAN_WUXING[day_gan]

    items: list[PowerItem] = []
    support = drain = 0.0
    for c in components(quad, month_siling=month_siling, include_day_gan=False):
        rel = wuxing.relation(ganzhi.GAN_WUXING[c.gan], day_wx)
        side: Side = "support" if rel in wuxing.SUPPORT else "drain"
        score = c.weight
        if side == "support" and rel == "比劫" and c.kind == "支":
            score += DAY_ROOT_BONUS * ROOT_COEF[c.level]   # 见 docstring (b)：默认 0.0
        src = f"{c.pos}{c.kind}{c.char}" + (f"藏{c.gan}" if c.kind == "支" else "")
        items.append(PowerItem(c.pos, src, c.gan, rel, side, round(score, 3), c.tags))
        if side == "support":
            support += score
        else:
            drain += score

    total = support + drain
    ratio = support / total if total > 0 else 0.5
    lo2, lo1, hi1, hi2 = RATIO_BANDS
    if ratio >= hi2:
        label, cat = "身旺", "strong"
    elif ratio >= hi1:
        label, cat = "偏旺", "slightly_strong"
    elif ratio <= lo2:
        label, cat = "身弱", "weak"
    elif ratio <= lo1:
        label, cat = "偏弱", "slightly_weak"
    else:
        label, cat = "中和", "balanced"

    # 强根闸
    notes: list[str] = []
    rooted = False
    for pos in POSITIONS:
        zhi = quad[pos][1]
        d = ganzhi.dishi(day_gan, zhi)
        if d in ROOT_DISHI:
            rooted = True
            notes.append(f"{pos}支{zhi}·{d}")
    same_cnt = sum(
        1
        for pos in POSITIONS
        for hg, _ in ganzhi.HIDDEN[quad[pos][1]]
        if ganzhi.GAN_WUXING[hg] == day_wx
    )
    if same_cnt > ROOT_COUNT_TH:
        rooted = True
        notes.append(f"比劫墓库根×{same_cnt}")

    return Strength(
        support=round(support, 3), drain=round(drain, 3),
        net=round(support - drain, 3), ratio=round(ratio, 4),
        label=label, category=cat, has_root=rooted,
        root_note=tuple(notes), items=tuple(items),
    )


# ── 十神力量 ────────────────────────────────────────────────────
def ten_god_power(quad: Quad, *, month_siling: str | None = None) -> dict[str, float]:
    """十个十神各自的力量。日干自身不计（它是被衡量的主体）。十个键恒在，缺者 0.0。"""
    validate_quad(quad)
    day_gan = quad["day"][0]
    out = {t: 0.0 for t in TEN_GODS}
    for c in components(quad, month_siling=month_siling, include_day_gan=False):
        out[ten_god(c.gan, day_gan)] += c.weight
    return {k: round(v, 3) for k, v in out.items()}


# ── 寒暖燥湿 ────────────────────────────────────────────────────
def climate_index(quad: Quad) -> float:
    """寒暖燥湿标量，负数偏寒湿、正数偏燥暖，取值落在 [-1, 1]。

    《穷通宝鉴》以寒暖燥湿论调候：金水寒、木火暖，辰丑湿、未戌燥。
    本包按月令为重、余支次之、天干最轻加权平均，系数为本包取值，可调。
    """
    validate_quad(quad)
    num = den = 0.0
    for pos in POSITIONS:
        gan, zhi = quad[pos]
        wz = CLIMATE_W_MONTH_ZHI if pos == "month" else CLIMATE_W_ZHI
        num += CLIMATE_ZHI[zhi] * wz
        den += wz
        num += CLIMATE_GAN[gan] * CLIMATE_W_GAN
        den += CLIMATE_W_GAN
    return round(num / den, 4) if den else 0.0
