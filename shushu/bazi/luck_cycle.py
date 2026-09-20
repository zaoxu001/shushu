"""大运、流年、流月：只排，不断。

这一层回答「第几步大运是什么干支、从哪一年到哪一年」，不回答「这步运好不好」。
吉凶要看这步运与原局的生克合冲、与喜忌的向背，那需要整张盘的上下文，属于上层。

三条规矩：

1. **顺逆看年干阴阳与性别**：阳年生男、阴年生女顺行（大运干支在月柱之后依次排），
   阴年生男、阳年生女逆行。注意看的是**年干**的阴阳，不是年支，也不是日干。
2. **三日折一年**：从出生数到交节（顺行数到下一个节，逆行数回上一个节），
   每三天折一岁。细到三天以下怎么折，两派：
   - `sect=1`（默认，与主流排盘软件及本包参考实现一致）：一天折四个月、一个时辰折十天，
     天数按整日计、时辰按时辰序号计。
   - `sect=2`：按分钟数线性折算，1440 分钟折 4 个月。
     两者差别通常在几天以内，只有卡在边界上才会把起运岁数差出一岁。
3. **流月按节气分，不按农历月**：寅月从立春起，卯月从惊蛰起，与月柱同一套规矩。

**关于起运前那段**：本模块的 `dayun_list` 只给真正的大运，第一步 index 为 1。
起运之前的童年不属于任何一步大运（有的排法记作「童限」或用小运补），
本包不替使用者把它编成 index 0 的空运，需要的话自行按 `start_age` 区间处理。
"""
from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from ..calendar import jieqi
from ..core import ganzhi as gz
from .chart import Chart, Pillar

__all__ = [
    "DaYun", "LiuNian", "LiuYue",
    "is_forward", "start_age", "dayun_list", "liunian", "liuyue",
]

Sect = Literal[1, 2]

#: 一「折算年」含十二折算月，一折算月含三十折算日。把起运的年月日折成小数时用这个尺度。
_MONTHS_PER_YEAR = 12
_DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class DaYun:
    """一步大运。十年一步。"""

    index: int          #: 第几步，从 1 起
    pillar: Pillar
    start_age: int      #: 虚岁，交运那一年记作这个岁数
    end_age: int
    start_year: int     #: 公历年
    end_year: int
    forward: bool       #: 该盘大运是否顺行

    @property
    def ganzhi(self) -> str:
        return self.pillar.ganzhi

    @property
    def gan(self) -> str:
        return self.pillar.gan

    @property
    def zhi(self) -> str:
        return self.pillar.zhi

    def to_dict(self) -> dict:
        return {
            "index": self.index, "ganzhi": self.ganzhi,
            "gan": self.gan, "zhi": self.zhi,
            "start_age": self.start_age, "end_age": self.end_age,
            "start_year": self.start_year, "end_year": self.end_year,
            "forward": self.forward,
        }


@dataclass(frozen=True)
class LiuNian:
    """一个流年。"""

    year: int
    age: int            #: 虚岁
    pillar: Pillar

    @property
    def ganzhi(self) -> str:
        return self.pillar.ganzhi

    @property
    def gan(self) -> str:
        return self.pillar.gan

    @property
    def zhi(self) -> str:
        return self.pillar.zhi

    def to_dict(self) -> dict:
        return {"year": self.year, "age": self.age, "ganzhi": self.ganzhi,
                "gan": self.gan, "zhi": self.zhi}


@dataclass(frozen=True)
class LiuYue:
    """一个流月。以节为界，不是农历月，也不是公历月。"""

    index: int          #: 0 为寅月（立春起），11 为丑月（小寒起）
    pillar: Pillar
    jieqi: str          #: 开启这个月的节名
    start: datetime     #: 交节时刻
    end: datetime       #: 下一个节的交节时刻

    @property
    def ganzhi(self) -> str:
        return self.pillar.ganzhi

    @property
    def gan(self) -> str:
        return self.pillar.gan

    @property
    def zhi(self) -> str:
        return self.pillar.zhi

    def to_dict(self) -> dict:
        return {"index": self.index, "ganzhi": self.ganzhi,
                "gan": self.gan, "zhi": self.zhi, "jieqi": self.jieqi,
                "start": self.start.isoformat(), "end": self.end.isoformat()}


def is_forward(chart: Chart) -> bool:
    """大运是否顺行。阳年男、阴年女顺行；阴年男、阳年女逆行。"""
    yang_year = chart.year.gan in gz.GAN_YANG
    male = chart.gender == 0
    return yang_year == male


