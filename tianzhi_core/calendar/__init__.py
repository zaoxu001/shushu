"""历法层：真太阳时与二十四节气。

这一层把「钟表上的一个时刻」翻译成术数需要的两个坐标：
当地的太阳时，以及这一刻落在哪个节令、距交节多久。
纯函数，不读系统时间，不读系统时区。
"""
from __future__ import annotations

from .jieqi import (
    JIE,
    JIE_ZHI,
    QI,
    ZHI_JIE,
    days_after_jieqi,
    jie_table,
    jieqi_table,
    lichun,
    month_jieqi,
    month_zhi,
    next_jie,
)
from .solar_time import (
    CHINA_STANDARD_LONGITUDE,
    correction_minutes,
    equation_of_time,
    longitude_offset,
    true_solar_time,
)

__all__ = [
    "CHINA_STANDARD_LONGITUDE",
    "equation_of_time",
    "longitude_offset",
    "correction_minutes",
    "true_solar_time",
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
