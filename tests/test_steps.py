"""解题步骤（steps）测试：每道题带非空 steps、末步含答案；多运算数括号题也带步骤。"""
from mathgen.config import Config, resolve
from mathgen.core.engine import generate
from mathgen.topics.steps import (arith_steps, multi_steps, vertical_steps,
                                  word_steps)


def _qs(topic, grade, lang="zh", count=8, seed=7, **kw):
    cfg = resolve(Config(grade=grade, topic=topic, lang=lang,
                         count=count, seed=seed, **kw))
    return generate(cfg)


def _assert_steps_ok(qs):
    assert qs, "生成题目不应为空"
    for q in qs:
        assert q.steps, f"{q.topic} {q.expression} 应有步骤"
        assert all(isinstance(s, str) and s for s in q.steps), q.expression
        assert q.answer in q.steps[-1], (
            f"{q.expression}: 末步 {q.steps[-1]!r} 未含答案 {q.answer!r}")


def test_arithmetic_ops_have_steps():
    for op in "+-×÷":
        _assert_steps_ok(_qs("arithmetic", 2, operators=op))
        _assert_steps_ok(_qs("arithmetic", 2, lang="en", operators=op))


def test_arithmetic_division_remainder_steps():
    _assert_steps_ok(_qs("arithmetic", 3, operators="÷", allow_remainder=True))
    _assert_steps_ok(_qs("arithmetic", 3, lang="en", operators="÷",
                         allow_remainder=True))


def test_vertical_ops_have_steps():
    for op in "+-×÷":
        _assert_steps_ok(_qs("vertical", 3, operators=op))
        _assert_steps_ok(_qs("vertical", 3, lang="en", operators=op))


def test_vertical_division_remainder_steps():
    _assert_steps_ok(_qs("vertical", 3, operators="÷", allow_remainder=True))


def test_word_problem_have_steps():
    _assert_steps_ok(_qs("word_problem", 2))
    _assert_steps_ok(_qs("word_problem", 4, lang="en"))


def test_multi_operand_parens_have_steps():
    qs = _qs("arithmetic", 6, count=30, operators="+-×÷", operand_count=4,
             parentheses=True, paren_weight=10)
    assert any("(" in q.expression for q in qs), "应出现括号题"
    _assert_steps_ok(qs)


def test_multi_steps_precedence():
    steps = multi_steps(["2", "+", "3", "×", "4"], 14, "zh")
    assert steps == [
        "先算乘法：3 × 4 = 12",
        "再算加减（从左到右）：2 + 12 = 14",
        "结果：14",
    ]


def test_multi_steps_multiplication_before_add_subtract():
    steps = multi_steps(
        ["2774", "+", "1794", "-", "13", "×", "46"], 3970, "zh")
    assert steps == [
        "先算乘法：13 × 46 = 598",
        "再算加减（从左到右）：2774 + 1794 = 4568",
        "再算加减（从左到右）：4568 - 598 = 3970",
        "结果：3970",
    ]


def test_multi_steps_same_precedence_runs_left_to_right():
    add_sub = multi_steps(["20", "-", "3", "+", "5"], 22, "zh")
    assert add_sub[:2] == [
        "先算加减：20 - 3 = 17",
        "再算加减（从左到右）：17 + 5 = 22",
    ]
    mul_div = multi_steps(["48", "÷", "6", "×", "5"], 40, "zh")
    assert mul_div[:2] == [
        "先算除法：48 ÷ 6 = 8",
        "再算乘法（从左到右）：8 × 5 = 40",
    ]


def test_multi_steps_parens():
    steps = multi_steps(["(", "2", "+", "3", ")", "×", "4"], 20, "zh")
    assert steps == [
        "先算括号内的加减：2 + 3 = 5",
        "再算乘法（从左到右）：5 × 4 = 20",
        "结果：20",
    ]
    en = multi_steps(["(", "2", "+", "3", ")", "×", "4"], 20, "en")
    assert en == [
        "First add/subtract inside parentheses: 2 + 3 = 5",
        "Then multiply (left to right): 5 × 4 = 20",
        "Result: 20",
    ]


def test_multi_steps_substituted_term():
    steps = multi_steps(["4", "+", "5", "×", "2"], 14, "zh")
    assert "5 × 2 = 10" in steps[0], "先乘后加"
    assert "4 + 10 = 14" in steps[1], "加法复合步代入因数结果"
    assert steps[-1] == "结果：14"


def test_multi_steps_division_parens():
    steps = multi_steps(["(", "20", "÷", "4", ")", "+", "3"], 8, "zh")
    assert "20 ÷ 4 = 5" in steps[0], "括号除法先算"
    assert "5 + 3 = 8" in steps[1], "复合步代入除法结果"
    assert steps[-1] == "结果：8"


def test_arith_steps_carry():
    steps = arith_steps("+", 47, 38, 85, "zh")
    assert "进1" in steps[0]
    assert steps[-1] == "结果：85"


def test_arith_steps_borrow():
    steps = arith_steps("-", 52, 27, 25, "zh")
    assert "不够减" in steps[0]
    assert "加10后：12 - 7 = 5" in steps[1]
    assert steps[-1] == "结果：25"


def test_arith_steps_multiplication():
    both = arith_steps("×", 7, 8, 56, "zh")
    assert both[0] == "乘法表：7 × 8 = 56"
    multi1 = arith_steps("×", 27, 4, 108, "zh")
    assert "个位" in multi1[0]
    multimulti = arith_steps("×", 23, 45, 1035, "zh")
    assert "相加" in multimulti[-2]
    assert multimulti[-1] == "结果：1035"


def test_vertical_steps_division():
    layout = {"kind": "vertical", "op": "÷", "divisor": "6",
              "dividend": "42", "quotient": "7", "remainder": "0"}
    steps = vertical_steps("÷", layout, "zh")
    assert steps[0] == "乘法表：6 × 7 = 42"
    assert steps[-1] == "结果：7"
    layout_r = {"kind": "vertical", "op": "÷", "divisor": "5",
                "dividend": "17", "quotient": "3", "remainder": "2"}
    steps_r = vertical_steps("÷", layout_r, "zh")
    assert steps_r[-1] == "结果：3 余 2"


def test_vertical_steps_uses_column_phrasing():
    layout = {"kind": "vertical", "op": "+", "numbers": ["47", "38"]}
    steps = vertical_steps("+", layout, "zh", result=85)
    assert steps[0].startswith("7 + 8")
    assert steps[-1] == "结果：85"


def test_word_steps_division_neutral():
    steps = word_steps("÷", 12, 4, 3, "zh")
    assert steps[0] == "列式：12 ÷ 4"
    assert steps[1] == "算式：12 ÷ 4 = 3"
    assert steps[-1] == "答：3"
    en = word_steps("÷", 12, 4, 3, "en")
    assert en[1] == "Work: 12 ÷ 4 = 3"
    assert en[-1] == "Answer: 3"


def test_worksheet_cells_carry_steps():
    from mathgen.web import _worksheet_cells
    qs = _qs("arithmetic", 2, count=3)
    cells = _worksheet_cells(qs)
    assert len(cells) == 3
    assert all(c["steps"] for c in cells)


def test_pdf_answer_page_renders_steps():
    from mathgen.output.pdf import render_pdf
    cfg = resolve(Config(grade=5, topic="arithmetic", count=60, seed=42))
    data = render_pdf(generate(cfg), cfg)
    assert data[:4] == b"%PDF"
    assert data.rstrip().endswith(b"%%EOF")
