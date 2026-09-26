"""紫微格局：照《紫微斗数全书》卷一「定富局」「定贵局」「定贫贱局」各条的释义字面判定。

每条返回书中原句（``text``）与本盘所据（``why``）。书里只写「见前批注」的条目、
杂局（论行限）这里不判。释义与安星法相矛盾、按字面永远不成立的条目也不判，
理由写在 ``SKIPPED`` 里（亦见 tianzhi-classics ziwei/collation.json）。

用语：守命＝在命宫；夹＝命宫前后两宫各一；拱＝三方（前后第四宫）与对宫。
庙旺取书中庙旺表（chart 里各星的 ``miao``），书中未载的格不算庙旺也不算陷。
"""
from __future__ import annotations

from .chart import ZHI, Z, at

SRC = "紫微斗数全书·"
SHA = ("擎羊", "陀罗", "火星", "铃星")
KONGWANG = ("截路空亡", "旬中空亡")


class _Pan:
    def __init__(self, chart: dict):
        self.c = chart
        self.by_zhi = {p["zhi"]: p for p in chart["palaces"]}
        self.by_name = {p["name"]: p["zhi"] for p in chart["palaces"]}
        self.pos: dict[str, list[str]] = {}
        self.star: dict[tuple[str, str], dict] = {}
        for p in chart["palaces"]:
            for s in p["stars"]:
                self.pos.setdefault(s["name"], []).append(p["zhi"])
                self.star[(s["name"], p["zhi"])] = s

    def names(self, z):
        return {s["name"] for s in self.by_zhi[z]["stars"]}

    def main(self, z):
        return [s["name"] for s in self.by_zhi[z]["stars"] if s["kind"] == "main"]

    def hua(self, h):
        return next((s["name"] for p in self.c["palaces"] for s in p["stars"] if s.get("hua") == h), None)

    def has_lu(self, z):
        """禄：禄存或化禄"""
        return "禄存" in self.names(z) or any(s.get("hua") == "禄" for s in self.by_zhi[z]["stars"])

    def miao(self, name, z):
        return self.star.get((name, z), {}).get("miao")

    def jia(self, z, a, b):
        """a、b 夹 z（前后各一，不论左右）"""
        l, r = at(z, -1), at(z, 1)
        return (a(l) and b(r)) or (a(r) and b(l))

    @staticmethod
    def gong(z):
        """拱：三方与对宫（不含本宫）"""
        return [at(z, 4), at(z, -4), at(z, 6)]


def _in(name):
    return lambda p, z: name in p.names(z)


