"""测试公用：四柱构造与随机盘生成器。随机数固定种子，测试不得依赖时间或环境。"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tianzhi_core.core import ganzhi  # noqa: E402

#: 基准命例：乙木生辰月，水多木漂、印重
CASE_YI_CHEN = ("丙子", "壬辰", "乙酉", "癸未")
#: 辛金生子月，食伤极旺
CASE_XIN_ZI = ("壬子", "壬子", "辛巳", "丁酉")
#: 戊土生寅月，七杀透
CASE_WU_YIN = ("甲子", "丙寅", "戊辰", "壬子")


def quad(year: str, month: str, day: str, hour: str) -> dict[str, tuple[str, str]]:
    return {
        "year": (year[0], year[1]), "month": (month[0], month[1]),
        "day": (day[0], day[1]), "hour": (hour[0], hour[1]),
    }


def random_quads(n: int = 500, seed: int = 20260920) -> list[dict[str, tuple[str, str]]]:
    """n 张随机盘，四柱各取六十甲子之一。固定种子，结果可复现。"""
    rng = random.Random(seed)
    return [quad(*[rng.choice(ganzhi.JIAZI) for _ in range(4)]) for _ in range(n)]
