"""reportlab A4 卷子渲染：行式分栏布局/标题/页眉/间距/答题线/答案页/竖式。"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from mathgen.config import ResolvedConfig
from mathgen.core.question import Question
from mathgen.output.answer import answer_lines
from mathgen.output.fonts import register_fonts
from mathgen.output.text import arrange

MARGIN = 18 * mm
LINE_GAP = 16
GUTTER = 26  # 编号与竖式题内容之间的固定间距 (pt)，保证列内数字对齐
SIZE = 13
LINE_H = 14
STEP_SIZE = 8.5     # 答案页解题步骤字号
STEP_LEADING = 10   # 解题步骤行距（尽量让整页答案不因步骤翻页）
STEP_GAP = 6        # 步骤块与下一条答案基线间距（≥ 答案字上升部，防重叠）
STEPS_INDENT = 18   # 解题步骤相对答案行的缩进
STEPS_COLOR = colors.Color(0.42, 0.38, 0.33)  # 答案页步骤的柔和棕灰色


def _wrap_text(text: str, font: str, size: int, max_w: float) -> list[str]:
    """逐词换行：按字体宽度把 text 拆为不超过 max_w 的多行。"""
    if pdfmetrics.stringWidth(text, font, size) <= max_w:
        return [text]
    lines: list[str] = []
    cur = ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if pdfmetrics.stringWidth(trial, font, size) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [text]


def _draw_vertical(c, x, y, layout, font, size) -> float:
    """绘制竖式（数字右对齐、符号贴数字块、除法按教材格式），返回占用高度。"""
    if layout["op"] == "÷":
        divisor = layout["divisor"]
        dividend = layout["dividend"]
        quotient = layout["quotient"]
        w_d = c.stringWidth(dividend, font, size)
        bracket_x = x + 0.9 * size  # 除数占位
        bar_y = y - 1.5 * size
        # 商：右对齐到被除数右端，位于横线上方
        c.drawRightString(bracket_x + w_d, y - size, quotient)
        # 横线（厂字上横）
        c.line(bracket_x, bar_y, bracket_x + w_d, bar_y)
        # 除数：右对齐到括号竖线左缘
        c.drawRightString(bracket_x - 0.25 * size, bar_y - size, divisor)
        # 括号竖线
        c.line(bracket_x, bar_y, bracket_x, bar_y - 2 * size)
        # 被除数：括号内右对齐
        c.drawRightString(bracket_x + w_d, bar_y - 0.75 * size, dividend)
        return 4 * size + LINE_GAP
    numbers = layout["numbers"]
    op = layout["op"]
    width = max(c.stringWidth(n, font, size) for n in numbers)
    w_first = c.stringWidth(numbers[0], font, size)
    line_y = y - (len(numbers) + 0.5) * size
    # 符号右缘贴首个数字左缘
    c.drawRightString(x + width - w_first - 0.4 * size, y - size, op)
    for i, n in enumerate(numbers):
        c.drawRightString(x + width, y - (i + 1) * size, n)
    c.line(x + width - w_first, line_y, x + width, line_y)
    return y - line_y + LINE_GAP


def _text_lines(q: Question, text: str, font: str, size: int, col_w: float) -> list[str] | None:
    """文字题的换行行列表；竖式返回 None。单行超宽（长单词）降 12pt 再换行。"""
    if q.layout and q.layout.get("kind") == "vertical":
        return None
    lines = _wrap_text(text, font, size, col_w - GUTTER)
    if len(lines) == 1 and pdfmetrics.stringWidth(text, font, size) > col_w - GUTTER:
        lines = _wrap_text(text, font, 12, col_w - GUTTER)
    return lines


def _item_height(q: Question, lines: list[str] | None, size: int) -> float:
    if lines is None:
        return 4 * size + LINE_GAP
    return len(lines) * LINE_H + 8


def _answer_area(cfg: ResolvedConfig) -> float:
    return 14 * cfg.answer_lines + 6 if cfg.answer_lines > 0 else 0


def _draw_item(c, x, top, row_h, idx, q, cfg, font, size, col_w, lines) -> None:
    if q.layout and q.layout.get("kind") == "vertical":
        c.setFont(font, size)
        if cfg.show_numbers:
            c.drawString(x, top - 2, f"{idx}.")
            _draw_vertical(c, x + GUTTER, top - 2, q.layout, font, size)
        else:
            _draw_vertical(c, x, top - 2, q.layout, font, size)
    else:
        fs = 12 if (len(lines) > 1 and pdfmetrics.stringWidth(
            lines[0], font, size) > col_w - GUTTER) else size
        c.setFont(font, fs)
        for li, line in enumerate(lines):
            c.drawString(x, top - 4 - li * LINE_H, line)
        c.setFont(font, size)
    if cfg.answer_lines > 0:
        for i in range(cfg.answer_lines):
            line_y = top - row_h + 8 + i * 14
            c.line(x, line_y, x + col_w - 8, line_y)


def render_pdf(questions: list[Question], cfg: ResolvedConfig) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    font = register_fonts()
    width, height = A4
    c.setFont(font, 16)

    def draw_header() -> None:
        c.setFont(font, 16)
        c.drawCentredString(width / 2, height - MARGIN, cfg.title)
        c.setFont(font, 11)
        c.drawString(MARGIN, height - MARGIN - 18, cfg.header)

    draw_header()
    top = height - MARGIN - 40
    ncols = cfg.columns
    col_w = (width - 2 * MARGIN) / ncols
    c.setFont(font, SIZE)

    def ensure_space(needed: float) -> None:
        nonlocal top
        if top - needed < MARGIN:
            c.showPage()
            nonlocal_page()
            c.setFont(font, SIZE)

    def nonlocal_page() -> None:
        nonlocal top
        top = height - MARGIN - 40
        draw_header()

    rows = arrange(questions, ncols, cfg.number_direction)
    numbers = {id(q): i for i, q in enumerate(questions, 1)}
    lines_map = {}
    for q in questions:
        text = f"{numbers[id(q)]}. {q.statement}" if cfg.show_numbers else q.statement
        lines_map[id(q)] = _text_lines(q, text, font, SIZE, col_w)
    for row in rows:
        items = [q for q in row if q is not None]
        if not items:
            continue
        row_h = max(_item_height(q, lines_map[id(q)], SIZE) for q in items) + _answer_area(cfg)
        if top - row_h < MARGIN:
            ensure_space(row_h)
        for j, q in enumerate(row):
            if q is None:
                continue
            x = MARGIN + j * col_w
            _draw_item(c, x, top, row_h, numbers[id(q)], q, cfg, font, SIZE, col_w,
                       lines_map[id(q)])
        top -= row_h + cfg.gap

    if cfg.answer_page:
        c.showPage()

        def answer_header() -> None:
            c.setFont(font, 16)
            c.drawCentredString(width / 2, height - MARGIN,
                                "Answers" if cfg.lang == "en" else "参考答案")
            c.setFont(font, SIZE)

        answer_header()
        y = height - MARGIN - 40
        lines = answer_lines(questions)
        for i, line in enumerate(lines, 1):
            if y - SIZE < MARGIN:
                c.showPage()
                answer_header()
                y = height - MARGIN - 40
            c.drawString(MARGIN, y, f"{i}. {line}")
            q = questions[i - 1]
            if q.steps:
                # 步骤块上下各留 16pt（= STEP_LEADING + STEP_GAP）：末步→下条答案
                # 与答案→首步对称，避免答案字形上升部（≈11.44pt）与步骤重叠，且每条
                # 带步骤的答案总高与旧版一致（16+2×10+6=42），答案页不会因此多翻一页
                y -= STEP_LEADING + STEP_GAP
                c.setFont(font, STEP_SIZE)
                c.setFillColor(STEPS_COLOR)
                for s in q.steps:
                    if y - STEP_SIZE < MARGIN:
                        c.showPage()
                        answer_header()
                        c.setFont(font, STEP_SIZE)
                        c.setFillColor(STEPS_COLOR)
                        y = height - MARGIN - 40
                    c.drawString(MARGIN + STEPS_INDENT, y, s)
                    y -= STEP_LEADING
                y -= STEP_GAP
                c.setFont(font, SIZE)
                c.setFillColor(colors.black)
            else:
                y -= 22
    c.save()
    return buf.getvalue()
