"""二十四节气：交节时刻，以及「这一刻属于哪个月令」。

节气时刻是天文量，要算日月位置、章动、地球时与世界时之差。本包不自己算天文，
依赖 `lunar_python`（MIT，6tail/lunar-python）：它移植自被广泛核对过的 lunar 系列，
1900–2100 年区间的交节时刻与紫金山天文台历书一致到分钟级。自己写一份只会多一个错误来源。

**节与气要分清**：二十四节气里单数位叫「节」（立春、惊蛰、清明……），双数位叫「气」
（雨水、春分、谷雨……，又称中气）。八字换月支以**节**为界，不以气为界——
过了立春才是寅月，过了惊蛰才是卯月。农历的闰月规则才看中气，那是另一套，别混。

**时间基准**：本模块返回的 datetime 一律是 naive 的东八区法定时（北京时间）。
排盘时用真太阳时与这里的交节时刻直接比较，严格说是拿当地视时比北京时——
这是主流排盘软件（含本包参考实现）的既定做法，误差不超过一小时，
只有生在交节前后半小时内才可能有争议。需要严谨的调用方应把两边都换算到同一基准再比。
带 tzinfo 的 datetime 传进来会先折算到东八区并去掉 tzinfo。
"""
from __future__ import annotations

import bisect
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from lunar_python import Solar

__all__ = [
    "JIE",
    "QI",
    "JIE_ZHI",
    "ZHI_JIE",
    "jieqi_table",
    "jie_table",
    "month_jieqi",
    "month_zhi",
    "days_after_jieqi",
    "next_jie",
    "lichun",
]

#: 十二节，按寅月起的次序。八字换月看这一组。
JIE: tuple[str, ...] = (
    "立春", "惊蛰", "清明", "立夏", "芒种", "小暑",
    "立秋", "白露", "寒露", "立冬", "大雪", "小寒",
)
#: 十二气（中气）。本包排盘不用，列出来是为了让 jieqi_table 的结果能被分类。
QI: tuple[str, ...] = (
    "雨水", "春分", "谷雨", "小满", "夏至", "大暑",
    "处暑", "秋分", "霜降", "小雪", "冬至", "大寒",
)

#: 节 → 该节开启的月支
JIE_ZHI: dict[str, str] = {name: zhi for name, zhi in zip(
    JIE, ("寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑")
)}
#: 月支 → 开启它的那个节
ZHI_JIE: dict[str, str] = {v: k for k, v in JIE_ZHI.items()}

#: lunar_python 的节气表里，跨年重复出现的那几个用大写拼音做键，这里还原成中文名。
_ALIAS: dict[str, str] = {
    "DA_XUE": "大雪", "DONG_ZHI": "冬至", "XIAO_HAN": "小寒", "DA_HAN": "大寒",
    "LI_CHUN": "立春", "YU_SHUI": "雨水", "JING_ZHE": "惊蛰",
}

#: 东八区。只用于把带 tzinfo 的输入折算成本模块的 naive 基准。
_CST = timezone(timedelta(hours=8))


def as_naive(dt: datetime) -> datetime:
    """统一时间基准：带 tzinfo 的折算到东八区并去掉 tzinfo，naive 的原样返回。"""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(_CST).replace(tzinfo=None)


@lru_cache(maxsize=512)
def jieqi_table(year: int) -> dict[str, datetime]:
    """某个公历年里二十四节气的精确交节时刻，按时间先后排序。

    键是中文节气名，值是东八区 naive datetime，精确到秒。恰好 24 项：
    一个公历年总是含首尾各一段不完整的农历年，但二十四个节气各出现且只出现一次。

    带 lru_cache 是因为排大运流年要反复查相邻几十年，而 lunar_python 每次
    构造 LunarYear 都会把当年的节气从头算一遍（上百万次三角函数）。
    """
    raw = Solar.fromYmdHms(year, 6, 1, 12, 0, 0).getLunar().getJieQiTable()
    out: dict[str, datetime] = {}
    for key, solar in raw.items():
        name = _ALIAS.get(key, key)
        dt = datetime(
            solar.getYear(), solar.getMonth(), solar.getDay(),
            solar.getHour(), solar.getMinute(), solar.getSecond(),
        )
        # 表里带了相邻年的节气（键名用拼音区分），只留落在本年的。
        if dt.year == year:
            out[name] = dt
    return dict(sorted(out.items(), key=lambda kv: kv[1]))


def jie_table(year: int) -> dict[str, datetime]:
    """某个公历年里十二个「节」的交节时刻，按时间先后排序。换月支只看这一组。"""
    table = jieqi_table(year)
    return {k: v for k, v in table.items() if k in JIE_ZHI}


@lru_cache(maxsize=512)
def _jie_axis(year: int) -> tuple[tuple[datetime, str], ...]:
    """year-1、year、year+1 三年的节，合成一条按时间排好的轴，供二分查找。

    取三年是因为：生在一月初的人，上一个节（小寒）可能在同一年，
    但生在立春前的人要往前找到上一年的节；而找下一个节可能要跨到下一年。
    """
    items: list[tuple[datetime, str]] = []
    for y in (year - 1, year, year + 1):
        items.extend((dt, name) for name, dt in jie_table(y).items())
    items.sort()
    return tuple(items)


def _prev_index(dt: datetime) -> tuple[tuple[tuple[datetime, str], ...], int]:
    """返回节气轴和「最后一个不晚于 dt 的节」的下标。"""
    axis = _jie_axis(dt.year)
    # bisect_right：交节那一秒算作已入新月令（过节即换月，不留模糊地带）。
    i = bisect.bisect_right(axis, (dt, "￿")) - 1
    if i < 0:
        raise ValueError(f"节气数据不覆盖 {dt!r}，lunar_python 的可用区间约为 1900–2100")
    return axis, i


def month_jieqi(dt: datetime) -> tuple[str, datetime]:
    """这一刻落在哪个节令里，以及该节令的交节时刻。

    返回 (节名, 交节时刻)。交节的那一瞬间算进新节令。
    """
    dt = as_naive(dt)
    axis, i = _prev_index(dt)
    when, name = axis[i]
    return name, when


def month_zhi(dt: datetime) -> str:
    """这一刻的月支。过节才换支，不看中气，也不看农历月。"""
    return JIE_ZHI[month_jieqi(dt)[0]]


def days_after_jieqi(dt: datetime) -> float:
    """距上一个**节**过了多少天，带小数。

    这个值喂给 `tianzhi_core.core.ganzhi.siling_gan`，用来定月令人元司令——
    同是辰月，生在清明后第三天与第二十天，当令的藏干不是一个。
    """
    dt = as_naive(dt)
    _, when = month_jieqi(dt)
    return (dt - when).total_seconds() / 86400.0


def next_jie(dt: datetime) -> tuple[str, datetime]:
    """下一个节及其交节时刻。起运顺行时要数到这里。"""
    dt = as_naive(dt)
    axis, i = _prev_index(dt)
    when, name = axis[i + 1]
    return name, when


def lichun(year: int) -> datetime:
    """某个公历年立春的精确时刻。八字年柱以此为界，不是元旦，也不是正月初一。"""
    return jieqi_table(year)["立春"]
