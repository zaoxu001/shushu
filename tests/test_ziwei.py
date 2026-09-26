"""紫微排盘与格局。

对拍：tests/fixtures/ziwei_iztro.json 是 iztro（社区用得最多的开源实现，MIT）排出的 60 张盘。
两家分歧只在三处有书可据的取舍（闰月、壬年化科、长生顺逆），传同样的参数后应逐星一致。
其余用《紫微斗数全书》卷二原文逐条核。
"""
import json
import random
from datetime import datetime
from pathlib import Path

import pytest

from tianzhi_core.ziwei import SKIPPED, build_chart, find_geju
from tianzhi_core.ziwei.chart import ZHI, ziwei_pos

FIX = json.loads((Path(__file__).parent / "fixtures" / "ziwei_iztro.json").read_text(encoding="utf-8"))
IZTRO = {"leap": "half", "sihua_ren": "左辅", "changsheng": "yinyang"}
CLASSICS = Path(__file__).resolve().parents[2] / "tianzhi-classics" / "ziwei"


def chart_of(c, **kw):
    y, m, d = map(int, c["solar"].split("-"))
    return build_chart(datetime(y, m, d, c["hour"], 30), c["gender"], **kw)


def star_pos(ch):
    return {s["name"]: p["zhi"] for p in ch["palaces"] for s in p["stars"]}


@pytest.mark.parametrize("c", FIX["cases"], ids=lambda c: f'{c["solar"]}h{c["hour"]}g{c["gender"]}')
def test_matches_iztro(c):
    ch = chart_of(c, **IZTRO)
    assert (ch["ming"], ch["shen"], ch["ju_name"]) == (c["ming"], c["shen"], c["ju"])
    pos = star_pos(ch)
    assert {k: pos[k] for k in c["stars"]} == c["stars"]
    assert {s["name"]: s["hua"] for p in ch["palaces"] for s in p["stars"] if s.get("hua")} == c["hua"]
    for p in ch["palaces"]:
        assert list(p["daxian"]) == c["daxian"][p["zhi"]]
        assert p["changsheng"] == c["changsheng"][p["zhi"]] and p["boshi"] == c["boshi"][p["zhi"]]


def test_anming_book_example():
    # 安身命例：「假如正月生子时就在寅宫安身命，丑时逆转丑安命，顺去卯安身」
    # 1990-01-27 是庚午年正月初一
    ch = build_chart(datetime(1990, 1, 27, 0, 30), 0)
    assert ch["input"]["lunar"]["month"] == 1 and (ch["ming"], ch["shen"]) == ("寅", "寅")
    ch = build_chart(datetime(1990, 1, 27, 2, 30), 0)
    assert (ch["ming"], ch["shen"]) == ("丑", "卯")


def day_num(name):
    """初一…初十、十一…十九、二十、廿一…廿九、三十"""
    n = "一二三四五六七八九十"
    if name in ("二十", "三十"):
        return 10 * (n.index(name[0]) + 1)
    head, tail = name[0], n.index(name[1]) + 1
    return {"初": 0, "十": 10, "廿": 20}[head] + tail


def test_ziwei_pos_matches_book_tables():
    """五张定紫微图逐日核。录文两处错格（木三局寅宫「初九」当作「初五」、金四局亥宫漏「三十」）已对明刻本确认"""
    path = CLASSICS / "entries" / "ziweiquanshu-ju.json"
    if not path.exists():
        pytest.skip("需要 tianzhi-classics 与本仓库同级")
    items = json.loads(path.read_text(encoding="utf-8"))["items"]
    seen = 0
    for it in items:
        ju = "水木金土火".index(it["key"][0]) + 2
        for name, z in it["days"].items():
            d = day_num(name)
            if (it["key"], d, z) == ("木三局", 9, "寅"):
                d = 5
            assert ziwei_pos(ju, d) == z, (it["key"], name)
            seen += 1
    assert seen == 148                                   # 5 × 30 减去两处错格
    assert ziwei_pos(4, 30) == "亥" and ziwei_pos(3, 9) == "辰"


def test_leap_month_follows_book():
    # 「若闰月正月生者要在二月内起安身命」：闰月作下月。1936-05-03 是闰三月十三
    ch = build_chart(datetime(1936, 5, 3, 2, 30), 0)
    assert ch["input"]["lunar"]["leap"] and ch["input"]["lunar"]["month"] == 4
    assert build_chart(datetime(1936, 5, 3, 2, 30), 0, leap="same")["input"]["lunar"]["month"] == 3


def test_late_zi_crosses_month():
    # 1932-07-03 23:30 是五月三十晚子时；次日六月初一。iztro 此处只把日数加一、月份不进，与本包不同
    ch = build_chart(datetime(1932, 7, 3, 23, 30), 0)
    assert (ch["input"]["lunar"]["month"], ch["input"]["lunar"]["day"], ch["input"]["lunar"]["hour"]) == (6, 1, "子")


