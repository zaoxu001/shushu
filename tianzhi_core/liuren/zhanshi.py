"""占事：按所问之事取类神，照《六壬大全》的断法逐条推出这一课对此事怎么论。

起课回答的是「盘是什么」，这里回答「这件事在盘上怎么看」。步骤都出自原书：

1. 取类神。卷八《事類神》：求官看青龙、太常与官星，求财看青龙与财爻，婚看天后，
   道路看白虎；「人事類神兼二三，以入課傳為取用；若是皆入皆不入，不用兼神責將神」。
   失物书中不在此歌之内，取卷二玄武条「凡占盗賊須責元武」。
2. 看类神：入不入课传（不入为局外，「有氣亦逺，無氣難」），旺相休囚，空亡，
   与日辰的生克合。
3. 各类事书中另有专条的，照专条判（青龙求财、天后占婚、玄武三传等，见卷二各将之下）。
4. 看三传：初传言事之始、末传决事之终（卷八物類課），用生终死、母子顺逆、初凶后吉
   （卷三發用）。
5. 看急迟与应期：用神与日辰在贵人前后（卷三），发用值岁、月、日（卷三）。

每条结论带 code、tone（+1 顺、-1 阻、0 只陈述）与出处标签；本包不出白话，
怎么说给人听是调用方的事。出处标签「六壬大全·占事·某」指回
tianzhi-classics liuren/entries/liurendaquan-zhanshi.json 的同名 key。
"""
from __future__ import annotations

from .pan import (GAN, GAN_JIGONG, WUXING_GAN, WUXING_ZHI, KE, TIAN_JIANG,
                  DAY_DE, liu_qin)
from .bifa import SHENG, CHANGSHENG, MU, LIUHE, SANHE, JIANG_WX
from ..core.ganzhi import wangxiang

SHI = ("事业", "求财", "感情", "出行", "寻物")

JI_JIANG = {"贵人", "六合", "青龙", "太常", "太阴", "天后"}      # 卷二天将总论：六吉将
XIONG_JIANG = {"腾蛇", "朱雀", "勾陈", "天空", "白虎", "玄武"}

# 每类事的类神：jiang 为将神（按书中次序，前者优先），yao 为兼神（六亲爻），
# ma 表示以驿马、天马为兼神。src 为该类神的出处。
LEISHEN = {
    "事业": {"jiang": ["青龙", "太常"], "yao": "官", "src": "事类神"},   # 求官龍常及官星
    "求财": {"jiang": ["青龙"], "yao": "财", "src": "事类神"},            # 求財青龍財爻通
    "感情": {"jiang": ["天后"], "yao": None, "src": "事类神"},            # 婚天后
    "出行": {"jiang": ["白虎"], "yao": None, "ma": True, "src": "事类神"},  # 路白虎；天馬驛馬入垣
    "寻物": {"jiang": ["玄武"], "yao": None, "src": "玄武盗贼"},
}

S = "六壬大全·占事·"


def _wx(x):
    return WUXING_GAN.get(x) or WUXING_ZHI.get(x) or JIANG_WX.get(x)


def _ke(a, b):
    return KE.get(_wx(a)) == _wx(b)


def _sheng(a, b):
    return SHENG.get(_wx(a)) == _wx(b)


def _he(a, b):
    """两支六合或同在一个三合里"""
    return LIUHE.get(a) == b or any(a in g and b in g and a != b for g in SANHE)


def _rel(x, gan):
    """x 对日干：生日 / 克日 / 日生 / 日克 / 比和"""
    if _sheng(x, gan):
        return "生日"
    if _ke(x, gan):
        return "克日"
    if _sheng(gan, x):
        return "日生"
    if _ke(gan, x):
        return "日克"
    return "比和"


