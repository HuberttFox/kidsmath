"""应用题：生活场景模板池，数字槽位复用随机引擎。"""
from __future__ import annotations

import random

from mathgen.config import ResolvedConfig
from mathgen.core.engine import check_result, gen_pair, gen_result
from mathgen.core.question import Question

# (模板, 运算)；槽位 a、b 即运算式 "a op b" 的两个数
TEMPLATES = [
    ("小明有{a}个苹果，小红又给他{b}个，现在一共有多少个？", "+"),
    ("教室里有{a}个同学，走了{b}个，还剩多少个？", "-"),
    ("小华买了{a}支铅笔，每支{b}元，一共花了多少元？", "×"),
    ("有{a}颗糖，平均分给{b}个小朋友，每人分到几颗？", "÷"),
    ("小红有{a}朵花，小丽比小红多{b}朵，小丽有多少朵？", "+"),
    ("小明有{a}个气球，飞走了{b}个，还剩几个？", "-"),
    ("一本书有{a}页，每天看{b}页，几天能看完？", "÷"),
    ("一盒彩笔有{a}支，{b}盒一共有多少支？", "×"),
    ("小刚有{a}个玩具，送给弟弟{b}个，还剩多少个？", "-"),
    ("果园里有{a}棵苹果树，又种了{b}棵，现在一共有多少棵？", "+"),
]


def gen(cfg: ResolvedConfig, rng: random.Random) -> Question:
    template, op = rng.choice(TEMPLATES)
    if op in "+-":
        def make():
            a, b = gen_pair(rng, cfg.operand_ranges,
                            None if op == "+" else cfg.borrow,
                            None if op == "-" else None,
                            True if op == "+" else cfg.allow_negative)
            return a, b, (a + b if op == "+" else a - b)

        a, b, result = gen_result(make, lambda t: check_result(cfg)(t[2]))
    elif op == "×":
        lo, hi = cfg.multiplication_table

        def make():
            a = rng.randint(lo, hi)
            b = rng.randint(lo, hi)
            return a, b, a * b

        a, b, result = gen_result(make, lambda t: check_result(cfg)(t[2]))
    else:
        lo, hi = cfg.multiplication_table
        d_lo, d_hi = cfg.divisor_range

        def make():
            divisor = rng.randint(d_lo, d_hi)
            quotient = rng.randint(lo, hi)
            return divisor, quotient, divisor * quotient

        divisor, quotient, a = gen_result(make, lambda t: check_result(cfg)(t[1]))
        b = divisor
        result = quotient
    statement = template.format(a=a, b=b)
    expr = f"{a} {op} {b}"
    return Question("word_problem", statement, str(result), expr, None)
