"""逐年评分的验证。分数是相对的，所以测的是「谁比谁高」与「breakdown 说得清」，
不测某一年应该是几分。"""
from __future__ import annotations

import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import pytest

from conftest_shusu_yunshu import BASE_QUAD, FAVORABLE, UNFAVORABLE, sample_cycles
from shushu.bazi import score


def _score(gz: str, **kw) -> score.YearScore:
    return score.score_year(BASE_QUAD, gz, favorable=FAVORABLE, unfavorable=UNFAVORABLE, **kw)


# ── 喜忌方向 ────────────────────────────────────────────────────
def test_favorable_year_beats_unfavorable_year():
    """丙午两字全在喜用（火），癸卯天干落忌神（水）且地支三处引动，必须拉开差距。"""
    good, bad = _score("丙午"), _score("癸卯")
    assert good.score > bad.score + 20


def test_stance_labels():
    assert _score("丙午").stance == "顺"
    assert _score("癸亥").stance == "逆"
    assert _score("癸卯").stance == "偏逆"
    assert _score("甲寅").stance == "平"


# ── breakdown 的可解释性 ────────────────────────────────────────
def test_breakdown_sums_to_score():
    for gz in ("丙午", "癸卯", "辛丑", "戊戌", "甲子"):
        ys = _score(gz)
        assert round(sum(ys.breakdown.values()), 1) == pytest.approx(ys.score, abs=0.05)


def test_breakdown_names_its_sources():
    """每一项都要说清从哪来：丙午这一年，喜用、十神、冲年支三项都得在。"""
    ys = _score("丙午")
    keys = list(ys.breakdown)
    assert "base" in keys
    assert any(k.startswith("year_gan|") and "喜用" in k for k in keys)
    assert any(k.startswith("year_zhi|") and "喜用" in k for k in keys)
    assert any(k.startswith("ten_god|") for k in keys)
    assert any(k.startswith("zhi.冲.year|") for k in keys)
    assert ys.breakdown["base"] == score.BASE


def test_breakdown_records_gan_chong_day_master():
    ys = _score("辛丑")
    assert any(k.startswith("gan.冲.day|") for k in ys.breakdown)
    assert any(k.startswith("zhi.冲.hour|") for k in ys.breakdown)
    assert any(k.startswith("zhi.合.year|") for k in ys.breakdown)


def test_terms_mirror_breakdown():
    ys = _score("癸卯")
    assert len(ys.terms) == len(ys.breakdown)
    assert round(sum(t.delta for t in ys.terms), 1) == pytest.approx(ys.score, abs=0.05)


# ── 大运与岁运 ──────────────────────────────────────────────────
def test_dayun_shifts_the_score():
    """同一流年，走喜用大运应高于走忌神大运。"""
    hot = _score("甲子", dayun_gz="丙午")
    cold = _score("甲子", dayun_gz="壬子")
    assert hot.score > cold.score


def test_binglin_and_chong_are_charged():
    plain = _score("辛丑", dayun_gz="甲寅")
    binglin = _score("辛丑", dayun_gz="辛丑")
    chong = _score("辛丑", dayun_gz="丁未")
    assert any("并临" in k for k in binglin.breakdown)
    assert any("suiyun.冲" in k for k in chong.breakdown)
    assert not any("并临" in k or "suiyun.冲" in k for k in plain.breakdown)


def test_no_favorable_given_still_scores():
    """不给喜忌也要能算，只是五行项一律计 0。"""
    ys = score.score_year(BASE_QUAD, "丙午")
    assert not any(k.startswith("year_gan|") for k in ys.breakdown)
    assert ys.stance == "平"
    assert 0.0 <= ys.score <= 100.0


# ── 曲线 ────────────────────────────────────────────────────────
def _curve():
    return score.curve(BASE_QUAD, sample_cycles(BASE_QUAD),
                       favorable=FAVORABLE, unfavorable=UNFAVORABLE)


def test_curve_length_and_order():
    pts = _curve()
    assert len(pts) == 95
    assert [p.year for p in pts] == sorted(p.year for p in pts)
    assert len({p.year for p in pts}) == 95


def test_curve_spread_is_reasonable():
    """一生的曲线要有形状：既不能全挤在 50 附近，也不能在 0 / 100 上扎堆。"""
    scores = [p.score for p in _curve()]
    assert max(scores) - min(scores) >= 25, scores
    assert statistics.pstdev(scores) >= 6, scores
    assert sum(1 for s in scores if s in (0.0, 100.0)) <= 2
    assert sum(1 for s in scores if 45 <= s <= 55) < len(scores) * 0.6


def test_curve_carries_breakdown_per_point():
    for p in _curve():
        assert p.breakdown
        assert round(sum(p.breakdown.values()), 1) == pytest.approx(p.score, abs=0.05)


def test_curve_accepts_plain_mappings_and_tuples():
    """Cycle、dict、(干支, 年表) 三种写法结果一致。"""
    cycles = sample_cycles(BASE_QUAD)
    as_dict = [{"ganzhi": c.ganzhi, "years": c.years} for c in cycles]
    as_tuple = [(c.ganzhi, c.years) for c in cycles]
    a = score.curve(BASE_QUAD, cycles, favorable=FAVORABLE, unfavorable=UNFAVORABLE)
    b = score.curve(BASE_QUAD, as_dict, favorable=FAVORABLE, unfavorable=UNFAVORABLE)
    c = score.curve(BASE_QUAD, as_tuple, favorable=FAVORABLE, unfavorable=UNFAVORABLE)
    assert a == b == c


def test_pre_dayun_years_have_no_dayun_terms():
    pts = _curve()
    early = [p for p in pts if p.dayun == ""]
    assert early
    for p in early:
        assert not any(k.startswith("dayun_") for k in p.breakdown)


# ── 确定性 ──────────────────────────────────────────────────────
def test_deterministic():
    assert _score("丙午") == _score("丙午")
    assert _curve() == _curve()


def test_score_is_clamped():
    for p in _curve():
        assert 0.0 <= p.score <= 100.0


def test_weights_are_module_level_constants():
    """权重必须挂在模块上，改口径不必动函数。"""
    for name in ("BASE", "WX_HIT", "SLOT_WEIGHT", "GOD_BIAS", "REL_DELTA",
                 "PILLAR_WEIGHT", "SUIYUN_BINGLIN", "SUIYUN_CHONG"):
        assert name in score.WEIGHT_TABLE
    assert "相对" in score.__doc__
