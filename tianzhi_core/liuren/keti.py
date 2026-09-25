"""六壬课体。

一课排出之后，看它属于《六壬大全》课经里的哪些课体。每一条判定都照该课体的定义原文，
出处写在 KETI 表里；课体可以同时成立好几个（一课既是重审，又是全局，又是鬼墓）。

只收判定条件在课式本身之内的课体。要用到占者年命、行年、太岁、月建的（三光、三阳、官爵、
繁昌、侵害、刑伤、盘珠等）暂未收，另待输入齐备。
"""
from __future__ import annotations

from .pan import (ZHI, GAN, GAN_JIGONG, WUXING_GAN, WUXING_ZHI, KE,
                  add_zhi, zhi_idx, build_tian_di_pan, build_four_classes,
                  get_three_chuan, build_tian_jiang_map, get_xun_shou)

MENG, ZHONG = set("寅申巳亥"), set("子午卯酉")
SAN_HE = {"润下": set("申子辰"), "炎上": set("寅午戌"), "曲直": set("亥卯未"), "从革": set("巳酉丑")}
FANG = ["寅卯辰", "巳午未", "申酉戌", "亥子丑"]

# 课体表：名、卷、定义原文（节录）。判定逻辑在下面同名的函数里。
KETI = {
    "元首": (5, "凡一上克下餘課無克為元首課"),
    "重审": (5, "凡一下賊上餘課無克為重審課"),
    "知一": (5, "凡課有二上克下或二下克上擇課之隂陽與今日比者而為用神曰知一課"),
    "涉害": (5, "凡課有二上克下或二下克上與今日俱比俱不比則以渉地盤歸本家受克深處為用為渉害課"),
    "遥克": (5, "凢課無克取日干與四課上神相克者為用曰遥克課"),
    "昴星": (5, "凢四課上下無相克又無遥克取從魁上下神為用曰昴星課"),
    "别责": (5, "凢三課無尅别取一神為用曰别責格"),
    "八专": (5, "凡干支同位無克取陽順隂逆三神為用曰八專課"),
    "伏吟": (5, "凢課月將加時十二神各居本宫取神克日為用曰伏吟"),
    "返吟": (5, "凢課十二神各居冲位取相克為用曰返吟課"),
    "铸印": (6, "凡課得戌加己中傳為鑄印課"),
    "斫轮": (6, "凡課卯加庚或加辛為用曰斵輪課"),
    "轩盖": (6, "凡課的勝光為用遇太冲神后為軒盖課"),
    "引从": (6, "凡課日辰干支前後上神發用為初末傳曰引從課"),
    "闭口": (6, "凡旬尾加旬首或旬首乘玄武或旬首位上神乘玄武發用者為閉口課"),
    "三交": (6, "凡四仲日占四仲加日辰三傳皆仲皆逢陰合為三交課"),
    "淫泆": (6, "凡課初傳卯酉為用將乘后合為淫泆課"),
    "度厄": (7, "凡四課内三上克下或三下賊上為度厄課"),
    "无禄": (7, "凡課四上俱克下為無祿課"),
    "六仪": (5, "凢課的旬首之儀發用或入傳為六儀課"),
    "三奇": (5, "如甲子甲戌旬用丑甲申甲午旬用子甲辰甲寅旬用亥此為旬三竒"),
    "殃咎": (8, "凡三傳逓克日神將克戰或干支乘墓為殃咎課"),
    "鬼墓": (8, "凡日辰墓神及日鬼發用為鬼墓課"),
    "励德": (8, "凡天乙立卯酉為勵徳課"),
    "全局": (8, "凡課得三合俱在者為全局課"),
    "玄胎": (8, "凡孟神發用皆四孟為玄胎課"),
    "连珠": (8, "凡用神在一方相連作中末為連珠課"),
    "亨通": (6, "如丙戌日申時亥將申加丙為用初傳申生中亥亥生末傳寅寅生日干丙火為亨通課"),
    "赘婿": (6, "如日往加辰干克支以上取下男就乎女……若辰來加日干剋支以小依大女就於男"),
    "一旬周遍": (6, "凡旬尾加干旬首加支為一旬周遍格"),
}

