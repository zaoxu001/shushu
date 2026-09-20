"""盘面量化的测试。"""
from __future__ import annotations

import pytest
from conftest import CASE_WU_YIN, CASE_XIN_ZI, CASE_YI_CHEN, quad, random_quads

from shushu.bazi import strength as S
from shushu.core import ganzhi, wuxing


def test_element_power_keys_and_total():
    q = quad(*CASE_YI_CHEN)
    p = S.element_power(q)
    assert set(p) == set(wuxing.ORDER)
    assert sum(p.values()) > 0
    # 含日主自身天干：乙木必有分
    assert p["木"] > 0


def test_pure_function_is_deterministic():
    q = quad(*CASE_XIN_ZI)
    assert S.element_power(q) == S.element_power(q)
    assert S.day_master_strength(q) == S.day_master_strength(q)
    assert S.ten_god_power(q) == S.ten_god_power(q)
    assert S.climate_index(q) == S.climate_index(q)


def test_validate_quad_rejects_bad_input():
    with pytest.raises(ValueError):
        S.validate_quad({"year": ("甲", "子"), "month": ("甲", "子"), "day": ("甲", "子")})
    with pytest.raises(ValueError):
        S.validate_quad(quad("甲子", "甲子", "甲子", "甲子") | {"day": ("X", "子")})


# ── bug (a)：贴身加权必须对称 ────────────────────────────────────
def _gan_component(q, pos):
    return next(c for c in S.components(q) if c.pos == pos and c.kind == "干")


def test_attach_factor_is_symmetric_between_support_and_drain():
    """月干无论帮身还是克泄，都吃同一个贴身加权 ×1.2。

    参考实现 bazi_score 只在克泄时加 ×1.2、帮身时不加，系统性地把天平压向身弱。
    用同一个天干分列年干与月干作对照，两处虚透与否一致，比值只剩贴身加权。
    """
    drain = quad("庚子", "庚午", "甲寅", "甲子")    # 庚 = 七杀，克身
    support = quad("壬子", "壬午", "甲寅", "甲子")  # 壬 = 偏印，帮身
    for q in (drain, support):
        ratio = _gan_component(q, "month").weight / _gan_component(q, "year").weight
        assert ratio == pytest.approx(S.ATTACH_FACTOR)


def test_day_zhi_attach_applies_regardless_of_relation():
    for q in (quad("甲子", "甲子", "甲申", "甲子"),     # 日支申藏庚 = 七杀，克身
              quad("甲子", "甲子", "甲亥", "甲子")):    # 日支亥藏壬 = 偏印，帮身
        day_zhi_comps = [c for c in S.components(q) if c.pos == "day" and c.kind == "支"]
        assert day_zhi_comps
        for c in day_zhi_comps:
            assert "贴身" in c.tags
            base = S.ZHI_BASE * S.ROOT_COEF[c.level]
            assert c.weight == pytest.approx(base * S.ATTACH_FACTOR)


# ── bug (b)：日主根气分与藏干比劫分二选一 ────────────────────────
def test_day_root_bonus_not_double_counted():
    """本包选「藏干比劫分」，取消额外的 +8 根气分：同一个根不许算两遍。"""
    assert S.DAY_ROOT_BONUS == 0.0
    q = quad("甲子", "甲寅", "甲寅", "甲子")
    body = S.day_master_strength(q)
    comps = {(c.pos, c.gan, c.level): c.weight
             for c in S.components(q, include_day_gan=False)}
    bijie = [it for it in body.items if it.relation == "比劫"]
    assert bijie
    for it in bijie:
        matches = [w for (p, g, _l), w in comps.items() if p == it.pos and g == it.gan]
        assert any(it.score == pytest.approx(w) for w in matches), it


