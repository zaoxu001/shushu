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
