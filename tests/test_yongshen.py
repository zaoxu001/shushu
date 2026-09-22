"""取用与调候的测试。"""
from __future__ import annotations

import pytest
from conftest import CASE_WU_YIN, CASE_XIN_ZI, CASE_YI_CHEN, quad, random_quads

from tianzhi_core.bazi import tiaohou as T
from tianzhi_core.bazi import yongshen as Y
from tianzhi_core.core import wuxing


# ── 调候两张表 ──────────────────────────────────────────────────
def test_climate_gods_lookup():
    """《穷通宝鉴》乙木生辰月，调候取癸丙戊。"""
    g = T.climate_gods("乙", "辰")
    assert g.gans == ("癸", "丙", "戊")
    assert g.primary == "癸"
    assert g.elements == ("水", "火", "土")
    assert T.climate_gods("乙", "X") is None


def test_adverse_gods_lookup():
    """《金不换》乙木辰月：喜丙、忌癸。"""
    a = T.adverse_gods("乙", "辰")
    assert a.xi_gans == ("丙",) and a.ji_gans == ("癸",)
    assert a.xi_elements == ("火",) and a.ji_elements == ("水",)
    assert isinstance(a.dayun_xi, tuple) and isinstance(a.dayun_ji, tuple)
    assert T.adverse_gods("乙", "X") is None


def test_climate_need_drops_the_disease_element():
    """病药法剔除：这张盘水最旺，古表点名的癸水是病不是药，剔除，只留丙戊。"""
    n = T.climate_need(quad(*CASE_YI_CHEN))
    assert n.gods.gans == ("癸", "丙", "戊")
    assert n.bing == "水"
    assert n.dropped == ("水",)
    assert n.kept == ("火", "土")
    assert n.fallback is False


def test_climate_need_falls_back_when_all_dropped():
    """全被剔除时保留首用神，不让调候整条失效。"""
    n = T.climate_need(quad("丙午", "丙午", "辛巳", "甲午"))   # 辛巳月调候取壬癸甲，火最旺
    assert n is not None
    hits = [q for q in random_quads(300) if (r := T.climate_need(q)) and r.fallback]
    for q in hits[:5]:
        r = T.climate_need(q)
        assert r.kept == r.gods.elements[:1]


# ── 三个基准命例 ────────────────────────────────────────────────
def test_case_yi_chen_takes_earth_and_fire():
    """丙子 壬辰 乙酉 癸未：水多木漂、印重，正法取戊土制水、丙火泄秀。

    机械五分下用神落土、喜神落火（生土者），故喜用为火土；
    水被土所克，落在仇位——仇与忌同属避忌一侧，见 YongShen.unfavorable。
    """
    ys = Y.select(quad(*CASE_YI_CHEN))
    assert ys.yong == "土"
    assert set(ys.favorable) == {"火", "土"}
    assert "水" in ys.unfavorable
    assert ys.method == "病药"


def test_case_xin_zi_never_takes_fire():
    """壬子 壬子 辛巳 丁酉：辛金偏弱，喜用须是印比一路（土金），火不得进喜用。

    参考实现因为调候无条件插队，把《穷通宝鉴》辛子的丙火（七杀）排到喜用首位，
    这是必须修掉的 bug。本包把调候降为同档排序加分，扶抑先行。
    """
    ys = Y.select(quad(*CASE_XIN_ZI))
    assert set(ys.favorable) == {"金", "土"}
    assert "火" not in ys.favorable
    assert ys.ji == "火"
    assert ys.method.startswith("扶抑")


def test_case_wu_yin_takes_fire_and_earth():
    """甲子 丙寅 戊辰 壬子：戊土偏弱，喜火土。"""
    ys = Y.select(quad(*CASE_WU_YIN))
    assert set(ys.favorable) == {"火", "土"}
    assert ys.method.startswith("扶抑")


def test_heige_priority_reproduces_the_climate_first_bug():
    """换成 HeiGe 口径（调候先于扶抑）会把火顶到用神位——用以说明本包为何不选它。"""
    ys = Y.select(quad(*CASE_XIN_ZI), priority=Y.HEIGE_PRIORITY)
    assert ys.method == "调候" and ys.yong == "火"
    # 默认口径不会
    assert Y.select(quad(*CASE_XIN_ZI)).yong == "金"


def test_unknown_priority_tier_raises():
    with pytest.raises(ValueError):
        Y.select(quad(*CASE_YI_CHEN), priority=("玄学",))


# ── 性质测试：500 张随机盘 ──────────────────────────────────────
def test_properties_over_500_charts():
    """用神非空、喜忌无交集、忌神非空、五位恰好覆盖五行。"""
    methods = set()
    for q in random_quads(500):
        ys = Y.select(q)
        assert ys.yong and ys.xi and ys.ji and ys.chou
        assert len(ys.xian) == 1
        five = (ys.yong, ys.xi, ys.ji, ys.chou) + ys.xian
        assert len(set(five)) == 5 and set(five) == set(wuxing.ORDER)
        assert not set(ys.favorable) & set(ys.unfavorable)
        assert ys.evidence and all(len(e) <= 24 for e in ys.evidence)
        methods.add(ys.method)
    # 中和局也必须有忌神（参考实现此处返回空列表，34.7% 的盘没有忌神）
    assert "病药" in methods


