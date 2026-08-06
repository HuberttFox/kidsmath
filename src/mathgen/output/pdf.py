"""reportlab A4 卷子渲染：标题/页眉/分栏/间距/答题线/答案页/竖式。"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from mathgen.config import ResolvedConfig
from mathgen.core.question import Question
from mathgen.output.answer import answer_lines
from mathgen.output.fonts import register_fonts

MARGIN = 18 * mm
LINE_GAP = 16


def _draw_vertical(c, x, y, layout, font, size) -> float:
    """绘制竖式，返回占用高度。"""
    if layout["op"] == "÷":
        divisor = layout["divisor"]
        dividend = layout["dividend"]
        w_d = c.stringWidth(dividend, font, size)
        top = y
        c.drawString(x, top - size, quotient := layout["quotient"])
        c.line(x, top - 1.5 * size, x + w_d + 2 * size, top - 1.5 * size)
        c.drawString(x + 1.6 * size, top - 1.5 * size - size, divisor)
        c.rect(x + 1.2 * size, top - 3.5 * size, w_d + 0.8 * size, 2.2 * size)
        c.drawString(x + 1.6 * size, top - 2.9 * size, dividend)
        return 4 * size + LINE_GAP
    numbers = layout["numbers"]
    op = layout["op"]
    width = max(c.stringWidth(n, font, size) for n in numbers)
    line_y = y - (len(numbers) + 0.5) * size
    c.drawString(x, y - size, op)
    for i, n in enumerate(numbers):
        c.drawRightString(x + width, y - (i + 1) * size, n)
    c.line(x, line_y, x + width, line_y)
    return y - line_y + LINE_GAP


def render_pdf(questions: list[Question], cfg: ResolvedConfig) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    font = register_fonts()
    width, height = A4
    c.setFont(font, 16)
    c.drawCentredString(width / 2, height - MARGIN, cfg.title)
    c.setFont(font, 11)
    c.drawString(MARGIN, height - MARGIN - 18, cfg.header)
    top = height - MARGIN - 40
    ncols = cfg.columns
    col_w = (width - 2 * MARGIN) / ncols

    page = 1
    c.setFont(font, 13)

    def ensure_space(needed: float) -> None:
        nonlocal top
        if top - needed < MARGIN:
            c.showPage()
            c.setFont(font, 13)
            nonlocal_page()

    def nonlocal_page() -> None:
        nonlocal page, top
        page += 1
        top = height - MARGIN

    for idx, q in enumerate(questions, 1):
        col = (idx - 1) % ncols
        x = MARGIN + col * col_w
        if q.layout and q.layout.get("kind") == "vertical":
            if top - 60 < MARGIN:
                ensure_space(60)
            c.setFont(font, 13)
            c.drawString(x, top - 2, f"{idx}.")
            _draw_vertical(c, x + 20, top - 2, q.layout, font, 13)
            top -= 60
        else:
            text = f"{idx}. {q.statement}"
            if c.stringWidth(text, font, 13) > col_w:
                c.setFont(font, 12)
            if top - 22 < MARGIN:
                ensure_space(22)
            c.drawString(x, top - 4, text)
            c.setFont(font, 13)
            top -= 22
        if cfg.answer_lines > 0:
            for i in range(cfg.answer_lines):
                line_y = top - 6 - i * 14
                if line_y < MARGIN:
                    ensure_space(60)
                    c.setFont(font, 13)
                    line_y = top - 6
                c.line(x, line_y, x + col_w - 8, line_y)
            top -= 14 * cfg.answer_lines + 6
        top -= cfg.gap

    if cfg.answer_page:
        c.showPage()
        c.setFont(font, 16)
        c.drawCentredString(width / 2, height - MARGIN, "参考答案")
        c.setFont(font, 13)
        y = height - MARGIN - 40
        for i, line in enumerate(answer_lines(questions), 1):
            if y < MARGIN:
                c.showPage()
                c.setFont(font, 13)
                y = height - MARGIN
            c.drawString(MARGIN, y, f"{i}. {line}")
            y -= 22
    c.save()
    return buf.getvalue()