class _Ke:
    """从 qike() 结果里取出判事要用的量"""
    def __init__(self, ke):
        self.ke = ke
        self.gan, self.zhi = ke["day_gan"], ke["day_zhi"]
        self.gong = GAN_JIGONG[self.gan]
        self.tdp = ke["tian_di_pan"]                           # 地盘 → 天盘
        self.below = {s: e for e, s in self.tdp.items()}      # 天盘 → 地盘
        self.tj = ke["tian_jiang_map"]                         # 天盘支 → 天将
        self.jiang_at = {j: s for s, j in self.tj.items()}    # 天将 → 所乘天盘支
        cls = ke["four_classes"]
        self.ke_up = {"干上": cls[0]["up"], "干阴": cls[1]["up"], "支上": cls[2]["up"], "支阴": cls[3]["up"]}
        ch = ke["three_chuan"]
        self.chuan = {"初传": ch["chu"]["zhi"], "中传": ch["zhong"]["zhi"], "末传": ch["mo"]["zhi"]}
        self.trio = list(self.chuan.values())
        self.kong = set(ke.get("xun_kong") or [])
        self.month_zhi = ke["ganzhi"]["month"][1]
        self.year_zhi = ke["ganzhi"]["year"][1]
        self.shensha = {s["name"]: s["zhi"] for s in ke.get("shen_sha") or []}

    def where(self, z):
        """z（天盘支）在课传何处；三传优先，其次四课。都不在为局外"""
        for k, v in self.chuan.items():
            if v == z:
                return k
        for k, v in self.ke_up.items():
            if v == z:
                return k
        return "局外"

    def void(self, z):
        """旬空，或坐在旬空的地盘上（落空）"""
        return z in self.kong or self.below.get(z) in self.kong

    def qi(self, z):
        return wangxiang(WUXING_ZHI[z], self.month_zhi)

    def with_ri_chen(self, z):
        """与日辰（日干、日支）相生或三六合"""
        sheng = _sheng(z, self.gan) or _sheng(self.gan, z) or _sheng(z, self.zhi) or _sheng(self.zhi, z)
        he = _he(z, self.gong) or _he(z, self.zhi)
        return sheng, he

    def front_of_gui(self, earth):
        """地盘某位上的天将在贵人前第几位。1–6 为前，7–11 为后，0 即贵人本位。
        卷三例：四月戊寅日午时，日干寄巳，上乘天空（贵前六），书仍说在贵神之前。"""
        return TIAN_JIANG.index(self.tj[self.tdp[earth]])


def _info(k: _Ke, name, z, kind):
    return {"name": name, "kind": kind, "zhi": z, "at": k.below.get(z, ""),
            "where": k.where(z), "qi": k.qi(z), "void": k.void(z),
            "jiang": k.tj.get(z, ""), "to_day": _rel(z, k.gan)}


def _pick(k: _Ke, shi):
    """取类神：将神、兼神各看入不入课传。只入一边的取那一边；都入或都不入，取将神"""
    spec = LEISHEN[shi]
    jiangs = [_info(k, j, k.jiang_at[j], "将") for j in spec["jiang"]]
    jiang = next((x for x in jiangs if x["where"] != "局外"), jiangs[0])
    jian = None
    if spec.get("yao"):
        places = list(k.chuan.items()) + list(k.ke_up.items())
        z = next((v for _, v in places if liu_qin(v, k.gan) == spec["yao"]), None)
        if z:
            jian = _info(k, spec["yao"] + "爻", z, "爻")
    elif spec.get("ma"):
        for nm in ("日马", "天马"):
            z = k.shensha.get(nm)
            if z and k.where(z) != "局外":
                jian = _info(k, "驿马" if nm == "日马" else "天马", z, "马")
                break
    j_in, y_in = jiang["where"] != "局外", bool(jian and jian["where"] != "局外")
    primary = jian if (y_in and not j_in) else jiang
    return primary, [x for x in [jiang, jian] if x]


def _f(code, tone, src, **args):
    return {"code": code, "tone": tone, "src": S + src, "args": args}


