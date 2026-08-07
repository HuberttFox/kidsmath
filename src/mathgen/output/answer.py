"""答案页行生成。"""
from __future__ import annotations

from mathgen.core.question import Question


def answer_lines(questions: list[Question]) -> list[str]:
    return [f"{q.expression if q.expression else q.statement} = {q.answer}" for q in questions]
