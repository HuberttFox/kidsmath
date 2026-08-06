"""纯文本渲染（调试/CLI 预览）。"""
from __future__ import annotations

from mathgen.config import ResolvedConfig
from mathgen.core.question import Question


def group_rows(questions: list[Question], ncols: int) -> list[list[Question]]:
    """按分栏数把题目分组为行，PDF 与网页预览共用，保证分栏同行对齐。"""
    return [questions[i:i + ncols] for i in range(0, len(questions), ncols)]


def render_text(questions: list[Question], cfg: ResolvedConfig) -> str:
    lines = [f"【{cfg.title}】", cfg.header, ""]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q.statement}")
    return "\n".join(lines)