def _common(k: _Ke, p, shi):
    """类神的一般看法：入传与否、旺衰、空亡"""
    out = []
    good_qi = p["qi"] in ("旺", "相")
    if p["where"] == "局外":
        # 局外以有气无气定远近难易（「有氣亦逺，無氣難」），旺衰已在其中，不再另计一次
        out.append(_f("类神局外", 0 if good_qi else -1, "事类神", name=p["name"], qi=p["qi"]))
    else:
        out.append(_f("类神入传", 1, "事类神", name=p["name"], where=p["where"]))
        out.append(_f("类神旺衰", 1 if good_qi else -1, "旺衰", name=p["name"], qi=p["qi"]))
    if p["void"]:
        out.append(_f("类神空亡", -2, "空亡", name=p["name"]))
    return out


def _shiye(k: _Ke, p):
    out = []
    for j in ("青龙", "太常"):
        z = k.jiang_at[j]
        if z == k.year_zhi:                       # 太嵗作龍常必主遷轉
            out.append(_f("岁作龙常", 1, "龙常占官", jiang=j))
    if p["kind"] == "将":                         # 與日和合者吉，反此者凶
        sheng, he = k.with_ri_chen(p["zhi"])
        good = sheng or he
        out.append(_f("龙常和日" if good else "龙常不和", 1 if good else -1, "龙常占官", name=p["name"]))
    g = k.jiang_at["贵人"]                        # 干贵：贵人与日干
    r = _rel(g, k.gan)
    if r == "生日":
        out.append(_f("贵人生日", 1, "贵人"))
    elif r == "克日":
        out.append(_f("贵人克日", -1, "贵人"))
    if k.void(g):
        out.append(_f("贵人空亡", -1, "贵人空亡"))
    return out


def _qiucai(k: _Ke, _p):
    """青龙求财专条：旺相、临旺相乡、与日辰相生或三六合、入日辰三传——四者都要"""
    z = k.jiang_at["青龙"]
    sheng, he = k.with_ri_chen(z)
    at = k.below[z]
    conds = {
        "乘旺相气": k.qi(z) in ("旺", "相"),
        "临旺相乡": k.qi(at) in ("旺", "相"),
        "与日辰生合": sheng or he,
        "入日辰三传": k.where(z) != "局外",
    }
    lack = [c for c, ok in conds.items() if not ok]
    if not lack:
        return [_f("青龙求财全", 2, "青龙求财")]
    if not conds["入日辰三传"]:
        return [_f("青龙闲地", -2, "青龙求财", lack=lack)]
    return [_f("青龙求财缺", -1 if len(lack) > 1 else 0, "青龙求财", lack=lack)]


def _ganqing(k: _Ke, p):
    out = []
    z = k.jiang_at["天后"]
    sheng = _sheng(z, k.gan) or _sheng(k.gan, z)
    he = _he(z, k.gong) or _he(z, k.zhi)
    if sheng or he:
        out.append(_f("后日生合", 2, "天后占婚"))
    else:
        out.append(_f("后日不合", -1, "天后占婚"))
    if _ke(z, k.gan):
        out.append(_f("后克日", 0, "天后占婚"))
    elif _ke(k.gan, z):
        out.append(_f("日克后", 0, "天后占婚"))
    lh = k.jiang_at["六合"]
    if k.where(lh) in k.chuan and k.qi(lh) in ("旺", "相") and (_sheng(lh, k.gan) or _sheng(k.gan, lh)):
        out.append(_f("六合主婚", 1, "六合婚姻"))
    if z in k.trio and lh in k.trio:
        out.append(_f("后合同传", -1, "狡童佚女"))
    return out


