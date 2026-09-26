"""紫微运限：大限、小限、流年、流月、流日、流时。

给一张本命盘（chart.build_chart 的结果）和一个时刻，推出那一刻各层运限落在哪一宫、各层的宫名、四化与流曜。

- 大限：按虚岁取本命盘上涵盖此岁的那一宫（《全书》安大限诀）；未交第一步大限时走童限
  （安童限诀：「一命二财三疾厄，四妻五福六官禄」）。
- 小限：本命盘上此岁所在的那一宫（安小限诀）。
- 流年：流年太岁的地支所在宫。
- 流月：先安斗君（安斗君诀：「于流年太岁宫起正月逆至本生月，又从本生月起子顺数至本生时安斗君」），
  斗君所在为正月，顺数到当月。
- 流日：流月宫起初一，顺数到当日；流时：流日宫起子时，顺数到当时。

各层四化：大限、小限取该宫宫干；流年、流月、流日、流时取当时的年、月、日、时干（年以正月初一为界，
月按农历月以五虎遁起干，与流年同一口径）。流曜：禄存羊陀依《全书》安流禄流羊流陀诀，随各层天干；昌曲魁钺马鸾喜为通行排法。
流年另有天德、月德（《全书》安天德月德解神诀，随流年太岁）与岁前十二神。
"""
from __future__ import annotations

from datetime import datetime

from lunar_python import Solar

from .chart import (GAN, HUA, LUCUN, SIHUA, SRC, SUIQIAN, TIANMA, TX, YIN_STEM, ZHI, Z, at, kuiyue)

NAMES = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄", "迁移", "交友", "官禄", "田宅", "福德", "父母"]
TONG = ["命宫", "财帛", "疾厄", "夫妻", "福德", "官禄"]   # 童限一至六岁
# 通行排法：流昌、流曲随天干
CHANGQU = {"甲": "巳酉", "乙": "午申", "丙": "申午", "戊": "申午", "丁": "酉巳", "己": "酉巳", "庚": "亥卯", "辛": "子寅", "壬": "寅子", "癸": "卯亥"}
PREFIX = {"daxian": "运", "liunian": "流", "liuyue": "月", "liuri": "日", "liushi": "时"}
LABEL = {"daxian": "大限", "xiaoxian": "小限", "liunian": "流年", "liuyue": "流月", "liuri": "流日", "liushi": "流时"}


def _sihua(gan: str, ren: str) -> dict:
    sh = SIHUA[gan] if gan != "壬" else SIHUA["壬"][:2] + (ren,) + SIHUA["壬"][3:]
    return {n: HUA[i] for i, n in enumerate(sh)}


def _liuyao(key: str, gan: str, zhi: str, bingding: str) -> dict:
    """一层运限的流曜：{地支: [星名]}"""
    pre, out = PREFIX[key], {z: [] for z in ZHI}
    lu = LUCUN[gan]
    out[lu].append(pre + "禄"); out[at(lu, 1)].append(pre + "羊"); out[at(lu, -1)].append(pre + "陀")
    k1, k2 = kuiyue(gan, bingding); out[k1].append(pre + "魁"); out[k2].append(pre + "钺")
    c, q = CHANGQU[gan]; out[c].append(pre + "昌"); out[q].append(pre + "曲")
    out[TIANMA[zhi]].append(pre + "马")
    luan = at("卯", -Z[zhi]); out[luan].append(pre + "鸾"); out[at(luan, 6)].append(pre + "喜")
    return out


def _layer(key, ming_zhi, gan, zhi, chart, extra=None):
    p = chart["params"]
    lay = {"key": key, "label": LABEL[key], "ming": ming_zhi, "gan": gan, "zhi": zhi,
           "palace_names": {at(ming_zhi, -i): NAMES[i] for i in range(12)},
           "sihua": _sihua(gan, p.get("sihua_ren", "天府"))}
    pos = {s["name"]: q["zhi"] for q in chart["palaces"] for s in q["stars"]}
    lay["sihua_at"] = {n: pos.get(n) for n in lay["sihua"]}
    if key in PREFIX:
        lay["stars"] = _liuyao(key, gan, zhi, p.get("kuiyue_bingding", "酉"))
    if extra:
        lay.update(extra)
    return lay