# 墓：木墓未、火墓戌、金墓丑、水土墓辰（卷八「戊己辰戌丑未、壬癸亥子見辰」，底本此句有脱讹，按水土同墓读）
MU = {"木": "未", "火": "戌", "金": "丑", "水": "辰", "土": "辰"}
# 旬三奇：甲子甲戌旬丑、甲申甲午旬子、甲辰甲寅旬亥
XUN_QI = {"子": "丑", "戌": "丑", "申": "子", "午": "子", "辰": "亥", "寅": "亥"}


def _wx(x):
    return WUXING_GAN.get(x) or WUXING_ZHI.get(x)


def _ke(a, b):
    """a 克 b"""
    return KE.get(_wx(a)) == _wx(b)


def _yang(x):
    return (GAN.index(x) if x in GAN else ZHI.index(x)) % 2 == 0


def detect(day_gz: str, tdp: dict, classes: list[dict], chuan: dict, tj: dict) -> list[dict]:
    """返回成立的课体：[{name, ge, vol, text}]。tj 为 {天盘支: 天将}。"""
    gan, zhi = day_gz[0], day_gz[1]
    chu, zhong, mo = chuan["chu"], chuan["zhong"], chuan["mo"]
    trio = [chu, zhong, mo]
    below = {sky: earth for earth, sky in tdp.items()}  # 天盘支 → 所临地盘支
    xun = get_xun_shou(day_gz)          # 旬首，如「甲申」
    xun_head = xun[1]                    # 旬首支
    xun_tail = add_zhi(xun_head, 9)      # 旬尾（癸）支
    gan_up, zhi_up = classes[0]["up"], classes[2]["up"]
    hits = []

    def add(name, ge=""):
        vol, text = KETI[name]
        hits.append({"name": name, "ge": ge, "vol": vol, "text": text})

    # —— 九宗门：取传走的哪一门，就是哪一课 ——
    m, ge = chuan["method"], chuan.get("ge", "")
    if m == "贼克":
        add(ge)                          # 元首 / 重审
    elif m == "比用":
        add("知一")
    elif m in ("涉害", "遥克", "昴星", "伏吟", "返吟"):
        add(m, ge if ge != m else "")
    elif m in ("别责", "八专"):
        add(m)

    # —— 上下克的数目：度厄、无禄 ——
    uk = sum(1 for c in classes if _ke(c["up"], c["down"]))
    dz = sum(1 for c in classes if _ke(c["down"], c["up"]))
    if uk == 3 or dz == 3:
        add("度厄", "三上克下" if uk == 3 else "三下贼上")
    if uk == 4:
        add("无禄")

    # —— 看三传 ——
    if trio == ["巳", "戌", "卯"]:
        add("铸印")
    if chu == "卯" and below.get("卯") in (GAN_JIGONG["庚"], GAN_JIGONG["辛"]):
        add("斫轮")
    if chu == "午" and "卯" in trio and "子" in trio:
        add("轩盖")
    for name, s in SAN_HE.items():
        if set(trio) == s:
            add("全局", name)
    for f in FANG:
        if set(trio) == set(f) and len(set(trio)) == 3:
            i = [f.index(x) for x in trio]
            if i in ([0, 1, 2], [2, 1, 0]):
                add("连珠", "进连茹" if i == [0, 1, 2] else "退连茹")
    if all(x in MENG for x in trio):
        add("玄胎")

    # 引从：初末传夹着干上神或支上神，前一辰为初、后一辰为末
    for up, who in ((gan_up, "拱干"), (zhi_up, "拱支")):
        if chu == add_zhi(up, 1) and mo == add_zhi(up, -1):
            add("引从", who)

    # 三交：四仲日，四仲加日辰，三传皆仲，仲神乘太阴或六合
    if zhi in ZHONG and zhi_up in ZHONG and all(x in ZHONG for x in trio) \
            and any(tj.get(x) in ("太阴", "六合") for x in trio):
        add("三交")
    # 淫泆：初传卯酉，乘天后或六合。另两格：初乘天后末乘六合为泆女，初乘六合末乘天后为狡童
    if chu in ("卯", "酉") and tj.get(chu) in ("天后", "六合"):
        add("淫泆")
    if tj.get(chu) == "天后" and tj.get(mo) == "六合":
        add("淫泆", "泆女")
    elif tj.get(chu) == "六合" and tj.get(mo) == "天后":
        add("淫泆", "狡童")

    # 闭口：旬尾加旬首为用；或天盘旬首乘玄武为用；或地盘旬首上神乘玄武为用
    if (chu == xun_tail and below.get(chu) == xun_head) \
            or (chu == xun_head and tj.get(chu) == "玄武") \
            or (chu == tdp.get(xun_head) and tj.get(chu) == "玄武"):
        add("闭口")

    # 一旬周遍：旬首、旬尾分加干支之上
    gan_gong = GAN_JIGONG[gan]
    if {tdp[gan_gong], tdp[zhi]} == {xun_head, xun_tail}:
        add("一旬周遍")
    # 赘婿：干支互加（干寄宫之神加支，或支加干），而干克支
    if (tdp[zhi] == gan_gong or tdp[gan_gong] == zhi) and _ke(gan, zhi):
        add("赘婿", "干加支" if tdp[zhi] == gan_gong else "支加干")
    # 亨通：三传递生，末传生日干
    sheng = lambda a, b: KE.get(_wx(b)) is not None and {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}[_wx(a)] == _wx(b)
    if sheng(chu, zhong) and sheng(zhong, mo) and sheng(mo, gan):
        add("亨通")

    # 六仪：旬首之支发用或入传
    if xun_head in trio:
        add("六仪", "旬仪")
    # 三奇：旬三奇发用或入传
    if XUN_QI[xun_head] in trio:
        add("三奇", "旬奇")

    # 殃咎：三传递克，末克日干（初克中、中克末、末克日），或反向（末克中、中克初、初克日）
    if (_ke(chu, zhong) and _ke(zhong, mo) and _ke(mo, gan)) or \
            (_ke(mo, zhong) and _ke(zhong, chu) and _ke(chu, gan)):
        add("殃咎", "递克")

    # 鬼墓：发用为日鬼（阳见阳、阴见阴克日者），或日干、日支之墓
    gui = _ke(chu, gan) and _yang(chu) == _yang(gan)
    mu = chu in (MU[_wx(gan)], MU[_wx(zhi)])
    if gui or mu:
        add("鬼墓", "日鬼" if gui else "墓神")

    # 励德：天乙贵人所立之地盘为卯或酉
    gui_sky = next((k for k, v in tj.items() if v == "贵人"), None)
    if gui_sky and below.get(gui_sky) in ("卯", "酉"):
        add("励德")
    return hits


def detect_ke(ke: dict) -> list[dict]:
    """qike() 的结果 → 课体"""
    ch = ke["three_chuan"]
    chuan = {"method": ch["method"], "ge": ch.get("ge", ""),
             "chu": ch["chu"]["zhi"], "zhong": ch["zhong"]["zhi"], "mo": ch["mo"]["zhi"]}
    return detect(ke["day_gan"] + ke["day_zhi"], ke["tian_di_pan"], ke["four_classes"], chuan, ke["tian_jiang_map"])


def detect_parts(day_gz: str, yue_jiang: str, zhan_shi: str, is_day: bool) -> list[dict]:
    """只给日干支、月将、占时与昼夜，排出课式再判课体。课例与测试用。"""
    tdp = build_tian_di_pan(yue_jiang, zhan_shi)
    classes = build_four_classes(day_gz[0], day_gz[1], tdp)
    chuan = get_three_chuan(classes, tdp, day_gz[0], day_gz[1])
    return detect(day_gz, tdp, classes, chuan, build_tian_jiang_map(day_gz[0], is_day, tdp))
