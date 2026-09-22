"""神煞的验证。除了起例对不对，还要守住一条底线：取用逻辑不许碰神煞。"""
from __future__ import annotations

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import pytest

from conftest_shusu_yunshu import BASE_QUAD
from tianzhi_core.bazi import score, shensha
from tianzhi_core.core import ganzhi


def _names(items) -> set[str]:
    return {x.name for x in items}


def _by_name(items, name: str):
    return [x for x in items if x.name == name]


# ── 基准盘 丙子 壬辰 乙酉 癸未 ──────────────────────────────────
def test_tianyi_guiren():
    """乙日干天乙贵人在子申，原局年支子命中。"""
    hits = _by_name(shensha.shensha(BASE_QUAD), "天乙贵人")
    assert ("year", "子") in {(h.pillar, h.zhi) for h in hits}
    assert any(h.base == "日干" and h.source == "乙" for h in hits)


def test_group_shensha_from_year_zhi():
    """年支子属申子辰局：桃花在酉、华盖在辰、将星在子、驿马在寅。"""
    items = shensha.shensha(BASE_QUAD)
    assert ("day", "酉") in {(h.pillar, h.zhi) for h in _by_name(items, "桃花")}
    assert ("month", "辰") in {(h.pillar, h.zhi) for h in _by_name(items, "华盖")}
    assert ("year", "子") in {(h.pillar, h.zhi) for h in _by_name(items, "将星")}
    assert not _by_name(items, "驿马")          # 寅不在盘上
    assert not _by_name(items, "亡神")          # 亥不在盘上


def test_tiande_yuede_land_on_stems():
    """辰月月德在壬、天德也在壬，都落月干。"""
    items = shensha.shensha(BASE_QUAD)
    for name in ("天德贵人", "月德贵人"):
        hits = _by_name(items, name)
        assert hits, name
        assert hits[0].position == "gan"
        assert hits[0].gan == "壬" and hits[0].zhi == ""
        assert hits[0].base == "月支"


def test_xun_kong():
    """乙酉在甲申旬，旬空午未；时支未落空，日柱自身不论空。"""
    assert shensha.xun_kong("乙", "酉") == ("午", "未")
    hits = _by_name(shensha.shensha(BASE_QUAD), "空亡")
    assert {(h.pillar, h.zhi) for h in hits} == {("hour", "未")}


def test_yin_day_gan_has_no_yangren():
    """阴干刃各家分歧，本包只给阳刃，乙日不出羊刃。"""
    assert not _by_name(shensha.shensha(BASE_QUAD), "羊刃")


def test_yangren_for_yang_day_gan():
    """丙日刃在午。"""
    quad = {"year": ("丙", "子"), "month": ("壬", "辰"), "day": ("丙", "午"), "hour": ("癸", "未")}
    hits = _by_name(shensha.shensha(quad), "羊刃")
    assert ("day", "午") in {(h.pillar, h.zhi) for h in hits}
    assert hits[0].base == "日干" and hits[0].source == "丙"


def test_yima_and_jiesha():
    """寅午戌局：驿马在申、劫煞在亥。"""
    quad = {"year": ("甲", "午"), "month": ("丙", "寅"), "day": ("戊", "申"), "hour": ("癸", "亥")}
    items = shensha.shensha(quad)
    assert ("day", "申") in {(h.pillar, h.zhi) for h in _by_name(items, "驿马")}
    assert ("hour", "亥") in {(h.pillar, h.zhi) for h in _by_name(items, "劫煞")}


def test_wenchang():
    """甲日文昌在巳。"""
    quad = {"year": ("甲", "子"), "month": ("己", "巳"), "day": ("甲", "戌"), "hour": ("乙", "丑")}
    hits = _by_name(shensha.shensha(quad), "文昌贵人")
    assert ("month", "巳") in {(h.pillar, h.zhi) for h in hits}


def test_required_coverage():
    """这几个名目必须都在起例表里，缺一不可。"""
    required = {"天乙贵人", "驿马", "桃花", "华盖", "文昌贵人", "羊刃",
                "将星", "劫煞", "亡神", "天德贵人", "月德贵人"}
    assert required <= set(shensha.NAME_ORDER)


# ── 结构与去重 ──────────────────────────────────────────────────
def test_every_entry_is_well_formed():
    rng = random.Random(2468)
    for _ in range(200):
        quad = {k: (rng.choice(ganzhi.GAN), rng.choice(ganzhi.ZHI))
                for k in ("year", "month", "day", "hour")}
        for item in shensha.shensha(quad):
            assert item.pillar in ("year", "month", "day", "hour")
            assert item.position in ("gan", "zhi")
            assert item.base in shensha.BASE_ORDER
            assert item.source
            if item.position == "zhi":
                assert item.char == quad[item.pillar][1] == item.zhi
                assert item.gan == ""
            else:
                assert item.char == quad[item.pillar][0] == item.gan
                assert item.zhi == ""


def test_no_duplicate_name_pillar_char():
    rng = random.Random(1122)
    for _ in range(200):
        quad = {k: (rng.choice(ganzhi.GAN), rng.choice(ganzhi.ZHI))
                for k in ("year", "month", "day", "hour")}
        items = shensha.shensha(quad)
        keys = [(x.name, x.pillar, x.char) for x in items]
        assert len(keys) == len(set(keys))


def test_stable_order():
    items = shensha.shensha(BASE_QUAD)
    ranks = [(shensha.NAME_ORDER.index(x.name), ("year", "month", "day", "hour").index(x.pillar))
             for x in items]
    assert ranks == sorted(ranks)


def test_deterministic():
    assert shensha.shensha(BASE_QUAD) == shensha.shensha(BASE_QUAD)


def test_include_kong_switch():
    assert "空亡" not in _names(shensha.shensha(BASE_QUAD, include_kong=False))
    assert "空亡" in _names(shensha.shensha(BASE_QUAD))


# ── 底线：取用逻辑不采信神煞 ────────────────────────────────────
def test_module_docstring_states_the_caveat():
    doc = shensha.__doc__ or ""
    assert "子平真诠" in doc
    assert "星辰好歹" in doc
    assert "绝不采信神煞" in doc


def test_score_breakdown_never_cites_a_shensha():
    """评分的 breakdown 里不许出现任何神煞名目。"""
    ys = score.score_year(BASE_QUAD, "辛丑", dayun_gz="丁酉",
                          favorable=["火", "土"], unfavorable=["水"])
    blob = "".join(ys.breakdown)
    for name in shensha.NAME_ORDER:
        assert name not in blob


def test_score_module_does_not_import_shensha():
    assert not hasattr(score, "shensha")
