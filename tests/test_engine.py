import random

import pytest

from mathgen.config import Config, resolve
from mathgen.core.engine import generate, has_borrow, has_carry


def test_seed_reproducible():
    a = generate(resolve(Config(grade=2, count=10, seed=7)))
    b = generate(resolve(Config(grade=2, count=10, seed=7)))
    assert [q.expression for q in a] == [q.expression for q in b]
    c = generate(resolve(Config(grade=2, count=10, seed=8)))
    assert [q.expression for q in a] != [q.expression for q in c]


def test_dedupe_no_duplicates():
    qs = generate(resolve(Config(grade=1, count=30, operators="+", seed=1)))
    exprs = [q.expression for q in qs]
    assert len(exprs) == len(set(exprs))


def test_carry_flag_respected():
    cfg = resolve(Config(grade=1, operators="+", count=30, seed=3, carry=False))
    for q in generate(cfg):
        a, b = map(int, q.expression.split("+"))
        assert not has_carry(a, b), q.expression
    cfg2 = resolve(Config(grade=1, operators="+", count=30, seed=3, carry=True))
    assert any(has_carry(*map(int, q.expression.split("+"))) for q in generate(cfg2))


def test_borrow_flag_respected():
    cfg = resolve(Config(grade=2, operators="-", count=30, seed=4, borrow=False))
    for q in generate(cfg):
        a, b = map(int, q.expression.split("-"))
        assert a >= b and not has_borrow(a, b), q.expression
    cfg2 = resolve(Config(grade=2, operators="-", count=30, seed=4, borrow=True))
    assert any(has_borrow(*map(int, q.expression.split("-"))) for q in generate(cfg2))


def test_result_within_range():
    cfg = resolve(Config(grade=2, operators="+-", count=50, seed=5))
    lo, hi = cfg.result_range
    for q in generate(cfg):
        a, op, b = q.expression.split(" ")
        r = {"+": lambda: int(a) + int(b), "-": lambda: int(a) - int(b)}[op]()
        assert lo <= r <= hi


def test_count():
    qs = generate(resolve(Config(grade=3, count=13, seed=6)))
    assert len(qs) == 13
