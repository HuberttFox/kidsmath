import random
import re

from mathgen.config import Config, resolve
from mathgen.topics.arithmetic import _eval_precedence, gen
from mathgen.core.engine import generate


def _eval(expr: str) -> int:
    return eval(expr.replace("×", "*").replace("÷", "//"))


def test_add_sub_within_ranges_and_result():
    cfg = resolve(Config(grade=1, count=20, seed=1))
    for _ in range(30):
        q = gen(cfg, random.Random())
        parts = q.expression.split(" ")
        a, op, b = int(parts[0]), parts[1], int(parts[2])
        assert a >= 0 and b >= 0
        if op == "-":
            assert a >= b
        r = a + b if op == "+" else a - b
        lo, hi = cfg.result_range
        assert lo <= r <= hi, q.expression
        assert q.answer == str(r)
        assert q.statement.endswith("= ____")


def test_multiplication_uses_table():
    cfg = resolve(Config(grade=2, operators="×", count=10, seed=2))
    for _ in range(30):
        q = gen(cfg, random.Random())
        a, b = map(int, q.expression.replace("×", " ").split())
        lo, hi = cfg.multiplication_table
        assert lo <= a <= hi and lo <= b <= hi


def test_division_exact():
    cfg = resolve(Config(grade=3, operators="÷", count=10, seed=3))
    for _ in range(30):
        q = gen(cfg, random.Random())
        a, b = map(int, q.expression.replace("÷", " ").split())
        assert b != 0 and a % b == 0
        assert q.answer == str(a // b)


def test_division_with_remainder():
    cfg = resolve(Config(grade=3, operators="÷", count=10, seed=4, allow_remainder=True))
    saw_remainder = False
    for _ in range(50):
        q = gen(cfg, random.Random())
        a, b = map(int, q.expression.replace("÷", " ").split())
        if a % b != 0:
            saw_remainder = True
        assert q.answer == f"{a // b} 余 {a % b}"
    assert saw_remainder


def test_mixed_three_operands():
    cfg = resolve(Config(grade=5, count=10, seed=5))
    for _ in range(30):
        q = gen(cfg, random.Random())
        assert q.expression.count(" ") >= 4  # 至少 3 个运算数
        assert _eval(q.expression) == int(q.answer)


def test_parentheses():
    cfg = resolve(Config(grade=6, count=10, seed=6))
    saw_paren = False
    for _ in range(50):
        q = gen(cfg, random.Random())
        if "(" in q.statement:
            saw_paren = True
            assert _eval(q.expression) == int(q.answer)
    assert saw_paren


PAREN_3 = re.compile(r"^\d+ [×÷] \(\s?\d+ [+-] \d+\s?\)$|^\(\s?\d+ [+-] \d+\s?\) [×÷] \d+$")


def test_parentheses_only_meaningful_forms():
    cfg = resolve(Config(grade=5, count=30, seed=6))
    qs = generate(cfg)
    for q in qs:
        if "(" in q.expression:
            assert PAREN_3.match(q.expression), q.expression
            assert _eval_precedence(q.expression.split(" ")) == int(q.answer)


def test_parentheses_four_operands_and_double_wrap():
    cfg = resolve(Config(grade=6, count=30, seed=6))
    qs = generate(cfg)
    saw_double = False
    for q in qs:
        if "(" in q.expression:
            toks = q.expression.split(" ")
            assert toks.count("(") in (1, 2), q.expression
            assert _eval_precedence(toks) == int(q.answer)
            saw_double = saw_double or toks.count("(") == 2
    assert saw_double


def test_parentheses_same_precedence_none():
    qs = generate(resolve(Config(grade=5, operators="×÷", count=6, seed=3)))
    assert all("(" not in q.expression for q in qs)
    qs2 = generate(resolve(Config(grade=5, operators="+-", count=6, seed=4)))
    assert all("(" not in q.expression for q in qs2)


def test_parentheses_two_operands_none():
    qs = generate(resolve(Config(grade=5, operators="+-×", operand_count=2, count=8, seed=5)))
    assert all("(" not in q.expression for q in qs)


def test_eval_precedence_left_assoc_and_parens():
    assert _eval_precedence("24 ÷ 6 ÷ 2".split(" ")) == 2
    assert _eval_precedence("10 ÷ 18 ÷ 9".split(" ")) is None
    assert _eval_precedence("22 × ( 2 + 3 )".split(" ")) == 110
    assert _eval_precedence("( 10 + 5 ) ÷ 3".split(" ")) == 5
    assert _eval_precedence("( 2 + 3 ) × ( 4 + 5 )".split(" ")) == 45


def test_multi_respects_table_and_divisor_range():
    for cfg in (
        resolve(Config(grade=3, operators="+-×÷", operand_count=3, count=20, seed=9,
                       operand_ranges=[(10, 999), (10, 999), (10, 999)],
                       multiplication_table=(2, 9), divisor_range=(2, 9))),
        resolve(Config(grade=3, operators="+-×÷", operand_count=3, count=20, seed=10,
                       multiplication_table=(2, 9), divisor_range=(2, 9))),
    ):
        for q in generate(cfg):
            toks = [t for t in q.expression.replace("(", "").replace(")", "").split(" ") if t]
            ops = toks[1::2]
            nums = [int(toks[i]) for i in range(0, len(toks), 2)]
            for j, op in enumerate(ops):
                if op in "×÷":
                    assert 2 <= nums[j + 1] <= 9, q.expression


def test_two_digit_times_one_digit_explicit_ranges():
    cfg = resolve(Config(grade=2, operators="×", count=20, seed=7,
                         operand_ranges=[(10, 99), (2, 9)]))
    assert cfg.explicit_ranges
    for q in generate(cfg):
        a, b = map(int, q.expression.replace("×", " ").split())
        assert 10 <= a <= 99 and 2 <= b <= 9, q.expression
    cfg2 = resolve(Config(grade=2, operators="×", count=20, seed=8,
                          operand_ranges=[(2, 9), (10, 99)]))
    for q in generate(cfg2):
        a, b = map(int, q.expression.replace("×", " ").split())
        assert 2 <= a <= 9 and 10 <= b <= 99, q.expression


def test_division_dividend_divisor_positions():
    cfg = resolve(Config(grade=3, operators="÷", count=20, seed=11,
                         operand_ranges=[(10, 99), (2, 9)],
                         multiplication_table=(2, 9)))
    for q in generate(cfg):
        a, b = map(int, q.expression.replace("÷", " ").split())
        assert 10 <= a <= 99 and 2 <= b <= 9, q.expression
    cfg2 = resolve(Config(grade=3, operators="÷", count=20, seed=12,
                          operand_ranges=[(100, 999), (10, 99)],
                          multiplication_table=(2, 9)))
    for q in generate(cfg2):
        a, b = map(int, q.expression.replace("÷", " ").split())
        assert 100 <= a <= 999 and 10 <= b <= 99, q.expression


def test_preset_multiplication_still_table():
    cfg = resolve(Config(grade=2, operators="×", count=20, seed=13))
    assert not cfg.explicit_ranges
    for q in generate(cfg):
        a, b = map(int, q.expression.replace("×", " ").split())
        lo, hi = cfg.multiplication_table
        assert lo <= a <= hi and lo <= b <= hi


def test_multi_result_within_range():
    cfg = resolve(Config(grade=5, count=30, seed=5))
    lo, hi = cfg.result_range
    for _ in range(30):
        q = gen(cfg, random.Random(42))
        result = _eval(q.expression)
        assert lo <= result <= hi, q.expression
        assert result >= 0, q.expression


def test_two_operand_mul_within_range():
    cfg = resolve(Config(grade=3, operators="×", count=30, seed=3))
    lo, hi = cfg.result_range
    for _ in range(30):
        q = gen(cfg, random.Random(42))
        result = _eval(q.expression)
        assert lo <= result <= hi, q.expression