def _chuxing(k: _Ke, p):
    out = []
    ma = [(nm, k.shensha.get(nm)) for nm in ("日马", "天马")]
    moving = [(nm, z) for nm, z in ma if z and z in k.trio]
    if moving:
        nm, z = moving[0]
        out.append(_f("马入传", 1, "马入垣", ma=nm, zhi=z, void=k.void(z)))
        if k.void(z):
            out.append(_f("马空", -1, "空亡", ma=nm))
    else:
        out.append(_f("马不入传", 0, "马入垣"))
    z = k.jiang_at["白虎"]
    r = _rel(z, k.gan)
    if r == "克日":
        out.append(_f("白虎克日", -1, "白虎道路"))
    elif r == "生日":
        out.append(_f("白虎生日", 1, "白虎道路"))
    w = k.where(z)
    if w in k.chuan:                               # 占行人以虎為准
        out.append(_f("行人", 0, "白虎行人", where=w))
    return out


def _xunwu(k: _Ke, p):
    """失物以玄武为本。获与不获，书中诸条各从一面说，逐条列出"""
    s1 = k.jiang_at["玄武"]
    out = [_f("玄武所在", 0, "玄武盗贼", where=k.where(s1), zhi=s1, at=k.below[s1])]
    s2 = k.tdp[s1]            # 玄武之阴：玄武所乘之神作地盘，其上之天盘神，谓之盗神
    s3 = k.tdp[s2]
    pairs = [(s1, s2), (s2, s3)]
    sheng = all(_sheng(a, b) or _sheng(b, a) for a, b in pairs)
    ke = any(_ke(a, b) or _ke(b, a) for a, b in pairs)
    ji = all(k.tj[x] in JI_JIANG for x in (s2, s3))
    xiong = any(k.tj[x] in XIONG_JIANG for x in (s2, s3))
    if sheng and ji:
        out.append(_f("玄武三传生吉", -2, "玄武盗贼", trio=[s1, s2, s3]))
    elif ke and xiong:
        out.append(_f("玄武三传克凶", 2, "玄武盗贼", trio=[s1, s2, s3]))
    if _ke(k.gan, s1):
        out.append(_f("日制玄武", 1, "玄武盗贼"))
    gou = k.jiang_at["勾陈"]
    if _ke(gou, s1):
        out.append(_f("勾制玄武", 1, "勾陈捕贼"))
    if gou == k.ke_up["干上"]:
        out.append(_f("勾临日干", 1, "勾陈捕贼"))
    if s1 == DAY_DE.get(k.gan) and k.where(s1) in ("干上", "支上"):
        out.append(_f("玄武附德", 2, "玄武附德"))
    for j, key, code in (("青龙", "青龙占盗", "龙入课"), ("六合", "六合占盗", "合入课"), ("太阴", "太阴占盗", "阴入课")):
        if k.where(k.jiang_at[j]) != "局外":
            out.append(_f(code, -1, key))
    return out


SPECIFIC = {"事业": _shiye, "求财": _qiucai, "感情": _ganqing, "出行": _chuxing, "寻物": _xunwu}


def _tone_of(k: _Ke, z):
    """一传的吉凶：看所乘天将，再以旺衰折之——凶将乘旺相不为凶，吉将乘休囚不为吉"""
    j = k.tj.get(z, "")
    good_qi = k.qi(z) in ("旺", "相")
    if j in JI_JIANG:
        return 1 if good_qi else 0
    if j in XIONG_JIANG:
        return 0 if good_qi else -1
    return 0


def shengsi(gan, chu, mo):
    """用生终死 / 用死终生：初传是日干五行的长生、末传是其墓，或反之（卷三）"""
    w = _wx(gan)
    if chu == CHANGSHENG[w] and mo == MU[w]:
        return "用生终死"
    if chu == MU[w] and mo == CHANGSHENG[w]:
        return "用死终生"
    return None


def muzi(chu, mo):
    """初传生末传为母传子（顺道）；末传生初传为子传母（失礼）（卷三）"""
    if _sheng(chu, mo):
        return "母传子"
    if _sheng(mo, chu):
        return "子传母"
    return None


