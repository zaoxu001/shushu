"""毕法赋百句中，条件可在课式上直接判定的句子。

赋文与各句之注出《六壬大全》卷九、卷十（tianzhi-classics：liuren/entries/liurendaquan-bifa.json）。
这里每一条的判定都照该句的注；`rule` 写明本包对注文的理解，与原文分开，不相混淆。
要用到占者年命、行年、占类或季节生死炁的句子暂未收。
"""
from __future__ import annotations

from .pan import (ZHI, GAN, GAN_JIGONG, WUXING_GAN, WUXING_ZHI, KE, add_zhi,
                  build_tian_di_pan, build_four_classes, get_three_chuan, build_tian_jiang_map,
                  get_xun_shou, get_xun_kong)

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
# 五行十二宫：水土同宫（与课体表的墓同一口径）
CHANGSHENG = {"木": "亥", "火": "寅", "金": "巳", "水": "申", "土": "申"}
BAI = {"木": "子", "火": "卯", "金": "午", "水": "酉", "土": "酉"}        # 沐浴，即败
WANG = {"木": "卯", "火": "午", "金": "酉", "水": "子", "土": "子"}       # 帝旺
SI = {"木": "午", "火": "酉", "金": "子", "水": "卯", "土": "卯"}
MU = {"木": "未", "火": "戌", "金": "丑", "水": "辰", "土": "辰"}
JUE = {"木": "申", "火": "亥", "金": "寅", "水": "巳", "土": "巳"}
LU = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳", "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
SANHE = [set("申子辰"), set("寅午戌"), set("巳酉丑"), set("亥卯未")]
YIMA = {**dict.fromkeys("申子辰", "寅"), **dict.fromkeys("寅午戌", "申"), **dict.fromkeys("巳酉丑", "亥"), **dict.fromkeys("亥卯未", "巳")}
HUAGAI = {**dict.fromkeys("寅午戌", "戌"), **dict.fromkeys("申子辰", "辰"), **dict.fromkeys("巳酉丑", "丑"), **dict.fromkeys("亥卯未", "未")}
LIUHE = {"子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯", "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午"}
LIUHAI = {"子": "未", "未": "子", "丑": "午", "午": "丑", "寅": "巳", "巳": "寅", "卯": "辰", "辰": "卯", "申": "亥", "亥": "申", "酉": "戌", "戌": "酉"}
JIANG_WX = {"贵人": "土", "腾蛇": "火", "螣蛇": "火", "朱雀": "火", "六合": "木", "勾陈": "土", "青龙": "木",
            "天空": "土", "白虎": "金", "太常": "土", "玄武": "水", "太阴": "金", "天后": "水"}


def wx(x):
    return WUXING_GAN.get(x) or WUXING_ZHI.get(x) or JIANG_WX.get(x)


def ke(a, b):
    return KE.get(wx(a)) == wx(b)


def sheng(a, b):
    return SHENG.get(wx(a)) == wx(b)


class Ctx:
    """一课里毕法要看的量，一次算齐"""
    def __init__(self, day_gz, tdp, classes, chuan, tj):
        self.gan, self.zhi = day_gz[0], day_gz[1]
        self.gong = GAN_JIGONG[self.gan]
        self.tdp, self.tj, self.classes = tdp, tj, classes
        self.below = {s: e for e, s in tdp.items()}
        self.gu, self.zu = classes[0]["up"], classes[2]["up"]       # 干上神、支上神
        self.chu, self.zhong, self.mo = chuan["chu"], chuan["zhong"], chuan["mo"]
        self.trio = [self.chu, self.zhong, self.mo]
        self.method = chuan["method"]
        xs = get_xun_shou(day_gz)
        self.xun_head = xs[1]
        self.xun_ding = add_zhi(self.xun_head, 3)                      # 旬内丁神
        self.kong = set(get_xun_kong(day_gz))
        self.gw, self.zw = WUXING_GAN[self.gan], WUXING_ZHI[self.zhi]
        self.gui = next((k for k, v in tj.items() if v == "贵人"), None)
        # 三传的「局」五行：成三合取局之五行，三传同一五行取之，否则无
        ws = {wx(x) for x in self.trio}
        hj = {"申子辰": "水", "寅午戌": "火", "巳酉丑": "金", "亥卯未": "木"}
        self.ju = next((w for k, w in hj.items() if set(self.trio) == set(k)), None) or (ws.pop() if len(ws) == 1 else None)

    def jiang(self, sky):
        return self.tj.get(sky)

    def void(self, x):
        """空：本身旬空（游行空亡），或坐在旬空的地盘上（落底空亡）。卷十第九十四句注分此二种。"""
        return x in self.kong or self.below.get(x) in self.kong


