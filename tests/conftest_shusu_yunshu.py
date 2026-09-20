"""岁运 / 合盘 / 神煞三块测试共用的基准数据。

不用 conftest.py，免得与另外两块的测试撞名——直接 import 这个模块即可。
"""
from __future__ import annotations

from shushu.core import ganzhi

#: 基准盘：丙子 壬辰 乙酉 癸未
BASE_QUAD: dict[str, tuple[str, str]] = {
    "year": ("丙", "子"),
    "month": ("壬", "辰"),
    "day": ("乙", "酉"),
    "hour": ("癸", "未"),
}
FAVORABLE: list[str] = ["火", "土"]
UNFAVORABLE: list[str] = ["水"]


def jiazi_after(gz: str, step: int) -> str:
    """六十甲子里往后数 step 位。"""
    return ganzhi.JIAZI[(ganzhi.jiazi_index(gz) + step) % 60]


def sample_cycles(quad: dict[str, tuple[str, str]], *, birth_year: int = 1996,
                  start_age: int = 5, steps: int = 9, per_step: int = 10):
    """造一条形状合理的大运流年表：大运从月柱顺排，流年按甲子顺推。

    只用于测试，不代表真实起运——真正的排运由 chart 层负责。
    """
    from shushu.bazi.score import Cycle

    month_gz = "".join(quad["month"])
    year_gz = "".join(quad["year"])
    out = []
    # 起运之前的那几年，没有大运
    pre = tuple((birth_year + i, jiazi_after(year_gz, i)) for i in range(start_age))
    if pre:
        out.append(Cycle("", pre))
    for s in range(steps):
        dy = jiazi_after(month_gz, s + 1)
        base_age = start_age + s * per_step
        years = tuple((birth_year + base_age + i, jiazi_after(year_gz, base_age + i))
                      for i in range(per_step))
        out.append(Cycle(dy, years))
    return out
