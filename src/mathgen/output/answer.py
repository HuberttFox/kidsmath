"""答案页行生成。"""
from __future__ import annotations

from mathgen.core.question import Question


def answer_lines(questions: list[Question]) -> list[str]:
    return [f"{q.expression} = {q.answer}" for q in questions]