def _jue(w):
    return {JUE[w], "亥"} if w == "土" else {JUE[w]}


def _gui_diff(c):  # 同阴阳克日者为鬼（七杀）；毕法注中「日鬼」泛指克日者，这里取克日即是
    return lambda x: ke(x, c.gan)


# (序号, 赋文, 本包对注文的理解, 判定)
RULES = [
    (1, "前後引從陞遷吉", "初传居干上神前一辰、末传居其后一辰（引干）；或同样夹着支上神（引支）",
     lambda c: (c.chu == add_zhi(c.gu, 1) and c.mo == add_zhi(c.gu, -1)) or (c.chu == add_zhi(c.zu, 1) and c.mo == add_zhi(c.zu, -1))),
    (2, "首尾相見始終宜", "干上、支上分别是旬首与旬尾（一旬周遍）",
     lambda c: {c.gu, c.zu} == {c.xun_head, add_zhi(c.xun_head, 9)}),
    (5, "六陽數足須公用", "四课上神与三传皆居阳支",
     lambda c: all(ZHI.index(x) % 2 == 0 for x in [k["up"] for k in c.classes] + c.trio)),
    (6, "六陰相繼儘昏迷", "四课上神与三传皆居阴支",
     lambda c: all(ZHI.index(x) % 2 == 1 for x in [k["up"] for k in c.classes] + c.trio)),
    (7, "旺禄臨身徒妄作", "日禄临干上，且此禄又是日干五行的旺地",
     lambda c: c.gu == LU[c.gan] and c.gu == WANG[c.gw]),
    (8, "權攝不正禄臨支", "日禄临支上",
     lambda c: c.zu == LU[c.gan]),
    (15, "脱上逢脱防虚詐", "日干生干上神，干上神又生其所乘天将",
     lambda c: sheng(c.gan, c.gu) and c.jiang(c.gu) and sheng(c.gu, c.jiang(c.gu))),
    (16, "空上逢空事莫追", "干上神旬空，又乘天空",
     lambda c: c.gu in c.kong and c.jiang(c.gu) == "天空"),
    (21, "交車相合交闗利", "干上神与支相合，支上神与干（寄宫）相合",
     lambda c: LIUHE[c.gu] == c.zhi and LIUHE[c.zu] == c.gong),
    (22, "上下相合兩心齊", "干上神与支上神六合，地盘干（寄宫）与支亦六合",
     lambda c: LIUHE[c.gu] == c.zu and LIUHE[c.gong] == c.zhi),
    (23, "彼求我事支傳干", "初传是支上神，末传归干上神",
     lambda c: c.chu == c.zu and c.mo == c.gu and c.gu != c.zu),
    (24, "我求彼事干傳支", "初传是干上神，末传归支上神",
     lambda c: c.chu == c.gu and c.mo == c.zu and c.gu != c.zu),
    (25, "金日逢丁㐫禍動", "庚辛日，干上、支上或三传见旬内丁神",
     lambda c: c.gan in "庚辛" and c.xun_ding in [c.gu, c.zu] + c.trio),
    (26, "水日逢丁財動之", "壬癸日，干上、支上或三传见旬内丁神",
     lambda c: c.gan in "壬癸" and c.xun_ding in [c.gu, c.zu] + c.trio),
    (27, "傳財化鬼財休覔", "三传之局为日财，而生起克日的干上神（「三未卯亥皆作木局為日之財……即生起干上」午火）",
     lambda c: c.ju and KE[c.gw] == c.ju and ke(c.gu, c.gan) and SHENG[c.ju] == wx(c.gu)),
    (29, "眷属豐盈居狹宅", "三传之局生日干，而支生此局（脱支）",
     lambda c: c.ju and SHENG[c.ju] == c.gw and SHENG[c.zw] == c.ju),
    (30, "屋宅寛廣致人衰", "日干生三传之局（盗干），而此局生支",
     lambda c: c.ju and SHENG[c.gw] == c.ju and SHENG[c.ju] == c.zw),
    (31, "三傳逓生人舉薦", "初生中、中生末、末生日干；或末生中、中生初、初生日干",
     lambda c: (sheng(c.chu, c.zhong) and sheng(c.zhong, c.mo) and sheng(c.mo, c.gan)) or (sheng(c.mo, c.zhong) and sheng(c.zhong, c.chu) and sheng(c.chu, c.gan))),
    (32, "三傳互尅衆人欺", "初克中、中克末、末克日干；或末克中、中克初、初克日干",
     lambda c: (ke(c.chu, c.zhong) and ke(c.zhong, c.mo) and ke(c.mo, c.gan)) or (ke(c.mo, c.zhong) and ke(c.zhong, c.chu) and ke(c.chu, c.gan))),
    (33, "有始無終難變易", "初传为日干长生、末传为日干之墓（有始无终）；或反之（难变易）",
     lambda c: {c.chu, c.mo} == {CHANGSHENG[c.gw], MU[c.gw]}),
    (35, "人宅受脱俱招盜", "干上神脱干、支上神脱支；或干上神脱支、支上神脱干",
     lambda c: (sheng(c.gan, c.gu) and sheng(c.zhi, c.zu)) or (sheng(c.zhi, c.gu) and sheng(c.gan, c.zu))),
    (36, "干支皆敗勢傾頽", "干上神为日干之败（沐浴），支上神为日支之败",
     lambda c: c.gu == BAI[c.gw] and c.zu == BAI[c.zw]),
    (40, "后合占婚豈用媒", "干上、支上分乘天后与六合",
     lambda c: {c.jiang(c.gu), c.jiang(c.zu)} == {"天后", "六合"}),
    (41, "富貴干支逢禄馬", "干上神为支之驿马，支上神为干禄",
     lambda c: c.gu == YIMA[c.zhi] and c.zu == LU[c.gan]),
    (47, "貴雖坐獄宜臨干", "天乙贵人立于地盘辰戌（乙辛日为贵人临身，余日为入狱）",
     lambda c: c.gui is not None and c.below.get(c.gui) in ("辰", "戌")),
    (51, "魁度天門闗隔定", "初传戌临地盘亥",
     lambda c: c.chu == "戌" and c.below.get("戌") == "亥"),
    (52, "罡雖鬼户任謀為", "天盘辰临地盘寅（不论发用）",
     lambda c: c.below.get("辰") == "寅"),
    (55, "所謀多拙逢羅網", "干上乘干（寄宫）前一辰，支上乘支前一辰（天罗地网）",
     lambda c: c.gu == add_zhi(c.gong, 1) and c.zu == add_zhi(c.zhi, 1)),
    (59, "華蓋覆日人昏晦", "支之华盖即日干之墓，临干上而发用",
     lambda c: c.chu == c.gu == MU[c.gw] == HUAGAI[c.zhi]),
    (61, "干乘墓虎無占病", "干上神为日干之墓，乘白虎",
     lambda c: c.gu == MU[c.gw] and c.jiang(c.gu) == "白虎"),
    (62, "支乘墓虎有伏屍", "支上神为干墓或支墓，乘白虎",
     lambda c: c.zu in (MU[c.gw], MU[c.zw]) and c.jiang(c.zu) == "白虎"),
    (63, "彼此全傷防兩損", "干被干上神克，支被支上神克",
     lambda c: ke(c.gu, c.gan) and ke(c.zu, c.zhi)),
    (64, "夫妻蕪淫各有私", "干被支上神克，支被干上神克",
     lambda c: ke(c.zu, c.gan) and ke(c.gu, c.zhi)),
    (70, "鬼臨三四訟災隨", "第三、第四课上神都克日干",
     lambda c: ke(c.classes[2]["up"], c.gan) and ke(c.classes[3]["up"], c.gan)),
    (74, "空空如也事休追", "三传每一传或空（旬空、落空）、或乘天空，且至少两传空",
     lambda c: all(c.void(x) or c.jiang(x) == "天空" for x in c.trio) and sum(c.void(x) for x in c.trio) >= 2),
    (75, "賔主不投形在上", "四课上神全是自刑之神（辰午酉亥）",
     lambda c: all(k["up"] in "辰午酉亥" for k in c.classes)),
    (76, "彼此猜忌害相隨", "干上神与干（寄宫）六害，支上神与支六害",
     lambda c: LIUHAI[c.gu] == c.gong and LIUHAI[c.zu] == c.zhi),
    (77, "互生俱生凡事益", "干上神生支，支上神生干",
     lambda c: sheng(c.gu, c.zhi) and sheng(c.zu, c.gan)),
    (78, "互旺皆旺坐謀宜", "干上神为支之旺，支上神为干之旺",
     lambda c: c.gu == WANG[c.zw] and c.zu == WANG[c.gw]),
    (79, "干支值絶凡謀決", "干上神为干之绝，支上神为支之绝。土之绝注中两说并存：水土同宫绝在巳，土寄寅者绝在亥",
     lambda c: c.gu in _jue(c.gw) and c.zu in _jue(c.zw)),
    (80, "人宅皆死各衰羸", "干上神为干之死，支上神为支之死",
     lambda c: c.gu == SI[c.gw] and c.zu == SI[c.zw]),
    (82, "不行傳者考初時", "中传、末传皆空（旬空或落空），只以初传断",
     lambda c: c.void(c.zhong) and c.void(c.mo)),
    (83, "萬事喜忻三六合", "三传成三合局，干上或支上见与中传六合之神",
     lambda c: set(c.trio) in SANHE and LIUHE[c.zhong] in (c.gu, c.zu)),
    (88, "干支乘墓各昏迷", "干上神为干墓，支上神为支墓",
     lambda c: c.gu == MU[c.gw] and c.zu == MU[c.zw]),
    (89, "任信丁馬須言動", "干上或支上见旬丁或支之驿马；伏吟课尤然（注：「非伏吟而乘丁馬者亦主動」）",
     lambda c: c.xun_ding in (c.gu, c.zu) or YIMA[c.zhi] in (c.gu, c.zu)),
    (90, "來去俱空豈動移", "返吟课，往来之神（初传即末传）空（旬空或落空）。注例「己酉返吟三傳卯酉卯……皆空亡」实只卯旬空",
     lambda c: c.method == "返吟" and c.void(c.chu) and c.void(c.mo)),
    (91, "虎臨干鬼㐫速速", "干上神克日干，乘白虎",
     lambda c: ke(c.gu, c.gan) and c.jiang(c.gu) == "白虎"),
]


