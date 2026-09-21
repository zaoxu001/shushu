"""藏干次序与人元司令分日必须自洽。

辰戌丑未四墓库各藏三干，司令分日恰好是 18 / 9 / 3 天，分别对应本气、中气、余气。
曾出现过未支把中气与余气写反：两张表各自看都对，合起来却矛盾，而且因为
ROOT_COEF 中气 0.5、余气 0.3，凡是带未的盘五行分量都会偏。这条测试把两张表锁在一起。

其余八支的司令分日不是这个比例（如寅为 7/7/16、申为 10/3/17），各家分法也不尽相同，
不适用这条约束，故不纳入。另有一处已知的来源差异：申的司令表首位作己，而藏干表作戊，
二者同属土，五行结论不受影响，此处不作断言。
"""
from shushu.core import ganzhi as G

MU_KU = ("丑", "辰", "未", "戌")
LEVEL_BY_DAYS = {18: "本", 9: "中", 3: "余"}


def test_storage_branch_hidden_order_matches_siling():
    table = G.siling_table()
    for zhi in MU_KU:
        hidden = {gan: level for gan, level in G.HIDDEN[zhi]}
        days = {item["gan"]: item["days"] for item in table[zhi]}
        assert sorted(days.values()) == [3, 9, 18], f"{zhi} 的司令分日不是 18/9/3"
        for gan, d in days.items():
            assert hidden.get(gan) == LEVEL_BY_DAYS[d], (
                f"{zhi} 藏 {gan}：司令 {d} 日应为 {LEVEL_BY_DAYS[d]} 气，"
                f"藏干表里却是 {hidden.get(gan)}"
            )


def test_hidden_matches_classical_table():
    """十二支藏干与通行本一致。"""
    expect = {
        "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
        "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
        "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
        "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
    }
    for zhi, gans in expect.items():
        assert [g for g, _ in G.HIDDEN[zhi]] == gans, zhi
