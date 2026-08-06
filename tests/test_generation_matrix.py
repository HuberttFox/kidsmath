"""生成矩阵：全年级×全题型恒等式 + 关键参数组合大样本约束。"""
import random

import pytest

from mathgen.config import Config, resolve
from mathgen.core.engine import generate
from mathgen.topics.arithmetic import _eval_precedence, _intermediate_ok

GRADES = range(1, 7)
TOPICS = ("arithmetic", "vertical", "word_problem")


def _check_answer(q) -> None:
    """(题, 答) 恒成立：口算/混合用优先级求值，竖式/应用题用 Python 语义。"""
    if q.topic == "arithmetic":
        assert _eval_precedence(q.expression.split(" ")) == int(q.answer), q
    elif q.topic == "vertical":
        if q.layout and q.layout.get("kind") == "vertical":
            toks = q.expression.split(" ")
            a, op, b = int(toks[0]), toks[1], int(toks[2])
            if op == "÷":
                if "余" in q.answer or " R " in q.answer:
                    qv, _, r = q.answer.split(" ")
                    assert int(qv) * b + int(r) == a, q
                else:
                    assert a // b == int(q.answer), q
            else:
                assert {"+": a + b, "-": a - b, "×": a * b}[op] == int(q.answer), q
        else:
            assert eval(q.expression.replace("×", "*").replace("÷", "//")) == int(q.answer), q
    else:  # word_problem
        expr = q.expression
        if "÷" in expr:
            a, b = map(int, expr.replace("÷", " ").split())
            if "余" in q.answer or " R " in q.answer:
                qv, _, r = q.answer.split(" ")
                assert int(qv) * b + int(r) == a, q
            else:
                assert a // b == int(q.answer), q
        else:
            assert eval(expr.replace("×", "*")) == int(q.answer), q


@pytest.mark.parametrize("grade", GRADES)
@pytest.mark.parametrize("topic", TOPICS)
def test_matrix_all_grades_topics_consistent(grade, topic):
    cfg = resolve(Config(grade=grade, topic=topic, count=50, seed=100 + grade))
    qs = generate(cfg)
    assert len(qs) == 50
    lo, hi = cfg.result_range
    for q in qs:
        _check_answer(q)
        if q.topic == "arithmetic" and q.layout is None:
            v = _eval_precedence(q.expression.split(" "))
            assert lo <= v <= hi, q
            assert v >= 0 or cfg.allow_negative, q


def test_matrix_table_divisor_constraints_3ops():
    cfg = resolve(Config(grade=5, count=200, seed=200,
                         multiplication_table=(2, 9), divisor_range=(2, 9)))
    from mathgen.topics.arithmetic import _eval_precedence as ev
    for q in generate(cfg):
        toks = q.expression.split(" ")
        assert _intermediate_ok(toks, False), q.expression
        for j, t in enumerate(toks):
            if t == "×":
                for k in (j - 1, j + 1):
                    if toks[k] == "(":
                        end = toks.index(")", k)
                        v = ev(toks[k:end + 1])
                    elif toks[k] == ")":
                        depth = 0
                        for m in range(k, -1, -1):
                            depth += 1 if toks[m] == ")" else -1 if toks[m] == "(" else 0
                            if toks[m] == "(" and depth == 0:
                                v = ev(toks[m:k + 1])
                                break
                    else:
                        v = int(toks[k])
                    assert 2 <= v <= 9, q.expression
            if t == "÷":
                divisor = ev(toks[j + 1:]) if toks[j + 1] == "(" else int(toks[j + 1])
                if toks[j + 1] == "(":
                    end = toks.index(")", j + 1)
                    divisor = ev(toks[j + 1:end + 1])
                assert 2 <= divisor <= 9, q.expression
                dividend = ev(toks[:j])
                assert 4 <= dividend <= 81, q.expression


@pytest.mark.parametrize("ranges,op,lo0,hi0,lo1,hi1,count", [
    ([(10, 99), (2, 9)], "×", 10, 99, 2, 9, 200),
    ([(2, 9), (10, 99)], "×", 2, 9, 10, 99, 200),
    ([(10, 99), (2, 9)], "÷", 10, 99, 2, 9, 50),
    ([(100, 999), (10, 99)], "÷", 100, 999, 10, 99, 100),
])
def test_matrix_explicit_ranges_asymmetric(ranges, op, lo0, hi0, lo1, hi1, count):
    cfg = resolve(Config(grade=3, operators=op, count=count, seed=300,
                         operand_ranges=ranges, multiplication_table=(2, 9)))
    for q in generate(cfg):
        a, b = map(int, q.expression.replace(op, " ").split())
        assert lo0 <= a <= hi0 and lo1 <= b <= hi1, q.expression


@pytest.mark.parametrize("grade,seeds", [(5, (400, 401)), (6, (402, 403))])
def test_matrix_parens_meaningful(grade, seeds):
    import re
    group = r"\(\s?\d+( [+-] \d+){1,2}\s?\)"
    pats = [
        re.compile(rf"^{group} [×÷] [^()]+$"),
        re.compile(rf"^[^()]+ [×÷] {group}$"),
        re.compile(rf"^{group} [×÷] {group}$"),
        re.compile(rf"^[^()]+ [×÷] {group} [×÷] [^()]+$"),
    ]
    cfg = resolve(Config(grade=grade, count=60, seed=seeds[0]))
    qs = generate(cfg)
    saw = 0
    for q in qs:
        if "(" in q.expression:
            saw += 1
            assert any(p.match(q.expression) for p in pats), q.expression
            assert _eval_precedence(q.expression.split(" ")) == int(q.answer)
    assert saw > 0


def test_matrix_op_weights_distribution_and_zero_exclusion():
    cfg = resolve(Config(grade=2, operators="+×", count=200, seed=500,
                         op_weights={"+": 9, "×": 1}))
    qs = generate(cfg)
    ops = [q.expression.split(" ")[1] for q in qs]
    plus = sum(1 for o in ops if o == "+")
    assert 160 <= plus <= 195, f"加权分布异常: + 出现 {plus}/200"
    cfg0 = resolve(Config(grade=2, operators="+×", count=60, seed=501,
                          op_weights={"+": 1, "×": 0}))
    assert all(q.expression.split(" ")[1] != "×" for q in generate(cfg0))


def test_matrix_numbering_column_direction():
    from mathgen.output.text import arrange
    cfg = resolve(Config(grade=1, count=10, columns=2, seed=600,
                         number_direction="column"))
    qs = generate(cfg)
    rows = arrange(qs, 2, "column")
    assert len(rows) == 5
    for idx, q in enumerate(qs):
        assert rows[idx % 5][idx // 5] is q
    cfg2 = resolve(Config(grade=1, count=6, columns=2, seed=601, show_numbers=False))
    for q in generate(cfg2):
        assert q.expression


def test_matrix_seed_reproducible():
    a = generate(resolve(Config(grade=3, count=20, seed=700)))
    b = generate(resolve(Config(grade=3, count=20, seed=700)))
    assert [q.expression for q in a] == [q.expression for q in b]
