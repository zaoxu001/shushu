"""毕法判定的回归测试：每条用该句注中的例，照注文排出整课，看判定是否命中。

注例多写作「某日〔X加Y〕」「某日〔干上X〕」，据此即可定出天地盘；注例未说昼夜的，昼夜两可。
"""
from tianzhi_core.liuren.bifa import detect_parts, RULES
from tianzhi_core.liuren.pan import ZHI, GAN_JIGONG


def _hit(no, gz, sky, earth, day=None):
    yj = ZHI[(ZHI.index(sky) - ZHI.index(earth)) % 12]
    days = (True, False) if day is None else (day,)
    return any(h["no"] == no for d in days for h in detect_parts(gz, yj, "子", d))


def _pos(gz, token):
    """注例写法 → (天盘神, 所临地盘)"""
    if token == "伏吟":
        return "子", "子"
    if token == "返吟":
        return "午", "子"
    if token.startswith("干上"):
        return token[2], GAN_JIGONG[gz[0]]
    if token.startswith("支上"):
        return token[2], gz[1]
    sky, earth = token.split("加")
    return sky, GAN_JIGONG.get(earth, earth)


# (句序, 日, 注例原写法)
NOTE_EXAMPLES = [
    (15, "庚子", "子加庚"),
    (16, "甲申", "干上未"),
    (21, "庚寅", "干上亥"),
    (25, "庚辰", "卯加辰"),
    (26, "癸丑", "干上未"),
    (27, "辛亥", "干上午"),
    (29, "甲申", "干上午"),
    (31, "辛丑", "卯加丑"),
    (32, "辛酉", "干上卯"),
    (33, "乙丑", "亥加丑"),
    (36, "甲申", "干上子"),
    (40, "丁卯", "干上寅"),
    (52, "己丑", "卯加丑"),
    (55, "甲申", "干上卯"),
    (62, "乙未", "伏吟"),
    (63, "丁亥", "干上子"),
    (64, "甲子", "干上戌"),
    (70, "乙未", "申加未"),
    (75, "癸亥", "干上午"),
    (76, "甲申", "干上巳"),
    (77, "辛卯", "干上亥"),
    (78, "甲申", "干上酉"),
    (79, "乙未", "干上申"),
    (80, "庚申", "干上子"),
    (82, "甲子", "干上巳"),
    (83, "乙酉", "申加辰"),
    (88, "壬申", "干上辰"),
    (89, "癸亥", "干上巳"),
    (90, "己酉", "返吟"),
    (22, "乙酉", "伏吟"),
    (22, "壬寅", "伏吟"),
    (91, "己巳", "卯加未"),
]

# 注例写法特殊（如「第一課戌加庚」「干上有旬尾」），照注文手工排出：(句序, 日, 天盘神, 所临地盘, 昼夜, 注文)
MANUAL = [
    (1, "庚辰", "寅", "酉", None, "庚辰日寅加酉為初傳子加未為末傳"),
    (2, "乙未", "卯", "辰", None, "干上有旬尾支上有旬首……乙未辛丑丙申壬寅戊申五日有之"),
    (5, "庚子", "戌", "申", None, "庚子日第一課戌加庚"),
    (6, "己卯", "酉", "未", None, "己卯日第一課酉加己"),
    (7, "乙卯", "卯", "辰", None, "乙卯日干上卯"),
    (8, "甲子", "寅", "子", None, "甲子日寅加子"),
    (23, "癸酉", "巳", "酉", None, "癸酉日初從支上巳起末至干上酉止"),
    (24, "丁亥", "酉", "未", None, "丁亥日自干上酉作初"),
    (30, "甲戌", "寅", "戌", None, "甲戌日寅加戌"),
    (51, "壬午", "戌", "亥", None, "壬午壬辰壬子壬戌癸亥五日并戌加亥"),
    (59, "壬申", "辰", "亥", None, "壬申壬辰二日辰加壬為用"),
    (61, "辛丑", "丑", "戌", True, "六辛日丑加戌旦將乘白虎作墓神"),
]


def test_note_examples():
    for no, gz, tok in NOTE_EXAMPLES:
        assert _hit(no, gz, *_pos(gz, tok)), (no, gz, tok)


def test_manual_examples():
    for no, gz, sky, earth, day, _ in MANUAL:
        assert _hit(no, gz, sky, earth, day), (no, gz)


def test_rules_are_documented():
    for no, verse, rule, _ in RULES:
        assert 1 <= no <= 100 and len(verse) == 7 and rule
