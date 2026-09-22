"""格局：月令取格、顺逆用相神、成象扫描。

三个函数各管一件事：
- month_pattern  以月令定格名，《子平真诠·论用神》「八字用神，专求月令」。
- pattern_ops    这个格该顺用还是逆用、相神是谁，《子平真诠·论用神》原文成表。
- scan_patterns  全盘生克链的成象扫描（杀印相生、食神制杀……），按十神力量判定。

scan_patterns **不读取喜忌**。参考实现 bazi_score.scan_patterns 的财印一组是按
useful/avoid 翻转吉凶的，等于让格局倒过来依赖取用；取用一错，格局跟着错。
本包把这一组改判在「印的力量相对日主是否已过」上，只依赖旺衰量化，不依赖取用。
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Literal

from ..core import ganzhi
from . import strength as _st
from .strength import Quad, ten_god

__all__ = [
    "Pattern", "PatternOps", "PatternHit", "OpsConflict",
    "month_pattern", "pattern_ops", "scan_patterns", "ops_conflicts", "PATTERN_OPS",
]

# ── 成象扫描的门槛（本包取值，可调）──────────────────────────────
# 力量刻度沿用 tianzhi_core.bazi.strength 的权重：一个透干 ≈ 10、一个本气根 ≈ 12。
#: 「现」——够资格参与成象的门槛，约等于一个透干或一个本气根
PRESENT_TH: float = 10.0
#: 「成势／为病」的门槛，约等于两个根
STRONG_TH: float = 20.0
#: 生克链两端力量之比超过它，标注「X轻Y重」
IMBALANCE_RATIO: float = 2.5

Mode = Literal["顺", "逆"]
Kind = Literal["吉", "病"]


# ── 一、月令取格 ────────────────────────────────────────────────
@dataclass(frozen=True)
class Pattern:
    """月令取出的格。"""

    name: str
    ten_god: str                      #: 定格所用那个天干的十神；建禄/阳刃格为比肩或劫财
    gan: str                          #: 定格所用的那个藏干
    month_zhi: str
    basis: Literal["本气", "司令", "透干", "建禄", "阳刃"]
    transparent_at: tuple[str, ...]   #: 该藏干透于哪几个位置（year/month/hour）
    evidence: tuple[str, ...]


def month_pattern(quad: Quad, *, month_siling: str | None = None) -> Pattern:
    """月令取格。《子平真诠·论用神》：「八字用神，专求月令」。

    四步：
    1. 取月支藏干，各自对日主取十神；
    2. 以本气十神为基础格（传入 month_siling 时改以司令者为基础，见《论用神》
       「以支中所藏之神，透干会支」之意，司令分日表为后世细化）；
    3. 藏干若透于年、月、时干，则以透出者定格（本气透 > 中气透 > 余气透）；
    4. 月支为日主临官则取建禄格、帝旺则取阳刃格。阳刃只给阳干——阴干有无刃
       各家分歧，本包不替使用者选边，见 tianzhi_core.core.ganzhi.YANGREN。
    """
    _st.validate_quad(quad)
    day_gan = quad["day"][0]
    month_zhi = quad["month"][1]
    hidden = ganzhi.HIDDEN[month_zhi]

    # 第 4 步优先：禄刃由月支本身决定，不待透干。《子平真诠·论建禄月劫》。
    dishi = ganzhi.dishi(day_gan, month_zhi)
    if dishi == "临官":
        return Pattern(
            name="建禄格", ten_god=ten_god(day_gan, day_gan), gan=day_gan,
            month_zhi=month_zhi, basis="建禄", transparent_at=(),
            evidence=(f"月令{month_zhi}为{day_gan}之临官", "子平真诠·论建禄月劫"),
        )
    if dishi == "帝旺" and ganzhi.YANGREN.get(day_gan) == month_zhi:
        return Pattern(
            name="阳刃格", ten_god=ten_god(day_gan, day_gan), gan=day_gan,
            month_zhi=month_zhi, basis="阳刃", transparent_at=(),
            evidence=(f"月令{month_zhi}为{day_gan}之帝旺·阳刃", "子平真诠·论阳刃"),
        )

    # 第 1、2 步：基础格
    base_gan = hidden[0][0]
    basis: Literal["本气", "司令", "透干", "建禄", "阳刃"] = "本气"
    if month_siling and any(hg == month_siling for hg, _ in hidden):
        base_gan = month_siling
        basis = "司令"

    # 第 3 步：透干定格
    visible_pos = {
        pos: quad[pos][0] for pos in ("year", "month", "hour")
    }
    chosen_gan, chosen_at = base_gan, ()
    for hg, _level in hidden:
        at = tuple(p for p, g in visible_pos.items() if g == hg)
        if at:
            chosen_gan, chosen_at = hg, at
            basis = "透干"
            break

    tg = ten_god(chosen_gan, day_gan)
    name = "月劫格" if tg in ("比肩", "劫财") else f"{tg}格"
    if basis == "透干":
        ev = (f"月令{month_zhi}藏{chosen_gan}·{tg}",
              "透于" + "、".join(chosen_at), "子平真诠·论用神")
    else:
        ev = (f"月令{month_zhi}{basis}{chosen_gan}·{tg}", "未见透出", "子平真诠·论用神")
    return Pattern(name=name, ten_god=tg, gan=chosen_gan, month_zhi=month_zhi,
                   basis=basis, transparent_at=chosen_at, evidence=ev)


# ── 二、顺用逆用与相神 ──────────────────────────────────────────
@dataclass(frozen=True)
class PatternOps:
    """一个格的顺逆与相神。"""

    name: str
    mode: Mode
    generate: tuple[str, ...]   #: 相生之神（顺用者生之、逆用者制之的那一路）
    protect: tuple[str, ...]    #: 护格之神
    taboo: tuple[str, ...]      #: 忌神（十神名）
    note: str
    source: str = "子平真诠·论用神"


#: 《子平真诠·论用神》原文：
#:   「財喜食神以相生，生官以護財；官喜透財以相生，生印以護官；
#:     印喜官煞以相生，劫才以護印；食喜身旺以相生，生財以護食。
#:     不善而逆用之，則七煞喜食神以制伏，忌財印以資扶；傷官喜佩印以制伏，生財以化傷；
#:     陽刃喜官煞以制伏，忌官煞之俱無；月劫喜透官以制伏，利用財而透食以化劫。」
#: 下表逐句成文，忌神一栏在原文未点名处按「克去相神者」补齐，并在 note 注明。
PATTERN_OPS: dict[str, PatternOps] = {
    "财格": PatternOps(
        "财格", "顺", ("食神",), ("正官",), ("比肩", "劫财"),
        "财喜食神以相生，生官以护财；忌比劫分夺",
    ),
    "正官格": PatternOps(
        "正官格", "顺", ("正财", "偏财"), ("正印", "偏印"), ("伤官", "七杀"),
        "官喜透财以相生，生印以护官；伤官见官、官杀混杂为破",
    ),
    "印格": PatternOps(
        "印格", "顺", ("正官", "七杀"), ("劫财",), ("正财", "偏财"),
        "印喜官煞以相生，劫财以护印；忌财星坏印",
    ),
    "食神格": PatternOps(
        "食神格", "顺", ("比肩", "劫财"), ("正财", "偏财"), ("偏印",),
        "食喜身旺以相生，生财以护食；忌枭神夺食",
    ),
    "七杀格": PatternOps(
        "七杀格", "逆", ("食神",), ("食神",), ("正财", "偏财", "正印", "偏印"),
        "七杀喜食神以制伏，忌财印以资扶",
    ),
    "伤官格": PatternOps(
        "伤官格", "逆", ("正印", "偏印"), ("正财", "偏财"), ("正官",),
        "伤官喜佩印以制伏，生财以化伤；忌见正官",
    ),
    "阳刃格": PatternOps(
        "阳刃格", "逆", ("正官", "七杀"), ("正官", "七杀"), (),
        "阳刃喜官煞以制伏，忌官煞之俱无——原文之忌在于「无」，故忌神一栏空",
    ),
    "月劫格": PatternOps(
        "月劫格", "逆", ("正官",), ("正财", "偏财", "食神"), ("伤官",),
        "月劫喜透官以制伏，利用财而透食以化劫；伤官克去所透之官为破",
    ),
}

#: 格名归并：正偏财同归财格、正偏印同归印格、建禄同月劫、比肩格同月劫。
#: 《子平真诠》财印各自合论，建禄月劫同篇。
PATTERN_ALIAS: dict[str, str] = {
    "正财格": "财格", "偏财格": "财格",
    "正印格": "印格", "偏印格": "印格",
    "建禄格": "月劫格", "比肩格": "月劫格", "劫财格": "月劫格",
}


def pattern_ops(pattern_name: str) -> PatternOps | None:
    """这个格顺用还是逆用、相神是谁。不认识的格名返回 None。"""
    key = PATTERN_ALIAS.get(pattern_name, pattern_name)
    return PATTERN_OPS.get(key)


# ── 三、成象扫描 ────────────────────────────────────────────────
@dataclass(frozen=True)
class PatternHit:
    """扫到的一个成象。chain 是短标签序列，不是叙述句。"""

    name: str
    kind: Kind
    actor: str                  #: 主动发起生克的十神，用于同一主动者择一
    power: float
    chain: tuple[str, ...]
    role: Literal["主象", "参考"]


def _imbalance(a: float, b: float, na: str, nb: str) -> tuple[str, ...]:
    if a <= 0 or b <= 0:
        return ()
    (hi, hn), (lo, ln) = ((a, na), (b, nb)) if a >= b else ((b, nb), (a, na))
    return (f"{ln}轻{hn}重",) if hi / lo >= IMBALANCE_RATIO else ()



#: 具体十神归入成象所用的大类
_GROUP_OF: dict[str, str] = {
    "正财": "财", "偏财": "财",
    "正官": "官杀", "七杀": "官杀",
    "正印": "印", "偏印": "印",
    "食神": "食伤", "伤官": "伤官",
    "比肩": "比劫", "劫财": "劫财",
}


@dataclass(frozen=True)
class OpsConflict:
    """通用顺逆规则与本盘成象相抵的一处。

    `pattern_ops` 给的是《子平真诠》对某一格的通行取舍，它只认格名、不看盘；
    `scan_patterns` 扫的是这张盘上实际成立的象，它看盘。两者相抵时**以成象为准**——
    规则说的是常态，成象说的是这一张。

    最常见的一种：印格通例忌财（财能坏印），但若这张盘印已过旺成病，财损其印反倒是药。
    """

    ten_god: str      #: 被通用规则列为忌神、却在本盘成了吉象的那一路
    hit: str          #: 是哪个成象让它翻了案
    chain: tuple[str, ...]
    note: str = "通用规则不看盘，成象看盘；两者相抵以成象为准"


def ops_conflicts(ops: PatternOps | None,
                  hits: Sequence[PatternHit]) -> tuple[OpsConflict, ...]:
    """找出「通用规则列为忌、本盘却成吉象」的那几路。

    成象的 actor 记的是大类（财、印、官杀），通用规则的忌神记的是具体十神
    （正财、偏财），所以按「具体十神属于哪一大类」来配对。

    调用方拿到非空结果时，应当按成象讲，不要把通用忌神照搬给用户，
    否则同一页上会出现「最怕财」与「财损印是吉」两句自相矛盾的话。
    """
    if not ops or not hits:
        return ()
    good = {h.actor: h for h in hits if h.kind == "吉" and h.actor}
    out: list[OpsConflict] = []
    for taboo in ops.taboo:
        hit = good.get(_GROUP_OF.get(taboo, taboo))
        if hit is not None:
            out.append(OpsConflict(ten_god=taboo, hit=hit.name, chain=hit.chain))
    return tuple(out)


def scan_patterns(quad: Quad, *, month_siling: str | None = None) -> list[PatternHit]:
    """成象扫描：链条验证 + 力量门槛 + 同一主动十神互斥择优。

    每个成象都要有真实力量支撑（各方均须过 PRESENT_TH），不凭空套名。
    只依赖旺衰与十神力量，不依赖取用结果。
    """
    _st.validate_quad(quad)
    day_gan = quad["day"][0]
    st = _st.ten_god_power(quad, month_siling=month_siling)
    body = _st.day_master_strength(quad, month_siling=month_siling)
    weak = body.category in ("weak", "slightly_weak")
    strong = body.category in ("strong", "slightly_strong")

    yin = st["正印"] + st["偏印"]
    sha, guan = st["七杀"], st["正官"]
    cai = st["正财"] + st["偏财"]
    shi, shang = st["食神"], st["伤官"]
    shishang = shi + shang
    bijie = st["比肩"] + st["劫财"]
    ok = lambda x: x >= PRESENT_TH

    hits: list[dict] = []

    def hit(name: str, kind: Kind, actor: str, power: float, *chain: str) -> None:
        hits.append({"name": name, "kind": kind, "actor": actor,
                     "power": round(power, 1), "chain": tuple(c for c in chain if c)})

    # 印绶组
    if ok(sha) and ok(yin) and not strong:
        hit("杀印相生", "吉", "七杀", sha + yin, "七杀", "生印", "印化身",
            *_imbalance(sha, yin, "杀", "印"))
    if ok(guan) and ok(yin):
        hit("官印相生", "吉", "正官", guan + yin, "正官", "生印",
            *_imbalance(guan, yin, "官", "印"))
    if ok(shang) and ok(yin):
        hit("伤官佩印", "吉", "印", yin + shang, "印", "制伤官", "护身",
            *_imbalance(yin, shang, "印", "伤"))
    # 食伤制杀（食、伤互斥取主导）
    if ok(shishang) and ok(sha):
        if shi >= shang:
            hit("食神制杀", "吉", "食神", shi + sha, "食神", "制七杀",
                *_imbalance(shi, sha, "食", "杀"))
        else:
            hit("伤官驾杀", "吉", "伤官", shang + sha, "伤官", "驾七杀",
                *_imbalance(shang, sha, "伤", "杀"))
    # 食伤生财（互斥）
    if ok(shishang) and ok(cai):
        if shi >= shang:
            hit("食神生财", "吉", "食神", shi + cai, "食神", "生财",
                *_imbalance(shi, cai, "食", "财"))
        else:
            hit("伤官生财", "吉", "伤官", shang + cai, "伤官", "生财",
                *_imbalance(shang, cai, "伤", "财"))
    # 财官
    if ok(cai) and ok(sha) and weak:
        hit("财滋弱杀", "吉", "财", cai + sha, "财", "滋七杀", "身弱")
    if ok(cai) and ok(guan) and strong:
        hit("财旺生官", "吉", "财", cai + guan, "财", "生正官", "身旺任之")
    # 财克印：吉凶只看印对日主是否已过，不读喜忌（见模块 docstring）
    if ok(cai) and ok(yin):
        if not weak and yin >= STRONG_TH:
            hit("财损印", "吉", "财", cai + yin, "财", "损重印", "去病")
        elif weak and yin >= PRESENT_TH:
            hit("贪财坏印", "病", "财", cai + yin, "财", "夺生身之印", "身弱")
    # 过旺为病
    if weak and cai >= STRONG_TH + 3 and cai > yin + bijie:
        hit("财多身弱", "病", "财", cai, "财成势", "日主难任")
    if weak and sha >= STRONG_TH and sha > yin:
        hit("杀重身轻", "病", "七杀", sha, "七杀重", "印化不及")
    if weak and yin >= STRONG_TH + 4 and yin > sha + guan + cai:
        hit("母多灭子", "病", "印", yin, "印过重", "反窒日主")
    if ok(shang) and ok(guan):
        hit("伤官见官", "病", "伤官", shang + guan, "伤官", "与正官并见相战")
    if ok(shang) and (sha + guan) < PRESENT_TH:
        hit("伤官伤尽", "吉", "伤官", shang, "伤官独清", "官杀近无")
    if ok(guan) and ok(sha):
        hit("官杀混杂", "病", "官杀", guan + sha, "正官", "七杀", "并见混杂")
    zhis = [quad[p][1] for p in _st.POSITIONS]
    if ganzhi.YANGREN.get(day_gan) in zhis and ok(sha):
        hit("羊刃驾杀", "吉", "比劫", bijie + sha,
            f"羊刃{ganzhi.YANGREN[day_gan]}", "帮身", "驾七杀")
    if strong and ok(shishang):
        hit("泄秀", "吉", "食伤", shishang, "身强", "食伤吐秀", "流通")
    if weak and shishang >= STRONG_TH and shishang > yin + bijie:
        hit("食伤泄气太过", "病", "食伤", shishang, "食伤过重", "泄身太过")
    if weak and STRONG_TH <= yin < STRONG_TH + 4 and yin > sha + guan + cai:
        hit("印重身弱", "病", "印", yin, "印偏重", "受生不及泄秀")

    # 同一主动十神只留最有力者，再按力量定主象
    best: dict[str, dict] = {}
    for h in hits:
        if h["actor"] not in best or h["power"] > best[h["actor"]]["power"]:
            best[h["actor"]] = h
    kept = sorted(best.values(), key=lambda h: (-h["power"], h["name"]))
    return [
        PatternHit(name=h["name"], kind=h["kind"], actor=h["actor"], power=h["power"],
                   chain=h["chain"], role="主象" if i == 0 else "参考")
        for i, h in enumerate(kept)
    ]