def test_ren_year_huake():
    # 「壬梁紫府武」：壬年天府化科
    ch = build_chart(datetime(2022, 4, 19, 3, 30), 0)
    hua = {s["name"]: s["hua"] for p in ch["palaces"] for s in p["stars"] if s.get("hua")}
    assert hua == {"天梁": "禄", "紫微": "权", "天府": "科", "武曲": "忌"}


def test_changsheng_book_male_forward_female_backward():
    # 「男命顺数、女命逆数」
    for g in (0, 1):
        ch = build_chart(datetime(1971, 3, 13, 20, 30), g)
        cs = {p["changsheng"]: p["zhi"] for p in ch["palaces"]}
        step = (ZHI.index(cs["沐浴"]) - ZHI.index(cs["长生"])) % 12
        assert step == (1 if g == 0 else 11)


def test_kongwang_xiaoxian():
    ch = build_chart(datetime(1990, 5, 8, 9, 30), 0)   # 庚午年
    pos = {}
    for p in ch["palaces"]:
        for s in p["stars"]:
            pos.setdefault(s["name"], []).append(p["zhi"])
    assert pos["截路空亡"] == ["午", "未"]      # 乙庚午未宫
    assert pos["旬中空亡"] == ["戌", "亥"]      # 甲子旬中空戌亥
    assert pos["解神"] == ["辰"]                # 戌上起子逆数至午
    first = {p["zhi"]: p["xiaoxian"][0] for p in ch["palaces"]}
    assert first["辰"] == 1 and first["巳"] == 2   # 寅午戌人起辰宫，男顺


def test_srcs_exist_in_classics():
    path = CLASSICS / "entries" / "ziweiquanshu-anxing.json"
    if not path.exists():
        pytest.skip("需要 tianzhi-classics 与本仓库同级")
    keys = {e["key"] for e in json.loads(path.read_text(encoding="utf-8"))["items"]}
    ch = build_chart(datetime(1990, 5, 8, 9, 30), 0)
    for p in ch["palaces"]:
        for s in p["stars"]:
            if not s.get("tongxing"):
                assert s["src"].split("·", 1)[1] in keys, s


def test_geju_hits_are_explained():
    random.seed(5)
    seen = set()
    for _ in range(3000):
        ch = build_chart(datetime(random.randint(1930, 2030), random.randint(1, 12), random.randint(1, 28),
                                  random.randint(0, 23), 30), random.randint(0, 1))
        for g in find_geju(ch):
            assert g["cat"] in ("富", "贵", "贫贱") and g["why"] and g["text"].startswith(g["name"])
            assert g["name"] not in SKIPPED
            seen.add(g["name"])
    assert len(seen) >= 18


def test_geju_examples():
    # 紫微、左辅、右弼同守命：君臣庆会；辅弼在命亦算不上「来拱」
    random.seed(9)
    for _ in range(20000):
        ch = build_chart(datetime(random.randint(1930, 2030), random.randint(1, 12), random.randint(1, 28),
                                  random.randint(0, 22), 30), random.randint(0, 1))
        names = {s["name"] for p in ch["palaces"] if p["zhi"] == ch["ming"] for s in p["stars"]}
        if {"紫微", "左辅", "右弼"} <= names:
            got = {g["name"] for g in find_geju(ch)}
            assert "君臣庆会" in got and "辅弼拱主" not in got
            return
    pytest.fail("没抽到君臣庆会的盘")


# ---------------- 通行杂曜、岁前将前、运限：与 iztro 对拍 ----------------
from tianzhi_core.ziwei.yunxian import daxian_list, horoscope  # noqa: E402

HORO = json.loads((Path(__file__).parent / "fixtures" / "ziwei_iztro_horo.json").read_text(encoding="utf-8"))
TXS = ['天官', '天福', '天厨', '天巫', '天月', '阴煞', '孤辰', '寡宿', '蜚廉', '破碎', '华盖', '咸池', '天才', '天寿', '恩光', '天贵']
LAYER = {'daxian': 'decadal', 'xiaoxian': 'age', 'liunian': 'yearly', 'liuyue': 'monthly', 'liuri': 'daily', 'liushi': 'hourly'}