def _shichen_index(dt: datetime) -> int:
    """时辰序号，子 0 到亥 11。

    23 点单独记作 11 而不是 0：这里数的是「当日过了几个时辰」，
    晚子时排在一天的末尾，若记作 0 会把日差算少一天。
    """
    return 11 if dt.hour == 23 else ((dt.hour + 1) // 2) % 12


def _add_calendar(dt: datetime, years: int, months: int, days: int, hours: int) -> datetime:
    """按年、月、日、时依次加到 dt 上。加月时日期溢出就压到当月最后一天。"""
    y = dt.year + years
    m = dt.month + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    d = min(dt.day, _calendar.monthrange(y, m)[1])
    return dt.replace(year=y, month=m, day=d) + timedelta(days=days, hours=hours)


def start_age(chart: Chart, *, sect: Sect = 1) -> tuple[float, datetime]:
    """起运岁数与交运时刻。

    返回 (岁数, 交运时刻)。岁数是小数：整数部分是折算出的年，
    小数部分按「一年十二折算月、一月三十折算日」摊开，方便排序与比较；
    要显示成「几年几个月」请用交运时刻减出生时刻，不要拿小数去乘。

    :param sect: 三天以下怎么折，见模块文档第二条。默认 1，与主流排盘软件一致。
    """
    birth = chart.solar
    if is_forward(chart):
        edge = jieqi.next_jie(birth)[1]
        start, end = birth, edge
    else:
        edge = chart.month_jieqi[1]
        start, end = edge, birth

    if sect == 2:
        # 按分钟线性折算：3 天 = 4320 分钟 = 1 年，1 天 = 1440 分钟 = 4 个月。
        minutes = int((end - start).total_seconds() // 60)
        years, minutes = divmod(minutes, 4320)
        months, minutes = divmod(minutes, 360)
        days, minutes = divmod(minutes, 12)
        hours = minutes * 2
    elif sect == 1:
        # 按整日数加时辰数折算，古法口径：三日一年、一日四月、一时辰十日。
        day_diff = (end.date() - start.date()).days
        hour_diff = _shichen_index(end) - _shichen_index(start)
        if hour_diff < 0:
            hour_diff += 12
            day_diff -= 1
        month_diff = hour_diff * 10 // 30
        total_months = day_diff * 4 + month_diff
        days = hour_diff * 10 - month_diff * 30
        years, months = divmod(total_months, 12)
        hours = 0
    else:
        raise ValueError(f"sect 只能是 1 或 2，收到 {sect!r}")

    age = (years
           + months / _MONTHS_PER_YEAR
           + days / (_MONTHS_PER_YEAR * _DAYS_PER_MONTH)
           + hours / (_MONTHS_PER_YEAR * _DAYS_PER_MONTH * 24))
    return age, _add_calendar(birth, years, months, days, hours)


def dayun_list(chart: Chart, count: int = 10, *, sect: Sect = 1) -> list[DaYun]:
    """排大运。第一步从月柱起算，顺行加一位、逆行减一位，此后每十年一步。

    岁数用虚岁：交运那个公历年记作 `交运年 - 出生年 + 1` 岁，与流年的虚岁同一口径。
    """
    if count < 0:
        raise ValueError("count 不能为负")
    _, enter = start_age(chart, sect=sect)
    forward = is_forward(chart)
    birth_year = chart.solar.year
    base = chart.month.index
    step = 1 if forward else -1

    out: list[DaYun] = []
    for i in range(1, count + 1):
        sy = enter.year + (i - 1) * 10
        sa = sy - birth_year + 1
        out.append(DaYun(
            index=i,
            pillar=Pillar.from_index(base + step * i),
            start_age=sa, end_age=sa + 9,
            start_year=sy, end_year=sy + 9,
            forward=forward,
        ))
    return out


def year_pillar(year: int) -> Pillar:
    """某个公历年（立春之后那一段）的年柱。1984 为甲子年。"""
    return Pillar.from_index(year - 1984)


def liunian(chart: Chart, start_year: int, end_year: int) -> list[LiuNian]:
    """逐年的流年干支与虚岁，含首尾两年。

    年干支按立春分界，所以这里的「年」指该公历年立春之后的那一段；
    要算某年一月的事，请用 `liuyue` 落到具体月令，别直接拿年柱。
    """
    if end_year < start_year:
        raise ValueError("end_year 不能小于 start_year")
    birth_year = chart.solar.year
    return [
        LiuNian(year=y, age=y - birth_year + 1, pillar=year_pillar(y))
        for y in range(start_year, end_year + 1)
    ]


def liuyue(chart: Chart, year: int) -> list[LiuYue]:
    """某个公历年的十二个流月。

    从该年立春（寅月）起，到次年小寒（丑月）止，共十二段，每段起止都是交节时刻。
    月干由该年年干按五虎遁推：年干序号 × 2 + 2 是寅月干，此后顺数。

    chart 参数目前只用来保证调用形态与其他函数一致（流月干支与个人盘无关），
    留着是为了将来要按盘做过滤时不必改签名。
    """
    del chart  # 流月干支只取决于年份，与个人盘无关
    year_gan = year_pillar(year).gan
    base_gan = (gz.GAN.index(year_gan) * 2 + 2) % 10
    # 立春到大雪在本年，小寒落在次年
    this_year, next_year = jieqi.jieqi_table(year), jieqi.jieqi_table(year + 1)

    out: list[LiuYue] = []
    for i, name in enumerate(jieqi.JIE):
        table = this_year if i < len(jieqi.JIE) - 1 else next_year
        start = table[name]
        if i + 1 < len(jieqi.JIE):
            nxt = jieqi.JIE[i + 1]
            end = (this_year if i + 1 < len(jieqi.JIE) - 1 else next_year)[nxt]
        else:
            end = next_year["立春"]
        out.append(LiuYue(
            index=i,
            pillar=Pillar(gz.GAN[(base_gan + i) % 10], jieqi.JIE_ZHI[name]),
            jieqi=name, start=start, end=end,
        ))
    return out
