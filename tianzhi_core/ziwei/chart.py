"""紫微斗数排盘：照《紫微斗数全书》卷二「安身命例」诸诀，把生辰排成十二宫命盘。

每一步都注明出自哪一诀（tianzhi-classics ziwei/entries/ziweiquanshu-anxing.json 的 key）。
各家说法不一处做成参数，默认值在参数说明里写明理由：

- ``leap``：闰月怎么算。书：「若闰月正月生者要在二月内起安身命，凡有闰月具要依此为例」→ 默认 ``"next"``（作下月）。
- ``kuiyue_bingding``：丙丁生人的天钺。录文作「丙丁猪狗位」，与诸家及六壬天乙贵人「猪鸡」不合，
  待对明刻本；默认 ``"酉"``，可改 ``"戌"``。
- ``changsheng``：长生十二神的顺逆。书：「男命顺数、女命逆数」→ 默认 ``"book"``；
  通行本多作阳男阴女顺、阴男阳女逆，传 ``"yinyang"``。
- ``daxian_start``：大限起宫。书：「阳男阴女从命前一宫起顺行，是父母宫」，通行读作从命宫起、
  往父母宫顺行 → 默认 ``"ming"``；照字面从父母 / 兄弟宫起，传 ``"next"``。
- ``sihua_ren``：壬年化科。书：「壬梁紫府武」→ 默认 ``"天府"``；中州派等作左辅化科，传 ``"左辅"``。

纯函数：不读系统时间。输入公历时刻与性别，农历换算用 lunar-python。
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from importlib import resources
from typing import Literal

from lunar_python import Solar

ZHI = "子丑寅卯辰巳午未申酉戌亥"
GAN = "甲乙丙丁戊己庚辛壬癸"
Z = {z: i for i, z in enumerate(ZHI)}
SRC = "紫微斗数全书·"

PALACE_NAMES = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄", "迁移", "交友", "官禄", "田宅", "福德", "父母"]
# 书中「妻妾」「奴仆」，今多称夫妻、交友；显示用今称，出处照书
PALACE_BOOK = {"夫妻": "妻妾", "交友": "奴仆"}

MAIN_STARS = ["紫微", "天机", "太阳", "武曲", "天同", "廉贞", "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军"]

# 安南北斗诸星诀：「紫微天机逆行旁，隔一阳武天同当，又隔二位廉贞地，空三复见紫微郎，
# 天府太阴与贪狼，巨门天相及天梁，七杀空三破军位，八星顺数细推详。」
ZIWEI_GROUP = {"紫微": 0, "天机": -1, "太阳": -3, "武曲": -4, "天同": -5, "廉贞": -8}
TIANFU_GROUP = {"天府": 0, "太阴": 1, "贪狼": 2, "巨门": 3, "天相": 4, "天梁": 5, "七杀": 6, "破军": 10}

# 起五行寅例：「甲己之岁起丙寅，乙庚之岁起戊寅，丙辛之岁起庚寅，丁壬之岁起壬寅，戊癸之岁起甲寅。」
YIN_STEM = {"甲": "丙", "己": "丙", "乙": "戊", "庚": "戊", "丙": "庚", "辛": "庚", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}

# 六十花甲子纳音歌 → 五行局（水二、木三、金四、土五、火六）
NAYIN = "".join(c * 2 for c in "金火木土金火水土金木水土火木水金火木土金火水土金木水土火木水")  # 甲子乙丑海中金 … 壬戌癸亥大海水，两干支一纳音
assert len(NAYIN) == 60
JU = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}

# 安禄存星诀；擎羊陀罗随禄存「禄前擎羊后陀罗」
LUCUN = {"甲": "寅", "乙": "卯", "丙": "巳", "戊": "巳", "丁": "午", "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
# 安天马星诀（论本生年支）
TIANMA = {**dict.fromkeys("寅午戌", "申"), **dict.fromkeys("申子辰", "寅"), **dict.fromkeys("巳酉丑", "亥"), **dict.fromkeys("亥卯未", "巳")}
# 安火铃二星诀：「寅午戌人丑卯方，申子辰人寅戌扬，巳酉丑人卯戌位，亥卯未人酉戌房。」起处（火、铃），子时起顺数至生时
HUOLING = {**dict.fromkeys("寅午戌", ("丑", "卯")), **dict.fromkeys("申子辰", ("寅", "戌")),
           **dict.fromkeys("巳酉丑", ("卯", "戌")), **dict.fromkeys("亥卯未", ("酉", "戌"))}
# 安禄权科忌四星变化诀
SIHUA = {"甲": ("廉贞", "破军", "武曲", "太阳"), "乙": ("天机", "天梁", "紫微", "太阴"), "丙": ("天同", "天机", "文昌", "廉贞"),
         "丁": ("太阴", "天同", "天机", "巨门"), "戊": ("贪狼", "太阴", "右弼", "天机"), "己": ("武曲", "贪狼", "天梁", "文曲"),
         "庚": ("太阳", "武曲", "太阴", "天同"), "辛": ("巨门", "太阳", "文曲", "文昌"), "壬": ("天梁", "紫微", "天府", "武曲"),
         "癸": ("破军", "巨门", "太阴", "贪狼")}
HUA = ("禄", "权", "科", "忌")
# 安命主（命宫地支）、安身主（生年地支）
MINGZHU = {"子": "贪狼", "丑": "巨门", "亥": "巨门", "寅": "禄存", "戌": "禄存", "卯": "文曲", "酉": "文曲", "辰": "廉贞", "申": "廉贞",
           "巳": "武曲", "未": "武曲", "午": "破军"}
SHENZHU = {"子": "火星", "午": "火星", "丑": "天相", "未": "天相", "寅": "天梁", "申": "天梁", "卯": "天同", "酉": "天同",
           "辰": "文昌", "戌": "文昌", "巳": "天机", "亥": "天机"}
CHANGSHENG = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
CS_START = {2: "申", 3: "亥", 4: "巳", 5: "申", 6: "寅"}  # 水 木 金 土 火
BOSHI = ["博士", "力士", "青龙", "小耗", "将军", "奏书", "飞廉", "喜神", "病符", "大耗", "伏兵", "官府"]
# 安截路空亡诀：「甲己申酉宫，乙庚午未宫，丙辛辰巳宫，丁壬寅卯宫，戊癸子丑宫」
JIELU = {"甲": "申酉", "己": "申酉", "乙": "午未", "庚": "午未", "丙": "辰巳", "辛": "辰巳", "丁": "寅卯", "壬": "寅卯", "戊": "子丑", "癸": "子丑"}
# 安小限诀：「寅午戌人起辰宫，申子辰人自戌宫，巳酉丑人起未宫，亥卯未人起丑宫」
XIAOXIAN = {**dict.fromkeys("寅午戌", "辰"), **dict.fromkeys("申子辰", "戌"), **dict.fromkeys("巳酉丑", "未"), **dict.fromkeys("亥卯未", "丑")}


@lru_cache(maxsize=1)
def _miaowang() -> dict:
    with resources.files("tianzhi_core.data").joinpath("ziwei_miaowang.json").open(encoding="utf-8") as f:
        return json.load(f)


def at(z: str, n: int) -> str:
    return ZHI[(Z[z] + n) % 12]


def kuiyue(gan: str, bingding: str = "酉") -> tuple[str, str]:
    """安天魁天钺诀：「甲戊庚牛羊，乙己鼠猴乡，六辛逢虎马，壬癸兔蛇藏，丙丁猪狗位」。先魁后钺"""
    t = {"甲": "丑未", "戊": "丑未", "庚": "丑未", "乙": "子申", "己": "子申", "辛": "午寅", "壬": "卯巳", "癸": "卯巳",
         "丙": "亥" + bingding, "丁": "亥" + bingding}[gan]
    return t[0], t[1]


def ziwei_pos(ju: int, day: int) -> str:
    """五行局定紫微：生日除以局数。书中五张宫位图（水二局至火六局）即此法逐日排出，
    与图逐日对过（录文两处错格见 tianzhi-classics ziwei/collation.json）"""
    q = -(-day // ju); r = q * ju - day
    pos = Z["寅"] + q - 1
    return ZHI[(pos - r if r % 2 else pos + r) % 12]


def build_chart(dt: datetime, gender: Literal[0, 1], *, leap: Literal["next", "half", "same"] = "next",
                late_zi: Literal["next", "same"] = "next", kuiyue_bingding: str = "酉",
                changsheng: Literal["book", "yinyang"] = "book", daxian_start: Literal["ming", "next"] = "ming",
                sihua_ren: Literal["天府", "左辅"] = "天府") -> dict:
    """排一张紫微命盘。gender：1 男、0 女。返回十二宫、各宫星曜、四化、五行局、命主身主、大限等，并带出处。"""
    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)
    lunar = solar.getLunar()
    hour_zi = Z[lunar.getTimeZhi()]
    if dt.hour == 23 and late_zi == "next":   # 晚子时：算作次日子时
        lunar = Solar.fromJulianDay(solar.getJulianDay() + 1).getLunar()   # 取次日的农历年月日（时刻只用来定子时）
        hour_zi = 0
    y_gan, y_zhi = lunar.getYearGan(), lunar.getYearZhi()
    month, day = lunar.getMonth(), lunar.getDay()
    if month < 0:   # 闰月
        m = -month
        month = m + 1 if leap == "next" or (leap == "half" and day > 15) else m
        month = 1 if month == 13 else month
    yang = GAN.index(y_gan) % 2 == 0
    forward = (yang and gender == 1) or (not yang and gender == 0)   # 阳男阴女

    # 安身命例：寅上起正月顺至生月；生月宫起子时，逆至生时安命、顺至生时安身
    m_pos = at("寅", month - 1)
    ming = at(m_pos, -hour_zi); shen = at(m_pos, hour_zi)
    # 安十二宫例：男女俱逆转
    palaces = {at(ming, -i): PALACE_NAMES[i] for i in range(12)}
    # 起五行寅例：寅宫干，余宫顺推
    yin_stem = YIN_STEM[y_gan]
    stem = {at("寅", i): GAN[(GAN.index(yin_stem) + i) % 10] for i in range(12)}
    # 命宫干支纳音 → 五行局
    gz = stem[ming] + ming
    idx = next(i for i in range(60) if GAN[i % 10] == gz[0] and ZHI[i % 12] == gz[1])
    ju = JU[NAYIN[idx]]

    stars: dict[str, list[dict]] = {z: [] for z in ZHI}
    def put(name, z, kind, src, **kw):
        stars[z].append({"name": name, "kind": kind, "src": SRC + src, **kw})

    zw = ziwei_pos(ju, day)
    tf = ZHI[(4 - Z[zw]) % 12]    # 天府与紫微以寅申为轴对称
    for n, off in ZIWEI_GROUP.items(): put(n, at(zw, off), "main", "安南北斗诸星诀")
    for n, off in TIANFU_GROUP.items(): put(n, at(tf, off), "main", "安南北斗诸星诀")
    # 六吉
    put("文昌", at("戌", -hour_zi), "good", "安文昌文曲星诀"); put("文曲", at("辰", hour_zi), "good", "安文昌文曲星诀")
    put("左辅", at("辰", month - 1), "good", "安左辅右弼星诀"); put("右弼", at("戌", -(month - 1)), "good", "安左辅右弼星诀")
    k1, k2 = kuiyue(y_gan, kuiyue_bingding); put("天魁", k1, "good", "安天魁天钺诀"); put("天钺", k2, "good", "安天魁天钺诀")
    # 禄存、羊陀、天马
    lc = LUCUN[y_gan]; put("禄存", lc, "lu", "安禄存星诀")
    put("擎羊", at(lc, 1), "bad", "安擎羊陀罗二星诀"); put("陀罗", at(lc, -1), "bad", "安擎羊陀罗二星诀")
    put("天马", TIANMA[y_zhi], "lu", "安天马星诀")
    # 火铃、空劫
    h0, l0 = HUOLING[y_zhi]; put("火星", at(h0, hour_zi), "bad", "安火铃二星诀"); put("铃星", at(l0, hour_zi), "bad", "安火铃二星诀")
    put("地劫", at("亥", hour_zi), "bad", "天空地劫诀"); put("天空", at("亥", -hour_zi), "bad", "天空地劫诀")
    # 杂曜
    put("天刑", at("酉", month - 1), "minor", "安天刑天姚星诀"); put("天姚", at("丑", month - 1), "minor", "安天刑天姚星诀")
    zf, yb = at("辰", month - 1), at("戌", -(month - 1))
    put("三台", at(zf, day - 1), "minor", "安三台八座二星诀"); put("八座", at(yb, -(day - 1)), "minor", "安三台八座二星诀")
    # 截路空亡（论本生年干）、旬中空亡（论本生年所在旬）
    for z in JIELU[y_gan]: put("截路空亡", z, "bad", "安截路空亡诀")
    xun = (Z[y_zhi] - GAN.index(y_gan)) % 12    # 本旬甲所临之支
    for z in (at(ZHI[xun], -2), at(ZHI[xun], -1)): put("旬中空亡", z, "bad", "安旬中空亡诀")
    yz = Z[y_zhi]
    put("天哭", at("午", -yz), "minor", "安天哭天虚星诀"); put("天虚", at("午", yz), "minor", "安天哭天虚星诀")
    put("龙池", at("辰", yz), "minor", "安龙池凤阁诀"); put("凤阁", at("戌", -yz), "minor", "安龙池凤阁诀")
    put("红鸾", at("卯", -yz), "minor", "安红鸾天喜诀"); put("天喜", at(at("卯", -yz), 6), "minor", "安红鸾天喜诀")
    put("台辅", at("午", hour_zi), "minor", "安台辅封诀"); put("封诰", at("寅", hour_zi), "minor", "安封诰诀")
    put("解神", at("戌", -yz), "minor", "安天德月德解神诀")
    put("天伤", at(ming, -7), "minor", "安天伤天使诀"); put("天使", at(ming, -5), "minor", "安天伤天使诀")   # 交友、疾厄
    # 生年四化
    sihua = SIHUA[y_gan] if y_gan != "壬" else SIHUA[y_gan][:2] + (sihua_ren,) + SIHUA[y_gan][3:]
    for i, s in enumerate(sihua):
        for z in ZHI:
            for st in stars[z]:
                if st["name"] == s: st["hua"] = HUA[i]; st["hua_src"] = SRC + "安禄权科忌四星变化诀"
    # 长生十二神（按五行局起长生）
    cs_fwd = (gender == 1) if changsheng == "book" else forward
    changsheng_map = {at(CS_START[ju], i if cs_fwd else -i): CHANGSHENG[i] for i in range(12)}
    # 博士十二神：从禄存起，阳男阴女顺、阴男阳女逆
    boshi = {at(lc, i if forward else -i): BOSHI[i] for i in range(12)}
    # 大限：起岁为局数，每宫十年
    first = ming if daxian_start == "ming" else at(ming, 1 if forward else -1)
    daxian = {at(first, i if forward else -i): (ju + 10 * i, ju + 10 * i + 9) for i in range(12)}
    # 小限：按生年三合起宫，「不论阴阳男俱顺数，不论阴阳女俱逆数」；虚岁一岁起，每年一宫
    xiaoxian = {at(XIAOXIAN[y_zhi], i if gender == 1 else -i): [i + 1 + 12 * k for k in range(10)] for i in range(12)}
    # 庙旺利陷：书中未载的格不填
    mw = _miaowang()
    for z in ZHI:
        for st in stars[z]:
            v = mw["table"].get(st["name"], {}).get(z)
            if v: st["miao"] = v; st["miao_src"] = mw["src"][st["name"]][z]

    return {
        "input": {"solar": dt.strftime("%Y-%m-%d %H:%M"), "gender": gender,
                  "lunar": {"year": f"{y_gan}{y_zhi}", "month": month, "day": day, "leap": lunar.getMonth() < 0, "hour": ZHI[hour_zi]}},
        "params": {"leap": leap, "late_zi": late_zi, "kuiyue_bingding": kuiyue_bingding, "changsheng": changsheng, "daxian_start": daxian_start,
                   "sihua_ren": sihua_ren},
        "ming": ming, "shen": shen, "ju": ju, "ju_name": "水木金土火"[[2, 3, 4, 5, 6].index(ju)] + "二三四五六"[[2, 3, 4, 5, 6].index(ju)] + "局",
        "ming_zhu": MINGZHU[ming], "shen_zhu": SHENZHU[y_zhi], "forward": forward,
        "palaces": [{"zhi": z, "gan": stem[z], "name": palaces[z], "book_name": PALACE_BOOK.get(palaces[z], palaces[z]),
                     "is_shen": z == shen, "stars": stars[z], "changsheng": changsheng_map[z], "boshi": boshi[z], "daxian": daxian[z],
                     "xiaoxian": xiaoxian[z]}
                    for z in ZHI],
        "src": {"ming": SRC + "安身命例", "ju": SRC + "起五行寅例", "ziwei": SRC + "安身命例", "daxian": SRC + "安大限诀", "xiaoxian": SRC + "安小限诀",
                "changsheng": SRC + "安长生十二神", "boshi": SRC + "安十二宫太岁杀禄诀", "miao": SRC + "命宫（庙旺利陷据各星入某宫句读出）",
                "ming_zhu": SRC + "安命主", "shen_zhu": SRC + "安身主"},
    }
