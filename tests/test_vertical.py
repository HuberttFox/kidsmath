import random

from mathgen.config import Config, resolve
from mathgen.core.engine import generate
from mathgen.topics.vertical import gen


def test_add_vertical_layout():
    cfg = resolve(Config(grade=2, topic="vertical", operators="+", count=10, seed=1))
    q = gen(cfg, random.Random(1))
    assert q.layout["kind"] == "vertical"
    assert q.layout["op"] == "+"
    a, b = int(q.layout["numbers"][0]), int(q.layout["numbers"][1])
    assert q.answer == str(a + b)
    assert a + b == int(q.answer)


def test_vertical_result_within_range():
    for seed in range(4):
        cfg = resolve(Config(grade=2, topic="vertical", count=40, seed=seed))
        lo, hi = cfg.result_range
        for q in generate(cfg):
            assert lo <= int(q.answer) <= hi, q.expression
            assert int(q.answer) >= 0, q.expression


def test_vertical_mul_result_within_range():
    for seed in range(4):
        cfg = resolve(Config(grade=3, topic="vertical", operators="×",
                             count=40, seed=seed))
        lo, hi = cfg.result_range
        for q in generate(cfg):
            assert lo <= int(q.answer) <= hi, q.expression


def test_sub_vertical_nonnegative():
    cfg = resolve(Config(grade=2, topic="vertical", operators="-", count=10, seed=2))
    for _ in range(20):
        q = gen(cfg, random.Random())
        a, b = int(q.layout["numbers"][0]), int(q.layout["numbers"][1])
        assert a >= b


def test_mul_vertical_uses_table():
    cfg = resolve(Config(grade=3, topic="vertical", operators="×", count=10, seed=3))
    for _ in range(20):
        q = gen(cfg, random.Random())
        a, b = int(q.layout["numbers"][0]), int(q.layout["numbers"][1])
        assert q.answer == str(a * b)
        lo, hi = cfg.multiplication_table
        assert lo <= a <= hi


def test_div_vertical_consistency():
    cfg = resolve(Config(grade=3, topic="vertical", operators="÷", count=10, seed=4))
    for _ in range(20):
        q = gen(cfg, random.Random())
        d, a = int(q.layout["divisor"]), int(q.layout["dividend"])
        qv, r = int(q.layout["quotient"]), int(q.layout["remainder"])
        assert d * qv + r == a and 0 <= r < d
        assert q.answer == (str(qv) if r == 0 else f"{qv} 余 {r}")