# (名, 类, 原句, 判定)。判定 f(pan) -> 所据说明或 None
def _rules():
    R = []
    def rule(name, cat, text):
        def deco(f):
            R.append((name, cat, text, f)); return f
        return deco

    @rule("日月夹财", "富", "日月夹财 武守命日月来夹是也，财帛宫亦然。")
    def _(p):
        for g in ("命宫", "财帛"):
            z = p.by_name[g]
            if "武曲" in p.names(z) and p.jia(z, lambda x: "太阳" in p.names(x), lambda x: "太阴" in p.names(x)):
                return f"武曲在{g}（{z}），太阳、太阴前后夹"

    @rule("财禄夹马", "富", "财禄夹马 马守命武禄来夹是也，逢生旺尤妙。")
    def _(p):
        z = p.c["ming"]
        if "天马" in p.names(z) and p.jia(z, lambda x: "武曲" in p.names(x), p.has_lu):
            return f"天马守命（{z}），武曲与禄前后夹"

    @rule("日月照璧", "富", "日月照璧 日月临田宅宫是也，喜居墓库。")
    def _(p):
        z = p.by_name["田宅"]
        if {"太阳", "太阴"} <= p.names(z):
            return f"太阳、太阴同在田宅（{z}）"

    @rule("金灿光辉", "富", "金灿光辉 太阳单守，命在午宫是也。")
    def _(p):
        z = p.c["ming"]
        if z == "午" and p.main(z) == ["太阳"]:
            return "命在午，太阳独守"

    @rule("日月夹命", "贵", "日月夹命 不坐空亡遇逢本宫有吉星是也。")
    def _(p):
        z = p.c["ming"]
        if p.jia(z, lambda x: "太阳" in p.names(x), lambda x: "太阴" in p.names(x)) and not (p.names(z) & set(KONGWANG)) \
                and any(s["kind"] == "good" for s in p.by_zhi[z]["stars"]):
            return f"太阳、太阴夹命（{z}），命宫不坐空亡且有吉星"

    @rule("日出扶桑", "贵", "日出扶桑 日在卯守命是也，守官禄宫亦然。")
    def _(p):
        if "太阳" in p.names("卯") and p.by_zhi["卯"]["name"] in ("命宫", "官禄"):
            return f"太阳在卯守{p.by_zhi['卯']['name']}"

    @rule("月落亥宫", "贵", "月落亥宫 月在亥守命是也，又名月朗天门。")
    def _(p):
        if p.c["ming"] == "亥" and "太阴" in p.names("亥"):
            return "太阴在亥守命"

    @rule("月生沧海", "贵", "月生沧海 月在子宫守田宅是也。")
    def _(p):
        if p.by_name["田宅"] == "子" and "太阴" in p.names("子"):
            return "太阴在子守田宅"

    @rule("辅弼拱主", "贵", "辅弼拱主 紫微守命二星来拱是也，夹之亦然。")
    def _(p):
        z = p.c["ming"]
        if "紫微" not in p.names(z):
            return None
        g = p.gong(z)
        if any("左辅" in p.names(x) for x in g) and any("右弼" in p.names(x) for x in g):
            return f"紫微守命（{z}），左辅、右弼在三方对宫"
        if p.jia(z, lambda x: "左辅" in p.names(x), lambda x: "右弼" in p.names(x)):
            return f"紫微守命（{z}），左辅、右弼前后夹"

    @rule("君臣庆会", "贵", "君臣庆会 紫微左右同守命是也，更会相武阴妙上。")
    def _(p):
        z = p.c["ming"]
        if {"紫微", "左辅", "右弼"} <= p.names(z):
            return f"紫微、左辅、右弼同守命（{z}）"

    @rule("坐贵向贵", "贵", "坐贵向贵 谓魁钺在命迭相坐拱是也。")
    def _(p):
        z = p.c["ming"]
        for a, b in (("天魁", "天钺"), ("天钺", "天魁")):
            if a in p.names(z) and any(b in p.names(x) for x in p.gong(z)):
                return f"{a}坐命（{z}），{b}在三方对宫来拱"

    @rule("刑囚夹印", "贵", "刑囚夹印 天刑廉贞同临身命主武勇之人。")
    def _(p):
        for g, z in (("命宫", p.c["ming"]), ("身宫", p.c["shen"])):
            if {"天刑", "廉贞"} <= p.names(z):
                return f"天刑、廉贞同在{g}（{z}）"

    @rule("贪火相逢", "贵", "贪火相逢 谓二星守命同居庙旺是也。")
    def _(p):
        z = p.c["ming"]
        # 书中火星不分宫论庙旺（命宫一节火星条：「诸宫不美，惟贪狼庙旺同度」），以贪狼庙旺为准
        if {"贪狼", "火星"} <= p.names(z) and p.miao("贪狼", z) in ("庙", "旺"):
            return f"贪狼、火星同守命（{z}），贪狼庙旺"

    @rule("武曲守垣", "贵", "武曲守垣 武守命卯宫是也，余不是。")
    def _(p):
        if p.c["ming"] == "卯" and "武曲" in p.names("卯"):
            return "武曲在卯守命"

    @rule("权禄生逢", "贵", "权禄生逢 二星守命庙旺是也，陷不是。")
    def _(p):
        z = p.c["ming"]; lu, quan = p.hua("禄"), p.hua("权")
        if lu in p.names(z) and quan in p.names(z) and p.miao(lu, z) in ("庙", "旺") and p.miao(quan, z) in ("庙", "旺"):
            return f"化禄（{lu}）、化权（{quan}）同守命（{z}），俱庙旺"

    @rule("羊刃入庙", "贵", "羊刃入庙 辰戍丑未守命遇吉是也。")
    def _(p):
        z = p.c["ming"]
        if z in "辰戌丑未" and "擎羊" in p.names(z) and any(s["kind"] == "good" for s in p.by_zhi[z]["stars"]):
            return f"擎羊在{z}守命，同宫有吉星"

    @rule("生不逢时", "贫贱", "生不逢时 命坐空亡逢廉贞是也。")
    def _(p):
        z = p.c["ming"]; k = p.names(z) & set(KONGWANG)
        if k and "廉贞" in p.names(z):
            return f"命宫（{z}）有{'、'.join(sorted(k))}，又逢廉贞"

    @rule("禄逢两杀", "贫贱", "禄逢两杀 禄坐空亡又逢空劫杀星是也。")
    def _(p):
        z = p.c["ming"]
        if p.has_lu(z) and p.names(z) & set(KONGWANG) and p.names(z) & {"天空", "地劫"}:
            return f"命宫（{z}）禄坐空亡，又逢天空地劫"

    @rule("马落空亡", "贫贱", "马落空亡 马既落亡虽禄冲会无用主奔波。")
    def _(p):
        z = p.c["ming"]; k = p.names(z) & set(KONGWANG)
        if k and "天马" in p.names(z):
            return f"天马守命（{z}）落{'、'.join(sorted(k))}"

    @rule("一生孤贫", "贫贱", "一生孤贫 谓破守命星陷地是也。")
    def _(p):
        z = p.c["ming"]
        if "破军" in p.names(z) and p.miao("破军", z) == "陷":
            return f"破军守命（{z}）陷地"

    @rule("君子在野", "贫贱", "君子在野 谓四杀守身命而言临陷地是也。")
    def _(p):
        for g, z in (("命宫", p.c["ming"]), ("身宫", p.c["shen"])):
            bad = [s for s in SHA if s in p.names(z) and p.miao(s, z) == "陷"]
            if bad:
                return f"{'、'.join(bad)}守{g}（{z}）陷地"

    @rule("两重华盖", "贫贱", "两重华盖 谓禄存化禄坐命遇空劫是也。")
    def _(p):
        z = p.c["ming"]
        if "禄存" in p.names(z) and any(s.get("hua") == "禄" for s in p.by_zhi[z]["stars"]) and p.names(z) & {"天空", "地劫"}:
            return f"禄存、化禄同坐命（{z}），又遇天空地劫"

    return R


