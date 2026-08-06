import random

from mathgen.config import Config, resolve
from mathgen.topics.arithmetic import gen


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
