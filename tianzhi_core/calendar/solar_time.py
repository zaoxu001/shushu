"""真太阳时：把钟表时间折算成出生地当地的日晷时间。

为什么要做这一步：干支的时柱按太阳在当地的位置分十二时辰，而钟表读的是时区时。
中国全境用东八区一个时间，最东与最西差出一个多小时，不修正会把时柱排错一到两位。

两项修正：

1. **经度时差**。地球每小时转 15 度，即每度 4 分钟。出生地经度减去时区标准经度，
   乘 4 分钟，就是当地视太阳与标准子午线太阳的时刻差。
2. **均时差**（equation of time）。地球轨道是椭圆且黄赤交角不为零，真太阳日长短不一，
   一年之内真太阳时与平太阳时最多差约 ±16 分钟。

本模块只做这两项，不做地方时区推断、不读系统时区、不查城市经纬度表——
这些都是调用方的事，传进来就好。

**流派说明**：术数界对「要不要用真太阳时」有分歧。主张用的认为时柱本就是太阳时；
主张不用的认为古人用的就是当地平太阳时甚至地方官时，且均时差在古法里没有对应概念。
本包不替使用者选边：`tianzhi_core.bazi.chart.build_chart` 有 `use_true_solar` 开关，
默认打开（与主流排盘软件一致），关掉就是拿钟表时间直接排。
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

__all__ = [
    "CHINA_STANDARD_LONGITUDE",
    "equation_of_time",
    "longitude_offset",
    "correction_minutes",
    "true_solar_time",
]

#: 东八区的标准经度。北京时间以东经 120 度为准，不是北京城的 116.4 度。
CHINA_STANDARD_LONGITUDE: float = 120.0


def equation_of_time(dt: datetime) -> float:
    """均时差，单位分钟。正值表示真太阳时快于平太阳时。

    用 Spencer（1971）的截断傅里叶近似式，只吃一个「年内第几天」，
    全年误差在半分钟以内——远小于一个时辰（两小时）的边界容差，对排盘足够。
    更高精度的解析式（如 NOAA 的）需要儒略世纪与黄经，收益在本场景里等于零。

    之所以单独导出，是为了能脱离时区、脱离经度单测这一段天文量。

    >>> round(equation_of_time(datetime(1996, 4, 18)), 3)
    0.758
    """
    day_of_year = dt.timetuple().tm_yday
    b = 2.0 * math.pi * (day_of_year - 81) / 364.0
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def longitude_offset(
    longitude: float,
    standard_longitude: float = CHINA_STANDARD_LONGITUDE,
) -> float:
    """经度时差，单位分钟。出生地在标准经线以西为负（当地太阳来得晚）。"""
    return (longitude - standard_longitude) * 4.0


def correction_minutes(
    dt: datetime,
    longitude: float,
    *,
    standard_longitude: float = CHINA_STANDARD_LONGITUDE,
) -> float:
    """总修正量，单位分钟。等于经度时差加均时差。"""
    return longitude_offset(longitude, standard_longitude) + equation_of_time(dt)


def true_solar_time(
    dt: datetime,
    longitude: float,
    *,
    standard_longitude: float = CHINA_STANDARD_LONGITUDE,
) -> datetime:
    """把标准时区时间修正为出生地的真太阳时。

    纯函数：不读系统时区，不读当前时间。`dt` 被当作 `standard_longitude` 所在时区的
    钟表时间；带 tzinfo 的 datetime 原样保留 tzinfo（只平移时刻），调用方自己负责
    传进来的 dt 与 standard_longitude 是同一个时区。

    :param dt: 出生时刻（标准时区钟表时间）
    :param longitude: 出生地经度，东经为正，西经为负
    :param standard_longitude: 时区标准经线，默认东八区的 120

    >>> true_solar_time(datetime(1996, 4, 18, 13, 46), 114.93).strftime("%H:%M:%S")
    '13:26:28'
    """
    return dt + timedelta(
        minutes=correction_minutes(dt, longitude, standard_longitude=standard_longitude)
    )
