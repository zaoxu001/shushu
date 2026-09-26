"""紫微断语：把《紫微斗数全书》里一句句断语（卷三「诸星同垣」、卷一诸赋）写成盘上可判的条件，逐条判这张盘合不合。

原句一字不改放在 text（出处 src），判定条件 cond 是本包据原文与小注拟定的读法——哪里是读法，界面上照实说。
读不准的句子（泛论、比喻、论人事而无星位、需看相貌的）不判，写进 skip 并说明缘故，宁缺毋滥。
规则表在 tianzhi_core/data/ziwei_duanyu.json，条件的写法如下（P 为宫：命、身，或宫名财帛、官禄……）：

  {"stars": [...], "at": P, "mode": "all"|"any"}   这些星在 P 宫（缺省 all）。P 为「命身」时，命宫或身宫任一合即可
  {"none": [...], "at": P}                          这些星都不在 P 宫
  {"sanfang": P, "stars": [...], "mode": ...}        在 P 宫的三方四正（本宫、对宫、两个三合宫）
  {"jia": P, "stars": [a, b]}                        a、b 夹 P（前后各一，不论左右）；只给一颗则两边都要是它这一类见 kind
  {"zhi": P, "in": [地支...]}                        P 宫落在这些地支
  {"star_at": 星, "in": [地支...]}                   某星（不论在哪宫）落在这些地支
  {"miao": 星, "in": ["庙","旺",...]}                某星庙旺（取其所在宫）
  {"hua": 星, "in": ["禄","权","科","忌"]}           某星的生年四化
  {"hua_at": P, "in": [...], "mode": "any"|"all"}    P 宫有带这些化的星
  {"hua_sanfang": P, "in": [...], "mode": ...}       P 宫三方四正里有这些化
  {"gan": [...]}、{"yzhi": [...]}                    生年天干、地支
  {"gender": 0|1}                                    0 男 1 女
  {"day": true|false}                                昼生（卯至申时）/ 夜生
  {"and": [...]}、{"or": [...]}、{"not": {...}}
星名里「四杀」「六杀」「六吉」「化忌」可用：四杀＝擎羊陀罗火星铃星，六杀＝四杀加地劫天空，六吉＝左辅右弼文昌文曲天魁天钺。
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

from .chart import ZHI, at

GROUPS = {"四杀": ["擎羊", "陀罗", "火星", "铃星"], "六杀": ["擎羊", "陀罗", "火星", "铃星", "地劫", "天空"],
          "六吉": ["左辅", "右弼", "文昌", "文曲", "天魁", "天钺"], "空亡": ["截路空亡", "旬中空亡"]}
DAY = set("卯辰巳午未申")


@lru_cache(maxsize=1)
def rules() -> list:
    with resources.files("tianzhi_core.data").joinpath("ziwei_duanyu.json").open(encoding="utf-8") as f:
        return json.load(f)["rules"]


class _Pan:
    def __init__(self, chart):
        self.c = chart
        self.by = {p["zhi"]: p for p in chart["palaces"]}
        self.name = {p["name"]: p["zhi"] for p in chart["palaces"]}
        self.pos, self.hua, self.miao = {}, {}, {}
        for p in chart["palaces"]:
            for s in p["stars"]:
                self.pos[s["name"]] = p["zhi"]
                if s.get("hua"): self.hua[s["name"]] = s["hua"]
                if s.get("miao"): self.miao[s["name"]] = s["miao"]
        lunar = chart["input"]["lunar"]
        self.gan, self.yzhi, self.hour = lunar["year"][0], lunar["year"][1], lunar["hour"]

    def zhis(self, P):
        """宫名 → 地支（「命身」给两个）"""
        if P == "命": return [self.c["ming"]]
        if P == "身": return [self.c["shen"]]
        if P == "命身": return list(dict.fromkeys([self.c["ming"], self.c["shen"]]))
        if P in self.name: return [self.name[P]]
        if P in ("妻妾", "夫妻"): return [self.name["夫妻"]]
        if P in ("奴仆", "交友"): return [self.name["交友"]]
        raise ValueError(f"不认识的宫：{P}")

    def names(self, z):
        return {s["name"] for s in self.by[z]["stars"]}

    @staticmethod
    def expand(stars):
        out = []
        for s in stars: out += GROUPS.get(s, [s])
        return out

    def has(self, z, stars, mode):
        ns = self.names(z) | {"化" + h for s, h in self.hua.items() if self.pos.get(s) == z}
        ss = self.expand(stars)
        ok = [s in ns for s in ss]
        return all(ok) if mode == "all" else any(ok)


def _ev(p: _Pan, c: dict) -> bool:
    if "and" in c: return all(_ev(p, x) for x in c["and"])
    if "or" in c: return any(_ev(p, x) for x in c["or"])
    if "not" in c: return not _ev(p, c["not"])
    mode = c.get("mode", "all")
    if "stars" in c and "at" in c:
        return any(p.has(z, c["stars"], mode) for z in p.zhis(c["at"]))
    if "none" in c:
        return all(not p.has(z, c["none"], "any") for z in p.zhis(c["at"]))
    if "sanfang" in c:
        def sf(z):
            zs = [z, at(z, 6), at(z, 4), at(z, -4)]
            ss = p.expand(c["stars"])
            inn = [any(p.has(q, [s], "all") for q in zs) for s in ss]
            return all(inn) if mode == "all" else any(inn)
        return any(sf(z) for z in p.zhis(c["sanfang"]))
    if "jia" in c:
        a, b = (c["stars"] * 2)[:2]
        def jia(z):
            l, r = at(z, -1), at(z, 1)
            return (p.has(l, [a], "any") and p.has(r, [b], "any")) or (p.has(r, [a], "any") and p.has(l, [b], "any"))
        return any(jia(z) for z in p.zhis(c["jia"]))
    if "zhi" in c: return any(z in c["in"] for z in p.zhis(c["zhi"]))
    if "star_at" in c: return p.pos.get(c["star_at"]) in c["in"]
    if "miao" in c: return p.miao.get(c["miao"]) in c["in"]
    if "hua" in c: return p.hua.get(c["hua"]) in c["in"]
    if "hua_at" in c:
        hs = [p.hua[s] for s in p.hua if p.pos.get(s) in p.zhis(c["hua_at"])]
        ok = [h in hs for h in c["in"]]
        return all(ok) if mode == "all" else any(ok)
    if "hua_sanfang" in c:
        def hsf(z):
            zs = {z, at(z, 6), at(z, 4), at(z, -4)}
            hs = [p.hua[s] for s in p.hua if p.pos.get(s) in zs]
            ok = [h in hs for h in c["in"]]
            return all(ok) if mode == "all" else any(ok)
        return any(hsf(z) for z in p.zhis(c["hua_sanfang"]))
    if "gan" in c: return p.gan in c["gan"]
    if "yzhi" in c: return p.yzhi in c["yzhi"]
    if "gender" in c: return p.c["input"]["gender"] == c["gender"]
    if "day" in c: return (p.hour in DAY) == c["day"]
    raise ValueError(f"不认识的条件：{c}")


def validate(rule: dict) -> None:
    """规则表自检：条件里的每一项都认得（跑一张盘，异常即不合法）"""
    from datetime import datetime
    from .chart import build_chart
    _ev(_Pan(build_chart(datetime(1990, 5, 8, 9, 30), 0)), rule["cond"])


def find_duanyu(chart: dict) -> list[dict]:
    """这张盘合的断语：[{id, src, text, note, verdict, topic}]。skip 的不判"""
    p = _Pan(chart)
    out = []
    for r in rules():
        if r.get("skip") or not r.get("cond"):
            continue
        if _ev(p, r["cond"]):
            out.append({k: r[k] for k in ("id", "src", "text", "note", "verdict", "topic", "reading") if r.get(k) is not None})
    return out
