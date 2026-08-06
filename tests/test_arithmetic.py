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
                          operand_ranges=[(100, 999), (10, 99)]))
    for q in generate(cfg2):
        a, b = map(int, q.expression.replace("÷", " ").split())
        assert 100 <= a <= 999 and 10 <= b <= 99, q.expression


def test_four_role_independent_ranges():
    # 加减 1-3 位 + 两位数×一位数 + 被除数两位÷除数一位，全解耦
    cfg = resolve(Config(operators="+-×÷", operand_count=3, parentheses=True,
                         operand_ranges=[(1, 999), (1, 999), (1, 999)],
                         result_range=(0, 1000),
                         left_factor_range=(10, 99), right_factor_range=(2, 9),
                         dividend_range=(10, 99), divisor_range=(2, 9),
                         count=200, seed=31))
    def factor_value(toks, k):
        if toks[k] == "(":
            end = toks.index(")", k)
            return _eval_precedence(toks[k:end + 1])
        if toks[k] == ")":
            depth = 0
            for m in range(k, -1, -1):
                depth += 1 if toks[m] == ")" else -1 if toks[m] == "(" else 0
                if toks[m] == "(" and depth == 0:
                    return _eval_precedence(toks[m:k + 1])
        return int(toks[k])

    for q in generate(cfg):
        toks = q.expression.split(" ")
        assert _eval_precedence(toks) == int(q.answer), q.expression
        for j, t in enumerate(toks):
            if t == "×":
                assert 10 <= factor_value(toks, j - 1) <= 99, q.expression
                assert 2 <= factor_value(toks, j + 1) <= 9, q.expression
            if t == "÷":
                assert 2 <= factor_value(toks, j + 1) <= 9, q.expression
                dividend = _eval_precedence(toks[:j])
                assert 10 <= dividend <= 99, q.expression


def test_paren_group_value_obeys_role_range():
    # (22-9)÷10 类：组值作为被除数须 ∈ 被除数区间；除数须 ∈ 除数区间
    cfg = resolve(Config(operators="+-×÷", operand_count=3, parentheses=True,
                         operand_ranges=[(1, 999), (1, 999), (1, 999)],
                         result_range=(0, 1000),
                         dividend_range=(10, 99), divisor_range=(2, 9),
                         count=150, seed=32))
    for q in generate(cfg):
        if "(" not in q.expression:
            continue
        toks = q.expression.split(" ")
        for i, t in enumerate(toks):
            if t == "(":
                end = toks.index(")", i)
                v = _eval_precedence(toks[i:end + 1])
                # 组邻接 ÷：÷ 在组前 → 组是除数（2-9）；÷ 在组后 → 组是被除数（10-99）
                if i > 0 and toks[i - 1] == "÷":
                    assert 2 <= v <= 9, q.expression
                if end + 1 < len(toks) and toks[end + 1] == "÷":
                    assert 10 <= v <= 99, q.expression
                if i > 0 and toks[i - 1] == "×":
                    assert 2 <= v <= 9, q.expression  # 组是 × 右因数（右因数区间 2-9）
                if end + 1 < len(toks) and toks[end + 1] == "×":
                    assert 10 <= v <= 99, q.expression  # 组是 × 左因数（左因数区间 10-99）


def test_quotient_derived_from_dividend_divisor():
    cfg = resolve(Config(operators="÷", count=60, seed=33,
                         dividend_range=(10, 99), divisor_range=(2, 9)))
    for q in generate(cfg):
        a, b = map(int, q.expression.replace("÷", " ").split())
        qv = a // b
        assert 2 <= qv <= 49, q.expression  # 推导区间 [ceil(10/9), 99//2]
        assert 10 <= a <= 99 and 2 <= b <= 9


def test_impossible_dividend_range_errors():
    from mathgen.core.engine import GenerationError
    import pytest as _pt
    cfg = resolve(Config(operators="÷", count=5, seed=34,
                         dividend_range=(2, 9), divisor_range=(10, 99)))
    with _pt.raises(GenerationError):
        generate(cfg)


