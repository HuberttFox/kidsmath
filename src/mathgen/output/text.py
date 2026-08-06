"""纯文本渲染（调试/CLI 预览）。"""
from __future__ import annotations

from mathgen.config import ResolvedConfig
from mathgen.core.question import Question


def render_text(questions: list[Question], cfg: ResolvedConfig) -> str:
    lines = [f"【{cfg.title}】", cfg.header, ""]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q.statement}")
    return "\n".join(lines)
