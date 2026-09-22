"""四柱排盘：从一个时刻排出年月日时四柱，以及挂在这张盘上的只读派生量。

本模块只做「排」，不做「断」。它回答「这一刻的四柱是什么、月令司令是谁、日干在某支上
处于十二长生的哪一位」，不回答「这个八字好不好」。吉凶、格局、喜忌一律属于上层。

排盘的四条规矩，以及本包在有分歧处的取舍：

1. **年柱以立春为界**，不是元旦，也不是正月初一。生在立春前的，年柱算上一年。
   这一条没有分歧。
2. **月柱换月以节不以气**。过了立春是寅月，过了惊蛰是卯月，中气（雨水、春分）不换月。
   这一条也没有分歧，但错得很常见，所以 `tianzhi_core.calendar.jieqi` 把节与气分开列了。
3. **晚子时（23:00–23:59）日柱算哪天，两派相争**：
   - 流派一「日柱换日」：子时既起，即算次日，所以日柱进一位。
   - 流派二「夜子时」：一天从子正（00:00）起算，23 点后仍是当日，只是时柱记作「夜子时」。
     本包做成 `late_zi` 参数，默认 `"next_day"`（流派一，与主流排盘软件一致），
     `"same_day"` 走流派二。**不替使用者选边**，因为这确实是未决的分歧，
     而两派排出的日柱、时干都不同，影响整张盘。
     注意：时干一律由本盘的日干按五鼠遁推出，保持自洽——
     选了 `"same_day"` 就连时干也用当日日干遁，不会出现「日柱当日、时干次日」的混搭。
4. **真太阳时**：见 `tianzhi_core.calendar.solar_time` 的流派说明，由 `use_true_solar` 控制。

一切干支属性（五行、阴阳、藏干、长生、司令）都从 `tianzhi_core.core.ganzhi` 取，本模块不存表。
唯一的例外是纳音：那是六十组固定词条（海中金、炉中火……），`core.ganzhi` 里没有，
直接借用已经是依赖的 `lunar_python` 的表，不再抄一份。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

from lunar_python.util import LunarUtil

from ..calendar import jieqi
from ..calendar.solar_time import correction_minutes, true_solar_time
from ..core import ganzhi as gz
from ..core import wuxing
from .shishen import ten_god

__all__ = ["Pillar", "Chart", "LateZi", "PillarRef", "build_chart", "nayin"]

LateZi = Literal["next_day", "same_day"]
PillarRef = Literal["year", "month", "day", "hour"]

#: 四柱的固定次序
PILLAR_NAMES: tuple[str, ...] = ("year", "month", "day", "hour")

#: 1984 是甲子年，六十甲子的起点。年柱序号由此推。
_JIAZI_YEAR_EPOCH: int = 1984
#: 1949-10-01 是甲子日。日柱序号 = (儒略日数 + 49) % 60，由此标定。
_JIAZI_DAY_OFFSET: int = 49
#: 命宫、身宫用的月支序列，从寅起，1 基。
_GONG_ZHI: tuple[str, ...] = ("", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑")


def nayin(ganzhi: str) -> str:
    """六十甲子纳音。两干支共一纳音，如甲子乙丑海中金。"""
    return LunarUtil.NAYIN.get(ganzhi, "")


def _jdn(d: date) -> int:
    """公历日期的儒略日数（取当日 12:00 那一刻的整数儒略日）。

    用标准的 Fliegel–Van Flandern 整数公式，不经过 datetime 的任何时区逻辑，
    所以日柱推算完全确定、可跨平台复现。
    """
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return (d.day + (153 * m + 2) // 5 + 365 * y
            + y // 4 - y // 100 + y // 400 - 32045)


@dataclass(frozen=True)
class Pillar:
    """一柱：一个天干加一个地支。"""

    gan: str
    zhi: str

    @property
    def ganzhi(self) -> str:
        """两个字连写，如「壬辰」。"""
        return self.gan + self.zhi

    @property
    def gan_wuxing(self) -> str:
        return gz.GAN_WUXING[self.gan]

    @property
    def zhi_wuxing(self) -> str:
        return gz.ZHI_WUXING[self.zhi]

    @property
    def index(self) -> int:
        """在六十甲子中的序号，0 为甲子。"""
        return gz.jiazi_index(self.ganzhi)

    def __str__(self) -> str:
        return self.ganzhi

    @classmethod
    def from_index(cls, index: int) -> "Pillar":
        """由六十甲子序号造一柱，序号自动取模，支持负数（逆行大运用得上）。"""
        s = gz.JIAZI[index % 60]
        return cls(s[0], s[1])

    @classmethod
    def from_ganzhi(cls, ganzhi: str) -> "Pillar":
        if len(ganzhi) != 2 or ganzhi[0] not in gz.GAN or ganzhi[1] not in gz.ZHI:
            raise ValueError(f"不是干支：{ganzhi!r}")
        return cls(ganzhi[0], ganzhi[1])


@dataclass(frozen=True)
class Chart:
    """一张排好的八字盘。构造后不可变，所有派生量都是只读属性，按需计算。"""

    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar
    #: 用于定柱的时刻。开了真太阳时就是修正后的，否则等于 clock。
    solar: datetime
    #: 0 男 1 女。只影响大运顺逆，不影响四柱。
    gender: int
    #: 调用方传进来的原始钟表时刻
    clock: datetime
    #: 出生地经度，0 表示未提供
    longitude: float = 0.0
    #: 真太阳时修正量，单位分钟；未修正为 0
    solar_correction: float = 0.0
    #: 晚子时取的流派
    late_zi: LateZi = "next_day"

    # ── 四柱 ────────────────────────────────────────────────
    @property
    def pillars(self) -> tuple[Pillar, Pillar, Pillar, Pillar]:
        """四柱，按年月日时的次序。"""
        return (self.year, self.month, self.day, self.hour)

    @property
    def named_pillars(self) -> dict[str, Pillar]:
        return dict(zip(PILLAR_NAMES, self.pillars))

    @property
    def quad(self) -> dict[str, tuple[str, str]]:
        """四柱的最简形式：{"year": ("丙", "子"), ...}。

        量化、取用、引动、合盘这几层都收这个结构，所以排完盘直接 `chart.quad`
        就能往下传，不必自己拆一遍。
        """
        return {name: (p.gan, p.zhi) for name, p in zip(PILLAR_NAMES, self.pillars)}

    @property
    def bazi(self) -> str:
        """四柱连写，如「丙子 壬辰 乙酉 癸未」。这是唯一的字符串便利输出。"""
        return " ".join(p.ganzhi for p in self.pillars)

    def _pillar(self, ref: "PillarRef | Pillar") -> Pillar:
        """柱名或柱本身都收，统一成 Pillar。"""
        if isinstance(ref, Pillar):
            return ref
        try:
            return self.named_pillars[ref]
        except KeyError:
            raise ValueError(f"不是柱名：{ref!r}，应为 {PILLAR_NAMES} 之一") from None

    # ── 日主 ────────────────────────────────────────────────
    @property
    def day_master(self) -> str:
        """日干，即「我」。全盘的十神、强弱、喜忌都以它为基准。"""
        return self.day.gan

    @property
    def day_element(self) -> str:
        """日干的五行。"""
        return gz.GAN_WUXING[self.day_master]

    @property
    def day_yang(self) -> bool:
        """日主是阳干为真。"""
        return self.day_master in gz.GAN_YANG

    # ── 柱上的派生量 ─────────────────────────────────────────
    def ten_god_of(self, ref: "PillarRef | Pillar") -> str:
        """该柱天干对日主的十神。日柱返回「比肩」（日干对自己同五行同阴阳）；
        要显示成「日主」是展示层的事，这里不做特例。"""
        return ten_god(self._pillar(ref).gan, self.day_master)

    def hidden(self, ref: "PillarRef | Pillar") -> list[dict[str, str]]:
        """该柱地支的藏干，按本气、中气、余气排列。

        每项含 gan（藏干）、level（本/中/余）、wuxing、shishen（对日主的十神）。
        藏干表取自 core.ganzhi.HIDDEN，本模块不自己列。
        """
        zhi = self._pillar(ref).zhi
        return [
            {
                "gan": g,
                "level": level,
                "wuxing": gz.GAN_WUXING[g],
                "shishen": ten_god(g, self.day_master),
            }
            for g, level in gz.HIDDEN[zhi]
        ]

    def nayin(self, ref: "PillarRef | Pillar") -> str:
        """该柱的纳音。"""
        return nayin(self._pillar(ref).ganzhi)

    def dishi(self, ref: "PillarRef | Pillar") -> str:
        """日干坐在该柱地支上的十二长生（地势）。阳干顺行、阴干逆行，见 core.ganzhi.dishi。"""
        return gz.dishi(self.day_master, self._pillar(ref).zhi)

    def zizuo(self, ref: "PillarRef | Pillar") -> str:
        """该柱天干坐自己地支的十二长生（自坐），衡量这个干本身有没有根气。"""
        p = self._pillar(ref)
        return gz.dishi(p.gan, p.zhi)

    # ── 月令 ────────────────────────────────────────────────
    @property
    def month_jieqi(self) -> tuple[str, datetime]:
        """本盘所在的节令名与交节时刻。"""
        return jieqi.month_jieqi(self.solar)

    @property
    def days_after_jieqi(self) -> float:
        """出生距上一个节过了多少天，带小数。定司令用。"""
        return jieqi.days_after_jieqi(self.solar)

    @property
    def siling(self) -> str:
        """月令人元司令的那个藏干。

        同一个月支，生在节后第几天决定当令的是本气还是中余气——辰月头九天乙木司令，
        接着三天癸水，之后十八天才轮到戊土。比「一律按本气」贴近古法。
        """
        return gz.siling_gan(self.month.zhi, self.days_after_jieqi)

    @property
    def siling_shishen(self) -> str:
        """司令藏干对日主的十神。"""
        return ten_god(self.siling, self.day_master)

    @property
    def month_wangxiang(self) -> str:
        """日主五行生在本月令，处于旺相休囚死的哪一档。"""
        return gz.wangxiang(self.day_element, self.month.zhi)

    # ── 三宫 ────────────────────────────────────────────────
    @property
    def taiyuan(self) -> Pillar:
        """胎元：月干进一位，月支进三位。受胎之月的干支，各家算法一致。"""
        gi = (gz.GAN.index(self.month.gan) + 1) % 10
        zi = (gz.ZHI.index(self.month.zhi) + 3) % 12
        return Pillar(gz.GAN[gi], gz.ZHI[zi])

    @property
    def minggong(self) -> Pillar:
        """命宫。

        取法：月支与时支都按「寅为一」编号相加，和数与十四相减（超过十四则减自二十六），
        得命宫地支的编号；宫干再由年干按五虎遁推。
        **流派提示**：命宫另有「以中气为界」「卯时安命」等算法，结果可差一位。
        本包取的是流通最广、与 lunar 系库一致的这一种，便于与现有排盘结果对照。
        """
        m = _GONG_ZHI.index(self.month.zhi)
        t = _GONG_ZHI.index(self.hour.zhi)
        offset = m + t
        offset = 26 - offset if offset >= 14 else 14 - offset
        return Pillar(self._gong_gan(offset), _GONG_ZHI[offset])

    @property
    def shengong(self) -> Pillar:
        """身宫。

        取法：月支按「寅为一」编号，时支按「子为一」编号，两数相加，超过十二则减十二。
        月支与时支的编号基准不同，这不是笔误，是这一派的定法。
        """
        m = _GONG_ZHI.index(self.month.zhi)
        t = gz.ZHI.index(self.hour.zhi) + 1
        offset = m + t
        if offset > 12:
            offset -= 12
        return Pillar(self._gong_gan(offset), _GONG_ZHI[offset])

    def _gong_gan(self, offset: int) -> str:
        """宫干：由年干起五虎遁数到该宫的位置。offset 是 1 基的寅起编号。"""
        i = (gz.GAN.index(self.year.gan) + 1) * 2 + offset
        while i > 10:
            i -= 10
        return gz.GAN[i - 1]

    # ── 整盘 ────────────────────────────────────────────────
    @property
    def wuxing_counts(self) -> dict[str, int]:
        """四柱八个字的五行个数。只数明干明支，不算藏干——
        带权重的量化属于评分层，那里要考虑藏干、司令、得地得势，口径复杂得多。
        """
        counts = {w: 0 for w in wuxing.ORDER}
        for p in self.pillars:
            counts[gz.GAN_WUXING[p.gan]] += 1
            counts[gz.ZHI_WUXING[p.zhi]] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        """整张盘的结构化快照。纯数据，无叙述文字。"""
        return {
            "bazi": self.bazi,
            "gender": self.gender,
            "clock": self.clock.isoformat(),
            "solar": self.solar.isoformat(),
            "longitude": self.longitude,
            "solar_correction": self.solar_correction,
            "late_zi": self.late_zi,
            "day_master": self.day_master,
            "day_element": self.day_element,
            "month_jieqi": {
                "name": self.month_jieqi[0],
                "at": self.month_jieqi[1].isoformat(),
                "days_after": self.days_after_jieqi,
            },
            "siling": {"gan": self.siling, "shishen": self.siling_shishen},
            "pillars": {
                name: {
                    "ganzhi": p.ganzhi,
                    "gan": p.gan,
                    "zhi": p.zhi,
                    "gan_wuxing": p.gan_wuxing,
                    "zhi_wuxing": p.zhi_wuxing,
                    "shishen": self.ten_god_of(p),
                    "hidden": self.hidden(p),
                    "nayin": self.nayin(p),
                    "dishi": self.dishi(p),
                    "zizuo": self.zizuo(p),
                }
                for name, p in self.named_pillars.items()
            },
            "minggong": self.minggong.ganzhi,
            "shengong": self.shengong.ganzhi,
            "taiyuan": self.taiyuan.ganzhi,
            "wuxing_counts": self.wuxing_counts,
        }


# ── 四柱的推算 ────────────────────────────────────────────────
def _year_pillar(dt: datetime) -> Pillar:
    """年柱。以立春交节的那一刻换年，不是元旦。"""
    y = dt.year if dt >= jieqi.lichun(dt.year) else dt.year - 1
    return Pillar.from_index(y - _JIAZI_YEAR_EPOCH)


def _month_pillar(dt: datetime, year_gan: str) -> Pillar:
    """月柱。支由节定，干由年干按五虎遁定。

    五虎遁：甲己之年丙作首，乙庚之年戊为头，丙辛之年寻庚上，丁壬壬寅顺水流，
    戊癸之年甲寅求。写成式子就是寅月干序号 = 年干序号 × 2 + 2（模十）。
    """
    zhi = jieqi.month_zhi(dt)
    offset = (gz.ZHI.index(zhi) - gz.ZHI.index("寅")) % 12
    gi = (gz.GAN.index(year_gan) * 2 + 2 + offset) % 10
    return Pillar(gz.GAN[gi], zhi)


def _day_pillar(dt: datetime, late_zi: LateZi) -> Pillar:
    """日柱。由儒略日数直接换算，与农历、节气都无关。

    晚子时（23:00–23:59）按 late_zi 决定算不算次日，见模块文档第三条。
    """
    d = dt.date()
    if late_zi == "next_day" and dt.hour == 23:
        d = d + timedelta(days=1)
    elif late_zi not in ("next_day", "same_day"):
        raise ValueError(f"late_zi 只能是 'next_day' 或 'same_day'，收到 {late_zi!r}")
    return Pillar.from_index(_jdn(d) + _JIAZI_DAY_OFFSET)


def _hour_pillar(dt: datetime, day_gan: str) -> Pillar:
    """时柱。支由钟点定（子时跨 23:00–00:59），干由日干按五鼠遁定。

    五鼠遁：甲己还加甲，乙庚丙作初，丙辛从戊起，丁壬庚子居，戊癸何方发，壬子是真途。
    写成式子就是子时干序号 = 日干序号 mod 5 × 2。
    这里的 day_gan 取本盘已定好的日干，所以 late_zi 的选择会一路贯穿到时干。
    """
    zi = ((dt.hour + 1) // 2) % 12
    gi = (gz.GAN.index(day_gan) % 5 * 2 + zi) % 10
    return Pillar(gz.GAN[gi], gz.ZHI[zi])


def build_chart(
    dt: datetime,
    *,
    longitude: float = 0.0,
    gender: int = 0,
    use_true_solar: bool = True,
    late_zi: LateZi = "next_day",
) -> Chart:
    """从一个出生时刻排出四柱。

    :param dt: 出生的钟表时刻。naive 的按东八区法定时理解；带 tzinfo 的先折算到东八区。
        本函数不读系统时间、不读系统时区，「现在」必须由调用方传进来。
    :param longitude: 出生地经度，东经为正。**传 0（默认）视为没提供出生地，
        不做真太阳时修正**——这与参考实现一致，也避免了「没填经度却被按本初子午线
        平移八小时」这种静默的错误。真要按经度 0 排，请自己先调 `true_solar_time`。
    :param gender: 0 男 1 女。不影响四柱，只在起大运时决定顺逆。
    :param use_true_solar: 是否做真太阳时修正，见 `tianzhi_core.calendar.solar_time`。
    :param late_zi: 晚子时的流派，见模块文档第三条。

    >>> build_chart(datetime(1996, 4, 18, 13, 46), longitude=114.93).bazi
    '丙子 壬辰 乙酉 癸未'
    """
    if gender not in (0, 1):
        raise ValueError(f"gender 只能是 0（男）或 1（女），收到 {gender!r}")
    if late_zi not in ("next_day", "same_day"):
        raise ValueError(f"late_zi 只能是 'next_day' 或 'same_day'，收到 {late_zi!r}")

    clock = jieqi.as_naive(dt)
    correction = 0.0
    solar = clock
    if use_true_solar and longitude != 0.0:
        correction = correction_minutes(clock, longitude)
        solar = true_solar_time(clock, longitude)

    year = _year_pillar(solar)
    month = _month_pillar(solar, year.gan)
    day = _day_pillar(solar, late_zi)
    hour = _hour_pillar(solar, day.gan)
    return Chart(
        year=year, month=month, day=day, hour=hour,
        solar=solar, gender=gender, clock=clock,
        longitude=longitude, solar_correction=correction, late_zi=late_zi,
    )