# 已用注中例子核过的句子（tests/test_liuren_bifa.py）。其余几句注中没有能直接排出整课的例，未经例核
CHECKED = frozenset({1, 2, 5, 6, 7, 8, 15, 16, 21, 22, 23, 24, 25, 26, 27, 29, 30, 31, 32, 33, 36, 40, 51, 52, 55, 59, 61, 62, 63, 64, 70, 75, 76, 77, 78, 79, 80, 82, 83, 88, 89, 90, 91})


def detect(day_gz, tdp, classes, chuan, tj) -> list[dict]:
    c = Ctx(day_gz, tdp, classes, chuan, tj)
    return [{"no": no, "verse": v, "rule": r, "vol": 9 if no <= 50 else 10, "checked": no in CHECKED}
            for no, v, r, fn in RULES if fn(c)]


def detect_ke(ke_: dict) -> list[dict]:
    ch = ke_["three_chuan"]
    chuan = {"method": ch["method"], "chu": ch["chu"]["zhi"], "zhong": ch["zhong"]["zhi"], "mo": ch["mo"]["zhi"]}
    return detect(ke_["day_gan"] + ke_["day_zhi"], ke_["tian_di_pan"], ke_["four_classes"], chuan, ke_["tian_jiang_map"])


def detect_parts(day_gz, yue_jiang, zhan_shi, is_day):
    tdp = build_tian_di_pan(yue_jiang, zhan_shi)
    classes = build_four_classes(day_gz[0], day_gz[1], tdp)
    chuan = get_three_chuan(classes, tdp, day_gz[0], day_gz[1])
    return detect(day_gz, tdp, classes, chuan, build_tian_jiang_map(day_gz[0], is_day, tdp))