def ying_ri(gan, good):
    """应日之干：吉卦取生日干者，凶卦取克日干者，阴阳与日干同（卷三：甲日吉应壬，戊日凶应甲）"""
    yang = GAN.index(gan) % 2
    w = _wx(gan)
    return next((g for g in GAN if GAN.index(g) % 2 == yang and
                 (SHENG[WUXING_GAN[g]] == w if good else KE[WUXING_GAN[g]] == w)), None)


def _course(k: _Ke):
    """三传始终"""
    out = []
    chu, zhong, mo = k.trio
    a, b = _tone_of(k, chu), _tone_of(k, mo)
    shape = {(1, 1): "始终皆顺", (-1, -1): "始终皆阻", (-1, 1): "先阻后顺", (1, -1): "先顺后阻"}.get((a, b))
    if shape is None:
        shape = "先阻后平" if a < 0 else "先顺后平" if a > 0 else "先平后阻" if b < 0 else "先平后顺" if b > 0 else "平"
    tone = {"始终皆顺": 2, "先阻后顺": 1, "先平后顺": 1, "先顺后平": 0, "平": 0,
            "先阻后平": -1, "先顺后阻": -1, "先平后阻": -1, "始终皆阻": -2}[shape]
    out.append(_f("三传始终", tone, "始终" if shape in ("先阻后顺", "先顺后阻") else "物类",
                  shape=shape, chu=[chu, k.tj.get(chu, "")], mo=[mo, k.tj.get(mo, "")]))
    sx = shengsi(k.gan, chu, mo)
    if sx:
        out.append(_f(sx, -1 if sx == "用生终死" else 1, "生死"))
    mz = muzi(chu, mo)
    if mz:
        out.append(_f(mz, 1 if mz == "母传子" else -1, "母子"))
    if tone < 0:                                   # 若遇徳生名有救
        de = DAY_DE.get(k.gan)
        if de in k.trio or any(_sheng(x, k.gan) for x in k.trio):
            out.append(_f("三传有救", 1, "三传有救"))
    return out


def _pace(k: _Ke):
    """事之急迟：用神与日辰都在贵人之前为急，都在之后为迟"""
    pts = [k.below[k.trio[0]], k.gong, k.zhi]
    d = [k.front_of_gui(e) for e in pts]
    if all(1 <= x <= 6 for x in d):
        return _f("事急", 0, "急迟")
    if all(7 <= x <= 11 for x in d):
        return _f("事迟", 0, "急迟")
    return None


def _timing(k: _Ke, good: bool):
    out = []
    chu = k.trio[0]
    if chu == k.year_zhi:
        out.append(_f("应在年内", 0, "应期", zhi=chu))
    if chu == k.month_zhi:
        out.append(_f("应在月内", 0, "应期", zhi=chu))
    if chu == k.zhi:
        out.append(_f("应在旬内", 0, "应期", zhi=chu))
    if chu == k.gong:
        out.append(_f("应在朝夕", 0, "应期", zhi=chu))
    g = ying_ri(k.gan, good)
    if g:
        out.append(_f("应日", 0, "应日", gan=g, good=good))
    return out


def read(ke: dict, shi: str) -> dict:
    """qike() 的结果 + 所问之事 → 这一课对此事的论断（结构化，带出处）。

    返回 {shi, leishen, primary, facts, course, pace, timing, score, trend}。
    trend 为「顺 / 可成 / 未定 / 多阻 / 难」，由各条 tone 相加而得，加法本身是本包取值；
    每条的方向（顺还是阻）都照原文。
    """
    if shi not in SHI:
        raise ValueError(f"所问之事只能是 {SHI} 之一：{shi!r}")
    k = _Ke(ke)
    primary, all_ls = _pick(k, shi)
    # 失物的玄武是盗神，旺相、入课对失主不是好事，一般看法不适用，只照玄武诸专条
    facts = ([] if shi == "寻物" else _common(k, primary, shi)) + SPECIFIC[shi](k, primary)
    course = _course(k)
    score = sum(f["tone"] for f in facts + course)
    trend = "顺" if score >= 4 else "可成" if score >= 2 else "未定" if score >= 0 else "多阻" if score >= -2 else "难"
    if primary["void"] and trend in ("顺", "可成"):
        trend = "未定"                              # 类神落空：当喜不喜
    pace = _pace(k)
    timing = _timing(k, score >= 0)
    return {"shi": shi, "leishen": all_ls, "primary": primary, "facts": facts,
            "course": course, "pace": pace, "timing": timing, "score": score, "trend": trend,
            "keti": keti_says(ke.get("keti") or [], shi)}


