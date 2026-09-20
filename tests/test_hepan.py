"""合盘的验证。核心是对称性：正反调用，对称的指标必须一模一样。"""
from __future__ import annotations

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import pytest

from conftest_shusu_yunshu import BASE_QUAD
from shushu.bazi import hepan
from shushu.core import ganzhi

OTHER: dict[str, tuple[str, str]] = {
    "year": ("庚", "午"),
    "month": ("戊", "寅"),
    "day": ("庚", "辰"),
    "hour": ("丁", "亥"),
}


def _random_quad(rng: random.Random) -> dict[str, tuple[str, str]]:
    return {k: (rng.choice(ganzhi.GAN), rng.choice(ganzhi.ZHI))
            for k in ("year", "month", "day", "hour")}


# ── 对称性 ──────────────────────────────────────────────────────
def test_symmetric_metrics_on_200_random_pairs():
    """分数、档位、五行轴、日干关系、互补总数、各柱关系，都与调用顺序无关。"""
    rng = random.Random(1357)
    for _ in range(200):
        a, b = _random_quad(rng), _random_quad(rng)
        ab, ba = hepan.relation_card(a, b), hepan.relation_card(b, a)
        assert ab.score == ba.score
        assert ab.grade == ba.grade
        assert ab.day_gan_axis == ba.day_gan_axis
        assert ab.day_gan_kind == ba.day_gan_kind
        assert ab.complement_count == ba.complement_count
        assert ([(r.pillar, r.kinds) for r in ab.pillar_relations]
                == [(r.pillar, r.kinds) for r in ba.pillar_relations])


def test_directional_fields_swap():
    ab = hepan.relation_card(BASE_QUAD, OTHER)
    ba = hepan.relation_card(OTHER, BASE_QUAD)
    assert ab.ten_god_b_to_a == ba.ten_god_a_to_b
    assert ab.ten_god_a_to_b == ba.ten_god_b_to_a
    assert ab.complement_to_a == ba.complement_to_b
    assert ab.a_ratio == ba.b_ratio


# ── 指标本身 ────────────────────────────────────────────────────
def test_day_gan_he_and_ten_gods():
    """乙与庚天干五合；庚对乙日主为正官，乙对庚日主为正财。"""
    card = hepan.relation_card(BASE_QUAD, OTHER)
    assert card.a_day_gan == "乙" and card.b_day_gan == "庚"
    assert card.day_gan_kind == "合"
    assert card.ten_god_b_to_a == "正官"
    assert card.ten_god_a_to_b == "正财"
    assert card.day_gan_axis == "克"


def test_pillar_relations_follow_core():
    """同名柱位的关系必须与 ganzhi.zhi_relation 一致。"""
    card = hepan.relation_card(BASE_QUAD, OTHER)
    for rel in card.pillar_relations:
        expect = tuple(r.kind for r in ganzhi.zhi_relation(rel.a_zhi, rel.b_zhi))
        assert rel.kinds == expect
    # 酉辰六合、子午相冲
    got = {(r.pillar, r.kinds) for r in card.pillar_relations}
    assert ("day", ("合",)) in got
    assert ("year", ("冲",)) in got


def test_score_range_and_grade_band():
    rng = random.Random(99)
    for _ in range(100):
        card = hepan.relation_card(_random_quad(rng), _random_quad(rng))
        assert 0.0 <= card.score <= 100.0
        assert card.grade in {g for _, g in hepan.GRADE_BANDS}
        assert round(sum(card.breakdown.values()), 1) == pytest.approx(
            card.score, abs=0.05) or card.score in (0.0, 100.0)


def test_favorable_overrides_the_share_heuristic():
    """给了喜用就按喜用判互补，不再用占比阈值。"""
    plain = hepan.relation_card(BASE_QUAD, OTHER)
    with_fav = hepan.relation_card(BASE_QUAD, OTHER, a_favorable=["火", "土"])
    assert "土" in with_fav.complement_to_a or "火" in with_fav.complement_to_a
    assert with_fav.complement_count >= len(plain.complement_to_b)


def test_ratios_sum_to_one():
    card = hepan.relation_card(BASE_QUAD, OTHER)
    assert sum(card.a_ratio.values()) == pytest.approx(1.0, abs=1e-3)
    assert sum(card.b_ratio.values()) == pytest.approx(1.0, abs=1e-3)


# ── 无文案 ──────────────────────────────────────────────────────
def test_no_prose_in_output():
    """返回里只许有术语标签，不许有成句的叙述。"""
    card = hepan.relation_card(BASE_QUAD, OTHER)
    for value in (*card.complement_to_a, *card.complement_to_b,
                  card.grade, card.day_gan_axis, card.ten_god_b_to_a):
        assert len(value) <= 4
    for key in card.breakdown:
        assert "。" not in key and "，" not in key


# ── 确定性与校验 ────────────────────────────────────────────────
def test_deterministic():
    assert hepan.relation_card(BASE_QUAD, OTHER) == hepan.relation_card(BASE_QUAD, OTHER)


def test_missing_day_gan_raises():
    with pytest.raises(Exception):
        hepan.relation_card({"year": ("丙", "子")}, OTHER)
