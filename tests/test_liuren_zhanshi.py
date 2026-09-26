"""占事判定：书中有实例的规则用书中的例子核，其余核取类神的次第与各条的方向。

例子出《六壬大全》卷三「發用」各句之注（tianzhi-classics liuren/entries/liurendaquan-zhanshi.json）。
"""
import pytest

from tianzhi_core.liuren import zhanshi
from tianzhi_core.liuren.pan import (build_tian_di_pan, build_four_classes, get_three_chuan,
                                     build_tian_jiang_map, get_xun_kong, get_shen_sha, qike)


def ke_of(day_gz, yue_jiang, zhan_shi, is_day, month_zhi="寅", year_zhi="子"):
    """只给日干支、月将、占时、昼夜，拼出 read() 要的起课结果"""
    gan, zhi = day_gz
    tdp = build_tian_di_pan(yue_jiang, zhan_shi)
    cls = build_four_classes(gan, zhi, tdp)
    ch = get_three_chuan(cls, tdp, gan, zhi)
    return {"day_gan": gan, "day_zhi": zhi, "tian_di_pan": tdp,
            "tian_jiang_map": build_tian_jiang_map(gan, is_day, tdp), "four_classes": cls,
            "three_chuan": {"method": ch["method"], **{k: {"zhi": ch[k]} for k in ("chu", "zhong", "mo")}},
            "xun_kong": get_xun_kong(day_gz), "shen_sha": get_shen_sha(gan, zhi, month_zhi),
            "ganzhi": {"month": "丙" + month_zhi, "year": "丙" + year_zhi}, "keti": []}


def test_pace_book_examples():
    # 四月戊寅日午时，传送加时，天罡临寅为用，大吉为贵神临亥顺行：用神日辰俱在贵神前，事急
    k = zhanshi._Ke(ke_of("戊寅", "申", "午", True, month_zhi="巳"))
    assert k.trio[0] == "辰" and k.below["丑"] == "亥"
    assert zhanshi._pace(k)["code"] == "事急"
    # 正月壬子日辰时，登明加时，胜光临壬为用，天乙加戌逆行：俱在贵人后，事迟
    k = zhanshi._Ke(ke_of("壬子", "亥", "辰", True))
    assert k.trio[0] == "午" and k.below["巳"] == "戌"
    assert zhanshi._pace(k)["code"] == "事迟"


def test_timing_book_examples():
    # 甲子日以功曹为用，是用日（甲寄寅）：克期在朝晚
    k = zhanshi._Ke(ke_of("甲子", "丑", "卯", True))
    k.trio = ["寅", "", ""]
    assert "应在朝夕" in [t["code"] for t in zhanshi._timing(k, True)]
    # 戊子日用起神后，是今日辰：应一旬之内
    k = zhanshi._Ke(ke_of("戊子", "丑", "卯", True))
    k.trio = ["子", "", ""]
    assert "应在旬内" in [t["code"] for t in zhanshi._timing(k, True)]


def test_ying_ri_book_examples():
    assert zhanshi.ying_ri("甲", True) == "壬"    # 甲子日吉卦，应在壬日
    assert zhanshi.ying_ri("戊", False) == "甲"   # 戊日凶卦，应在甲日


@pytest.mark.parametrize("gan,chu,mo,want", [
    ("甲", "亥", "未", "用生终死"), ("丙", "寅", "戌", "用生终死"),
    ("庚", "丑", "巳", "用死终生"), ("壬", "辰", "申", "用死终生"),
])
def test_shengsi_book_examples(gan, chu, mo, want):
    assert zhanshi.shengsi(gan, chu, mo) == want


def test_muzi_book_examples():
    assert zhanshi.muzi("寅", "午") == "母传子"   # 初用功曹木，末见胜光火
    assert zhanshi.muzi("子", "申") == "子传母"   # 初用神后水，末传传送金


def test_pick_rule():
    """人事类神兼二三：只入一边取那一边，都入或都不入取将神"""
    for d in ["甲子", "丁卯", "庚戌", "癸巳", "丙辰"]:
        for yj, zs in [("子", "卯"), ("申", "巳"), ("亥", "丑"), ("午", "午")]:
            k = zhanshi._Ke(ke_of(d, yj, zs, True))
            p, both = zhanshi._pick(k, "求财")
            j = both[0]
            y = both[1] if len(both) > 1 else None
            if y and y["where"] != "局外" and j["where"] == "局外":
                assert p is y
            else:
                assert p is j and p["name"] == "青龙"


def test_read_all_kinds_on_real_casts():
    for m in range(1, 13):
        ke = qike(2026, m, 7 + m, (m * 5) % 24, 10)
        for shi in zhanshi.SHI:
            r = zhanshi.read(ke, shi)
            assert r["trend"] in ("顺", "可成", "未定", "多阻", "难")
            for f in r["facts"] + r["course"] + r["timing"]:
                assert f["src"].startswith("六壬大全·占事·")
            for s in r["keti"]:
                assert s["text"]


def test_keti_quotes_are_verbatim():
    """课体象辞截句必须原样出现在该课的象曰里"""
    import json, os
    path = os.path.join(os.path.dirname(__file__), "..", "..", "tianzhi-classics", "liuren", "entries", "liurendaquan-keti.json")
    if not os.path.exists(path):
        pytest.skip("没有 tianzhi-classics")
    trad = {"元首": "元首課", "重审": "重審課", "知一": "知一課", "涉害": "渉害課", "遥克": "遥克課", "昴星": "昴星課",
            "别责": "别責課", "八专": "八專課", "伏吟": "伏吟課", "返吟": "返吟課", "铸印": "鑄印課", "斫轮": "斵輪課",
            "轩盖": "軒盖課", "引从": "引從課", "闭口": "閉口課", "三交": "三交課", "淫泆": "淫泆課", "度厄": "度厄課",
            "无禄": "無祿絶嗣課", "六仪": "六儀課", "三奇": "三竒課", "殃咎": "殃咎課", "鬼墓": "鬼墓課", "全局": "全局課",
            "玄胎": "玄胎課", "连珠": "連珠課"}
    xiang = {x["name"]: x.get("xiang", "") for x in json.load(open(path))["items"]}
    for name, d in zhanshi.KETI_SHI.items():
        for s in d.values():
            assert s in xiang[trad[name]], (name, s)


def test_bad_shi():
    with pytest.raises(ValueError):
        zhanshi.read(qike(2026, 9, 25, 16, 30), "疾病")
