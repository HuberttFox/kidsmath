from mathgen.config import Config, resolve
from mathgen.core.engine import generate
from mathgen.core.question import Question
from mathgen.output.fonts import register_fonts
from mathgen.output.pdf import render_pdf, _draw_vertical
import mathgen.output.pdf as pdf_module

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO


def test_pdf_header_and_answers():
    for topic in ("arithmetic",):
        cfg = resolve(Config(grade=2, topic=topic, count=8, seed=1, answer_page=True))
        qs = generate(cfg)
        data = render_pdf(qs, cfg)
        assert data[:4] == b"%PDF", topic
        assert data.rstrip().endswith(b"%%EOF"), topic


def test_pdf_vertical_layout_renders():
    cfg = resolve(Config(grade=2, topic="arithmetic", count=1, seed=1))
    layout = {"kind": "vertical", "op": "+", "numbers": ["12", "34"]}
    q = Question(topic="vertical", statement="12+34", answer="46",
                 expression="12 + 34", layout=layout)
    data = render_pdf([q], cfg)
    assert data[:4] == b"%PDF"
    assert data.rstrip().endswith(b"%%EOF")


def test_draw_vertical_division_layout():
    from mathgen.output.fonts import register_fonts as rf
    c = canvas.Canvas(BytesIO(), pagesize=A4)
    font = rf()
    c.setFont(font, 13)
    layout = {"kind": "vertical", "op": "÷", "divisor": "6",
              "dividend": "42", "quotient": "7", "remainder": "0"}
    used = _draw_vertical(c, 40, 700, layout, font, 13)
    assert used > 0


def test_font_register_returns_name():
    assert isinstance(register_fonts(), str) and len(register_fonts()) > 0



class _RecordingCanvas:
    def __init__(self):
        self.lines = []
        self.strings = []

    def setFont(self, *args):
        pass

    def drawString(self, x, y, text):
        self.strings.append((x, y, text))

    def drawRightString(self, x, y, text):
        self.strings.append((x, y, text))

    def line(self, x1, y1, x2, y2):
        self.lines.append((x1, y1, x2, y2))

    def stringWidth(self, text, font, size):
        return len(text) * size


def test_answer_rules_share_question_to_rule_pitch():
    cfg = resolve(Config(grade=1, topic="arithmetic", gap=0, answer_lines=3))
    q = Question(topic="arithmetic", statement="2 + 3 = ____", answer="5", expression="2 + 3")
    c = _RecordingCanvas()
    pdf_module._draw_item(c, 50, 700, 1, q, cfg, "Helvetica", 13, 220, ["1. 2 + 3 = ____"])
    rule_ys = [line[1] for line in c.lines]
    assert rule_ys == [672, 648, 624]
    assert (700 - 4) - rule_ys[0] == 24
    assert rule_ys[0] - rule_ys[1] == 24
    assert rule_ys[1] - rule_ys[2] == 24
    assert c.lines[0][0] == 60
    assert c.lines[0][2] == 260



def test_gap_is_evenly_distributed_across_answer_intervals():
    import pytest

    cfg = resolve(Config(grade=1, topic="arithmetic", gap=20, answer_lines=3))
    q = Question(topic="arithmetic", statement="2 + 3 = ____", answer="5", expression="2 + 3")
    c = _RecordingCanvas()
    pdf_module._draw_item(c, 50, 700, 1, q, cfg, "Helvetica", 13, 220, ["1. 2 + 3 = ____"])
    rule_ys = [line[1] for line in c.lines]
    pitch = 24 + 20 / 3
    assert (700 - 4) - rule_ys[0] == pytest.approx(pitch)
    assert rule_ys[0] - rule_ys[1] == pytest.approx(pitch)
    assert rule_ys[1] - rule_ys[2] == pytest.approx(pitch)


def test_single_answer_line_gets_all_gap():
    cfg = resolve(Config(grade=1, topic="arithmetic", gap=20, answer_lines=1))
    q = Question(topic="arithmetic", statement="2 + 3 = ____", answer="5", expression="2 + 3")
    c = _RecordingCanvas()
    pdf_module._draw_item(c, 50, 700, 1, q, cfg, "Helvetica", 13, 220, ["1. 2 + 3 = ____"])
    assert (700 - 4) - c.lines[0][1] == 44


def test_wrapped_question_rules_start_after_last_line():
    cfg = resolve(Config(grade=1, topic="arithmetic", gap=0, answer_lines=2))
    q = Question(topic="arithmetic", statement="long question", answer="5", expression="2 + 3")
    c = _RecordingCanvas()
    pdf_module._draw_item(c, 50, 700, 1, q, cfg, "Helvetica", 13, 220,
                          ["1. long question", "continued"])
    rule_ys = [line[1] for line in c.lines]
    assert rule_ys == [658, 634]
    assert (700 - 4 - 14) - rule_ys[0] == 24


