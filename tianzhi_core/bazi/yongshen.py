"""取用：把量化层与格局层收口成一组「用喜忌仇闲」。

═══ 取用优先级：本包选「算准网」一派，理由在下 ═══
两个权威口径互相矛盾：
  算准网：格局 > 扶抑 > 通关 > 病药 > 调候
  HeiGe ：从格专旺 > 调候 ≥ 扶抑 > 通关 > 病药
本包默认取前者（DEFAULT_PRIORITY），两条理由：
  1. 调候若能越过扶抑，就会出现「辛金生子月、水旺身弱，却因《穷通宝鉴》辛子取丙
     而把七杀火排到喜用首位」这类结论——救寒之药反成克身之病。调候表只由日干与
     月令两格决定，看不见盘里其余六个字，让它压过看得见全盘的扶抑，方法上站不住。
  2. 「格局」一档本包只放**特殊格局**（从格、专旺）：日主已无根可扶时，扶抑的前提
     自身不成立，必须先判从与不从。这一条与 HeiGe 的第一档其实一致，两派的真正分歧
     只在调候的位次上。
调候并未被丢掉：它在同档候选之间做**排序加分**（CLIMATE_TIEBREAK），并始终以
evidence 标签透出，只是不再单独顶掉扶抑的结论。
换派用 priority 参数，见 HEIGE_PRIORITY。

═══ 用喜忌仇闲 ═══
定了用神之后是纯机械推导，与流派无关：
  喜 = 生用神者，忌 = 克用神者，仇 = 生忌神者，闲 = 其余。
五行成环，这四者加闲神恰好是五行的一个双射，**天然互斥、不会重复**，
且忌神恒为一行、永不为空——中和局也有忌神。
注意「仇」与「忌」同属避忌一侧，取用落在财上时，被用神所克的那一行会落在仇位，
外部若要渲染「忌什么」，请取 YongShen.unfavorable（忌 + 仇）。

favorable / unfavorable **不是第二套口径**：它们是只读属性，分别等于 (yong, xi) 与
(ji, chou)，由五分逐字推出，不单独存储、无法与五分打架。包里不留互斥冗余。

═══ 月令司令（month_siling）═══
司令只细化月令藏干的粗细，不该翻转结论。为此做了三件事：
  1. SILING_BOOST 压到 1.1（见 strength 模块的常量注释与实测数据）；
  2. 通关档收紧到三道门槛，不再把「一行独大、另一行正克它」判成相持；
  3. 病药档要求病领先次旺 BING_MARGIN 倍，且身弱时不以日主自身为病。
实测 500 张随机盘 × 每张各个月令藏干（1159 对）：传与不传司令给出方向相克的用神
占 0.95%，且多数伴随旺衰档位本身跨线——分档是硬边界，跨线换档属预期，不是 bug。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..core import ganzhi, wuxing
from . import geju as _geju
from . import strength as _st
from . import tiaohou as _th
from .strength import Quad

__all__ = [
    "YongShen", "select", "DEFAULT_PRIORITY", "HEIGE_PRIORITY", "PRIORITY_TIERS",
]

#: 本包默认：算准网口径。「格局」一档只收从格与专旺。
DEFAULT_PRIORITY: tuple[str, ...] = ("格局", "扶抑", "通关", "病药", "调候")
#: HeiGe 口径，供换派
HEIGE_PRIORITY: tuple[str, ...] = ("格局", "调候", "扶抑", "通关", "病药")

# ── 阈值（本包取值，可调）──────────────────────────────────────
#: 从弱：同党占比低于它、且无强根，则不扶而从。《滴天髓》「从得真者只论从」。
FOLLOW_WEAK_RATIO: float = 0.12
#: 专旺/从强：同党占比高于它、且有强根。
FOLLOW_STRONG_RATIO: float = 0.88
#: 通关：两行相战，各自占全盘的份额都要够
TONGGUAN_MIN_SHARE: float = 0.22
#: 通关：两行须势均力敌，强弱之比不得超过它；一边压倒另一边时该用病药，不是通关。
#: 原取 1.20 过松，把「一行独大」的局面也判成相持，已收紧。
TONGGUAN_BALANCE_MAX: float = 1.10
#: 病药：最旺者要领先次旺者这个倍数才算「病」。压得不明显就不是病，
#: 免得两行分量咬得很近时，月令司令这类细化权重一动就换一个病、换出相反的药。
#: 本包取值，可调。
BING_MARGIN: float = 1.10
#: 扶抑·身旺：比劫要领先印这个倍数，才改以官煞为用（否则一律以财为用）。
#: 同样是防止两者咬得很近时结论摇摆。本包取值，可调。
FUYI_BIJIE_MARGIN: float = 1.15
#: 调候在同档候选间的排序加分（只排序，不改档）
CLIMATE_TIEBREAK: bool = True


@dataclass(frozen=True)
class YongShen:
    """取用结论。五个五行位互斥，合起来恰是五行全集。"""

    yong: str                   #: 用神
    xi: str                     #: 喜神 = 生用神者
    ji: str                     #: 忌神 = 克用神者
    chou: str                   #: 仇神 = 生忌神者
    xian: tuple[str, ...]       #: 闲神 = 其余
    method: str                 #: 取用依据，短标签
    evidence: tuple[str, ...]   #: 逐条短标签，不是句子

    @property
    def favorable(self) -> tuple[str, ...]:
        """喜用一侧 = (用, 喜)。只读派生，不是另一套口径，不会与五分矛盾。"""
        return (self.yong, self.xi)

    @property
    def unfavorable(self) -> tuple[str, ...]:
        """避忌一侧 = (忌, 仇)。只读派生，同上。"""
        return (self.ji, self.chou)


@dataclass(frozen=True)
class _Ctx:
    quad: Quad
    day_wx: str
    body: _st.Strength
    mass: dict[str, float]
    gods: dict[str, float]
    need: _th.ClimateNeed | None
    pattern: _geju.Pattern


@dataclass(frozen=True)
class _Pick:
    yong: str
    method: str
    evidence: tuple[str, ...]


def _climate_first(ctx: _Ctx, candidates: list[str]) -> list[str]:
    """同档候选之间用调候排序：命中调候需求的提到前面。只排序，不增删。"""
    if not CLIMATE_TIEBREAK or ctx.need is None:
        return candidates
    kept = set(ctx.need.kept)
    return [c for c in candidates if c in kept] + [c for c in candidates if c not in kept]


# ── 各档取用 ────────────────────────────────────────────────────
def _tier_geju(ctx: _Ctx) -> _Pick | None:
    """特殊格局：从格与专旺。《滴天髓》「从得真者只论从」、「一气专旺」。

    普通的月令格（财官印食……）本身不定用神，它定的是顺逆与相神，
    那一层在 tianzhi_core.bazi.geju.pattern_ops，不在这里顶替扶抑。
    """
    b = ctx.body
    if b.ratio <= FOLLOW_WEAK_RATIO and not b.has_root:
        foe = {w: p for w, p in ctx.mass.items()
               if wuxing.relation(w, ctx.day_wx) in wuxing.DRAIN}
        if foe:
            yong = max(foe, key=lambda k: foe[k])
            rel = wuxing.relation(yong, ctx.day_wx)
            return _Pick(yong, f"从格·从{rel}",
                         (f"同党占比{b.ratio:.2f}", "日主无强根", f"从其旺神·{rel}",
                          "滴天髓·从象"))
    if b.ratio >= FOLLOW_STRONG_RATIO and b.has_root:
        return _Pick(ctx.day_wx, "专旺·顺其势",
                     (f"同党占比{b.ratio:.2f}", "日主有强根", "顺势不逆"))
    return None


def _tier_fuyi(ctx: _Ctx) -> _Pick | None:
    """扶抑。身弱扶之、身旺抑之；中和不归这一档。

    身弱一律以比劫为用：喜神随之落在印上，喜用恰是「印比一路」。
    若改以印为用，喜神会落到官杀（生印者），与身弱的盘意相反——
    这是机械五分法下唯一自洽的选法。
    身旺以财为用（喜落食伤、忌落比劫、仇落印），比劫独重时改以官杀为用
    （《子平真诠·论用神》：阳刃、月劫皆逆用，喜官煞以制伏）。
    """
    b = ctx.body
    if b.category in ("weak", "slightly_weak"):
        return _Pick(ctx.day_wx, "扶抑·身弱扶",
                     (f"同党占比{b.ratio:.2f}", "用比劫·喜印"))
    if b.category in ("strong", "slightly_strong"):
        cai = wuxing.KE[ctx.day_wx]
        guansha = wuxing.KE_ME[ctx.day_wx]
        bijie = ctx.gods["比肩"] + ctx.gods["劫财"]
        yin = ctx.gods["正印"] + ctx.gods["偏印"]
        jie_leads = bijie > yin * FUYI_BIJIE_MARGIN
        cands = [guansha, cai] if jie_leads else [cai, guansha]
        why = "劫重·官煞制之" if jie_leads else "财制印比"
        ordered = _climate_first(ctx, cands)
        tag = ("调候合",) if ctx.need and ordered[0] in ctx.need.kept else ()
        src = ("子平真诠·论用神",) if jie_leads else ()
        return _Pick(ordered[0], "扶抑·身旺抑",
                     (f"同党占比{b.ratio:.2f}", why) + tag + src)
    return None


def _tier_tongguan(ctx: _Ctx) -> _Pick | None:
    """通关：两行相战而势均力敌，取居中一行泄强生弱。《滴天髓·通关》之意。

    三道门槛，缺一不通关——前两道是修 bug 补的，原先只有份额与均势两条，
    把「一行独大、另一行正在克它」的局面也判成了相持：

    1. 两行份额都够（TONGGUAN_MIN_SHARE）且势均力敌（TONGGUAN_BALANCE_MAX）。
    2. **相战的两行都不是全盘最旺的那一行（病）。** 一行独大时是病药的局面，
       该去病而不是拆架；《神峰通考·病药说》「格中如去病，财禄两相随」。
    3. **通关神不得生病。** 通关是把敌意引通，若引出来的那一行正是病，
       越通病越重——例如水为病、土正在制水时取金通关，金反过来生水。
    """
    total = sum(ctx.mass.values())
    if total <= 0:
        return None
    bing = max(ctx.mass, key=lambda k: ctx.mass[k])   # 通关只需知道谁最旺，不要求领先幅度
    best: tuple[float, str, str, str] | None = None
    for a, b in wuxing.KE.items():           # a 克 b
        pa, pb = ctx.mass[a], ctx.mass[b]
        if min(pa, pb) <= 0:
            continue
        if pa / total < TONGGUAN_MIN_SHARE or pb / total < TONGGUAN_MIN_SHARE:
            continue
        if max(pa, pb) / min(pa, pb) > TONGGUAN_BALANCE_MAX:
            continue
        if bing in (a, b):                   # 门槛 2：病在其中，走病药
            continue
        mid = wuxing.SHENG[a]                # a 生 mid、mid 生 b
        if wuxing.SHENG.get(mid) != b:
            continue
        if wuxing.SHENG[mid] == bing:        # 门槛 3：通关神生病，否决
            continue
        cand = (pa + pb, a, b, mid)
        if best is None or cand[0] > best[0]:
            best = cand
    if best is None:
        return None
    _, a, b, mid = best
    return _Pick(mid, "通关",
                 (f"{a}{b}相战", f"通关·{mid}", f"非病·{bing}不与", "滴天髓·通关"))


def _bing_of(ctx: _Ctx) -> str | None:
    """全盘之病：最旺且领先次旺 BING_MARGIN 倍的那一行。压得不明显则无病。

    身弱时日主自身那一行不作病：《神峰通考·病药说》的「病」指太过之神，
    日主不旺就谈不上太过，否则会推出「去掉自己」这种自相矛盾的药。
    """
    pool = dict(ctx.mass)
    if ctx.body.category in ("weak", "slightly_weak"):
        pool.pop(ctx.day_wx, None)
    pool = {k: v for k, v in pool.items() if v > 0}
    if not pool:
        return None
    ranked = sorted(pool.items(), key=lambda kv: (-kv[1], wuxing.ORDER.index(kv[0])))
    if len(ranked) > 1 and ranked[0][1] < ranked[1][1] * BING_MARGIN:
        return None
    return ranked[0][0]


def _tier_bingyao(ctx: _Ctx) -> _Pick | None:
    """病药：全盘最旺者为病，克之者为药。

    《神峰通考·病药说》：「有病方为贵，无伤不是奇；格中如去病，财禄两相随。」
    病的判定见 _bing_of：要领先得明显，且身弱时不以日主自身为病。
    """
    bing = _bing_of(ctx)
    if bing is None:
        return None
    yao = wuxing.KE_ME[bing]
    return _Pick(yao, "病药",
                 (f"病·{bing}最旺", f"药·{yao}制之", "神峰通考·病药说"))


def _tier_tiaohou(ctx: _Ctx) -> _Pick | None:
    """调候：《穷通宝鉴》查表，已按盘面剔除过（见 tiaohou.climate_need）。

    这一档不自己给出处。调候那一条每盘都会透出，不论最后取的是哪一档，出处
    就跟着它一起走（见 select），挂在这里只有调候被选中的那几盘才带得出来。
    """
    if ctx.need is None or not ctx.need.kept:
        return None
    return _Pick(ctx.need.kept[0], "调候",
                 (f"取{''.join(ctx.need.gods.gans)}",
                  f"剔除·{''.join(ctx.need.dropped) or '无'}"))


PRIORITY_TIERS: dict[str, Callable[[_Ctx], "_Pick | None"]] = {
    "格局": _tier_geju,
    "扶抑": _tier_fuyi,
    "通关": _tier_tongguan,
    "病药": _tier_bingyao,
    "调候": _tier_tiaohou,
}


# ── 收口 ────────────────────────────────────────────────────────
def select(quad: Quad, *, month_siling: str | None = None,
           priority: tuple[str, ...] = DEFAULT_PRIORITY) -> YongShen:
    """取用。按 priority 逐档尝试，第一个给出用神的档即为依据。

    默认 priority 为算准网口径，理由见模块 docstring；HEIGE_PRIORITY 为另一派。
    无论走哪一档，用喜忌仇闲都由用神机械推出，互斥且忌神非空。
    """
    _st.validate_quad(quad)
    day_gan = quad["day"][0]
    ctx = _Ctx(
        quad=quad,
        day_wx=ganzhi.GAN_WUXING[day_gan],
        body=_st.day_master_strength(quad, month_siling=month_siling),
        mass=_st.element_power(quad, month_siling=month_siling),
        gods=_st.ten_god_power(quad, month_siling=month_siling),
        need=_th.climate_need(quad),
        pattern=_geju.month_pattern(quad, month_siling=month_siling),
    )

    pick: _Pick | None = None
    for tier in priority:
        fn = PRIORITY_TIERS.get(tier)
        if fn is None:
            raise ValueError(f"未知的取用档次：{tier!r}")
        pick = fn(ctx)
        if pick is not None:
            break
    if pick is None:   # 兜底：一档都没落地时扶身，保证 yong 非空
        pick = _Pick(ctx.day_wx, "兜底·扶身", ("各档均未落地",))

    yong = pick.yong
    xi = wuxing.SHENG_ME[yong]
    ji = wuxing.KE_ME[yong]
    chou = wuxing.SHENG_ME[ji]
    xian = tuple(w for w in wuxing.ORDER if w not in (yong, xi, ji, chou))

    ev: list[str] = [f"旺衰·{ctx.body.label}", f"格·{ctx.pattern.name}"]
    if ctx.body.has_root:
        ev.append("日主有强根")
    ev.extend(pick.evidence)
    if ctx.need is not None:
        ev.append(f"调候·{''.join(ctx.need.kept)}")
        # 出处挂在这里而不是调候那一档里：调候这条每盘都出，不论最后取的是
        # 哪一档，出处也就该每盘都有；挂在档里只有调候被选中那几盘才带得出来。
        ev.append(f"穷通宝鉴·{day_gan}日{quad['month'][1]}月")
    adv = _th.adverse_gods(day_gan, quad["month"][1])
    if adv is not None:
        ev.append(f"金不换喜·{''.join(adv.xi_gans)}")
        ev.append(f"金不换忌·{''.join(adv.ji_gans)}")
        clash = [w for w in adv.ji_elements if w in (yong, xi)]
        if clash:
            ev.append(f"金不换冲突·{''.join(clash)}")   # 只标注，不翻转扶抑的结论
    ops = _geju.pattern_ops(ctx.pattern.name)
    if ops is not None:
        ev.append(f"{ops.mode}用·相神{''.join(ops.generate)}")

    return YongShen(yong=yong, xi=xi, ji=ji, chou=chou, xian=xian,
                    method=pick.method, evidence=tuple(ev))
