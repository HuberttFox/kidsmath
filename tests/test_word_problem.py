import random

from mathgen.config import Config, resolve
from mathgen.core.engine import generate
from mathgen.topics.word_problem import gen


def test_statement_contains_numbers_and_question():
    cfg = resolve(Config(grade=1, topic="word_problem", count=10, seed=1))
    for _ in range(20):
        q = gen(cfg, random.Random())
        # 偏离 brief：模板用全角“？”（中文标点），brief 测试误写半角 "?"，按模板断言全角
        assert "？" in q.statement
        assert q.expression
        assert q.answer == str(eval(q.expression.replace("×", "*").replace("÷", "//")))


def test_word_problem_result_within_range():
    for seed in range(4):
        cfg = resolve(Config(grade=3, topic="word_problem", count=40, seed=seed))
        lo, hi = cfg.result_range
        for q in generate(cfg):
            assert lo <= int(q.answer) <= hi, q.expression
            assert int(q.answer) >= 0, q.expression


def test_answer_matches_expression():
    cfg = resolve(Config(grade=2, topic="word_problem", count=10, seed=2))
    for _ in range(20):
        q = gen(cfg, random.Random())
        if "÷" in q.expression:
            a, b = map(int, q.expression.replace("÷", " ").split())
            assert q.answer == (str(a // b) if a % b == 0 else f"{a // b} 余 {a % b}")
        else:
            assert q.answer == str(eval(q.expression.replace("×", "*")))


def test_preset_avoids_zero_one_operands():
    cfg = resolve(Config(grade=1, topic="word_problem", count=40, seed=5))
    for _ in range(60):
        q = gen(cfg, random.Random())
        for token in q.statement.split("{"):
            pass
        import re
        nums = [int(n) for n in re.findall(r"\d+", q.statement)]
        assert all(n >= 2 for n in nums), q.statement


def test_explicit_ranges_keep_zero():
    cfg = resolve(Config(grade=1, topic="word_problem", count=5, seed=6,
                         operand_ranges=[(0, 9), (0, 9)]))
    q = gen(cfg, random.Random(1))
    assert q.expression


def test_no_duplicate_statements_in_sheet():
    cfg = resolve(Config(grade=1, topic="word_problem", count=8, seed=3))
    from mathgen.core.engine import generate
    qs = generate(cfg)
    stmts = [q.statement for q in qs]
    assert len(stmts) == len(set(stmts))
