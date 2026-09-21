"""通用顺逆规则与本盘成象相抵时，要能被识别出来。

`pattern_ops` 只认格名不看盘，`scan_patterns` 看盘。二者相抵是常事：
印格通例忌财，可若这张盘印已过旺成病，财损其印反倒是药。不把这种冲突标出来，
调用方会在同一页上同时印出「最怕财」和「财损印是吉」两句自相矛盾的话。
"""
import pytest

from shushu.bazi import geju

PRINT_HEAVY = {"year": ("丙", "子"), "month": ("壬", "辰"),
               "day": ("乙", "酉"), "hour": ("癸", "未")}
LU = {"year": ("戊", "辰"), "month": ("戊", "午"),
      "day": ("丁", "未"), "hour": ("丙", "午")}
SHISHEN = {"year": ("壬", "子"), "month": ("壬", "子"),
           "day": ("辛", "巳"), "hour": ("丁", "酉")}


def _conflicts(quad, siling=None):
    p = geju.month_pattern(quad, month_siling=siling)
    return p, geju.ops_conflicts(geju.pattern_ops(p.name),
                                 geju.scan_patterns(quad, month_siling=siling))


def test_heavy_seal_chart_flips_the_wealth_taboo():
    """印重身轻：通例忌财，本盘财损重印去病，两条财都该翻案。"""
    pattern, conflicts = _conflicts(PRINT_HEAVY, "戊")
    assert pattern.name == "偏印格"
    assert {c.ten_god for c in conflicts} == {"正财", "偏财"}
    assert all(c.hit == "财损印" for c in conflicts)


def test_conflict_carries_the_evidence_chain():
    """翻案要给出是哪个成象翻的，以及它的链条，供调用方交代理由。"""
    _, conflicts = _conflicts(PRINT_HEAVY, "戊")
    assert conflicts[0].chain and all(isinstance(x, str) for x in conflicts[0].chain)
    assert "成象" in conflicts[0].note


def test_no_conflict_when_evidence_agrees_with_the_rule():
    """成象里没有与忌神同路的吉象时，不应凭空报冲突。"""
    _, conflicts = _conflicts(SHISHEN)
    assert conflicts == ()


@pytest.mark.parametrize("quad,siling", [(PRINT_HEAVY, "戊"), (LU, None), (SHISHEN, None)])
def test_conflicting_gods_are_always_listed_in_the_taboo(quad, siling):
    """翻案的那一路必须确实出现在通用忌神里，不能是凭空多出来的。"""
    pattern, conflicts = _conflicts(quad, siling)
    ops = geju.pattern_ops(pattern.name)
    for c in conflicts:
        assert c.ten_god in ops.taboo


def test_empty_inputs_are_tolerated():
    assert geju.ops_conflicts(None, []) == ()
    assert geju.ops_conflicts(geju.pattern_ops("偏印格"), []) == ()
