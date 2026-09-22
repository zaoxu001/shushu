"""格局：月令取格、顺逆相神、成象扫描的测试。"""
from __future__ import annotations

from conftest import CASE_WU_YIN, CASE_XIN_ZI, CASE_YI_CHEN, quad, random_quads

from tianzhi_core.bazi import geju as G
from tianzhi_core.core import ganzhi


# ── 月令取格 ────────────────────────────────────────────────────
def test_month_pattern_benchmarks():
    """三例的月令取格，人工核对：

    丙子壬辰乙酉癸未：辰藏戊乙癸，本气戊为正财；癸透于时干，以透出者定格 → 偏印格。
    壬子壬子辛巳丁酉：子藏癸独气，癸对辛为食神；壬透非癸，不作透干 → 食神格（本气）。
    甲子丙寅戊辰壬子：寅藏甲丙戊，本气甲对戊为七杀，且甲透于年干 → 七杀格（本气透出）。
    """
    p1 = G.month_pattern(quad(*CASE_YI_CHEN))
    assert (p1.name, p1.ten_god, p1.gan, p1.basis) == ("偏印格", "偏印", "癸", "透干")
    assert p1.transparent_at == ("hour",)

    p2 = G.month_pattern(quad(*CASE_XIN_ZI))
    assert (p2.name, p2.ten_god, p2.gan, p2.basis) == ("食神格", "食神", "癸", "本气")
    assert p2.transparent_at == ()

    p3 = G.month_pattern(quad(*CASE_WU_YIN))
    assert (p3.name, p3.ten_god, p3.gan, p3.basis) == ("七杀格", "七杀", "甲", "透干")
    assert p3.transparent_at == ("year",)


def test_jianlu_pattern():
    """月支为日主临官取建禄格。甲之临官在寅。"""
    p = G.month_pattern(quad("甲子", "丙寅", "甲午", "乙亥"))
    assert p.name == "建禄格" and p.basis == "建禄"
    assert ganzhi.dishi("甲", "寅") == "临官"


def test_yangren_pattern_only_for_yang_gan():
    """月支为日主帝旺取阳刃，且只给阳干。"""
    yang = G.month_pattern(quad("甲子", "丙午", "丙寅", "己亥"))
    assert yang.name == "阳刃格" and yang.basis == "阳刃"
    # 乙之帝旺在寅，但阴干不立阳刃，退回月令取格
    assert ganzhi.dishi("乙", "寅") == "帝旺"
    assert "乙" not in ganzhi.YANGREN
    yin = G.month_pattern(quad("甲子", "丙寅", "乙巳", "丁亥"))
    assert yin.name != "阳刃格"


def test_month_siling_changes_base_qi():
    """传 month_siling 时以司令者为基础格；未透干才看得出差别。"""
    q = quad("庚申", "戊辰", "庚午", "丁丑")   # 辰藏戊乙癸，戊透于月干
    base = G.month_pattern(q)
    assert base.basis == "透干" and base.gan == "戊"
    q2 = quad("庚申", "甲辰", "庚午", "丁丑")   # 无一藏干透出
    assert G.month_pattern(q2).gan == "戊"
    assert G.month_pattern(q2, month_siling="乙").gan == "乙"
    assert G.month_pattern(q2, month_siling="乙").basis == "司令"


def test_month_pattern_total_coverage():
    """任何一张盘都取得出格，且格名在顺逆表里认得（经别名归并）。"""
    for q in random_quads(200):
        p = G.month_pattern(q)
        assert p.name
        assert G.pattern_ops(p.name) is not None, p.name


# ── 顺用逆用与相神 ──────────────────────────────────────────────
def test_pattern_ops_table_matches_ziping_zhenquan():
    """《子平真诠·论用神》八条逐条核对。"""
    cai = G.pattern_ops("财格")
    assert cai.mode == "顺" and cai.generate == ("食神",) and cai.protect == ("正官",)
    guan = G.pattern_ops("正官格")
    assert guan.mode == "顺" and "正财" in guan.generate and "正印" in guan.protect
    yin = G.pattern_ops("印格")
    assert yin.mode == "顺" and yin.generate == ("正官", "七杀") and yin.protect == ("劫财",)
    shi = G.pattern_ops("食神格")
    assert shi.mode == "顺" and "比肩" in shi.generate and "正财" in shi.protect
    sha = G.pattern_ops("七杀格")
    assert sha.mode == "逆" and sha.generate == ("食神",)
    assert set(sha.taboo) == {"正财", "偏财", "正印", "偏印"}     # 忌财印以资扶
    shang = G.pattern_ops("伤官格")
    assert shang.mode == "逆" and "正印" in shang.generate and "正官" in shang.taboo
    ren = G.pattern_ops("阳刃格")
    assert ren.mode == "逆" and ren.generate == ("正官", "七杀") and ren.taboo == ()
    jie = G.pattern_ops("月劫格")
    assert jie.mode == "逆" and jie.generate == ("正官",) and "伤官" in jie.taboo


def test_pattern_ops_alias_and_unknown():
    assert G.pattern_ops("正财格") is G.pattern_ops("财格")
    assert G.pattern_ops("偏印格") is G.pattern_ops("印格")
    assert G.pattern_ops("建禄格") is G.pattern_ops("月劫格")
    assert G.pattern_ops("没有这个格") is None


# ── 成象扫描 ────────────────────────────────────────────────────
def test_scan_patterns_does_not_depend_on_yongshen():
    """成象只看量化，不看喜忌：模块不得引入 yongshen。"""
    import inspect

    src = inspect.getsource(G)
    assert "yongshen" not in src


def test_scan_patterns_shape_and_determinism():
    q = quad(*CASE_YI_CHEN)
    hits = G.scan_patterns(q)
    assert hits == G.scan_patterns(q)
    assert [h.name for h in hits] == [h.name for h in G.scan_patterns(q)]
    assert sum(1 for h in hits if h.role == "主象") == 1
    for h in hits:
        assert h.kind in ("吉", "病")
        assert h.chain and all(isinstance(t, str) for t in h.chain)
        assert h.power > 0


def test_scan_patterns_finds_expected_images():
    names = {h.name for h in G.scan_patterns(quad(*CASE_WU_YIN))}
    assert "杀印相生" in names          # 戊土身弱，寅中甲杀、丙印透
    names2 = {h.name for h in G.scan_patterns(quad(*CASE_XIN_ZI))}
    assert "食伤泄气太过" in names2     # 辛金身弱，两壬两子食伤成势


def test_scan_patterns_actor_is_unique():
    for q in random_quads(100):
        hits = G.scan_patterns(q)
        actors = [h.actor for h in hits]
        assert len(actors) == len(set(actors))
