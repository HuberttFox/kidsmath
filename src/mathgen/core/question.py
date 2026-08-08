from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Question:
    """一道题。expression 为规范化算式（供去重/答案页），layout 供竖式等排版。"""

    topic: str
    statement: str
    answer: str
    expression: str
    layout: dict | None = field(default=None)
    steps: list[str] | None = field(default=None)