def test_preset_multiplication_still_table():
    cfg = resolve(Config(grade=2, operators="×", count=20, seed=13))
    assert not cfg.explicit_ranges
    for q in generate(cfg):
        a, b = map(int, q.expression.replace("×", " ").split())
        lo, hi = cfg.multiplication_table
        assert lo <= a <= hi and lo <= b <= hi


def test_multi_all_mul_factors_in_table():
    from mathgen.topics.arithmetic import _eval_precedence
    cfg = resolve(Config(grade=5, count=40, seed=14,
                         multiplication_table=(2, 9), divisor_range=(2, 9)))
    for q in generate(cfg):
        toks = [t for t in q.expression.split(" ") if t]
        for j, t in enumerate(toks):
            if t != "×":
                continue

            def factor_at(k: int) -> int:
                if toks[k] == "(":
                    end = toks.index(")", k)
                    return _eval_precedence(toks[k:end + 1])
                if toks[k] == ")":
                    depth = 0
                    for m in range(k, -1, -1):
                        if toks[m] == ")":
                            depth += 1
                        elif toks[m] == "(":
                            depth -= 1
                            if depth == 0:
                                return _eval_precedence(toks[m:k + 1])
                return int(toks[k])

            assert 2 <= factor_at(j - 1) <= 9, q.expression
            assert 2 <= factor_at(j + 1) <= 9, q.expression


def test_multi_division_operands_constrained():
    from mathgen.topics.arithmetic import _eval_precedence
    cfg = resolve(Config(grade=5, count=40, seed=15,
                         multiplication_table=(2, 9), divisor_range=(2, 9)))
    for q in generate(cfg):
        toks = [t for t in q.expression.split(" ") if t]
        for j, t in enumerate(toks):
            if t != "÷":
                continue
            # 除数：紧邻右 token，或括号组值
            if toks[j + 1] == "(":
                end = toks.index(")", j)
                divisor = _eval_precedence(toks[j + 1:end + 1])
            else:
                divisor = int(toks[j + 1])
            assert 2 <= divisor <= 9, q.expression
            dividend = _eval_precedence(toks[:j])
            assert 4 <= dividend <= 81, q.expression


def test_multi_no_negative_intermediate():
    cfg = resolve(Config(grade=5, count=40, seed=16))
    for q in generate(cfg):
        toks = q.expression.replace("(", "( ").replace(")", " )").split(" ")
        toks = [t for t in toks if t]
        from mathgen.topics.arithmetic import _intermediate_ok
        assert _intermediate_ok(toks, False), q.expression


def test_multi_paren_group_value_in_table():
    import re as _re
    cfg = resolve(Config(grade=5, count=40, seed=17, multiplication_table=(2, 9)))
    pats = [
        _re.compile(r"^(\d+) ([×÷]) \(\s?(\d+) ([+-]) (\d+)\s?\)$"),
        _re.compile(r"^\(\s?(\d+) ([+-]) (\d+)\s?\) ([×÷]) (\d+)$"),
    ]
    for q in generate(cfg):
        if "(" not in q.expression:
            continue
        m = next((p.match(q.expression) for p in pats if p.match(q.expression)), None)
        assert m, q.expression
        if m.group(2) in "×÷":
            other, op_adj = int(m.group(1)), m.group(2)
            a, b, op = int(m.group(3)), int(m.group(5)), m.group(4)
        else:
            a, b, op = int(m.group(1)), int(m.group(3)), m.group(2)
            op_adj, other = m.group(4), int(m.group(5))
        val = a + b if op == "+" else a - b
        if op_adj == "×":
            assert 2 <= val <= 9 and 2 <= other <= 9, q.expression
        else:  # ÷：右侧组=除数，左侧组=被除数
            if m.group(2) in "×÷":  # num ÷ ( group )：other 是被除数
                assert 4 <= other <= 891, q.expression
            else:  # ( group ) ÷ num：other 是除数
                assert 2 <= other <= 99, q.expression


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
