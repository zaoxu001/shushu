"""历法层的回归测试：真太阳时与二十四节气。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tianzhi_core.calendar import jieqi, solar_time
from tianzhi_core.core import ganzhi as gz

#: 基准命例：1996-04-18 13:46，赣州经度 114.93
BASE_CLOCK = datetime(1996, 4, 18, 13, 46)
GANZHOU = 114.93


# ── 真太阳时 ──────────────────────────────────────────────────
def test_equation_of_time_is_pure_and_bounded():
    """均时差全年落在 ±16 分钟内，且只取决于年内第几天。"""
    values = [solar_time.equation_of_time(datetime(1996, 1, 1) + timedelta(days=i))
              for i in range(366)]
    assert max(values) < 16.5
    assert min(values) > -16.5
    # 同一天不同时刻，均时差不变（本近似式只吃 day-of-year）
    assert solar_time.equation_of_time(datetime(1996, 4, 18, 0, 0)) == pytest.approx(
        solar_time.equation_of_time(datetime(1996, 4, 18, 23, 59))
    )


def test_longitude_offset_sign():
    """在标准经线以西，当地太阳来得晚，修正为负。"""
    assert solar_time.longitude_offset(114.93) < 0
    assert solar_time.longitude_offset(125.0) > 0
    assert solar_time.longitude_offset(120.0) == 0.0
    # 每度 4 分钟
    assert solar_time.longitude_offset(121.0) == pytest.approx(4.0)


def test_true_solar_time_base_case():
    """基准命例：赣州 13:46 修正后约为 13:26:28，仍落在未时。"""
    corrected = solar_time.true_solar_time(BASE_CLOCK, GANZHOU)
    assert corrected.strftime("%Y-%m-%d %H:%M:%S") == "1996-04-18 13:26:28"
    total = solar_time.correction_minutes(BASE_CLOCK, GANZHOU)
    assert total == pytest.approx(-19.52, abs=0.01)


def test_true_solar_time_keeps_tzinfo():
    """带 tzinfo 的输入只平移时刻，不丢时区。"""
    cst = timezone(timedelta(hours=8))
    out = solar_time.true_solar_time(BASE_CLOCK.replace(tzinfo=cst), GANZHOU)
    assert out.tzinfo == cst


# ── 节气 ─────────────────────────────────────────────────────
@pytest.mark.parametrize("year", [1900, 1949, 1996, 2000, 2024, 2100])
def test_jieqi_table_has_24_entries(year):
    """一个公历年恰好含二十四个节气，各一次，且按时间排好序。"""
    table = jieqi.jieqi_table(year)
    assert len(table) == 24
    assert set(table) == set(jieqi.JIE) | set(jieqi.QI)
    times = list(table.values())
    assert times == sorted(times)
    assert all(t.year == year for t in times)


def test_jie_table_is_the_twelve_jie_only():
    """换月只看十二个节，中气不在其中。"""
    table = jieqi.jie_table(1996)
    assert list(table) == sorted(jieqi.JIE, key=lambda n: table[n])
    assert "雨水" not in table and "春分" not in table


def test_lichun_1996():
    assert jieqi.lichun(1996) == datetime(1996, 2, 4, 21, 7, 54)


def test_month_jieqi_base_case():
    """基准命例落在清明之后、立夏之前，故为辰月。"""
    solar = solar_time.true_solar_time(BASE_CLOCK, GANZHOU)
    name, at = jieqi.month_jieqi(solar)
    assert name == "清明"
    assert at == datetime(1996, 4, 4, 20, 2, 1)
    assert jieqi.month_zhi(solar) == "辰"
    assert jieqi.next_jie(solar)[0] == "立夏"


def test_days_after_jieqi_feeds_siling():
    """距清明约十四天，辰月此时戊土司令（乙 9 天、癸 3 天、戊 18 天）。"""
    solar = solar_time.true_solar_time(BASE_CLOCK, GANZHOU)
    days = jieqi.days_after_jieqi(solar)
    assert days == pytest.approx(13.73, abs=0.02)
    assert round(days) == 14
    assert gz.siling_gan("辰", days) == "戊"
    # 边界自检：头九天乙，第十到十二天癸
    assert gz.siling_gan("辰", 1.0) == "乙"
    assert gz.siling_gan("辰", 10.0) == "癸"


def test_換月以节不以气():
    """过了中气不换月支，过了节才换。1996 年谷雨在 4/20，惊蛰在 3/5。"""
    guyu = jieqi.jieqi_table(1996)["谷雨"]
    assert jieqi.month_zhi(guyu - timedelta(minutes=1)) == "辰"
    assert jieqi.month_zhi(guyu + timedelta(minutes=1)) == "辰"
    jingzhe = jieqi.jieqi_table(1996)["惊蛰"]
    assert jieqi.month_zhi(jingzhe - timedelta(minutes=1)) == "寅"
    assert jieqi.month_zhi(jingzhe + timedelta(minutes=1)) == "卯"


def test_jieqi_moment_belongs_to_new_month():
    """交节那一瞬算进新节令，不留模糊地带。"""
    lc = jieqi.lichun(1996)
    assert jieqi.month_jieqi(lc)[0] == "立春"
    assert jieqi.days_after_jieqi(lc) == 0.0
    assert jieqi.month_jieqi(lc - timedelta(seconds=1))[0] == "小寒"


def test_jieqi_crosses_year_boundary():
    """生在元旦到立春之间，上一个节要回到上一年的小寒。"""
    name, at = jieqi.month_jieqi(datetime(1996, 1, 3, 12, 0))
    assert name == "大雪"
    assert at.year == 1995
    assert jieqi.month_zhi(datetime(1996, 1, 3, 12, 0)) == "子"


def test_tzaware_input_is_normalised_to_cst():
    """带时区的输入折算到东八区再判月令。UTC 的 1996-04-04 12:30 等于北京 20:30，仍在清明前。"""
    utc = timezone.utc
    dt = datetime(1996, 4, 4, 12, 30, tzinfo=utc)  # = 北京 20:30，清明在 20:02
    assert jieqi.month_jieqi(dt)[0] == "清明"
    dt2 = datetime(1996, 4, 4, 11, 30, tzinfo=utc)  # = 北京 19:30
    assert jieqi.month_jieqi(dt2)[0] == "惊蛰"
