"""排盘层的回归测试：四柱、十神、三宫、大运流年流月。

基准命例取自参考实现（bazi/app.py）：1996-04-18 13:46，赣州经度 114.93，男。
凡是「跟现有实现对拍」的用例，都直接调 lunar_python 现算一份来比，
而不是把答案抄成常量——这样库升级导致的口径漂移会立刻暴露。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from lunar_python import Solar

from tianzhi_core.bazi import luck_cycle as lc
from tianzhi_core.bazi.chart import Pillar, build_chart
from tianzhi_core.bazi.shishen import ten_god, ten_god_of_wuxing
from tianzhi_core.calendar import jieqi, solar_time
from tianzhi_core.core import ganzhi as gz

BASE_CLOCK = datetime(1996, 4, 18, 13, 46)
GANZHOU = 114.93


@pytest.fixture(scope="module")
def base():
    """基准命例：男，开真太阳时，晚子时默认流派一。"""
    return build_chart(BASE_CLOCK, longitude=GANZHOU, gender=0)


@pytest.fixture(scope="module")
def reference():
    """参考实现的同一张盘（lunar_python，秒位按 app.py 的做法截掉）。"""
    c = solar_time.true_solar_time(BASE_CLOCK, GANZHOU)
    solar = Solar.fromYmdHms(c.year, c.month, c.day, c.hour, c.minute, 0)
    return solar.getLunar().getEightChar()


# ── 基准命例：四柱 ────────────────────────────────────────────
def test_base_case_four_pillars(base):
    assert base.bazi == "丙子 壬辰 乙酉 癸未"
    assert [p.ganzhi for p in base.pillars] == ["丙子", "壬辰", "乙酉", "癸未"]


def test_base_case_matches_reference(base, reference):
    """与参考实现逐柱对拍。"""
    assert (base.year.ganzhi, base.month.ganzhi, base.day.ganzhi, base.hour.ganzhi) == (
        reference.getYear(), reference.getMonth(), reference.getDay(), reference.getTime()
    )


def test_base_case_day_master(base):
    assert base.day_master == "乙"
    assert base.day_element == "木"
    assert base.day_yang is False


def test_base_case_month_and_siling(base):
    """月令辰，距清明约十四天，戊土司令。"""
    assert base.month.zhi == "辰"
    assert base.month_jieqi[0] == "清明"
    assert round(base.days_after_jieqi) == 14
    assert base.siling == "戊"
    assert base.siling_shishen == "正财"   # 乙木见戊土


def test_base_case_three_palaces(base, reference):
    assert base.minggong.ganzhi == "甲午"
    assert base.shengong.ganzhi == "庚子"
    assert base.taiyuan.ganzhi == "癸未"
    assert base.minggong.ganzhi == reference.getMingGong()
    assert base.shengong.ganzhi == reference.getShenGong()
    assert base.taiyuan.ganzhi == reference.getTaiYuan()


def test_base_case_pillar_details(base):
    assert base.nayin("day") == "泉中水"
    assert base.ten_god_of("year") == "伤官"      # 乙木见丙火
    assert base.ten_god_of("month") == "正印"     # 乙木见壬水
    assert base.ten_god_of("hour") == "偏印"      # 乙木见癸水
    hidden = base.hidden("month")
    assert [h["gan"] for h in hidden] == ["戊", "乙", "癸"]
    assert [h["level"] for h in hidden] == ["本", "中", "余"]
    assert [h["shishen"] for h in hidden] == ["正财", "比肩", "偏印"]
    assert base.wuxing_counts == {"木": 1, "火": 1, "土": 2, "金": 1, "水": 3}


def test_to_dict_is_pure_data(base):
    d = base.to_dict()
    assert d["bazi"] == "丙子 壬辰 乙酉 癸未"
    assert d["pillars"]["day"]["dishi"] == "绝"
    assert d["siling"] == {"gan": "戊", "shishen": "正财"}


# ── 真太阳时开关 ──────────────────────────────────────────────
def test_longitude_zero_means_no_correction():
    """没给经度就不做修正，不会被静默地按本初子午线平移八小时。"""
    c = build_chart(BASE_CLOCK)
    assert c.solar == BASE_CLOCK
    assert c.solar_correction == 0.0


def test_use_true_solar_switch_changes_hour_pillar():
    """找一个修正后跨过时辰界的时刻，验证开关确实起作用。"""
    clock = datetime(1996, 4, 18, 15, 5)     # 修正约 -19.5 分钟 → 14:45，申时退回未时
    on = build_chart(clock, longitude=GANZHOU, use_true_solar=True)
    off = build_chart(clock, longitude=GANZHOU, use_true_solar=False)
    assert off.hour.zhi == "申"
    assert on.hour.zhi == "未"


# ── 节气边界：年柱切换 ────────────────────────────────────────
def test_lichun_boundary_switches_year_pillar():
    """1996 年立春在 02-04 21:07:54。前一分钟仍是乙亥年丑月，后一分钟即丙子年寅月。"""
    lich = jieqi.lichun(1996)
    before = build_chart(lich - timedelta(minutes=1), use_true_solar=False)
    after = build_chart(lich + timedelta(minutes=1), use_true_solar=False)
    assert before.year.ganzhi == "乙亥"
    assert before.month.zhi == "丑"
    assert after.year.ganzhi == "丙子"
    assert after.month.zhi == "寅"
    # 只差两分钟，日柱不变，年月柱全换
    assert before.day.ganzhi == after.day.ganzhi


def test_lichun_boundary_matches_reference():
    """立春前后各取一点，与参考实现对拍年柱。"""
    lich = jieqi.lichun(1996)
    for dt in (lich - timedelta(minutes=1), lich + timedelta(minutes=1)):
        mine = build_chart(dt, use_true_solar=False)
        ref = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0) \
            .getLunar().getEightChar()
        assert mine.year.ganzhi == ref.getYear()
        assert mine.month.ganzhi == ref.getMonth()


def test_new_year_before_lichun_uses_previous_year_pillar():
    """元旦之后、立春之前出生，年柱仍算上一年。"""
    c = build_chart(datetime(1996, 1, 20, 12, 0), use_true_solar=False)
    assert c.year.ganzhi == "乙亥"
    assert c.month.zhi == "丑"


# ── 晚子时 ───────────────────────────────────────────────────
def test_late_zi_two_schools_differ():
    """23:30 出生，两种流派下日柱差一位，时干也随之不同。"""
    clock = datetime(1996, 4, 18, 23, 30)
    nxt = build_chart(clock, use_true_solar=False, late_zi="next_day")
    same = build_chart(clock, use_true_solar=False, late_zi="same_day")

    assert same.day.ganzhi == "乙酉"          # 当日日柱
    assert nxt.day.ganzhi == "丙戌"           # 进一位
    assert (nxt.day.index - same.day.index) % 60 == 1
    # 时支都是子，时干各自由本盘日干按五鼠遁推，保持自洽
    assert nxt.hour.zhi == same.hour.zhi == "子"
    assert nxt.hour.ganzhi == "戊子"
    assert same.hour.ganzhi == "丙子"


def test_late_zi_irrelevant_before_23():
    """22:59 出生与流派无关，两种参数结果相同。"""
    clock = datetime(1996, 4, 18, 22, 59)
    a = build_chart(clock, use_true_solar=False, late_zi="next_day")
    b = build_chart(clock, use_true_solar=False, late_zi="same_day")
    assert a.bazi == b.bazi == "丙子 壬辰 乙酉 丁亥"


def test_early_zi_belongs_to_that_day():
    """00:30 是早子时，两派一致都算当日。"""
    clock = datetime(1996, 4, 19, 0, 30)
    for school in ("next_day", "same_day"):
        c = build_chart(clock, use_true_solar=False, late_zi=school)
        assert c.day.ganzhi == "丙戌"
        assert c.hour.ganzhi == "戊子"


def test_bad_arguments():
    with pytest.raises(ValueError):
        build_chart(BASE_CLOCK, late_zi="whatever")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        build_chart(BASE_CLOCK, gender=2)


# ── 日柱：与参考实现大范围对拍 ────────────────────────────────
@pytest.mark.parametrize("dt", [
    datetime(1900, 1, 1, 12, 0), datetime(1949, 10, 1, 12, 0),
    datetime(1984, 2, 2, 12, 0), datetime(2000, 2, 29, 12, 0),
    datetime(2024, 12, 31, 12, 0), datetime(2100, 6, 15, 12, 0),
])
def test_day_pillar_matches_reference(dt):
    mine = build_chart(dt, use_true_solar=False)
    ref = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0) \
        .getLunar().getDayInGanZhi()
    assert mine.day.ganzhi == ref


def test_day_pillar_anchor():
    """1949-10-01 是甲子日，六十甲子的锚点。"""
    assert build_chart(datetime(1949, 10, 1, 12, 0), use_true_solar=False).day.ganzhi == "甲子"


# ── 十二长生 ─────────────────────────────────────────────────
def test_dishi_yin_gan_runs_backwards(base):
    """乙木在酉为绝：阴干逆行，乙长生在午，逆数到酉正是绝。"""
    assert gz.dishi("乙", "酉") == "绝"
    assert base.dishi("day") == "绝"


def test_dishi_yang_gan_runs_forwards():
    """甲木在亥为长生：阳干顺行，甲长生在亥。"""
    assert gz.dishi("甲", "亥") == "长生"
    assert gz.dishi("甲", "子") == "沐浴"
    assert gz.dishi("乙", "午") == "长生"


def test_zizuo_uses_pillar_own_gan(base):
    """自坐看本柱天干坐本柱地支：壬水坐辰为墓。"""
    assert base.zizuo("month") == gz.dishi("壬", "辰")
    assert base.zizuo("month") == "墓"


# ── 十神 ─────────────────────────────────────────────────────
def test_ten_god_polarity_rule():
    """同阴阳取偏侧，异阴阳取正侧；比劫食伤的命名与直觉相反。"""
    assert ten_god("乙", "乙") == "比肩"     # 同干
    assert ten_god("甲", "乙") == "劫财"     # 同五行异阴阳
    assert ten_god("丙", "乙") == "伤官"     # 我生，异阴阳
    assert ten_god("丁", "乙") == "食神"     # 我生，同阴阳
    assert ten_god("戊", "乙") == "正财"
    assert ten_god("己", "乙") == "偏财"
    assert ten_god("庚", "乙") == "正官"
    assert ten_god("辛", "乙") == "七杀"
    assert ten_god("壬", "乙") == "正印"
    assert ten_god("癸", "乙") == "偏印"


def test_ten_god_matches_reference():
    """一百组干对干，与 lunar_python 的十神表逐个对拍。"""
    from lunar_python.util import LunarUtil
    for day in gz.GAN:
        for target in gz.GAN:
            assert ten_god(target, day) == LunarUtil.SHI_SHEN.get(day + target)


def test_ten_god_of_wuxing_is_the_five_bucket_version():
    assert ten_god_of_wuxing("水", "乙") == "印"
    assert ten_god_of_wuxing("土", "乙") == "财"
    assert ten_god_of_wuxing("木", "乙") == "比劫"
    with pytest.raises(ValueError):
        ten_god_of_wuxing("雷", "乙")


# ── 大运 ─────────────────────────────────────────────────────
def test_direction_is_yang_male_forward(base):
    """年干丙为阳，男，故顺行。"""
    assert base.year.gan in gz.GAN_YANG
    assert lc.is_forward(base) is True
    female = build_chart(BASE_CLOCK, longitude=GANZHOU, gender=1)
    assert lc.is_forward(female) is False


def test_start_age_matches_reference(base, reference):
    """起运岁数与交运时刻，跟参考实现（lunar_python，流派一）对拍。"""
    age, enter = lc.start_age(base)
    yun = reference.getYun(1)          # lunar_python：1 男 0 女
    assert int(age) == yun.getStartYear() == 5
    assert age == pytest.approx(5 + 8 / 12)
    ref_enter = yun.getStartSolar()
    assert (enter.year, enter.month, enter.day) == (
        ref_enter.getYear(), ref_enter.getMonth(), ref_enter.getDay()
    )
    assert (enter.year, enter.month, enter.day) == (2001, 12, 18)


def test_dayun_list_matches_reference(base, reference):
    """逐步大运的干支与起讫岁数，跟参考实现对拍。"""
    mine = lc.dayun_list(base, 8)
    ref = reference.getYun(1).getDaYun(9)[1:]   # 参考实现的 index 0 是起运前的童限，不是大运
    assert [d.ganzhi for d in mine] == [d.getGanZhi() for d in ref]
    assert [d.start_age for d in mine] == [d.getStartAge() for d in ref]
    assert [d.end_age for d in mine] == [d.getEndAge() for d in ref]
    assert [d.start_year for d in mine] == [d.getStartYear() for d in ref]
    assert mine[0].ganzhi == "癸巳"
    assert mine[0].index == 1
    assert (mine[0].start_age, mine[0].end_age) == (6, 15)
    assert (mine[0].start_year, mine[0].end_year) == (2001, 2010)


def test_dayun_steps_from_month_pillar(base):
    """顺行时每步在月柱之后依次加一位。"""
    base_i = base.month.index
    for d in lc.dayun_list(base, 6):
        assert d.pillar.index == (base_i + d.index) % 60


def test_dayun_backward_for_yin_male():
    """阴年男逆行：每步在月柱之前依次减一位。"""
    c = build_chart(datetime(1995, 6, 10, 10, 0), use_true_solar=False, gender=0)
    assert c.year.gan not in gz.GAN_YANG
    assert lc.is_forward(c) is False
    steps = lc.dayun_list(c, 5)
    for d in steps:
        assert d.pillar.index == (c.month.index - d.index) % 60


def test_start_age_two_sects_are_close(base):
    a1, _ = lc.start_age(base, sect=1)
    a2, _ = lc.start_age(base, sect=2)
    assert abs(a1 - a2) < 0.05
    with pytest.raises(ValueError):
        lc.start_age(base, sect=3)  # type: ignore[arg-type]


# ── 流年、流月 ───────────────────────────────────────────────
def test_liunian_ganzhi_and_age(base):
    rows = lc.liunian(base, 1996, 2026)
    assert len(rows) == 31
    assert rows[0].year == 1996 and rows[0].ganzhi == "丙子" and rows[0].age == 1
    assert rows[-1].year == 2026 and rows[-1].ganzhi == "丙午" and rows[-1].age == 31
    # 六十甲子循环
    assert lc.year_pillar(1984).ganzhi == "甲子"
    assert lc.year_pillar(2044).ganzhi == "甲子"
    with pytest.raises(ValueError):
        lc.liunian(base, 2000, 1999)


def test_liuyue_follows_jieqi_not_lunar_month(base):
    """流月十二段，首段自立春起为寅月，末段自小寒起为丑月，段段首尾相接。"""
    months = lc.liuyue(base, 2026)
    assert len(months) == 12
    assert [m.zhi for m in months] == list("寅卯辰巳午未申酉戌亥子丑")
    assert months[0].jieqi == "立春"
    assert months[0].start == jieqi.lichun(2026)
    assert months[11].jieqi == "小寒"
    assert months[11].start.year == 2027
    assert months[11].end == jieqi.lichun(2027)
    for a, b in zip(months, months[1:]):
        assert a.end == b.start
    # 丙年五虎遁：丙辛之年寻庚上，寅月为庚寅
    assert months[0].ganzhi == "庚寅"
    assert months[2].ganzhi == "壬辰"


def test_liuyue_matches_reference(base):
    """流月干支跟参考实现对拍（取 2026 丙午年）。"""
    mine = [m.ganzhi for m in lc.liuyue(base, 2026)]
    # 参考实现从流年对象取流月
    ec = Solar.fromYmdHms(1996, 4, 18, 13, 26, 0).getLunar().getEightChar()
    yun = ec.getYun(1)
    for dy in yun.getDaYun(10):
        for ln in dy.getLiuNian():
            if ln.getYear() == 2026:
                assert [ly.getGanZhi() for ly in ln.getLiuYue()] == mine
                return
    pytest.fail("参考实现里没找到 2026 流年")


def test_pillar_helpers():
    assert Pillar.from_ganzhi("甲子").index == 0
    assert Pillar.from_index(-1).ganzhi == "癸亥"
    assert str(Pillar("壬", "辰")) == "壬辰"
    with pytest.raises(ValueError):
        Pillar.from_ganzhi("甲甲")