# ── bug (c)：纯气支本气应重于杂气支本气 ──────────────────────────
def test_pure_zhi_benqi_outweighs_mixed_zhi_benqi():
    pure = quad("甲子", "甲子", "甲子", "甲子")     # 子：纯气，只藏癸
    mixed = quad("甲辰", "甲辰", "甲辰", "甲辰")    # 辰：杂气，戊乙癸
    wp = next(c.weight for c in S.components(pure) if c.pos == "year" and c.kind == "支")
    wm = next(c.weight for c in S.components(mixed)
              if c.pos == "year" and c.kind == "支" and c.level == "本")
    assert wp > wm
    assert wp == pytest.approx(wm * S.PURE_ZHI_COEF)


def test_month_and_siling_weighting():
    q = quad("甲子", "甲辰", "甲子", "甲子")
    plain = {(c.gan, c.level): c.weight for c in S.components(q)
             if c.pos == "month" and c.kind == "支"}
    boosted = {(c.gan, c.level): c.weight
               for c in S.components(q, month_siling="癸")
               if c.pos == "month" and c.kind == "支"}
    assert boosted[("癸", "余")] > plain[("癸", "余")]
    assert boosted[("戊", "本")] == plain[("戊", "本")]


# ── 旺衰 ────────────────────────────────────────────────────────
def test_benchmark_strength_labels():
    assert S.day_master_strength(quad(*CASE_XIN_ZI)).label == "身弱"
    assert S.day_master_strength(quad(*CASE_WU_YIN)).category in ("weak", "slightly_weak")
    assert S.day_master_strength(quad(*CASE_YI_CHEN)).category == "balanced"


def test_ratio_is_normalised():
    for q in random_quads(50):
        b = S.day_master_strength(q)
        assert 0.0 <= b.ratio <= 1.0
        assert b.support + b.drain > 0
        assert b.ratio == pytest.approx(b.support / (b.support + b.drain), abs=1e-3)


def test_has_root_gate():
    # 辛坐酉为临官
    assert S.day_master_strength(quad(*CASE_XIN_ZI)).has_root is True
    # 甲木全盘无木根、无长生临官帝旺
    assert S.day_master_strength(quad("庚申", "庚申", "甲申", "庚午")).has_root is False


def test_strength_distribution_over_500_charts():
    """五档分布不得有任何一档低于 5%——检验归一化阈值是否生效。"""
    from collections import Counter
    labels = Counter(S.day_master_strength(q).label for q in random_quads(500))
    assert set(labels) == {"身旺", "偏旺", "中和", "偏弱", "身弱"}
    for label, cnt in labels.items():
        assert cnt / 500 >= 0.05, (label, cnt, labels)


# ── 十神与调候标量 ──────────────────────────────────────────────
def test_ten_god_power_has_all_ten_keys():
    p = S.ten_god_power(quad(*CASE_YI_CHEN))
    assert set(p) == set(S.TEN_GODS)
    assert sum(p.values()) > 0
    # 日干自身不计入十神
    body = S.day_master_strength(quad(*CASE_YI_CHEN))
    assert sum(p.values()) == pytest.approx(body.support + body.drain, abs=1e-6)


def test_ten_god_matches_wuxing_relation():
    for g in ganzhi.GAN:
        for d in ganzhi.GAN:
            tg = S.ten_god(g, d)
            rel = wuxing.relation(ganzhi.GAN_WUXING[g], ganzhi.GAN_WUXING[d])
            assert tg in {"比劫": ("比肩", "劫财"), "印": ("偏印", "正印"),
                          "食伤": ("食神", "伤官"), "财": ("偏财", "正财"),
                          "官杀": ("七杀", "正官")}[rel]


def test_climate_index_sign():
    cold = S.climate_index(quad(*CASE_XIN_ZI))          # 壬子壬子辛巳丁酉：水旺
    warm = S.climate_index(quad("丙午", "丙午", "丙午", "丙午"))
    assert cold < 0 < warm
    assert -1.0 <= cold <= 1.0 and -1.0 <= warm <= 1.0