def test_balanced_charts_always_have_a_taboo():
    from tianzhi_core.bazi import strength as S

    seen = 0
    for q in random_quads(500):
        if S.day_master_strength(q).category != "balanced":
            continue
        seen += 1
        ys = Y.select(q)
        assert ys.ji and ys.chou
        assert ys.ji not in ys.favorable
    assert seen > 0


def test_select_is_deterministic():
    q = quad(*CASE_YI_CHEN)
    assert Y.select(q) == Y.select(q)


# ── 月令司令：传与不传两条路径 ──────────────────────────────────
def _siling_candidates(q):
    from tianzhi_core.core import ganzhi
    return [hg for hg, _ in ganzhi.HIDDEN[q["month"][1]]]


@pytest.mark.parametrize("case", [CASE_YI_CHEN, CASE_XIN_ZI, CASE_WU_YIN])
def test_benchmarks_are_stable_under_month_siling(case):
    """排盘层会把月令司令算出来传进来，线上就是这么调的。

    三个基准盘在「不传司令」与「传入月令任一藏干」下，用喜忌仇必须逐字相同：
    司令只细化月令藏干的粗细，不该翻转结论。
    曾经的 bug：司令把土的分量顶上来，土水咬平，通关档误判成两行相持，
    取到金做用神——金生水，而水正是这张盘的病，越通病越重。
    """
    q = quad(*case)
    base = Y.select(q)
    for sl in _siling_candidates(q):
        ys = Y.select(q, month_siling=sl)
        assert (ys.yong, ys.xi, ys.ji, ys.chou) == (base.yong, base.xi, base.ji, base.chou), (sl, ys)


def test_yi_chen_with_siling_still_takes_earth_not_metal():
    """丙子壬辰乙酉癸未 + 司令戊：仍须取土、忌不得落在火上。

    忌落火会与包里自带的《金不换》乙辰格「喜丙忌癸」（喜火忌水）直接矛盾。
    """
    ys = Y.select(quad(*CASE_YI_CHEN), month_siling="戊")
    assert ys.yong == "土" and ys.method == "病药"
    assert set(ys.favorable) == {"土", "火"}
    assert ys.ji != "火" and "火" not in ys.unfavorable
    adv = T.adverse_gods("乙", "辰")
    assert set(adv.xi_elements) <= set(ys.favorable)      # 金不换喜丙=火，落在喜用
    assert set(adv.ji_elements) <= set(ys.unfavorable)    # 金不换忌癸=水，落在避忌


def test_tongguan_requires_a_real_standoff():
    """通关三道门槛：份额、势均力敌，且病不在相战两行之内、通关神不生病。"""
    assert Y.TONGGUAN_BALANCE_MAX <= 1.10
    from tianzhi_core.bazi import strength as S
    from tianzhi_core.core import wuxing

    for q in random_quads(400):
        ys = Y.select(q)
        if ys.method != "通关":
            continue
        mass = S.element_power(q)
        bing = max(mass, key=lambda k: mass[k])
        assert wuxing.SHENG[ys.yong] != bing, (q, ys)     # 通关神不得生病


def test_month_siling_does_not_reverse_direction_on_500_charts():
    """500 张盘 × 每张月令的各个藏干：传与不传司令，用神方向相克的比例设上限。

    分档是硬边界，恰好压线的盘换档属预期；这里守的是「不要大面积翻转」。
    收紧通关与压低 SILING_BOOST 之前是 4.7%，之后 0.95%，阈值取 2% 作回归护栏。
    """
    from tianzhi_core.core import ganzhi, wuxing

    total = clash = 0
    for q in random_quads(500):
        base = Y.select(q)
        for hg, _lv in ganzhi.HIDDEN[q["month"][1]]:
            ys = Y.select(q, month_siling=hg)
            total += 1
            if wuxing.KE[ys.yong] == base.yong or wuxing.KE[base.yong] == ys.yong:
                clash += 1
    assert total > 1000
    assert clash / total < 0.02, f"{clash}/{total}"


def test_favorable_is_derived_not_a_second_opinion():
    """favorable/unfavorable 只是 (用,喜) 与 (忌,仇) 的只读派生，不得与五分矛盾。"""
    for q in random_quads(100):
        ys = Y.select(q)
        assert ys.favorable == (ys.yong, ys.xi)
        assert ys.unfavorable == (ys.ji, ys.chou)
        assert not set(ys.favorable) & set(ys.unfavorable)


def test_xi_ji_chou_are_mechanical():
    for q in random_quads(100):
        ys = Y.select(q)
        assert ys.xi == wuxing.SHENG_ME[ys.yong]
        assert ys.ji == wuxing.KE_ME[ys.yong]
        assert ys.chou == wuxing.SHENG_ME[ys.ji]
