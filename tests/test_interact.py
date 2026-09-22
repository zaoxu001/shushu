"""岁运引动的验证。重点是：本层的判定与 core.ganzhi 严格一致，排序与确定性稳定。"""
from __future__ import annotations

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import pytest

from conftest_shusu_yunshu import BASE_QUAD
from tianzhi_core.bazi import interact
from tianzhi_core.core import ganzhi


# ── 基准盘的已知引动 ────────────────────────────────────────────
def test_xin_chou_zhi_relations():
    """流年辛丑：丑与时支未相冲（且相刑），与年支子相合。"""
    rels = interact.pillar_relations("丑", BASE_QUAD)
    got = {(r.kind, r.pillar, r.zhi) for r in rels}
    assert ("冲", "hour", "未") in got
    assert ("合", "year", "子") in got
    # 丑未同在恃势之刑一组，既冲又刑，两条都要给出
    assert ("刑", "hour", "未") in got


def test_xin_chou_he_into_tu():
    """子丑六合化土，化神要跟着给出。"""
    he = [r for r in interact.pillar_relations("丑", BASE_QUAD) if r.kind == "合"]
    assert [r.into for r in he] == ["土"]


def test_xin_gan_chong_day_master():
    """流年天干辛冲日主乙。"""
    rels = interact.gan_relations("辛", BASE_QUAD)
    assert ("冲", "day", "乙") in {(r.kind, r.pillar, r.gan) for r in rels}


def test_bing_wu_chong_year():
    """流年丙午：午冲年支子。"""
    rels = interact.pillar_relations("午", BASE_QUAD)
    assert ("冲", "year", "子") in {(r.kind, r.pillar, r.zhi) for r in rels}


# ── 与底层对拍 ──────────────────────────────────────────────────
def _random_quad(rng: random.Random) -> dict[str, tuple[str, str]]:
    return {k: (rng.choice(ganzhi.GAN), rng.choice(ganzhi.ZHI))
            for k in ("year", "month", "day", "hour")}


def test_matches_core_ganzhi_on_200_random_cases():
    """随机 200 组：pillar_relations 必须与 ganzhi.zhi_relation 逐条一致，不多不少。"""
    rng = random.Random(20240917)
    for _ in range(200):
        quad = _random_quad(rng)
        target = rng.choice(ganzhi.ZHI)
        mine = {(r.kind, r.pillar, r.zhi, r.into) for r in interact.pillar_relations(target, quad)}
        theirs = {
            (rel.kind, key, quad[key][1], rel.into)
            for key in ("year", "month", "day", "hour")
            for rel in ganzhi.zhi_relation(target, quad[key][1])
        }
        assert mine == theirs, (target, quad)


def test_gan_matches_core_ganzhi_on_200_random_cases():
    rng = random.Random(4242)
    for _ in range(200):
        quad = _random_quad(rng)
        target = rng.choice(ganzhi.GAN)
        mine = {(r.kind, r.pillar, r.gan, r.into) for r in interact.gan_relations(target, quad)}
        theirs = set()
        for key in ("year", "month", "day", "hour"):
            rel = ganzhi.gan_relation(target, quad[key][0])
            if rel is not None:
                theirs.add((rel.kind, key, quad[key][0], rel.into))
        assert mine == theirs, (target, quad)


# ── 排序 ────────────────────────────────────────────────────────
def test_sorted_by_kind_then_pillar():
    """冲 > 刑 > 自刑 > 害 > 合，同一档内按年月日时。"""
    rng = random.Random(7)
    for _ in range(100):
        quad = _random_quad(rng)
        target = rng.choice(ganzhi.ZHI)
        rels = interact.pillar_relations(target, quad)
        keys = [(interact.KIND_ORDER[r.kind], interact.PILLARS.index(r.pillar)) for r in rels]
        assert keys == sorted(keys)


# ── combine ─────────────────────────────────────────────────────
def test_combine_ten_god_and_moved_pillars():
    inter = interact.combine(BASE_QUAD, year_gz="辛丑")
    assert inter.day_gan == "乙"
    assert inter.year_ten_god == "七杀"          # 辛金克乙木，阴阳相同为七杀
    assert "hour" in inter.moved_pillars         # 丑冲刑时支未
    assert "year" in inter.moved_pillars         # 丑合年支子、辛合年干丙


def test_suiyun_binglin():
    """岁运并临：流年干支与大运干支相同。"""
    assert interact.combine(BASE_QUAD, year_gz="辛丑", dayun_gz="辛丑").suiyun_binglin
    assert not interact.combine(BASE_QUAD, year_gz="辛丑", dayun_gz="庚子").suiyun_binglin


def test_suiyun_chong_and_he():
    assert interact.combine(BASE_QUAD, year_gz="辛丑", dayun_gz="丁未").suiyun_chong
    assert interact.combine(BASE_QUAD, year_gz="辛丑", dayun_gz="庚子").suiyun_he
    assert not interact.combine(BASE_QUAD, year_gz="辛丑", dayun_gz="庚子").suiyun_chong


def test_combine_without_year_or_dayun():
    inter = interact.combine(BASE_QUAD)
    assert inter.year_ten_god is None
    assert inter.moved_pillars == ()
    assert inter.transforms == ()


def test_transform_verdict_is_tristate():
    """合化只给 True / False / None 三态，拿不准时必须是 None，不许硬判。"""
    inter = interact.combine(BASE_QUAD, year_gz="辛丑", dayun_gz="丁酉")
    assert inter.transforms
    for t in inter.transforms:
        assert t.can_transform in (True, False, None)
        assert 0.0 <= t.share <= 1.0
        assert isinstance(t.month_supports, bool)
    # 子丑合土，月令辰土帮化神，但化神分量未过线，拿不准
    tu = [t for t in inter.transforms if t.into == "土" and t.level == "zhi"][0]
    assert tu.month_supports is True
    assert tu.can_transform is None


def test_groups_picked_up_from_liunian():
    """流年申到，与原局子辰凑成申子辰水局。"""
    inter = interact.combine(BASE_QUAD, year_gz="庚申")
    assert ("合", "申子辰", "水") in inter.groups


# ── 十神 ────────────────────────────────────────────────────────
@pytest.mark.parametrize("gan,expect", [
    ("乙", "比肩"), ("甲", "劫财"), ("丙", "伤官"), ("丁", "食神"),
    ("戊", "正财"), ("己", "偏财"), ("庚", "正官"), ("辛", "七杀"),
    ("壬", "正印"), ("癸", "偏印"),
])
def test_ten_god_against_day_master_yi(gan: str, expect: str):
    assert interact.ten_god(gan, "乙") == expect


# ── 确定性与输入校验 ────────────────────────────────────────────
def test_deterministic():
    a = interact.combine(BASE_QUAD, year_gz="辛丑", dayun_gz="丁酉")
    b = interact.combine(BASE_QUAD, year_gz="辛丑", dayun_gz="丁酉")
    assert a == b
    assert interact.pillar_relations("丑", BASE_QUAD) == interact.pillar_relations("丑", BASE_QUAD)


def test_bad_input_raises():
    with pytest.raises(interact.QuadError):
        interact.pillar_relations("X", BASE_QUAD)
    with pytest.raises(interact.QuadError):
        interact.combine({"day": ("乙", "酉")}, year_gz="子丑")
    with pytest.raises(interact.QuadError):
        interact.combine({"year": ("丙", "子")})
