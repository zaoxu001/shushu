"""八字。

自下而上分五段，每一段只做一件事：

    chart / shishen / luck_cycle   排布：四柱、十神、大运流年流月
    strength                       量化：五行力量、日主旺衰、十神力量、寒暖燥湿
    tiaohou / geju / yongshen      取用：调候、格局、用喜忌仇闲
    interact / score               引动：岁运对原局的作用、逐年起伏
    hepan                          双盘：两张盘的关系指标
    shensha                        参考：神煞。取用逻辑不采信，仅为完整性提供

全部是纯函数：不读系统时间、不碰网络与文件，同一输入永远同一输出。
所有模块只输出结构化数据与术语标签，一句叙述性长句都没有——那属于调用方。
"""
from __future__ import annotations

# 先绑子模块名，再导符号。这样 `from tianzhi_core.bazi import shensha` 拿到的是模块，
# 不会被同名函数遮住。
from . import (  # noqa: F401
    chart,
    geju,
    hepan,
    interact,
    luck_cycle,
    score,
    shensha,
    shishen,
    strength,
    tiaohou,
    yongshen,
)

from .chart import Chart, LateZi, Pillar, build_chart, nayin
from .luck_cycle import (
    DaYun,
    LiuNian,
    LiuYue,
    dayun_list,
    is_forward,
    liunian,
    liuyue,
    start_age,
    year_pillar,
)
from .geju import Pattern, PatternHit, PatternOps, month_pattern, pattern_ops, scan_patterns
from .hepan import Synastry, relation_card
from .interact import Interaction, PillarRelation, combine, gan_relations, pillar_relations
from .score import YearPoint, YearScore, curve, score_year
from .shensha import ShenSha
from .shishen import TEN_GODS, TenGod, ten_god, ten_god_of_wuxing
from .strength import (
    Strength,
    climate_index,
    day_master_strength,
    element_power,
    ten_god_power,
)
from .tiaohou import AdverseGods, ClimateGods, ClimateNeed, adverse_gods, climate_gods, climate_need
from .yongshen import DEFAULT_PRIORITY, HEIGE_PRIORITY, YongShen, select

__all__ = [
    "Pillar",
    "Chart",
    "LateZi",
    "build_chart",
    "nayin",
    "TenGod",
    "TEN_GODS",
    "ten_god",
    "ten_god_of_wuxing",
    "DaYun",
    "LiuNian",
    "LiuYue",
    "is_forward",
    "start_age",
    "dayun_list",
    "liunian",
    "liuyue",
    "year_pillar",
    # 量化
    "Strength",
    "element_power",
    "day_master_strength",
    "ten_god_power",
    "climate_index",
    # 取用
    "ClimateGods",
    "AdverseGods",
    "ClimateNeed",
    "climate_gods",
    "adverse_gods",
    "climate_need",
    "Pattern",
    "PatternOps",
    "PatternHit",
    "month_pattern",
    "pattern_ops",
    "scan_patterns",
    "YongShen",
    "select",
    "DEFAULT_PRIORITY",
    "HEIGE_PRIORITY",
    # 引动
    "PillarRelation",
    "Interaction",
    "pillar_relations",
    "gan_relations",
    "combine",
    "YearScore",
    "YearPoint",
    "score_year",
    "curve",
    # 双盘与参考
    "Synastry",
    "relation_card",
    "ShenSha",
]