def test_vertical_rules_start_after_calculation_bottom():
    cfg = resolve(Config(grade=1, topic="vertical", gap=0, answer_lines=2))
    q = Question(topic="vertical", statement="12 + 34", answer="46", expression="12 + 34",
                 layout={"kind": "vertical", "op": "+", "numbers": ["12", "34"]})
    c = _RecordingCanvas()
    pdf_module._draw_item(c, 50, 700, 1, q, cfg, "Helvetica", 13, 220, None)
    rule_ys = [line[1] for line in c.lines]
    calculation_bottom, first_rule, second_rule = rule_ys
    assert calculation_bottom - first_rule == 24
    assert first_rule - second_rule == 24


def test_extreme_gap_and_many_lines_keep_rules_on_page():
    fresh_top = A4[1] - pdf_module.MARGIN - 40  # 新页页顶，模拟 ensure_space 换页后
    for gap, lines_n in [(800, 1), (0, 30), (1000, 3), (0, 60)]:
        cfg = resolve(Config(grade=1, topic="arithmetic",
                             gap=gap, answer_lines=lines_n))
        q = Question(topic="arithmetic", statement="2 + 3 = ____", answer="5",
                     expression="2 + 3")
        ys = pdf_module._answer_rule_ys(fresh_top, q, ["1. 2 + 3 = ____"], 13, cfg)
        assert len(ys) == lines_n
        assert all(y >= pdf_module.MARGIN - 0.01 for y in ys), (gap, lines_n)


def test_gap_and_answer_lines_render():
    cfg = resolve(Config(grade=1, topic="arithmetic", count=6, seed=2, gap=40, answer_lines=3))
    data = render_pdf(generate(cfg), cfg)
    assert data[:4] == b"%PDF"


def test_multi_page_mixed_row_layout():
    cfg = resolve(Config(grade=5, topic="vertical", count=40, seed=3, answer_lines=2))
    data = render_pdf(generate(cfg), cfg)
    assert data[:4] == b"%PDF"
    assert data.rstrip().endswith(b"%%EOF")


def _extract_lines(data: bytes) -> list[tuple[float, float, str]]:
    """提取题目页文本行（若最后一页是答案页则丢弃）。"""
    from pypdf import PdfReader
    pages = PdfReader(BytesIO(data)).pages
    page_texts = [p.extract_text() or "" for p in pages]
    drop_last = len(pages) > 1 and ("Answers" in page_texts[-1] or "参考答案" in page_texts[-1])
    max_page = len(pages) - (1 if drop_last else 0)
    pts = []
    for pno, page in enumerate(pages[:max_page]):
        def visit(text, cm, tm, font, size):
            x, y = tm[4], tm[5]
            for line in text.splitlines():
                if line.strip():
                    pts.append((round(x, 1), round(y, 1), line.strip()))
        page.extract_text(visitor_text=visit)
    return pts


def test_english_word_problems_wrap_no_overlap():
    import re
    cfg = resolve(Config(grade=1, topic="word_problem", count=12, columns=2,
                         lang="en", seed=71))
    qs = generate(cfg)
    pts = _extract_lines(render_pdf(qs, cfg))
    question_lines = [(x, y, t) for x, y, t in pts if re.match(r"^\d+\.", t)]
    assert len(question_lines) == len(qs), "题目首行数应等于题数"
    # 换行发生：总文本行数明显多于题数
    assert len(pts) > len(qs) * 2, f"英文应用题应多行换行，实际行数 {len(pts)}"
    width, _ = A4
    margin = 51.0  # 18mm
    col_w = (width - 2 * margin) / 2
    for x, y, t in question_lines:
        assert x < width - margin + 2, (x, t)
        assert x < margin + col_w + 2 or x >= margin + col_w - 2, (x, t)
    # 无重叠：同行两列允许同 y（异列），但同 y 的 x 必须属不同列区间
    ys = sorted(set(y for _, y, _ in question_lines))
    for y in ys:
        xs = sorted(x for x, yy, _ in question_lines if yy == y)
        for a, b in zip(xs, xs[1:]):
            assert b - a >= col_w - 4, f"同 y={y} 相邻 x 差 {b - a} < 列宽，疑似重叠"


def test_column_major_numbering_continuous_across_pages():
    import re
    cfg = resolve(Config(grade=1, count=16, columns=2, seed=72,
                         number_direction="column"))
    qs = generate(cfg)
    assert len(qs) == 16
    pts = _extract_lines(render_pdf(qs, cfg))
    margin = 51.0
    col_w = (A4[0] - 2 * margin) / 2
    col0 = sorted(int(re.match(r"(\d+)\.", t).group(1))
                  for x, y, t in pts if x < margin + col_w / 2 and re.match(r"^\d+\.", t))
    col1 = sorted(int(re.match(r"(\d+)\.", t).group(1))
                  for x, y, t in pts if x >= margin + col_w / 2 and re.match(r"^\d+\.", t))
    assert col0 == list(range(1, 9)), f"左列应连续 1-8: {col0}"
    assert col1 == list(range(9, 17)), f"右列应连续 9-16: {col1}"