def horoscope(chart: dict, when: datetime, *, late_zi: str = "next", leap: str | None = None) -> dict:
    """本命盘在 when 这一刻的各层运限。late_zi / leap 与排盘同义，缺省取本命盘的参数"""
    leap = leap or chart["params"].get("leap", "next")
    solar = Solar.fromYmdHms(when.year, when.month, when.day, when.hour, when.minute, 0)
    lunar = solar.getLunar()
    hz = Z[lunar.getTimeZhi()]
    if when.hour == 23 and late_zi == "next":
        lunar = Solar.fromJulianDay(solar.getJulianDay() + 1).getLunar(); hz = 0
    b = chart["input"]["lunar"]
    age = lunar.getYear() - b["y"] + 1   # 虚岁
    by = {q["zhi"]: q for q in chart["palaces"]}
    layers = []
    # 大限 / 童限
    dx = next((q for q in chart["palaces"] if q["daxian"][0] <= age <= q["daxian"][1]), None)
    if dx is None and 1 <= age <= len(TONG):
        dx = next(q for q in chart["palaces"] if q["name"] == TONG[age - 1])
        layers.append(_layer("daxian", dx["zhi"], dx["gan"], dx["zhi"], chart, {"childhood": True, "src": SRC + "安童限诀"}))
    elif dx:
        layers.append(_layer("daxian", dx["zhi"], dx["gan"], dx["zhi"], chart, {"range": list(dx["daxian"]), "src": SRC + "安大限诀"}))
    # 小限
    xx = next((q for q in chart["palaces"] if age in q["xiaoxian"]), None)
    if xx:
        layers.append(_layer("xiaoxian", xx["zhi"], xx["gan"], xx["zhi"], chart, {"src": SRC + "安小限诀"}))
    # 流年
    yg, yzh = lunar.getYearGan(), lunar.getYearZhi()
    tai = yzh
    layers.append(_layer("liunian", tai, yg, yzh, chart, {
        "src": SRC + "安流禄流羊流陀诀",
        "suiqian": {at(tai, i): SUIQIAN[i] for i in range(12)},
        "tiande": at("酉", Z[yzh]), "yuede": at("子", Z[yzh]),   # 安天德月德解神诀：酉上、子上起子，顺数至流年太岁
    }))
    # 流月：斗君为正月
    m = lunar.getMonth()
    if m < 0:
        m = -m
        m = m + 1 if leap == "next" or (leap == "half" and lunar.getDay() > 15) else m
        m = 1 if m == 13 else m
    doujun = at(at(tai, -(b["month"] - 1)), Z[b["hour"]])
    yue = at(doujun, m - 1)
    # 月干支与流年同一口径：按农历月，五虎遁（流年干定正月之干），不按节气换月
    mg = GAN[(GAN.index(YIN_STEM[yg]) + m - 1) % 10]
    layers.append(_layer("liuyue", yue, mg, at("寅", m - 1), chart, {"doujun": doujun, "src": SRC + "安斗君诀"}))
    ri = at(yue, lunar.getDay() - 1)
    layers.append(_layer("liuri", ri, lunar.getDayGan(), lunar.getDayZhi(), chart))
    shi = at(ri, hz)
    layers.append(_layer("liushi", shi, lunar.getTimeGan() if not (when.hour == 23 and late_zi == "next") else _zi_gan(lunar.getDayGan()), ZHI[hz], chart))
    return {"when": when.strftime("%Y-%m-%d %H:%M"), "lunar": f"{lunar.getYearInGanZhi()}年{'闰' if lunar.getMonth() < 0 else ''}{abs(lunar.getMonth())}月{lunar.getDay()}日{ZHI[hz]}时",
            "age": age, "layers": layers, "tongxing_src": TX + "流曜"}


def _zi_gan(day_gan: str) -> str:
    """次日子时的时干（五鼠遁：甲己还加甲）"""
    return GAN[(GAN.index(day_gan) % 5) * 2]


def daxian_list(chart: dict) -> list:
    """十二步大限，按起岁排序，带宫干支与起止虚岁、起止公历年"""
    y0 = chart["input"]["lunar"]["y"]
    out = [{"zhi": q["zhi"], "gan": q["gan"], "name": q["name"], "range": list(q["daxian"]),
            "years": [y0 + q["daxian"][0] - 1, y0 + q["daxian"][1] - 1]} for q in chart["palaces"]]
    return sorted(out, key=lambda x: x["range"][0])
