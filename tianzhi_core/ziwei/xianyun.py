"""紫微运限论断：照《紫微斗数全书》卷三限运诸论，判一张盘某一时刻的大限、小限、流年。

horoscope() 只给出各层落在哪一宫、四化、流曜；这里再依卷三逐条论：
- 论大限十年祸福何如：限宫星曜庙旺与否、有无羊陀火铃空劫忌、所行宫位与所遇之星、伤使夹、羊陀夹与冲照；
- 论行限分南北斗：限宫主星属北斗者吉凶应在前五年（小限上半年），属南斗者应在后五年（小限下半年）；
  阳男阴女南斗为福，阴男阳女北斗为福；
- 论羊陀迭并、论七杀重逢：本命羊陀、七杀与流年流羊流陀相会；
- 论大小限星辰过十二宫遇十二支所忌诀：生年地支忌行某些岁限；
- 论太岁小限星辰庙陷遇十二宫中吉凶：太岁所临之宫遇哪些星主吉、哪些主凶，太岁与小限同宫时并看。
每条返回原句（text）、本盘所据（why）、吉凶方向（verdict）与出处（src）。只说「书中怎么论」。
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

from .chart import SRC, ZHI, at

# 论诸星分属南北斗化吉凶并分属五行（安星诸诀之末）
BEI = {"禄存", "廉贞", "武曲", "贪狼", "巨门", "破军", "文曲", "左辅", "右弼", "擎羊", "陀罗"}
NAN = {"天机", "天同", "天府", "天相", "天梁", "七杀", "火星", "铃星"}
BOTH = {"紫微", "太阳", "太阴", "文昌"}
SHA6 = {"擎羊", "陀罗", "火星", "铃星", "地劫", "天空"}
GOOD_AT_MENG = {"紫微", "天府", "天同", "太阳", "太阴", "文昌", "文曲", "禄存"}   # 「遇紫微天府天同太阳太阴昌曲禄存禄主吉星」
BAD_AT_MU = {"廉贞", "天使", "擎羊", "陀罗", "火星", "铃星", "地劫", "天空"}     # 「遇恶杀廉贞天使羊陀火铃空劫忌星」
# 论大小限星辰过十二宫遇十二支所忌诀：生年支 → 忌行的岁限之支（诀文与其下小注）
JI_SUIXIAN = {
    "子": ("寅申午", "人生子命忌寅申：子年生人切忌寅申岁限，灾晦至重，及忌子午岁限相冲"),
    "丑": ("丑午", "丑午生人丑午瞋：丑年生人忌午丑岁限"),
    "午": ("丑午", "丑午生人丑午瞋：午生人亦忌丑午岁限"),
    "寅": ("巳亥申", "寅卯之人防巳亥：寅卯人忌巳亥岁限，及忌卯酉寅申相冲"),
    "卯": ("巳亥酉", "寅卯之人防巳亥：寅卯人忌巳亥岁限，及忌卯酉寅申相冲"),
    "辰": ("辰戌", "龙蛇切忌本身临：辰生人忌行辰年又忌行到辰限为天罗，又忌行到戌为地网"),
    "巳": ("巳", "龙蛇切忌本身临：巳生人忌逢巳年及忌行到巳限"),
    "申": ("寅", "申人铃火灾殃重：申生人忌逢火铃二星，及忌寅年冲"),
    "未": ("酉戌", "未遇猪鸡墓患殷：未生人忌逢酉戌岁限，又忌见擎羊在四墓宫"),
    "戌": ("戌辰", "戌亥羊陀须避忌：戌生人又行到戌宫岁限为地网，又忌行到辰宫岁限为天罗"),
    "亥": ("巳", "猪犬生人莫遇蛇"),
    "酉": ("卯", "酉人陀刃亦非亲：酉生人亦忌羊陀岁限及忌行卯宫限，及卯年岁君相冲"),
}
JI_SHA = {"申": {"火星", "铃星"}, "戌": {"擎羊", "陀罗"}, "亥": {"擎羊", "陀罗"}, "酉": {"擎羊", "陀罗"}}   # 所忌诀中生年支忌逢之星


@lru_cache(maxsize=1)
def _taisui() -> dict:
    with resources.files("tianzhi_core.data").joinpath("ziwei_taisui.json").open(encoding="utf-8") as f:
        return json.load(f)


def _say(out, layer, key, text, why, verdict, src):
    out.append({"layer": layer, "key": key, "text": text, "why": why, "verdict": verdict, "src": SRC + "卷三·" + src})


def judge(chart: dict, horo: dict) -> list[dict]:
    """chart：build_chart 的结果；horo：horoscope(chart, when) 的结果。返回 [{layer, key, text, why, verdict, src}]"""
    by = {p["zhi"]: p for p in chart["palaces"]}
    names = lambda z: {s["name"] for s in by[z]["stars"]}   # noqa: E731
    hua_at = lambda z: [s["name"] for s in by[z]["stars"] if s.get("hua") == "忌"]   # noqa: E731
    L = {l["key"]: l for l in horo["layers"]}
    yz = chart["input"]["lunar"]["year"][1]
    gender = chart["input"]["gender"]
    yang = chart["input"]["lunar"]["year"][0] in "甲丙戊庚壬"
    out = []

    for key in ("daxian", "xiaoxian", "liunian"):
        l = L.get(key)
        if not l:
            continue
        z, lab = l["ming"], l["label"]
        p = by[z]; ns = names(z)
        mains = [s for s in p["stars"] if s["kind"] == "main"]
        sha = sorted(ns & SHA6); ji = hua_at(z)
        # 论大限十年祸福何如（大小二限与太岁同论）
        if key == "daxian":
            if mains and all(s.get("miao") in ("庙", "旺", "得") for s in mains) and not sha and not ji:
                _say(out, lab, "安静", "如宫分星缠全吉庙旺得地，无擎羊陀罗火铃空劫者，主十年安静，人财全美。",
                     f"{lab}在{z}，{'、'.join(s['name'] + s['miao'] for s in mains)}，宫中无羊陀火铃空劫忌", "吉", "论大限十年祸福何如")
            elif mains and any(s.get("miao") == "陷" for s in mains) and (sha or ji):
                _say(out, lab, "陷杀", "如宫分星缠陷地，值擎羊陀罗火铃空劫忌，又加流年恶杀凑合，及小限巡逢凶杀，则官灾死亡立见。",
                     f"{lab}在{z}，{'、'.join(s['name'] for s in mains if s.get('miao') == '陷')}落陷，又见{'、'.join(sha + [n + '化忌' for n in ji])}", "凶", "论大限十年祸福何如")
            elif sha or ji:
                _say(out, lab, "成败", "若限内有擎羊陀罗火铃空劫忌星为伴，成败不一。",
                     f"{lab}在{z}，见{'、'.join(sha + [n + '化忌' for n in ji])}", "中", "论大限十年祸福何如")
        good = sorted(ns & GOOD_AT_MENG)
        if z in "寅申巳亥子午" and good:
            _say(out, lab, "行生地", "凡行至寅申巳亥子午宫，遇紫微天府天同太阳太阴昌曲禄存禄主吉星，主人财兴旺，添丁进口之庆。",
                 f"{lab}行至{z}宫，遇{'、'.join(good)}", "吉", "论大限十年祸福何如")
        bad = sorted(ns & BAD_AT_MU) + [n + "化忌" for n in ji]
        if z in "辰戌丑未卯酉" and bad:
            _say(out, lab, "行墓地", "行至辰戍丑未卯酉，遇恶杀廉贞天使羊陀火铃空劫忌星，主人酒色荒迷，贫乏死生。",
                 f"{lab}行至{z}宫，遇{'、'.join(bad)}", "凶", "论大限十年祸福何如")
        fz = sorted(ns & {"左辅", "右弼", "文昌", "文曲"})
        if fz:
            _say(out, lab, "左右昌曲", "遇左右昌曲，仕宦迁官加职，士民生子发财，妇人喜事，僧道亦利，商贾得益。",
                 f"{lab}宫中有{'、'.join(fz)}", "吉", "论大限十年祸福何如")
        l1, r1 = names(at(z, -1)), names(at(z, 1))
        if ({"天伤"} <= l1 and {"天使"} <= r1) or ({"天使"} <= l1 and {"天伤"} <= r1):
            _say(out, lab, "伤使夹", "凡大小二限及太岁，怕行天伤天使夹地。",
                 f"{lab}在{z}，前后是天伤、天使", "凶", "论大限十年祸福何如")
        if ({"擎羊"} <= l1 and {"陀罗"} <= r1) or ({"陀罗"} <= l1 and {"擎羊"} <= r1):
            _say(out, lab, "羊陀夹", "羊陀守命尚且无用，况夹限乎。",
                 f"{lab}在{z}，前后是擎羊、陀罗", "凶", "论大限十年祸福何如")
        kj = sorted(ns & {"地劫", "天空", "擎羊", "陀罗"})
        if kj:
            _say(out, lab, "劫空羊陀", "怕行天空地劫之地，怕行擎羊陀罗之地。",
                 f"{lab}宫中有{'、'.join(kj)}", "凶", "论大限十年祸福何如")
        dui = sorted(names(at(z, 6)) & {"擎羊", "陀罗"})
        if dui:
            _say(out, lab, "羊陀冲照", "及羊陀冲照。", f"{lab}对宫有{'、'.join(dui)}", "凶", "论大限十年祸福何如")
        # 论行限分南北斗
        if key in ("daxian", "xiaoxian") and mains:
            bei = [s["name"] for s in mains if s["name"] in BEI]; nan = [s["name"] for s in mains if s["name"] in NAN]
            half = ("前五年", "后五年") if key == "daxian" else ("上半年", "下半年")
            fu = "南斗" if (yang and gender == 0) or (not yang and gender == 1) else "北斗"
            parts = []
            if bei: parts.append(f"{'、'.join(bei)}属北斗，吉凶应在{half[0]}")
            if nan: parts.append(f"{'、'.join(nan)}属南斗，吉凶应在{half[1]}")
            if parts:
                _say(out, lab, "南北斗", "阳男阴女南斗为福，阴男阳女北斗为福。北斗诸星吉凶，大限断上五年应，小限断上半年应。南斗诸星吉凶，大限断下五年应，小限断下半年应。",
                     "；".join(parts) + f"；此命{'阳' if yang else '阴'}{'男' if gender == 0 else '女'}，{fu}为福", "中", "论行限分南北斗")

    # 论羊陀迭并、论七杀重逢：看流年
    ln = L.get("liunian")
    if ln:
        m = chart["ming"]; sf = {m, at(m, 6), at(m, 4), at(m, -4)}
        liu = {n: z for z, ns in ln["stars"].items() for n in ns}
        ly, lt = liu.get("流羊"), liu.get("流陀")
        ben = {n: q["zhi"] for q in chart["palaces"] for s in q["stars"] for n in [s["name"]] if n in ("擎羊", "陀罗", "七杀")}
        if (ben.get("擎羊") in sf or ben.get("陀罗") in sf) and (ly in sf or lt in sf):
            _say(out, "流年", "羊陀迭并", "是命在卯宫原有酉宫擎羊冲合，流年又遇流羊流陀，谓之羊陀迭并。",
                 f"本命{'擎羊' if ben.get('擎羊') in sf else '陀罗'}在命宫三方四正，流年{'流羊' if ly in sf else '流陀'}又入命宫三方四正", "凶", "论羊陀迭并")
        if ben.get("七杀") in sf and (ly in sf or lt in sf):
            qs = by[ben["七杀"]]
            miao = next((s.get("miao") for s in qs["stars"] if s["name"] == "七杀"), None)
            jie = sorted({"紫微", "天相", "禄存"} & set().union(*[names(q) for q in sf]))
            why = f"本命七杀在{ben['七杀']}，照命宫；流年{'流羊' if ly in sf else '流陀'}又冲照"
            if miao == "庙": why += "；七杀入庙，书云灾晦减轻"
            if jie: why += f"；命宫三方有{'、'.join(jie)}，书云可解"
            _say(out, "流年", "七杀重逢", "如命中三合原有七杀守照，而流年又遇流羊流陀冲照凶，七杀重逢二者为祸最毒。入庙灾晦减轻……擎羊陀罗七杀逢紫微天相禄存三合拱照可解。",
                 why, "中" if (miao == "庙" or jie) else "凶", "论七杀重逢")
    # 论大小限星辰过十二宫遇十二支所忌诀：岁限＝流年太岁与小限
    if yz in JI_SUIXIAN:
        zs, line = JI_SUIXIAN[yz]
        for key in ("liunian", "xiaoxian"):
            l = L.get(key)
            if l and l["ming"] in zs:
                _say(out, l["label"], "所忌", line, f"生年属{yz}，{l['label']}行至{l['ming']}", "凶", "论大小限星辰过十二宫遇十二支所忌诀")
        for key in ("liunian", "xiaoxian"):
            l = L.get(key)
            hit = sorted(names(l["ming"]) & JI_SHA.get(yz, set())) if l else []
            if hit:
                _say(out, l["label"], "所忌星", line, f"生年属{yz}，{l['label']}宫中遇{'、'.join(hit)}", "凶", "论大小限星辰过十二宫遇十二支所忌诀")
    # 论太岁小限星辰庙陷遇十二宫中吉凶
    if ln:
        t = _taisui()[ln["zhi"]]
        ns = names(ln["ming"]) | {n + "化忌" for n in hua_at(ln["ming"])}
        g = [n for n in t["good"] if n in ns]
        b = [n for n in t["bad"] if n in ns or (n == "化忌" and hua_at(ln["ming"]))]
        if g or b:
            _say(out, "流年", "太岁所值", t["zhi"],
                 f"{ln['zhi']}年太岁在{ln['ming']}宫" + (f"，遇{'、'.join(g)}（吉）" if g else "") + (f"，遇{'、'.join(b)}（凶）" if b else ""),
                 "吉" if g and not b else "凶" if b and not g else "中", "论太岁小限星辰庙陷遇十二宫中吉凶")
        xx = L.get("xiaoxian")
        if xx and xx["ming"] == ln["ming"]:
            _say(out, "流年", "太岁并小限", f"{ln['zhi']}年太岁并小限到{ln['zhi']}宫入庙化吉：{t['ji']}　不入庙化凶：{t['xiong']}",
                 f"今年太岁与小限同在{ln['ming']}宫，书中此宫另有专论", "中", "论太岁小限星辰庙陷遇十二宫中吉凶")
    return out
