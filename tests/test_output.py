from mathgen.config import Config, resolve
from mathgen.core.engine import generate
from mathgen.output.answer import answer_lines
from mathgen.output.text import group_rows, render_text


def test_render_text_numbered():
    cfg = resolve(Config(grade=1, count=3, seed=1))
    qs = generate(cfg)
    out = render_text(qs, cfg)
    assert len(out.splitlines()) == 6  # 标题+页眉+3 题+空行
    for i in range(1, 4):
        assert f"{i}. " in out
    assert all(f"{i}. {q.statement}" in out for i, q in enumerate(qs, 1))


def test_answer_lines_arithmetic():
    cfg = resolve(Config(grade=1, operators="+", count=5, seed=1))
    qs = generate(cfg)
    lines = answer_lines(qs)
    assert len(lines) == 5
    for q, line in zip(qs, lines):
        assert q.expression in line and f"= {q.answer}" in line


def test_answer_lines_remainder():
    from mathgen.topics.arithmetic import gen
    import random
    cfg = resolve(Config(grade=3, operators="÷", count=1, seed=1, allow_remainder=True))
    q = gen(cfg, random.Random(1))
    if "余" in q.answer:
        assert answer_lines([q])[0] == f"{q.expression} = {q.answer}"


def test_group_rows_two_columns():
    qs = [1, 2, 3, 4, 5]
    rows = group_rows(qs, 2)
    assert rows == [[1, 2], [3, 4], [5]]


def test_group_rows_single_column():
    qs = [1, 2, 3]
    assert group_rows(qs, 1) == [[1], [2], [3]]


def test_group_rows_exact_and_empty():
    assert group_rows([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]
    assert group_rows([], 3) == []


def test_arrange_column_direction():
    from mathgen.output.text import arrange
    qs = list("ABCDEFG")
    rows = arrange(qs, 2, "column")
    assert rows == [["A", "E"], ["B", "F"], ["C", "G"], ["D", None]]
    rows2 = arrange(qs, 1, "column")
    assert rows2 == [["A"], ["B"], ["C"], ["D"], ["E"], ["F"], ["G"]]
    assert arrange(qs, 2, "row") == [["A", "B"], ["C", "D"], ["E", "F"], ["G"]]


def test_render_text_without_numbers():
    from mathgen.core.question import Question
    cfg = resolve(Config(grade=1, count=2, seed=1, show_numbers=False))
    qs = [Question("arithmetic", "3 + 5 = ____", "8", "3 + 5", None)] * 2
    out = render_text(qs, cfg)
    assert "1." not in out
    assert "3 + 5 = ____" in out