@pytest.mark.parametrize("c", HORO["cases"], ids=lambda c: f'{c["d"]}@{c["t"]}')
def test_tongxing_and_horoscope_match_iztro(c):
    y, m, d = map(int, c["d"].split("-"))
    ch = build_chart(datetime(y, m, d, c["h"], 30), c["g"], leap="half", sihua_ren="左辅")
    for p in ch["palaces"]:
        names = {s["name"] for s in p["stars"]}
        assert {s for s in TXS if s in names} == {s for s in TXS if s in c["adj"][p["zhi"]]}
        assert (p["suiqian"], p["jiangqian"]) == (c["sq"][p["zhi"]], c["jq"][p["zhi"]])
    ty, tm, td = map(int, c["t"].split("-"))
    h = horoscope(ch, datetime(ty, tm, td, c["th"], 30))
    for L in h["layers"]:
        t = c["horo"][LAYER[L["key"]]]
        assert (L["ming"], L["gan"], list(L["sihua"])) == (t["zhi"], t["gan"], t["mut"]), L["key"]
        if "stars" in L:
            assert {n: z for z, ns in L["stars"].items() for n in ns} == {k: v for k, v in t["stars"].items() if k[1:] in "禄羊陀魁钺昌曲马鸾喜"}


def test_doujun_book_rule():
    # 安斗君诀：流年太岁宫起正月逆至生月，生月宫起子顺至生时。1990 年四月巳时生，2024 甲辰年：辰逆三位得丑，丑起子顺五位得午
    ch = build_chart(datetime(1990, 5, 8, 9, 30), 0)
    h = horoscope(ch, datetime(2024, 3, 1, 12))
    assert next(L for L in h["layers"] if L["key"] == "liuyue")["doujun"] == "午"
    assert [x["range"][0] for x in daxian_list(ch)][:3] == [6, 16, 26]


def test_feihua_self():
    ch = build_chart(datetime(1990, 5, 8, 9, 30), 0)
    for p in ch["palaces"]:
        assert len(p["fei"]) == 4 and all(f["self"] == (f["to"] == p["zhi"]) for f in p["fei"])


# ---------------- 断语与运限论断 ----------------
from tianzhi_core.ziwei import find_duanyu, judge  # noqa: E402
from tianzhi_core.ziwei.duanyu import _Pan, _ev, rules as duanyu_rules  # noqa: E402


def test_duanyu_rules_well_formed():
    rs = duanyu_rules()
    assert len({r["id"] for r in rs}) == len(rs)
    ch = _Pan(build_chart(datetime(1990, 5, 8, 9, 30), 0))
    for r in rs:
        assert r["verdict"] in ("吉", "凶", "中") and r["text"] and r["src"].startswith("紫微斗数全书·")
        assert bool(r.get("skip")) != bool(r.get("cond")), r["id"]
        if r.get("cond"):
            _ev(ch, r["cond"])   # 条件写法都认得


def test_duanyu_every_rule_can_fire():
    """每条判定的断语都至少在一张盘上成立；按安星法不可能的组合已在规则表里改为不判"""
    random.seed(4)
    fired = set()
    for _ in range(6000):
        ch = build_chart(datetime(random.randint(1930, 2030), random.randint(1, 12), random.randint(1, 28), random.randint(0, 23), 30), random.randint(0, 1))
        fired |= {x["id"] for x in find_duanyu(ch)}
    never = [r["id"] for r in duanyu_rules() if r.get("cond") and r["id"] not in fired]
    assert len(never) <= 3, never   # 极罕见的组合（如天梁文昌同守命俱庙旺）允许抽不到


def test_duanyu_examples():
    # 骨髓赋「日照雷门富贵荣华」：太阳守命在卯
    for d in range(1, 29):
        ch = build_chart(datetime(1984, 3, d, 6, 30), 0)
        sun = next(p["zhi"] for p in ch["palaces"] for s in p["stars"] if s["name"] == "太阳")
        ids = {x["id"] for x in find_duanyu(ch)}
        assert ("gs-37-a" in ids) == (sun == ch["ming"] == "卯")


def test_xianyun_judge():
    ch = build_chart(datetime(1990, 5, 8, 9, 30), 0)
    for y in (2024, 2025, 2026):
        out = judge(ch, horoscope(ch, datetime(y, 6, 1, 12)))
        assert out and all(x["src"].startswith("紫微斗数全书·卷三·") and x["verdict"] in ("吉", "凶", "中") for x in out)
    # 天伤天使夹：只在限行迁移宫时出现（天伤在交友、天使在疾厄）
    random.seed(3)
    for _ in range(300):
        c = build_chart(datetime(random.randint(1950, 2005), random.randint(1, 12), random.randint(1, 28), 12), random.randint(0, 1))
        h = horoscope(c, datetime(2030, 3, 3, 12))
        qy = next(p["zhi"] for p in c["palaces"] if p["name"] == "迁移")
        for x in judge(c, h):
            if x["key"] == "伤使夹":
                L = next(l for l in h["layers"] if l["label"] == x["layer"])
                assert L["ming"] == qy
