from mathgen.config import Config, resolve
from mathgen.core.engine import generate
from mathgen.core.question import Question
from mathgen.output.fonts import register_fonts
from mathgen.output.pdf import render_pdf, _draw_vertical

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


def test_gap_and_answer_lines_render():
    cfg = resolve(Config(grade=1, topic="arithmetic", count=6, seed=2, gap=40, answer_lines=3))
    data = render_pdf(generate(cfg), cfg)
    assert data[:4] == b"%PDF"