# 课体象辞里论到此类事的原话（卷五至卷八各课「象曰」，原样截取）。
# 「通」是不分事类的总论，某类事没有专句时才取。
KETI_SHI = {
    "元首": {"事业": "官職首擢", "求财": "市賈出色名利超羣", "感情": "婚諧鸞鳯", "通": "天地得位品物咸新"},
    "重审": {"通": "諸般謀望先難後成"},
    "知一": {"寻物": "尋人失物近處堪求", "通": "事向朋謀"},
    "涉害": {"事业": "謀為利名多費機闗", "求财": "謀為利名多費機闗", "感情": "婚姻有阻", "通": "風波險惡度渉艱難"},
    "遥克": {"事业": "文書虚謀", "通": "憂喜未實"},
    "昴星": {"出行": "闗梁閉塞越度稽留", "通": "家居守静方免閒憂"},
    "别责": {"求财": "財物不全", "感情": "求婚别娶", "通": "謀為處正"},
    "八专": {"事业": "成功異路顯擢士林", "寻物": "物失内尋", "通": "二人同心其利斷金"},
    "伏吟": {"事业": "科舉高中求名榮歸", "通": "律身謹慎動作無虞"},
    "返吟": {"求财": "得物尤失敗物反成", "寻物": "得物尤失敗物反成", "通": "髙岸為谷深谷為陵"},
    "铸印": {"事业": "官職高擢詔命重宣"},
    "斫轮": {"事业": "禄位加增官職超擢", "求财": "財喜懽躍"},
    "轩盖": {"事业": "朱輪稳上詔用榮宣", "求财": "求財大獲", "出行": "行者必旋"},
    "引从": {"事业": "官職陞遷名利榮耀", "感情": "婚招金玉", "出行": "出行取財"},
    "闭口": {"寻物": "尋人没影失物潛藏", "通": "事跡難明"},
    "三交": {"事业": "謀事不明", "求财": "求財無益", "通": "謀事不明"},
    "淫泆": {"感情": "嫁娶不吉", "寻物": "捕捉難獲"},
    "度厄": {"出行": "行者多災", "通": "類神旺相禍去福來"},
    "无禄": {"通": "求謀不遂動作多疑"},
    "六仪": {"事业": "干貴逢時", "通": "兆多喜慶"},
    "三奇": {"事业": "士有竒遇", "感情": "婚求淑女", "通": "萬事和合千殃觧除"},
    "殃咎": {"事业": "營幹不一", "出行": "出行不樂", "通": "營幹不一"},
    "鬼墓": {"寻物": "捕盗深藏", "出行": "行人可至", "通": "謀為遲滯"},
    "全局": {"事业": "有官官易就", "求财": "求財有財財易得", "感情": "利合婚姻", "通": "吉事必成凶事難棄"},
    "玄胎": {"事业": "官加恩爵", "求财": "財利叠興", "感情": "婚獲娉婷"},
    "连珠": {"通": "凶則重重吉當累累"},
}


def keti_says(keti: list[dict], shi: str) -> list[dict]:
    out = []
    for h in keti:
        t = KETI_SHI.get(h["name"], {})
        s = t.get(shi) or t.get("通")
        if s:
            out.append({"keti": h["name"], "text": s, "specific": shi in t, "src": f"六壬大全·{h['name']}课"})
    return out