RULES = _rules()

# 释义与安星法相矛盾、按字面不会成立的条目
SKIPPED = {
    "财荫夹印": "释义「相守命武梁来夹」：武曲与天梁永不相隔一宫，夹不住任何一宫",
    "荫印拱身": "释义「身临田宅」：身宫只落命、夫妻、财帛、迁移、官禄、福德六宫，不临田宅",
    "金舆扶驾": "释义「紫微守命前后有日月来夹」：太阳恒在紫微后三宫，太阴随天府，夹不住紫微",
    "财印夹禄": "释义「禄守命梁相来夹」：天梁恒在天相顺行下一宫，二星相邻，不能分居一宫前后",
    "马头带剑": "释义「马有刃」：天马只落寅申巳亥，擎羊（禄存前一宫）只落卯辰午未酉戌子丑，二星不能同宫",
    "财与囚仇": "释义「武贞同守身命」：廉贞恒在武曲前四宫，二星不能同宫",
    "禄马佩印": "释义「马前有禄印星同宫」句读未定",
    "日月藏辉": "释义「日月反背又逢巨暗」，「反背」「逢」所指未定",
}


def find_geju(chart: dict) -> list[dict]:
    """返回本盘合的格局：[{name, cat 富/贵/贫贱, text 书中原句, why 本盘所据, src}]"""
    p = _Pan(chart)
    out = []
    for name, cat, text, f in RULES:
        why = f(p)
        if why:
            sec = {"富": "定富局", "贵": "定贵局", "贫贱": "定贫贱局"}[cat]
            out.append({"name": name, "cat": cat, "text": text, "why": why, "src": SRC + sec})
    return out
