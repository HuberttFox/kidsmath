"""纯文本渲染（调试/CLI 预览）。"""
from __future__ import annotations

import math

from mathgen.config import ResolvedConfig
from mathgen.core.question import Question


def arrange(questions: list[Question], ncols: int,
            direction: str = "row") -> list[list[Question | None]]:
    """按分栏数与编号方向把题目排成行。

    row（横向）：1 2 / 3 4；column（竖向，列优先）：1 3 / 2 4。
    尾行不足处以 None 补齐。PDF 与网页预览共用。
    """
    if direction != "column":
        return [list(questions[i:i + ncols]) for i in range(0, len(questions), ncols)]
    rows_per_col = math.ceil(len(questions) / ncols)
    grid: list[list[Question | None]] = [[None] * ncols for _ in range(rows_per_col)]
    for idx, q in enumerate(questions):
        grid[idx % rows_per_col][idx // rows_per_col] = q
    return grid


def group_rows(questions: list[Question], ncols: int) -> list[list[Question]]:
    """兼容旧接口：横向排列（= arrange(row)）。"""
    return [r for r in arrange(questions, ncols, "row") if r]


def render_text(questions: list[Question], cfg: ResolvedConfig) -> str:
    lines = [f"【{cfg.title}】", cfg.header, ""]
    for i, q in enumerate(questions, 1):
        prefix = f"{i}. " if cfg.show_numbers else ""
        lines.append(f"{prefix}{q.statement}")
    return "\n".join(lines)
